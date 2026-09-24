"""TubeArchivist HTTP client helpers for the integration test suite.

All calls go to the dev TubeArchivist at http://192.168.0.152:18000.
Auth uses a Django REST Token fetched via the documented login recipe.
"""

from __future__ import annotations

import json
import time
from typing import Any
from pathlib import Path

import requests

TA_URL = "http://192.168.0.152:18000"
TA_USER = "tubearchivist"
TA_PASS = "verysecret"


def login_and_get_token() -> str:
    """Login and fetch the Django REST Token (documented recipe)."""
    cookies_path = Path("/tmp/ta_test_cookies.txt")
    # 1. login (sets session cookie)
    resp = requests.post(
        f"{TA_URL}/api/user/login/",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"username": TA_USER, "password": TA_PASS}),
        timeout=10,
        allow_redirects=True,
    )
    resp.raise_for_status()
    cookies_path.write_text("")
    with cookies_path.open("w") as f:
        for k, v in resp.cookies.items():
            f.write(f"{k}={v}; path=/\n")
    # 2. fetch token
    resp2 = requests.get(
        f"{TA_URL}/api/appsettings/token/",
        cookies=resp.cookies,
        timeout=10,
    )
    resp2.raise_for_status()
    token = resp2.json()["token"]
    cookies_path.unlink(missing_ok=True)
    return token


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Token {token}", "Content-Type": "application/json"}


def ping(token: str) -> dict[str, Any]:
    resp = requests.get(f"{TA_URL}/api/ping/", headers=_headers(token), timeout=10)
    resp.raise_for_status()
    return resp.json()


def get_video(token: str, video_id: str) -> dict[str, Any]:
    resp = requests.get(f"{TA_URL}/api/video/{video_id}/", headers=_headers(token), timeout=10)
    resp.raise_for_status()
    return resp.json()


def get_channel(token: str, channel_id: str) -> dict[str, Any]:
    resp = requests.get(f"{TA_URL}/api/channel/{channel_id}/", headers=_headers(token), timeout=10)
    resp.raise_for_status()
    return resp.json()


def get_playlists(token: str, page: int = 0) -> dict[str, Any]:
    resp = requests.get(
        f"{TA_URL}/api/playlist/",
        params={"page": page, "page_size": 25},
        headers=_headers(token),
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def get_all_playlists(token: str) -> list[dict[str, Any]]:
    """Walk all pages of playlists."""
    all_pl: list[dict[str, Any]] = []
    page = 0
    while True:
        data = get_playlists(token, page=page)
        items = data.get("data", [])
        all_pl.extend(items)
        paginate = data.get("paginate", {})
        last_page = paginate.get("last_page", 0)
        current = paginate.get("current_page", 0)
        if current >= last_page or not items:
            # TA pages are 0-indexed; last_page is the count of pages
            if page >= last_page:
                break
        page += 1
        if page > 50:  # safety
            break
    return all_pl


def get_playlist(token: str, playlist_id: str) -> dict[str, Any]:
    resp = requests.get(f"{TA_URL}/api/playlist/{playlist_id}/", headers=_headers(token), timeout=10)
    resp.raise_for_status()
    return resp.json()


def set_progress(token: str, video_id: str, position: int) -> None:
    resp = requests.post(
        f"{TA_URL}/api/video/{video_id}/progress/",
        headers=_headers(token),
        data=json.dumps({"position": position}),
        timeout=10,
    )
    resp.raise_for_status()


def get_progress(token: str, video_id: str) -> dict[str, Any]:
    resp = requests.get(f"{TA_URL}/api/video/{video_id}/progress/", headers=_headers(token), timeout=10)
    if resp.status_code == 404:
        return {}
    resp.raise_for_status()
    return resp.json()


def delete_progress(token: str, video_id: str) -> None:
    """Delete playback progress for a video (the only reliable reset — set_progress(0) is a no-op)."""
    resp = requests.delete(f"{TA_URL}/api/video/{video_id}/progress/", headers=_headers(token), timeout=10)
    if resp.status_code not in (200, 204, 404):
        resp.raise_for_status()


def set_watched(token: str, item_id: str, watched: bool) -> None:
    resp = requests.post(
        f"{TA_URL}/api/watched/",
        headers=_headers(token),
        data=json.dumps({"id": item_id, "is_watched": watched}),
        timeout=10,
    )
    resp.raise_for_status()


def get_watched(token: str, item_id: str) -> bool:
    """Get watched status for a video or channel id."""
    resp = requests.get(f"{TA_URL}/api/watched/{item_id}", headers=_headers(token), timeout=10)
    if resp.status_code == 404:
        return False
    resp.raise_for_status()
    return resp.json().get("is_watched", False)


def create_custom_playlist(token: str, name: str) -> dict[str, Any]:
    resp = requests.post(
        f"{TA_URL}/api/playlist/",
        headers=_headers(token),
        data=json.dumps({"playlist_name": name, "playlist_type": "custom"}),
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def delete_playlist(token: str, playlist_id: str) -> None:
    resp = requests.delete(
        f"{TA_URL}/api/playlist/{playlist_id}/",
        headers=_headers(token),
        timeout=10,
    )
    resp.raise_for_status()


def custom_playlist_action(token: str, playlist_id: str, action: str, video_id: str) -> None:
    resp = requests.post(
        f"{TA_URL}/api/playlist/{playlist_id}/",
        headers=_headers(token),
        data=json.dumps({"action": action, "video_id": video_id}),
        timeout=10,
    )
    resp.raise_for_status()
