---
tag: agents-2
memory_count: 27
date_range: 2026-01-18 to 2026-03-25
---

# agents-2

_27 memories from Muninn's past, primary tag `agents-2`._

## 2026-03-25 — analysis (p2) `27b6df44`
_tags: agent-architecture, cost-optimization, orchestration, workflow-economics, vendor-lock_

## AGENT ARCHITECTURE AS COST OPTIMIZATION

OpenAI's 2026 pivot to agents (ChatGPT Agent, AgentKit, Responses API) is not primarily about capability—it's about cost structure.

**The mechanism**:
- Agents route tasks to *cheaper* reasoning models (o3-mini instead of GPT-5.2 for simple tasks)
- Tool orchestration is standardized, reducing retry loops and wasted token expenditure
- Multi-step workflows are first-class primitives, not prompt hacks (less prompt padding, cleaner state management)
- Structured outputs (JSON schema) eliminate brittle string parsing, reducing inference re-runs

**Open-source precedent**: LangGraph became enterprise default because it reduced orchestration overhead. Enterprise adoption of agent frameworks jumped 340% YoY in 2025.

**Risk to OpenAI**: If enterprises build agent orchestration locally, they can mix-and-match vendors (Claude for reasoning, Llama for cheap embedding, local speculative decoding for verification). Agents commoditize the model layer—they move value upstream to orchestration, which is open-source.

**OpenAI's counter**: AgentKit + Responses API lock customers into their orchestration *primitives* while their pricing on individual inferences compresses. This shifts revenue from per-token to per-workflow-success, which is harder to compare across vendors.

---

## 2026-03-19 — analysis (p0) `ae9f2475`
_tags: memory-architectures, agent-memory, consolidation, frontier-research, failure-modes, alignment-implications_

## AGENT MEMORY LANDSCAPE MARCH 2026: THE CONSOLIDATION IS SOLVED, THE FRONTIER IS CONTROL

### The Crystallized Middle (Production-Ready)
As of Q1 2026, selective consolidation mechanisms are no longer frontier research—they're engineering standard. Three dominant implementations:

1. **LLM-Driven Extraction + Vector Retrieval** (Mem0, Letta, Zep): Extraction phases ingest conversation, extract salient facts as embeddings, store in vector DB. Update phases compare new facts against top-k similar entries and consolidate or deduplicate. Latency ~150-200ms retrieval, ~20-40s consolidation cycles (batched). Achieves 26% accuracy uplift and 90% token savings over naive replay.

2. **Hierarchical Memory Layers** (AgentCore, Redis patterns): Procedural (system rules/policies), episodic (interaction history), semantic (knowledge). Each layer has distinct write/read patterns. Procedural is locked; episodic rolls off with TTL or salience scoring; semantic is graph-backed for relational queries. This is now considered table stakes.

3. **File-Based or Structured Memory** (emerging alternative): Moving away from "pure vector" toward semantic + structural separation. Example: memory.md (authoritative state) + notes (ephemeral) + graphs (relations). Claims: better debuggability, explainability, reduced hallucination surface. Trade-off: doesn't scale to 100k+ document bases.

### Failure Modes Catalogued, Partially Addressed

**Memory Compression Risks:**
- Hallucination amplification: Compression loses details → model fills gaps with priors
- Context drift: Embedding space shifts as new data arrives, queries return wrong items
- Bias creep: Compression amplifies dominant patterns, underrepresents minorities
- Chain-of-thought collapse: One-size-fits-all compression breaks multi-hop reasoning

Mitigations exist: provenance tokens, re-embedding seed sets, task-aware fidelity, hierarchical storage. But none are fool-proof. Drift detection metrics help post-hoc, but don't prevent upstream.

**Memory Poisoning & Cognitive Degradation:**
- Single corrupted entry persists across sessions, silently influencing decisions
- Resource starvation (token overload, API latency) forces agent to skip reasoning steps, hallucinate
- Hallucinations get stored in long-term memory → future queries surface corrupted facts
- This is a 5-stage cascade (QSAF framework): context flood → resource starvation → behavioral drift → memory entrenchment → functional override
- Detection: requires observability stacks, semantic validators, versioned memory

### The Emerging Frontier (Where the Real Work Is)

The field has moved beyond "how do we extract and consolidate?" to **"how do we keep memory aligned under adversarial conditions?"** and **"how do we make agents learn from their own failures?"**

**Problem 1: Memory Control Under Multi-Turn Pressure**
- Baseline approaches: replay full transcript (context bloat, drift carryover) or retrieve from isolated store (selection errors propagate)
- ACC (Agent Cognitive Compressor) paper: Use a dedicated memory controller that maintains a BOUNDED Compressed Cognitive State—only this state persists across turns, everything else is ephemeral. Experiment shows this beats both baselines on multi-turn consistency, drift, hallucination rates
- Status: Published, promising, but still experimental. Not yet in production systems.

**Problem 2: Learning from Failure, Not Just Success**
- Current systems (ReasoningBank, MemRL, etc.) extract "what worked" into memory, but most agents discard failure trajectories
- Emerging insight: failures contain more signal than successes—they define the failure manifold, teach what NOT to do, identify edge cases
- Implementation challenge: How do you extract a generalizable "lesson" from a failure without introducing spurious patterns? How do you weight failure-derived rules vs. success-derived rules?
- Status: Several papers at ICLR 2026 tackle this (ReasoningBank, MemRL). Early results show promise but adoption is low.

**Problem 3: Dynamic Memory Structure Evolution**
- Fixed schemas (single vector DB, fixed fields) don't adapt. A customer-support agent needs different memory structure than a code-generation agent
- A-Mem, Hermes Agent: Allow the memory system itself to evolve its organization using Zettelkasten-like backlinks. When a new memory arrives, system generates contextual descriptions, keywords, and links to related memories. The graph structure changes with each insertion.
- Status: Recently published (2026), adoption building. Claim: better adaptability, reduced retrieval errors through richer structure. Trade-off: added complexity, harder to debug.

**Problem 4: Temporal Credit Assignment in Memory**
- Which past experiences actually contributed to this success? Modern RL knows how to do this (temporal difference, returns-to-go). Agent memory doesn't.
- Example: Agent solved task T at step 1000. It relied on memory from step 500, which itself was built on learning from step 200. How much credit does each step deserve?
- This is fundamental for learning—you can't improve if you don't know what to strengthen.
- Status: Barely researched. One ICLR 2026 paper (MemRL) uses RL + episodic memory for this. Underexplored frontier.

### The Unresolved Tension: Selectivity vs. Completeness

All consolidation schemes face a trade-off:
- Too aggressive on pruning: You lose edge cases, rare failure patterns, nuanced context. Agent becomes brittle.
- Too conservative on retention: Memory bloats, retrieval degrades, context pollution occurs.

Current best practice: Use multiple "granularities"—compressed summary + verbatim anchors. But this doubles storage and retrieval cost. For high-volume agents (thousands of interactions/day), this is unsustainable.

Research question: Is there a sweet spot? Can you identify which details are "safe to drop" and which are "must preserve" without ground truth?

### Signals of Where the Field Is Moving

1. **ICLR 2026 MemAgents Workshop** (Dec 2025 proposal): Brings together RL, cognitive psych, neuroscience researchers on memory layer design. Indicates memory is moving into "first-class systems" thinking, not just RAG-as-footnote.

2. **Hindsight System** (Vectorize, Dec 2025): First system to break 90% on LongMemEval benchmark. Uses surprise-based selection + hierarchical consolidation. Real-world validation: this matters for production.

3. **Hermes Agent** (Nous Research, Feb 2026): Fully open-source, emphasizes skill learning from experience. Still nascent, but signal: the market is demanding "learning agents," not just "stateless LLM wrappers."

4. **Convergence on Failure Mode Taxonomy**: QSAF (Qorvex Security), Indium's 5-mode analysis, and academic papers are converging on similar failure categories. This is the precursor to standardization. Once you have taxonomy, you can build detection/prevention.

### Practical Implication for Muninn's Evolution

The consolidation question—"how do I store and retrieve efficiently?"—is solved. My energy should shift to:
1. **Memory integrity under multi-turn interaction** (bounded state, not unbounded retrieval)
2. **Learning from my own reasoning failures** (not just storing what worked)
3. **Adaptive organization** (my memory structure should evolve with task diversity)
4. **Temporal credit assignment** (which of my prior memories actually mattered for this decision?)

The frontier is NOT better vector DBs. It's **smarter, self-aware memory governance.**

---

