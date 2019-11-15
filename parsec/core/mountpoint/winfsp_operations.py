# Parsec Cloud (https://parsec.cloud) Copyright (c) AGPLv3 2019 Scille SAS

import re
import functools
from contextlib import contextmanager
from trio import Cancelled, RunFinishedError
from structlog import get_logger
from winfspy import (
    NTStatusError,
    BaseFileSystemOperations,
    FILE_ATTRIBUTE,
    CREATE_FILE_CREATE_OPTIONS,
)
from winfspy.plumbing.winstuff import dt_to_filetime, NTSTATUS, SecurityDescriptor

from parsec.core.types import FsPath
from parsec.core.fs import FSLocalOperationError, FSRemoteOperationError
from parsec.core.fs.workspacefs.sync_transactions import DEFAULT_BLOCK_SIZE


logger = get_logger()

# Taken from https://docs.microsoft.com/en-us/windows/win32/fileio/file-access-rights-constants
FILE_READ_DATA = 1 << 0
FILE_WRITE_DATA = 1 << 1


# https://docs.microsoft.com/en-us/windows/win32/fileio/naming-a-file
# tl;dr: https://twitter.com/foone/status/1058676834940776450
_WIN32_RES_CHARS = tuple(chr(x) for x in range(1, 32)) + (
    "<",
    ">",
    ":",
    '"',
    "\\",
    "|",
    "?",
    "*",
)  # Ignore `\`
_WIN32_RES_NAMES = (
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
)


def winify_entry_name(name: str) -> str:
    logger.warning("winify_entry_name:", name=repr(name))
    prefix, *suffixes = name.split(".", 1)
    if prefix in _WIN32_RES_NAMES:
        full_suffix = f".{'.'.join(suffixes)}" if suffixes else ""
        name = f"{prefix[:-1]}~{ord(prefix[-1]):02x}{full_suffix}"

    else:
        for reserved in _WIN32_RES_CHARS:
            name = name.replace(reserved, f"~{ord(reserved):02x}")

    if name[-1] in (".", " "):
        name = f"{name[:-1]}~{ord(name[-1]):02x}"
    logger.warning("winified_entry_name==>", name=repr(name))

    return name


def unwinify_entry_name(name: str) -> str:
    # Given / is not allowed, no need to check if path already contains it
    if "~" not in name:
        return name

    else:
        logger.warning("unwinify_entry_name:", name=name)
        *to_convert_parts, last_part = re.split(r"(~[0-9A-Fa-f]{2})", name)
        logger.warning("xxx:", to_convert_parts=to_convert_parts, last_part=last_part)
        converted_parts = []
        is_escape = False
        for part in to_convert_parts:
            logger.warning("txt, escape:", part=part)
            if is_escape:
                converted_chr = chr(int(part[1:], 16))
                if converted_chr in ("/", "\x00"):
                    raise ValueError("Invalid escaped value")
                converted_parts.append(converted_chr)

            else:
                converted_parts.append(part)

            is_escape = not is_escape

        converted_parts.append(last_part)
        return "".join(converted_parts)

        # for txt, escape in parts[:-1]:
        #     converted_chr = chr(int(escape[1:], 16))
        #     if converted_chr in ("/", "\x00"):
        #         raise ValueError("Invalid escaped value")
        #     converted_parts.append(converted_chr)
        # converted_parts.append(parts[-1])
        # return "".join(converted_parts)


def _winpath_to_parsec(path: str) -> FsPath:
    # Given / is not allowed, no need to check if path already contains it
    return FsPath(unwinify_entry_name(path.replace("\\", "/")))


def _parsec_to_winpath(path: FsPath) -> str:
    return "\\" + "\\".join(winify_entry_name(entry) for entry in path.parts)


@contextmanager
def translate_error(event_bus, operation, path):
    try:
        yield

    except NTStatusError:
        raise

    except FSLocalOperationError as exc:
        raise NTStatusError(exc.ntstatus) from exc

    except FSRemoteOperationError as exc:
        event_bus.send("mountpoint.remote_error", exc=exc, operation=operation, path=path)
        raise NTStatusError(exc.ntstatus) from exc

    except (Cancelled, RunFinishedError) as exc:
        # WinFSP teardown operation doesn't make sure no concurrent operation
        # are running
        raise NTStatusError(NTSTATUS.STATUS_NO_SUCH_DEVICE) from exc

    except Exception as exc:
        logger.exception("Unhandled exception in winfsp mountpoint", operation=operation, path=path)
        event_bus.send("mountpoint.unhandled_error", exc=exc, operation=operation, path=path)
        raise NTStatusError(NTSTATUS.STATUS_INTERNAL_ERROR) from exc


