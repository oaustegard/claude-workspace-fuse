# Revoking muninn-verdict

This tool has one write path and two read paths. `store_verdict()` writes a
single `analysis` memory per call. `stale_verdicts()` and `count_verdicts()`
read verdict-tagged memories and one markdown file per profile. Nothing else is
contacted, no state persists between calls, and nothing invokes the tool on its
own — it runs only when a caller asks.

## Step 1 — Stop future writes

`store_verdict()` is the only writer. It is called explicitly; no hook, trigger
or boot path calls it. To stop writes, stop calling it, or make
`muninn_utils.verdict` unimportable. There is nothing to unwire.

## Step 2 — Stop future reads

`stale_verdicts()` and `count_verdicts()` read the store on their default path
only. Passing `memories=[...]` makes them do no store I/O at all, and passing
`root=` (or setting `CHALLENGING_REFERENCES`) redirects the criterion read away
from `/mnt/skills/user/challenging/references`.

## Step 3 — Remove what was already written

Verdicts are ordinary memories tagged `verdict`. To retract them:

```python
from remembering import recall, forget
for m in recall(query="verdict", tags=["verdict"], n=5000):
    forget(m["id"])
```

Check the tag before deleting — `verdict` is a plain tag and a memory written by
hand could carry it.

## Step 4 — Uninstall the code

If installed via the manifest's `runtime.install` (git clone of
`oaustegard/muninn-utilities`, subpath `muninn_utils`), delete the cloned tree,
including `muninn_utils/verdict.py`.

## Step 5 — (only if the default Turso path was used) Rotate the token

Reads and writes use `TURSO_TOKEN`. Rotate at https://app.turso.tech/, but
rotate the tools sharing that token first (the `remembering` skill,
`memory_tfidf`, `remind`, `correction_gate`, `satisfaction_skew`), since they
will need the new token too.

## What this kill switch cannot do

- Cannot un-judge anything. The verdicts came from `challenge()`; this tool only
  recorded them, and removing the records does not retract the review.
- Cannot restore a criterion. `crit-sha` is a hash, not the prose — deleting a
  verdict loses the only note that a particular rubric version was ever applied.
- Cannot affect any decision made on the strength of a staleness report.
