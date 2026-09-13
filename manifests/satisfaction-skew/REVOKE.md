# Revoking muninn-satisfaction-skew

This tool is a read-only measurement. It counts and buckets memory rows and
computes ratios — no writes to Turso, no config mutation, no trigger firing, no
third party contacted, no state persisted between calls. Callers may inject the
row list (`measure_skew(memories=[...])`), in which case the module performs no
I/O at all.

## Step 1 — Stop future reads

The only I/O is the default path, a single `SELECT` of non-deleted memories
through the `remembering` `_exec` layer. To stop it, either always pass an
injected `memories` list, or make `muninn_utils.satisfaction_skew` unimportable.
There is no write-path hook to unwire — nothing in `remembering` calls this
tool; it is invoked on demand only.

## Step 2 — Uninstall the code

If installed via the manifest's `runtime.install` (git clone of
`oaustegard/muninn-utilities`, subpath `muninn_utils`), delete the cloned tree,
including `muninn_utils/satisfaction_skew.py`.

## Step 3 — (only if the default Turso path was used) Rotate the token

The read uses `TURSO_TOKEN`. If you must guarantee no further reads, rotate it
at https://app.turso.tech/ — but rotate the tools that share the token first
(the `remembering` skill, `memory_tfidf`, `remind`, `correction_gate`), since
they will need the new token too.

## What this kill switch cannot do

- Cannot retract a `SkewReport` already returned to a caller — it lives in the
  caller's output, not in the tool.
- Cannot affect Turso contents: this tool never writes, so there is nothing in
  the store to undo.
- Cannot un-decide any rebalance made on the strength of a report; the
  satisfaction-register ops entry is edited through the normal `config_set`
  path, independently of this tool.
