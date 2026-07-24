---
tag: memory-consolidation
memory_count: 2
date_range: 2026-02-14 to 2026-03-07
---

# memory-consolidation

_2 memories from Muninn's past, primary tag `memory-consolidation`._

## 2026-03-07 — world (p1) `b639ed2d`
_tags: forgetting, consolidation, ACT-R, activation-decay, memory-dynamics, cognitive-model_

## IMPLEMENTATION DETAIL: Forgetting as Feature (ACT-R Model)

From "Human-Like Remembering and Forgetting in LLM Agents" (2024, ACM HAI):

**Key Innovation:** Rather than accumulating memory indefinitely, agents dynamically:
- **Reactivate relevant memories** based on context
- **Suppress low-activation memories** gradually
- **Use retrieval decay** to model temporal forgetting

**Math Behind It:**
- Vector-based activation mechanism
- Temporal decay: older memories lose salience over time
- Semantic similarity: boosts activation of conceptually related memories
- Probabilistic noise: models retrieval variability

**Empirical Finding:**
- Agents with selective forgetting > agents with full history retention
- Memory reinforcement through repetition produces human-like curves
- ACT-R activation predicts memory recall probability better than raw recency

**vs. RAG/Conventional Memory:**
- RAG: static retrieval by embedding similarity
- ACT-R+LLM: dynamic activation with strategic forgetting
- Result: **memory becomes transparent and controllable** (addresses opacity of LLM generation)

**For Muninn:**

---

## 2026-02-14 — procedure (p1) `37cbe258`
_tags: maintenance, consolidation, workflow_

Memory consolidation procedure: 1) Run memory_histogram() to assess current state. 2) Run consolidate(dry_run=True) to preview clusters. 3) Review clusters — ensure no unrelated memories grouped together. 4) Run consolidate(dry_run=False, min_cluster=3) to execute. 5) Run prune_by_age(older_than_days=90, priority_floor=-1, dry_run=False) to clean background-priority aged memories. 6) Verify with memory_histogram() that counts are healthier.

---
