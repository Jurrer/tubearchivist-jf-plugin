"""test_01: Connectivity — plugin loaded in dev Jellyfin + TA ping with Token header.

Verifies:
  - The TubeArchivistMetadata plugin is loaded in dev Jellyfin (log check).
  - The configured TA URL/API-key produce a successful ping with a Token Authorization header.
"""

from __future__ import annotations

import subprocess

import pytest

from . import ta_client

pytestmark = pytest.mark.integration


def test_plugin_loaded_in_jellyfin():
    """The plugin DLL must be loaded — check JF logs for the plugin name."""
    result = subprocess.run(
        ["docker", "logs", "jf-plugin-dev"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    logs = result.stdout + result.stderr
    # Jellyfin logs plugin loading; the plugin GUID or name should appear.
    # The plugin name in the manifest is "TubeArchivist Metadata".
    assert "TubeArchivist" in logs, "TubeArchivist plugin not found in JF logs"


def test_ta_ping_succeeds_with_token(ta_token: str):
    """The configured TA URL/API-key must produce a successful ping."""
    resp = ta_client.ping(ta_token)
    assert resp["response"] == "pong"
    assert "version" in resp


def test_ta_token_has_access_to_video_endpoints(ta_token: str):
    """The token must authorize access to video endpoints (used by progress/watched tests)."""
    # Fetch the TA video list to confirm the token works for data endpoints.
    import requests

    resp = requests.get(
        f"{ta_client.TA_URL}/api/video/",
        headers={"Authorization": f"Token {ta_token}"},
        params={"page": 0, "page_size": 1},
        timeout=10,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "data" in data
    assert len(data["data"]) >= 1, "TA has no downloaded videos; dev stack needs test data"
