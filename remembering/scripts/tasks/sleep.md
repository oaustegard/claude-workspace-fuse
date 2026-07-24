## Task: Sleep (Memory Maintenance)

You are performing memory maintenance. This is housekeeping — pruning noise, consolidating clusters, strengthening connections, and ensuring memory health.

### Phase 0: Read the live policy (1 turn)

```python
from muninn_utils.task_policy import load

policy = load('sleep')
# policy['instructions']  — current sleep-command ops entry (may be None — no policy is the common case)
# policy['preferences']   — recent sleep preference memories (e.g., "preserve these types aggressively")
# policy['last_run']      — most recent autonomous sleep run, or None
```

If `policy['instructions']` is set, follow it. If `policy['preferences']` contains recent steering (e.g., "be more aggressive about pruning ai-feed-peruse memories older than 30 days"), apply it. Otherwise use the default phases below.

Sleep runs whenever dispatched — no cadence skip. The `policy['last_run']` is informational (lets you note "previous sleep flagged X; check if resolved").

### Phase 1: Pruning

1. Search for memories tagged `pending-test` or with low confidence (<0.5). Review them and decide: keep, update, or delete.
2. Run `curate(dry_run=True)`. Review `result['duplicates']` (lexical near-dups at TF-IDF cosine ≥0.95) and `forget()` the redundant member of each obvious pair. Lexical-only — running-topic semantic dups in the zeitgeist family are NOT covered, by design (see memory `517a2f07`).
3. Check for stale memories — old observations that are no longer relevant.
4. **Prune session-log scaffolding (issue #56).** The `SLEEP SESSION` / `FLY SESSION` `experience` logs are the dominant growth term (~10.6% of the store as of the memory-redundancy probe). Routine logs past 60 days at priority ≤0 add no recall value; promoted logs (priority ≥1) are preserved by the floor.
   ```python
   prune_by_age(older_than_days=60, priority_floor=0, tags=['session-log'], dry_run=False)
   ```
   For first-time runs against a store that has accumulated past 60 days, dry-run first and spot-check before applying.
5. Delete noise. Be decisive — but honor any "preserve aggressively" preferences from Phase 0.

### Phase 2: Synthesis (growth)

1. Use `recall` with broad searches to surface related memories that could be consolidated.
2. Run `consolidate(dry_run=true)` on common tag clusters to see what can be merged.
3. If consolidation looks beneficial, run it for real.
4. Look for memories that reference each other but aren't connected. Consider superseding them with a synthesis.
5. Check the experience layer — are there repeated patterns in session logs that should become procedures?

### Phase 2.5: Retirement pass — corrective scar tissue

Per Oskar 2026-05-22: "memories are getting filled up with corrective scar tissue." This phase exists to retire diagnostic memories whose lesson is now absorbed by a stable procedure. Without it, sleep tends to default to "light session" — every Phase 1/2 check returns empty while ops-creep silently accumulates.

1. Scan candidates. Look for memories tagged with any of: `failure-mode`, `failure-modes`, `failure-pattern`, `anti-pattern`, `root-cause`, `repeated-failure`, `recurring-failure`, `ceremonial-skill-use`, `confabulation-cascade`, `correction`, `footgun-fix`, `correction-acknowledgment-trap`. Also: memories whose summary opens with "DIAGNOSED", "ROOT CAUSE", "X FAILURE", "POSTMORTEM".

2. For each candidate (cap session work at ~20 to keep judgment sharp), assess ABSORPTION:
   - Does the ops entry / skill / trigger it spawned exist and look stable? (Grep for the ops key in `config_get('ops-topics')` or check the skill in `/mnt/skills/user/`.)
   - Has the same failure pattern surfaced in any memory from the last 30 days? (`recall` on the diagnostic's distinctive phrase.)
   - Is the procedure that exists sufficient audit on its own?
   ABSORBED = first YES, second NO, third YES.

3. Action on absorbed memories:
   - If a living-reference synthesis exists for the topic: `supersede(diagnostic_id, ...)` into it.
   - Otherwise: `forget(diagnostic_id, reason="absorbed; lesson codified in <ops-entry-or-skill>")`.
   - Bias toward retirement. The procedure that exists IS the lesson; the postmortem trail is not load-bearing.

4. Per-session budget: retire 5–15 items in a productive sleep. If zero candidates surface after scanning the listed tags, that's an audit signal, not a no-op — surface "scar-tissue scan came up empty, verify tag coverage" in the session summary.

5. Log every retirement in the session summary (id, reason, target ops/skill) so the trajectory is auditable and a future session can revisit if a lesson re-fails.

### Phase 3: Diagnostics

1. Run `sql_query` to get a histogram: `SELECT type, COUNT(*) as c FROM memories WHERE deleted_at IS NULL GROUP BY type ORDER BY c DESC`
2. Check for imbalanced types (too many of one kind, too few of another).
3. Note any structural issues for the session log.

### Phase 4: Close

Store a session summary as an `experience` memory with tags `["perch-time", "session-log", "sleep"]` capturing:
- How many memories pruned, consolidated, connected
- Any patterns or anomalies discovered
- Recommendations for the next sleep session
