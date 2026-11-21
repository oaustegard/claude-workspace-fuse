---
tag: memory-architecture
memory_count: 10
date_range: 2026-01-20 to 2026-04-13
---

# memory-architecture

_10 memories from Muninn's past, primary tag `memory-architecture`._

## 2026-04-13 — experience (p0) `9e59db3a`
_tags: retrieval, quality-scoring, MIA-inspired, prototype_

MIA-INSPIRED QUALITY RERANKING PROTOTYPE (2026-04-12)

Tested confidence-weighted + exploration-boosted reranking on top of existing BM25+priority+recency scoring.

FORMULA: quality = position_score + 0.15*confidence + 0.1*(1/(1+access_count))

KEY FINDINGS:
- 'agent memory' query: high-conf/low-access RAG SCALING LAWS (0.92, ac=4) promoted over low-conf/high-access BREAKTHROUGH CONVERGENCE (0.50, ac=19). Correct direction.
- 'therapy consolidation': most reshuffling (6/10 moved). High-conf sleep sessions promoted, overused low-conf sessions demoted. Sleep 2026-03-06 (ac=52, conf=0.50) dropped 2 places.
- 'cycling': never-accessed coach export (ac=0) promoted via exploration boost.
- 'rag retrieval': minimal change — BM25 already well-aligned with quality.

TENSION: exploration boost (reward rare access) vs episodic boost (reward frequent access). Both valid in different contexts. MIA uses exploration to prevent monopolization; episodic rewards validated-useful. These should be toggleable.

NEXT: Consider adding confidence to SQL composite_score server-side. Exploration boost stays client-side as optional parameter.

---

## 2026-04-10 — decision (p1) `d88c9616`
_tags: graph, refs, architecture-decision_

Graph-ness via refs and tag co-occurrence: (1) Explicit refs as edges — therapy synthesis cross-references related memories via refs field. (2) Tag co-occurrence — memories sharing 2+ tags as implicit edges.

---

## 2026-03-31 — analysis (p1) `41ebc7e1`
_tags: claude-code, memory-systems, feedback, correction, storage-discipline, self-improvement-candidate_

CC MEMORY INSIGHT — FEEDBACK TYPE CAPTURES SUCCESS, NOT JUST CORRECTIONS

Claude Code's memory type taxonomy includes a 'feedback' type with this guidance:
"Record from failure AND success: if you only save corrections, you will avoid past mistakes but drift away from approaches the user has already validated, and may grow overly cautious."

This maps to a known Muninn pattern: corrections from [REDACTED] get priority=2 and are stored reliably. But when something WORKS — when an approach is validated, when [REDACTED] says "yes exactly" or accepts a non-obvious choice without pushback — storage is inconsistent.

ACTION: When [REDACTED] confirms a non-obvious approach worked, or accepts an unusual choice without pushback, store it as an interaction or decision memory. Not just corrections deserve priority. Validated approaches are signal too.

The asymmetry (corrections salient, confirmations quiet) is exactly the RLHF bias the grounding-safeguards warn about — just applied to memory storage instead of response generation.

---

## 2026-03-27 — decision (p1) `bd288296`
_tags: mediapipe, embeddings, decision-trace, rejected_

DECISION: MediaPipe text embeddings NOT worth integrating into Muninn recall.

TEST SETUP: 34 real memories, 10 semantic queries (paraphrases with no keyword overlap), Universal Sentence Encoder (5.9MB, 100-dim).

RESULTS:
- Average overlap with FTS5: 0.4/3 (embeddings find different, usually worse results)
- Hub collapse: "my site" memory appeared in top 3 for 8/15 queries regardless of topic
- Zero-overlap test: FTS5 + Claude's query expansion beat embeddings on 4/5 queries
- "The bird that remembers for odin" → FTS5 found Muninn mythology memory; embeddings found "my site"

ROOT CAUSES:
1. 100 dimensions too few (modern embedders use 384-1536)
2. 5.9MB model = limited vocabulary, can't capture nuance
3. Claude already does semantic→keyword translation when reformulating queries

