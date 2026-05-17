#!/bin/bash
# Rebuild and upload the container layer cache.
# Triggered by PostToolUse hook on Containerfile edits, or by SessionStart
# drift detection. Run manually for ad-hoc rebuilds.
#
# Emits structured one-line status events to stdout (tee'd to a log file)
# so the Monitor tool can stream progress as session notifications:
#   START containerfile=<path>
#   BOOTSTRAP                 (only if container-layer skill missing)
#   RESTORE repo=<owner/name>
#   DONE hash=<sha>
#   FAIL reason=<short-tag>
#   SKIP reason=<short-tag>

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"
PROJECT_DIR="$(cd "$PROJECT_DIR" && pwd)"
MANIFEST="$PROJECT_DIR/.claude/container-layers.json"
CONTAINERFILE="$PROJECT_DIR/Containerfile"
SKILL_DIR="/tmp/_container_layer"
HASH_FILE="/tmp/.containerfile-hash"
LOG="/tmp/.rebuild-layer.log"
LOCK="/tmp/.rebuild-layer.lock"

# Tee stdout to the log: Monitor tails the log while a persistent record
# survives for next-session diagnosis.
exec > >(tee -a "$LOG") 2>&1

_emit() { printf '%s\n' "$*"; }
_fail() { _emit "FAIL reason=$*"; trap - EXIT; exit 1; }

# Single-flight: SessionStart drift-detect and PostToolUse(Containerfile)
# can both fire on the same session boot. Without a lock, two rebuilds
# race, both append to $LOG, and tracebacks interleave character-by-character.
exec 9>"$LOCK"
if ! flock -n 9; then
    _emit "SKIP reason=already-running"
    exit 0
fi

# Catch unexpected exits (set -e tripping, segfault, killed) so silence
# never means success.
trap '[ "$?" -eq 0 ] || _emit "FAIL reason=unexpected-exit"' EXIT

# Identify trigger source for logging
if [ -f "$MANIFEST" ]; then
    _emit "START manifest=$MANIFEST"
elif [ -f "$CONTAINERFILE" ]; then
    _emit "START containerfile=$CONTAINERFILE (legacy)"
else
    _fail "no-manifest-no-containerfile"
fi

for envfile in "$PROJECT_DIR"/.env "$PROJECT_DIR"/*.env /mnt/project/*.env; do
    [ -f "$envfile" ] && { set -a; . "$envfile" 2>/dev/null; set +a; } || true
done

if [ -z "${GH_TOKEN:-}" ]; then
    _emit "SKIP reason=no-gh-token"
    trap - EXIT
    exit 0
fi

if [ ! -f "$SKILL_DIR/scripts/containerfile.py" ]; then
    _emit "BOOTSTRAP"
    mkdir -p "$SKILL_DIR"
    curl -sL "https://codeload.github.com/oaustegard/claude-skills/tar.gz/main" \
        | tar -xz --strip-components=2 -C "$SKILL_DIR" "claude-skills-main/container-layer/" 2>/dev/null \
        || _fail "bootstrap"
fi

REPO="${LAYER_CACHE_REPO:-oaustegard/claude-container-layers}"
_emit "RESTORE repo=$REPO"

# compose_layers.py handles both manifest-driven multi-layer and legacy
# single-Containerfile cases. It writes the composite hash to $HASH_FILE.
LAYER_CACHE_REPO="$REPO" python3 "$PROJECT_DIR/scripts/compose_layers.py" apply || _fail "apply"

new_hash=$(cat "$HASH_FILE" 2>/dev/null || true)

touch /tmp/.container-layer-booted
_emit "DONE hash=${new_hash:-unknown}"
trap - EXIT
