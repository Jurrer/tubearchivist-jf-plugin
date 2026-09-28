"""Jellyfin HTTP client helpers for the integration test suite.

All calls go to the dev Jellyfin at http://127.0.0.1:18096.
Auth uses the X-Emby-Authorization header (MediaBrowser scheme).
"""

from __future__ import annotations

import json
from typing import Any

import requests

JF_URL = "http://127.0.0.1:18096"
# Test identities (per spec).
ADMIN_USER = "test admin"
ADMIN_PASS = "verysecure"
TEST_USER = "test user"
TEST_PASS = "verystrong"

_DEFAULT_DEVICE_ID = "tameta-test-runner"
_token_device_ids: dict[str, str] = {}


def _device_id_for_user(user: str) -> str:
    return "tameta-" + user.replace(" ", "-").lower()


def _auth_header(token: str | None = None, user: str | None = None, pw: str | None = None) -> dict[str, str]:
    """Build the X-Emby-Authorization header, with optional token."""
    if token and token in _token_device_ids:
        device_id = _token_device_ids[token]
    elif user:
        device_id = _device_id_for_user(user)
    else:
        device_id = _DEFAULT_DEVICE_ID
    header = (
        f'MediaBrowser Client="TAMetaTests", Device="test", '
        f'DeviceId="{device_id}", Version="1.0.0"'
    )
    if token:
        header += f', Token="{token}"'
    if user:
        header += f', UserName="{user}"'
    return {"X-Emby-Authorization": header, "Content-Type": "application/json"}


def authenticate(user: str, pw: str) -> str:
    """Authenticate by name, return the access token."""
    resp = requests.post(
        f"{JF_URL}/Users/AuthenticateByName",
        headers=_auth_header(user=user, pw=pw),
        data=json.dumps({"Username": user, "Pw": pw}),
        timeout=10,
    )
    resp.raise_for_status()
    token = resp.json()["AccessToken"]
    _token_device_ids[token] = _device_id_for_user(user)
    return token


def get_users(token: str) -> list[dict[str, Any]]:
    resp = requests.get(f"{JF_URL}/Users", headers=_auth_header(token), timeout=10)
    resp.raise_for_status()
    return resp.json()


def get_user_by_name(token: str, name: str) -> dict[str, Any] | None:
    for u in get_users(token):
        if u.get("Name") == name:
            return u
    return None


def get_items(token: str, parent_id: str | None = None, **params: Any) -> dict[str, Any]:
    """Get items from JF, walking all API pages.

    JF paginates /Items by default (returns a subset with
    TotalRecordCount). We walk StartIndex/Limit to collect everything.
    """
    import time

    p: dict[str, Any] = {"Recursive": True, "Limit": 200}
    p.update(params)
    if parent_id:
        p["ParentId"] = parent_id

    all_items: list[dict[str, Any]] = []
    start = 0
    total = 1  # placeholder to enter loop
    while start < total:
        p["StartIndex"] = start
        resp = requests.get(f"{JF_URL}/Items", params=p, headers=_auth_header(token), timeout=30)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("Items", [])
        all_items.extend(items)
        total = data.get("TotalRecordCount", 0)
        start += len(items)
        if not items:
            break

    return {"Items": all_items, "TotalRecordCount": total}


def get_item(token: str, item_id: str) -> dict[str, Any]:
    resp = requests.get(f"{JF_URL}/Items/{item_id}", headers=_auth_header(token), timeout=10)
    resp.raise_for_status()
    return resp.json()


