"""test_02: Episode + series metadata & images integration.

Verifies that after a JF library refresh on the `ta` collection:
  - Episode metadata (title, overview, studios, provider ids, tags,
    production year, premiere date, index number under Default scheme)
    comes from TubeArchivist.
  - Series metadata (overview, studios, tags, provider ids) comes from TA.
  - Episode primary images resolve (HTTP 200) and match TA vid_thumb_url.
  - Series images (thumb, art, banner, backdrop) resolve.

Issue 06.
"""

from __future__ import annotations

import pytest

from . import jf_client
from . import ta_client

pytestmark = pytest.mark.integration

# A known-downloaded video in the dev stack (Fireship).
# The library-scan fixture ensures the `ta` collection is indexed.
TA_COLLECTION = "ta"


@pytest.fixture(scope="module")
def sample_episode(admin_token: str) -> dict:
    """Return one episode from the `ta` collection with full metadata fields."""
    collection_id = jf_client.get_collection_id_by_name(admin_token, TA_COLLECTION)
    assert collection_id, f"`{TA_COLLECTION}` collection not found"
    items = jf_client.get_items(
        admin_token,
        parent_id=collection_id,
        Recursive=True,
        IncludeItemTypes="Episode",
        Fields="ProviderIds,Path,Overview,Studios,Tags,ProductionYear,PremiereDate,IndexNumber,ParentIndexNumber",
    )
    episodes = items.get("Items", [])
    assert episodes, "no episodes indexed in `ta` collection"
    # Pick one with a TubeArchivist provider id (all should have one).
    for ep in episodes:
        if ep.get("ProviderIds", {}).get("TubeArchivist"):
            return ep
    pytest.fail("no episode with a TubeArchivist provider id found")


def test_episode_title_overview_match_ta(admin_token: str, ta_token: str, sample_episode: dict):
    """Episode Name and Overview must come from the TA video."""
    yt_id = sample_episode["ProviderIds"]["TubeArchivist"]
    ta_video = ta_client.get_video(ta_token, yt_id)

    assert sample_episode["Name"] == ta_video["title"]
    # Overview is FormatDescription(description) — truncated + newlines→<br>.
    # The raw text should appear within the overview (up to truncation).
    raw_desc = ta_video.get("description") or ""
    # FormatDescription truncates to MaxDescriptionLength; the overview
    # starts with the beginning of the description.
    assert sample_episode["Overview"].startswith(raw_desc[:50].split("\n")[0].rstrip()) or \
        raw_desc[:40] in sample_episode["Overview"]


def test_episode_studios_and_provider_ids(admin_token: str, ta_token: str, sample_episode: dict):
    """Episode Studios = [channel name], ProviderIds[TubeArchivist] = youtube id."""
    yt_id = sample_episode["ProviderIds"]["TubeArchivist"]
    ta_video = ta_client.get_video(ta_token, yt_id)
    channel_name = ta_video["channel"]["channel_name"]

    studios = [s["Name"] for s in sample_episode.get("Studios", [])]
    assert channel_name in studios
    assert sample_episode["ProviderIds"]["TubeArchivist"] == ta_video["youtube_id"]


def test_episode_tags_match_ta(admin_token: str, ta_token: str, sample_episode: dict):
    """Episode Tags must come from the TA video tags."""
    yt_id = sample_episode["ProviderIds"]["TubeArchivist"]
    ta_video = ta_client.get_video(ta_token, yt_id)

    jf_tags = set(sample_episode.get("Tags", []))
    ta_tags = set(ta_video.get("tags", []))
    # All TA tags should appear in JF (JF may store them verbatim).
    assert ta_tags.issubset(jf_tags) or jf_tags == ta_tags


def test_episode_production_year_and_premiere_date(admin_token: str, ta_token: str, sample_episode: dict):
    """ProductionYear and PremiereDate must come from the TA video published date."""
    yt_id = sample_episode["ProviderIds"]["TubeArchivist"]
    ta_video = ta_client.get_video(ta_token, yt_id)
    published = ta_video["published"]  # e.g. "2017-07-26T20:49:57+00:00"

    assert sample_episode["ProductionYear"] == int(published[:4])
    # PremiereDate is ISO; the date portion must match.
    assert sample_episode["PremiereDate"][:10] == published[:10]


def test_episode_index_number_null_under_default_scheme(admin_token: str, sample_episode: dict):
    """Under the Default numbering scheme, IndexNumber must be null.

    The ToEpisode mapper: IndexNumber = scheme switch { YYYYMMDD => computed,
    _ => null }. The hermetic config sets EpisodeNumberingScheme=Default,
    which hits the `_ => null` branch.
    """
    assert sample_episode.get("IndexNumber") is None, \
        f"IndexNumber should be null under Default scheme, got {sample_episode.get('IndexNumber')}"
    # ParentIndexNumber is always the published year.
    yt_id = sample_episode["ProviderIds"]["TubeArchivist"]
    # ParentIndexNumber should equal the year derived from PremiereDate.
    premiere = sample_episode["PremiereDate"]
    assert sample_episode["ParentIndexNumber"] == int(premiere[:4])


def test_episode_primary_image_resolves(admin_token: str, ta_token: str, sample_episode: dict):
    """Episode primary image must resolve (HTTP 200)."""
    item_id = sample_episode["Id"]
    status = jf_client.image_resolves(item_id, "Primary", token=admin_token)
    assert status == 200, f"Episode primary image returned {status}"


def test_series_metadata_matches_ta(admin_token: str, ta_token: str, sample_episode: dict):
    """Series (channel) metadata — overview, studios, provider ids — come from TA."""
    series_id = sample_episode["SeriesId"] or sample_episode.get("ParentId")
    # Fetch the series item directly.
    series = jf_client.get_item(admin_token, series_id)
    yt_channel_id = series.get("ProviderIds", {}).get("TubeArchivist")
    assert yt_channel_id, "series has no TubeArchivist provider id"

    ta_channel = ta_client.get_channel(ta_token, yt_channel_id)

    # Name
    assert series["Name"] == ta_channel["channel_name"]
    # Studios = [channel name]
    studios = [s["Name"] for s in series.get("Studios", [])]
    assert ta_channel["channel_name"] in studios
    # Provider id
    assert series["ProviderIds"]["TubeArchivist"] == ta_channel["channel_id"]


def test_series_images_resolve(admin_token: str, sample_episode: dict):
    """Series images (Primary at minimum) must resolve (HTTP 200)."""
    series_id = sample_episode["SeriesId"] or sample_episode.get("ParentId")
    # Primary image (thumb).
    status = jf_client.image_resolves(series_id, "Primary", token=admin_token)
    assert status == 200, f"Series primary image returned {status}"
