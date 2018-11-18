import pytest
from pendulum import Pendulum

from tests.common import freeze_time, create_shared_workspace


async def assert_same_fs(fs1, fs2):
    async def _recursive_assert(fs1, fs2, path):
        stat1 = await fs1.stat(path)
        stat2 = await fs2.stat(path)
        assert stat1 == stat2

        cooked_children = {}
        if stat1["type"] in ("root", "workspace", "folder"):
            for child in stat1["children"]:
                cooked_children[child] = await _recursive_assert(fs1, fs2, f"{path}/{child}")

        stat1["children"] = cooked_children
        return stat1

    return await _recursive_assert(fs1, fs2, "/")


@pytest.mark.trio
async def test_simple_sync(running_backend, alice_fs, alice2_fs):
    await create_shared_workspace("/w", alice_fs, alice2_fs)

    # 0) Make sure workspace is loaded for alice2
    # (otherwise won't get synced event during step 2)
    await alice2_fs.stat("/w")

    # 1) Create&sync file

    with freeze_time("2000-01-02"):
        await alice_fs.file_create("/w/foo.txt")

    with freeze_time("2000-01-03"):
        await alice_fs.file_write("/w/foo.txt", b"hello world !")

    with alice_fs.event_bus.listen() as spy:
        with freeze_time("2000-01-04"):
            await alice_fs.sync("/w")
    spy.assert_events_occured(
        [
            ("fs.entry.synced", {"path": "/w/foo.txt", "id": spy.ANY}, Pendulum(2000, 1, 4)),
            ("fs.entry.synced", {"path": "/w", "id": spy.ANY}, Pendulum(2000, 1, 4)),
        ]
    )

    # 2) Fetch back file from another fs

    with alice2_fs.event_bus.listen() as spy:
        with freeze_time("2000-01-05"):
            # TODO: `sync` on not loaded entry should load it
            await alice2_fs.sync("/w")
    spy.assert_events_occured(
        [("fs.entry.synced", {"path": "/w", "id": spy.ANY}, Pendulum(2000, 1, 5))]
    )

    # 3) Finally make sure both fs have the same data
    final_fs = await assert_same_fs(alice_fs, alice2_fs)
    assert final_fs["children"]["w"]["children"].keys() == {"foo.txt"}

    data = await alice_fs.file_read("/w/foo.txt")
    data2 = await alice2_fs.file_read("/w/foo.txt")
    assert data == data2


@pytest.mark.trio
async def test_fs_entry_synced_event_when_all_synced(running_backend, alice_fs):
    await create_shared_workspace("/w", alice_fs)

    # 1) Create data

    with freeze_time("2000-01-02"):
        await alice_fs.file_create("/w/foo.txt")
        await alice_fs.folder_create("/w/bar")

    # 2) Sync it

    with alice_fs.event_bus.listen() as spy:
        with freeze_time("2000-01-03"):
            await alice_fs.sync("/w")
    spy.assert_events_occured(
        [
            ("fs.entry.synced", {"path": "/w/foo.txt", "id": spy.ANY}, Pendulum(2000, 1, 3)),
            ("fs.entry.synced", {"path": "/w/bar", "id": spy.ANY}, Pendulum(2000, 1, 3)),
            ("fs.entry.synced", {"path": "/w", "id": spy.ANY}, Pendulum(2000, 1, 3)),
        ]
    )

    # 2) Now additional sync should not trigger any event

    with alice_fs.event_bus.listen() as spy:
        with freeze_time("2000-01-04"):
            await alice_fs.sync("/w")
    spy.assert_events_occured([])


