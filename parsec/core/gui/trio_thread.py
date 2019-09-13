# Parsec Cloud (https://parsec.cloud) Copyright (c) AGPLv3 2019 Scille SAS

from contextlib import contextmanager
import trio
import threading
from inspect import iscoroutinefunction
from structlog import get_logger
from parsec.utils import trio_run
from parsec.core.fs import FSError
from PyQt5.QtCore import pyqtBoundSignal, Q_ARG, QMetaObject, Qt


logger = get_logger()


def split_multi_error(exc):
    def is_cancelled(exc):
        return exc if isinstance(exc, trio.Cancelled) else None

    def not_cancelled(exc):
        return None if isinstance(exc, trio.Cancelled) else exc

    cancelled_errors = trio.MultiError.filter(is_cancelled, exc)
    other_exceptions = trio.MultiError.filter(not_cancelled, exc)
    return cancelled_errors, other_exceptions


class JobResultError(Exception):
    def __init__(self, status, **kwargs):
        self.status = status
        self.params = kwargs


class ThreadSafeQtSignal:
    def __init__(self, qobj, signal_name, *args_types):
        signal = getattr(qobj, signal_name)
        assert isinstance(signal, pyqtBoundSignal)
        self.qobj = qobj
        self.signal_name = signal_name
        self.args_types = args_types

    def emit(self, *args):
        assert len(self.args_types) == len(args)
        cooked_args = [Q_ARG(t, v) for t, v in zip(self.args_types, args)]
        QMetaObject.invokeMethod(self.qobj, self.signal_name, Qt.QueuedConnection, *cooked_args)


class QtToTrioJob:
    def __init__(self, portal, fn, args, kwargs, qt_on_success, qt_on_error):
        self._portal = portal
        assert isinstance(qt_on_success, ThreadSafeQtSignal)
        assert qt_on_success.args_types in ((), (QtToTrioJob,))
        self._qt_on_success = qt_on_success
        assert isinstance(qt_on_error, ThreadSafeQtSignal)
        assert qt_on_error.args_types in ((), (QtToTrioJob,))
        self._qt_on_error = qt_on_error
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self.cancel_scope = None
        self._started = trio.Event()
        self._done = threading.Event()
        self.status = None
        self.ret = None
        self.exc = None

    def __str__(self):
        return f"{self._fn.__name__}"

    def is_finished(self):
        return self._done.is_set()

    def is_cancelled(self):
        return self.status == "cancelled"

    def is_ok(self):
        return self.status == "ok"

    def is_errored(self):
        return self.status == "ko"

    def is_crashed(self):
        return self.status == "crashed"

    async def _run_fn(self, *, task_status=trio.TASK_STATUS_IGNORED):
        with trio.CancelScope() as self.cancel_scope:
            task_status.started()
            self._started.set()

            try:
                if not iscoroutinefunction(self._fn):
                    result = self._fn(*self._args, **self._kwargs)
                else:
                    result = await self._fn(*self._args, **self._kwargs)
                self.set_result(result)

            except Exception as exc:
                self.set_exception(exc)

            except trio.Cancelled as exc:
                self.set_cancelled(exc)
                raise

            except trio.MultiError as exc:
                cancelled_errors, other_exceptions = split_multi_error(exc)
                if other_exceptions:
                    self.set_exception(other_exceptions)
                else:
                    self.set_cancelled(cancelled_errors)
                if cancelled_errors:
                    raise cancelled_errors

    def set_result(self, result):
        self.status = "ok"
        self.ret = result
        self._set_done()

    def set_cancelled(self, exc):
        self.status = "cancelled"
        self.exc = exc
        self._set_done()

    def set_exception(self, exc):
        if isinstance(exc, JobResultError):
            self.status = exc.status
            self.exc = exc
        elif isinstance(exc, FSError):
            self.status = "ko"
            self.exc = exc
        else:
            logger.exception("Uncatched error", exc_info=exc)
            wrapped = JobResultError("crashed", exc=exc, info=f"Unexpected error: {repr(exc)}")
            wrapped.__traceback__ = exc.__traceback__
            self.status = wrapped.status
            self.exc = wrapped
        self._set_done()

    def _set_done(self):
        self._done.set()
        signal = self._qt_on_success if self.is_ok() else self._qt_on_error
        signal.emit(self) if signal.args_types else signal.emit()

    def cancel_and_join(self):
        assert self.cancel_scope
        try:
            self._portal.run_sync(self.cancel_scope.cancel)
        except trio.RunFinishedError:
            pass
        self._done.wait()


