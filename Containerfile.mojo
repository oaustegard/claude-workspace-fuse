# Mojo addon layer — restored on demand via scripts/install-mojo.sh.
# Cached separately from the base layer; cache key = content hash of this file.
#
# Mojo 1.0.0b1 is a prerelease, so versions are pinned explicitly and
# --prerelease=allow is required for uv to resolve the transitive
# mojo-compiler==1.0.0b1 / mojo-lldb-libs==1.0.0b1 deps.
# --no-deps on `modular` skips `max-core` and ML extras (~350MB saved).
# `mojo max` then pulls the CLI entry points + base deps (numpy, pyyaml, rich).

RUN uv pip install --system --break-system-packages modular==26.3.0 --no-deps
RUN uv pip install --system --break-system-packages --prerelease=allow mojo==1.0.0b1 max==26.3.0

SNAPSHOT /usr/local/lib/python3.11/dist-packages
SNAPSHOT /usr/local/bin/mojo
SNAPSHOT /usr/local/bin/mojo-lldb
SNAPSHOT /usr/local/bin/mojo-lsp-server
