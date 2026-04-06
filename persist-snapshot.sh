#!/bin/bash
# SessionEnd hook: persist container snapshot if Containerfile changed during session
set -e

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"
CONTAINERFILE="$(cd "$PROJECT_DIR" && pwd)/Containerfile"
SKILL_DIR="/tmp/_container_layer"
HASH_FILE="/tmp/.containerfile-hash"

[ -f "$CONTAINERFILE" ] || exit 0
[ -f "$SKILL_DIR/scripts/containerfile.py" ] || exit 0
[ -n "${GH_TOKEN:-}" ] || exit 0

# Compare current hash to boot-time hash
current_hash=$(cd "$SKILL_DIR" && python3 -m scripts.cli hash "$CONTAINERFILE" --token "${GH_TOKEN}" --repo "${LAYER_CACHE_REPO:-oaustegard/claude-container-layers}" 2>/dev/null)

if [ -f "$HASH_FILE" ] && [ "$(cat "$HASH_FILE")" = "$current_hash" ]; then
  echo "Containerfile unchanged, skipping snapshot."
  exit 0
fi

echo "Containerfile changed — rebuilding and pushing snapshot..."
cd "$SKILL_DIR"
python3 -m scripts.cli build "$CONTAINERFILE" \
  --token "${GH_TOKEN}" \
  --repo "${LAYER_CACHE_REPO:-oaustegard/claude-container-layers}" 2>&1

echo "✓ Snapshot persisted"
