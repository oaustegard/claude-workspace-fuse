#!/bin/bash
# Surface post-build smoke-test failures to the model.
#
# Companion to scripts/rebuild-status.sh. Wired as a UserPromptSubmit hook —
# every user message checks /tmp/.smoke-failures (written by smoke_test.py
# when a validator failed) and flushes it into the next prompt's context.
#
# To avoid spamming the same failure on every prompt, we only emit when the
# marker's mtime is newer than the last-shown timestamp tracked in
# /tmp/.smoke-failures.shown.
#
# Issue: https://github.com/oaustegard/claude-workspace/issues/52

set -e

MARKER="/tmp/.smoke-failures"
CURSOR="/tmp/.smoke-failures.shown"

[ -f "$MARKER" ] || exit 0

mtime=$(stat -c %Y "$MARKER" 2>/dev/null || echo 0)
shown=0
[ -f "$CURSOR" ] && shown=$(cat "$CURSOR" 2>/dev/null || echo 0)
shown=${shown:-0}

if [ "$mtime" -le "$shown" ]; then
    exit 0
fi

echo "$mtime" > "$CURSOR"

echo "<smoke-failures marker=\"$MARKER\">"
cat "$MARKER"
echo "</smoke-failures>"
