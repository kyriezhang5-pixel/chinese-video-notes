#!/usr/bin/env bash
set -euo pipefail

LABEL="io.github.kyriezhang5-pixel.chinese-video-notes"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true
rm -f "$PLIST"
echo "Uninstalled $LABEL"
