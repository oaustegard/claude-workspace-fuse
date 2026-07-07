#!/bin/bash
# scripts/install-base-deps.sh
#
# SPIKE (2026-07-07): install the LIGHT always-on deps natively from
# allowlisted registries (PyPI + apt), replacing the `base` and `fuse`
# GitHub-Releases layers for those deps. See docs/spike-native-base-deps.md.
#
# WHY: the container-layer path restores tarballs from GitHub Releases
# (oaustegard/claude-container-layers) — the SAME codeload/GitHub-scope
# surface that cold-start-degrades (403 until the first-turn `add_repo`).
# PyPI (pypi.org, files.pythonhosted.org) and the Ubuntu apt repos are in
# the CCotw **Trusted** network allowlist and are NOT GitHub-proxy-scoped,
# so this path survives a cold start that the base/fuse layers cannot.
#
# The heavy modular layers (scientific, torch-cpu, mojo, julia-sr) stay on
# the layer system — tarball restore genuinely wins there (per-layer cache
# keys, the 5-min setup-script budget, ~1GB Julia precompile). This only
# carves out the light slice where the GitHub coupling buys nothing.
#
# IDEMPOTENT: every step short-circuits when already satisfied, so on a
# warm/cached environment (deps already on disk) this is a fast no-op.

set -u

_pip() {
    if command -v uv >/dev/null 2>&1; then
        uv pip install --system --break-system-packages "$@"
    else
        pip install --break-system-packages "$@"
    fi
}

# ── Python deps (PyPI — allowlisted, not GitHub-scoped) ──
#   httpx + libsql-experimental : Turso client for the remembering skill
#   fusepy                      : FUSE bindings for the /mnt/muninn mount
_need_py=""
python3 -c "import httpx"              2>/dev/null || _need_py="$_need_py httpx"
python3 -c "import libsql_experimental" 2>/dev/null || _need_py="$_need_py libsql-experimental"
python3 -c "import fuse"               2>/dev/null || _need_py="$_need_py fusepy"
if [ -n "$_need_py" ]; then
    echo "  base-deps: installing$_need_py (PyPI)"
    # shellcheck disable=SC2086
    _pip $_need_py >/dev/null 2>&1 \
        && echo "  ✓ base-deps: python deps installed" \
        || echo "  ✗ base-deps: pip install failed ($_need_py)"
else
    echo "  ✓ base-deps: python deps already present"
fi

# ── libfuse runtime (apt — allowlisted) ──
# fusepy is only bindings; the mount also needs libfuse.so.2 + fusermount.
# Usually in the base image, but not guaranteed on a cold fuse cache.
if ! ldconfig -p 2>/dev/null | grep -q 'libfuse.so.2' || ! command -v fusermount >/dev/null 2>&1; then
    echo "  base-deps: installing libfuse2 + fuse (apt)"
    (apt-get update >/dev/null 2>&1; apt-get install -y libfuse2 fuse >/dev/null 2>&1) \
        && echo "  ✓ base-deps: libfuse2 + fusermount installed" \
        || echo "  ✗ base-deps: apt install of libfuse2/fuse failed"
fi

# ── env-source shim (filesystem — no network at all) ──
# Auto-source /mnt/project/*.env into bash subprocesses (claude-workspace#80).
if [ ! -f /etc/profile.d/muninn-env.sh ]; then
    printf '%s\n' \
        '# Auto-source project credentials (claude-workspace#80)' \
        'if [ -d /mnt/project ]; then' \
        '    set -a' \
        '    for f in /mnt/project/*.env; do' \
        '        [ -r "$f" ] && . "$f"' \
        '    done' \
        '    set +a' \
        'fi' > /etc/profile.d/muninn-env.sh 2>/dev/null \
        && chmod 0644 /etc/profile.d/muninn-env.sh 2>/dev/null \
        && echo "  ✓ base-deps: env-source shim written"
fi
grep -q '^BASH_ENV=' /etc/environment 2>/dev/null \
    || echo 'BASH_ENV=/etc/profile.d/muninn-env.sh' >> /etc/environment 2>/dev/null

# ── gh CLI (best-effort; vestigial per CLAUDE.md — nothing calls it) ──
# CLAUDE.md: "gh CLI is not used anywhere in this repo's operational paths."
# Best-effort convenience only; never blocks boot. The GitHub-CLI apt repo
# may not be allowlisted, in which case this quietly no-ops.
if ! command -v gh >/dev/null 2>&1; then
    (apt-get install -y gh >/dev/null 2>&1) \
        && echo "  ✓ base-deps: gh installed (apt)" \
        || echo "  · base-deps: gh unavailable (vestigial — no operational path uses it)"
fi

exit 0
