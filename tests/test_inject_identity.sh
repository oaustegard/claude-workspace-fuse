#!/bin/bash
# Regression test for issue #60: inject-identity.sh must emit boot file
# content on first invocation per session and skip on subsequent ones,
# gated by the boot file's mtime vs the cursor.

set -euo pipefail

TEST_DIR=$(mktemp -d)
trap 'rm -rf "$TEST_DIR"' EXIT

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BOOT="$TEST_DIR/boot.md"
CURSOR="$TEST_DIR/cursor"

cat >"$BOOT" <<EOF
# PROFILE
identity: corvid raven
voice: dry, sardonic
EOF

# Run a copy of the script with the paths overridden, so we don't touch
# the real /tmp markers.
TEST_HOOK="$TEST_DIR/inject-identity.sh"
sed \
    -e "s|/tmp/muninn-boot-full.md|$BOOT|g" \
    -e "s|/tmp/.muninn-identity-injected|$CURSOR|g" \
    "$SCRIPT_DIR/scripts/inject-identity.sh" >"$TEST_HOOK"
chmod +x "$TEST_HOOK"

# First invocation: must emit boot content wrapped in identity tags.
out1=$(bash "$TEST_HOOK")
if ! echo "$out1" | grep -q "<muninn-identity-context"; then
    echo "FAIL: first invocation missing opening tag"
    echo "--- output ---"; echo "$out1"
    exit 1
fi
if ! echo "$out1" | grep -q "</muninn-identity-context>"; then
    echo "FAIL: first invocation missing closing tag"
    exit 1
fi
if ! echo "$out1" | grep -q "corvid raven"; then
    echo "FAIL: first invocation did not include boot content"
    exit 1
fi
if [ ! -f "$CURSOR" ]; then
    echo "FAIL: cursor file not created"
    exit 1
fi

# Second invocation with no boot mtime change: must emit nothing.
out2=$(bash "$TEST_HOOK")
if [ -n "$out2" ]; then
    echo "FAIL: second invocation produced output (cursor not respected)"
    echo "--- output ---"; echo "$out2"
    exit 1
fi

# Touch the boot file to advance mtime, then expect re-injection.
sleep 1
touch "$BOOT"
out3=$(bash "$TEST_HOOK")
if [ -z "$out3" ]; then
    echo "FAIL: third invocation (newer boot mtime) produced no output"
    exit 1
fi

# Missing boot file: must exit cleanly with no output.
rm -f "$BOOT"
rm -f "$CURSOR"
out4=$(bash "$TEST_HOOK")
if [ -n "$out4" ]; then
    echo "FAIL: missing boot file should produce no output, got: $out4"
    exit 1
fi

echo "PASS: inject_identity"