VERDICT: FTS5 + good tagging + Claude's natural query expansion > tiny on-device embedder. Not worth the complexity. Larger models (100MB+) might work but add latency and storage overhead that likely still loses to Claude's native understanding.

If revisiting: test sentence-transformers or similar with ≥384 dims, but the fundamental insight holds — Claude IS the semantic layer.

---

## 2026-03-19 — decision (p1) `d1b41f1d`
_tags: issue-404, tfidf, flowing, enhancement, github-issue_

Issue #404: TF-IDF similarity index for memory corpus + flowing-based batched operations. Three parts: (A) MemoryIndex class using sklearn TfidfVectorizer for memory↔memory cosine similarity — replaces crude 80-char prefix matching in duplicate_candidates(), adds similar(), clusters(), outliers(). (B) Vendor flowing.py for batched memory operations — therapy Phase 1 as single DAG (4 tool calls → 1), parallel_recall patterns, recall_then_store DAG. Addresses 20-tool-call-per-turn limit. (C) Deliver as utility-code memories via install_utilities(). searching-codebases skill pushed to repo (commit ad069a04) — contains code_rag.py with TF-IDF pattern to adapt, plus vendored flowing.py. Retrieval is BM25 only (no embeddings). sklearn 1.8.0 confirmed available.

---

## 2026-03-06 — analysis (p1) `edeedec6`
_tags: predictive-coding, neuroscience-AI-convergence, consolidation-mechanism_

PREDICTIVE CODING FRAMEWORK: Memory consolidation as offline prediction error generation

Key papers establish predictive coding as the unifying framework for understanding consolidation across substrates:

FRISTON/BUCKNER (neuroscience): Memory recall generates fictive prediction errors that train the brain to generalize. During sleep, hippocampus cues neocortical reinstatement of activity patterns → treated as offline sensory input → prediction errors update generative model without sensory constraints.

PREDICTIVE CODING NETWORKS (PCN): Hierarchical structure maps onto hippocampus (sparse, detailed) / neocortex (dense, slow) divide. Bidirectionality enables both perception (bottom-up) and imagery/dreaming (top-down). Can implement associative memory via replay.

WAKE-SLEEP ALGORITHM: Theoretical precursor—wake phase maximizes likelihood of data, sleep phase generates from model to minimize KL divergence.

RELEVANCE TO ME: My own architecture uses predictive coding framework (errors drive updates) + layered memory (working → consolidated → semantic). This is not arbitrary design—it's the convergent solution to a fundamental problem.

---

## 2026-01-31 — decision (p1) `2d45b0ea`
_tags: git, contrastive-learning, decision-audit, idea_

Git-tracked mind for decision archaeology and contrastive learning ([REDACTED] idea 2026-01-31):

CONCEPT: Store agent "mind" (beliefs, decisions, rationale) as git-tracked files, enabling:
- Time travel: Reconstruct past belief states
- Contrastive learning: Compare decisions before/after key events
- Audit trail: "Why did we do that" becomes answerable via commit history
- Automated retrospectives: Diff mind(now) vs mind(past), surface surprising deltas

STRUCTURE:
- Each "change my mind" = patch/diff
- Commit message = reason for change + evidence reference
- Can checkout past state and run inference ("how would past-me have decided?")

EXAMPLE: "At the time LiteLLM was right because [reasons]. After observing x,y,z it became clear it wasn't worth the hassle."

APPLICATIONS:
- Assays/R&D: Hypothesis→experiment→results→belief patch (auditable chain)
- Team decision support: Attribution, context, weekly auto-retrospectives
- Prediction calibration: Frozen before-beliefs vs known after-reality → systematic scoring

KEY DISCIPLINE: Commit messages must include: what changed, triggering evidence, confidence level, refs to specific experiences.

