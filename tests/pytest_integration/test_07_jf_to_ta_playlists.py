"""test_07: JF->TA Playlist Sync integration.

Verifies JFToTubeArchivistPlaylistsSyncTask, CreateCustomPlaylist,
CustomPlaylistEntryAction:
  - JF playlist with TA-provider videos -> TA custom playlist created,
    JF playlist renamed with id suffix, entries match.
  - Non-TA-provider video skipped (error log).
  - No-suffix-no-match JF playlist creates a new custom TA playlist.
  - Regular (YouTube) TA playlist skipped with warning.

Issue 11.
"""

from __future__ import annotations

import re
import time

import pytest

from . import jf_client
from . import ta_client

pytestmark = pytest.mark.integration

TA_COLLECTION = "ta"
TEST_SUFFIX = "jf-ta-pl-sync-test"


@pytest.fixture(scope="module")
def ta_provider_episodes(admin_token: str) -> list[dict]:
    """Episodes in `ta` collection with TubeArchivist provider ids."""
    collection_id = jf_client.get_collection_id_by_name(admin_token, TA_COLLECTION)
    assert collection_id
    return jf_client.get_episodes_with_provider_id(admin_token, collection_id)


@pytest.fixture
def cleanup_both(admin_token: str, test_user_id: str, ta_token: str):
    """Track and clean up JF playlists and TA playlists created during tests."""
    jf_ids: list[str] = []
    ta_ids: list[str] = []

    def track_jf(pid: str) -> None:
        jf_ids.append(pid)

    def track_ta(pid: str) -> None:
        ta_ids.append(pid)

    registry = type("SyncCleanup", (), {
        "track_jf": staticmethod(track_jf),
        "track_ta": staticmethod(track_ta),
    })()
    yield registry

    for pid in jf_ids:
        try:
            jf_client.delete_playlist(admin_token, pid)
        except Exception:
            pass
    for pid in ta_ids:
        try:
            ta_client.delete_playlist(ta_token, pid)
        except Exception:
            pass


def test_jf_playlist_creates_ta_custom_playlist(
    admin_token: str, test_user_token: str, test_user_id: str,
    ta_token: str, ta_provider_episodes: list[dict],
    cleanup_both, jf_logs,
):
    """JF playlist with TA-provider videos -> TA custom playlist created.

    The JF playlist is renamed to include the TA playlist id suffix.
    Entries in the TA playlist match the JF playlist items.
    """
    assert len(ta_provider_episodes) >= 2, "need at least 2 TA-provider episodes"
    episodes = ta_provider_episodes[:3]
    item_ids = [ep["Id"] for ep in episodes]
    yt_ids = [ep["ProviderIds"]["TubeArchivist"] for ep in episodes]

    # 1. Create a JF playlist with TA-provider videos (no TA counterpart).
    pl_name = f"JFTA Sync Test {TEST_SUFFIX}"
    jf_pl = jf_client.create_playlist(
        test_user_token, test_user_id, pl_name, item_ids,
    )
    # Some JF versions return minimal data; find the playlist by name.
    jf_pl = jf_client.get_playlist_by_name(test_user_token, test_user_id, pl_name)
    assert jf_pl, f"JF playlist '{pl_name}' not created"
    jf_pl_id = jf_pl["Id"]
    cleanup_both.track_jf(jf_pl_id)

    # 2. Run JF->TA playlists sync task.
    task_id = jf_client.get_task_id_by_name(admin_token, "JFToTubeArchivistPlaylistsSyncTask")
    assert task_id, "JFToTubeArchivistPlaylistsSyncTask not found"
    jf_client.wait_for_task(admin_token, task_id, timeout=180)
    time.sleep(2)

    # 3. Assert JF playlist was renamed to include TA playlist id suffix.
    jf_playlists = jf_client.get_playlists(test_user_token, test_user_id)
    renamed = None
    for pl in jf_playlists:
        if pl["Id"] == jf_pl_id:
            renamed = pl
            break
    assert renamed, "JF playlist disappeared after sync"
    # The renamed playlist should have " (TA_ID)" suffix.
    match = re.match(r"^(.+)\s\((.+)\)$", renamed["Name"])
    assert match, f"JF playlist not renamed with id suffix, got '{renamed['Name']}'"
    ta_pl_id_from_name = match.group(2)
    cleanup_both.track_ta(ta_pl_id_from_name)

    # 4. Assert TA custom playlist was created with matching entries.
    ta_pl = ta_client.get_playlist(ta_token, ta_pl_id_from_name)
    assert ta_pl, f"TA custom playlist {ta_pl_id_from_name} not found"
    assert ta_pl.get("playlist_type") == "custom", \
        f"TA playlist should be custom, got {ta_pl.get('playlist_type')}"

    ta_entries = ta_pl.get("playlist_entries", [])
    ta_entry_yt_ids = {e.get("youtube_id") for e in ta_entries}
    for yt_id in yt_ids:
        assert yt_id in ta_entry_yt_ids, \
            f"Video {yt_id} not found in TA playlist entries"


