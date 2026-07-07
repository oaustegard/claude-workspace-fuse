#!/bin/bash
# muninn-boot skill entrypoint (FUSE variant).
#
# Thin, health-aware wrapper — NOT a second boot implementation. The real boot
# lives in boot-ccotw.sh (run by the SessionStart hook on warm resumes) and the
# cold-start recovery lives in scripts/session-recover.sh. This skill is the
# model-invocable front door for the cold path, where the model has just called
# add_repo for the three spokes (the one step a shell hook cannot do) and now
# needs boot re-run with scope in hand.
#
# Idempotent: invoking it on an already-healthy session is a cheap no-op.

set -uo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../../../.." && pwd)}"

# Already booted (warm resume / hook succeeded)? Nothing to do.
if mountpoint -q /mnt/muninn 2>/dev/null && [ -d /mnt/skills/user/remembering ]; then
    n=$(ls /mnt/muninn/memories 2>/dev/null | wc -l)
    echo "[muninn-boot] already healthy — /mnt/muninn mounted ($n memories), remembering present. No-op."
    exit 0
fi

# Degraded → run the shared recovery (confirms scope, re-runs boot, fuse fallback).
recover="$PROJECT_DIR/scripts/session-recover.sh"
if [ ! -f "$recover" ]; then
    echo "[muninn-boot] ✗ $recover missing — cannot recover." >&2
    exit 1
fi

echo "[muninn-boot] degraded boot detected — running recovery"
echo "[muninn-boot] (if this reports 'spokes NOT in scope', call add_repo for"
echo "[muninn-boot]  oaustegard/{claude-skills,muninn-utilities,claude-container-layers} first)"
exec bash "$recover"
