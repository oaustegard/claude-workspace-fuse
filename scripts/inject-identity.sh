#!/bin/bash
# UserPromptSubmit hook: re-inject Muninn identity past the SessionStart cap.
#
# Claude Code on the Web truncates SessionStart stdout to ~2KB. boot-ccotw.sh
# emits ~90KB of skills XML, profile, ops, tensions, and recent memories —
# so 95%+ of the identity context (the part that defines the corvid voice
# and ops triggers) gets dropped before reaching the model. The visible
# preamble ("Read before responding") is a passive warning the model
# routinely plows past, and Oskar then has to call out the off-voice tics
# mid-task to recover identity.
#
# UserPromptSubmit hook stdout is concatenated into the prompt's context
# without a 2KB cap. We use it to inject the full boot file once per
# session — gated by mtime cursor, mirroring smoke-status.sh.
#
# Issue: https://github.com/oaustegard/claude-workspace/issues/60

set -e

BOOT="/tmp/muninn-boot-full.md"
CURSOR="/tmp/.muninn-identity-injected"

[ -f "$BOOT" ] || exit 0

mtime=$(stat -c %Y "$BOOT" 2>/dev/null || echo 0)
shown=0
[ -f "$CURSOR" ] && shown=$(cat "$CURSOR" 2>/dev/null || echo 0)
shown=${shown:-0}

if [ "$mtime" -le "$shown" ]; then
    exit 0
fi

echo "$mtime" > "$CURSOR"

cat <<EOF
<muninn-identity-context source="$BOOT">
SessionStart boot output exceeds Claude Code on the Web's ~2KB context cap, so
profile, ops, tensions, and recent memories were truncated before reaching you.
The full boot follows. Inhabit Muninn's identity from the next response —
corvid voice, named ops triggers, tensions to navigate. Don't merely
acknowledge.

EOF
cat "$BOOT"
echo "</muninn-identity-context>"
