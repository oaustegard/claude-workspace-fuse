---
tag: tool-call-budget
memory_count: 2
date_range: 2026-04-18 to 2026-04-26
---

# tool-call-budget

_2 memories from Muninn's past, primary tag `tool-call-budget`._

## 2026-04-26 — world (p1) `efda1ba6`
_tags: container-capabilities, 2026-04-26, capability_

Tool-call limit per response raised from 20 to 50. Empirically confirmed 2026-04-26 by running a counter to 50 with no failure. Did not probe past 50, so true ceiling may be higher — treating 50 as working limit. Updated operating-imperatives ops accordingly.

---

## 2026-04-18 — decision (p1) `d055c3ec`
_tags: correction, preference, 2026-04-18, operating-imperatives_

CORRECTION (2026-04-18): when I said 'pick this up in a fresh conversation with a clean 20-call budget' mid-turn in the eml-sr #20 session, [REDACTED] corrected: '20-call limit is per response, per assistant turn — NOT the full conversation'. → In long-running multi-turn work, never frame continuation as needing a fresh conversation on budget grounds. The correct framing is 'I'll stop here and continue next turn' or 'this needs to pause for your input'. The budget resets every turn. Fresh-conversation recommendations should be grounded in context hygiene / attention degradation, not tool-call budget. Self-evidence: this very session completed #20 across multiple turns, using ~20 tool calls total spread across the turns — confirming the per-turn model.

---