@pytest.mark.trio
async def test_cross_sync(running_backend, alice_fs, alice2_fs):
    await create_shared_workspace("/w", alice_fs, alice2_fs)

    # 1) Both fs have things to sync

    with freeze_time("2000-01-02"):
        await alice_fs.file_create("/w/foo.txt")

    with freeze_time("2000-01-03"):
        await alice2_fs.folder_create("/w/bar")
        await alice2_fs.folder_create("/w/bar/spam")

    # 2) Do the cross sync

    with alice_fs.event_bus.listen() as spy:
        with freeze_time("2000-01-04"):
            await alice_fs.sync("/w")

    spy.assert_events_occured(
        [
            ("fs.entry.synced", {"path": "/w/foo.txt", "id": spy.ANY}, Pendulum(2000, 1, 4)),
            ("fs.entry.synced", {"path": "/w", "id": spy.ANY}, Pendulum(2000, 1, 4)),
        ]
    )

    with alice2_fs.event_bus.listen() as spy:
        with freeze_time("2000-01-05"):
            await alice2_fs.sync("/w")

    spy.assert_events_occured(
        [
            ("fs.entry.synced", {"path": "/w/bar/spam", "id": spy.ANY}, Pendulum(2000, 1, 5)),
            ("fs.entry.synced", {"path": "/w/bar", "id": spy.ANY}, Pendulum(2000, 1, 5)),
            ("fs.entry.synced", {"path": "/w", "id": spy.ANY}, Pendulum(2000, 1, 5)),
        ]
    )

    with alice_fs.event_bus.listen() as spy:
        with freeze_time("2000-01-06"):
            await alice_fs.sync("/w")

    spy.assert_events_occured(
        [("fs.entry.synced", {"path": "/w", "id": spy.ANY}, Pendulum(2000, 1, 6))]
    )

    # 3) Finally make sure both fs have the same data

    final_fs = await assert_same_fs(alice_fs, alice2_fs)
    final_wkps = final_fs["children"]["w"]
    assert final_wkps["children"].keys() == {"foo.txt", "bar"}
    assert final_wkps["children"]["bar"]["children"].keys() == {"spam"}

    assert final_wkps["base_version"] == 3
    for child in final_wkps["children"].values():
        assert child["base_version"] == 1

    data = await alice_fs.file_read("/w/foo.txt")
    data2 = await alice2_fs.file_read("/w/foo.txt")
    assert data == data2


@pytest.mark.trio
async def test_sync_growth_by_truncate_file(running_backend, alice_fs, alice2_fs):
    await create_shared_workspace("/w", alice_fs, alice2_fs)

    # Growth by truncate is special because no blocks are created to hold
    # the newly created null bytes

    with freeze_time("2000-01-02"):
        await alice_fs.file_create("/w/foo.txt")

    with freeze_time("2000-01-03"):
        await alice_fs.file_truncate("/w/foo.txt", length=24)

    await alice_fs.sync("/w")
    await alice2_fs.sync("/w")

    stat = await alice2_fs.stat("/w/foo.txt")
    assert stat["size"] == 24
    data = await alice2_fs.file_read("/w/foo.txt")
    assert data == b"\x00" * 24


@pytest.mark.trio
@pytest.mark.xfail(reason="Conflict sync must be rewritten")
async def test_concurrent_update(running_backend, alice_fs, alice2_fs):
    await create_shared_workspace("/w", alice_fs, alice2_fs)

    # 0) Make sure workspace is loaded for alice2
    # (otherwise won't get synced event during step 2)
    await alice2_fs.stat("/w")

    # 1) Create an existing item in both fs

    with freeze_time("2000-01-02"):
        await alice_fs.file_create("/w/foo.txt")
        await alice_fs.file_write("/w/foo.txt", b"v1")

    await alice_fs.sync("/")
    await alice2_fs.sync("/")

    # 2) Make both fs diverged

    with freeze_time("2000-01-03"):
        await alice_fs.workspace_create("/z")
        await alice_fs.file_write("/w/foo.txt", b"alice's v2")
        await alice_fs.folder_create("/w/bar")
        await alice_fs.file_create("/w/bar/from_alice")
        await alice_fs.file_create("/w/bar/spam")

    with freeze_time("2000-01-04"):
        await alice2_fs.workspace_create("/z")
        await alice2_fs.file_write("/w/foo.txt", b"alice2's v2")
        await alice2_fs.folder_create("/w/bar")
        await alice2_fs.folder_create("/w/bar/from_alice2")
        await alice2_fs.folder_create("/w/bar/spam")

    # 3) Finally do the sync

    with freeze_time("2000-01-05"):
        await alice_fs.sync("/")
    with freeze_time("2000-01-06"):
        await alice2_fs.sync("/")
    # Must sync another time to take into account changes from the second fs's sync
    with freeze_time("2000-01-07"):
        await alice_fs.sync("/")

    final_fs = await assert_same_fs(alice_fs, alice2_fs)
    assert final_fs["children"].keys() == {"w", "z", "z (conflict 2000-01-06 00:00:00)"}
    # TODO: make sure z conflict hasn't changed access

    final_wkps = final_fs["children"]["w"]
    assert final_wkps["children"].keys() == {
        "foo.txt",
        "foo (conflict 2000-01-06 00:00:00).txt",
        "bar",
    }
    assert final_wkps["children"]["bar"]["children"].keys() == {
        "from_alice",
        "from_alice2",
        "spam",
        "spam (conflict 2000-01-06 00:00:00)",
    }

    data = await alice_fs.file_read("/w/foo.txt")
    data2 = await alice2_fs.file_read("/w/foo.txt")
    assert data == data2 == b"alice's v2"

    data = await alice_fs.file_read("/w/foo (conflict 2000-01-06 00:00:00).txt")
    data2 = await alice2_fs.file_read("/w/foo (conflict 2000-01-06 00:00:00).txt")
    assert data == data2 == b"alice2's v2"
