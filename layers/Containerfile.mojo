# Mojo toolchain (~550MB).
# Cached as `layer-mojo-<hash>`.
# NOT in the hub default composition — opt-in per session via
# .claude/container-layers.json (or per-spoke overlay once #25's spoke
# manifest lands).
#
# Triggers: any .mojo file, fusemojo/tree-sitter-mojo work, `mojo` CLI
# usage. The session adds 'mojo' to its container-layers.json before
# work begins.
#
# Mojo 1.0.0b1 is a prerelease, so versions are pinned explicitly and
# --prerelease=allow is required for uv to resolve the transitive
# mojo-compiler==1.0.0b1 / mojo-lldb-libs==1.0.0b1 deps.
# --no-deps on `modular` skips `max-core` and ML extras (~350MB saved).
# `mojo max` then pulls the CLI entry points + base deps (numpy, pyyaml, rich).
# cache-bust: 2026-05-17

RUN uv pip install --system --break-system-packages modular==26.3.0 --no-deps
RUN uv pip install --system --break-system-packages --prerelease=allow mojo==1.0.0b1 max==26.3.0

SNAPSHOT /usr/local/lib/python3.11/dist-packages
SNAPSHOT /usr/local/bin/mojo
SNAPSHOT /usr/local/bin/mojo-lldb
SNAPSHOT /usr/local/bin/mojo-lsp-server
