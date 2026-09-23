"""Spec-mirror unit tests for Utils.GetTAPlaylistIdFromName and GetTAPlaylistNameFromName.

Mirrors the C# playlist-name regex parsing for both the YouTube
``Name - Channel (ID)`` format and the custom ``Name (ID)`` format.
No dev stack required.
"""

from __future__ import annotations

import re

import pytest

_TA_PLAYLIST_ID_RE = re.compile(r"^(.*)\((.*)\)$")
_YT_PLAYLIST_NAME_RE = re.compile(r"^(.*)\s\-\s(.*)\s\((.*)\)$")
_TA_PLAYLIST_NAME_RE = re.compile(r"^(.*)\s\((.*)\)$")


def get_ta_playlist_id_from_name(playlist_name: str) -> str:
    """Mirror of Utils.GetTAPlaylistIdFromName."""
    m = _TA_PLAYLIST_ID_RE.match(playlist_name)
    return m.group(2) if m else ""


def get_ta_playlist_name_from_name(playlist_name: str) -> str:
    """Mirror of Utils.GetTAPlaylistNameFromName."""
    yt_match = _YT_PLAYLIST_NAME_RE.match(playlist_name)
    if yt_match:
        return yt_match.group(1)

    m = _TA_PLAYLIST_NAME_RE.match(playlist_name)
    return m.group(1) if m else ""


@pytest.mark.parametrize(
    "name, expected",
    [
        ("My Playlist - Fireship (PL12345)", "PL12345"),
        ("Best Videos - Gamers Nexus (PLabc-DEF789)", "PLabc-DEF789"),
        ("Name with (parens) inside - Channel (PLxyz)", "PLxyz"),
    ],
)
def test_get_ta_playlist_id_from_name_youtube_format(name, expected):
    assert get_ta_playlist_id_from_name(name) == expected


@pytest.mark.parametrize(
    "name, expected",
    [
        ("My Custom Playlist (PLcustom123)", "PLcustom123"),
        ("Simple (abc-def-456)", "abc-def-456"),
    ],
)
def test_get_ta_playlist_id_from_name_custom_format(name, expected):
    assert get_ta_playlist_id_from_name(name) == expected


def test_get_ta_playlist_id_from_name_no_parens_returns_empty():
    assert get_ta_playlist_id_from_name("PlaylistWithoutId") == ""


@pytest.mark.parametrize(
    "name, expected",
    [
        ("My Playlist - Fireship (PL12345)", "My Playlist"),
        ("Best Videos - Gamers Nexus (PLabc-DEF789)", "Best Videos"),
    ],
)
def test_get_ta_playlist_name_from_name_youtube_format(name, expected):
    assert get_ta_playlist_name_from_name(name) == expected


@pytest.mark.parametrize(
    "name, expected",
    [
        ("My Custom Playlist (PLcustom123)", "My Custom Playlist"),
        ("Simple (abc-def-456)", "Simple"),
    ],
)
def test_get_ta_playlist_name_from_name_custom_format(name, expected):
    assert get_ta_playlist_name_from_name(name) == expected


def test_get_ta_playlist_name_from_name_nested_parens_youtube_format():
    assert (
        get_ta_playlist_name_from_name("Name with (parens) inside - Channel (PLxyz)")
        == "Name with (parens) inside"
    )


def test_get_ta_playlist_name_from_name_no_parens_returns_empty():
    assert get_ta_playlist_name_from_name("PlaylistWithoutId") == ""
