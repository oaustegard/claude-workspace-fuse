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

_refresh_container_layer_skill() {
    # Re-fetch /tmp/_container_layer from claude-skills@main. /tmp survives
    # across sessions in the same container, so a checkout from when the
    # container was first provisioned would persist and miss newer skill
    # features (e.g. the `compose` subcommand added in v0.2.0). Cheap:
    # ~50KB tarball, one curl. Idempotent.
    local skill_dir="/tmp/_container_layer"
    rm -rf "$skill_dir"
    mkdir -p "$skill_dir"
    curl -sL "https://codeload.github.com/oaustegard/claude-skills/tar.gz/main" \
        | tar -xz --strip-components=2 -C "$skill_dir" "claude-skills-main/container-layer/" 2>/dev/null
}

_detect_containerfile_drift() {
    local skill_dir="/tmp/_container_layer"
    [ -f "/tmp/.containerfile-hash" ] || return 0
    _refresh_container_layer_skill
    [ -f "$skill_dir/scripts/cli.py" ] || return 0
    # Manifest-driven OR legacy Containerfile — compose_layers.py handles both
    [ -f "$PROJECT_DIR/.claude/container-layers.json" ] || [ -f "$CONTAINERFILE" ] || return 0
    local current cached
    current=$(cd "$PROJECT_DIR" && python3 scripts/compose_layers.py hash 2>/dev/null)
    cached=$(cat /tmp/.containerfile-hash)
    if [ -n "$current" ] && [ "$current" != "$cached" ]; then
        echo "  ⚠ Container layer drift detected — rebuilding in background"
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

_fetch_muninn_utilities() {
    # Pull canonical muninn-utilities — installs `remembering/` to
    # $SKILLS_DIR/remembering/ (overriding the deprecated mirror that
    # claude-skills still ships) and `muninn_utils/*.py` to ~/muninn_utils/.
    #
    # Must run AFTER _fetch_skills so the muninn-utilities copy wins over the
    # claude-skills mirror. Must run BEFORE post-boot.sh so boot() loads from
    # the canonical source.
    #
    # The repo is public, so no GH_TOKEN required.
    local repo="${MUNINN_UTILITIES_REPO:-oaustegard/muninn-utilities}"
    local branch="${MUNINN_UTILITIES_BRANCH:-main}"
    local home_dir
    home_dir=$(python3 -c 'import os; print(os.path.expanduser("~"))')
    local util_dir="${MUNINN_UTIL_DIR:-$home_dir/muninn_utils}"
    local stage="/tmp/.muninn-utilities-stage"

    rm -rf "$stage" && mkdir -p "$stage"
    if ! curl -sfL "https://codeload.github.com/$repo/tar.gz/$branch" -o "$stage/repo.tar.gz" 2>/dev/null; then
        echo "  ✗ muninn-utilities fetch failed (network)"
        rm -rf "$stage"
        return 0
    fi
    if ! tar -xzf "$stage/repo.tar.gz" -C "$stage" 2>/dev/null; then
        echo "  ✗ muninn-utilities extract failed"
        rm -rf "$stage"
        return 0
    fi
    local src
    src=$(find "$stage" -maxdepth 1 -type d -name 'muninn-utilities-*' | head -1)
    if [ -z "$src" ]; then
        echo "  ✗ muninn-utilities top-dir missing in tarball"
        rm -rf "$stage"
        return 0
    fi

    # remembering/ → $SKILLS_DIR/remembering/  (overrides claude-skills mirror)
    if [ -d "$src/remembering" ] && [ -d "$SKILLS_DIR" ]; then
        rm -rf "$SKILLS_DIR/remembering"
        cp -r "$src/remembering" "$SKILLS_DIR/remembering"
        echo "  ✓ remembering installed from muninn-utilities"
    fi

    # muninn_utils/*.py → ~/muninn_utils/  (skip tests/ subdir)
    if [ -d "$src/muninn_utils" ]; then
        mkdir -p "$util_dir"
        local count=0
        for f in "$src/muninn_utils"/*.py; do
            [ -f "$f" ] || continue
            cp "$f" "$util_dir/" && count=$((count + 1))
        done
        [ -f "$util_dir/__init__.py" ] || touch "$util_dir/__init__.py"
        echo "  ✓ muninn_utils installed from muninn-utilities ($count files)"
    fi

    rm -rf "$stage"
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
    #
    # Names are deduped: two directories occasionally declare the same
    # `name:` (e.g. `building-github-index/` and `building-github-index-v2/`
    # both shipped from claude-skills with `name: building-github-index`).
    # The structural fix lives upstream, but emitting duplicates pollutes
    # the boot signal regardless of cause.
    [ -d "$SKILLS_DIR" ] || return 0
    echo ""
    local names
    names=$(
        for skill_dir in "$SKILLS_DIR"/*/; do
            local skill_file="${skill_dir}SKILL.md"
            if [ -f "$skill_file" ]; then
                local name=$(grep -m1 "^name:" "$skill_file" | sed 's/name: *//')
                [ -n "$name" ] && echo "$name"
            fi
        done | sort -u | paste -sd ',' -
    )
    echo "<available_skills source=\"$SKILLS_DIR\">$names</available_skills>"
    echo "Use finding-skills to search descriptions or load a specific SKILL.md:"
    echo "  python3 $SKILLS_DIR/finding-skills/scripts/skills.py search <query>"
    echo "  python3 $SKILLS_DIR/finding-skills/scripts/skills.py show <name>"
}

