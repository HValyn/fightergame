#!/usr/bin/env bash
# Run the Godot simulation tests headlessly.  Usage: scripts/run_godot_tests.sh [filter]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GODOT="${GODOT:-godot}"
# first run on a fresh checkout: build the class cache
[ -d "$ROOT/godot/.godot" ] || "$GODOT" --headless --path "$ROOT/godot" --import >/dev/null 2>&1 || true
exec "$GODOT" --headless --path "$ROOT/godot" -s res://tests/run_tests.gd -- "$@"
