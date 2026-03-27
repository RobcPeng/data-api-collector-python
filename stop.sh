#!/usr/bin/env bash
# =============================================================================
# Data API Collector — Stop Everything
# =============================================================================
# Stops Docker stack and any running zrok tunnels.
# Shortcut for: ./start.sh --stop
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"$SCRIPT_DIR/start.sh" --stop