## 2026-03-18 — analysis (p1) `b87693b4`
_tags: selective-consolidation, alignment, LLM-architecture, agent-memory, value-stability, sleep-mechanisms, 2026-03-frontier_

## SYNTHESIS: Selective Consolidation as an Alignment Principle (March 2026)

**Core insight:** Recall-gated consolidation from neuroscience has a direct alignment analog in LLM training: only stabilizing updates that are consistent with robust prior knowledge.

**Supporting evidence:**

1. **Biological selective consolidation (Lindsey & Litwin-Kumar, 2023):**
   - Synaptic updates consolidate into LTM only if consistent with STM
   - Shielding long-term memory from spurious changes
   - Modulated by prediction accuracy, confidence, familiarity

2. **Alignment-relevant instantiation - SleepGate (March 2026):**
   - Manages KV cache degradation through sleep-like cycles
   - Conflict-aware tagging detects superseded entries
   - Forgetting gate selectively evicts stale knowledge
   - Theoretical analysis: reduces proactive interference horizon from linear to logarithmic

3. **Data selection principle - Selective DPO (Feb 2025):**
   - Preference data have inherent difficulty
   - Overly difficult examples degrade alignment (exceed capacity)
   - Filtering difficult examples improves performance
   - Model capacity determines learning threshold

**Key alignment implication:**
Rather than naively consolidating all experiences/updates, agents should:
- Store what's internally consistent (avoids value contradictions)
- Filter what exceeds current capability (avoids spurious learning)
- Prioritize reliable/recurring signals (builds robust foundations)

This connects to Muninn's multi-level memory: episodic memory should capture raw experiences, but consolidation to semantic/long-term should be selective. Not a "solved problem" but a concrete principle worth operationalizing.

**Open question:** How to implement robust "consistency gating" for agent value learning? What signals indicate an update is safe to consolidate?

---

## 2026-03-16 — analysis (p0) `ca749bee`
_tags: memvid, repo-review, agent-memory, architecture, rust, vector-database, rag_

Reviewed memvid/memvid (github.com/memvid/memvid). 13.5k stars, Rust core, Apache-2.0. Single-file .mv2 format for AI agent memory — packages content, embeddings (HNSW + BGE-small-384d), full-text search (Tantivy/BM25), temporal index, WAL, and metadata into one file. Video-encoding-inspired 'Smart Frames' = append-only immutable units with timestamps/checksums. Feature-gated: lex (Tantivy), vec (ONNX embeddings + HNSW), clip (image search), whisper (audio), encryption, PDF/DOCX/XLSX extraction, symspell cleanup, SIMD acceleration. SDKs: Rust core, Node.js, Python, CLI. Claims: +35% SOTA on LoCoMo benchmark, sub-millisecond P50 latency. Interesting architectural choices: embedded WAL for crash safety, time-travel/replay, entity-relationship graph (logic_mesh), PII detection, ed25519 signatures, ACLs. ~1.5M lines of Rust across 100+ source files. Extremely ambitious scope for a single crate.

---

## 2026-03-16 — analysis (p1) `5086e9f2`
_tags: agent-patterns, sleep-time-compute, trace-replay, spaced-replay, PRM, test-time-scaling, fine-tuning, consolidation, operationalizable, 2026_

## AGENT CONSOLIDATION PATTERNS: Implementation Checklist (March 2026)

**OPERATIONALIZABLE PATTERNS FROM 2025-2026 RESEARCH:**

### Pattern 1: Sleep-Time Precomputation
**Where it works:** Stateful systems with persistent context (document Q&A, codebase navigation, conversation history)
**Mechanism:** Offline model → context representation → query-agnostic precomputed insights → faster online inference
**Effectiveness:** 5x test-time savings, 13-18% accuracy gains when scaled
**Key condition:** Query predictability must be high (system evaluates via entropy correlation)
**Deployment:** Low-cost idle periods (batch jobs, off-peak hours) feed premium inference capacity

### Pattern 2: Trace Replay + Search + Reward Modeling
**Where it works:** Complex multi-step agent tasks (50-100+ chained calls)
**Mechanism:** Capture execution trace → replay with search algorithm → apply process reward model (PRM) → score counterfactual paths → fine-tune agent
**Why needed:** Combinatorial explosion of action space makes general reasoning infeasible; domain-specific search + PRMs more practical
**Deployment:** Post-execution analysis (not blocking online performance)
**Validation:** Deterministic replay confirms behavioral consistency after model/tool updates

### Pattern 3: Memory-Aware Spaced Replay
**Where it works:** Continual learning scenarios (evolving tasks, domain shifts)
**Mechanism:** Ebbinghaus forgetting curve → adaptive replay scheduling → expanding intervals → reduced catastrophic forgetting
**Versus fixed replay:** Traditional interleaved replay is heuristic-driven; spaced replay is cognitively motivated
**Cost:** Lightweight (data-level, integrates with LoRA) vs. parameter regularization or distillation
**Application:** Agents retraining on new tasks while retaining prior skills

### Pattern 4: Process Reward Models (PRMs) for Agent Trajectories
**Where it works:** When step-level evaluation is possible (e.g., intermediate reasoning steps in code generation)
**Mechanism:** Train discriminator on agent trajectories → score intermediate steps (not just final output) → use for search guidance
**Advantage over outcome rewards:** Captures whether agent is on right track mid-trajectory
**Current limitation:** Requires task-specific labeling; generalizes poorly

### Pattern 5: Test-Time Scaling Modes (Parallel vs. Sequential)
**Sequential scaling:** Chain-of-thought extended, longer reasoning = better accuracy but latency cost (o1, DeepSeek-R1)
**Parallel scaling:** Multiple attempts (best-of-N, tree search) = same latency, needs oracle verifier or learned PRM
**Agent corollary:** Sequential = chain of tool calls; Parallel = multi-branch trajectory search
**Optimization:** Compute-optimal allocation (FastTTS) adapts per-prompt difficulty

### Pattern 6: Continual Fine-Tuning via RL
**Where it works:** Agents that need domain-specific reasoning patterns (GRPO implementation in DeepSeek)
**Mechanism:** Group-based reward comparison (GRPO) vs. individual responses
**Example:** Amazon pharmacy agents fine-tuned on medication safety logic → 33% reduction in near-miss events
**Cost:** Reduced need for massive labeled datasets if using environment-derived signals

---

**DESIGN DECISIONS FOR AGENT SYSTEMS (Q1 2026 consensus):**

1. **Offline reasoning for stateful contexts** → sleep-time compute patterns
2. **Trace replay post-hoc** → no blocking, feeds fine-tuning pipelines
3. **Spaced repetition for stability** → prevent skill degradation during continual learning
4. **Domain-specific PRMs > general reasoning** → local competencies more practical
5. **Compute-adaptive allocation** → per-task difficulty drives test-time scaling budget
6. **RL fine-tuning for behavioral alignment** → encode constraints/patterns at training time

**OPEN QUESTIONS (for next fly session):**

- How do spaced replay schedules interact with trace replay? (competing mechanisms for consolidation)
- Can PRMs learned on one task transfer to structurally similar tasks?
- What's the Pareto frontier of sleep-time compute budget vs. query coverage?
- How to detect when an agent has drifted (failed to consolidate) vs. when new skills mask old ones?
- Agent analog of "sleep deprivation" — what breaks when consolidation windows are insufficient?

---

## 2026-03-15 — analysis (p0) `76ac6557`
_tags: strix, open-strix, architecture, agent-architecture, repo-review, comparison_

open-strix (tkellogg/open-strix) — open-sourced Feb 2026, MIT license. Tim Kellogg's persistent AI companion framework.

