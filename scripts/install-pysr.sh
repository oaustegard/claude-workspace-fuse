#!/usr/bin/env bash
# Restore the cached PySR addon layer (or build + push it on first miss).
# Idempotent — returns instantly when pysr is already present.
#
# Invoke when the session involves symbolic regression: eml-sr spoke,
# PySR runs, SymbolicRegression.jl, anything importing pysr.
#
# Cache hit: ~30s (downloads ~1GB tarball including precompiled .julia).
# Cache miss: ~5min (fresh Julia 1.10 + SymbolicRegression.jl precompile).

set -e

if python3 -c "import pysr" 2>/dev/null; then
    echo "✓ pysr already installed: $(python3 -c 'import pysr; print(pysr.__version__)')"
    exit 0
fi

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONTAINERFILE="$REPO_ROOT/Containerfile.pysr"
SKILL_DIR="/tmp/_container_layer"

if [ ! -f "$SKILL_DIR/scripts/cli.py" ]; then
    echo "✗ container-layer skill not bootstrapped at $SKILL_DIR"
    echo "  (boot-ccotw.sh should have done this; retry after a fresh boot)"
    exit 1
fi

t0=$(date +%s)
echo "Restoring PySR addon layer (cache hit: ~30s for ~1GB; cache miss: ~5min)..."

cd "$SKILL_DIR"
python3 -m scripts.cli \
    --token "${GH_TOKEN:-}" \
    --repo "${LAYER_CACHE_REPO:-oaustegard/claude-container-layers}" \
    --invalidate-on oaustegard/claude-workspace-fuse \
    restore "$CONTAINERFILE"

t1=$(date +%s)
echo "✓ pysr restored in $((t1 - t0))s: $(python3 -c 'import pysr; print(pysr.__version__)')"
