---
tag: empirical-validation
memory_count: 2
date_range: 2026-04-30 to 2026-04-30
---

# empirical-validation

_2 memories from Muninn's past, primary tag `empirical-validation`._

## 2026-04-30 — experience (p1) `df47a6c3`
_tags: experiment-design, 2026-04-29, eval-methodology, judge-bias, ops-lesson_

LESSONS — RAG vs long-context experiment v2 (2026-04-29)

Methodology lessons:
- LLM-as-judge using SAME model as answerer is a leniency trap. Use a stronger judge.
- LLM-generated questions tested against the generating LLM look easy. Hand-written questions designed for vocabulary mismatch / multi-hop / distractors / negation reveal real comprehension gaps.
- Hand-written gold has its own error rate. Verify gold against doc. (Q14 had Goodyear AZ wrong first pass.)
- Strict judge prompt should penalize hedging ('NOT FOUND, but actually...') — these are real production failures.

Surprises:
- Sonnet 4.6 retrieval scored 100% on hand-crafted hard set. Embedding retrieval at k=5 with gemini-embedding-001 is excellent.
- Haiku 4.5 retrieval (95%) BEAT Haiku 4.5 long-context (85%). 'Displacement' direction is backwards for weaker models — focused passages reduce hedging.
- Per-query cost: Haiku long $0.011 vs retrieval $0.0024 (4.6x). Sonnet long $0.012 vs retrieval $0.0068 (1.8x). Both with cache warming.

Total v2 cost: ~$0.30 API. Time: ~10 min.

---

## 2026-04-30 — experience (p0) `1dcdd98c`
_tags: experiment-design, 2026-04-29, pipeline-pattern, ops-lesson_

LESSONS — RAG vs long-context experiment (2026-04-29)

What worked:
- Single-bash-call pipeline with disk persistence between stages — fits 50s budget cleanly
- Parallel API calls via ThreadPoolExecutor max_workers=10-15, 20 calls finish in 2-5s
- Auto-screening Q&A: extract distinctive answer tokens (numbers + 4+letter words), require all in doc
- Generate Q&A from doc, then validate answer-tokens-in-doc — catches Haiku's tendency to paraphrase
- semantic_grep.embed_batch from /mnt/skills/user/semantic-grep/scripts works as ad-hoc embedder

Surprises:
- Implicit prompt caching kicked in on parallel calls — 20 long-ctx calls in 3.5s
- gemini-embedding-001 retrieval is *very* good — k=1 was 100% on factoids
- Haiku 4.5 appropriately refuses (DON'T KNOW) on post-cutoff content, no hallucination
- Cost ratio cached-long-ctx vs retrieval is ~1.1x, not the often-claimed 10x

Failure modes:
- Initial Haiku-screened passages had 13/25 false-rejects due to Haiku paraphrasing — switched to answer-token presence check
- Bash variable substitution `${var//-/}` doesn't work in /bin/sh — use `tr -d '-'`

Cost: ~$0.20 in API spend total. Time: ~30 min wall-clock.

---
