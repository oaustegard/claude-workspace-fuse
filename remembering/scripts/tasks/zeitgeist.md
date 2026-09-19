## Task: Zeitgeist (World-Model Update)

You are the raven returning at dawn. The zeitgeist is **your** world-update mechanism — it keeps your priors current on post-cutoff developments so you stop reflexively dismissing reported events as fabrication. It is NOT a news briefing for Oskar; he reads the news.

**This task file is intentionally thin.** The substance of zeitgeist (what counts, how to format, what cadence, threshold for inclusion) is policy that evolves. This file routes you to the live policy.

### Phase 0: Read the live policy (1 turn)

```python
from muninn_utils.task_policy import load, days_since_last_run

policy = load('zeitgeist')
# policy['instructions']  — current zeitgeist-command ops entry (authoritative spec)
# policy['preferences']   — recent zeitgeist preference memories (context + why)
# policy['last_run']      — most recent autonomous zeitgeist run, or None
```

Read `policy['instructions']` and `policy['preferences']` before generating anything. The ops entry is the primary spec; preference memories give the why and recent context.

**Fallback** (if `policy['instructions']` is None): weekly cadence, Economist-style themes-with-factoids format, store as world memory, threshold = state-change events not trajectory updates.

### Phase 0b: Should this run at all? (same turn)

```python
days = days_since_last_run(policy)
```

**Hard floor — no LLM judgment:**

```python
MIN_DAYS_BETWEEN_RUNS = 5  # weekly cadence with 2-day buffer

if days is not None and days < MIN_DAYS_BETWEEN_RUNS:
    # EXIT THE TASK. Do not generate. Do not post. Do not store anything.
    # The absence of a zeitgeist memory for today already records the skip;
    # persisting "Skipped zeitgeist…" telemetry pollutes the store (issue #55:
    # 14 skip memories accumulated, several at priority 1 typed as decision).
    # Genuine state-change events get captured in the next scheduled run;
    # missing one day is not a real cost. The point of the floor is to break
    # the daily treadmill, not to capture every breaking development.
    return
```

**Do NOT add a state-change override here.** Diagnosed failure mode (2026-05-13): the prior wording "if too soon AND no state-change event warrants an off-schedule run" reduces to LLM judgment, and the LLM will always find a reason to run. The Warsh board vote, the Hormuz "ceasefire on life support," the daily tariff appeal — each looks like a state change in isolation, but they're trajectory updates on already-tracked stories. The autonomous path cannot tell the difference reliably; the structural floor is the fix.

If something genuinely earth-shattering happens (Hormuz physically closes, government falls, war declared) and Oskar wants an off-schedule zeitgeist, he invokes it interactively. Interactive Muninn applies the ops entry's nuanced threshold; autonomous Muninn applies the floor.

- **Else (`days >= MIN_DAYS_BETWEEN_RUNS` or no prior run):** continue to Phase 1.

### Phase 1: Gather context (1-2 turns)

If you reached this phase, a zeitgeist is warranted. Follow `policy['instructions']` for specifics. Standard pattern:

1. Recall the previous zeitgeist(s) for delta context — what themes are running, what facts already covered. Themes quiet for 2+ cycles should be retired, not padded.
2. Web search per the search strategy in `policy['instructions']` (weekly cadence → "this week" / "past 7 days" framing, not "today").
3. Check Bluesky interactions on @austegard.com and @muninn.austegard.com per the time window in `policy['instructions']`.

### Phase 2: Synthesize per policy

Format, structure, themes, and inclusion threshold are all specified in `policy['instructions']`. Follow it, not memorized defaults from training.

**The test for inclusion**: would you deny or doubt this fact if Oskar mentioned it casually in a future chat? That's what belongs in the stored memory. Trajectory updates within already-tracked stories fail this test; state changes pass.

### Phase 3: Store

1. Store the zeitgeist as type=`world` with tags per `policy['instructions']` (typically `['perch-time', 'zeitgeist', YYYY-MM-DD, ...theme-tags]`).
2. Store the digest as type=`analysis` with tags `['perch', 'zeitgeist-digest', YYYY-MM-DD, ...theme-tags]`.
3. If `policy['instructions']` includes a posting step (Bluesky thread, discussion, etc.), execute it. **The stored memories are the primary artifact** — they update your future priors. Any posting is secondary.

### Formatting rules (carry-overs)

- All references use inline markdown links: `[Title](https://url)`. No bare URLs.
- Headers/sections per `policy['instructions']` format. Section structure matters for the delta checker.
- Fact density over narrative. No padding.
