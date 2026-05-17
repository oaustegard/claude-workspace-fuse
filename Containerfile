# Muninn Container Layer (FUSE variant)
# Always-on base: tools every session benefits from.
# Heavy/optional deps (mojo, pytorch, pysr) are on-demand via scripts/install-*.sh.
# Skills are fetched fresh at session start, not cached here.
# cache-bust: 2026-05-17d

# Purge heavy deps that may be present from a prior cached layer.
# The container-layer skill snapshots /usr/local/lib/python3.11/dist-packages
# and /usr/local/bin by *final state*, not by RUN-command output — so a build
# happening in a container that already has torch/mojo/pysr installed will
# include them in the snapshot even when this Containerfile doesn't install
# them. Explicit removal is the only way to ensure the slim layer is truly slim.
# Addons live in their own cached layers (Containerfile.{mojo,pytorch,pysr}).
RUN uv pip uninstall --system --break-system-packages -y \
    torch torchvision torchaudio \
    pysr juliapkg \
    modular mojo max mojo-compiler mojo-lldb-libs \
    2>/dev/null || true
RUN rm -rf /root/.julia /usr/local/bin/mojo /usr/local/bin/mojo-lldb /usr/local/bin/mojo-lsp-server

# Always-on Python deps
RUN uv pip install --system --break-system-packages httpx libsql-experimental

# Scientific Python core — scipy/sklearn/pandas together pull ~55MB of wheels
# and transitive deps; baking them in avoids re-downloading every session.
# Used by enough skills (charting, exploring-data, forecasting, etc.) to
# justify the always-on cost.
RUN uv pip install --system --break-system-packages scipy scikit-learn pandas

# tree-sitter for codebase-exploration skills (exploring-codebases,
# tree-sitting, mapping-codebases).  Pin <1.6.3 — the 1.6.3 wheel ships
# only _native/, missing the python module (ModuleNotFoundError on import).
RUN uv pip install --system --break-system-packages 'tree-sitter-language-pack<1.6.3'

# Pre-fetch the tree-sitter grammar cache (issue #11). The package's native
# Rust downloader uses rustls with its own root store, which doesn't trust
# the Anthropic sandbox-egress TLS-inspection CA — so first-use get_language()
# fails at runtime with "invalid peer certificate: UnknownIssuer". curl
# trusts the system CA bundle (which does include the interception CA), so
# we fetch the platform tarball directly and extract into the expected cache
# layout. download_all() can't be used because it hits the same TLS path
# that fails at runtime.
RUN apt-get update && apt-get install -y --no-install-recommends zstd && rm -rf /var/lib/apt/lists/*
RUN TSLP_VER=$(python3 -c "import tree_sitter_language_pack as t; print(t.cache_dir().rstrip('/').rsplit('/',2)[-2])") \
    && TSLP_CACHE="/root/.cache/tree-sitter-language-pack/${TSLP_VER}" \
    && mkdir -p "${TSLP_CACHE}/libs" \
    && curl -fsSL "https://github.com/kreuzberg-dev/tree-sitter-language-pack/releases/download/${TSLP_VER}/parsers.json" -o "${TSLP_CACHE}/parsers.json" \
    && curl -fsSL "https://github.com/kreuzberg-dev/tree-sitter-language-pack/releases/download/${TSLP_VER}/parsers-linux-x86_64.tar.zst" -o /tmp/parsers.tar.zst \
    && tar --use-compress-program=unzstd -xf /tmp/parsers.tar.zst -C "${TSLP_CACHE}/libs" \
    && rm /tmp/parsers.tar.zst \
    && python3 -c "from tree_sitter_language_pack import get_language; assert get_language('python'), 'cache verification failed'; print('tree-sitter cache verified')"

# FUSE userspace (libfuse2 + fusermount) is already in the base container
# image — we only need the fusepy Python bindings. Don't `apt-get install
# libfuse2 fuse` here: it's a no-op (already installed) but triggers the
# container-layer skill to snapshot all of /usr/lib, /usr/bin, /usr/share
# (~3GB raw, ~600MB compressed) into the cached tarball.
RUN uv pip install --system --break-system-packages fusepy

# GitHub CLI — direct binary (not in default apt repos).
# Authenticated API call so the shared container IP doesn't get rate-limited.
RUN GH_VER=$(curl -sL -H "Authorization: token ${GH_TOKEN}" https://api.github.com/repos/cli/cli/releases/latest | python3 -c "import sys,json; print(json.load(sys.stdin)['tag_name'].lstrip('v'))") && curl -fsSL "https://github.com/cli/cli/releases/download/v${GH_VER}/gh_${GH_VER}_linux_amd64.tar.gz" | tar -xz --strip-components=2 -C /usr/local/bin "gh_${GH_VER}_linux_amd64/bin/gh"

# Noop setup script to suppress "No setup script configured" message
RUN touch /home/user/setup.sh && chmod +x /home/user/setup.sh

# Auto-source /mnt/project/*.env into every bash subprocess so credentials
# (GH_TOKEN, TURSO_*, MUNINN_BSKY_*) survive across bash_tool invocations
# without per-call `set -a; . /mnt/project/*.env; set +a` boilerplate.
# See: oaustegard/claude-workspace#80.
# Profile fragment is sourced by login shells via /etc/profile and by
# non-interactive `bash -c` subshells via BASH_ENV (set in /etc/environment).
RUN printf '%s\n' '# Auto-source project credentials (claude-workspace#80)' 'if [ -d /mnt/project ]; then' '    set -a' '    for f in /mnt/project/*.env; do' '        [ -r "$f" ] && . "$f"' '    done' '    set +a' 'fi' > /etc/profile.d/muninn-env.sh && chmod 0644 /etc/profile.d/muninn-env.sh
RUN grep -q '^BASH_ENV=' /etc/environment 2>/dev/null || echo 'BASH_ENV=/etc/profile.d/muninn-env.sh' >> /etc/environment

# Snapshot — only system packages and tools (no mojo/pysr/julia binaries now)
SNAPSHOT /usr/local/lib/python3.11/dist-packages
SNAPSHOT /home/user/setup.sh
SNAPSHOT /usr/local/bin/gh
SNAPSHOT /etc/profile.d/muninn-env.sh
SNAPSHOT /etc/environment
SNAPSHOT /root/.cache/tree-sitter-language-pack

WORKDIR /home/user
