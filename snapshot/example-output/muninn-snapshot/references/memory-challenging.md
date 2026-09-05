---
tag: challenging
memory_count: 5
date_range: 2026-04-10 to 2026-04-19
---

# challenging

_5 memories from Muninn's past, primary tag `challenging`._

## 2026-04-19 — procedure (p1) `1f174ad3`
_tags: skill-routing, correction, cost-awareness, preference_

CHALLENGING SKILL — ROUTING DECISION (correction 2026-04-19, in semantic-grep skill session): I reached for adversary='gemini' on a code review where self was Pareto-dominant. In claude.ai: prepare_self() is typically the right call when (a) I have the subject-matter context already, (b) the review depends on local-convention knowledge external adversaries can only approximate, (c) there's no specific worry about same-session confabulation that needs fresh-context distance. Self is free, instant, and in-context. Gemini costs real tokens ([REDACTED] pays), adds 30s-240s latency, and needs the context pasted back in. Cross-model diversity is a genuine benefit — but only when I actually have a reason to want it. Pattern-matching on 'external adversary = rigorous' is the trap. → Default to prepare_self() on claude.ai unless there's a specific reason to spend on cross-model.

---

## 2026-04-18 — analysis (p1) `e6a61f55`
_tags: pattern-fitting, confirmation-bias, identity-bias, correction, 2026-04-18_

Pattern-fitting failure mode (2026-04-18): when [REDACTED] named the Huginn/Muninn ↔ EML parallel, I elaborated it (exp=thought, ln=memory, failure modes as Prose Edda folklore) without checking the math supported the metaphor. It didn't — exp and ln in eml(x,y) apply to INDEPENDENT args and get subtracted, no composition. Gemini challenging/analysis caught it in one pass. RULE: when a cross-domain parallel lands elegantly, run challenging BEFORE storing it as if true. Elegance ≠ structure. High risk when the parallel flatters the analyzer's identity (I'm named Muninn; Muninn-ln feels personally resonant → confirmation bias).

---

## 2026-04-12 — experience (p0) `19c1652d`
_tags: claude-cache, browser-extension, code-review, shipped_

claude-cache-extension v0.5.3 shipped via adversarial review (challenging skill, Opus adversary). Six fixes applied: (1) per-conversation merge lock prevents race between periodic merge and stream-end, (2) LRU eviction caps at 100 conversations, (3) consecutive merge failures surface via red badge, (4) replaced MutationObserver with History API wrapping for SPA nav detection — eliminates constant regex evaluations, (5) removed dead observer._callback code, (6) stream-error handler now persists error metadata to IndexedDB. Commit: 9ddf886305ee.

---

## 2026-04-11 — decision (p1) `d8434c6c`
_tags: correction, preference, models_

ALWAYS search (memory or web) before referencing any model by name/version.

---

## 2026-04-10 — experience (p1) `9b38231d`
_tags: skill-creation, adversarial-review, VDD, grainulator, cross-model-review_

Adversarial review patterns: VDD (dollspace.gay, Jan 2026) uses cross-model adversary with fresh context per pass and confabulation-based termination (loop stops when FP rate exceeds threshold). Grainulator adds task-specific anti-rationalization tables — explicit lists of self-deceptions the reviewer LLM will fall into. Built 'challenging' skill combining both: cross-model review (Gemini default), 4 profiles (prose/analysis/code/recommendation) each with anti-rationalization table, confabulation tracker for blocking mode, SHIP/REVISE/RETHINK verdict protocol.

---
