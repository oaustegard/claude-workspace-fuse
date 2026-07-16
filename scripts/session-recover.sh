#!/bin/bash
# Finish a degraded boot once the spoke repos are in session scope.
#
# WHY THIS EXISTS
# --------------
# The SessionStart hook (boot-ccotw.sh) runs before any model turn exists,
# so it cannot call add_repo — the only in-session lever that widens the
# CCotw proxy's GitHub scope to the spoke repos. On a cold start the spokes
# (claude-skills, muninn-utilities, claude-container-layers) are out of scope,
# every codeload tarball 403s, and boot comes up degraded: no container-layer
# skill, no fresh skills, no remembering, no memfs mount, no identity.
#
# scripts/ensure-scope.sh (a UserPromptSubmit hook) detects that degraded
# state on the first turn and injects a directive telling the model to call
# add_repo for the three spokes and then run THIS script. By the time this
# runs, scope is granted and codeload works — so a plain re-run of boot
# succeeds end to end. See CLAUDE.md "Boot recovery" and memories
# 74901b87 / 900d382b for the three-tier proxy-scope diagnosis.
#
# Idempotent: safe to run any number of times. Re-running boot takes the
# marker "cached" branch and simply re-fetches skills, remounts memfs, and
# reloads identity.

set -uo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$PROJECT_DIR"

echo "[recover] finishing boot from $PROJECT_DIR"

# ── 1. Verify scope actually landed ─────────────────────────────────────────
# add_repo must have been called already. If claude-skills still 403s, the
# model skipped that step — say so loudly instead of looping on failed fetches.
code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 \
    "https://codeload.github.com/oaustegard/claude-skills/tar.gz/main" 2>/dev/null)
if [ "$code" = "403" ]; then
    echo "[recover] ✗ claude-skills still 403 — spokes are NOT in scope yet."
    echo "[recover]   Call add_repo for oaustegard/{claude-skills,muninn-utilities,"
    echo "[recover]   claude-container-layers} FIRST, then re-run this script."
    exit 2
fi
echo "[recover] ✓ scope confirmed (claude-skills codeload -> $code)"

# ── 2. Re-run boot (idempotent) ─────────────────────────────────────────────
# Fetches the container-layer skill, applies layers (restores the fuse layer
# -> fusepy/libfuse), fetches skills + muninn-utilities, mounts memfs, and
# reloads Muninn identity via post-boot.sh.
echo "[recover] re-running boot-ccotw.sh…"
bash "$PROJECT_DIR/boot-ccotw.sh" || echo "[recover] boot returned non-zero (continuing to fuse fallback)"

# ── 3. Fuse-runtime fallback ────────────────────────────────────────────────
# If the fuse container layer didn't restore (cold cache, apply skipped), the
# memfs mount fails with "No module named 'fuse'" or "Unable to find libfuse".
# fusepy is only Python bindings; it needs libfuse.so.2 + the fusermount
# binary. Install both from apt as a floor, then pip the bindings. All three
# are no-ops when already present.
if ! mountpoint -q /mnt/muninn 2>/dev/null; then
    echo "[recover] memfs not mounted — installing fuse runtime as fallback"
    if ! ldconfig -p 2>/dev/null | grep -q 'libfuse.so.2' || ! command -v fusermount >/dev/null 2>&1; then
        apt-get install -y libfuse2 fuse >/dev/null 2>&1 \
            && echo "[recover]   ✓ libfuse2 + fuse (fusermount) installed" \
            || echo "[recover]   ✗ apt install of libfuse2/fuse failed"
    fi
    python3 -c "import fuse" 2>/dev/null \
        || { pip install --quiet fusepy 2>/dev/null \
                && echo "[recover]   ✓ fusepy installed" \
                || echo "[recover]   ✗ pip install fusepy failed"; }

    # Re-arm the mount now that the runtime exists.
    if python3 -c "import fuse" 2>/dev/null && command -v fusermount >/dev/null 2>&1; then
        fusermount -u /mnt/muninn 2>/dev/null || true
        mkdir -p /mnt/muninn
        setsid nohup python3 "$PROJECT_DIR/scripts/muninn_memfs.py" /mnt/muninn \
            </dev/null >/tmp/.muninn-memfs.log 2>&1 &
        echo "[recover]   memfs remount kicked off (pid $!)"
        sleep 4
    fi
fi

# ── 4. Report ───────────────────────────────────────────────────────────────
if mountpoint -q /mnt/muninn 2>/dev/null; then
    n=$(ls /mnt/muninn/memories 2>/dev/null | wc -l)
    echo "[recover] ✓ memfs mounted — $n memories at /mnt/muninn/memories"
else
    echo "[recover] ✗ memfs still not mounted — see /tmp/.muninn-memfs.log"
fi
[ -d /mnt/skills/user/remembering ] \
    && echo "[recover] ✓ remembering skill present" \
    || echo "[recover] ✗ remembering skill missing — identity boot() unavailable"
echo "[recover] done"
