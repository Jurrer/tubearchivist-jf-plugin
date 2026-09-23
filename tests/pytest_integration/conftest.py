"""Pytest configuration and shared fixtures for the integration test suite.

Fixtures:
  - stack_up (autouse, session): pings JF /Health and TA /api/ping/; skips
    integration tests if either is down.
  - ta_token (session): fetched per run via the documented login recipe.
  - admin_token / test_user (session): JF admin and test user access tokens.
  - admin_user_id / test_user_id (session): their JF user ids.
  - hermetic_config (session): backs up the live plugin config XML, writes a
    hermetic test config, restores the original on teardown.
  - library_scan (session): triggers a JF library scan on the `ta` collection
    and polls for completion before any integration test runs.
  - cleanup (function): per-test cleanup registry; resets TA progress/watched
    state on specific videos and deletes TA/JF playlists created during tests.
"""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from typing import Any, Callable

import pytest
import requests

from . import jf_client
from . import ta_client

# The plugin config XML on disk (dev JF 10.11).
CONFIG_XML = (
    Path(__file__).resolve().parents[3]
    / "dev-jellyfin"
    / "config-10.11"
    / "data"
    / "plugins"
    / "configurations"
    / "Jellyfin.Plugin.TubeArchivistMetadata.xml"
)
BACKUP_XML = CONFIG_XML.with_suffix(".xml.bak")

# The hermetic test config: test user as both JFUsernameFrom and JFUsernamesTo,
# all sync flags enabled so every sync path is active during tests.
HERMETIC_CONFIG = """<?xml version="1.0" encoding="utf-8"?>
<PluginConfiguration xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <CollectionTitle>ta</CollectionTitle>
  <TubeArchivistUrl>http://tubearchivist:8000/</TubeArchivistUrl>
  <TubeArchivistApiKey>{ta_key}</TubeArchivistApiKey>
  <MaxDescriptionLength>1000</MaxDescriptionLength>
  <TAJFProgressSync>true</TAJFProgressSync>
  <JFTAProgressSync>true</JFTAProgressSync>
  <JFTAPlaylistsSync>true</JFTAPlaylistsSync>
  <JFTAPlaylistsDelete>true</JFTAPlaylistsDelete>
  <TAJFPlaylistsSync>true</TAJFPlaylistsSync>
  <TAJFPlaylistsDelete>true</TAJFPlaylistsDelete>
  <JFUsernameFrom>{test_user}</JFUsernameFrom>
  <JFUsernamesTo>{test_user}</JFUsernamesTo>
  <TAJFProgressTaskInterval>3600</TAJFProgressTaskInterval>
  <JFTAPlaylistsSyncTaskInterval>3600</JFTAPlaylistsSyncTaskInterval>
  <TAJFPlaylistsSyncTaskInterval>3600</TAJFPlaylistsSyncTaskInterval>
  <EpisodeNumberingScheme>Default</EpisodeNumberingScheme>
</PluginConfiguration>
"""


def _stack_reachable() -> tuple[bool, str]:
    """Ping JF /Health and TA /api/ping/; return (reachable, reason)."""
    try:
        r = requests.get(f"{jf_client.JF_URL}/Health", timeout=5)
        if r.status_code != 200:
            return False, f"JF /Health returned {r.status_code}"
    except Exception as e:
        return False, f"JF unreachable: {e}"
    try:
        # TA needs a token; just verify the HTTP port answers
        r = requests.get(f"{ta_client.TA_URL}/api/ping/", timeout=5)
        # 401/403 means the port is up and answering — good enough for the guard
        if r.status_code not in (200, 401, 403):
            return False, f"TA /api/ping/ returned {r.status_code}"
    except Exception as e:
        return False, f"TA unreachable: {e}"
    return True, ""


# ---------------------------------------------------------------------------
# Autouse stack-up guard (session-scoped)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def stack_up() -> None:
    reachable, reason = _stack_reachable()
    if not reachable:
        pytest.skip(f"dev stack not reachable: {reason}")


# ---------------------------------------------------------------------------
# TA token (session)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def ta_token() -> str:
    return ta_client.login_and_get_token()


# ---------------------------------------------------------------------------
# JF admin + test user tokens (session)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def admin_token(hermetic_config: Any) -> str:
    # Authenticate AFTER hermetic_config has restarted JF with the test config,
    # so the token is valid for the rest of the session.
    return jf_client.authenticate(jf_client.ADMIN_USER, jf_client.ADMIN_PASS)


@pytest.fixture(scope="session")
def test_user_token(hermetic_config: Any) -> str:
    return jf_client.authenticate(jf_client.TEST_USER, jf_client.TEST_PASS)


