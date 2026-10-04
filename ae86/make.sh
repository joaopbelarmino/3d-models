#!/usr/bin/env bash
# Full pipeline: build from scratch -> export for Roblox -> validation renders.
# BLENDER_PY must be a Python with the `bpy` 5.0 module (pip install bpy==5.0.1, Python 3.11).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PY="${BLENDER_PY:-python3}"
OUT="$HERE/export"
TMP="$(mktemp -d)"

"$PY" "$HERE/build.py" "$TMP/build.blend"
"$PY" "$HERE/export.py" "$TMP/build.blend" "$OUT"
if [[ "${SKIP_RENDERS:-0}" != "1" ]]; then
  "$PY" "$HERE/final_renders.py" "$OUT/ae86_trueno.blend" "$HERE/renders"
fi
rm -rf "$TMP"
echo "done: $OUT"