class QtToTrioJobScheduler:
    def __init__(self):
        self._portal = None
        self._cancel_scope = None
        self.started = threading.Event()
        self._stopped = trio.Event()

    async def _start(self, *, task_status=trio.TASK_STATUS_IGNORED):
        assert not self.started.is_set()
        self._portal = trio.BlockingTrioPortal()
        self._send_job_channel, recv_job_channel = trio.open_memory_channel(1)
        try:
            async with trio.open_nursery() as nursery, recv_job_channel:
                self._cancel_scope = nursery.cancel_scope
                self.started.set()
                task_status.started()
                while True:
                    job = await recv_job_channel.receive()
                    assert job.status is None
                    await nursery.start(job._run_fn)

        finally:
            self._stopped.set()

    async def _stop(self):
        self._cancel_scope.cancel()
        await self._send_job_channel.aclose()
        await self._stopped.wait()

    def stop(self):
        try:
            self._portal.run(self._stop)
        except trio.RunFinishedError:
            pass

    def is_stopped(self):
        return self._stopped.is_set()

    def submit_job(self, qt_on_success, qt_on_error, fn, *args, **kwargs):
        # Fool-proof sanity check, signals must be wrapped in `ThreadSafeQtSignal`
        assert not [x for x in args if isinstance(x, pyqtBoundSignal)]
        assert not [v for v in kwargs.values() if isinstance(v, pyqtBoundSignal)]
        job = QtToTrioJob(self._portal, fn, args, kwargs, qt_on_success, qt_on_error)

        async def _submit_job():
            # While inside this async function we are blocking the Qt thread
            # hence we just wait for the job to start (to avoid concurrent
            # crash if the job is cancelled)
            await self._send_job_channel.send(job)
            await job._started.wait()

        try:
            self._portal.run(_submit_job)

        except trio.BrokenResourceError as exc:
            logger.info(f"The submitted job `{job}` won't run as the scheduler is stopped")
            job.set_cancelled(exc)

        except trio.RunFinishedError as exc:
            logger.info(f"The submitted job `{job}` won't run as the trio loop is not running")
            job.set_cancelled(exc)

        return job

    # This method is only here for legacy purposes.
    # It shouldn't NOT be used as running an async job synchronously
    # might block the Qt loop for too long and cause the application
    # to freeze. TODO: remove it later

    def run(self, afn, *args):
        if self.is_stopped():
            raise RuntimeError("The job scheduler is stopped")
        return self._portal.run(afn, *args)

    # In contrast to the `run` method, it is acceptable to block
    # the Qt loop while waiting for a synchronous job to finish
    # as it shouldn't take too long (it might simply wait for
    # a few scheduled trio task steps to finish). However,
    # it shouln't be used too aggressively as it might still slow
    # down the application.

    def run_sync(self, fn, *args):
        if self.is_stopped():
            raise RuntimeError("The job scheduler is stopped")
        return self._portal.run_sync(fn, *args)


# TODO: Running the trio loop in a QThread shouldn't be needed
# make sure it's the case, then remove this dead code
# class QtToTrioJobSchedulerThread(QThread):
#     def __init__(self, job_scheduler):
#         super().__init__()
#         self.job_scheduler = job_scheduler

#     def run(self):
#         trio_run(self.job_scheduler._start)


@contextmanager
def run_trio_thread():
    job_scheduler = QtToTrioJobScheduler()
    thread = threading.Thread(target=trio_run, args=[job_scheduler._start])
    thread.setName("TrioLoop")
    thread.start()
    # thread = QtToTrioJobSchedulerThread(job_scheduler)
    # thread.start()
    job_scheduler.started.wait()

    try:
        yield job_scheduler

    finally:
        job_scheduler.stop()
        thread.join()
        # thread.wait()