def get_user_data(token: str, user_id: str, item_id: str) -> dict[str, Any]:
    resp = requests.get(
        f"{JF_URL}/Users/{user_id}/Items/{item_id}/UserData",
        headers=_auth_header(token),
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def update_user_data(token: str, user_id: str, item_id: str, data: dict[str, Any]) -> dict[str, Any]:
    resp = requests.post(
        f"{JF_URL}/Users/{user_id}/Items/{item_id}/UserData",
        headers=_auth_header(token),
        data=json.dumps(data),
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json() if resp.content else {}


def mark_played(token: str, user_id: str, item_id: str) -> dict[str, Any]:
    """Mark an item played via /UserPlayedItems (propagates to children for folders)."""
    resp = requests.post(
        f"{JF_URL}/UserPlayedItems/{item_id}",
        params={"userId": user_id},
        headers=_auth_header(token),
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json() if resp.content else {}


def mark_unplayed(token: str, user_id: str, item_id: str) -> dict[str, Any]:
    """Mark an item unplayed via DELETE /UserPlayedItems (propagates to children for folders)."""
    resp = requests.delete(
        f"{JF_URL}/UserPlayedItems/{item_id}",
        params={"userId": user_id},
        headers=_auth_header(token),
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json() if resp.content else {}


def report_playback_progress(token: str, user_id: str, item_id: str, position_ticks: int) -> None:
    """Report playback progress to trigger OnPlaybackProgress.

    A /Sessions/Playing (playback start) call is needed first to establish an
    active session in SessionManager — OnPlaybackProgress bails out if no
    session exists for the request (GetSession returns null → early return,
    PlaybackProgress event never fires, plugin never sees it).
    """
    start_data = {
        "ItemId": item_id,
        "PositionTicks": 0,
        "IsPaused": True,
        "PlayMethod": "DirectStream",
    }
    resp = requests.post(
        f"{JF_URL}/Sessions/Playing",
        headers=_auth_header(token),
        data=json.dumps(start_data),
        timeout=10,
    )
    resp.raise_for_status()

    data = {
        "ItemId": item_id,
        "PositionTicks": position_ticks,
        "IsPaused": True,
        "PlayMethod": "DirectStream",
    }
    resp = requests.post(
        f"{JF_URL}/Sessions/Playing/Progress",
        headers=_auth_header(token),
        data=json.dumps(data),
        timeout=10,
    )
    resp.raise_for_status()


def get_scheduled_tasks(token: str) -> list[dict[str, Any]]:
    resp = requests.get(f"{JF_URL}/ScheduledTasks", headers=_auth_header(token), timeout=10)
    resp.raise_for_status()
    return resp.json()


def trigger_task(token: str, task_id: str) -> None:
    resp = requests.post(
        f"{JF_URL}/ScheduledTasks/Running/{task_id}",
        headers=_auth_header(token),
        timeout=10,
    )
    resp.raise_for_status()


def wait_for_task(token: str, task_id: str, timeout: int = 120) -> None:
    import time

    deadline = time.time() + timeout
    trigger_task(token, task_id)
    # Wait for the task to actually enter Running state before checking
    # for completion. Without this, the poll can see "Idle" (task hasn't
    # started yet) and return prematurely.
    start_deadline = time.time() + 15
    while time.time() < start_deadline:
        tasks = {t["Id"]: t for t in get_scheduled_tasks(token)}
        state = tasks.get(task_id, {}).get("State")
        if state == "Running":
            break
        time.sleep(0.5)
    # Now wait for the task to finish (leave Running state).
    while time.time() < deadline:
        tasks = {t["Id"]: t for t in get_scheduled_tasks(token)}
        state = tasks.get(task_id, {}).get("State")
        if state != "Running":
            return
        time.sleep(2)
    raise TimeoutError(f"Scheduled task {task_id} did not finish within {timeout}s")


def trigger_library_scan(token: str, collection_id: str) -> None:
    """Trigger a library scan by refreshing the collection folder.

    Uses /Items/{id}/Refresh with FullRefresh to index the CollectionFolder.
    """
    resp = requests.post(
        f"{JF_URL}/Items/{collection_id}/Refresh",
        params={
            "Recursive": "true",
            "MetadataRefreshMode": "FullRefresh",
            "ImageRefreshMode": "FullRefresh",
            "ReplaceAllMetadata": "false",
        },
        headers=_auth_header(token),
        timeout=10,
    )
    # 204 No Content on success; tolerate non-error statuses
    if resp.status_code not in (200, 202, 204):
        resp.raise_for_status()


def get_collections(token: str) -> list[dict[str, Any]]:
    """List CollectionFolders (library roots) via MediaFolders."""
    resp = requests.get(
        f"{JF_URL}/Library/MediaFolders",
        headers=_auth_header(token),
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("Items", [])


def get_collection_id_by_name(token: str, name: str) -> str | None:
    for c in get_collections(token):
        if c.get("Name") == name:
            return c.get("Id")
    return None


def get_playlists(token: str, user_id: str) -> list[dict[str, Any]]:
    """Get all playlists visible to a user, walking all API pages."""
    all_items: list[dict[str, Any]] = []
    start = 0
    while True:
        resp = requests.get(
            f"{JF_URL}/Users/{user_id}/Items",
            params={"IncludeItemTypes": "Playlist", "Recursive": True, "StartIndex": start, "Limit": 200},
            headers=_auth_header(token),
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("Items", [])
        all_items.extend(items)
        total = data.get("TotalRecordCount", 0)
        start += len(items)
        if not items or start >= total:
            break
    return all_items


def get_playlist(token: str, playlist_id: str) -> dict[str, Any]:
    resp = requests.get(f"{JF_URL}/Playlists/{playlist_id}", headers=_auth_header(token), timeout=10)
    resp.raise_for_status()
    return resp.json()


def create_playlist(token: str, user_id: str, name: str, item_ids: list[str] | None = None) -> dict[str, Any]:
    data = {"Name": name, "UserId": user_id}
    if item_ids:
        data["Ids"] = ",".join(item_ids)
    resp = requests.post(
        f"{JF_URL}/Playlists",
        headers=_auth_header(token),
        params={"Name": name, "UserId": user_id, "Ids": ",".join(item_ids) if item_ids else ""},
        timeout=10,
    )
    resp.raise_for_status()
    if resp.content:
        return resp.json()
    # Some JF versions return the playlist id in Location or require a follow-up
    return {"Name": name}


def delete_playlist(token: str, playlist_id: str) -> None:
    resp = requests.delete(f"{JF_URL}/Items/{playlist_id}", headers=_auth_header(token), timeout=10)
    resp.raise_for_status()


def get_playlist_items(token: str, playlist_id: str) -> list[dict[str, Any]]:
    resp = requests.get(
        f"{JF_URL}/Playlists/{playlist_id}/Items",
        headers=_auth_header(token),
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("Items", [])


def get_image_url(token: str, item_id: str, image_type: str = "Primary") -> str:
    """Return the JF image URL (no token needed for images on dev)."""
    return f"{JF_URL}/Items/{item_id}/Images/{image_type}"


def image_resolves(item_id: str, image_type: str = "Primary", token: str | None = None) -> int:
    headers = _auth_header(token) if token else {}
    resp = requests.get(f"{JF_URL}/Items/{item_id}/Images/{image_type}", headers=headers, timeout=10, stream=True)
    return resp.status_code


def get_task_id_by_name(token: str, name: str) -> str | None:
    """Find a scheduled task ID by its Name field."""
    for t in get_scheduled_tasks(token):
        if t.get("Name") == name:
            return t.get("Id")
    return None


def get_jf_logs(lines: int = 500) -> str:
    """Return recent JF container logs (stdout + stderr)."""
    import subprocess

    result = subprocess.run(
        ["docker", "logs", "jf-plugin-dev", "--tail", str(lines)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.stdout + result.stderr


def get_playlist_by_name(token: str, user_id: str, name: str) -> dict[str, Any] | None:
    """Find a JF playlist by exact name."""
    for pl in get_playlists(token, user_id):
        if pl.get("Name") == name:
            return pl
    return None


def get_episodes_with_provider_id(token: str, collection_id: str) -> list[dict[str, Any]]:
    """Return episodes in a collection that have a TubeArchivist provider id."""
    items = get_items(
        token,
        parent_id=collection_id,
        Recursive=True,
        IncludeItemTypes="Episode",
        Fields="ProviderIds,Path",
    )
    return [
        ep for ep in items.get("Items", [])
        if ep.get("ProviderIds", {}).get("TubeArchivist")
    ]


def add_to_playlist(token: str, playlist_id: str, item_ids: list[str]) -> None:
    """Add items to an existing JF playlist."""
    resp = requests.post(
        f"{JF_URL}/Playlists/{playlist_id}/Items",
        headers=_auth_header(token),
        params={"ids": ",".join(item_ids)},
        timeout=10,
    )
    resp.raise_for_status()


def remove_from_playlist(token: str, playlist_id: str, item_ids: list[str]) -> None:
    """Remove items from a JF playlist."""
    for item_id in item_ids:
        resp = requests.delete(
            f"{JF_URL}/Playlists/{playlist_id}/Items",
            headers=_auth_header(token),
            params={"entryIds": item_id},
            timeout=10,
        )
        if resp.status_code not in (200, 204):
            resp.raise_for_status()
