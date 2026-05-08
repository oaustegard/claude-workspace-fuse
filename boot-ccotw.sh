#!/bin/bash
# Container-layer boot for Claude Code (Web + CLI)
# Called by SessionStart hook. stdout goes into Claude's context.
#
# Ephemeral containers: restores cached layer, fetches fresh skills, boots Muninn.
# Idempotent within a session via marker file.
#
# Per-phase timings are always emitted via _tmark. Set BOOT_TELEMETRY=1 to also
# enable the python-side boot() telemetry in post-boot.sh.

# Mirror all output to a file so the model can read the full boot
# when Claude Code's ~2KB SessionStart preview truncates this stream.
exec > >(tee /tmp/muninn-boot-full.md) 2>&1
echo "⚠️ SessionStart output truncates to ~2KB in context. Full boot at /tmp/muninn-boot-full.md — Read before responding."
echo ""

set -e

MARKER="/tmp/.container-layer-booted"
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"
CONTAINERFILE="$(cd "$PROJECT_DIR" && pwd)/Containerfile"
SKILLS_DIR="/mnt/skills/user"

# ── Clock ──
# _BOOT_T0  = epoch ms at boot start (for cumulative TOTAL)
# _LAST_MARK = epoch ms at last _tmark (for per-phase deltas)
_BOOT_T0=$(date +%s%3N)
_LAST_MARK=$_BOOT_T0

_tmark() {
    local now=$(date +%s%3N)
    local elapsed=$((now - _LAST_MARK))
    echo "⏱ bash:$1 ${elapsed}ms"
    _LAST_MARK=$now
}

_ttotal() {
    echo "⏱ bash:TOTAL $(($(date +%s%3N) - _BOOT_T0))ms"
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
        # Truncate the log AND drop the rebuild-status cursor so the
        # UserPromptSubmit hook (`scripts/rebuild-status.sh`) emits this
        # run's events from byte 0 instead of inheriting an old offset.
        : > /tmp/.rebuild-layer.log
        rm -f /tmp/.rebuild-layer.log.cursor
        nohup bash "$PROJECT_DIR/rebuild-layer.sh" </dev/null >>/tmp/.rebuild-layer.log 2>&1 &
        # No model-side action needed: the UserPromptSubmit hook flushes
        # new log lines into the next user prompt's context, so START /
        # RESTORE / DONE / FAIL events surface naturally without the
        # model having to arm Monitor.
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

_run_smoke_test_background() {
    # Fire smoke_test.py in the background after the container layer is
    # restored and skills are fetched. Failures land in /tmp/.smoke-failures
    # and are surfaced to the next user prompt by scripts/smoke-status.sh.
    # Skipped if the script or flowing skill is missing — those failures will
    # show up at session start in other ways.
    local smoke="$PROJECT_DIR/scripts/smoke_test.py"
    [ -f "$smoke" ] || return 0
    [ -f "$SKILLS_DIR/flowing/scripts/flowing.py" ] || return 0
    nohup python3 "$smoke" </dev/null >/tmp/.smoke-test.log 2>&1 &
}

_output_skills() {
    # Emit names only — full descriptions live on disk at
    # $skill/SKILL.md and are loaded on demand via the finding-skills
    # meta-skill. This keeps the skills block under ~1.5KB instead of
    # the ~35KB that a descriptions dump would cost every session, which
    # is important because Claude Code's SessionStart hook truncates
    # stdout to a ~2KB preview.
    [ -d "$SKILLS_DIR" ] || return 0
    echo ""
    echo "<available_skills source=\"$SKILLS_DIR\">"
    for skill_dir in "$SKILLS_DIR"/*/; do
        local skill_file="${skill_dir}SKILL.md"
        if [ -f "$skill_file" ]; then
            local name=$(grep -m1 "^name:" "$skill_file" | sed 's/name: *//')
            [ -n "$name" ] && echo "<skill>$name</skill>"
        fi
    done
    echo "</available_skills>"
    echo "Use finding-skills to search descriptions or load a specific SKILL.md:"
    echo "  python3 $SKILLS_DIR/finding-skills/scripts/skills.py search <query>"
    echo "  python3 $SKILLS_DIR/finding-skills/scripts/skills.py show <name>"
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
    _tmark "drift_check"
    # Skills are always fetched fresh — never rely on stale copies from a previous boot
    _wait_for_network
    _tmark "network_wait"
    _fetch_skills
    _tmark "skills_fetch"
    _setup_python_paths
    _tmark "python_paths"
    _output_skills
    _tmark "skills_list"
    _run_smoke_test_background
    # Still run post-boot hook — identity must load every session, not just first boot
    [ -f "$PROJECT_DIR/post-boot.sh" ] && bash "$PROJECT_DIR/post-boot.sh" 2>&1
    _tmark "post_boot"
    _ttotal
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
_tmark "skills_fetch"
_setup_python_paths
_tmark "python_paths"

touch "$MARKER"
_output_skills
_tmark "skills_list"
_run_smoke_test_background

# Custom post-boot hook
[ -f "$PROJECT_DIR/post-boot.sh" ] && bash "$PROJECT_DIR/post-boot.sh" 2>&1
_tmark "post_boot"
_ttotal

exit 0
