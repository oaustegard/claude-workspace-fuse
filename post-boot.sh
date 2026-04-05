#!/bin/bash
# Post-boot: load Muninn identity from Turso
# Called by boot-ccotw.sh after container layer is applied.
# Output goes into Claude's context window.

cd /mnt/skills/user/remembering
python3 -c "from scripts import boot; print(boot())"