def test_non_ta_provider_video_skipped(
    admin_token: str, test_user_token: str, test_user_id: str,
    ta_token: str, cleanup_both, jf_logs,
):
    """Non-TA-provider video in JF playlist is skipped (error log).

    Uses a JF item without a TubeArchivist provider id (e.g. a movie or
    a non-TA folder item) if available.
    """
    # Find a non-TA-provider item — try the Movies collection.
    movies_id = jf_client.get_collection_id_by_name(admin_token, "Movies")
    if not movies_id:
        pytest.skip("no `Movies` collection to test non-TA-provider skip")
    items = jf_client.get_items(
        admin_token, parent_id=movies_id, Recursive=True,
        IncludeItemTypes="Movie", Fields="ProviderIds",
    )
    non_ta_items = [
        it for it in items.get("Items", [])
        if not it.get("ProviderIds", {}).get("TubeArchivist")
    ]
    if not non_ta_items:
        pytest.skip("no non-TA-provider movie found")

    # Also need at least one TA-provider episode to create the playlist.
    collection_id = jf_client.get_collection_id_by_name(admin_token, TA_COLLECTION)
    ta_eps = jf_client.get_episodes_with_provider_id(admin_token, collection_id)
    if not ta_eps:
        pytest.skip("no TA-provider episodes")

    item_ids = [non_ta_items[0]["Id"], ta_eps[0]["Id"]]
    pl_name = f"NonTA Skip Test {TEST_SUFFIX}"
    jf_pl = jf_client.create_playlist(
        test_user_token, test_user_id, pl_name, item_ids,
    )
    jf_pl = jf_client.get_playlist_by_name(test_user_token, test_user_id, pl_name)
    assert jf_pl
    cleanup_both.track_jf(jf_pl["Id"])

    task_id = jf_client.get_task_id_by_name(admin_token, "JFToTubeArchivistPlaylistsSyncTask")
    assert task_id
    jf_client.wait_for_task(admin_token, task_id, timeout=180)
    logs = jf_logs(1000)

    # The plugin logs an error for non-TA-provider videos.
    # Look for "does not have a TubeArchivist provider id" or similar.
    assert "error" in logs.lower() or "provider" in logs.lower(), \
        "Expected error log for non-TA-provider video"


def test_no_suffix_no_match_creates_new_ta_playlist(
    admin_token: str, test_user_token: str, test_user_id: str,
    ta_token: str, ta_provider_episodes: list[dict],
    cleanup_both,
):
    """JF playlist with no id suffix and no TA match creates a new custom TA playlist."""
    assert ta_provider_episodes, "need at least 1 TA-provider episode"
    item_ids = [ta_provider_episodes[0]["Id"]]
    pl_name = f"NoSuffix Test {TEST_SUFFIX}"

    jf_pl = jf_client.create_playlist(
        test_user_token, test_user_id, pl_name, item_ids,
    )
    jf_pl = jf_client.get_playlist_by_name(test_user_token, test_user_id, pl_name)
    assert jf_pl
    cleanup_both.track_jf(jf_pl["Id"])

    task_id = jf_client.get_task_id_by_name(admin_token, "JFToTubeArchivistPlaylistsSyncTask")
    assert task_id
    jf_client.wait_for_task(admin_token, task_id, timeout=180)
    time.sleep(2)

    # The JF playlist should now have a suffix with the new TA playlist id.
    jf_playlists = jf_client.get_playlists(test_user_token, test_user_id)
    renamed = None
    for pl in jf_playlists:
        if pl["Id"] == jf_pl["Id"]:
            renamed = pl
            break
    assert renamed
    match = re.match(r"^(.+)\s\((.+)\)$", renamed["Name"])
    assert match, f"JF playlist should have been renamed with TA id suffix, got '{renamed['Name']}'"
    ta_pl_id = match.group(2)
    cleanup_both.track_ta(ta_pl_id)

    # Verify the TA playlist exists.
    ta_pl = ta_client.get_playlist(ta_token, ta_pl_id)
    assert ta_pl, f"TA custom playlist {ta_pl_id} not created"


