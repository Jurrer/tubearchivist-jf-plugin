"""test_08: Playlist delete-flag integration.

Verifies delete-flag behavior on both playlist sync paths:
  - JFTAPlaylistsDelete=true deletes TA playlist when JF counterpart removed.
  - JFTAPlaylistsDelete=false prevents JF->TA deletion.
  - TAJFPlaylistsDelete=false prevents TA->JF deletion.

Issue 12.
"""

from __future__ import annotations

import time

import pytest

from . import jf_client
from . import ta_client

pytestmark = pytest.mark.integration

TA_COLLECTION = "ta"
TEST_SUFFIX = "del-flag-test"


@pytest.fixture
def cleanup_both(admin_token: str, test_user_id: str, ta_token: str):
    """Track and clean up JF playlists and TA playlists created during tests."""
    jf_ids: list[str] = []
    ta_ids: list[str] = []

    def track_jf(pid: str) -> None:
        jf_ids.append(pid)

    def track_ta(pid: str) -> None:
        ta_ids.append(pid)

    registry = type("DelFlagCleanup", (), {
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


def test_jf_to_ta_delete_flag_true(
    admin_token: str, test_user_token: str, test_user_id: str,
    ta_token: str, cleanup_both,
):
    """JFTAPlaylistsDelete=true deletes TA playlist when JF counterpart removed.

    1. Create a TA custom playlist.
    2. Run TA->JF sync to create the JF counterpart.
    3. Delete the JF playlist.
    4. Run JF->TA sync.
    5. Assert the TA playlist is deleted.
    """
    # 1. Create TA custom playlist.
    ta_pl_name = f"DelFlagTrue_{TEST_SUFFIX}"
    ta_pl = ta_client.create_custom_playlist(ta_token, ta_pl_name)
    assert ta_pl
    ta_pl_id = ta_pl.get("playlist_id")
    assert ta_pl_id
    cleanup_both.track_ta(ta_pl_id)

    # 2. Run TA->JF sync to create the JF counterpart.
    ta_jf_task = jf_client.get_task_id_by_name(admin_token, "TAToJellyfinPlaylistsSyncTask")
    assert ta_jf_task
    jf_client.wait_for_task(admin_token, ta_jf_task, timeout=180)

    expected_jf_name = f"{ta_pl_name} ({ta_pl_id})"
    jf_pl = jf_client.get_playlist_by_name(admin_token, test_user_id, expected_jf_name)
    assert jf_pl, f"JF playlist '{expected_jf_name}' not created"
    cleanup_both.track_jf(jf_pl["Id"])

    # 3. Delete the JF playlist.
    jf_client.delete_playlist(admin_token, jf_pl["Id"])

    # 4. Run JF->TA sync (hermetic config has JFTAPlaylistsDelete=true).
    jf_ta_task = jf_client.get_task_id_by_name(admin_token, "JFToTubeArchivistPlaylistsSyncTask")
    assert jf_ta_task
    jf_client.wait_for_task(admin_token, jf_ta_task, timeout=180)
    time.sleep(2)

    # 5. Assert TA playlist is deleted (GET returns 404).
    try:
        ta_client.get_playlist(ta_token, ta_pl_id)
        # If we get here, the playlist still exists — deletion did not happen.
        # Remove it from cleanup to avoid double-delete errors.
        # Actually, we still want to clean up if it exists.
        pytest.fail(
            f"TA playlist {ta_pl_id} should have been deleted "
            "(JFTAPlaylistsDelete=true) but still exists"
        )
    except Exception:
        pass  # 404 — playlist was deleted as expected


def test_jf_to_ta_delete_flag_false(
    admin_token: str, test_user_token: str, test_user_id: str,
    ta_token: str, cleanup_both, config_override,
):
    """JFTAPlaylistsDelete=false prevents JF->TA deletion.

    1. Create a TA custom playlist.
    2. Run TA->JF sync to create the JF counterpart.
    3. Delete the JF playlist.
    4. Override config: JFTAPlaylistsDelete=false, restart JF.
    5. Run JF->TA sync.
    6. Assert the TA playlist still exists.
    """
    # 1. Create TA custom playlist.
    ta_pl_name = f"DelFlagFalse_{TEST_SUFFIX}"
    ta_pl = ta_client.create_custom_playlist(ta_token, ta_pl_name)
    assert ta_pl
    ta_pl_id = ta_pl.get("playlist_id")
    assert ta_pl_id
    cleanup_both.track_ta(ta_pl_id)

    # 2. Run TA->JF sync to create the JF counterpart.
    ta_jf_task = jf_client.get_task_id_by_name(admin_token, "TAToJellyfinPlaylistsSyncTask")
    assert ta_jf_task
    jf_client.wait_for_task(admin_token, ta_jf_task, timeout=180)

    expected_jf_name = f"{ta_pl_name} ({ta_pl_id})"
    jf_pl = jf_client.get_playlist_by_name(admin_token, test_user_id, expected_jf_name)
    assert jf_pl, f"JF playlist '{expected_jf_name}' not created"
    cleanup_both.track_jf(jf_pl["Id"])

    # 3. Delete the JF playlist.
    jf_client.delete_playlist(admin_token, jf_pl["Id"])

    # 4. Override config and run JF->TA sync.
    with config_override(JFTAPlaylistsDelete="false"):
        jf_ta_task = jf_client.get_task_id_by_name(admin_token, "JFToTubeArchivistPlaylistsSyncTask")
        assert jf_ta_task
        jf_client.wait_for_task(admin_token, jf_ta_task, timeout=180)
        time.sleep(2)

    # 5. Assert TA playlist still exists.
    ta_pl_after = ta_client.get_playlist(ta_token, ta_pl_id)
    assert ta_pl_after, \
        f"TA playlist {ta_pl_id} should still exist (JFTAPlaylistsDelete=false) but was deleted"


def test_ta_to_jf_delete_flag_false(
    admin_token: str, test_user_id: str, ta_token: str,
    cleanup_both, config_override,
):
    """TAJFPlaylistsDelete=false prevents TA->JF deletion.

    1. Create a TA custom playlist.
    2. Run TA->JF sync to create the JF counterpart.
    3. Delete the TA playlist.
    4. Override config: TAJFPlaylistsDelete=false, restart JF.
    5. Run TA->JF sync.
    6. Assert the JF playlist still exists.
    """
    # 1. Create TA custom playlist.
    ta_pl_name = f"DelFlagTAtoJF_{TEST_SUFFIX}"
    ta_pl = ta_client.create_custom_playlist(ta_token, ta_pl_name)
    assert ta_pl
    ta_pl_id = ta_pl.get("playlist_id")
    assert ta_pl_id

    # 2. Run TA->JF sync to create the JF counterpart.
    ta_jf_task = jf_client.get_task_id_by_name(admin_token, "TAToJellyfinPlaylistsSyncTask")
    assert ta_jf_task
    jf_client.wait_for_task(admin_token, ta_jf_task, timeout=180)

    expected_jf_name = f"{ta_pl_name} ({ta_pl_id})"
    jf_pl = jf_client.get_playlist_by_name(admin_token, test_user_id, expected_jf_name)
    assert jf_pl, f"JF playlist '{expected_jf_name}' not created"
    cleanup_both.track_jf(jf_pl["Id"])

    # 3. Delete the TA playlist.
    ta_client.delete_playlist(ta_token, ta_pl_id)

    # 4. Override config and run TA->JF sync.
    with config_override(TAJFPlaylistsDelete="false"):
        jf_client.wait_for_task(admin_token, ta_jf_task, timeout=180)
        time.sleep(2)

    # 5. Assert JF playlist still exists.
    jf_pl_after = jf_client.get_playlist_by_name(admin_token, test_user_id, expected_jf_name)
    assert jf_pl_after, \
        f"JF playlist '{expected_jf_name}' should still exist (TAJFPlaylistsDelete=false) but was deleted"
