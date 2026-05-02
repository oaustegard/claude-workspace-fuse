#!/bin/bash
# Surface incremental container-layer rebuild status to the model.
#
# Replaces the old `<rebuild-monitor-directive>` boot-text approach (which
# asked the model to arm the Monitor tool against /tmp/.rebuild-layer.log).
# Wired as a UserPromptSubmit hook — every user message flushes any new
# log lines since the last check, so START / RESTORE / DONE / FAIL events
# from rebuild-layer.sh reach the model without a tool-arming request.
#
# Cursor file tracks bytes consumed. boot-ccotw.sh resets both files when
# it kicks off a fresh rebuild, so a new run never inherits a stale offset.

set -e

LOG="/tmp/.rebuild-layer.log"
CURSOR="/tmp/.rebuild-layer.log.cursor"

[ -f "$LOG" ] || exit 0

start=0
if [ -f "$CURSOR" ]; then
    start=$(cat "$CURSOR" 2>/dev/null || echo 0)
    start=${start:-0}
fi

size=$(stat -c %s "$LOG" 2>/dev/null || echo 0)

# Log truncated under our feet (e.g. a new rebuild started since last
# check). Reset and read from byte 0.
if [ "$size" -lt "$start" ]; then
    start=0
fi

if [ "$size" -le "$start" ]; then
    echo "$size" > "$CURSOR"
    exit 0
fi

new=$(tail -c +$((start + 1)) "$LOG")
echo "$size" > "$CURSOR"

[ -z "$new" ] && exit 0

# Tag so the model recognizes these as background-rebuild events, not
# anything tied to the user's current prompt.
echo "<rebuild-status log=\"$LOG\">"
printf '%s\n' "$new"
echo "</rebuild-status>"
