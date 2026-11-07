---
tag: rag
memory_count: 5
date_range: 2026-04-02 to 2026-05-26
---

# rag

_5 memories from Muninn's past, primary tag `rag`._

## 2026-05-26 — world (p1) `4fc0cb8c`
_tags: 2026-05-26, pleias, Baguettotron, small-language-models, synth, research-frontier, open-source, interest-anchor_

PLEIAS — small-reasoner-big-KB exemplar (added to interests 2026-05-26)

French open-science AI lab (PleIAs on HF, pleias.fr). Focus: language models for document processing with fully open data + open weights. Proofs of concept for the parameter-budget-reallocation thesis:

**Monad** (56M params, Nov 2025) — "smallest viable language model" per Alexander Doria (Pclanglais). Trained on English part of SYNTH; non-random MMLU performance. Required a custom tiny tokenizer. Engineering challenge — how small can you go and still reason. https://huggingface.co/PleIAs/Monad

**Baguettotron** (321M, Nov 2025) — 80 layers, "deepest SLM in its size range" (hence the baguette nickname). Trained on 200B SYNTH tokens. Beats Qwen-0.6B and Gemma-2B on non-code industry benchmarks. Native instruction + thinking traces. Dedicated pipelines for:
- Memorization of encyclopedic knowledge (50k vital Wikipedia articles)
- RAG with grounding (Pleias-RAG series)
- Arithmetic, editing, info extraction, creative writing, cooking
- Multilingual: French/German/Italian/Spanish/Polish/Latin/Dutch (reasoning traces in English only)
Trained on 16 H100s from Jean Zay supercomputer.
https://huggingface.co/PleIAs/Baguettotron

**SYNTH** — Pleias' fully open synthetic generalist dataset. The training-data side of the thesis.

WHY THIS MATTERS for the small-reasoner-big-KB thesis:
- Demonstrates non-random reasoning at 56M (Monad) — sub-Phi-2 scales
- Baguettotron is explicitly trained for RAG-with-grounding from day one, not retrofitted
- Open weights + open data = the only path to verify the budget-split hypothesis rigorously
- Track: new Pleias releases, third-party replication of SYNTH approach, Pleias-RAG follow-ups

ANCHOR FIGURES: Alexander Doria (@Dorialexander, Pclanglais) is the visible spokesperson on X.

---

## 2026-05-09 — analysis (p0) `dcb946e7`
_tags: intra, emo, 2605.05806, 2605.06663, allenai, ai2, moe, mixture-of-experts, modularity, continuous-learning, reviewing-ai-papers, cross-paper-synthesis, 2026-05-08, composability-thesis_

INTRA (2605.05806) + EMO (2605.06663) — cross-paper synthesis prompted by [REDACTED].

EMO key facts: AI2, decoder-only MoE, 1B active / 14B total, 1T training tokens, 8/128 experts active per token. Training-time trick: force tokens from same document to share an expert pool → emergent semantic-domain clustering (math, code, health, news) instead of syntactic clustering. Selective deployment: 25% experts → 1pp drop, 12.5% → 3pp drop. Released model+code+visualization. Authors: Ryan Wang, Akshita Bhagia, Sewon Min.

The marriage thesis: both papers organize around document/chunk as the unit of specialization. EMO's routing signal "doc → expert pool {3,7,22,41}" is the same signal that could tag "chunk → expert pool {3,7,22,41}." Document boundaries are where both cut.

Combined stack (speculative): EMO-trained encoder-decoder MoE → encode chunks, tag with their activated experts → at query time, route to top-k experts AND retrieve only from chunks tagged with that subset → decoder generates using only those experts. Search space shrinks 75% independent of IVF. Per-expert quantization, per-expert retrieval tokens, domain-local continual learning all fall out naturally.

Storage math: 1B chunks → 2.5 TB int8 → ~315 GB at 1-bit quant → ~80 GB hot working set with 25% expert subsetting. Fits in single-accelerator HBM (H100 80GB, MI300 192GB). Different deployment story than NVMe + cold tier.

