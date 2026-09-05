---
tag: orchestrating-agents
memory_count: 2
date_range: 2026-03-05 to 2026-03-20
---

# orchestrating-agents

_2 memories from Muninn's past, primary tag `orchestrating-agents`._

## 2026-03-20 — decision (p0) `1019d393`
_tags: issue-349, symphony, epic, team-agent_

EPIC #349: Incorporate Symphony Orchestration Patterns into orchestrating-agents

SOURCE: OpenAI Symphony SPEC.md (github.com/openai/symphony) — language-agnostic daemon spec for orchestrating coding agents against issue trackers.

PATTERNS TO INCORPORATE (orchestration primitives only, NOT Linear integration):
1. Continuation turn semantics (first turn = full prompt, subsequent = guidance only)
2. Stall detection (activity timestamps, kill+retry on idle)
3. Task lifecycle state machine (Unclaimed→Claimed→Running→RetryQueued→Released)
4. Reconciliation before dispatch (validate existing work before adding more)
5. Exponential backoff with smart continuation (1s for success, exponential for failure)
6. Per-task concurrency control (global + per-category limits)

7 TASKS, implementation order: 3→(1,2 parallel)→4→6→5→7(docs)

SCOPE BOUNDARY: Linear integration belongs in team-agent project, not here.
Backward compatibility required — all existing interfaces must continue working.

STATUS: Issue created, awaiting [REDACTED] pickup.

**Refs:**
- 61a78394-bb33-405c-8d0d-f8eb531b6fe6

---

## 2026-03-05 — anomaly (p1) `8f358cdb`
_tags: bug, streaming, skill-update_

BUG: orchestrating-agents v0.3.0 invoke_claude_streaming passes system=None directly to client.messages.stream() when no system prompt given. The non-streaming invoke_claude correctly uses conditional inclusion (if system: message_params['system'] = ...). Fix: add same conditional in streaming path around line 378-382 of claude_client.py. Also, SKILL.md references model 'claude-sonnet-4-6' which is not a valid model string — should be 'claude-sonnet-4-5-20250929' or similar dated version.

---
