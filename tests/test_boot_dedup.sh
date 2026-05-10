#!/bin/bash
# Regression test for issue #62: _output_skills must dedup duplicate `name:`
# fields across skill directories. Two dirs (e.g. building-github-index/ and
# building-github-index-v2/) shipping with the same `name:` should produce
# exactly one occurrence of the skill name in the boot output (now emitted
# as a comma-delimited list inside <available_skills>).

set -euo pipefail

TEST_DIR=$(mktemp -d)
trap 'rm -rf "$TEST_DIR"' EXIT

# Build a fake $SKILLS_DIR with three skills, two of which collide on name.
mkdir -p "$TEST_DIR/skills/dup-a" "$TEST_DIR/skills/dup-b" "$TEST_DIR/skills/unique"
cat >"$TEST_DIR/skills/dup-a/SKILL.md" <<EOF
---
name: shared-name
description: first
EOF
cat >"$TEST_DIR/skills/dup-b/SKILL.md" <<EOF
---
name: shared-name
description: second
EOF
cat >"$TEST_DIR/skills/unique/SKILL.md" <<EOF
---
name: unique
description: third
EOF

# Source boot-ccotw.sh into a stub-friendly subshell. We can't run it
# directly because main flow expects network + container layer. Instead,
# extract the function and exercise it.
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SKILLS_DIR="$TEST_DIR/skills"
export SKILLS_DIR

# Strip set -e (which fires inside the script) and unrelated runtime
# bits. We just need _output_skills.
output=$(bash -c "
    set +e
    SKILLS_DIR='$SKILLS_DIR'
    $(sed -n '/^_output_skills()/,/^}/p' "$SCRIPT_DIR/boot-ccotw.sh")
    _output_skills
")

# Extract just the comma-delimited body inside <available_skills ...>...</available_skills>
body=$(echo "$output" | sed -n 's|.*<available_skills[^>]*>\(.*\)</available_skills>.*|\1|p')

# Count occurrences of each name as comma-bounded tokens (handles start/end of list).
count_name() {
    echo ",$body," | grep -o ",$1," | wc -l
}

n_shared=$(count_name "shared-name")
n_unique=$(count_name "unique")

if [ "$n_shared" -ne 1 ]; then
    echo "FAIL: expected exactly 1 occurrence of shared-name, got $n_shared"
    echo "--- output ---"
    echo "$output"
    exit 1
fi
if [ "$n_unique" -ne 1 ]; then
    echo "FAIL: expected exactly 1 occurrence of unique, got $n_unique"
    echo "--- output ---"
    echo "$output"
    exit 1
fi

# Sanity-check: no per-skill <skill> tags should be emitted anymore.
if echo "$output" | grep -q '<skill>'; then
    echo "FAIL: legacy <skill> tag still present in output"
    echo "--- output ---"
    echo "$output"
    exit 1
fi

echo "PASS: boot dedup ($n_shared shared, $n_unique unique; comma-delimited)"
