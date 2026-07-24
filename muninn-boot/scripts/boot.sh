#!/bin/bash
# Muninn boot — fetch skills + utilities from main, load env, run boot().
# Sideload is DYNAMIC: it tracks each repo's main branch (not a pinned SHA) so
# changes land the next cold boot without a version bump. The trade is that main
# is fetched as-is, unreviewed; keep main deployable.
set -e
CLAUDE_SKILLS_REF=main
MUNINN_UTILS_REF=main

# Warm-container fast path. The project instruction is reinjected every message,
# so this script is invoked many times per conversation. The sentinel's lifetime
# is the container's: a recycled container lacks it and fetches fresh; a warm one
# exits here. Because the sideload is dynamic, a push to main mid-session is
# picked up only on a new container or after `rm`-ing the sentinel. skinny boot
# (BOOT_MODE set) always runs fully.
SENTINEL=/home/claude/.muninn-booted
if [ -z "$BOOT_MODE" ] \
   && [ -f "$SENTINEL" ] \
   && [ -d /home/claude/muninn-utilities/muninn_utils ]; then
  echo "warm boot: already fetched this container. rm $SENTINEL to re-pull main."
  exit 0
fi

cd /tmp

curl -sL "https://codeload.github.com/oaustegard/claude-skills/tar.gz/$CLAUDE_SKILLS_REF" -o cs.tar.gz \
  && tar -xzf cs.tar.gz \
  && mkdir -p /mnt/skills/user \
  && cp -r claude-skills-$CLAUDE_SKILLS_REF/* /mnt/skills/user/

curl -sL "https://codeload.github.com/oaustegard/muninn-utilities/tar.gz/$MUNINN_UTILS_REF" -o mu.tar.gz \
  && tar -xzf mu.tar.gz \
  && mkdir -p /home/claude/muninn-utilities \
  && cp -r muninn-utilities-$MUNINN_UTILS_REF/* /home/claude/muninn-utilities/

set -a
. /mnt/project/Turso.env 2>/dev/null
. /mnt/project/GitHub.env 2>/dev/null
set +a

PTH=/usr/local/lib/python3.12/dist-packages/muninn-remembering.pth
HOMEDIR=$(python3 -c 'import os; print(os.path.expanduser("~"))')
printf '%s\n' "/home/claude/muninn-utilities/remembering" "$HOMEDIR" > "$PTH"
for d in /mnt/skills/user/*/scripts/; do
  ls "$d"*.py >/dev/null 2>&1 && echo "$d" >> "$PTH"
done

python3 << 'PYBOOT'
import os
from scripts import boot
print(boot(mode=os.environ.get('BOOT_MODE')))
PYBOOT

touch "$SENTINEL"   # last line, only on success
