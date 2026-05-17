#!/usr/bin/env bash
# Install PyTorch (CPU-only) on demand.
# Idempotent — re-running is cheap when already installed.
# Cost: ~1-2 minutes on a cold container (~200MB download).
#
# Invoke when the session involves model training/inference, tensors,
# torch.nn, anything importing torch/torchvision/torchaudio.

set -e

if python3 -c "import torch" 2>/dev/null; then
    echo "✓ torch already installed: $(python3 -c 'import torch; print(torch.__version__)')"
    exit 0
fi

t0=$(date +%s)
echo "Installing PyTorch CPU-only (~200MB, 1-2 min)..."

# CPU-only build (no CUDA, ~200MB vs ~2GB for GPU build).
uv pip install --system --break-system-packages \
    torch torchvision torchaudio \
    --index-url https://download.pytorch.org/whl/cpu

t1=$(date +%s)
echo "✓ torch installed in $((t1 - t0))s: $(python3 -c 'import torch; print(torch.__version__)')"
