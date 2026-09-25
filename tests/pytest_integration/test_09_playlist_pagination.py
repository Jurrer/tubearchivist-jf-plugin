"""test_09: TA->JF playlist pagination integration.

Verifies GetPlaylists pagination: playlists across multiple TA pages appear
in JF (not just page 1) after TAToJellyfinPlaylistsSyncTask runs.

The dev TA stack natively has 43 playlists across 3 pages (page_size=25,
last_page=2). This test treats the live inventory as a soft fixture — it
skips with a clear reason if the expected multi-page inventory is missing.

Issue 13.
"""

from __future__ import annotations

import pytest

from . import jf_client
from . import ta_client

pytestmark = pytest.mark.integration


def test_all_pages_playlists_in_jf(
    admin_token: str, test_user_id: str, ta_token: str,
):
    """All playlists across multiple TA pages appear in JF after sync.

    Asserts that TA has multiple pages (otherwise the pagination path is
    not exercised), then verifies every TA playlist ID appears in the JF
    playlist set after the sync task runs.
    """
    # 1. Fetch all TA playlists and verify pagination is active.
    first_page = ta_client.get_playlists(ta_token, page=0)
    paginate = first_page.get("paginate", {})
    last_page = paginate.get("last_page", 0)

    if last_page <= 1:
        pytest.skip(
            f"TA only has {last_page} page(s) of playlists; "
            "pagination path not exercised (need >= 2 pages)"
        )

    # 2. Get the full TA playlist inventory.
    ta_playlists = ta_client.get_all_playlists(ta_token)
    ta_ids = {pl.get("playlist_id") for pl in ta_playlists if pl.get("playlist_id")}
    assert ta_ids, "TA has no playlists"

    # 3. Run TA->JF playlists sync task.
    task_id = jf_client.get_task_id_by_name(admin_token, "TAToJellyfinPlaylistsSyncTask")
    assert task_id, "TAToJellyfinPlaylistsSyncTask not found"
    jf_client.wait_for_task(admin_token, task_id, timeout=180)

    # 4. Verify all TA playlist IDs appear in JF playlist names.
    jf_playlists = jf_client.get_playlists(admin_token, test_user_id)

    # Build a set of TA IDs extracted from JF playlist names.
    # JF playlist names end with "(TA_ID)" — extract the ID.
    jf_ta_ids = set()
    import re
    for pl in jf_playlists:
        match = re.match(r"^.*\((.+)\)$", pl.get("Name", ""))
        if match:
            jf_ta_ids.add(match.group(1))

    missing = ta_ids - jf_ta_ids
    assert not missing, (
        f"{len(missing)} TA playlists from later pages not found in JF. "
        f"Missing IDs: {list(missing)[:5]}..."
    )
