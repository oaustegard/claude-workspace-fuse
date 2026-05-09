#!/bin/bash
# Regression test for issue #61: _link_slash_skills must symlink curated
# skills from /mnt/skills/user/ into ~/.claude/skills/ so the harness's
# Skill tool can invoke them. Skips skills missing from the source dir.

set -euo pipefail

TEST_DIR=$(mktemp -d)
trap 'rm -rf "$TEST_DIR"' EXIT

# Fake source: only some of the curated skills are present.
mkdir -p "$TEST_DIR/skills/composing-html" "$TEST_DIR/skills/flowing"
echo "name: composing-html" > "$TEST_DIR/skills/composing-html/SKILL.md"
echo "name: flowing"        > "$TEST_DIR/skills/flowing/SKILL.md"

FAKE_HOME="$TEST_DIR/home"
mkdir -p "$FAKE_HOME"

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# Override HOME (referenced via python expanduser inside the function)
# and SKILLS_DIR, then exercise the function.
output=$(HOME="$FAKE_HOME" bash -c "
    set +e
    SKILLS_DIR='$TEST_DIR/skills'
    $(sed -n '/^_link_slash_skills()/,/^}/p' "$SCRIPT_DIR/boot-ccotw.sh")
    _link_slash_skills
")

target="$FAKE_HOME/.claude/skills"

if [ ! -L "$target/composing-html" ]; then
    echo "FAIL: composing-html symlink missing"
    echo "--- $target ---"; ls -la "$target" 2>/dev/null || echo "(missing)"
    echo "--- output ---"; echo "$output"
    exit 1
fi
if [ ! -L "$target/flowing" ]; then
    echo "FAIL: flowing symlink missing"
    exit 1
fi
# A curated skill that DOESN'T exist in the source must NOT be symlinked.
if [ -e "$target/tree-sitting" ]; then
    echo "FAIL: tree-sitting was symlinked despite missing source"
    exit 1
fi
# A non-curated skill present in source must NOT be symlinked.
mkdir -p "$TEST_DIR/skills/random-skill"
echo "name: random-skill" > "$TEST_DIR/skills/random-skill/SKILL.md"
if [ -e "$target/random-skill" ]; then
    echo "FAIL: non-curated random-skill was symlinked"
    exit 1
fi

# Symlink should point at the source directory.
resolved=$(readlink -f "$target/composing-html")
expected=$(readlink -f "$TEST_DIR/skills/composing-html")
if [ "$resolved" != "$expected" ]; then
    echo "FAIL: symlink target wrong. got=$resolved expected=$expected"
    exit 1
fi

# Idempotence: running twice should not error.
HOME="$FAKE_HOME" bash -c "
    set +e
    SKILLS_DIR='$TEST_DIR/skills'
    $(sed -n '/^_link_slash_skills()/,/^}/p' "$SCRIPT_DIR/boot-ccotw.sh")
    _link_slash_skills
" >/dev/null

echo "PASS: link_slash_skills"
