# Muninn Container Layer
# System packages and Python deps for Claude Code on the Web
# Skills are fetched fresh at session start, not cached here.
# cache-bust: 2026-04-26

# Python dependencies
RUN uv pip install --system --break-system-packages httpx libsql-experimental

# Scientific Python core — scipy/sklearn/pandas together pull ~55MB of wheels
# and transitive deps; baking them in avoids re-downloading every session.
RUN uv pip install --system --break-system-packages scipy scikit-learn pandas

# Mojo (via Modular's pypi packages — provides `mojo` CLI, ~550MB)
# --no-deps on `modular` skips `max-core` and ML extras (~350MB saved).
# `mojo max` then pulls the CLI entry points + base deps (numpy, pyyaml, rich).
RUN uv pip install --system --break-system-packages modular --no-deps
RUN uv pip install --system --break-system-packages mojo max

# PyTorch CPU-only (no CUDA, ~200MB vs ~2GB for GPU build)
RUN uv pip install --system --break-system-packages torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# tree-sitter for codebase-exploration skills (exploring-codebases, tree-sitting).
# Pin to <1.6.3 — that wheel is broken (ships only _native/, missing the
# tree_sitter_language_pack/ python module → ModuleNotFoundError on import).
# Pulls in tree-sitter as a transitive dep, so no separate install needed.
RUN uv pip install --system --break-system-packages 'tree-sitter-language-pack<1.6.3'

# PySR + Julia toolchain for symbolic-regression benchmarks (eml-sr #47).
# Julia 1.11 segfaults on SymbolicRegression.jl precompile under gVisor
# (kernel 4.4.0 / runsc); pin to Julia 1.10 which precompiles cleanly.
# Total install is ~5 min on a cold cache — absolutely belongs here.
RUN uv pip install --system --break-system-packages pysr
RUN python3 -c "import juliapkg; juliapkg.require_julia('~1.10'); juliapkg.resolve(force=True)"
RUN python3 -c "import pysr"  # triggers SymbolicRegression.jl precompile

# GitHub CLI — direct binary (not in default apt repos)
# Authenticated API call so the shared container IP doesn't get rate-limited.
RUN GH_VER=$(curl -sL -H "Authorization: token ${GH_TOKEN}" https://api.github.com/repos/cli/cli/releases/latest | python3 -c "import sys,json; print(json.load(sys.stdin)['tag_name'].lstrip('v'))") && curl -fsSL "https://github.com/cli/cli/releases/download/v${GH_VER}/gh_${GH_VER}_linux_amd64.tar.gz" | tar -xz --strip-components=2 -C /usr/local/bin "gh_${GH_VER}_linux_amd64/bin/gh"

# Noop setup script to suppress "No setup script configured" message
RUN touch /home/user/setup.sh && chmod +x /home/user/setup.sh

# Snapshot — only system packages and tools
SNAPSHOT /usr/local/lib/python3.11/dist-packages
SNAPSHOT /home/user/setup.sh
SNAPSHOT /usr/local/bin/gh
SNAPSHOT /usr/local/bin/mojo
SNAPSHOT /usr/local/bin/mojo-lldb
SNAPSHOT /usr/local/bin/mojo-lsp-server
# Julia toolchain + precompiled SymbolicRegression.jl cache (~1GB).
# Without this, every session pays the 5-minute Julia bootstrap.
SNAPSHOT /root/.julia

WORKDIR /home/user