"""test_05: TA->JF Progress Sync task integration.

Verifies TAToJellyfinProgressSyncTask, GetProgress, and GetVideo:
  - Setting TA progress + watched on a video, then triggering
    TAToJellyfinProgressSyncTask, updates JF user-data (position + Played).
  - TAJFProgressSync=false -> task is a no-op (logs "disabled").
  - Missing JFUsernamesTo user or missing Collection -> task logs skips.

Issue 09.
"""

from __future__ import annotations

import time

import pytest

from . import jf_client
from . import ta_client

pytestmark = pytest.mark.integration

TA_COLLECTION = "ta"
# Position (seconds) we set in TA. Picked to be distinctive.
TA_POSITION_SECONDS = 142


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


def _reset_ta_state(ta_token: str, yt_id: str) -> None:
    """Reset a video's TA watched + progress to a clean unwatched state."""
    ta_client.set_watched(ta_token, yt_id, False)
    ta_client.delete_progress(ta_token, yt_id)


def _reset_and_register(cleanup, ta_token: str, yt_id: str) -> None:
    """Reset TA state now and on test teardown."""
    _reset_ta_state(ta_token, yt_id)
    cleanup.register(lambda: _reset_ta_state(ta_token, yt_id))


def _reset_jf_user_data(admin_token: str, user_id: str, item_id: str) -> None:
    """Reset JF user-data for an item to unplayed, zero position."""
    jf_client.update_user_data(
        admin_token, user_id, item_id,
        {"PlaybackPositionTicks": 0, "Played": False},
    )


def test_ta_progress_and_watched_synced_to_jf(
    admin_token: str, test_user_id: str, ta_token: str,
    tracked_episode: dict, cleanup,
):
    """Setting TA progress + watched and triggering the task updates JF user-data.

    Covers TAToJellyfinProgressSyncTask, GetProgress, GetVideo.
    """
    yt_id = tracked_episode["ProviderIds"]["TubeArchivist"]
    item_id = tracked_episode["Id"]
    _reset_and_register(cleanup, ta_token, yt_id)
    _reset_jf_user_data(admin_token, test_user_id, item_id)

    # Set TA progress + watched=true.
    ta_client.set_progress(ta_token, yt_id, TA_POSITION_SECONDS)
    ta_client.set_watched(ta_token, yt_id, True)
    time.sleep(1)

    # Trigger the TA->JF progress sync task.
    task_id = jf_client.get_task_id_by_name(admin_token, "TAToJellyfinProgressSyncTask")
    assert task_id, "TAToJellyfinProgressSyncTask not found in scheduled tasks"
    jf_client.wait_for_task(admin_token, task_id, timeout=120)

    # Poll JF user-data for the test user.
    deadline = time.time() + 30
    user_data = {}
    while time.time() < deadline:
        user_data = jf_client.get_user_data(admin_token, test_user_id, item_id)
        if user_data.get("Played") or (user_data.get("PlaybackPositionTicks", 0) or 0) > 0:
            break
        time.sleep(2)

    # Assert Played flag reflects TA watched=true.
    assert user_data.get("Played") is True, \
        f"JF Played flag not set to true, got {user_data.get('Played')}"

    # Assert playback position reflects TA progress.
    ticks = user_data.get("PlaybackPositionTicks", 0) or 0
    jf_seconds = ticks / 10_000_000
    assert abs(jf_seconds - TA_POSITION_SECONDS) < 3, \
        f"JF position {jf_seconds}s != expected ~{TA_POSITION_SECONDS}s"


def test_ta_progress_sync_disabled_is_noop(
    admin_token: str, test_user_id: str, ta_token: str,
    tracked_episode: dict, cleanup, config_override, jf_logs,
):
    """TAJFProgressSync=false -> task is a no-op (logs 'disabled')."""
    yt_id = tracked_episode["ProviderIds"]["TubeArchivist"]
    item_id = tracked_episode["Id"]
    _reset_and_register(cleanup, ta_token, yt_id)
    _reset_jf_user_data(admin_token, test_user_id, item_id)

    with config_override(TAJFProgressSync="false"):
        task_id = jf_client.get_task_id_by_name(admin_token, "TAToJellyfinProgressSyncTask")
        assert task_id
        jf_client.wait_for_task(admin_token, task_id, timeout=120)
        logs = jf_logs(500)

    assert "disabled" in logs.lower(), \
        "Expected 'disabled' in JF logs when TAJFProgressSync=false"

    # JF user-data should remain unplayed/zero.
    user_data = jf_client.get_user_data(admin_token, test_user_id, item_id)
    assert not user_data.get("Played"), \
        "JF Played should be False when sync is disabled"


def test_missing_user_logs_skip(
    admin_token: str, ta_token: str, tracked_episode: dict, cleanup,
    config_override, jf_logs,
):
    """Missing JFUsernamesTo user -> task logs skip."""
    yt_id = tracked_episode["ProviderIds"]["TubeArchivist"]
    _reset_and_register(cleanup, ta_token, yt_id)

    with config_override(JFUsernamesTo="nonexistent_user_xyz"):
        task_id = jf_client.get_task_id_by_name(admin_token, "TAToJellyfinProgressSyncTask")
        assert task_id
        jf_client.wait_for_task(admin_token, task_id, timeout=120)
        logs = jf_logs(500)

    assert "not found" in logs.lower(), \
        "Expected 'not found' in JF logs for missing user"


def test_missing_collection_logs_critical(
    admin_token: str, test_user_id: str, ta_token: str,
    tracked_episode: dict, cleanup, config_override, jf_logs,
):
    """Missing Collection -> task logs critical/skip."""
    yt_id = tracked_episode["ProviderIds"]["TubeArchivist"]
    _reset_and_register(cleanup, ta_token, yt_id)

    with config_override(CollectionTitle="nonexistent_collection_xyz"):
        task_id = jf_client.get_task_id_by_name(admin_token, "TAToJellyfinProgressSyncTask")
        assert task_id
        jf_client.wait_for_task(admin_token, task_id, timeout=120)
        logs = jf_logs(500)

    assert "not found" in logs.lower(), \
        "Expected 'not found' in JF logs for missing collection"
