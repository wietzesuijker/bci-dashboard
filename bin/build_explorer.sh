#!/usr/bin/env bash
# Rebuild the complete photo catalogue and its standalone browser offline.
set -euo pipefail

REPO="${BCI_DASHBOARD_REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
DATA="${BCI_DASHBOARD_DATA:-$REPO/data}"
BUILD="${BCI_DASHBOARD_BUILD:-$REPO/build}"
mkdir -p "$BUILD"

REPRESENTATION=()
if [ -f "$BUILD/embedding-atlas.json" ]; then
  REPRESENTATION=(--plantnet-atlas "$BUILD/embedding-atlas.json")
fi
python3 "$REPO/labelling/export_explorer.py" --data-root "$DATA" \
  "${REPRESENTATION[@]}" --output "$BUILD/explorer.json"
python3 "$REPO/dashboard/build_explorer.py" --input "$BUILD/explorer.json" \
  --output "$BUILD/explorer.html"
