# Test Suite

Two-tier test suite for the TubeArchivistMetadata Jellyfin plugin.

## Tiers

### Unit tier (C# xUnit)

Tests pure plugin logic without a running Jellyfin or TubeArchivist instance:

- `Utils` static methods (`SanitizeUrl`, `GetVideoNameFromPath`, `GetChannelNameFromPath`, `GetTAPlaylistIdFromName`, `GetTAPlaylistNameFromName`, `FormatDescription`)
- JSON deserialization contracts (video, channel, playlist, paginated playlist, ping, progress, watched, player) against committed fixtures in `Fixtures/`
- `Video.ToEpisode`, `Channel.ToSeries`, `ToSearchResult` mappers (including `NumberingScheme.YYYYMMDD` branch)

Location: `tests/TubeArchivistMetadata.UnitTests/`

### Integration tier (Python pytest)

Tests the deployed plugin DLL through Jellyfin's and TubeArchivist's HTTP APIs — no mocking, no source-level injection.

Location: `tests/pytest_integration/`

Test files:

| File | Issue | Coverage |
|---|---|---|
| `test_01_connectivity.py` | 05 | Plugin loaded in dev JF; TA ping with Token header |
| `test_02_metadata.py` | 06 | Episode + series metadata & images from TA |
| `test_03_jf_to_ta_progress.py` | 07 | JF→TA progress sync (OnPlaybackProgress) |
| `test_04_jf_to_ta_watched_status.py` | 08 | JF→TA watched-status sync (OnWatchedStatusChange) |
| `test_05_ta_to_jf_progress.py` | 09 | TA→JF progress sync task |
| `test_06_ta_to_jf_playlists.py` | 10 | TA→JF playlist sync task |
| `test_07_jf_to_ta_playlists.py` | 11 | JF→TA playlist sync task |
| `test_08_playlist_delete_flag.py` | 12 | Playlist delete-flag (both directions) |
| `test_09_playlist_pagination.py` | 13 | TA→JF playlist pagination |
| `test_10_collection_boundary.py` | 14 | Collection-boundary consolidation |

### Python spec-mirror unit tier

Python unit tests mirroring the C# unit tier (for environments without .NET SDK):

Location: `tests/pytest_unit/`

## How to run

### Full suite (build, deploy, test)

```sh
./scripts/run-tests.sh
```

This rebuilds the plugin, deploys it to the dev Jellyfin, restarts the container, and runs both tiers.

### Unit tier only

```sh
./scripts/run-tests.sh --unit-only
```

Or directly via the SDK container:

```sh
docker run --rm -v "$(pwd):/src" -w /src mcr.microsoft.com/dotnet/sdk:10.0 \
    dotnet test TubeArchivistMetadata.sln -c Debug
```

### Integration tier only

```sh
./scripts/run-tests.sh --integration-only
```

Or directly:

```sh
python -m pytest tests/pytest_integration -m integration -v
```

### Skip integration tests (Python spec-mirror only)

```sh
python -m pytest -m "not integration"
```

## Prerequisites

- **Docker** — for building the plugin and running the dev stack
- **Dev stack running** — start with `docker compose --profile dev up -d` from `dev-jellyfin/`
- **Dev Jellyfin** at `http://127.0.0.1:18096` (container `jf-plugin-dev`)
- **Dev TubeArchivist** at `http://192.168.0.152:18000`
- **Two JF users**: `test admin`/`verysecure` (administrator) and `test user`/`verystrong` (regular user)
- **TubeArchivist API token** — fetched automatically by the test suite via the documented login recipe
- **Python 3.12+** with `pytest` and `requests` installed (a `.venv` is recommended)

## Markers

- `integration` — marks tests requiring the dev Jellyfin + TubeArchivist stack. Deselect with `-m "not integration"`.

## Fixtures and helpers

- `conftest.py` — session-scoped fixtures: stack-up guard, TA token, JF admin/test tokens, hermetic plugin config, library scan, per-test cleanup, config override context manager.
- `jf_client.py` — Jellyfin HTTP client helpers (auth, items, user-data, scheduled tasks, playlists, logs).
- `ta_client.py` — TubeArchivist HTTP client helpers (login, ping, video, channel, playlists, progress, watched).

## Hermetic config

The integration suite uses a hermetic plugin config (`conftest.py` writes it to the plugin's XML config file) that sets all sync flags to `true`, configures `test user` as both `JFUsernameFrom` and `JFUsernamesTo`, and points at the dev TubeArchivist. The original config is backed up and restored on teardown. JF is restarted when the config is written and when it is restored.