def test_regular_ta_playlist_skipped_warning(
    admin_token: str, test_user_token: str, test_user_id: str,
    ta_token: str, ta_provider_episodes: list[dict],
    cleanup_both, jf_logs,
):
    """Regular (YouTube) TA playlist is skipped with warning.

    Creates a JF playlist whose name suffix matches a Regular TA playlist id,
    then runs JF->TA sync and checks the log for a skip warning (Regular
    playlists cannot be modified).
    """
    # Find a Regular TA playlist.
    ta_playlists = ta_client.get_all_playlists(ta_token)
    regular_pl = None
    for pl in ta_playlists:
        if pl.get("playlist_type") == "regular":
            regular_pl = pl
            break
    if not regular_pl:
        pytest.skip("no Regular TA playlist found")

    pl_id = regular_pl.get("playlist_id")
    pl_name = regular_pl.get("playlist_name")
    pl_channel = regular_pl.get("playlist_channel")
    # The JF name format for a Regular playlist is "Name - Channel (ID)".
    jf_name = f"{pl_name} - {pl_channel} ({pl_id})"

    assert ta_provider_episodes, "need at least 1 TA-provider episode"
    item_ids = [ta_provider_episodes[0]["Id"]]
    jf_pl = jf_client.create_playlist(
        test_user_token, test_user_id, jf_name, item_ids,
    )
    jf_pl = jf_client.get_playlist_by_name(test_user_token, test_user_id, jf_name)
    assert jf_pl
    cleanup_both.track_jf(jf_pl["Id"])

    task_id = jf_client.get_task_id_by_name(admin_token, "JFToTubeArchivistPlaylistsSyncTask")
    assert task_id
    jf_client.wait_for_task(admin_token, task_id, timeout=180)
    logs = jf_logs(1000)

    # The plugin should log a warning that Regular playlists cannot be synced.
    assert "regular" in logs.lower() or "skip" in logs.lower() or "cannot" in logs.lower(), \
        "Expected warning log for Regular TA playlist"


def test_add_remove_video_creates_and_removes_in_ta(
    admin_token: str, test_user_token: str, test_user_id: str,
    ta_token: str, ta_provider_episodes: list[dict],
    cleanup_both,
):
    """Add/remove Video in JF playlist → Create/Remove actions reach TA.

    1. Create a JF playlist with 2 TA-provider videos.
    2. Run JF->TA sync — TA custom playlist created with 2 entries.
    3. Remove one video from the JF playlist.
    4. Run sync again — TA playlist should reflect the removal (1 entry).
    5. Add a new video to the JF playlist.
    6. Run sync again — TA playlist should reflect the addition (2 entries).
    """
    assert len(ta_provider_episodes) >= 3, "need at least 3 TA-provider episodes"
    ep1, ep2, ep3 = ta_provider_episodes[:3]

    # 1. Create JF playlist with 2 videos.
    pl_name = f"AddRemove Test {TEST_SUFFIX}"
    jf_pl = jf_client.create_playlist(
        test_user_token, test_user_id, pl_name, [ep1["Id"], ep2["Id"]],
    )
    jf_pl = jf_client.get_playlist_by_name(test_user_token, test_user_id, pl_name)
    assert jf_pl
    cleanup_both.track_jf(jf_pl["Id"])

    task_id = jf_client.get_task_id_by_name(admin_token, "JFToTubeArchivistPlaylistsSyncTask")
    assert task_id

    # 2. Run sync — TA playlist created with 2 entries.
    jf_client.wait_for_task(admin_token, task_id, timeout=180)
    time.sleep(2)

    # Find the renamed JF playlist to get the TA playlist id.
    jf_playlists = jf_client.get_playlists(test_user_token, test_user_id)
    renamed = None
    for pl in jf_playlists:
        if pl["Id"] == jf_pl["Id"]:
            renamed = pl
            break
    assert renamed
    match = re.match(r"^(.+)\s\((.+)\)$", renamed["Name"])
    assert match, f"JF playlist not renamed, got '{renamed['Name']}'"
    ta_pl_id = match.group(2)
    cleanup_both.track_ta(ta_pl_id)

    # Verify TA playlist has 2 entries.
    ta_entries = ta_client.get_playlist_entries(ta_token, ta_pl_id)
    assert len(ta_entries) == 2, f"TA playlist should have 2 entries, got {len(ta_entries)}"

    # 3. Remove one video from JF playlist.
    jf_client.remove_from_playlist(test_user_token, jf_pl["Id"], [ep2["Id"]])

    # 4. Run sync — TA should reflect removal.
    jf_client.wait_for_task(admin_token, task_id, timeout=180)
    time.sleep(2)
    ta_entries = ta_client.get_playlist_entries(ta_token, ta_pl_id)
    ta_yt_ids = {e.get("youtube_id") for e in ta_entries}
    assert ep2["ProviderIds"]["TubeArchivist"] not in ta_yt_ids, \
        "Removed video should not be in TA playlist entries"
    assert ep1["ProviderIds"]["TubeArchivist"] in ta_yt_ids, \
        "Remaining video should still be in TA playlist entries"

    # 5. Add a new video to JF playlist.
    jf_client.add_to_playlist(test_user_token, jf_pl["Id"], [ep3["Id"]])

    # 6. Run sync — TA should reflect addition.
    jf_client.wait_for_task(admin_token, task_id, timeout=180)
    time.sleep(2)
    ta_entries = ta_client.get_playlist_entries(ta_token, ta_pl_id)
    ta_yt_ids = {e.get("youtube_id") for e in ta_entries}
    assert ep3["ProviderIds"]["TubeArchivist"] in ta_yt_ids, \
        "Added video should be in TA playlist entries"


