# Revoking muninn-remind

This tool stores reminders as `procedure`-typed memories in the Muninn Turso
DB. There is no third-party transmission; everything lives in the user's own
memory store. Revocation is credential rotation plus optional cleanup of
already-stored reminders.

## Step 1 — Stop future writes (credential rotation)

Rotate `TURSO_TOKEN` at https://app.turso.tech/. This immediately stops the
tool from creating, completing, snoozing, or archiving reminders. **Primary
kill.**

`TURSO_TOKEN` is shared across all the memory-touching utilities
(`remembering` itself, `issue_close`, `verify_patch`, `memory_tfidf`,
`zeitgeist_delta`, `perch_triage`'s auto-close path). Generate a new token
and update consumers before revoking the old.

## Step 2 — Remove already-stored reminders (optional)

Past reminders live as memories tagged `remind` / `remind-active` /
`remind-<kind>`. To wipe them:

```python
from muninn_utils.remind import remind_list
from scripts.memory import forget
for r in remind_list(include_done=True):
    forget(r["id"])
```

Or, less surgically, delete by tag from the Turso console (drop everything
tagged `remind`).

## Step 3 — Uninstall the code

If installed via the manifest's `runtime.install`, delete the cloned tree.

## What this kill switch cannot do

- Cannot retract reminders that have already surfaced in past boots — those
  live in the boot output / transcripts of past sessions, not in the
  current memory state.
- Cannot affect any non-reminder memory in Turso; the cleanup script above
  only touches `remind`-tagged rows.
