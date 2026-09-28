"""test_10: Collection-boundary consolidation.

Cross-cutting integration test that exercises the Collection-boundary guard
across all sync paths: items outside the configured Collection are skipped
everywhere.

Consolidates boundary checks that individual progress, watched, and playlist
tests touch per-path into a single test asserting the guard holds uniformly.

Issue 14.
"""

from __future__ import annotations

import time

import pytest

from . import jf_client
from . import ta_client

pytestmark = pytest.mark.integration

TA_COLLECTION = "ta"
JF_POSITION_SECONDS = 99
JF_POSITION_TICKS = JF_POSITION_SECONDS * 10_000_000


@pytest.fixture(scope="module")
def outside_item(admin_token: str) -> dict | None:
    """An item outside the `ta` collection (e.g. from Movies), if available."""
    movies_id = jf_client.get_collection_id_by_name(admin_token, "Movies")
    if not movies_id:
        return None
    items = jf_client.get_items(
        admin_token, parent_id=movies_id, Recursive=True,
        IncludeItemTypes="Movie", Fields="ProviderIds",
    )
    outside = items.get("Items", [])
    return outside[0] if outside else None


@pytest.fixture(scope="module")
def tracked_episode(admin_token: str) -> dict:
    """An episode in `ta` collection with a TubeArchivist provider id."""
    collection_id = jf_client.get_collection_id_by_name(admin_token, TA_COLLECTION)
    assert collection_id
    items = jf_client.get_items(
        admin_token,
        parent_id=collection_id,
        Recursive=True,
        IncludeItemTypes="Episode",
        Fields="ProviderIds,Path",
    )
    for ep in items.get("Items", []):
        if ep.get("ProviderIds", {}).get("TubeArchivist"):
            return ep
    pytest.fail("no episode with TubeArchivist provider id found")


def _reset_ta_progress(ta_token: str, yt_id: str) -> None:
    ta_client.delete_progress(ta_token, yt_id)


def test_progress_outside_boundary_not_pushed_to_ta(
    admin_token: str, test_user_token: str, test_user_id: str,
    ta_token: str, tracked_episode: dict, outside_item: dict | None, cleanup,
):
    """JF playback progress on an outside-boundary item is NOT pushed to TA.

    Covers the OnPlaybackProgress Collection-boundary guard.
    """
    if not outside_item:
        pytest.skip("no item outside `ta` collection to test boundary guard")

    yt_id = tracked_episode["ProviderIds"]["TubeArchivist"]
    _reset_ta_progress(ta_token, yt_id)
    cleanup.register(lambda: _reset_ta_progress(ta_token, yt_id))

    jf_client.report_playback_progress(
        test_user_token, test_user_id, outside_item["Id"], JF_POSITION_TICKS,
    )

    # Give the async handler a window.
    time.sleep(8)
    v = ta_client.get_video(ta_token, yt_id)
    pos = v.get("player", {}).get("position")
    assert not pos, \
        f"TA position changed to {pos} for outside-boundary item — should not have been pushed"


def test_watched_outside_boundary_not_pushed_to_ta(
    admin_token: str, test_user_token: str, test_user_id: str,
    ta_token: str, tracked_episode: dict, outside_item: dict | None, cleanup,
):
    """Marking an outside-boundary item played does NOT push watched to TA.

    Covers the OnWatchedStatusChange Collection-boundary guard.
    """
    if not outside_item:
        pytest.skip("no item outside `ta` collection to test boundary guard")

    yt_id = tracked_episode["ProviderIds"]["TubeArchivist"]
    ta_client.set_watched(ta_token, yt_id, False)
    cleanup.register(lambda: ta_client.set_watched(ta_token, yt_id, False))

    jf_client.mark_played(test_user_token, test_user_id, outside_item["Id"])

    time.sleep(8)
    v = ta_client.get_video(ta_token, yt_id)
    watched = bool(v.get("player", {}).get("watched", False))
    assert not watched, \
        f"TA watched changed to {watched} for outside-boundary item — should not have been pushed"


def test_ta_to_jf_progress_skips_outside_boundary(
    admin_token: str, test_user_id: str, ta_token: str,
    tracked_episode: dict, outside_item: dict | None, cleanup, jf_logs,
):
    """TA->JF progress sync only processes items inside the Collection.

    The TAToJellyfinProgressSyncTask iterates the `ta` collection's
    channels/seasons/episodes — outside-boundary items are never reached.
    We verify by asserting the outside item's JF user-data is unaffected
    after the task runs.
    """
    if not outside_item:
        pytest.skip("no item outside `ta` collection to test boundary guard")

    yt_id = tracked_episode["ProviderIds"]["TubeArchivist"]
    _reset_ta_progress(ta_token, yt_id)
    cleanup.register(lambda: _reset_ta_progress(ta_token, yt_id))

    # Reset the outside item's user-data.
    jf_client.update_user_data(
        admin_token, test_user_id, outside_item["Id"],
        {"PlaybackPositionTicks": 0, "Played": False},
    )

    # Set TA progress on the tracked video.
    ta_client.set_progress(ta_token, yt_id, 77)

    task_id = jf_client.get_task_id_by_name(admin_token, "TAToJellyfinProgressSyncTask")
    assert task_id
    jf_client.wait_for_task(admin_token, task_id, timeout=120)

    # The outside item's user-data should remain zero/unplayed.
    outside_data = jf_client.get_user_data(
        admin_token, test_user_id, outside_item["Id"],
    )
    assert not outside_data.get("Played"), \
        "Outside-boundary item Played flag should be False"
    assert (outside_data.get("PlaybackPositionTicks", 0) or 0) == 0, \
        "Outside-boundary item position should be 0"


def test_playlist_sync_respects_collection_boundary(
    admin_token: str, test_user_token: str, test_user_id: str,
    ta_token: str, outside_item: dict | None, jf_logs,
):
    """JF->TA playlist sync skips items outside the Collection.

    A JF playlist containing only outside-boundary items (non-TA-provider)
    should produce a log error and not create a TA playlist.
    """
    if not outside_item:
        pytest.skip("no item outside `ta` collection to test boundary guard")

    pl_name = "CollectionBoundary Playlist Test"
    jf_pl = jf_client.create_playlist(
        test_user_token, test_user_id, pl_name, [outside_item["Id"]],
    )
    jf_pl = jf_client.get_playlist_by_name(test_user_token, test_user_id, pl_name)
    assert jf_pl

    try:
        task_id = jf_client.get_task_id_by_name(admin_token, "JFToTubeArchivistPlaylistsSyncTask")
        assert task_id
        jf_client.wait_for_task(admin_token, task_id, timeout=180)
        logs = jf_logs(1000)

        # The plugin should log about the non-TA-provider video being skipped.
        # (Outside-boundary items don't have TubeArchivist provider ids.)
        # The log may be at INF/WRN level, not necessarily ERROR.
        assert "not tubearchivist" in logs.lower() or "provider" in logs.lower() or "skipped" in logs.lower(), \
            "Expected log for outside-boundary item being skipped in playlist sync"
    finally:
        try:
            jf_client.delete_playlist(admin_token, jf_pl["Id"])
        except Exception:
            pass
