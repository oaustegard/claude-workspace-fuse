# Muninn Container Layer (FUSE variant)
# Always-on base: tools every session benefits from.
# Heavy/optional deps (mojo, pytorch, pysr) are on-demand via scripts/install-*.sh.
# Skills are fetched fresh at session start, not cached here.
# cache-bust: 2026-05-17b

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

WORKDIR /home/user
