# Revoking muninn-boot-ledger

The ledger itself is read-only: it loads the config table and active memories,
computes cost + a fire-rate proxy, and returns a report. It writes nothing.
Revoking has two independent parts — the read tool, and the opt-in fire counter
it ships with.

## Step 1 — Turn off the go-forward fire counter

The counter only runs when `MUNINN_INSTRUMENT_FIRES` is set in the environment.
Unset it (remove it from the boot env / session profile) and `config_get`
returns to a plain read with zero added cost. Nothing else is needed — the hook
is best-effort and already swallows all errors.

To also drop the accumulated counts:

```sql
UPDATE config SET fire_count = 0, last_fired = NULL;   -- or ALTER TABLE ... DROP COLUMN
```

The `fire_count` / `last_fired` columns are additive; leaving them in place with
the env var unset is harmless.

## Step 2 — Unwire the counter from config_get (optional)

If you want `config_get` to have no instrumentation branch at all, remove the
`config_fire(key)` call guarded by `MUNINN_INSTRUMENT_FIRES` in
`remembering/scripts/config.py`, and drop the `config_fire` export from
`remembering/scripts/__init__.py`.

## Step 3 — Uninstall the code

If installed via the manifest's `runtime.install` (git clone of
`oaustegard/muninn-utilities`, subpath `muninn_utils`), delete
`muninn_utils/boot_ledger.py` and `muninn_utils/tests/test_boot_ledger.py`.

## Step 4 — (only if the report was run against live Turso) Stop future reads

`report()` reads through the live `_exec`. Passing an injected `exec_fn` avoids
Turso entirely; if it was bound to live Turso and you need to stop reads, rotate
`TURSO_TOKEN` at https://app.turso.tech/ (rotate any tools that share the token
first — `remembering`, `memory_tfidf`, `remind`).

## What this kill switch cannot do

- Cannot un-collapse the voice-signature edit that shipped with issue #84 — that
  is a config change, reversible by restoring
  `docs/muninn-voice-signature.pre-84.md` with `config_set`, not by revoking
  this tool.
- Cannot retract reports already returned to a caller — they live in the
  caller's output, not in the tool.
