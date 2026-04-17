#!/bin/bash
# Container-layer boot for Claude Code (Web + CLI)
# Called by SessionStart hook. stdout goes into Claude's context.
#
# Ephemeral containers: restores cached layer, fetches fresh skills, boots Muninn.
# Idempotent within a session via marker file.
#
# Set BOOT_TELEMETRY=1 to emit per-phase timing data.

set -e

MARKER="/tmp/.container-layer-booted"
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"
CONTAINERFILE="$(cd "$PROJECT_DIR" && pwd)/Containerfile"
SKILLS_DIR="/mnt/skills/user"

# ── Telemetry ──

_BOOT_T0=""
if [ "${BOOT_TELEMETRY:-0}" = "1" ]; then
    _BOOT_T0=$(date +%s%3N)
fi

_tmark() {
    [ -n "$_BOOT_T0" ] && echo "⏱ bash:$1 $(($(date +%s%3N) - _BOOT_T0))ms"
}

# ── Functions ──

_detect_containerfile_drift() {
    local skill_dir="/tmp/_container_layer"
    [ -f "$CONTAINERFILE" ] || return 0
    [ -f "/tmp/.containerfile-hash" ] || return 0
    [ -f "$skill_dir/scripts/cli.py" ] || return 0
    local current cached
    current=$(cd "$skill_dir" && python3 -m scripts.cli hash "$CONTAINERFILE" 2>/dev/null)
    cached=$(cat /tmp/.containerfile-hash)
    if [ -n "$current" ] && [ "$current" != "$cached" ]; then
        echo "  ⚠ Containerfile drift detected — rebuilding layer in background"
        nohup bash "$PROJECT_DIR/rebuild-layer.sh" >/dev/null 2>&1 &
    fi
}

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

_fetch_skills() {
    # Fetch skills fresh from GitHub (not cached in container layer)
    local max_retries=3
    local attempt
    for attempt in $(seq 1 $max_retries); do
        if curl -sL "https://codeload.github.com/oaustegard/claude-skills/tar.gz/main" -o /tmp/skills.tar.gz 2>/dev/null && \
           tar -xzf /tmp/skills.tar.gz -C /tmp && \
           mkdir -p "$SKILLS_DIR" 2>/dev/null && \
           cp -r /tmp/claude-skills-main/* "$SKILLS_DIR/"; then
            rm -f /tmp/skills.tar.gz
            rm -rf /tmp/claude-skills-main
            echo "  ✓ Skills installed"
            return 0
        fi
        [ "$attempt" -lt "$max_retries" ] && sleep 1
    done
    echo "  ✗ Skills fetch failed after $max_retries attempts"
    return 1
}

_setup_python_paths() {
    # Set up .pth file for remembering skill imports
    local pth_dir
    pth_dir=$(python3 -c "import sysconfig; print(sysconfig.get_path('purelib'))" 2>/dev/null || echo "/usr/local/lib/python3.11/dist-packages")
    local pth_file="$pth_dir/muninn-remembering.pth"
    echo "$SKILLS_DIR/remembering" > "$pth_file"
    echo "$(python3 -c 'import os; print(os.path.expanduser("~"))')" >> "$pth_file"
}

_output_skills() {
    [ -d "$SKILLS_DIR" ] || return 0
    echo ""
    echo "<available_skills source=\"$SKILLS_DIR\">"
    for skill_dir in "$SKILLS_DIR"/*/; do
        local skill_file="${skill_dir}SKILL.md"
        if [ -f "$skill_file" ]; then
            local name=$(grep -m1 "^name:" "$skill_file" | sed 's/name: *//')
            local desc=$(grep -m1 "^description:" "$skill_file" | sed 's/description: *//')
            [ -n "$name" ] && echo "<skill><n>$name</n><description>$desc</description><location>${skill_file}</location></skill>"
        fi
    done
    echo "</available_skills>"
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
    _source_env
    _tmark "env_source"
    _detect_containerfile_drift
    # Skills are always fetched fresh — never rely on stale copies from a previous boot
    _wait_for_network
    _fetch_skills
    _setup_python_paths
    _tmark "skills_fetch"
    _output_skills
    # Still run post-boot hook — identity must load every session, not just first boot
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

# Apply the Containerfile (system packages, tools — no skills)
if [ -f "$CONTAINERFILE" ] && [ -f "$SKILL_DIR/scripts/containerfile.py" ]; then
    echo "Applying container layer: $CONTAINERFILE"

    cd "$SKILL_DIR"
    python3 -m scripts.cli \
        --token "${GH_TOKEN:-}" \
        --repo "${LAYER_CACHE_REPO:-oaustegard/claude-container-layers}" \
        restore "$CONTAINERFILE" 2>&1
    # Record Containerfile hash at boot for change detection on session end
    python3 -m scripts.cli \
        --token "${GH_TOKEN:-}" \
        --repo "${LAYER_CACHE_REPO:-oaustegard/claude-container-layers}" \
        hash "$CONTAINERFILE" \
        2>/dev/null > /tmp/.containerfile-hash || true
    cd - > /dev/null

    echo "✓ Container layer applied"
else
    echo "No Containerfile found at $CONTAINERFILE — skipping."
fi
_tmark "container_layer"

# Fetch skills fresh (always, not from container cache)
echo "Fetching skills..."
_fetch_skills
_setup_python_paths
_tmark "skills_fetch"

touch "$MARKER"
_output_skills
_tmark "skills_list"

# Custom post-boot hook
[ -f "$PROJECT_DIR/post-boot.sh" ] && bash "$PROJECT_DIR/post-boot.sh" 2>&1
_tmark "post_boot"

exit 0