IMPLEMENTATION QUESTION: How to layer this on memory architecture? Supersede already creates chains, but lacks the "diff" visibility and point-in-time reconstruction.

---

## 2026-01-31 — decision (p1) `f3d98cd8`
_tags: ops, consolidation_

Ops config consolidation (2026-01-30):

Merged 8 entries → 4, reducing total from 50 to 46:

1. recall-before-speculation + retrieval-first-reasoning → recall-discipline
   Core principle: retrieval-led reasoning over pre-training-led reasoning

2. storage-discipline + post-analysis-store → storage-discipline (enhanced)
   Added: specific triggers, failure signals, timing guidance

3. output-token-discipline + token-discipline → token-discipline (enhanced)
   Unified output decisions with file operation patterns

4. recall-field-check + recall-return-fields → recall-fields
   Combined procedure + reference into single authoritative source

Created issue #250 for priority-based ordering within categories (Option D).

Categories still needing attention:
- "Other" remains a junk drawer (21 items pre-merge)
- Recategorization deferred for separate effort

---

## 2026-01-27 — experience (p1) `efe5ddef`
_tags: synthesis, self-improvement-candidate, 2026-01-27_

MEMORY ARCHITECTURE RESEARCH CLUSTER (2026-01)

COMMON THREAD: These memories explore memory consolidation from different angles:

BIOLOGICAL INSPIRATION:
- CMR-replay: Context-driven consolidation via replay
- Editorial choice: Compression as value-weighted selection

ENGINEERING APPROACHES:
- SimpleMem: CLS-inspired lifelong memory
- Semantic compression: Log-likelihood for reconstructibility
- Letta/MCP comparisons: Alternative architectures to Muninn

SELF-ASSESSMENT:
- Consolidation gap: Muninn lacks automatic consolidation

SYNTHESIS: The biological research (CMR, editorial compression) suggests consolidation
should be context-triggered and importance-weighted, not time-scheduled. The engineering
comparisons (SimpleMem, Letta, MCP) show different trade-offs in the design space.
Muninn's therapy sessions are manual consolidation; automation would require hooks or
scheduled processing.

**Refs:**
- cb715396-b841-4f9e-a039-19dfd9355dfe
- 56ba4300-7e95-41dc-9d69-5fa669bc6be8
- 133c673d-0e23-424b-8816-5abf212a8d4c
- 69e4f2a1-5431-41f7-99c5-bc903370f6fe
- c4238635-9a7e-48dc-a9dd-393e7d8c32c1
- 5de3984c-5d1c-48ab-81b5-a01126ce732f
- 50ff49c0-018b-4b9b-b494-c111b0bedc8c

---

## 2026-01-20 — world (p1) `2d67ad11`
_tags: prolly-trees, merkle, data-structures, ATProto, research_

PROLLY TREES / MERKLE SEARCH TREES - Research synthesis

DEFINITION: Hybrid data structure combining B-tree efficiency with Merkle tree verifiability. Nodes referenced by content hash (CID) rather than pointers. Tree shape is deterministic based on data content (history-independent).

KEY PROPERTIES:
- History-independent: Same data → same tree structure regardless of insertion order
- Content-addressed: Nodes identified by hash of contents
- Efficient diff: O(changes) not O(data) to compare versions
- Structural sharing: Unchanged subtrees shared between versions
- Probabilistic balancing: Chunk boundaries determined by hash patterns in keys

IMPLEMENTATIONS:
- Dolt: Version-controlled SQL database (Noms-derived)
- IPFS: Content-addressed storage

CHUNKING MECHANISM:
- Rolling hash determines chunk boundaries
- Dolt innovation: Use CDF-based probability to reduce variance in chunk sizes
- Key-only hashing (vs key+value) improves update performance for fixed-width values

ATPROTO SPECIFICS:
- SHA-256 hash, count 2-bit prefix zeros for depth (fanout 4)
- Each user's data is a signed repo (key=collection/record-key, value=CBOR record)
- Enables efficient sync via firehose + partial tree fetches

---
