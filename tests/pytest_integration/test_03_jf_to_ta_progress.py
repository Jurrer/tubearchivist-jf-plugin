"""test_03: JF->TA Progress Sync integration.

Verifies OnPlaybackProgress + TubeArchivistApi.SetProgress:
  - JF playback progress for the tracked user (JFUsernameFrom) reaches TA.
  - Progress on an item outside the Collection boundary is NOT pushed to TA.
  - Progress for a user other than JFUsernameFrom is NOT pushed to TA.

Issue 07.
"""

from __future__ import annotations

import time

import pytest

from . import jf_client
from . import ta_client

pytestmark = pytest.mark.integration

TA_COLLECTION = "ta"
# Position (seconds) we push from JF. Picked to be distinctive and < duration.
JF_POSITION_SECONDS = 137
JF_POSITION_TICKS = JF_POSITION_SECONDS * 10_000_000  # JF uses 100ns ticks


@pytest.fixture(scope="module")
def tracked_episode(admin_token: str, test_user_id: str) -> dict:
    """An episode in the `ta` collection, with its JF Id and TA youtube id."""
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
    pytest.fail("no episode with a TubeArchivist provider id found")


def _ta_position(ta_token: str, yt_id: str) -> float | None:
    """Read TA playback position from the video's player.position."""
    v = ta_client.get_video(ta_token, yt_id)
    return v.get("player", {}).get("position")


def _reset_ta_progress(ta_token: str, yt_id: str) -> None:
    """Reset TA progress for a video (DELETE — set_progress(0) is a no-op in TA)."""
    ta_client.delete_progress(ta_token, yt_id)


def _reset_and_register(cleanup, ta_token: str, yt_id: str) -> None:
    """Reset TA progress now and on test teardown."""
    _reset_ta_progress(ta_token, yt_id)
    cleanup.register(lambda: _reset_ta_progress(ta_token, yt_id))


def test_jf_playback_progress_reaches_ta(
    admin_token: str, test_user_token: str, test_user_id: str,
    ta_token: str, tracked_episode: dict, cleanup,
):
    """JF playback progress for the tracked user must reach TA."""
    yt_id = tracked_episode["ProviderIds"]["TubeArchivist"]
    item_id = tracked_episode["Id"]
    _reset_and_register(cleanup, ta_token, yt_id)

    # Report progress as the test user (JFUsernameFrom in hermetic config).
    jf_client.report_playback_progress(test_user_token, test_user_id, item_id, JF_POSITION_TICKS)

    # The plugin's OnPlaybackProgress fires asynchronously; poll TA.
    deadline = time.time() + 30
    seen = None
    while time.time() < deadline:
        seen = _ta_position(ta_token, yt_id)
        if seen is not None and seen > 0:
            break
        time.sleep(2)

    assert seen is not None, "TA player.position is missing"
    # The plugin converts ticks→seconds (long)ticks/TicksPerSecond.
    # Allow a small delta for rounding/TA storage.
    assert abs(seen - JF_POSITION_SECONDS) < 3, \
        f"TA position {seen} != expected ~{JF_POSITION_SECONDS}"


def test_progress_outside_collection_boundary_not_pushed(
    admin_token: str, test_user_token: str, test_user_id: str,
    ta_token: str, tracked_episode: dict, cleanup,
):
    """Progress on an item outside the Collection boundary is NOT pushed to TA.

    The `Movies` collection is outside the `ta` boundary. Reporting progress on
    a movie must not update the tracked TA video's position. The plugin derives
    the YT id from the item's path via GetVideoNameFromPath (filename stem); a
    movie's stem won't match a real TA youtube id, so SetProgress should 404
    and not mutate any real TA video.
    """
    movies_id = jf_client.get_collection_id_by_name(admin_token, "Movies")
    if not movies_id:
        pytest.skip("no `Movies` collection to test outside-boundary guard")
    items = jf_client.get_items(
        admin_token, parent_id=movies_id, Recursive=True,
        IncludeItemTypes="Movie", Fields="ProviderIds",
    )
    outside = items.get("Items", [])
    if not outside:
        pytest.skip("no movie in `Movies` collection to test boundary guard")
    item = outside[0]

    yt_id = tracked_episode["ProviderIds"]["TubeArchivist"]
    _reset_and_register(cleanup, ta_token, yt_id)
    before = _ta_position(ta_token, yt_id)

    jf_client.report_playback_progress(test_user_token, test_user_id, item["Id"], JF_POSITION_TICKS)

    deadline = time.time() + 10
    while time.time() < deadline:
        seen = _ta_position(ta_token, yt_id)
        if seen is not None and seen > 0:
            break
        time.sleep(2)

    assert seen is None or seen == 0, \
        f"TA position changed to {seen} for outside-boundary item — should not have been pushed"


def test_progress_for_untracked_user_not_pushed(
    admin_token: str, ta_token: str, tracked_episode: dict, cleanup,
):
    """Progress for a user other than JFUsernameFrom is NOT pushed to TA.

    The admin user is NOT JFUsernameFrom (which is `test user`). Reporting
    progress as admin must not update the TA video's position.
    """
    yt_id = tracked_episode["ProviderIds"]["TubeArchivist"]
    item_id = tracked_episode["Id"]
    _reset_and_register(cleanup, ta_token, yt_id)

    admin_id = jf_client.get_user_by_name(admin_token, jf_client.ADMIN_USER)["Id"]
    # Report as admin (NOT the tracked user).
    jf_client.report_playback_progress(admin_token, admin_id, item_id, JF_POSITION_TICKS)

    # Give the async handler a window.
    time.sleep(8)
    seen = _ta_position(ta_token, yt_id)
    # Position should remain ~0 (not pushed).
    assert seen is None or seen == 0, \
        f"TA position changed to {seen} for untracked user — should not have been pushed"