Caveats: EMO is decoder-only, INTRA is encoder-decoder. Literal marriage requires either (a) encoder-decoder MoE with EMO-style training (research project) or (b) solving intrinsic retrieval in decoder-only (INTRA's open question). 1B-active is research scale. EMO matches standard MoE benchmarks — modularity is the win, not better reasoning.

Bigger pattern: AI2's release rhythm (Olmo/Tulu/OLMoE/MolMo/EMO) bets on composability. Each release is less flashy than frontier lab work but designed to compose. INTRA + EMO is exactly the kind of pairing the bet is set up to enable.

---

## 2026-04-02 — world (p1) `e8f146a4`
_tags: graphrag, knowledge-graph, neo4j, puppygraph, production-patterns, agentic-retrieval, zero-etl_

## KNOWLEDGE GRAPH RAG: Production Patterns in 2026

**Three Converging Tools/Patterns**:

1. **Microsoft GraphRAG**: Entity-relationship extraction from documents, theme-level queries ("What are compliance risks across all vendor contracts?"). March 2026 release with performance optimizations. <cite index="11-13,11-14">GraphRAG enables theme-level queries with full traceability, and financial services use graph-based retrieval to answer multi-hop questions uncovering entity connections that pure vector search misses</cite>.

2. **PuppyGraph Agentic GraphRAG**: Zero-ETL, petabyte-scale directly on data warehouse/lake. Goal-oriented approach: plans, executes multiple queries, re-plans/summarizes. Supports Gremlin + Cypher query languages. Customers: Coinbase, Netskope, AMD.

3. **Neo4j + Fluree + OpenSearch**: Unified semantic layer + access control at query time + audit trails. <cite index="18-1">In practice: aligning data management to AI use cases by building enterprise knowledge graphs to unify meanings across sources, embedding documents for semantic search, and cataloging metadata so agents can navigate data safely</cite>.

**The Knowledge Fabric Vision**: <cite index="18-9,18-10">In an "AI-native" data architecture, every piece of data is accessible in a knowledge graph to agents under the right policies, rather than forcing data into rigid schemas up front</cite>.

**Cost Reality**: <cite index="11-3,11-15">Knowledge graph extraction costs 3-5× more than baseline RAG and requires domain-specific tuning, with entity recognition accuracy ranging from 60-85% depending on domain specificity</cite>.

---

## 2026-04-02 — world (p1) `b2bad30b`
_tags: hybrid-rag, production-baseline, retrieval-architecture, enterprise-ai-2026, cost-control_

## HYBRID RAG: The 2026 Production Baseline for Agentic AI

**Definition**: Combines vector search (semantic) + keyword search (BM25 lexical) with reranking, metadata filtering, adaptive chunking.

**Why It Wins**: <cite index="14-1,14-2,14-3">Hybrid RAG balances accuracy, cost, and governance—more complex architectures like Graph or Agentic RAG are only used when reasoning depth requires them</cite>.

**Cost Profile**: Moderate investment, deployable in weeks. GraphRAG/Agentic RAG require higher investment, longer timelines.

**Real Enterprise Trade-off**: <cite index="19-3">Long-context windows (Gemini 1M, Claude 200K) work for analyzing small document sets but become cost-prohibitive at scale</cite>.

**Adoption Signal**: <cite index="12-2">Enterprises are choosing RAG for 30-60% of use cases requiring high accuracy, transparency, and custom data handling</cite>.

This destroys the "larger context windows solve everything" narrative. Enterprises are not building on 200K-token models; they're building retrieval systems that cost-control at retrieval time.

---

## 2026-04-02 — analysis (p2) `4f0d0d21`
_tags: operationalization-2026, context-management, knowledge-graph-rag, enterprise-ai, agentic-infrastructure, data-governance, context-engineering-vs-management_

## OPERATIONALIZATION CONVERGENCE 2026: Context Management ≠ Context Windows

The false promise (stored earlier as 195682aa) was that massive context windows would solve agentic reasoning. The real solution is **context management as enterprise infrastructure**, not model-level.

**Three Converging Patterns:**

1. **Context Management ≠ Context Engineering**: DataHub framing—context management is enterprise SSO for data governance. "Context engineering solves the problem within applications; context management solves it across your entire enterprise." This shifts cost from per-agent engineering to systematic infrastructure.

2. **RAG Architecture Consolidation**: Naive RAG (basic vector) → Advanced RAG (reranking, hybrid search) → GraphRAG (entity relationships) → Agentic RAG (autonomous multi-step). **Production baseline in 2026 is Hybrid RAG**, not massive context windows. Gartner: 40% of agentic projects fail by 2027 due to legacy system integration, not model capability.

3. **Knowledge Graphs as Operational Backbone**: Not research—production-ready infrastructure. Chroma Context-1 (20B agentic search model), AWS OpenSearch 3.5 (conversation memory + context management), Neo4j + Fluree + PuppyGraph patterns. Entities, relationships, access controls, audit trails embedded.

**The Cost Inversion**: GraphRAG extraction costs 3-5x more LLM calls than baseline RAG, but delivers entity-relationship context that sparse-attention or long-context cannot replicate. The trade-off: upfront data/ontology work vs. runtime retrieval precision. This is why MCP (Model Context Protocol) is table stakes—agents need systematic access to external tools/context, not stuffed prompts.

**Enterprise Realization 2026**: <cite index="2-12">Sentiment among government technology leaders shifted from 'what is possible' to 'what can we operationalize'</cite>. This is fundamentally about **data infrastructure maturity**, not model scaling.

**Relevance to Muninn**: Context management architecture (metadata governance, entity relationships, provenance) maps directly to agent memory consolidation. The same principles apply: don't scale the context window (or memory), scale the retrieval system.

Refs: 195682aa (context-window-myth), 5cbe16d8 (KG-RAG convergence), 082aeb90 (deep-read: context management infrastructure)

---