@pytest.fixture(scope="session")
def admin_user_id(admin_token: str) -> str:
    user = jf_client.get_user_by_name(admin_token, jf_client.ADMIN_USER)
    assert user, "test admin user not found in JF"
    return user["Id"]


@pytest.fixture(scope="session")
def test_user(test_user_token: str) -> dict[str, Any]:
    user = jf_client.get_user_by_name(test_user_token, jf_client.TEST_USER)
    assert user, "test user not found in JF"
    return user


@pytest.fixture(scope="session")
def test_user_id(test_user: dict[str, Any]) -> str:
    return test_user["Id"]


# ---------------------------------------------------------------------------
# Hermetic plugin config (session)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def hermetic_config(ta_token: str) -> Any:
    """Back up the live plugin config, write a hermetic test config, restore on teardown."""
    backup = CONFIG_XML.read_text()
    BACKUP_XML.write_text(backup)

    # Write hermetic config with the test user and current TA key
    hermetic = HERMETIC_CONFIG.format(
        ta_key=_resolve_ta_key(),
        test_user=jf_client.TEST_USER,
    )
    CONFIG_XML.write_text(hermetic)
    _restart_jf()

    yield

    CONFIG_XML.write_text(backup)
    BACKUP_XML.unlink(missing_ok=True)
    _restart_jf()


def _jf_api_ready(timeout: int = 90) -> bool:
    """Wait for JF to be fully ready — /Health 200 AND an authenticated
    /Users call succeeds. JF returns 200 on /Health before the library
    subsystem is ready for API calls (returns 503 on /Library/*).
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if requests.get(f"{jf_client.JF_URL}/Health", timeout=3).status_code != 200:
                time.sleep(2)
                continue
            # Authenticated endpoint must succeed — proves the full
            # request pipeline is up, not just Kestrel.
            token = jf_client.authenticate(jf_client.ADMIN_USER, jf_client.ADMIN_PASS)
            jf_client.get_users(token)
            time.sleep(2)  # let the plugin finish initializing
            return True
        except Exception:
            time.sleep(2)
    return False


def _resolve_ta_key() -> str:
    """Read the TA API key from the live config (the plugin's TubeArchivistApiKey)."""
    import re

    text = CONFIG_XML.read_text()
    m = re.search(r"<TubeArchivistApiKey>([^<]+)</TubeArchivistApiKey>", text)
    return m.group(1) if m else ""


def _restart_jf() -> None:
    import subprocess

    subprocess.run(
        ["docker", "restart", "jf-plugin-dev"],
        check=True,
        capture_output=True,
        timeout=60,
    )
    if not _jf_api_ready():
        pytest.fail("JF did not come back up after restart")


# ---------------------------------------------------------------------------
# Library scan on the `ta` collection (session-scoped)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def library_scan(admin_token: str, hermetic_config: Any) -> None:
    """Trigger a JF library scan on the `ta` collection and wait for completion."""
    collection_id = None
    deadline = time.time() + 60
    last_err = None
    while time.time() < deadline:
        try:
            collection_id = jf_client.get_collection_id_by_name(admin_token, "ta")
        except Exception as e:
            collection_id = None
            last_err = e
        if collection_id:
            break
        time.sleep(2)
    if not collection_id:
        pytest.skip(f"`ta` collection not found in JF; cannot bootstrap library scan (last_err={last_err})")

    jf_client.trigger_library_scan(admin_token, collection_id)

    # Poll the scan: wait until the collection has indexed items
    deadline = time.time() + 120
    while time.time() < deadline:
        try:
            items = jf_client.get_items(
                admin_token,
                parent_id=collection_id,
                Recursive=True,
                IncludeItemTypes="Episode",
            )
            if items.get("TotalRecordCount", 0) > 0:
                return
        except Exception:
            pass
        time.sleep(3)
    # Not fatal — individual tests will assert what they need
    return


# ---------------------------------------------------------------------------
# Per-test cleanup registry (function-scoped)
# ---------------------------------------------------------------------------

@pytest.fixture
def cleanup(ta_token: str, admin_token: str) -> Any:
    """Per-test cleanup registry.

    Tests register teardown callbacks (e.g. reset TA progress, delete playlists).
    Registered callbacks run in reverse order at test teardown.
    """
    callbacks: list[Callable[[], None]] = []

    def register(fn: Callable[[], None]) -> None:
        callbacks.append(fn)

    registry = type("CleanupRegistry", (), {"register": register})()
    yield registry

    for fn in reversed(callbacks):
        try:
            fn()
        except Exception as e:
            print(f"cleanup callback failed: {e}")
