#!/bin/bash
# Container-layer boot for Claude Code (Web + CLI)
# Called by SessionStart hook. stdout goes into Claude's context.
#
# Ephemeral containers: bootstraps skill, restores cached layer or builds fresh.
# Idempotent within a session via marker file.
#
# Set BOOT_TELEMETRY=1 to emit per-phase timing data.

set -e

MARKER="/tmp/.container-layer-booted"
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"
CONTAINERFILE="$(cd "$PROJECT_DIR" && pwd)/Containerfile"

# ── Telemetry ──

_BOOT_T0=""
if [ "${BOOT_TELEMETRY:-0}" = "1" ]; then
    _BOOT_T0=$(date +%s%3N)
fi

_tmark() {
    [ -n "$_BOOT_T0" ] && echo "⏱ bash:$1 $(($(date +%s%3N) - _BOOT_T0))ms"
}

# ── Functions ──

_wait_for_network() {
    local max_attempts=5
    local delay=2
    for i in $(seq 1 $max_attempts); do
        if curl -sf --max-time 5 -o /dev/null "https://github.com"; then
            return 0
        fi
        echo "  Waiting for network (attempt $i/$max_attempts)..."
        sleep "$delay"
        delay=$((delay * 2))
    done
    echo "  ✗ Network not available after $max_attempts attempts"
    return 1
}

_output_skills() {
    local skills_dir="${1:-/mnt/skills/user}"
    [ -d "$skills_dir" ] || return 0
    echo ""
    echo "Available skills:"
    for skill_dir in "$skills_dir"/*/; do
        local skill_file="${skill_dir}SKILL.md"
        if [ -f "$skill_file" ]; then
            local name=$(grep -m1 "^name:" "$skill_file" | sed 's/name: *//')
            [ -n "$name" ] && echo "  - $name"
        fi
    done
}

_source_env() {
    # Source from project dir
    for envfile in "$PROJECT_DIR"/*.env "$PROJECT_DIR"/.env; do
        [ -f "$envfile" ] && { set -a; . "$envfile" 2>/dev/null; set +a; } || true
    done
    # Also check Claude.ai project files
    for envfile in /mnt/project/*.env; do
        [ -f "$envfile" ] && { set -a; . "$envfile" 2>/dev/null; set +a; } || true
    done
}

# ── Idempotency ──
if [ -f "$MARKER" ]; then
    echo "Environment ready (cached)."
    _output_skills
    # Still run post-boot hook — identity must load every session, not just first boot
    _source_env
    _tmark "env_source"
    [ -f "$PROJECT_DIR/post-boot.sh" ] && bash "$PROJECT_DIR/post-boot.sh" 2>&1
    _tmark "post_boot"
    exit 0
fi

# ── Main ──
_source_env
_tmark "env_source"

# Wait for network before doing anything that hits the internet
_wait_for_network
_tmark "network_wait"

# Bootstrap the container-layer skill from GitHub
SKILL_DIR="/tmp/_container_layer"
if [ ! -f "$SKILL_DIR/scripts/containerfile.py" ]; then
    echo "Bootstrapping container-layer..."
    mkdir -p "$SKILL_DIR"
    if curl -sL "https://codeload.github.com/oaustegard/claude-skills/tar.gz/main" \
        | tar -xz --strip-components=2 -C "$SKILL_DIR" "claude-skills-main/container-layer/" 2>/dev/null; then
        echo "  ✓ container-layer skill loaded"
    else
        echo "  ✗ bootstrap failed (check network/token)"
        exit 1
    fi
fi
_tmark "bootstrap"

# Apply the Containerfile
if [ -f "$CONTAINERFILE" ] && [ -f "$SKILL_DIR/scripts/containerfile.py" ]; then
    echo "Applying container layer: $CONTAINERFILE"

    INVALIDATE_ARGS=""
    if [ -n "$INVALIDATE_ON" ]; then
        for repo in $INVALIDATE_ON; do
            INVALIDATE_ARGS="$INVALIDATE_ARGS --invalidate-on $repo"
        done
    fi

    cd "$SKILL_DIR"
    python3 -m scripts.cli \
        --token "${GH_TOKEN:-}" \
        --repo "${LAYER_CACHE_REPO:-oaustegard/claude-container-layers}" \
        $INVALIDATE_ARGS \
        restore "$CONTAINERFILE" 2>&1
    # Record Containerfile hash at boot for change detection on session end
    python3 -m scripts.cli hash "$CONTAINERFILE" \
        --token "${GH_TOKEN:-}" \
        --repo "${LAYER_CACHE_REPO:-oaustegard/claude-container-layers}" \
        2>/dev/null > /tmp/.containerfile-hash || true
    cd - > /dev/null

    echo "✓ Container layer applied"
else
    echo "No Containerfile found at $CONTAINERFILE — skipping."
fi
_tmark "container_layer"

touch "$MARKER"
_output_skills
_tmark "skills_list"

# Custom post-boot hook
[ -f "$PROJECT_DIR/post-boot.sh" ] && bash "$PROJECT_DIR/post-boot.sh" 2>&1
_tmark "post_boot"

exit 0
