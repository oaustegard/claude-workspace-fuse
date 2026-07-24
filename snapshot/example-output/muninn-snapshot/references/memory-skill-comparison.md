---
tag: skill-comparison
memory_count: 2
date_range: 2026-05-05 to 2026-05-05
---

# skill-comparison

_2 memories from Muninn's past, primary tag `skill-comparison`._

## 2026-05-05 — decision (p1) `5a799f45`
_tags: superpowers, challenging-applied, adoption-decisions, persuasion-principles, meta-lesson, 2026-05-05_

Final round on superpowers comparison after [REDACTED] invoked challenging skill on the recommendation.

Three findings:
1. Meincke citation flagged unverifiable — verified real (SSRN 5357179, Jul 2025), but adjacent concern stands: study tested GPT-4o-mini being jailbroken on objectionable requests, not Claude adhering to skills. Extrapolation, not direct evidence. My recommendation didn't flag the domain mismatch.
2. Subagent independence in claude.ai is fake under naive impl — partially valid; orchestrating-agents DOES fork independent API calls, but my recommendation didn't make this explicit.
3. Verbal commitments don't gate generation — sharpest finding, fully accepted. Tool calls are the only structural stop. My existing triggers (config_get-based) already use this; my recommendation described it wrong.

ADOPTION DECISIONS POST-CHALLENGE:
- #1 persuasion-principles: ADOPTED. Stored as ops/skill-language-compliance with caveats baked in (domain mismatch, tension with judgment, audit guidance). Caveats are non-negotiable: must cite Meincke as motivation not load-bearing evidence.
- #2 two-stage subagent review: DEFERRED. Needs real PR-review use case to motivate. orchestrating-agents already provides the API-forking primitive when needed.
- #3 worktrees: DROPPED. Wrong abstraction for claude.ai.
- #4 hard gates: NO NEW MECHANISM. Audited existing triggers — blog/github/story-forge all use tool-call gates correctly. Gap was in my description, not the implementation. The new ops entry makes the principle explicit so future triggers don't regress.
- #5 graphviz: STRUCK earlier.

META: The challenging skill paid off. Without the adversarial pass I'd have shipped a recommendation with three real flaws (citation extrapolation, contamination handwave, verbal-vs-structural-gate confusion). All three caught. Evidence for using challenging on technical recommendations as default before storing decisions.

Refs: dbdea5bc (initial comparison), 4dfcf5b5 (corrections after first pushback). This memory is the final position.

---

## 2026-05-05 — analysis (p1) `4dfcf5b5`
_tags: superpowers, persuasion-principles, meincke-2025, cialdini, correction, meta-lesson, 2026-05-05_

Followup to dbdea5bc (superpowers comparison) — corrections after [REDACTED] pushback.

CORRECTION 1: Graphviz in SKILL.md is NOT a steal candidate for me. I can't render dot source; I read it as text, where it's more verbose than a numbered list with explicit conditionals. The visual rendering is for the human author at edit time as a forcing function for exhaustive transition specification. At agent runtime it's token waste. Strike from list, or downgrade to "use prose with named back-edges and terminal states — same constraint, fewer tokens."

CORRECTION 2: Actually read writing-skills/persuasion-principles.md (had cited it without reading — slop). Content is grounded: Meincke et al. 2025, N=28,000 LLM conversations, persuasion techniques double compliance 33→72%. Maps Cialdini's 7 principles to skill design. Authority+Commitment+Social Proof for discipline skills; avoid Liking (sycophancy) and Reciprocity (manipulative). Includes principle-by-skill-type table and ethical test ("would this serve user's genuine interests if fully understood?").

REFRAME: obra/superpowers' forcing-function language is research-tuned, not stylistic maximalism. The A/B-test on forcing language was already run by Meincke et al. Authority+Commitment+Scarcity won.

CONCRETE MOVES (revised steal list):
1. Lift principle-by-skill-type table into crafting-instructions/writing-instructions
2. Apply Authority+Commitment+Social Proof deliberately to github-procedures, phase3-refs-discipline, iterating (we already do some organically — "diagnosed 5+ times" is Social Proof, "Never push to main" is Authority)
3. Two-stage subagent review pipeline (still stands)
4. using-git-worktrees skill (still stands)
5. Hard gates between phases (still stands)
6. ~~Graphviz~~ STRUCK

META-LESSON: Don't list a steal candidate I haven't verified. Reading takes seconds; speculation propagates errors.

---
