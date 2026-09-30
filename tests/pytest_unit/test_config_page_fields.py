"""Static-analysis test: verify configPage.html round-trips every PluginConfiguration field.

Parses ``PluginConfiguration.cs`` for all public serializable properties and
checks that each one appears in **both** the load (pageshow) and save (submit)
JavaScript handlers inside ``configPage.html``.

This catches the class of bug where a property is added to the C# model and the
HTML checkbox/input is added to the form, but the JavaScript that reads/writes
the value is forgotten — exactly what happened with ``JFTAPlaylistsDelete`` and
``TAJFPlaylistsDelete`` (present since commit d386f79, never wired up in JS).

No dev stack required.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Locate source files relative to the repo root.
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]

CONFIG_CS = (
    REPO_ROOT
    / "Jellyfin.Plugin.TubeArchivistMetadata"
    / "Configuration"
    / "PluginConfiguration.cs"
)

CONFIG_HTML = (
    REPO_ROOT
    / "Jellyfin.Plugin.TubeArchivistMetadata"
    / "Configuration"
    / "configPage.html"
)

# ---------------------------------------------------------------------------
# Parse PluginConfiguration.cs for public properties.
# ---------------------------------------------------------------------------

# Matches:  public <type> <Name> { get; set; }
# Also matches multi-line property declarations with backing fields:
#   public string TubeArchivistUrl
#       {
#           get { ... }
#           set { ... }
#       }
_SIMPLE_PROP_RE = re.compile(
    r"^\s*public\s+(?:\w+(?:<[^>]+>)?(?:\[\]|\??)?)\s+(\w+)\s*\{\s*get;\s*set;\s*\}",
    re.MULTILINE,
)

# Matches the *name* on the line:  public <type> <Name>  (followed by newline or {)
_MULTI_LINE_PROP_RE = re.compile(
    r"^\s*public\s+(?:\w+(?:<[^>]+>)?(?:\[\]|\??)?)\s+(\w+)\s*$",
    re.MULTILINE,
)


def _extract_properties(cs_source: str) -> set[str]:
    """Return the set of public property names declared in PluginConfiguration.cs."""
    props: set[str] = set()

    # Simple auto-properties:  public bool Foo { get; set; }
    for m in _SIMPLE_PROP_RE.finditer(cs_source):
        props.add(m.group(1))

    # Multi-line properties with get/set blocks:  public string Foo\n { get ... set ... }
    # These have the name on a line by itself, followed by a block containing get/set.
    for m in _MULTI_LINE_PROP_RE.finditer(cs_source):
        name = m.group(1)
        # Check that the following block contains both get and set.
        tail = cs_source[m.end():]
        block_match = re.match(r"\s*\{[^}]*\bget\b[^}]*\bset\b", tail, re.DOTALL)
        if block_match:
            props.add(name)

    # Exclude methods and non-serializable members.
    props.discard("GetJFUsernamesToArray")

    return props


# ---------------------------------------------------------------------------
# Parse configPage.html into load and save sections.
# ---------------------------------------------------------------------------

def _split_html_handlers(html: str) -> tuple[str, str]:
    """Split the JavaScript in configPage.html into the load and save code blocks.

    The load handler is inside the ``pageshow`` listener.
    The save handler is inside the ``submit`` listener.
    """
    # The pageshow handler ends where the submit handler begins.
    pageshow_match = re.search(
        r"pageshow.*?function\s*\([^)]*\)\s*\{(.*?)\}\s*\)\s*;",
        html,
        re.DOTALL,
    )
    submit_match = re.search(
        r"submit.*?function\s*\([^)]*\)\s*\{(.*?)\}\s*\)\s*;",
        html,
        re.DOTALL,
    )

    load_code = pageshow_match.group(1) if pageshow_match else ""
    save_code = submit_match.group(1) if submit_match else ""
    return load_code, save_code


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def cs_source() -> str:
    return CONFIG_CS.read_text()

@pytest.fixture(scope="module")
def html_source() -> str:
    return CONFIG_HTML.read_text()

@pytest.fixture(scope="module")
def properties(cs_source: str) -> set[str]:
    return _extract_properties(cs_source)

@pytest.fixture(scope="module")
def handler_codes(html_source: str) -> tuple[str, str]:
    return _split_html_handlers(html_source)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_all_properties_present_in_load_handler(
    properties: set[str],
    handler_codes: tuple[str, str],
):
    """Every PluginConfiguration property must be loaded in the pageshow handler."""
    load_code, _ = handler_codes
    missing = {
        prop
        for prop in properties
        if f"config.{prop}" not in load_code
    }
    assert not missing, (
        f"Properties missing from the configPage.html load (pageshow) handler: "
        f"{sorted(missing)}.  Add a line like: "
        f"document.querySelector('#Name').checked/value = config.Name;"
    )


def test_all_properties_present_in_save_handler(
    properties: set[str],
    handler_codes: tuple[str, str],
):
    """Every PluginConfiguration property must be saved in the submit handler."""
    _, save_code = handler_codes
    missing = {
        prop
        for prop in properties
        if f"config.{prop}" not in save_code
    }
    assert not missing, (
        f"Properties missing from the configPage.html save (submit) handler: "
        f"{sorted(missing)}.  Add a line like: "
        f"config.Name = document.querySelector('#Name').checked/value;"
    )


def test_all_properties_have_html_input(
    properties: set[str],
    html_source: str,
):
    """Every PluginConfiguration property should have a corresponding HTML input element."""
    missing = {
        prop
        for prop in properties
        if f'id="{prop}"' not in html_source and f"id='{prop}'" not in html_source
    }
    assert not missing, (
        f"Properties without an HTML input element in configPage.html: {sorted(missing)}."
    )


def test_html_inputs_have_load_and_save(
    properties: set[str],
    handler_codes: tuple[str, str],
):
    """Every HTML input with a matching property should be wired up in both handlers."""
    load_code, save_code = handler_codes
    # Gather all input IDs from the HTML.
    input_ids = set(re.findall(r'id="([^"]+)"', _read_html_inputs_only()))
    relevant = input_ids & properties  # only IDs that match config properties

    missing_load = {pid for pid in relevant if f"#{pid}" not in load_code}
    missing_save = {pid for pid in relevant if f"#{pid}" not in save_code}

    assert not missing_load, f"HTML inputs not loaded in pageshow: {sorted(missing_load)}"
    assert not missing_save, f"HTML inputs not saved in submit: {sorted(missing_save)}"


def _read_html_inputs_only() -> str:
    """Return only the HTML portion (before <script>) of configPage.html."""
    html = CONFIG_HTML.read_text()
    script_idx = html.find("<script")
    return html[:script_idx] if script_idx != -1 else html
