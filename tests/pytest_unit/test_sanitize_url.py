"""Spec-mirror unit tests for Utils.SanitizeUrl.

Mirrors the C# ``Utils.SanitizeUrl`` behavior: schema preservation,
double-slash/space collapse, trailing-slash rules, query/fragment preservation.
No dev stack required.
"""

from __future__ import annotations

import re

import pytest

# Reimplementation of the C# SanitizeUrl logic for spec-mirroring.
# The C# source is the source of truth; these tests pin the observed behavior.
_SCHEMA_RE = re.compile(r"^(?P<schema>https?://)", re.IGNORECASE)
_SLASH_SPACE_RE = re.compile(r"[/\s]+")


def sanitize_url(input_url: str) -> str:
    """Mirror of Jellyfin.Plugin.TubeArchivistMetadata.Utilities.Utils.SanitizeUrl."""
    if not input_url or not input_url.strip():
        return ""

    schema_match = _SCHEMA_RE.match(input_url)
    schema_length = len(schema_match.group("schema")) if schema_match else 0
    rest = input_url[schema_length:]

    path_part = rest
    query_and_fragment = ""

    q_index = rest.find("?")
    f_index = rest.find("#")

    split_index = -1
    if q_index >= 0 and f_index >= 0:
        split_index = min(q_index, f_index)
    elif q_index >= 0:
        split_index = q_index
    elif f_index >= 0:
        split_index = f_index

    if split_index >= 0:
        path_part = rest[:split_index]
        query_and_fragment = rest[split_index:]

    cleaned_path = _SLASH_SPACE_RE.sub("/", path_part)
    cleaned_path = cleaned_path.lstrip("/")

    if not query_and_fragment:
        cleaned_path = cleaned_path.rstrip("/") + "/"

    schema = schema_match.group("schema") if schema_match else ""
    return schema + cleaned_path + query_and_fragment


@pytest.mark.parametrize(
    "input_url",
    [None, "", "   "],
)
def test_sanitize_url_null_or_whitespace_returns_empty(input_url):
    assert sanitize_url(input_url) == ""  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "input_url, expected",
    [
        ("http://example.com", "http://example.com/"),
        ("https://example.com", "https://example.com/"),
        ("HTTPS://example.com", "HTTPS://example.com/"),
        ("Http://Example.Com", "Http://Example.Com/"),
    ],
)
def test_sanitize_url_preserves_schema_and_case(input_url, expected):
    assert sanitize_url(input_url) == expected


@pytest.mark.parametrize(
    "input_url, expected",
    [
        ("http://example.com//path", "http://example.com/path/"),
        ("http://example.com///a//b///c", "http://example.com/a/b/c/"),
        ("http://example.com/path/", "http://example.com/path/"),
        ("http://example.com/path//", "http://example.com/path/"),
        ("http://example.com/ /path", "http://example.com/path/"),
        ("http://example.com/ / /path", "http://example.com/path/"),
    ],
)
def test_sanitize_url_collapses_double_slashes_and_spaces(input_url, expected):
    assert sanitize_url(input_url) == expected


@pytest.mark.parametrize(
    "input_url, expected",
    [
        ("http://example.com/path", "http://example.com/path/"),
        ("http://example.com/path/", "http://example.com/path/"),
        ("http://example.com/path///", "http://example.com/path/"),
    ],
)
def test_sanitize_url_adds_trailing_slash_when_no_query_or_fragment(input_url, expected):
    assert sanitize_url(input_url) == expected


@pytest.mark.parametrize(
    "input_url, expected",
    [
        ("http://example.com/path?q=1", "http://example.com/path?q=1"),
        ("http://example.com/path/?q=1", "http://example.com/path/?q=1"),
        ("http://example.com/path#frag", "http://example.com/path#frag"),
        ("http://example.com/path/#frag", "http://example.com/path/#frag"),
    ],
)
def test_sanitize_url_does_not_add_trailing_slash_when_query_or_fragment(input_url, expected):
    assert sanitize_url(input_url) == expected


@pytest.mark.parametrize(
    "input_url, expected",
    [
        ("http://example.com/path?q=1&r=2", "http://example.com/path?q=1&r=2"),
        ("http://example.com/path#section", "http://example.com/path#section"),
        ("http://example.com/path?q=1#frag", "http://example.com/path?q=1#frag"),
        ("http://example.com/path#frag?q=1", "http://example.com/path#frag?q=1"),
    ],
)
def test_sanitize_url_preserves_query_and_fragment(input_url, expected):
    assert sanitize_url(input_url) == expected


@pytest.mark.parametrize(
    "input_url, expected",
    [
        ("example.com/path", "example.com/path/"),
        ("example.com//path", "example.com/path/"),
        ("example.com/path?q=1", "example.com/path?q=1"),
    ],
)
def test_sanitize_url_no_schema_treats_whole_string_as_path(input_url, expected):
    assert sanitize_url(input_url) == expected
