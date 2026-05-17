#!/usr/bin/env bash
# Install PySR + Julia toolchain on demand.
# Idempotent — re-running is cheap when already installed.
# Cost: ~5 minutes on a cold container (Julia 1.10 + SymbolicRegression.jl
# precompile). The Julia toolchain alone is ~1GB once precompiled.
#
# Invoke when the session involves symbolic regression (eml-sr spoke,
# PySR runs, SymbolicRegression.jl), anything importing pysr.
#
# Note: Julia 1.11 segfaults on SymbolicRegression.jl precompile under
# gVisor (kernel 4.4.0 / runsc); this pins to Julia 1.10 which works.

set -e

if python3 -c "import pysr" 2>/dev/null; then
    echo "✓ pysr already installed: $(python3 -c 'import pysr; print(pysr.__version__)')"
    exit 0
fi

t0=$(date +%s)
echo "Installing PySR + Julia 1.10 + SymbolicRegression.jl (~5 min)..."

uv pip install --system --break-system-packages pysr
python3 -c "import juliapkg; juliapkg.require_julia('~1.10'); juliapkg.resolve(force=True)"
python3 -c "import pysr"  # triggers SymbolicRegression.jl precompile

t1=$(date +%s)
echo "✓ pysr installed in $((t1 - t0))s: $(python3 -c 'import pysr; print(pysr.__version__)')"
