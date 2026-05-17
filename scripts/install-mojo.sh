#!/usr/bin/env bash
# Install the Mojo toolchain on demand.
# Idempotent — re-running is cheap when already installed (uv skips satisfied deps).
# Cost: ~2-3 minutes on a cold container (~550MB download).
#
# Invoke when the session involves Mojo code: fusemojo, tree-sitter-mojo,
# any .mojo file, "compile this Mojo", `mojo run`, etc.

set -e

if command -v mojo >/dev/null 2>&1; then
    echo "✓ mojo already installed: $(mojo --version 2>&1 | head -1)"
    exit 0
fi

t0=$(date +%s)
echo "Installing Mojo toolchain (~550MB, 2-3 min)..."

# Mojo 1.0.0b1 is a prerelease, so versions are pinned explicitly and
# --prerelease=allow is required for uv to resolve the transitive
# mojo-compiler==1.0.0b1 / mojo-lldb-libs==1.0.0b1 deps.
# --no-deps on `modular` skips `max-core` and ML extras (~350MB saved).
uv pip install --system --break-system-packages modular==26.3.0 --no-deps
uv pip install --system --break-system-packages --prerelease=allow mojo==1.0.0b1 max==26.3.0

t1=$(date +%s)
echo "✓ mojo installed in $((t1 - t0))s: $(mojo --version 2>&1 | head -1)"
