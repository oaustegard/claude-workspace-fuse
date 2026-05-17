#!/usr/bin/env bash
# Restore the cached PyTorch addon layer (or build + push it on first miss).
# Idempotent — returns instantly when torch is already present.
#
# Invoke when the session involves tensors, torch.nn, model training/inference.

set -e

if python3 -c "import torch" 2>/dev/null; then
    echo "✓ torch already installed: $(python3 -c 'import torch; print(torch.__version__)')"
    exit 0
fi

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONTAINERFILE="$REPO_ROOT/layers/Containerfile.torch-cpu"
SKILL_DIR="/tmp/_container_layer"

if [ ! -f "$SKILL_DIR/scripts/cli.py" ]; then
    echo "✗ container-layer skill not bootstrapped at $SKILL_DIR"
    echo "  (boot-ccotw.sh should have done this; retry after a fresh boot)"
    exit 1
fi

# Note: torch-cpu is in the default layer composition (see
# .claude/container-layers.json), so a fresh boot normally has torch already.
# This script remains as a fallback for sessions where the layer composition
# was customized to exclude torch-cpu.
t0=$(date +%s)
echo "Restoring PyTorch addon layer (cache hit: fast download; cache miss: ~2min build)..."

cd "$SKILL_DIR"
python3 -m scripts.cli \
    --token "${GH_TOKEN:-}" \
    --repo "${LAYER_CACHE_REPO:-oaustegard/claude-container-layers}" \
    restore "$CONTAINERFILE" --name torch-cpu

t1=$(date +%s)
echo "✓ torch restored in $((t1 - t0))s: $(python3 -c 'import torch; print(torch.__version__)')"
