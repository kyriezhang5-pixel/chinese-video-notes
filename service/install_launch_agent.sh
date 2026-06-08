#!/usr/bin/env bash
set -euo pipefail

LABEL="io.github.kyriezhang5-pixel.chinese-video-notes"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
SERVICE_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3)}"
APP_SUPPORT="$HOME/Library/Application Support/ChineseVideoNotes"
APP_SERVICE="$APP_SUPPORT/service"
NOTES_HOME="${VIDEO_NOTES_HOME:-$APP_SUPPORT/VideoNotes}"

mkdir -p "$HOME/Library/LaunchAgents"
mkdir -p "$APP_SERVICE"
mkdir -p "$HOME/Documents/VideoNotes"
cp "$SERVICE_DIR/video_notes_service.py" "$APP_SERVICE/video_notes_service.py"

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PYTHON_BIN</string>
    <string>$APP_SERVICE/video_notes_service.py</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>VIDEO_NOTES_HOME</key>
    <string>$NOTES_HOME</string>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>/tmp/chinese-video-notes.out.log</string>
  <key>StandardErrorPath</key>
  <string>/tmp/chinese-video-notes.err.log</string>
</dict>
</plist>
EOF

launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "Installed and started $LABEL"
