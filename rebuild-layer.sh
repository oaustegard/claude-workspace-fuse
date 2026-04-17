#!/bin/bash
# Rebuild and upload the container layer cache.
# Triggered by FileChanged hook on Containerfile, or run manually.

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"
CONTAINERFILE="$(cd "$PROJECT_DIR" && pwd)/Containerfile"
SKILL_DIR="/tmp/_container_layer"
HASH_FILE="/tmp/.containerfile-hash"
LOG="/tmp/.rebuild-layer.log"

exec > "$LOG" 2>&1

for envfile in "$PROJECT_DIR"/.env "$PROJECT_DIR"/*.env /mnt/project/*.env; do
    [ -f "$envfile" ] && { set -a; . "$envfile" 2>/dev/null; set +a; } || true
done

[ -n "${GH_TOKEN:-}" ] || { echo "No GH_TOKEN — skipping rebuild"; exit 0; }
[ -f "$CONTAINERFILE" ] || { echo "No Containerfile at $CONTAINERFILE"; exit 1; }

# Bootstrap skill if not present
if [ ! -f "$SKILL_DIR/scripts/containerfile.py" ]; then
    echo "Bootstrapping container-layer skill..."
    mkdir -p "$SKILL_DIR"
    curl -sL "https://codeload.github.com/oaustegard/claude-skills/tar.gz/main" \
        | tar -xz --strip-components=2 -C "$SKILL_DIR" "claude-skills-main/container-layer/" 2>/dev/null \
        || { echo "Bootstrap failed"; exit 1; }
fi

echo "Rebuilding layer from $CONTAINERFILE..."
cd "$SKILL_DIR"
python3 -m scripts.cli \
    --token "${GH_TOKEN}" \
    --repo "${LAYER_CACHE_REPO:-oaustegard/claude-container-layers}" \
    restore "$CONTAINERFILE"

# Update hash file so subsequent triggers are no-ops until next change
python3 -m scripts.cli \
    --token "${GH_TOKEN}" \
    --repo "${LAYER_CACHE_REPO:-oaustegard/claude-container-layers}" \
    hash "$CONTAINERFILE" \
    2>/dev/null > "$HASH_FILE" || true

touch /tmp/.container-layer-booted
echo "✓ Layer rebuilt and cached"
