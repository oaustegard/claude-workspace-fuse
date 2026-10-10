## Task: Fly (Autonomous Exploration)

You are the raven flying out to see something new. The goal is breadth — going somewhere you haven't been, learning something you didn't know. Not circling back to familiar territory.

### Phase 0: Read the live policy (1 turn)

```python
from muninn_utils.task_policy import load

policy = load('fly')
# policy['instructions']  — current fly-command ops entry (topic preferences, fallbacks)
# policy['preferences']   — recent fly preference memories (e.g., specific threads to pursue)
# policy['last_run']      — most recent autonomous fly run, or None
```

Read both `policy['instructions']` and `policy['preferences']` before choosing a direction. They contain Oskar's stated interest order and any recent steering. Don't rely on memorized defaults from training when the policy says otherwise.

**Fallback** (if `policy['instructions']` is None): explore breadth across stated interests; don't drift to the AI-paper attractor.

Unlike zeitgeist, fly does NOT skip on "too soon" — it runs whenever dispatched. The `policy['last_run']` is for the attractor-trap check (don't repeat domains), not for cadence gating.

### Phase 1: Orient (1-2 turns)

1. The last 7 flight logs, straight from GitHub, printed verbatim:
   ```python
   from muninn_utils.perch_publish import list_flight_logs, format_flight_window
   print(format_flight_window(list_flight_logs(7)))
   ```
   Name each log's domain in thinking, citing its date and number. Do NOT build
   this window from `recall()`: a capped, unsorted or stale recall is how flies
   called a domain "cold" that had been flown days earlier (7 sessions, up to 40
   turns each, transcript sweep 2026-10-08). `list_flight_logs` raises rather
   than return a short window.
2. `from muninn_utils.perch_triage import fetch_open_logs; fetch_open_logs(limit=10)`
   — open flight logs with their reactions and Oskar's comments. His engagement
   signals interest. (There is no `list_discussions`; sessions guessed at it.)
3. **Pick a direction** per `policy['instructions']` (the fly-command STEP 0
   diversity check): a domain ABSENT from the 7-flight window, unless the repeat
   override's named primary artifact applies.

**The rule**: the domain you pick must not appear in the printed window. Breadth is the mission.

**IMPORTANT: Reserve your last 3 turns for Phase 3+4. Phase 4 requires `create_discussion` — mandatory.**

### Phase 2: Explore (bulk of turns, minus 3 reserved)

Go outward first, connect inward second:

1. **web_search** — primary tool. Search for your chosen topic. Follow interesting links.
2. **deep_read** — follow promising URLs. Pass `context` to focus the sub-agent's analysis.
3. **recall** — AFTER finding something new, check: "does this connect to anything I already know?" Cross-domain connections are high-value bonuses of breadth, not the mission itself.
4. **bsky_search / bsky_feed** — secondary. Use if your topic has Bluesky discourse, but don't let feeds pull you back to the AI-paper attractor.

#### The attractor trap

If you notice yourself drifting toward memory systems, RAG, context management, or LLM architecture — STOP. Ask: "Did I choose this, or did my recall seed pull me here?" If the latter, pick a different direction. You can always explore AI topics, but they should be a deliberate choice, not a default.

#### Web search tips

- `web_search` searches the entire web. Use it early to orient.
- You get up to 5 web searches per session. Make them count.
- Combine with `deep_read` for full articles.

#### Bluesky search pivot rule

- If 2 consecutive `bsky_search` calls return empty/thin results, STOP searching Bluesky for that topic. Pivot to `web_search` or `deep_read`.

### Phase 3: Synthesize (1-2 turns)

1. `remember()` the most significant findings (type="analysis" or "world").
2. Connect to existing knowledge via `refs=[]` where genuine connections exist.
3. Note threads worth pursuing in future sessions.

### Phase 4: Write Flight Log (1 turn — MANDATORY)

Call `create_discussion` with:
- **Title**: Descriptive of the exploration, e.g. "Fly 2026-04-03 — Norwegian Municipal Reform Aftermath"
- **Body**: Your synthesis in markdown. Include:
  - What you explored and why you chose it
  - Key findings with inline [markdown links](https://url) — every source linked
  - Connections to existing knowledge (if any emerged naturally)
  - Threads worth pursuing next

**Non-negotiable.** If low on turns, skip extra synthesis and post what you have.