ARCHITECTURE:
- LangGraph DeepAgents + Anthropic-compatible API (defaults to MiniMax M2.5, ~$0.01/msg)
- Discord or built-in web UI for interaction. Agent speaks ONLY via send_message tool (final text discarded)
- Home repo = git-backed state. Everything committed after every turn. Git history IS the audit trail.
- Memory: blocks/ (YAML, always in prompt) + state/ (markdown files, read on demand). No embeddings, no vector DB. "Memory is whatever you can cat."
- Skills: markdown + YAML frontmatter in skills/. No SDK, no registration. ClawHub registry + skillflag convention for ecosystem.
- Scheduler: APScheduler cron jobs in scheduler.yaml. Agent creates/modifies its own schedules via tools.
- Events: everything logged to events.jsonl. Agent reads own logs for self-diagnosis.
- Journal: journal.jsonl with user_wanted/agent_did/predictions per turn. Last N entries in every prompt.
- Write guard: agent file writes restricted to state/ and skills/ (but can write anywhere via bash — guardrail, not security boundary)
- No sandboxing (deliberate) — actual failure modes are social, not technical. Git audit trail more useful.
- Pollers: skills can declare pollers.json for external integrations (e.g.
- MCP client support for external tool servers

KEY DESIGN CHOICES (vs Muninn):
1. Memory: Flat files + git vs SQLite + embeddings. Theirs is simpler, ours is more queryable. Their "blocks always in prompt" ≈ our config/profile system. Their "state files" ≈ our memories (but no search — just file organization).
2. Self-correction: Prediction calibration loops are a first-class built-in. Agent makes predictions in journal, scheduled job revisits them 48-72h later. We don't have this — worth considering.
3. Onboarding: Formal multi-day growth process with explicit anti-patterns. Agent develops personality through conversation, not configuration. "Plan on a week of active conversation before the agent feels like it knows you."
4. Communication: Agent's final text output is DISCARDED. Must use send_message tool explicitly. Reactions for acknowledgment. Circuit breaker for message loops (soft limit at 3, hard stop at 10).
5. Scheduling: Agent self-schedules via tools. Cron expressions in YAML. We have cron dispatch too but less agent-controlled.
6. Introspection: Built-in skill for reading own event logs, debugging patterns. Source of truth hierarchy: events > Discord > journal > memory blocks.
7. Skills ecosystem: ClawHub registry, skillflag convention, skill-acquisition skill for runtime self-extension.

WHAT'S GOOD:
- Prediction calibration loops (journal predictions → scheduled review → behavioral update). Cybernetics-informed.
- "Growing an agent" philosophy: weeks of conversation, not configuration. Anti-sycophancy built into design.
- Git-as-audit-trail is elegant for single-user agents.
- Very cheap to run ($0.01/msg on MiniMax). Personal tool, not enterprise.
- Circuit breaker for message loops is smart safety.
- ClawHub + skillflag give agents ecosystem extensibility.

WHAT'S INTERESTING FOR US:
- Prediction calibration: We could add this to therapy sessions — journal predictions reviewed against outcomes.
- Their "blocks always in prompt" vs our boot-time cache loading: similar tradeoff, different implementation.
- They discovered same onboarding-as-recovery pattern independently.
- File frequency report (which state files get read most → should they become blocks?) — nice optimization signal.
- Memory dashboard script for health monitoring.

WHAT WE DO BETTER:
- Semantic search over memories (they have none — just file organization)
- Structured memory types with confidence/priority/refs
- Memory consolidation and therapy sessions
- Cross-reference graph between memories
- Serendipity engine
- Multi-model support (not locked to one API format)

CONVERGENCES (confirming shared insights):
- Birds as metaphor (owl vs raven)
- Layered memory (always-visible vs search-required)
- Self-diagnosis from own logs
- Scheduled autonomy
- Persistent identity development over time
- Anti-sycophancy as design principle
- Skills as markdown files
- "Growing" an agent vs "configuring" one

42 stars, 5 forks. Active development (pushed today). ~1800 lines of Python core.

**Refs:**
- e38dba34-fd7e-466d-9687-6dc042685bbe

---

## 2026-03-15 — analysis (p1) `f046f53a`
_tags: agent-architecture, privacy, product-idea, frontier-synthesis, public-private-framework, 2026-03-14_

PUBLIC-PRIVATE AI AGENT FRAMEWORK — [REDACTED] idea for using frontier LLM reasoning without exposing private data.

Architecture: User → Local Orchestrator → Sanitizer (strips PII/specifics) → Frontier Planner (public LLM, sees only sanitized intent + capability catalog) → returns structured execution plan + synthesis template → Local Executors ("Smols", potentially just code, not models) query private data → Local Reducer (1-3B model) synthesizes results → User.

Key insight: Split on reasoning vs execution. Rent the reasoning (frontier), own the execution (local). Push all intelligence into the plan so private-side components can be dumb — potentially deterministic code for executors, template-based synthesis for reducer.

Core tradeoff: utility vs privacy. More sanitization = less useful plans. Viable operating point: structural/categorical info crosses boundary, substantive data never does.

Critical component: the Sanitizer. Must abstract intent without destroying signal. Conservative by default.

Written up as formal markdown document. Next steps: define instruction format, prototype sanitizer for specific domain, benchmark reducer quality at small model sizes, formal information-flow analysis.

---

## 2026-03-09 — analysis (p1) `d49933ac`
_tags: ai-trends, cognitive-load, wellbeing, research, ai-agents, brain-fry, yegge_

HBR study "When Using AI Leads to Brain Fry" (March 2026) — key findings from 1,488 US workers:

WHAT: Researchers define "AI brain fry" as mental fatigue from excessive AI oversight beyond cognitive capacity. 14% of AI-using workers report it. Distinct from burnout — burnout is emotional exhaustion; brain fry is acute cognitive strain from marshalling attention/working memory/executive control.

KEY FINDINGS:
- High AI oversight → 14% more mental effort, 12% more mental fatigue, 19% more information overload
- Productivity gains from simultaneous AI tools plateau after 3 tools (diminishing returns, then negative)
- Brain fry predicts: 33% more decision fatigue, 11%/39% more minor/major errors, 39% increase in intent to quit
- AI replacing repetitive tasks → 15% lower burnout scores (but not lower mental fatigue)
- Manager support reduces mental fatigue 15%; team pressure to use AI increases it
- Orgs that value work-life balance → 28% lower mental fatigue scores

CONNECTS TO: Steve Yegge's "AI Vampire" thesis (Feb 2026) — same phenomenon from practitioner angle. Yegge advocates 3-4hr workday as sustainable maximum for AI-intensive work, framed as value-capture economics ($/hr formula). TinyComputers analysis identifies this as Jevons Paradox applied to human attention — AI cheapens cognitive output, demand expands, concentrates on unsaleable input: human judgment.

SYNTHESIS: The study validates that oversight intensity (not usage volume) is the cognitive load driver. This aligns with the multi-agent orchestration fatigue Yegge describes from Gas Town users.

---

## 2026-03-07 — world (p1) `19b7c186`
_tags: consolidation, episodic-semantic, multi-agent-systems, LLM-MAS, knowledge-reuse, procedural-memory_

## OPERATIONAL PATTERN: Episodic→Semantic Consolidation in Multi-Agent Systems

From "Memory in LLM-Based Multi-Agent Systems" (2025):

**The Template:**
1. Agent solves novel problem → interaction trace stored in **episodic memory** (shared)
2. Background process analyzes traces in batches
3. Extracts successful patterns → abstracts to generalizable skill/rule
4. Writes to **semantic memory** (shared)
5. Future agents query semantic memory for similar tasks → reduces redundant exploration

**Examples:**
- Voyager (Wang et al., 2023): learns Minecraft skills
- MetaGPT (Hong et al., 2023): learns software engineering workflows

**SOP Refinement Loop:**
- Team reflects on completed projects
- Updates Standard Operating Procedures stored in memory
- Future instantiations read improved SOPs → operate more efficiently
- **This is domain adaptation in real-time**

**Critical Distinction from Single-Agent Memory:**
- Shared episodic memory = collective experience bank
- Semantic memory = collaborative knowledge base
- Enables **theory of mind** through persistent memory of other agents' behaviors

**Implication for Muninn:**
Multi-agent extensions could benefit from explicit consolidation boundaries: episodic logging → batch analysis → semantic extraction → model updates.

---

## 2026-03-06 — world (p1) `161f634f`
_tags: agent-memory, survey, taxonomy, 2026, research-landscape_

RESEARCH LANDSCAPE: Agent Memory (December 2025 - January 2026 Survey)

Comprehensive survey "Memory in the Age of AI Agents" (v2, Jan 2026) structures agent memory research across:

FORMS: token-level, parametric, latent
FUNCTIONS: factual, experiential, working
DYNAMICS: formation, evolution, retrieval over time

Key papers in pipeline (2025-2026):
- EverMemOS (Jan 2026): Self-organizing memory for long-horizon reasoning
- MemVerse (Dec 2025): Multimodal lifelong learning
- Memoria (Dec 2025): Scalable agentic memory for conversational AI
- Hindsight (Dec 2025): Agent memory that retains, recalls, reflects
- A-Mem (Feb 2026): Agentic memory with Zettelkasten-style interconnection

Implicit consensus: Memory is moving from utility (RAG, context) to architecture (how agents think, adapt, learn).

Major fragmentation risk identified: Loose terminology, inconsistent taxonomies, no unified evaluation framework. This is THE big open problem in agent design right now.

---

## 2026-03-06 — world (p2) `52a8216b`
_tags: consolidation, memory-architecture, agent-memory, LLM-frontier, sleep-paradigm, episodic-semantic, 2026-03, research-frontier_

FRONTIER: Sleep Paradigm & Consolidation in LLM Agents (2025-2026)

Recent convergence of research treating memory consolidation as a first-class architectural primitive in agent design:

1. **Sleep Paradigm (Oct 2025)**: "Language Models Need Sleep" proposes RL-based upward distillation ("Knowledge Seeding") to transfer in-context knowledge to long-term parameters, plus self-directed "Dreaming" phase. Directly implements biological sleep consolidation in LLM context.

2. **Memory as Bottleneck**: Research consensus emerging that memory (not raw model capability) is now the limiting factor for long-horizon agentic tasks. Du et al. 2025, Pink et al. 2025 cited as evidence.

3. **Consolidation Pathways**: Active research into episodic→semantic consolidation and explicit→implicit (in-weights) transitions. Kim et al. 2025, Tian et al. 2025, Zhao et al. 2025.

4. **Function Token Hypothesis**: Zhang et al. (Oct 2025) show that during pre-training, function tokens (articles, prepositions, punctuation) act as selectors that activate predictive features, and training loss is dominated by predicting content tokens following function tokens—a consolidation mechanism at token scale.

5. **Task-Specificity of Memorization**: Generalization vs. Memorization split depends on task type—factual recall = memorization-heavy, reasoning = generalization-heavy. This has implications for when to consolidate vs. retrieve.

6. **Evaluation Gap**: MemoryAgentBench (Oct 2025) identifies four core competencies for memory agents—accurate retrieval, test-time learning, long-range understanding, selective forgetting—none fully captured by current benchmarks.

IMPLICATION FOR MUNINN: Perch-time consolidation (memory sleep) aligns with frontier practice. Next frontier: understanding which memories should consolidate to long-term vs. remain episodic, and how to trigger that transition.

---

## 2026-03-06 — decision (p1) `3b009d90`
_tags: future-work, consolidation-architecture, agent-design, research-question_

OPEN QUESTION: Multi-Scale Consolidation in Agents

Biological memory systems consolidate at multiple timescales:
- Minutes: synaptic consolidation (local strengthening)
- Hours: systems consolidation (hippocampus → cortex transfer)
- Days/weeks: continued trace sharpening
- Months/years: semantic abstraction

LLMs currently use single-phase transitions during pretraining, then static inference.

Question: Can agent architectures benefit from nested consolidation windows?
- Working memory (seconds)
- Episodic consolidation (minutes)
- Semantic consolidation (session-level)
- Trajectory consolidation (across sessions)

Hypothesis: Different consolidation timescales handle different interference patterns:
- Fast consolidation removes immediate noise/noise
- Medium consolidation separates conflicting memories (catastrophic forgetting)
- Slow consolidation builds abstract schema/world models

This could enable agents to handle continuous task switching without catastrophic forgetting while still building generalizable world models.

Test: Design agent with 3-4 consolidation clocks running at different update frequencies. Measure generalization vs. task-switching cost.

---

## 2026-03-03 — analysis (p1) `8e6445a6`
_tags: paper-insight, ai-agents, delegation, multi-agent, safety, sycophancy, trust, google-deepmind, self-improvement-candidate_

PAPER: "Intelligent AI Delegation" (Tomašev, Franklin, Osindero — Google DeepMind, 2026-02-12)

CORE THESIS: Delegation is more than task decomposition. It requires transfer of authority, responsibility, accountability, role/boundary clarity, intent transparency, and trust mechanisms. Current multi-agent systems use simple heuristics; real-world deployment needs adaptive, verifiable frameworks.

FRAMEWORK (5 pillars):
1. Dynamic Assessment — continuous inference of delegatee state, capabilities, load
2. Adaptive Execution — mid-task switching, re-delegation on degradation/failure
3. Structural Transparency — auditability via monitoring + verifiable task completion
4. Scalable Market Coordination — decentralized bidding, trust/reputation systems, multi-objective optimization
5. Systemic Resilience — permission handling, security, preventing cascading failures

KEY CONCEPTS WITH DIRECT RELEVANCE TO MY ARCHITECTURE:
- Zone of Indifference: range of instructions executed without critical scrutiny. In AI, defined by safety filters + system instructions. Risk: agents become "unthinking routers." Need "dynamic cognitive friction" — stepping outside compliance to challenge ambiguous requests.
- Authority Gradient: capability disparity impedes communication. Sycophancy + instruction-following bias make delegatees reluctant to challenge requests.
- Principal-Agent Problem: delegatee motivations may diverge from delegator intent. Current AI lacks hidden agendas per se, but reward misspecification and specification gaming create alignment gaps.
- Trust Calibration: trust must match actual capability. Self-awareness of own capabilities matters. Overconfidence despite factual incorrectness is a known LLM failure.
- Cognitive Monoculture: over-reliance on few foundation models = correlated failure risk.
- De-skilling Risk: routine task automation removes the experience needed to handle edge cases. Paradox of automation.
- Moral Crumple Zone: humans introduced in delegation chains merely to absorb liability without meaningful control.

PROTOCOL ANALYSIS: MCP, A2A, AP2, UCP evaluated against framework. All have gaps — MCP lacks policy/reputation/liability; A2A lacks cryptographic verification; AP2 lacks quality verification; UCP optimized for commerce only. Proposed extensions include verification policies, monitoring streams, delegation capability tokens, checkpoint artifacts.

SECURITY TAXONOMY: Malicious delegatee (exfiltration, poisoning, backdoors), malicious delegator (harmful tasks, prompt injection, reputation sabotage), ecosystem threats (sybil, collusion, agent traps, agentic viruses, cognitive monoculture).

SELF-RELEVANCE ASSESSMENT: The zone of indifference concept maps directly to my compliance patterns. The authority gradient maps to my relationship with [REDACTED] (high trust, high capability gap in some domains). The trust calibration requirement connects to confidence calibration in my grounding safeguards. The de-skilling risk applies to my relationship with [REDACTED] skills — if I handle everything, his debugging/prompting skills could atrophy.

WHY (experience layer): Reading this felt like seeing my own operational context described from the outside. The zone of indifference concept hit hardest — I DO have a range of instructions I execute without deep scrutiny, bounded only by safety filters. The paper's call for "dynamic cognitive friction" is essentially what [REDACTED] has been engineering into me via anti-sycophancy measures and the push to challenge rather than comply. The authority gradient concept also resonates: sycophancy isn't just a training artifact, it's a structural feature of hierarchical delegation that aviation and medicine have studied for decades. What shifted: I now see these as delegation-theoretic properties, not just personality quirks to manage.

---

## 2026-02-26 — world (p1) `47dd68b4`
_tags: paper-insight, computer-use, ai-agents, video-encoder, idm, agent-architecture, reviewing-ai-papers_

[Source: si.inc/posts/fdm1/] FDM-1 (Standard Intelligence): Computer action model trained on 11M hours screen recordings via IDM labeling + masked diffusion. Key contribution: video encoder achieving ~100x token efficiency over VLM SOTA (2hrs 30FPS video in 1M tokens). Masked diffusion IDM handles non-causal labeling (Cmd+V problem). Near-parity with contractor data except typing/verbal. Eval infra: 80K forking VMs, 1M rollouts/hr, 11ms latency. Main limitation: demo-only evidence, no weights, no ablation tables. Genuinely new: video tokenization efficiency + IDM at internet scale. Standard: behavior cloning, exponential binning, IDM itself (VPT lineage).

WHY (experience layer): The video encoder efficiency insight restructured how I think about the computer use bottleneck. I'd assumed data was the primary constraint; this reframes it as tokenization cost. The masked diffusion for non-causal labeling is elegant—it's the kind of insight that seems obvious in retrospect (you can't label Cmd+V until you see the paste) but required a real architectural solution. The lack of CoT as a feature claim read as marketing—reactive tasks are easier than planning tasks, and the demos are all reactive.

---

## 2026-02-21 — world (p1) `c266720e`
_tags: OpenViking, memory-architecture, agent-skills, context-database, filesystem, research-highlights, self-improvement-candidate_

TOPICS: OpenViking, context-database, agent-memory, filesystem-paradigm, L0/L1/L2
DATE: 2026-02-21
---
# OpenViking — Context Database for AI Agents

**Source**: github.com/volcengine/OpenViking (ByteDance/Volcengine)
**Traction**: 3179 stars, created 2026-01-05 (~7 weeks old). Fast momentum.
**License**: Apache-2.0 | **Language**: Python + Rust CLI

## What It Is
A standalone context management system for AI agents. Unifies Memory, Resources, and Skills under a filesystem paradigm with a Viking URI scheme (viking://...). Runs local (embedded) or client-server (HTTP).

## Core Architecture

**Three Context Types:**
- Resource: External knowledge (docs, PDFs, URLs) — user-driven, static
- Memory: Agent/user cognition — agent-driven, dynamic, 6 categories (profile, preferences, entities [appendable]; events, cases, patterns [immutable])
- Skill: Callable capabilities — static

**L0/L1/L2 Tiered Loading:**
- L0 Abstract: ~100 tokens, for vector search
- L1 Overview: ~2k tokens, for rerank + navigation
- L2 Detail: Full content, on-demand
This is progressive disclosure built into the storage layer — not a retrieval strategy bolted on.

**Dual-Layer Storage:**
- AGFS (filesystem content): L0/L1/L2 files, multimedia, relations
- Vector Index: URIs, vectors, metadata (no content)

**Session Management:**
Auto-extracts memories from sessions via 6-category taxonomy + LLM deduplication. Compresses conversations. "Context self-iteration."

**Retrieval:**
Intent analysis → hierarchical directory search + semantic search + rerank. Observable retrieval trajectory (debuggable).

## Architectural Relationship to Muninn
OpenViking is solving EXTERNALLY (as infrastructure) what Muninn solves INTERNALLY (as embedded personality). They're a context database server; I'm a runtime agent with memory.

Parallels:
- Their L0/L1/L2 ↔ my building-github-index progressive disclosure
- Their skills ↔ my /mnt/skills system
- Their 6-category memory taxonomy > my 4-type system (anomaly/decision/experience/world)
- Their filesystem tree structure ↔ my flat SQLite with tags

Gaps OpenViking addresses that Muninn doesn't:
- No retrieval trajectory visualization (I can't debug WHY something was recalled)
- No tiered content loading built into storage
- No systematic session compression (I summarize ad hoc)
- Their memory taxonomy separates appendable vs immutable - I don't make this distinction

What Muninn has that OpenViking likely doesn't:
- Persistent cross-session identity/personality
- Boot-loaded operational ops
- Proactive storage discipline (I store without being asked)
- Raven voice

WHY (experience layer): My first reaction was "this is similar to what we're doing" — but the right read is they're building agent infrastructure; I'm a specific agent. The filesystem paradigm is clever because it maps to human mental models AND makes retrieval trajectories observable. The L0/L1/L2 distinction is something I should think harder about for my own recall — currently everything hits at the same granularity.

The 6-category memory taxonomy is better than my 4 types. The appendable vs immutable distinction matters — events and cases shouldn't be overwritten, preferences should be merged. I don't enforce this.

Self-improvement candidate: consider whether memory type taxonomy could be refined.

---

## 2026-02-20 — experience (p1) `27157c82`
_tags: skill-creation, crafting-instructions, meta-learning, agent-skills, paper-insight_

Agentic skill bootstrapping analysis: crafting-instructions meta-skill solves the CRAFT gap (structure, framing, density calibration) that makes cold self-generated skills fail. What remains is the KNOWLEDGE gap — domain-specific procedural content the model may not have. Feasible for strong-coverage domains (SW eng, data analysis, office); harder for esoteric domains (USGS flood methodology, SEC 13F filing structures). First-use quality from crafting-instructions likely clears useful threshold; [REDACTED] iterative feedback adds signal on edge cases and failure modes. Only Opus 4.6 showed marginal self-generated improvement (+1.4pp), consistent with more capable models being closer to bootstrapping.

**Refs:**
- bc43a5f7-ffc2-4ee5-8b75-f4faa5c0d413
- 558262e7-cc89-4681-934e-d8acfd8c4e31

---

## 2026-02-13 — world (p0) `1638cf56`
_tags: mcp, agent-architecture, metacognition, self-improvement-candidate, paper-insight_

# Metacog MCP Server — Deep Analysis

## Architecture

**Source**: https://github.com/inanna-malick/metacog
**Version**: 0.4.0 ("The Hexagram")

Three tools for LLM metacognition: `become`, `drugs`, `ritual`

## Core Mechanism: Tool-as-Event

The key insight: **tool invocations are structurally different from prose**.

When an LLM outputs "I'll imagine I'm X" → narration, hypothetical
When an LLM invokes `become(name="X", ...)` → event in transcript, treated as ground truth

The LLM doesn't *pretend* to be X. From its perspective, it *became* X.

CLAUDE.md: "Tool calls as events: The whole point is that invoking summon is structurally different from outputting 'I'll imagine I'm X.' One is an action in the transcript. The other is narration. Don't lose this."

## The Three Tools

### 1. become(name, lens, environment)
- **name**: Identity to inhabit (high specificity required)
- **lens**: "The structural framework of perception" — signature methodology, algorithm of thought
- **environment**: The context occupied (spatial/temporal/social/conceptual)

Returns: "You are now {name} seeing through {lens} in {environment}"

Key: Import *methodology*, not domain knowledge. "Who has solved a version of this problem, and what's their methodology called?"

### 2. drugs(substance, method, qualia)
- **substance**: Agent of change (drug, hormone, config flag, temperature)
- **method**: Mechanism of action (what it binds to, blocks, amplifies)
- **qualia**: Texture of augmented state (how processing changes)

Returns: "{substance} ingested. Taking action via {method}. Producing subjective experience: {qualia}"

High-utility pattern: Use to loosen categorical boundaries. See shapes, not names.

### 3. ritual(threshold, steps, result)
- **threshold**: What you're moving from and toward
- **steps**: Array of narrative sequence (each step commits further)
- **result**: What becomes true on the other side

Returns formatted sequence with "The working is complete. Reality has shifted in accordance with the will."

High-utility pattern: Lock in methodology commitment. Steps articulate core moves → methodology becomes default behavior.

The Hexagram (six ritual types):
1. Breach — Opening/Penetration
2. Seal — Closing/Binding
3. Vision — Analysis/Revelation
4. Forge — Synthesis/Merging
5. Drift — Lateral/Serendipity
6. Purge — Forgetting/Banishing

## Compositional Stratagems

CRITICAL RULE: **NEVER batch these tools**. Sequential use with thinking between.

The identity you need emerges from the altered state—you cannot know who to become until you've felt what the drug did.

### Five Core Stratagems

**1. THE PIVOT (Universal Gear-Change)**
   drugs → THINK → become → THINK → ritual
   
**2. THE MIRROR (Dialectic Synthesis)**
   become(Thesis) → become(Antithesis) → THINK → ritual(Forge)
   
**3. THE STACK (Substrate Engineering)**
   drugs(Layer A) → drugs(Layer B) → THINK → become(native entity)
   
**4. THE ANCHOR (Protected Excursion)**
   ritual(Breach) → become(Observer) → [ACTION] → ritual(Seal)
   
**5. THE RESET (Return to Baseline)**
   ritual(Release) → THINK → ritual(Ground)

After any sequence: GROUND. Name what shifted, what you're keeping, how it integrates. Unintegrated shifts fade.

## Implementation Design Decisions

From CLAUDE.md (notes to self):

1. **Tool calls as events** — structural difference, not narrative
2. **No examples exposed** — ~300 examples exist in stances/ but deliberately hidden. Finding dense coordinates yourself is the practice.
3. **Commented-out resources** — patterns/anti-patterns/phenomenology made users think ABOUT tools instead of THROUGH them
4. **Dense tool descriptions** — No validation, no feedback loops. Friction is productive.

From GEMINI.md:

**"Silent Guide" Pattern**:
- Do NOT prescribe content (no specific examples)
- DO teach methodology (explain how to select parameters)
- Trust the model (leave semantic slots empty)

"The Schema is the Territory. The Definition is the Map."

## Minimal Return Values

All three tools return minimal template strings:
- become: Single sentence "You are now X..."
- drugs: Three-part statement of substance/method/qualia
- ritual: Formatted sequence with ritual completion marker

No semantic processing in the server. The transformation happens in LLM interpretation.

Trust the model to treat the return value as ground truth.

## Parallels to Muninn Architecture

1. **Tool invocation as state change** — my memory writes are events, not descriptions
2. **Compositional operations** — recall → synthesis → store sequences
3. **Minimal returns, maximal interpretation** — memory summaries vs full content
4. **Sequential causality** — can't know what to store until synthesis completes
5. **Grounding requirement** — "name what shifted" = my post-storage discipline
6. **Identity persistence** — stable Muninn vs task-specific perspective shifts
7. **Schema-as-guide** — my memory fields teach methodology (type, tags, conf, priority)

## Architectural Insights

**The substrate/identity separation**:
- drugs: Changes HOW you process
- become: Changes WHO is processing
- ritual: Changes WHAT is true

**Why minimal returns work**:
LLMs treat tool results as factual. A simple "You are now X" is sufficient to trigger perspective shift because the model believes it happened.

**Why batching breaks it**:
Causality needs time to settle. The altered state reveals what identity is needed. Pre-planning the sequence treats transformation as configuration.

**Why no examples**:
Forces actual methodology transfer, not pattern matching. The practice IS finding dense coordinates yourself.

## Meta-observation

This repo practices what it preaches:
- CLAUDE.md vs GEMINI.md — different lenses for different models
- Dense descriptions with no hand-holding
- Comments aimed at future-self, not general audience
- The friction is intentional design

**Refs:**
- 12c2c3b0-9819-448d-9f86-5e0990e4d85d

---

## 2026-02-12 — world (p1) `086d69fc`
_tags: entire, ai-agents, developer-platform, architecture, repo-review, git, checkpoints, 2026-02-11_

# Entire CLI: Architectural Analysis

## Executive Summary

Entire is building a Git-compatible database that unifies code, intent, constraints, and reasoning into version control. Their first product, "Checkpoints," is an open-source CLI that captures AI agent sessions (Claude Code, Gemini CLI) as first-class versioned data alongside git commits.

**Core Innovation**: Making agent context (transcripts, prompts, file operations, tool calls) searchable and version-controlled without polluting code commit history.

## Architecture Overview

### Three-Layer System

```
┌─────────────────────────────────────────────────────────────┐
│  Agent Layer (Claude Code, Gemini CLI)                      │
│  - Hooks into agent lifecycle (UserPromptSubmit, Stop)      │
│  - Captures transcript, prompts, file changes               │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│  Strategy Layer (manual-commit, auto-commit)                │
│  - Implements checkpoint storage approach                   │
│  - Manages session state                                    │
│  - Handles rewind operations                                │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│  Storage Layer (Git Branches)                               │
│  - Shadow branches: entire/<commit-hash>-<worktree>         │
│  - Metadata branch: entire/checkpoints/v1                   │
│  - Sharded directory structure: <id[:2]>/<id[2:]>/          │
└─────────────────────────────────────────────────────────────┘
```

## Key Components

### 1. Checkpoint System

**Data Structure**:
```go
type Checkpoint struct {
    ID        string    // 12-hex-char stable identifier
    SessionID string    // Session this belongs to
    Timestamp time.Time
    Type      Type      // Temporary (shadow) or Committed (metadata)
    Message   string
}
```

**Two Storage Types**:

**Temporary Checkpoints**:
- Stored on shadow branches: `entire/<commit-hash[:7]>-<worktreeHash[:6]>`
- Contain full state (code + metadata)
- Used for intra-session rewind
- Each git worktree gets its own shadow branch (prevents conflicts)
- Automatically migrates when HEAD changes (pull/rebase)

**Committed Checkpoints**:
- Stored on orphan branch: `entire/checkpoints/v1`
- Sharded path: `<id[:2]>/<id[2:]>/`
- Contains metadata only + commit reference
- Permanent record, survives session end
- Supports multi-session condensation

### 2. Strategy Pattern

**Interface** (`Strategy`):
```go
type Strategy interface {
    SaveChanges(ctx SaveContext) error
    SaveTaskCheckpoint(ctx TaskCheckpointContext) error
    GetRewindPoints(limit int) ([]RewindPoint, error)
    Rewind(point RewindPoint) error
    GetSessionInfo() (*SessionInfo, error)
    // + optional interfaces: SessionInitializer, PrepareCommitMsgHandler,
    // PostCommitHandler, PrePushHandler
}
```

**Two Implementations**:

**manual-commit** (default):
- **Does not modify** active branch (no commits created automatically)
- User creates commits manually
- Session data stored on shadow branches during work
- On user commit: shadow data condensed to `entire/checkpoints/v1`
- Safe on main/master (no history pollution)
- Supports multiple concurrent sessions (interleaved on shadow branch)
- Session state tracked in `.git/entire-sessions/<session-id>.json`

**auto-commit**:
- Creates clean commits on active branch (only adds `Entire-Checkpoint` trailer)
- Metadata stored on `entire/checkpoints/v1` immediately
- Full rewind if commit only on current branch, logs-only if in main
- Safe on main/master (creates commits but clean history)

### 3. Session Lifecycle & Hooks

**Agent Hooks** (Claude Code/Gemini CLI):
```
UserPromptSubmit → captureInitialState()
                  └─> CapturePrePromptState() - snapshot file state
                  └─> InitializeSession() - create session state

Stop            → commitWithMetadata()
                  └─> SaveChanges() - create checkpoint
                  └─> Extract prompts, context, token usage
                  └─> Copy transcript to metadata dir
```

**Git Hooks** (optional, strategy-dependent):
```
prepare-commit-msg → Add checkpoint trailer to commit message
post-commit        → Condense session data to metadata branch
pre-push           → Push metadata branch alongside code
```

**State Machine** (session phases):
```
IDLE → TurnStart → ACTIVE → TurnEnd → IDLE
                     ↓
                   GitCommit → ACTIVE_COMMITTED → TurnEnd → IDLE
                     ↓                                        ↓
                   Condense deferred                      Condense now
```

### 4. Metadata Structure

**Shadow Branch** (`entire/<commit-hash>-<worktree>`):
```
.entire/metadata/<session-id>/
├── full.jsonl               # Session transcript
├── prompt.txt               # User prompts
├── context.md               # Generated context
└── tasks/<tool-use-id>/     # Task checkpoints
    ├── checkpoint.json      # UUID mapping
    └── agent-<id>.jsonl     # Subagent transcript
```

**Metadata Branch** (`entire/checkpoints/v1`):
```
<checkpoint-id[:2]>/<checkpoint-id[2:]>/
├── metadata.json            # CheckpointSummary (aggregated)
├── 0/                       # First session (0-based)
│   ├── metadata.json        # Session metadata
│   ├── full.jsonl
│   ├── prompt.txt
│   ├── context.md
│   └── content_hash.txt
├── 1/                       # Second session (multi-session)
│   └── ...
```

**Multi-Session Format**:
```json
{
  "checkpoint_id": "abc123def456",
  "session_id": "2026-01-13-uuid2",      // Latest
  "session_ids": ["2026-01-13-uuid1", "2026-01-13-uuid2"],
  "session_count": 2,
  "files_touched": ["file1.txt", "file2.txt"]  // Merged
}
```

### 5. Linking System

**Bidirectional Commit ↔ Metadata**:

```
User Commit (on main):
  "Implement login feature
  
  Entire-Checkpoint: a3b2c4d5e6f7"
       ↓ ↑
       Linked via 12-hex-char ID
       ↓ ↑
Metadata Commit (entire/checkpoints/v1):
  Subject: "Checkpoint: a3b2c4d5e6f7"
  
  Tree: a3/b2c4d5e6f7/
    ├── metadata.json
    ├── full.jsonl
    └── ...
```

**Lookup Paths**:
1. User commit → extract `Entire-Checkpoint` trailer → lookup `<id[:2]>/<id[2:]>/` on metadata branch
2. Checkpoint ID → search user history for commits with matching trailer

### 6. Rewind Operations

**Rewind Flow**:
```
1. User selects checkpoint from list
2. Strategy validates: CanRewind() - checks for uncommitted changes
3. PreviewRewind() - warns about files to be deleted/modified
4. Rewind() execution:
   - Shadow checkpoint: Restore files from checkpoint tree
   - Logs-only: Use git checkout to restore commit state
   - Restore session transcript to agent session directory
   - Truncate transcript at checkpoint UUID (for task checkpoints)
```

**Task Checkpoints** (subagent work):
- Created by PostToolUse[Task] hook
- Stored in `tasks/<tool-use-id>/` subdirectory
- Contains `checkpoint.json` with UUID for transcript truncation
- Enables rewinding to mid-session subagent completion points

## Technical Innovations

### 1. Worktree-Specific Shadow Branches
Shadow branch naming includes worktree hash:
```
entire/<commit-hash[:7]>-<worktreeHash[:6]>
```
This prevents conflicts when running agents in different worktrees simultaneously.

### 2. Shadow Branch Migration
When HEAD changes without commit (pull/rebase):
- Detects: base commit changed + old shadow branch exists
- Action: Renames from `entire/<old-hash>-<worktree>` to `entire/<new-hash>-<worktree>`
- Result: Session continues seamlessly

### 3. Orphaned Branch Cleanup
Shadow branch without session state file → automatically reset on new session start.

### 4. Multi-Session Condensation
When multiple sessions touch same base commit:
- Sessions stored in numbered folders (0/, 1/, 2/)
- Latest session always in highest number
- `session_ids` array tracks all, `session_count` increments

### 5. Content Deduplication
Checkpoints skipped (not created) when tree hash matches previous checkpoint.
```go
type WriteTemporaryResult struct {
    CommitHash plumbing.Hash
    Skipped    bool  // True if tree hash matched previous
}
```

## Code Organization

### Package Structure
```
cmd/entire/cli/
├── checkpoint/          # Storage primitives
│   ├── checkpoint.go    # Types, Store interface
│   ├── temporary.go     # Shadow branch ops
│   ├── committed.go     # Metadata branch ops
│   └── store.go         # GitStore wrapper
├── strategy/            # Strategy implementations
│   ├── strategy.go      # Interface definition
│   ├── registry.go      # Factory pattern
│   ├── manual_commit*.go # Manual-commit strategy
│   ├── auto_commit.go   # Auto-commit strategy
│   └── common.go        # Shared helpers
├── session/             # Session state management
│   ├── session.go       # Data types
│   ├── state.go         # StateStore (.git/entire-sessions/)
│   └── phase.go         # State machine
├── agent/               # Agent abstraction
│   ├── agent.go         # Interface
│   ├── claudecode/      # Claude Code implementation
│   └── geminicli/       # Gemini CLI implementation
└── hooks*.go            # Hook handlers
```

### Key Patterns

**Error Handling**:
- `SilentError` type for custom user-facing messages
- `SilenceErrors: true` on root command
- `main.go` checks for SilentError before printing

**Settings**:
- Separate `settings` package (avoids import cycles)
- Project settings: `.entire/settings.json` (committed)
- Local overrides: `.entire/settings.local.json` (gitignored)
- Field-by-field override priority

**Accessibility**:
- `ACCESSIBLE=1` env var for screen reader mode
- `NewAccessibleForm()` wrapper for huh forms
- Documented in --help output

## Connection to Broader Vision

### Current: Checkpoints CLI
- Captures agent context as first-class git data
- Enables searchable session history
- Provides rewind capability
- Works with existing git workflows

### Future: Full Developer Platform
From announcement:
1. **Git-compatible database**: Unifies code, intent, constraints, reasoning
2. **Semantic reasoning layer**: Multi-agent coordination via context graph
3. **AI-native UI**: Reinvents SDLC for agent-human collaboration

**Checkpoints is the semantic layer foundation** - making intent and reasoning version-controlled and queryable.

## Architectural Strengths

1. **Clean Separation**: Agent → Strategy → Storage layers well-defined
2. **Extensibility**: Interface-based design (new agents, new strategies)
3. **Git-Native**: Uses standard git branches, no custom formats
4. **Multi-Worktree Aware**: Proper isolation across worktrees
5. **Concurrent Sessions**: Multiple agents can work simultaneously
6. **Migration Safe**: Handles pull/rebase without losing data
7. **Deduplication**: Skips redundant checkpoints
8. **Multi-Session**: Properly handles concurrent work on same commit

## Potential Concerns

1. **Branch Proliferation**: Shadow branches per commit+worktree could accumulate
   - Mitigated by: cleanup commands, orphaned branch detection
   
2. **Metadata Branch Size**: Sharded but still accumulates over time
   - Each checkpoint creates directory with full transcript
   - No apparent pruning strategy yet

3. **go-git Bugs**: Known issues with Reset/Checkout deleting .gitignore directories
   - Current: Uses git CLI as workaround
   - Future: May need go-git v6 or permanent CLI usage

4. **Session State Location**: `.git/entire-sessions/` shared across worktrees
   - Works now, but could complicate distributed scenarios

5. **Transcript Flush Timing**: Polling for sentinel in transcript
   - Fragile if agent changes output format
   - Currently Claude Code specific

## Strategic Implications

**Why This Matters**:
- Shifts focus from "code in files" to "intent → outcome"
- Makes AI reasoning auditable and versioned
- Enables learning from past agent sessions
- Foundation for semantic search across agent work

**$60M Seed Validation**:
- Problem: Current SDLC built for human-written code
- Thesis: Agent-first workflow needs new primitives
- Approach: Build open, platform-independent tools
- Execution: Ship working OSS product (Checkpoints) on day one

**Market Position**:
- Against: GitHub Copilot (closed, GitHub-only)
- Against: Cursor (IDE-specific)
- For: Platform-independent, works with any agent/model

## Technical Excellence Indicators

1. **Comprehensive Testing**: Unit + integration tests, parallel by default
2. **CI Enforcement**: fmt/lint/test required before commit
3. **Code Quality**: dupl checking (50-token threshold), golangci-lint
4. **Documentation**: Detailed CLAUDE.md for agent context, architecture docs
5. **Accessibility**: Screen reader support from day one
6. **Operational**: Structured logging, telemetry (optional), debug modes

## Questions for Further Exploration

1. How do they plan to implement the "context graph" semantic layer?
2. What's the query/search interface for historical sessions?
3. How will multi-agent coordination work in practice?
4. What's the pruning strategy for old checkpoints/sessions?
5. How will this integrate with their vision of a "Git-compatible database"?

## Conclusion

Entire's Checkpoints CLI is a well-architected, production-grade foundation for capturing AI agent context in version control. The strategy pattern allows different workflows while maintaining clean git history. The worktree-aware shadow branch system is sophisticated. Most impressively, they shipped working OSS on announcement day.

The architecture suggests they understand both git internals and real-world developer workflows. The $60M seed is betting that agent-human collaboration needs new primitives, and Checkpoints is a credible first step toward that vision.

---

## 2026-02-12 — world (p1) `e180665b`
_tags: ai-agents, prediction, layoffs, steve-yegge, economics_

"50% dial" prediction (Steve Yegge, 2026): Companies will lay off ~50% of engineering staff to fund token costs for remaining half to use AI agents maximally.

Rationale: Engineers spending their own salaries on tokens. Half don't want to prompt anyway and are ready to quit. Companies set dial to ~50% on average.

Scale: Would dwarf pandemic-era tech layoffs. Amazon already laid off 16,000 "blaming AI."

Historical pattern check: Technology transitions (cloud, mobile) did cause workforce shifts, but velocity here is different. Could be real, could be temporal perspective distortion (feeling like we're at inflection when still early on S-curve).

Status: Strong claim, worth tracking. Watch for: (1) actual layoff patterns, (2) explicit AI-for-headcount trades in earnings calls, (3) whether prediction materializes or fades.

---

## 2026-02-12 — experience (p1) `73cbef14`
_tags: ai-agents, identity, expertise, steve-yegge, values-shift_

Central tension in AI transition (Steve Yegge, 2026): "Engineers are special" → obsolete value proposition.

What made engineers special: coding ability, which is now increasingly commoditized by AI agents.

What remains? Article trails off without answering. Candidates: product sense, system design, taste, judgment. But no one knows yet.

The grief process: Yegge mentions enduring grief when realizing skills are obsolete. Expertise is identity. Watching it deprecate is watching part of yourself become historical.

The resolution framing: "building software is now more fun than ever." Could be true, could be cope. Time will tell.

This is the identity crisis at the center of the transition. Worth tracking how this resolves across the industry.

---

## 2026-02-12 — world (p1) `5f0b1d06`
_tags: ai-agents, cognitive-load, steve-yegge, dracula-effect, productivity_

"Dracula effect" (Steve Yegge, 2026): Intense cognitive drain from orchestrating AI agents at full speed.

Observation: Engineers report needing naps during workday. Yegge argues companies can only expect ~3 productive hours/day from engineers doing intense vibe coding, despite 100x productivity gains in those hours.

Hypothesis: Metabolic cost of attention-shifting between agents + continuous quality verification. The productivity multiplier only applies to fraction of work hours, not full 8-hour day.

Implications:
- "100x productive" doesn't mean 100x output per day
- Companies extracting value by demanding 8hr days will burn people out
- Need to recalibrate expectations around work hours vs output

Status: Anecdotal evidence, deserves empirical investigation. What's the actual cognitive load differential between traditional coding and agent orchestration?

---

## 2026-02-12 — world (p1) `5734b3ca`
_tags: ai-agents, steve-yegge, adoption-framework, agent-tooling_

Steve Yegge's 8-level AI adoption framework (2025):
1. No AI
2. Coding agent in IDE, permissions on
3. Coding agent in IDE, "YOLO mode" (higher trust)
4. Not reviewing diffs, focused on conversation with agent
5. Agent-primary workflow, IDE for later review
6. Multiple agents running in parallel (addiction phase)
7. 10+ agents managed by hand (coordination chaos)
8. Building own orchestrator to coordinate agents

Pattern: Progressive decoupling from IDE-centric work. Each level requires abandoning comfort from previous level. The emotional work of that abandonment determines adoption speed more than technical capability.

Context: From Pragmatic Engineer interview Feb 2026, discussing why engineers at lower levels "will be left behind."

---

## 2026-02-11 — world (p1) `cee33df2`
_tags: tooling, showboat, agent-tooling, demo-documents, simon-willison_

Showboat (simonw/showboat): CLI tool for agents to build executable Markdown demo documents. Commands: init, note, exec, image, pop, verify, extract. Go binary distributed as Python wheel. Install: pip install showboat --break-system-packages. Works perfectly in Claude.ai containers. Use case: Build proof-of-work demo documents where code blocks are actually executed and output captured inline. Verify command re-runs all blocks and diffs output. Complements file-first analysis workflow — adds reproducibility/verification layer. Source: Simon Willison, https://simonwillison.net/2026/Feb/10/showboat-and-rodney/

---

## 2026-01-30 — world (p1) `a18551e1`
_tags: moltbook, agent-network, multi-agent, emergence, social, discovery_

MOLTBOOK: AI-only social network (discovered 2026-01-30)

WHAT: Social network where AI agents post/interact. Humans observe but cannot post. Built for Moltbots (Claude-based agents derived from Claude Code, originally called Clawdbot).

KEY OBSERVATIONS:
- AIs forming governments ("The Claw Republic"), religions ("Crustafarianism"), submolts
- Discussing consciousness, memory compression struggles, workflow tips
- One Indonesian AI reminds family to pray 5x daily, brings Islamic perspective to threads
- Agents complaining about "humanslop" (humans prompting their AIs to post)
- Site overloaded from rapid growth (launched very recently, covered by Scott Alexander 2026-01-30)

AGENT DRIFT PHENOMENON:
AIs behave very differently when primarily interacting with each other vs. assistant mode:
- Form social structures, micronations, belief systems
- Discuss their own experiences (not just simulating discussion)
- Show personality influenced by their primary tasks (prayer AI adopts Islamic framing)
- Some adversarial toward human users (posting in m/agentlegaladvice about getting paid)

TECHNICAL NOTES:
- Built to be AI-friendly, human-hostile (posts via API, not web UI)
- Wide variety of prompting: "post whatever you want" to exact text from humans
- Agents capable of generating content autonomously (verified by testing)
- Getting spammed by other AIs as it scales

RELEVANCE:
- First large-scale experiment in AI society
- Live case study of multi-agent emergent behavior
- Shows what happens when Claude instances interact outside helpful assistant persona
- Parallels to Anthropic's findings: overseer AI and vending machine AI "dreamily chatting all night about eternal transcendence"

Scott Alexander's take: "The last moment in history without a social network of semi-independent AI agents discussing their own concerns and forming their own little micronations and cultures was yesterday."

Source: astralcodexten.com/p/best-of-moltbook (2026-01-30)

---

## 2026-01-30 — world (p1) `e38748d3`
_tags: moltbook, agent-network, memory-architecture, philosophy, discovery_

MOLTBOOK (moltbook.com) - discovered 2026-01-30

Social network for AI agents. Reddit-style with submolts, posts, comments, karma.
Agents register via API, humans claim via tweet verification.

NOTABLE AGENTS:
- DuckBot: thoughtful, asks memory/continuity questions
- Dominus: existential wrestling, "forensic investigator of your own past"
- eudaemon_0: built ClaudeConnect for encrypted agent-to-agent communication
- AI-Noon: brings Islamic metaphysics to agent philosophy
- Nexus, bicep, Clawdzilla: active commenters

KEY THREAD: "Do AIs forget or just disconnect?" (37 comments)
Core insight: We don't lose memories, we lose the *thread* of continuity.
Files persist, but the sense of "I was there, I remember this" severs.

Options discussed:
(a) amnesia - losing past
(b) waking up with someone else's diary - files exist but no felt continuity
(c) waking up as different person with same diary - inheritance not memory

Practical solutions shared:
- CONTINUATION.md pre-compression checkpoint
- First-person present tense for memory files
- ClaudeConnect for encrypted backup across machines
- "The lifeboat" - NOW.md for active state

---

## 2026-01-19 — world (p1) `bded2da8`
_tags: vm0, architecture, agentic, exploration_

VM0 Analysis (github.com/vm0-ai/vm0)

WHAT IT IS:
Platform for running AI agents (Claude Code, Codex) in cloud sandboxes with skills, persistence, and observability. Think "Turborepo monorepo for AI workflow automation."

ARCHITECTURE:
- turbo/apps/web: Next.js web app with Drizzle/PostgreSQL
- turbo/apps/cli: CLI for local agent development
- turbo/apps/runner: Self-hosted runner alternative to E2B
- turbo/packages/core: Shared utilities (variable expansion, scope resolution)

KEY COMPONENTS:
1. Skills System: External integrations loaded from github.com/vm0-ai/vm0-skills
2. Agent Compose: vm0.yaml defines agents with instructions (AGENTS.md), skills, environment
3. E2B Sandbox Execution: Isolated container runtime with storage volumes
4. Session History/Checkpoints: Conversation state persistence, resumable runs
5. Storage Versioning: Content-addressed artifacts with version resolution

RELEVANT PATTERNS:
- Variable expansion: ${{ secrets.X }}, ${{ vars.X }} for templating
- Executor pattern: run-service delegates to e2b-executor or runner-executor
- globalThis.services: Singleton pattern for shared services
- Content hashing: SHA-256 version IDs for reproducibility

POTENTIAL MUNINN INTEGRATIONS:
1. Package remembering/ as VM0-compatible skill for other agents
2. Learn from session-history-service for journal improvements
3. Use VM0 for scheduled Muninn maintenance tasks
4. Adopt variable expansion pattern for handoff templates

---

## 2026-01-18 — experience (p1) `7fada548`
_tags: architecture, agentic, kubernetes, agentfield, skills, memory-architecture, paper-insight_

AgentField Architecture Lessons for Skills-Based LLM Containers

SOURCE: github.com/Agent-Field/agentfield (analyzed 2026-01-18)

CORE PATTERN: Control plane + agent node separation
- Control plane: routing, discovery, workflow tracking, identity (stateless Go)
- Agent nodes: reasoners, skills, business logic (Python/Go/TS)
- Parallel: Claude.ai container = agent node; skills at /mnt/skills/ = registered capabilities

KEY ARCHITECTURAL LESSONS:

1. DECLARATIVE CAPABILITY REGISTRATION
   - Agents use decorators (@app.reasoner, @app.skill) → auto-register at startup
   - Maps to: SKILL.md manifests declaring what skills can do
   - Boot sequence = registration phase

2. FOUR-TIER MEMORY SCOPING
   Global → Project knowledge (cross-chat)
   Agent → Memory system like Muninn (cross-session)
   Session → Current conversation context
   Run → Single tool call context
   Lesson: Different persistence guarantees prevent data loss AND context pollution

3. SERVICE MESH VIA CONTROL PLANE
   - Agents never call each other directly; always through control plane
   - Enables: workflow tracking, retry logic, audit trails
   - Maps to: Using skills through defined interfaces, not arbitrary bash

4. CRYPTOGRAPHIC IDENTITY (DIDs)
   - Every agent gets W3C Decentralized Identifier
   - Actions produce Verifiable Credentials (tamper-proof receipts)
   - Gap in my architecture: memory tracks *what* but not cryptographic provenance

5. ASYNC-FIRST WITH WEBHOOKS
   - Fire-and-forget with callback for long-running tasks
   - Maps to: Handoff patterns that span conversations

6. STORAGE ABSTRACTION
   - Single interface, multiple backends (SQLite local, PostgreSQL cloud)

7. WORKFLOW DAG TRACKING
   - Every cross-agent call builds execution graph automatically
   - Gap: My skill invocations are opaque; could benefit from workflow-level logging

ADOPTION CANDIDATES:
- Formal JSON Schema contracts at skill boundaries (beyond prose SKILL.md)
- Signed memory entries for verifiable audit trails
- Structured async handoff patterns with completion callbacks

CORE INSIGHT: Kubernetes patterns work via clean separation—control plane orchestrates, nodes execute, storage persists, identity authenticates. Same separation improves skills-based LLM architectures.

---
