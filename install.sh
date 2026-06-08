#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

"$PYTHON_BIN" -m pip install --user -r "$ROOT/requirements.txt"
bash "$ROOT/scripts/install_skill.sh"
mkdir -p "${VIDEO_NOTES_HOME:-$HOME/Documents/VideoNotes}"

if [[ "$(uname -s)" == "Darwin" ]]; then
  bash "$ROOT/service/install_launch_agent.sh"
else
  echo "Start the capture service with: bash $ROOT/service/start_service.sh"
fi

bash "$ROOT/scripts/package_extension.sh"

echo
echo "Installation complete."
echo "Next: open chrome://extensions, enable Developer mode, and load:"
echo "$ROOT/chrome-extension"
