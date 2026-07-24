# Revoking muninn-correction-gate

This tool is pure local computation. Its core (trigger-firing match, held-in /
held-out differential comparison, budget guard) performs no I/O: no third party
is contacted, nothing is written to Turso, and no state persists in the tool's
own storage between calls. The optional recall slice reads the memory store
only through a runner the caller injects — the module itself never opens a
connection.

## Step 1 — Unwire the write-path hook

The gate is invoked from `remembering/scripts/config.py` `set_rule` via
`_run_correction_gate`. To stop it from gating corrections, remove that call
(or make `muninn_utils` unimportable — the hook swallows `ImportError` and
proceeds without gating). The hook is already fail-open: it only ever raises on
a decisive REJECT, never on a gate-internal error.

## Step 2 — Uninstall the code

If installed via the manifest's `runtime.install` (git clone of
`oaustegard/muninn-utilities`, subpath `muninn_utils`), delete the cloned tree,
including `muninn_utils/correction_gate.py` and
`muninn_utils/correction_gate_benchmark.json`.

## Step 3 — (only if the recall slice was used) Stop future reads

The recall slice reads only through an injected `query -> ids` runner. If that
runner was bound to live `recall()`, rotate `TURSO_TOKEN` at
https://app.turso.tech/ to stop reads. Rotate any tools that share the token
first (see the `remembering` skill, `memory_tfidf`, `remind`).

## What this kill switch cannot do

- Cannot retract gate verdicts already returned to a caller — those live in the
  caller's output, not in the tool.
- Cannot un-block a correction the gate already rejected; simply re-propose it
  once corrected, or update the benchmark if the behaviour change is intended.
- Cannot affect the Turso DB contents; this tool never writes to it.
