#!/usr/bin/env bash
# Restore the cached Mojo addon layer (or build + push it on first miss).
# Idempotent — returns instantly when mojo is already present.
#
# Invoke when the session involves Mojo code: fusemojo, tree-sitter-mojo,
# any .mojo file, `mojo run`, etc.

set -e

if command -v mojo >/dev/null 2>&1; then
    echo "✓ mojo already installed: $(mojo --version 2>&1 | head -1)"
    exit 0
fi

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONTAINERFILE="$REPO_ROOT/Containerfile.mojo"
SKILL_DIR="/tmp/_container_layer"

if [ ! -f "$SKILL_DIR/scripts/cli.py" ]; then
    echo "✗ container-layer skill not bootstrapped at $SKILL_DIR"
    echo "  (boot-ccotw.sh should have done this; retry after a fresh boot)"
    exit 1
fi

t0=$(date +%s)
echo "Restoring Mojo addon layer (cache hit: fast download; cache miss: ~3min build)..."

cd "$SKILL_DIR"
python3 -m scripts.cli \
    --token "${GH_TOKEN:-}" \
    --repo "${LAYER_CACHE_REPO:-oaustegard/claude-container-layers}" \
    restore "$CONTAINERFILE"

t1=$(date +%s)
echo "✓ mojo restored in $((t1 - t0))s: $(mojo --version 2>&1 | head -1)"
