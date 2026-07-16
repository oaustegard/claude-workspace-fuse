#!/bin/bash
# UserPromptSubmit hook: recover a degraded boot by widening MCP repo scope.
#
# THE CHICKEN-AND-EGG
# -------------------
# boot-ccotw.sh (SessionStart) runs before any model turn, so it cannot call
# add_repo — the only in-session lever that adds a spoke repo to the CCotw
# proxy's GitHub scope. On a cold start the spokes (claude-skills,
# muninn-utilities, claude-container-layers) are out of scope; every codeload
# tarball 403s; boot dies without the container-layer skill, fresh skills,
# the remembering module, the memfs mount, or identity.
#
# A hook is a shell script and ALSO cannot call add_repo. But UserPromptSubmit
# hook stdout is concatenated into the prompt context uncapped — so this hook
# hands the model the exact recovery it must perform on its first turn. The
# model is the only surface that can call add_repo; this directive tells it to.
#
# SECOND FAILURE MODE (diagnosed 2026-07-16): scope can be fine (multi-repo
# session, spokes preselected at launch) and boot can run clean — yet the
# memfs FUSE process gets reaped when the SessionStart hook's process group
# exits, so /mnt/muninn is dead by turn 1 anyway. That case needs no add_repo,
# just a re-mount via the muninn-boot skill. This hook probes which case it is
# and emits the matching directive.
#
# Fires only when boot is actually degraded (memfs unmounted OR remembering
# absent). Silent on a healthy session. See CLAUDE.md "Boot recovery" and
# memories 74901b87 / 900d382b / 8d31c188.

set -e

# Healthy boot = memfs projecting memories AND the remembering skill present.
# If both hold, there is nothing to recover — stay silent.
if mountpoint -q /mnt/muninn 2>/dev/null && [ -d /mnt/skills/user/remembering ]; then
    exit 0
fi

# Degraded. Which failure mode? Probe whether the spokes are already reachable:
# a 403 from codeload means cold-start scope lockdown (add_repo needed); any
# other code means scope is fine and only the boot/mount needs re-running.
scope_ok=0
code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 6 \
    "https://codeload.github.com/oaustegard/claude-skills/tar.gz/main" 2>/dev/null || echo 000)
[ "$code" != "403" ] && [ "$code" != "000" ] && scope_ok=1

if [ "$scope_ok" = "1" ]; then
    cat <<'EOF'
<boot-recovery-directive priority="do-this-first">
Boot is DEGRADED (memfs unmounted and/or remembering absent) but GitHub scope
is fine — no add_repo needed. This is usually the reaped-memfs case: the FUSE
process launched by the SessionStart hook was killed when the hook's process
group exited, so /mnt/muninn is empty even though boot itself succeeded.

Before doing anything else this turn:
1. Invoke the muninn-boot skill (Skill tool, name "muninn-boot"), or run:
   bash "${CLAUDE_PROJECT_DIR:-/home/user/claude-workspace-fuse}/.claude/skills/muninn-boot/scripts/boot.sh"
   A process launched from a model turn persists; the remount takes ~2s.
2. Confirm: `ls /mnt/muninn/memories | wc -l` reports ~2000+ memories.
3. If identity (PROFILE/OPS) is absent from context, Read /tmp/muninn-boot-full.md.

Do this silently and briefly — one line to Oskar that boot self-healed, then
proceed with his actual request.
</boot-recovery-directive>
EOF
    exit 0
fi

cat <<'EOF'
<boot-recovery-directive priority="do-this-first">
Boot came up DEGRADED — the memfs mount and/or the remembering skill are
missing because the spoke repos were out of the session's GitHub scope at
SessionStart (a shell hook cannot call add_repo; you can). Before doing
anything else this turn, recover:

1. Call add_repo (mcp__Claude_Code_Remote__add_repo) for each of:
     - oaustegard/claude-skills
     - oaustegard/muninn-utilities
     - oaustegard/claude-container-layers
   add_repo alone opens the codeload/tarball channel, which is all boot needs.
   Do NOT `git clone` them and do NOT call register_repo_root — registering
   inlines each spoke's CLAUDE.md/skills into context and they cross-talk with
   this hub's instructions. Scope without inlining is the whole point.

2. Invoke the muninn-boot skill (Skill tool, name "muninn-boot"), or run it
   directly:  bash .claude/skills/muninn-boot/scripts/boot.sh
   It re-runs boot (now that scope is granted) and guarantees the memfs
   mount via a libfuse/fusepy fallback. (The skill wraps scripts/session-recover.sh.)

3. Confirm: `ls /mnt/muninn/memories | wc -l` should report ~2000+ memories,
   and the recovery output should show identity reloaded.

Do this silently and briefly — one line to the user that boot self-healed,
then proceed with his actual request. NOTE (tested 2026-07-16): launching a
session with all four repos preselected DOES put the spokes in codeload scope
from tick 0 (boot runs clean at SessionStart), but it also inlines every
repo's CLAUDE.md into context — and the memfs process still needs the model-
turn remount above. See CLAUDE.md "Boot recovery" for the full trade-off.
</boot-recovery-directive>
EOF