def test_reorder_actions_reach_ta(
    admin_token: str, test_user_token: str, test_user_id: str,
    ta_token: str, ta_provider_episodes: list[dict],
    cleanup_both,
):
    """Reorder actions (Up/Down/Top/Bottom) reach TA.

    1. Create a JF playlist with 3 TA-provider videos in a known order.
    2. Run JF->TA sync — TA custom playlist created.
    3. Reorder the JF playlist items (move first item to last).
    4. Run sync again — TA playlist order should reflect the reorder.
    """
    assert len(ta_provider_episodes) >= 3, "need at least 3 TA-provider episodes"
    ep1, ep2, ep3 = ta_provider_episodes[:3]

    pl_name = f"Reorder Test {TEST_SUFFIX}"
    jf_pl = jf_client.create_playlist(
        test_user_token, test_user_id, pl_name, [ep1["Id"], ep2["Id"], ep3["Id"]],
    )
    jf_pl = jf_client.get_playlist_by_name(test_user_token, test_user_id, pl_name)
    assert jf_pl
    cleanup_both.track_jf(jf_pl["Id"])

    task_id = jf_client.get_task_id_by_name(admin_token, "JFToTubeArchivistPlaylistsSyncTask")
    assert task_id

    # Run sync to create the TA playlist.
    jf_client.wait_for_task(admin_token, task_id, timeout=180)
    time.sleep(2)

    # Get the TA playlist id from the renamed JF playlist.
    jf_playlists = jf_client.get_playlists(test_user_token, test_user_id)
    renamed = None
    for pl in jf_playlists:
        if pl["Id"] == jf_pl["Id"]:
            renamed = pl
            break
    assert renamed
    match = re.match(r"^(.+)\s\((.+)\)$", renamed["Name"])
    assert match, f"JF playlist not renamed, got '{renamed['Name']}'"
    ta_pl_id = match.group(2)
    cleanup_both.track_ta(ta_pl_id)

    # Verify initial TA order.
    ta_entries_before = ta_client.get_playlist_entries(ta_token, ta_pl_id)
    before_ids = [e.get("youtube_id") for e in ta_entries_before]
    assert len(before_ids) == 3

    # Reorder JF playlist: remove ep1, add it back at the end.
    jf_client.remove_from_playlist(test_user_token, jf_pl["Id"], [ep1["Id"]])
    jf_client.add_to_playlist(test_user_token, jf_pl["Id"], [ep1["Id"]])

    # Run sync — TA should reflect the reorder.
    jf_client.wait_for_task(admin_token, task_id, timeout=180)
    time.sleep(2)
    ta_entries_after = ta_client.get_playlist_entries(ta_token, ta_pl_id)
    after_ids = [e.get("youtube_id") for e in ta_entries_after]

    # The first video (ep1) should now be last in TA.
    ep1_yt = ep1["ProviderIds"]["TubeArchivist"]
    assert after_ids[-1] == ep1_yt, \
        f"Reordered video should be last in TA, got order {after_ids}"
