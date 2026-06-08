#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="$(python3 -c 'import json, pathlib, sys; print(json.loads(pathlib.Path(sys.argv[1]).read_text())["version"])' "$ROOT/chrome-extension/manifest.json")"

OUT="$ROOT/dist/chinese-video-notes-extension-v$VERSION.zip"
rm -f "$OUT"
(
  cd "$ROOT/chrome-extension"
  zip -q -r -X "$OUT" . -x '*.DS_Store'
)
echo "$OUT"
