"""Spec-mirror unit tests for Utils.GetVideoNameFromPath and GetChannelNameFromPath.

Mirrors the C# path-parsing logic: the majority separator (backslash vs forward
slash) is detected from the path, then the last segment is returned.
For video names, the last ``.``-delimited extension is stripped.
No dev stack required.
"""

from __future__ import annotations

import pytest


def _detect_separator(path: str) -> str:
    backslash = path.count("\\")
    forward = path.count("/")
    return "\\" if backslash > forward else "/"


def get_video_name_from_path(path: str) -> str:
    sep = _detect_separator(path)
    last = path.split(sep)[-1]
    return last.split(".")[0]


def get_channel_name_from_path(path: str) -> str:
    sep = _detect_separator(path)
    return path.split(sep)[-1]


@pytest.mark.parametrize(
    "path, expected",
    [
        ("/data/TubeArchivist/Fireship/UCsBjURrPoezykLs9EqgamOA/video.mkv", "video"),
        ("/data/TubeArchivist/Fireship/UCsBjURrPoezykLs9EqgamOA/subdir/another.mp4", "another"),
        ("/data/TubeArchivist/Fireship/UCsBjURrPoezykLs9EqgamOA/name.with.dots.mp4", "name"),
    ],
)
def test_get_video_name_from_path_unix_separators(path, expected):
    assert get_video_name_from_path(path) == expected


@pytest.mark.parametrize(
    "path, expected",
    [
        (r"C:\data\TubeArchivist\Fireship\UCsBjURrPoezykLs9EqgamOA\video.mkv", "video"),
        (r"C:\data\TubeArchivist\Fireship\UCsBjURrPoezykLs9EqgamOA\subdir\another.mp4", "another"),
        (r"C:\data\TubeArchivist\Fireship\UCsBjURrPoezykLs9EqgamOA\name.with.dots.mp4", "name"),
    ],
)
def test_get_video_name_from_path_windows_separators(path, expected):
    assert get_video_name_from_path(path) == expected


@pytest.mark.parametrize(
    "path, expected",
    [
        ("/data/TubeArchivist/Fireship/UCsBjURrPoezykLs9EqgamOA", "UCsBjURrPoezykLs9EqgamOA"),
        ("/data/TubeArchivist/Gamers Nexus/UChIs72whgZI9w6d6FhwGGHA", "UChIs72whgZI9w6d6FhwGGHA"),
    ],
)
def test_get_channel_name_from_path_unix_separators(path, expected):
    assert get_channel_name_from_path(path) == expected


def test_get_channel_name_from_path_trailing_slash_returns_empty():
    # Documents current C# behavior: trailing slash → last segment is empty
    assert get_channel_name_from_path("/data/TubeArchivist/Fireship/UCsBjURrPoezykLs9EqgamOA/") == ""


@pytest.mark.parametrize(
    "path, expected",
    [
        (r"C:\data\TubeArchivist\Fireship\UCsBjURrPoezykLs9EqgamOA", "UCsBjURrPoezykLs9EqgamOA"),
    ],
)
def test_get_channel_name_from_path_windows_separators(path, expected):
    assert get_channel_name_from_path(path) == expected


def test_get_channel_name_from_path_trailing_backslash_returns_empty():
    assert get_channel_name_from_path(
        r"C:\data\TubeArchivist\Fireship\UCsBjURrPoezykLs9EqgamOA\\"
    ) == ""


@pytest.mark.parametrize(
    "path, expected",
    [
        # backslashes outnumber forward slashes → backslash is the separator
        (r"C:\mixed/path\channel-id", "channel-id"),
        # forward slashes outnumber backslashes → forward slash is the separator
        (r"/mixed\path/to/channel-id", "channel-id"),
    ],
)
def test_get_channel_name_from_path_mixed_separators_uses_majority(path, expected):
    assert get_channel_name_from_path(path) == expected
