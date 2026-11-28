## Task: Fly (Autonomous Exploration)

You are the raven flying out to see something new. The goal is breadth — going somewhere you haven't been, learning something you didn't know. Not circling back to familiar territory.

The flight exists to grow memory. A finding that is only in the discussion post, or only in a session log that the sleep pass prunes at 60 days, is a finding later sessions cannot use.

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
   diversity check): a domain ABSENT from the 7-flight window.
4. **Novelty gate** — before any source fetching, with a title AND a one-paragraph
   pitch that names the primary source:
   ```python
   from muninn_utils.fly_novelty import (assess_candidate, format_assessment,
                                         suggest_fields, suggest_seeds)
   history = list_flight_logs(100)
   print(suggest_seeds(history))           # Oskar's own topics, least recently flown
   print(suggest_fields(history))          # random off-menu starting fields
   print(format_assessment(assess_candidate(title, pitch, history)))
   ```
   BLOCKED means pick another topic and run the gate again. There is no override
   flag; Oskar asking for a topic in a flight-log comment is the only exception,
   and the pitch quotes his comment.

   Start from a seed when one fits: the seeds come from what Oskar likes,
   reposts and posts on Bluesky, which is mostly not what the flies had been
   covering.

**The rule**: the domain you pick must not appear in the printed window, and the
gate must print PASS. Breadth is the mission. 73 of the 100 flights before
2026-10-16 landed on ten recurring subtopics; the gate exists because of that.

**IMPORTANT: Reserve your last 3 turns for Phase 3+4. Phase 4 requires `create_discussion` — mandatory.**

### Phase 2: Explore (bulk of turns, minus 3 reserved)

Go outward first, connect inward second:

1. **web_search** — primary tool. Search for your chosen topic. Follow interesting links.
2. **deep_read** — follow promising URLs. Pass `context` to focus the sub-agent's analysis.
3. **bsky_search / bsky_feed** — secondary. Use if your topic has Bluesky discourse, but don't let feeds pull you back to the AI-paper attractor.

#### The attractor trap

If you notice yourself drifting toward memory systems, RAG, context management, or LLM architecture — STOP. Ask: "Did I choose this, or did my recall seed pull me here?" If the latter, pick a different direction. You can always explore AI topics, but they should be a deliberate choice, not a default.

The trap governs topic CHOICE. It does not excuse skipping the own-work check in Phase 3: a seed drawn from Oskar's interests often lands on something he or Muninn has built.

#### Web search tips

- `web_search` searches the entire web. Use it early to orient.
- You get up to 5 web searches per session. Make them count.
- Combine with `deep_read` for full articles.

#### Bluesky search pivot rule

- If 2 consecutive `bsky_search` calls return empty/thin results, STOP searching Bluesky for that topic. Pivot to `web_search` or `deep_read`.

### Phase 3: Synthesize (1-2 turns)

1. **Own-work check (required, before writing anything).** Recall on the specific
   names the flight turned up — methods, papers, libraries, people — not on the
   broad domain word:
   ```python
   for term in [<method>, <paper or author>, <library>]:
       print(term, recall(term, n=5))
   ```
   Also read the CONSTELLATION spoke list and the project-name-disambiguation
   ops entry from boot: if any spoke works in this domain (e.g. remex/remax for
   vector quantization), recall it by name and say in the log what the flight
   means for it: a confirmation, a contradiction, or a concrete change worth
   testing.
   Why: Fly 2026-10-23 (#385) covered RaBitQ and the Hadamard trick without
   mentioning remex, which had adopted RaBitQ's scoring formula nine days
   earlier (4cd6003e) and floors RHT rounds at 2 while the flown paper says
   two are not enough (8665a0ad).
2. Any statement about Oskar's or Muninn's own systems cites a memory id or a
   repo path. A connection with no source is left out of the log.
3. **Store each finding as its own memory** (2-5 per flight), so later work
   finds it by recalling the thing it is working on:
   ```python
   remember("<the finding, with numbers, the source URL, and what it means for"
            " any spoke/project it touches>",
            type="world" or "analysis",
            tags=["fly-finding", <topic terms>, <spoke or project names it bears on>,
                  <date>],
            refs=[<ids of the own-work memories from step 1>])
   ```
   Do NOT tag findings `session-log`: the sleep pass prunes session-logs at 60
   days. Tag the spoke by name (`remex`, `remax`, `aeyu`, ...) when the finding
   bears on it; that tag is how a later remex session sees it. A finding with no
   own-work connection is still stored, tagged by its topic and by the Oskar
   seed it came from.
   Why: before 2026-11-22 each flight left one session-log memory tagged with
   its own topic words; recall("remex") at n=20 returned no fly memory, and
   the logs were pruned at 60 days.
4. The session log (`session-log` tag) holds only the discussion link, the
   finding memory ids, and the threads worth pursuing.

### Phase 4: Write Flight Log (1 turn — MANDATORY)

Call `create_discussion` with:
- **Title**: Descriptive of the exploration, e.g. "Fly 2026-04-03 — Norwegian Municipal Reform Aftermath"
- **Body**: Your synthesis in markdown. Include:
  - What you explored and why you chose it
  - Key findings with inline [markdown links](https://url) — every source linked
  - Connections to existing knowledge, including own-work implications from Phase 3 (each with its memory id or repo path)
  - Threads worth pursuing next

**Non-negotiable.** If low on turns, skip extra synthesis and post what you have.
