#!/usr/bin/env bash
# run-tests.sh — rebuild, deploy, and run the full test suite.
#
# Usage: ./scripts/run-tests.sh [--unit-only | --integration-only]
#
# Steps:
#   1. Build the plugin via the dotnet SDK container (dotnet publish).
#   2. Copy the DLL to the dev Jellyfin plugin directory.
#   3. Restart jf-plugin-dev so the new DLL loads.
#   4. Run the C# unit tier (dotnet test).
#   5. Run the Python integration tier (pytest tests/pytest_integration).
#
# Prerequisites:
#   - Docker daemon running.
#   - Dev stack up: docker compose --profile dev up -d (from dev-jellyfin/).
#   - The dev Jellyfin container is named jf-plugin-dev (port 18096).
#   - The dev TubeArchivist is at http://192.168.0.152:18000.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SDK_IMAGE="mcr.microsoft.com/dotnet/sdk:10.0"
# Dev Jellyfin config dir — change to config-12.1 for JF 12.1.
CONFIG_DIR="config-10.11"
PLUGIN_DIR="$REPO_ROOT/../dev-jellyfin/$CONFIG_DIR/plugins/TubeArchivistMetadata"
JF_CONTAINER="jf-plugin-dev"

RUN_UNIT=true
RUN_INTEGRATION=true

while [[ $# -gt 0 ]]; do
    case "$1" in
        --unit-only)
            RUN_INTEGRATION=false
            shift
            ;;
        --integration-only)
            RUN_UNIT=false
            shift
            ;;
        *)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
    esac
done

echo "=== TubeArchivistMetadata Test Suite ==="
echo "Repo root: $REPO_ROOT"
echo ""

# ---------------------------------------------------------------------------
# 1. Build + deploy the plugin
# ---------------------------------------------------------------------------
if [[ "$RUN_INTEGRATION" == "true" ]]; then
    echo "--- Building and deploying plugin ---"
    # Publish directly into the mounted plugin dir so the DLL persists.
    docker run --rm \
        -v "$REPO_ROOT:/src" \
        -v "$PLUGIN_DIR:/out" \
        -w /src \
        "$SDK_IMAGE" \
        dotnet publish TubeArchivistMetadata.sln -c Debug -o /out

    echo "--- Restarting $JF_CONTAINER ---"
    docker restart "$JF_CONTAINER"

    # Wait for JF to be ready.
    echo "--- Waiting for Jellyfin to be ready ---"
    deadline=$((SECONDS + 90))
    while [[ $SECONDS -lt $deadline ]]; do
        if curl -sf "http://127.0.0.1:18096/Health" >/dev/null 2>&1; then
            echo "Jellyfin is up."
            break
        fi
        sleep 2
    done
    if ! curl -sf "http://127.0.0.1:18096/Health" >/dev/null 2>&1; then
        echo "ERROR: Jellyfin did not come up after restart." >&2
        exit 1
    fi
    # Give the plugin time to initialize.
    sleep 5
    echo ""
fi

# ---------------------------------------------------------------------------
# 2. C# unit tier
# ---------------------------------------------------------------------------
if [[ "$RUN_UNIT" == "true" ]]; then
    echo "--- Running C# unit tier (dotnet test) ---"
    docker run --rm -v "$REPO_ROOT:/src" -w /src "$SDK_IMAGE" \
        dotnet test TubeArchivistMetadata.sln -c Debug \
        --verbosity normal
    echo ""
fi

# ---------------------------------------------------------------------------
# 3. Python integration tier
# ---------------------------------------------------------------------------
if [[ "$RUN_INTEGRATION" == "true" ]]; then
    echo "--- Running Python integration tier (pytest) ---"
    cd "$REPO_ROOT"
    if [[ -d .venv ]]; then
        source .venv/bin/activate
    fi
    python -m pytest tests/pytest_integration -m integration -v
    echo ""
fi

echo "=== Test suite complete ==="
