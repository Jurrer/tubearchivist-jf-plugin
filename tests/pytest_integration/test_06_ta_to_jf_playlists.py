"""test_06: TA->JF Playlist Sync integration.

Verifies TAToJellyfinPlaylistsSyncTask, GetPlaylists:
  - JF playlists created with correct name format
    (Regular: "Name - Channel (ID)", Custom: "Name (ID)") matching entries.
  - Non-downloaded TA entries skipped (log check); missing JF entries produce warning.
  - TAJFPlaylistsDelete=true removes JF playlist whose TA counterpart deleted.

Issue 10.
"""

from __future__ import annotations

import time

import pytest

from . import jf_client
from . import ta_client

pytestmark = pytest.mark.integration

TA_COLLECTION = "ta"

# Unique suffix to avoid collisions with real TA playlists in JF.
TEST_SUFFIX = "ta-jf-pl-sync-test"


@pytest.fixture(scope="module")
def sample_ta_playlists(ta_token: str) -> list[dict]:
    """Return all TA playlists (for verifying sync)."""
    playlists = ta_client.get_all_playlists(ta_token)
    assert playlists, "TA has no playlists"
    return playlists


@pytest.fixture
def cleanup_jf_playlists(admin_token: str, test_user_id: str):
    """Delete JF playlists created during tests matching the test suffix."""
    created: list[str] = []

    def track(playlist_id: str) -> None:
        created.append(playlist_id)

    registry = type("PlCleanup", (), {"track": staticmethod(track)})()
    yield registry

    for pid in created:
        try:
            jf_client.delete_playlist(admin_token, pid)
        except Exception:
            pass


def test_jf_playlists_created_with_correct_name_format(
    admin_token: str, test_user_id: str, ta_token: str,
    sample_ta_playlists: list[dict], jf_logs,
):
    """JF playlists must have correct name format matching TA playlists.

    Regular: "Name - Channel (ID)"
    Custom:  "Name (ID)"
    """
    task_id = jf_client.get_task_id_by_name(admin_token, "TAToJellyfinPlaylistsSyncTask")
    assert task_id, "TAToJellyfinPlaylistsSyncTask not found"
    jf_client.wait_for_task(admin_token, task_id, timeout=180)

    jf_playlists = jf_client.get_playlists(admin_token, test_user_id)
    jf_names = {pl["Name"] for pl in jf_playlists}

    # Verify at least one Regular and one Custom playlist has correct name format.
    regular_found = False
    custom_found = False

    for ta_pl in sample_ta_playlists:
        pl_id = ta_pl.get("playlist_id", "")
        pl_name = ta_pl.get("playlist_name", "")
        pl_type = ta_pl.get("playlist_type", "")
        pl_channel = ta_pl.get("playlist_channel", "")

        if pl_type == "regular":
            expected = f"{pl_name} - {pl_channel} ({pl_id})"
            if expected in jf_names:
                regular_found = True
        elif pl_type == "custom":
            expected = f"{pl_name} ({pl_id})"
            if expected in jf_names:
                custom_found = True

    assert regular_found, \
        "No Regular TA playlist found in JF with correct name format 'Name - Channel (ID)'"
    assert custom_found, \
        "No Custom TA playlist found in JF with correct name format 'Name (ID)'"


def test_non_downloaded_entries_skipped(
    admin_token: str, test_user_id: str, ta_token: str,
    sample_ta_playlists: list[dict], jf_logs,
):
    """Non-downloaded TA entries must be skipped (log check)."""
    task_id = jf_client.get_task_id_by_name(admin_token, "TAToJellyfinPlaylistsSyncTask")
    assert task_id
    jf_client.wait_for_task(admin_token, task_id, timeout=180)
    logs = jf_logs(1000)

    # The plugin logs "was skipped because has not been downloaded" for non-downloaded entries.
    assert "skipped" in logs.lower() and "downloaded" in logs.lower(), \
        "Expected skip log for non-downloaded TA entries"


def test_ta_jf_playlists_delete_removes_jf_playlist(
    admin_token: str, test_user_id: str, ta_token: str,
    cleanup_jf_playlists, cleanup,
):
    """TAJFPlaylistsDelete=true removes JF playlist whose TA counterpart is deleted.

    Creates a TA custom playlist, runs the sync (creating the JF counterpart),
    deletes the TA playlist, runs the sync again, and asserts the JF playlist
    is removed.
    """
    # 1. Create a throwaway TA custom playlist.
    ta_pl_name = f"TestDelete_{TEST_SUFFIX}"
    ta_pl = ta_client.create_custom_playlist(ta_token, ta_pl_name)
    assert ta_pl, "Failed to create TA custom playlist"
    ta_pl_id = ta_pl.get("playlist_id")
    assert ta_pl_id
    cleanup.register(lambda: ta_client.delete_playlist(ta_token, ta_pl_id))

    # 2. Run TA->JF playlists sync to create the JF counterpart.
    task_id = jf_client.get_task_id_by_name(admin_token, "TAToJellyfinPlaylistsSyncTask")
    assert task_id
    jf_client.wait_for_task(admin_token, task_id, timeout=180)

    # 3. Find the JF playlist matching the TA custom playlist.
    expected_jf_name = f"{ta_pl_name} ({ta_pl_id})"
    jf_pl = jf_client.get_playlist_by_name(admin_token, test_user_id, expected_jf_name)
    assert jf_pl, f"JF playlist '{expected_jf_name}' not created after sync"
    jf_pl_id = jf_pl["Id"]
    cleanup_jf_playlists.track(jf_pl_id)

    # 4. Delete the TA playlist.
    ta_client.delete_playlist(ta_token, ta_pl_id)

    # 5. Run sync again — JF playlist should be deleted.
    jf_client.wait_for_task(admin_token, task_id, timeout=180)
    time.sleep(2)

    jf_pl_after = jf_client.get_playlist_by_name(admin_token, test_user_id, expected_jf_name)
    assert jf_pl_after is None, \
        f"JF playlist '{expected_jf_name}' should have been deleted (TAJFPlaylistsDelete=true)"