_link_slash_skills() {
    # Make a curated set of /mnt/skills/user/* skills invocable via the
    # harness's `Skill` tool (and as `/<name>` slash commands). The
    # registry only scans ~/.claude/skills/<name>/SKILL.md — sideloaded
    # skills are otherwise unreachable except by direct `python3` invoke.
    #
    # Curated, not blanket: each registered skill's frontmatter description
    # gets concatenated into the skill list every turn. Symlinking 80+
    # skills would burn meaningful context every prompt; the long tail
    # stays discoverable via finding-skills.
    #
    # Effect lags one session: SessionStart fires AFTER the harness has
    # already built its registry. Symlinks created here take effect next
    # session. Acceptable.
    local home_dir
    home_dir=$(python3 -c 'import os; print(os.path.expanduser("~"))')
    local target_dir="$home_dir/.claude/skills"
    [ -d "$SKILLS_DIR" ] || return 0
    mkdir -p "$target_dir" 2>/dev/null || return 0
    local slash_skills=(
        composing-html
        flowing
        browsing-bluesky
        charting
        iterating
        json-render-ui
        creating-skill
        exploring-codebases
        tree-sitting
        uploading-files
        finding-skills
        remembering
    )
    local linked=0
    local s
    for s in "${slash_skills[@]}"; do
        if [ -d "$SKILLS_DIR/$s" ] && [ -f "$SKILLS_DIR/$s/SKILL.md" ]; then
            ln -sfn "$SKILLS_DIR/$s" "$target_dir/$s" 2>/dev/null && linked=$((linked + 1))
        fi
    done
    echo "  ✓ Linked $linked slash skills into $target_dir"
}

_verify_fuse_deps() {
    # FUSE Python bindings now ship in `layers/Containerfile.fuse` (cached as
    # `layer-fuse-<hash>`). libfuse2 + fusermount have always been in the base
    # container image. This function is a verification-only fallback: it warns
    # if the fuse layer hasn't warmed up yet for this session so memfs failures
    # have a clear pointer rather than mysterious ImportError tracebacks.
    local missing=0
    command -v fusermount >/dev/null 2>&1 || missing=1
    python3 -c "import fuse" 2>/dev/null || missing=1
    [ "$missing" -eq 0 ] && return 0
    echo "  ! FUSE deps missing — fuse layer cache may not have warmed yet."
    echo "    Memfs mount will likely fail; re-run boot or rebuild layer cache."
}

_start_memfs_background() {
    # Mount the Muninn memory FUSE filesystem at /mnt/muninn — read-only
    # projection of the active Turso memories. Bootstrap pull runs inside
    # the FUSE process (~700ms) and is hidden behind CCotw's own startup
    # dead time. Idempotent: skipped if already mounted in this container.
    local mount_point="/mnt/muninn"
    if mountpoint -q "$mount_point" 2>/dev/null; then
        echo "  ✓ memfs already mounted at $mount_point"
        return 0
    fi
    local script="$PROJECT_DIR/scripts/muninn_memfs.py"
    [ -f "$script" ] || { echo "  ✗ memfs script missing: $script"; return 0; }
    mkdir -p "$mount_point"
    nohup python3 "$script" "$mount_point" </dev/null >/tmp/.muninn-memfs.log 2>&1 &
    echo "  ✓ memfs mount kicked off (pid $!, log /tmp/.muninn-memfs.log)"
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
    # muninn-utilities overlays remembering/ + installs muninn_utils/ before boot
    _fetch_muninn_utilities
    _tmark "muninn_utilities"
    _setup_python_paths
    _tmark "python_paths"
    _verify_fuse_deps
    _tmark "fuse_deps"
    _start_memfs_background
    _tmark "memfs_start"
    _link_slash_skills
    _tmark "slash_skills"
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

SKILL_DIR="/tmp/_container_layer"
echo "Fetching container-layer skill..."
_refresh_container_layer_skill
if [ -f "$SKILL_DIR/scripts/containerfile.py" ]; then
    echo "  ✓ container-layer skill loaded"
else
    echo "  ✗ bootstrap failed (check network/token)"
    exit 1
fi
_tmark "bootstrap"

# Apply composable container layers per .claude/container-layers.json
# (or fall back to legacy single Containerfile if no manifest exists yet).
if [ -f "$SKILL_DIR/scripts/containerfile.py" ]; then
    if [ -f "$PROJECT_DIR/.claude/container-layers.json" ] || [ -f "$CONTAINERFILE" ]; then
        echo "Applying container layers..."
        (cd "$PROJECT_DIR" && python3 scripts/compose_layers.py apply 2>&1)
        echo "✓ Container layers applied"
    else
        echo "No manifest at .claude/container-layers.json and no Containerfile — skipping."
    fi
else
    echo "container-layer skill not bootstrapped — skipping."
fi
_tmark "container_layer"

# Fetch skills fresh (always, not from container cache)
echo "Fetching skills..."
_fetch_skills
_tmark "skills_fetch"
# muninn-utilities overlays remembering/ + installs muninn_utils/ before boot
_fetch_muninn_utilities
_tmark "muninn_utilities"
_setup_python_paths
_tmark "python_paths"
_verify_fuse_deps
_tmark "fuse_deps"
_start_memfs_background
_tmark "memfs_start"

touch "$MARKER"
_output_skills
_tmark "skills_list"
_run_smoke_test_background

# Custom post-boot hook
[ -f "$PROJECT_DIR/post-boot.sh" ] && bash "$PROJECT_DIR/post-boot.sh" 2>&1
_tmark "post_boot"
_ttotal

exit 0
