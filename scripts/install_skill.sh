#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
DEST="$CODEX_HOME/skills/chinese-video-notes"

mkdir -p "$DEST"
cp "$ROOT/skill/SKILL.md" "$DEST/SKILL.md"
mkdir -p "$DEST/agents" "$DEST/scripts"
cp "$ROOT/skill/agents/openai.yaml" "$DEST/agents/openai.yaml"
cp "$ROOT"/skill/scripts/*.py "$DEST/scripts/"

echo "Installed chinese-video-notes skill to $DEST"
