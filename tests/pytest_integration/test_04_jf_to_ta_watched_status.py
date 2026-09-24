"""test_04: JF->TA watched-status integration.

Verifies OnWatchedStatusChange + TubeArchivistApi.SetWatchedStatus:
- Marking an Episode played via JF flips TA video player.watched to true
  (and progress is pushed).
- Marking an Episode unplayed flips TA player.watched to false.
- Marking a Series (channel) played fires OnWatchedStatusChange per child
  Episode, pushing watched=true to TA for each video.

Issue 08.
"""

from __future__ import annotations

import time

import pytest

from . import jf_client
from . import ta_client

pytestmark = pytest.mark.integration

TA_COLLECTION = "ta"


@pytest.fixture(scope="module")
def tracked_episode(admin_token: str, test_user_id: str) -> dict:
    """An episode in `ta` collection with a TubeArchivist provider id."""
    collection_id = jf_client.get_collection_id_by_name(admin_token, TA_COLLECTION)
    assert collection_id, f"`{TA_COLLECTION}` collection not found"
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


def _ta_watched(ta_token: str, yt_id: str) -> bool:
    """Read TA watched status from the video object's player.watched."""
    v = ta_client.get_video(ta_token, yt_id)
    return bool(v.get("player", {}).get("watched", False))


def _reset_ta_state(ta_token: str, yt_id: str) -> None:
    """Reset a video's TA watched + progress to a clean unwatched state."""
    ta_client.set_watched(ta_token, yt_id, False)
    ta_client.delete_progress(ta_token, yt_id)


def _reset_and_register(cleanup, ta_token: str, yt_id: str) -> None:
    _reset_ta_state(ta_token, yt_id)
    cleanup.register(lambda: _reset_ta_state(ta_token, yt_id))


def test_mark_episode_played_flips_ta_watched_true(
    test_user_token: str, test_user_id: str, ta_token: str,
    tracked_episode: dict, cleanup,
):
    """Marking a JF Episode played flips TA player.watched to true.

    Covers OnWatchedStatusChange Episode branch + SetWatchedStatus(true).
    Also asserts progress is pushed (OnWatchedStatusChange pushes progress
    after SetWatchedStatus for Episodes).
    """
    yt_id = tracked_episode["ProviderIds"]["TubeArchivist"]
    item_id = tracked_episode["Id"]
    _reset_and_register(cleanup, ta_token, yt_id)

    # Ensure starting state is unwatched.
    assert _ta_watched(ta_token, yt_id) is False

    jf_client.mark_played(test_user_token, test_user_id, item_id)

    # OnWatchedStatusChange is async; poll TA.
    deadline = time.time() + 30
    seen = False
    while time.time() < deadline:
        seen = _ta_watched(ta_token, yt_id)
        if seen:
            break
        time.sleep(2)

    assert seen, "TA player.watched did not flip to true after marking played"

    # OnWatchedStatusChange also pushes progress for Episodes. mark_played
    # resets JF PlaybackPositionTicks to 0, so the plugin calls SetProgress(0).
    # TA treats progress(0) as a no-op and stores no position, so player.position
    # is null/absent — that null state confirms no leftover progress remains.
    v = ta_client.get_video(ta_token, yt_id)
    pos = v.get("player", {}).get("position")
    assert not pos, f"TA position should be null/0 after mark_played reset, got {pos}"


def test_mark_episode_unplayed_flips_ta_watched_false(
    test_user_token: str, test_user_id: str, ta_token: str,
    tracked_episode: dict, cleanup,
):
    """Marking a JF Episode unplayed flips TA player.watched to false.

    Covers the unplayed branch of OnWatchedStatusChange.
    """
    yt_id = tracked_episode["ProviderIds"]["TubeArchivist"]
    item_id = tracked_episode["Id"]
    _reset_and_register(cleanup, ta_token, yt_id)

    # First mark it played so we have a known watched=true state to flip from.
    ta_client.set_watched(ta_token, yt_id, True)
    time.sleep(1)
    assert _ta_watched(ta_token, yt_id) is True

    # Now mark unplayed via JF.
    jf_client.mark_unplayed(test_user_token, test_user_id, item_id)

    deadline = time.time() + 30
    seen = True
    while time.time() < deadline:
        seen = _ta_watched(ta_token, yt_id)
        if not seen:
            break
        time.sleep(2)

    assert seen is False, "TA player.watched did not flip to false after marking unplayed"


def test_mark_series_played_flips_ta_channel_watched(
    admin_token: str, test_user_token: str, test_user_id: str,
    ta_token: str, tracked_episode: dict, cleanup,
):
    """Marking a JF Series (channel) played pushes watched=true to TA for its videos.

    OnWatchedStatusChange: when eventArgs.Item is Series, itemYTId comes from
    GetChannelNameFromPath (channel id) and SetWatchedStatus is called with
    that channel id. But Folder.MarkPlayed propagates to child Episodes — each
    child fires UserDataSaved as an Episode (not Series), so the Episode branch
    runs for each video, calling SetWatchedStatus(videoId, true).

    We assert that at least one video in the series flips to watched=true in TA.
    Uses the tracked_episode's series.
    """
    series_id = tracked_episode.get("SeriesId") or tracked_episode.get("ParentId")
    assert series_id, "tracked episode has no series id"
    yt_id = tracked_episode["ProviderIds"]["TubeArchivist"]
    _reset_and_register(cleanup, ta_token, yt_id)

    assert _ta_watched(ta_token, yt_id) is False

    # Mark the entire series played via JF (propagates to all child episodes).
    jf_client.mark_played(test_user_token, test_user_id, series_id)

    # Poll: the tracked episode's video should flip to watched=true in TA.
    deadline = time.time() + 40
    seen = False
    while time.time() < deadline:
        seen = _ta_watched(ta_token, yt_id)
        if seen:
            break
        time.sleep(2)

    assert seen, (
        "TA player.watched did not flip to true after marking Series played — "
        "OnWatchedStatusChange Episode branch (via Folder.MarkPlayed propagation) "
        "did not reach TA"
    )
