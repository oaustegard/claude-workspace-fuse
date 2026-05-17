#!/bin/bash
# Regression test for issue #80: the env-loader fragment installed by
# Containerfile must source every /mnt/project/*.env when present and
# silently no-op when the directory is missing.
#
# Reconstructs the loader script via the same `printf` invocation used in
# Containerfile, then sources it under a fake /mnt/project to verify env
# exposure.

set -euo pipefail

TEST_DIR=$(mktemp -d)
trap 'rm -rf "$TEST_DIR"' EXIT

LOADER="$TEST_DIR/muninn-env.sh"
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# Extract the printf invocation from Containerfile and run it to materialize
# the loader. This guarantees the test exercises exactly what gets baked into
# the snapshot — any drift between Containerfile and test fails here.
loader_cmd=$(grep -n 'printf .* /etc/profile.d/muninn-env.sh' "$SCRIPT_DIR/layers/Containerfile" \
    | head -1 | sed 's/^[0-9]*:RUN //; s| > /etc/profile.d/muninn-env.sh.*||')
if [ -z "$loader_cmd" ]; then
    echo "FAIL: could not locate loader printf in Containerfile"
    exit 1
fi
eval "$loader_cmd" > "$LOADER"

# ── Case 1: /mnt/project absent → loader is a silent no-op
output=$(bash -c "PROJECT_OVERRIDE='$TEST_DIR/nonexistent'; . '$LOADER'; echo \"ok=\$?\"")
if [ "$output" != "ok=0" ]; then
    echo "FAIL: loader errored when /mnt/project absent: $output"
    exit 1
fi

# ── Case 2: rewritten loader pointed at fake project dir sources every *.env
FAKE_PROJECT="$TEST_DIR/project"
mkdir -p "$FAKE_PROJECT"
cat > "$FAKE_PROJECT/a.env" <<'EOF'
TEST_A=alpha
TEST_SHARED=from_a
EOF
cat > "$FAKE_PROJECT/b.env" <<'EOF'
TEST_B=beta
TEST_SHARED=from_b
EOF

# Substitute /mnt/project for our fake dir to exercise the loop logic.
sed "s|/mnt/project|$FAKE_PROJECT|g" "$LOADER" > "$LOADER.local"

output=$(bash -c ". '$LOADER.local'; echo \"A=\$TEST_A B=\$TEST_B SHARED=\$TEST_SHARED\"")
if [ "$output" != "A=alpha B=beta SHARED=from_b" ]; then
    echo "FAIL: env vars not sourced as expected"
    echo "  expected: A=alpha B=beta SHARED=from_b"
    echo "  actual:   $output"
    exit 1
fi

# ── Case 3: vars must be EXPORTED (visible to child processes), not just set
output=$(bash -c ". '$LOADER.local'; bash -c 'echo CHILD=\$TEST_A'")
if [ "$output" != "CHILD=alpha" ]; then
    echo "FAIL: vars not exported to child shells: $output"
    exit 1
fi

# ── Case 4: empty .env file (e.g. zero-length) doesn't break the loop
: > "$FAKE_PROJECT/empty.env"
output=$(bash -c ". '$LOADER.local'; echo \"A=\$TEST_A\"")
if [ "$output" != "A=alpha" ]; then
    echo "FAIL: empty .env broke loader: $output"
    exit 1
fi

# ── Case 5: Containerfile registers BASH_ENV and snapshots the loader/env
grep -q '^RUN .*BASH_ENV=/etc/profile.d/muninn-env.sh' "$SCRIPT_DIR/layers/Containerfile" \
    || { echo "FAIL: Containerfile missing BASH_ENV registration"; exit 1; }
grep -q '^SNAPSHOT /etc/profile.d/muninn-env.sh' "$SCRIPT_DIR/layers/Containerfile" \
    || { echo "FAIL: Containerfile missing SNAPSHOT for env loader"; exit 1; }
grep -q '^SNAPSHOT /etc/environment' "$SCRIPT_DIR/layers/Containerfile" \
    || { echo "FAIL: Containerfile missing SNAPSHOT for /etc/environment"; exit 1; }

echo "PASS: muninn-env loader sources /mnt/project/*.env and exports to children"
