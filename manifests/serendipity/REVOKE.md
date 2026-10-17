# Revoking muninn-serendipity

This tool is a read-only generator of candidate memory pairs. It never writes to
Turso, never mutates config, never fires a trigger, contacts no third party, and
persists no state between calls. Callers may inject the row list
(`serendipity(memories=[...])`), in which case the module performs no I/O at all.

## Step 1 — Stop future reads

The only I/O is the default path: a single `SELECT` of non-deleted memories
through the `remembering` `_exec` layer. To stop it, either always pass an
injected `memories` list, or make `muninn_utils.serendipity` unimportable.
Nothing in `remembering` calls this tool — it is invoked on demand only, so
there is no write-path hook to unwire.

## Step 2 — Uninstall the code

If installed via the manifest's `runtime.install` (git clone of
`oaustegard/muninn-utilities`, subpath `muninn_utils`), delete the cloned tree,
including `muninn_utils/serendipity.py`.

## Step 3 — (only if the default Turso path was used) Rotate the token

The read uses `TURSO_TOKEN`. Rotate at https://app.turso.tech/ — but rotate the
tools that share the token first (the `remembering` skill, `memory_tfidf`,
`satisfaction_skew`, `remind`, `correction_gate`), since they will need the new
token too.

## What this kill switch cannot do

- Cannot retract pairs already returned to a caller; they live in the caller's
  output, not in the tool.
- Cannot affect Turso contents. This tool never writes, so there is nothing in
  the store to undo.
- Cannot undo a connection acted on from a pair. Adding `refs`, `supersede`, and
  `forget` all run through the normal `remembering` API as separate, explicit
  decisions; reverse them there.