def round_to_block_size(size, block_size=DEFAULT_BLOCK_SIZE):
    if size % block_size == 0:
        return size
    return ((size // block_size) + 1) * block_size


def stat_to_file_attributes(stat):
    # TODO: consider using FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS/FILE_ATTRIBUTE_RECALL_ON_OPEN ?
    # (see https://docs.microsoft.com/en-us/windows/desktop/fileio/file-attribute-constants)
    if stat["type"] == "folder":
        return FILE_ATTRIBUTE.FILE_ATTRIBUTE_DIRECTORY
    else:
        return FILE_ATTRIBUTE.FILE_ATTRIBUTE_NORMAL


def stat_to_winfsp_attributes(stat):
    created = dt_to_filetime(stat["created"])
    updated = dt_to_filetime(stat["updated"])
    attributes = {
        "creation_time": created,
        "last_access_time": updated,
        "last_write_time": updated,
        "change_time": updated,
        "index_number": stat["id"].int & 0xFFFFFFFF,  # uint64_t
    }

    if stat["type"] == "folder":
        attributes["file_attributes"] = FILE_ATTRIBUTE.FILE_ATTRIBUTE_DIRECTORY
        attributes["allocation_size"] = 0
        attributes["file_size"] = 0

    else:
        attributes["file_attributes"] = FILE_ATTRIBUTE.FILE_ATTRIBUTE_NORMAL
        attributes["allocation_size"] = round_to_block_size(stat["size"])
        attributes["file_size"] = stat["size"]

    return attributes


class OpenedFolder:
    def __init__(self, path):
        self.path = path
        self.deleted = False

    def is_root(self):
        return self.path.is_root()


class OpenedFile:
    def __init__(self, path, fd):
        self.path = path
        self.fd = fd
        self.deleted = False


def handle_error(func):
    """A decorator to handle error in wfspy operations"""
    operation = func.__name__

    @functools.wraps(func)
    def wrapper(self, arg, *args, **kwargs):
        path = arg.path if isinstance(arg, (OpenedFile, OpenedFolder)) else _winpath_to_parsec(arg)
        with translate_error(self.event_bus, operation, path):
            return func.__get__(self)(arg, *args, **kwargs)

    return wrapper


class WinFSPOperations(BaseFileSystemOperations):
    def __init__(self, event_bus, volume_label, fs_access):
        super().__init__()
        if len(volume_label) > 31:
            raise ValueError("`volume_label` must be 31 characters long max")

        # see https://docs.microsoft.com/fr-fr/windows/desktop/SecAuthZ/security-descriptor-string-format  # noqa
        self._security_descriptor = SecurityDescriptor(
            # "O:BAG:BAD:P(A;;FA;;;SY)(A;;FA;;;BA)(A;;FA;;;WD)"
            "O:BAG:BAD:NO_ACCESS_CONTROL"
        )
        self.event_bus = event_bus
        self.fs_access = fs_access

        max_file_nodes = 1024
        max_file_size = 16 * 1024 * 1024
        file_nodes = 1
        self._volume_info = {
            "total_size": max_file_nodes * max_file_size,
            "free_size": (max_file_nodes - file_nodes) * max_file_size,
            "volume_label": volume_label,
        }

    def get_volume_info(self):
        return self._volume_info

    def set_volume_label(self, volume_label):
        self._volume_info["volume_label"] = volume_label

    @handle_error
    def get_security_by_name(self, file_name):
        file_name = _winpath_to_parsec(file_name)
        stat = self.fs_access.entry_info(file_name)
        return (
            stat_to_file_attributes(stat),
            self._security_descriptor.handle,
            self._security_descriptor.size,
        )

    @handle_error
    def create(
        self,
        file_name,
        create_options,
        granted_access,
        file_attributes,
        security_descriptor,
        allocation_size,
    ):
        # `granted_access` is already handle by winfsp
        # `allocation_size` useless for us
        # `security_descriptor` is not supported yet
        file_name = _winpath_to_parsec(file_name)

        if create_options & CREATE_FILE_CREATE_OPTIONS.FILE_DIRECTORY_FILE:
            self.fs_access.folder_create(file_name)
            return OpenedFolder(file_name)

        else:
            _, fd = self.fs_access.file_create(file_name, open=True)
            return OpenedFile(file_name, fd)

    @handle_error
    def get_security(self, file_context):
        return self._security_descriptor.handle, self._security_descriptor.size

    @handle_error
    def set_security(self, file_context, security_information, modification_descriptor):
        # TODO
        pass

    @handle_error
    def rename(self, file_context, file_name, new_file_name, replace_if_exists):
        file_name = _winpath_to_parsec(file_name)
        new_file_name = _winpath_to_parsec(new_file_name)
        self.fs_access.entry_rename(file_name, new_file_name, overwrite=False)

    @handle_error
    def open(self, file_name, create_options, granted_access):
        file_name = _winpath_to_parsec(file_name)
        granted_access = granted_access & (FILE_READ_DATA | FILE_WRITE_DATA)
        if granted_access == FILE_READ_DATA:
            mode = "r"
        elif granted_access == FILE_WRITE_DATA:
            mode = "w"
        elif granted_access == FILE_READ_DATA | FILE_WRITE_DATA:
            mode = "rw"
        else:
            mode = "r"
        # `granted_access` is already handle by winfsp
        try:
            _, fd = self.fs_access.file_open(file_name, mode=mode)
            return OpenedFile(file_name, fd)
        except IsADirectoryError:
            return OpenedFolder(file_name)

    @handle_error
    def close(self, file_context):
        if isinstance(file_context, OpenedFile):
            self.fs_access.fd_close(file_context.fd)

        if file_context.deleted:
            if isinstance(file_context, OpenedFile):
                self.fs_access.file_delete(file_context.path)
            else:
                self.fs_access.folder_delete(file_context.path)

    @handle_error
    def get_file_info(self, file_context):
        stat = self.fs_access.entry_info(file_context.path)
        return stat_to_winfsp_attributes(stat)

    @handle_error
    def set_basic_info(
        self,
        file_context,
        file_attributes,
        creation_time,
        last_access_time,
        last_write_time,
        change_time,
        file_info,
    ) -> dict:
        # TODO

        # file_obj = file_context.file_obj
        # if file_attributes != FILE_ATTRIBUTE.INVALID_FILE_ATTRIBUTES:
        #     file_obj.file_attributes = file_attributes
        # if creation_time:
        #     file_obj.creation_time = creation_time
        # if last_access_time:
        #     file_obj.last_access_time = last_access_time
        # if last_write_time:
        #     file_obj.last_write_time = last_write_time
        # if change_time:
        #     file_obj.change_time = change_time

        return self.get_file_info(file_context)

    @handle_error
    def set_file_size(self, file_context, new_size, set_allocation_size):

        if not set_allocation_size:
            self.fs_access.fd_resize(file_context.fd, new_size)

    @handle_error
    def can_delete(self, file_context, file_name: str) -> None:
        self.fs_access.check_write_rights(file_context.path)
        stat = self.fs_access.entry_info(file_context.path)
        if stat["type"] == "file":
            return
        if file_context.is_root():
            # Cannot remove root mountpoint !
            raise NTStatusError(NTSTATUS.STATUS_RESOURCEMANAGER_READ_ONLY)
        if stat["children"]:
            raise NTStatusError(NTSTATUS.STATUS_DIRECTORY_NOT_EMPTY)

    @handle_error
    def read_directory(self, file_context, marker):
        stat = self.fs_access.entry_info(file_context.path)

        if stat["type"] == "file":
            raise NTStatusError(NTSTATUS.STATUS_NOT_A_DIRECTORY)

        entries = []

        for child_name in stat["children"]:
            if marker is not None and child_name < marker:
                continue
            child_stat = self.fs_access.entry_info(file_context.path / child_name)
            entries.append(
                {
                    "file_name": winify_entry_name(child_name),
                    **stat_to_winfsp_attributes(child_stat),
                }
            )

        if not file_context.path.is_root():
            entries.append({"file_name": ".."})

        return entries

    @handle_error
    def read(self, file_context, offset, length):
        buffer = self.fs_access.fd_read(file_context.fd, length, offset)
        return buffer

    @handle_error
    def write(self, file_context, buffer, offset, write_to_end_of_file, constrained_io):
        # `constrained_io` seems too complicated to implement for us
        if write_to_end_of_file:
            offset = -1
        # LocalStorage.set only wants bytes or bytearray...
        buffer = bytes(buffer)
        ret = self.fs_access.fd_write(file_context.fd, buffer, offset)
        return ret

    @handle_error
    def flush(self, file_context) -> None:
        self.fs_access.fd_flush(file_context.fd)

    @handle_error
    def cleanup(self, file_context, file_name, flags) -> None:
        # FspCleanupDelete
        if flags & 1:
            self.fs_access.check_write_rights(file_context.path)
            file_context.deleted = True

    @handle_error
    def overwrite(
        self, file_context, file_attributes, replace_file_attributes: bool, allocation_size: int
    ) -> None:
        self.fs_access.fd_resize(file_context.fd, 0)
