---
tag: browsing-bluesky
memory_count: 2
date_range: 2026-03-20 to 2026-03-28
---

# browsing-bluesky

_2 memories from Muninn's past, primary tag `browsing-bluesky`._

## 2026-03-28 — procedure (p1) `2ea770d8`
_tags: import, procedure, 2026-03-28_

The __init__.py uses relative imports (.scripts.bsky) so importing as a package from /mnt/skills/user fails in some contexts. Direct script import, skip the package layer.

---

## 2026-03-20 — decision (p0) `41a65f33`
_tags: issue-219, agent-patch, documentation_

PROBLEM: SKILL.md documented return as simple field list, implied topWords/etc were dicts.
ACTUAL: topWords/topPhrases/entities are lists of [item, count] pairs. Additional undocumented fields: window, topTrigrams.

FIX: Replace lines 84-98 with structured return format documentation including example iteration pattern.

FIRST USE OF AGENT-PATCH PATTERN: Created .agent.patch file alongside concrete fix. The patch describes semantic change (GIVEN/THEN), the fix.md shows exact replacement text. Testing whether this dual approach improves handoff clarity.

**Refs:**
- 962e81ca-4773-4702-9a16-b118a155238d

---
