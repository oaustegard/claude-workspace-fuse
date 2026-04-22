#!/bin/bash
# Post-boot: load Muninn identity from Turso
# Called by boot-ccotw.sh after container layer is applied.
# Output goes into Claude's context window.
#
# Set BOOT_TELEMETRY=1 to append per-phase timing data to boot output.

cd /mnt/skills/user/remembering

TELEMETRY_ARG=""
if [ "${BOOT_TELEMETRY:-0}" = "1" ]; then
    TELEMETRY_ARG="telemetry=True"
fi

# Stderr goes to a log file so retry tracebacks don't pollute Claude's
# context window. If both attempts fail, surface the log so failures stay
# visible.
ERR_LOG=/tmp/muninn-boot-stderr.log
python3 -c "from scripts import boot; print(boot($TELEMETRY_ARG))" 2>"$ERR_LOG" \
    || python3 -c "from scripts import boot; print(boot())" 2>"$ERR_LOG" \
    || cat "$ERR_LOG"
