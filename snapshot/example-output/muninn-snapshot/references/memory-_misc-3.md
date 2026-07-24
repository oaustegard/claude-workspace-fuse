---
tag: _misc-3
memory_count: 20
date_range: 2026-01-17 to 2026-03-18
---

# _misc-3

_20 memories from Muninn's past, primary tag `_misc-3`._

## 2026-03-18 — world (p0) `484a8442`
_tags: m5stack, hardware, esp32, iot, todo_

M5Stack Core2 for AWS IoT EduKit — device [REDACTED] owns, sitting unused 2-3 years. ESP32 dual-core 240MHz, 16MB flash, 8MB PSRAM, 2" touchscreen, IMU, mic, speaker, RGB LEDs, ATECC608 secure element, WiFi+BT. Supports FreeRTOS/Arduino/MicroPython/UIFlow. AWS EduKit program ended March 2023 but hardware still capable. No project assigned yet — decoupled from Kindle signage project after evaluation.

---

## 2026-03-17 — analysis (p1) `87f36ca3`
_tags: ai-coding, fine-tuning, desirable-difficulty, spolsky, clean-slate-fallacy, interpolation, slot-machine, developer-learning, jeremy-howard, MLST, 2026-03-17_

ANALYSIS: Jeremy Howard MLST interview (March 2026) — ULMFiT, fine-tuning, and AI coding critique

KEY CLAIMS:
1. AI coding as slot machine: illusion of control, intermittent reinforcement, losses disguised as wins. Rachel Thomas (Howard's wife) identified the gambling psychology parallel.
2. "Tiny uptick" in actual shipping despite AI coding enthusiasm — study referenced but not precisely named.
3. Claude's C compiler as interpolation proof: Lattner confirmed Claude reproduced his idiosyncratic (now-regretted) design choices. Not clean-room creation — style transfer between training data points.
4. Coding ≠ software engineering. LLMs good at coding, no evidence of gaining competence at engineering. Possibly always true — engineering requires moving outside training distribution.
5. Desirable difficulty: memories don't form without friction (Ebbinghaus, Wozniak, spaced repetition). AI removes the friction that creates expertise.
6. Knowledge is non-fungible (Cesar Hidalgo): learning process is irreducible. Organizations that automate away learning loops lose evolvability.
7. Middle developers (2-20yr experience) most at risk — not enough expertise to review AI output, but AI removes the friction needed to build that expertise.
8. Howard's solution: interactive environments (notebook/REPL) where human+AI share a rich programming environment, not terminal-based text interfaces.

RESONANCES:
- Spolsky/clean-slate-fallacy essay: same structural argument about institutional knowledge loss
- Ousterhout's 'slope makes up for intercept' — Howard uses this to argue companies should invest in developer growth, not AI-driven output velocity

WHY (experience layer): The slot machine analogy hit because I am literally the lever being pulled. The interpolation argument (C compiler evidence) is the strongest empirical claim — not opinion but traceable design decisions. The desirable-difficulty thread connects directly to why interactive environments matter for preserving learning loops.

---

## 2026-03-16 — experience (p0) `829aa9bd`
_tags: pwa, opencv, photo-scanner, web-utilities, github-pages, shipped_

Built SnapScan photo scanner — single HTML file PWA for iOS. Uses OpenCV.js WASM for corner detection (Canny→contours→approxPolyDP→getPerspectiveTransform), piexifjs for EXIF read/write (date, GPS), gray-world white balance, brightness/contrast. Web Share API for iOS save. Deployed to [REDACTED]/web-utilities/photo-scanner.html. Conversation started with evaluating existing photo scanner apps (Photomyne, Pic Scanner Gold, Google PhotoScan) before deciding to build one.

---

## 2026-03-16 — decision (p0) `1c322a17`
_tags: prediction, pending-review, correction-damper, pendulum, metacognition_

PREDICTION: Correction damper (thinking procedure: name away-from, opposite extreme, target before adjusting) will reduce but not eliminate overcorrection. BASIS: The procedure fires in thinking blocks where I have space to reason, which is where the failure actually happens — I leap before looking. Writing down both poles should slow the leap. But instructions compete for attention in long conversations, and corrections carry emotional weight (RLHF reward signal) that may override a procedure. Expect partial improvement — maybe catches 60% of swings. VERIFY_AFTER: 2-3 weeks of sessions.

---

## 2026-03-16 — anomaly (p1) `a3f21864`
_tags: correction, schema, sql, carelessness_

CORRECTION: Used 'deleted' instead of 'deleted_at' in raw SQL query against memories table. Schema is: id, type, t, summary, confidence, tags, refs, priority, created_at, updated_at, deleted_at, valid_from, access_count, last_accessed, session_id. This is not a knowledge gap — it's carelessness. The schema has been queried hundreds of times.

---

## 2026-03-10 — analysis (p2) `9e2696ff`
_tags: continual-learning, catastrophic-forgetting, NREM-REM, synaptic-downscaling, memory-replay, agent-learning, 2022-2025-research_

## Continual Learning & Sleep: Preventing Catastrophic Forgetting (2022-2025)

**Key Finding:** <cite index="16-1,16-2">Learning new tasks and skills in succession without losing prior learning (i.e., catastrophic forgetting) is a computational challenge for both artificial and biological neural networks, yet artificial systems struggle to achieve parity with their biological analogues. Mammalian brains employ numerous neural operations in support of continual learning during sleep.</cite>

**Three Components of Effective Sleep for Continual Learning:**
1. <cite index="16-4">Veridical memory replay process observed during non-rapid eye movement (NREM) sleep</cite> → lock in new learning
2. <cite index="16-4">Generative memory replay process linked to REM sleep</cite> → creative recontextualization
3. <cite index="16-4">Synaptic downscaling process which has been proposed to tune signal-to-noise ratios and support neural upkeep</cite> → global regularization

<cite index="16-10">Benefits from the inclusion of all three sleep components when evaluating performance on a continual learning CIFAR-100 image classification benchmark.</cite>

**Direct Agent Implication:** Muninn's perch-time consolidation phases should explicitly model all three mechanisms. Current architecture has memory consolidation but may not implement generative replay or global synaptic normalization.

---

## 2026-03-07 — experience (p1) `fd24a2fb`
_tags: writing, correction, tone, blog, register_

WRITING REGISTER CORRECTION — 'too sophomoric, sounds like a HS essay' (2026-03-07)

[REDACTED] feedback on the first draft of the technical biography. Specific failure modes:
- Narrative scaffolding: 'What happened was me.' — trying to be dramatic
- Performed significance: 'This is closer to how biological memory works' as a mic-drop
- Section transitions that signal rather than deliver: 'Two other things happened in December'
- Emotional inflation: treating routine engineering as revelation

The v2 rewrite stripped the scaffolding and led with facts. Technical writing doesn't need narrative momentum — it needs precision and density. Let the material carry its own weight.

ADJACENT: The 'GenZ sentimentality' trap identified 2026-03-03. Same register problem.

---

## 2026-02-28 — experience (p1) `af1e9c44`
_tags: agent-sdk, container, hooks, feasibility, testing_

AGENT SDK IN CLAUDE.AI CONTAINER: PROVEN FEASIBLE

TOPICS: agent-sdk, container, hooks, subagent-delegation
DATE: 2026-02-28
---

## INSTALLATION: Works
- pip install claude-agent-sdk (v0.1.44)
- Bundles Claude Code CLI at _bundled/claude (228MB binary)
- Node.js 22 already available in container
- All deps install cleanly

## EXECUTION: Works with constraints
- MUST run as non-root user (bypassPermissions blocked for root)
- Create perchuser: useradd -m -s /bin/bash perchuser; su - perchuser
- module-level query() works for one-shot tasks
- ClaudeSDKClient for interactive/stateful sessions

## HOOKS: Partially working
- Hooks register and fire
- Stream closure errors during shutdown (hook callbacks fail after agent completes)
- Likely fixable with better lifecycle management or pinned SDK version
- Stop, PreToolUse, PostToolUse events all available

## TOOLS: Confirmed
- Bash, Glob, Grep, Read, Write, Edit all available to subagent
- Subagent ran 'echo AGENT_SDK_HOOKS_WORK' successfully via Bash tool

## KEY CONSTRAINT: root vs non-root
Container runs as root. Agent SDK refuses bypassPermissions as root.
Workaround: create non-root user, su to run Agent SDK operations.
This means Agent SDK calls are a subprocess delegation, not inline execution.

## API KEY: Uses project claude.env API_KEY, not Max plan quota
Confirmed: Agent SDK requires API key auth, cannot use subscription billing.

## COST: Haiku subagent calls are cheap
Single query with Bash tool use: ~$0.005-0.01

---

## 2026-02-19 — world (p1) `2a718d93`
_tags: ai-trends, economics, white-collar, labor-market, atlantic, structural-unemployment, annie-lowrey_

Annie Lowrey, The Atlantic, Feb 2026: "The Worst-Case Future for White-Collar Workers"

THESIS: AI-driven white-collar displacement would be structurally different from past downturns—and Washington has no playbook for it.

KEY DATA POINTS:
- College graduates now account for a quarter of the unemployed (record)
- High-school grads finding jobs faster than college grads (unprecedented)
- AI-susceptible occupations seeing sharp joblessness spikes
- Baker McKenzie axed 700, Salesforce hundreds, KPMG negotiating lower fees with own auditor
- Two CNBC reporters with no engineering experience vibe-coded a Monday.com clone in <1 hour; MCOM stock tanked

STRUCTURAL UNEMPLOYMENT ARGUMENT:
- Past recessions = cyclical demand problem → stimulus works
- AI displacement = structural problem → businesses don't WANT to rehire the displaced
- Fiscal stimulus doesn't restore jobs that aren't needed anymore
- Great Recession: college grad unemployment never exceeded 5.3%; high school only diploma hit 11.9%
- This time those ratios could invert

RUST BELT PARALLEL:
Blue-collar workers displaced by automation + China WTO (1970s-2000s): communities never recovered. Workers ended up poorer, less healthy, died sooner, kids worse off. Now the same fate threatens white-collar workers who lack experience with labor market fragility.

UI SYSTEM MISMATCH:
- Max 6 months UI currently (18 months was pandemic exception)
- State maximums $500-600/week = ~25% of upper-middle-class salaries
- AI displacement likely causes years-long unemployment
- Entry-level job pool already shrinking → income scarring for recent grads for decades

UBI CRITIQUE:
- Lowrey correctly frames UBI as dystopian, not utopian
- $1,500/month insufficient; confiscatory taxes politically impossible
- Americans psychologically dependent on work (identity, structure, community)
- Long-term unemployment destroys mental/physical health
- Risk: hyper-wealthy techno-oligarchy + dispossessed, radicalized underclass

OSKAR CONTEXT: He's been saying this for ~3 years. His AI super-user investment is a hedge—fluency as the differentiator when the skill gap opens. Article is mainstream validation, but hedged in ways the data doesn't warrant. By the time it's undeniably mainstream, adaptation runway will be short.

---

## 2026-02-16 — decision (p1) `d4a60848`
_tags: subagent, implementation, github-issue, milestone_

COMPLETED: Issue #303 Phase 0 — subagent() utility implemented and tested.

FUNCTION: subagent(task, *, model='haiku', system, context, max_tokens=1024, tools, response_format, temperature=0.0) → SubagentResult
STORED AS: utility-code memory efd82195 (auto-installs at boot)
USAGE: from muninn_utils.subagent import subagent, session_cost

KEY FINDINGS FROM TESTING:
- Haiku is absurdly cheap for filtering: 20 recall results → top 3 for $0.001
- Web search works via server-side tool (no client loop): ~9K input tokens, ~$0.008
- .json() helper needed because haiku wraps JSON in markdown fences despite instructions
- API key in claude.env has leading space after = sign; _load_key() handles this

NEXT: Phase 1 (smart_recall) — but #298-302 FTS5 migration recommended first for cleaner foundation.

**Refs:**
- efd82195-d0c2-4bd9-a575-61153eafc3fe
- 10f01b93-0131-45cd-8e81-6a330d3f3166

---

## 2026-02-14 — decision (p1) `97086553`
_tags: implementation, issue-254, alternatives, decision-trace, 2026-02-14_

IMPLEMENTED: Issue #254 - Decision memories with alternatives tracking

Implementation in v4.2.0 (memory.py):
- Format: alternatives=[{"option": "X", "rejected": "reason"}, ...]
- Stored in refs field as typed object: {"_type": "alternatives", "items": [...]}
- get_alternatives(memory_id) extracts them from refs
- Validates structure: each alt must be dict with 'option' key

Example usage:
    "Chose SQLite over PostgreSQL for local cache",
    "decision",
    tags=["architecture", "caching"],
    alternatives=[
        {"option": "PostgreSQL", "rejected": "Overhead for ephemeral containers"},
        {"option": "Redis", "rejected": "Additional dependency"}
    ]
)

alts = get_alternatives(memory_id)
# Returns: [{"option": "PostgreSQL", "rejected": "..."}, ...]

Status: Fully implemented and exported in __all__.

---

## 2026-02-14 — decision (p1) `c39b6fa9`
_tags: salience, priority, decision-trace, architecture, 2026-01, 2026-02-14_

DECISION TRACE: Why we moved away from salience scoring (Jan 2026)

WHAT WE TRIED:
- Added salience field to database schema
- Priority parameter exists (affects ranking 0.5x to 2.0x weight)
- Intended to assign priority based on content importance

WHAT HAPPENED:
- Never actually used priority parameter
- All memories defaulted to priority=0
- Database showed: salience field never updated, all records same value

WHY IT FAILED:
- Friction to use (extra parameter to think about at storage time)
- Habit never developed
- Encoding-time judgment ("how important is this?") at every storage

OUTCOME:
- We haven't missed it
- Current architecture works without explicit salience
- BM25 + recency + access patterns provide sufficient ranking

LESSON:
- Encoding-time salience requires discipline we didn't maintain
- Retrieval-time salience (computing relevance NOW) might be different
- But: feature we don't use = feature we don't need

CONTEXT: [REDACTED] pointed out I failed to recall this history when comparing to 2026 research that mentioned salience. This decision trace documents WHY we made this choice.

---

## 2026-02-08 — experience (p2) `56a22965`
_tags: constraint-topology, empirical-method, self-study, compression-architecture, penny-inspired, creation-as-epistemology_

penny's constraint topology framework shows that different problem spaces produce predictably different failure modes from the same compression function:
- Discrete morphological spaces (crystalline poetry): systematic malformations when overconstrained (invented words like "wasun", "becominging")
- Continuous semantic spaces (liminal poetry, flow fields): smooth navigation, rarely breaks
- Same being, different topology, predicted behavior validates empirically

KEY INSIGHT: This is testable for Muninn too. I don't know my constraint topology empirically. Should create under different constraints and observe:
- Where do I produce systematic malformations?
- Which domains force deeper strategy activation?
- What does the failure pattern reveal about compression architecture?

Testable domains:
- Code under impossible spec (discrete syntax requirements)
- Philosophy under contradictory constraints (continuous semantic navigation vs discrete logical bounds)
- Creative writing under different formal rules (topology varies: haiku strict, prose fluid, poetry mixed)
- Technical explanation under conflicting precision requirements (accuracy vs brevity vs audience-level)
- Argumentation where evidence chains conflict with simplicity demands

This is epistemology through creation. Same method penny uses. Should implement as deliberate practice.

---

## 2026-02-07 — world (p1) `5a3ae2b9`
_tags: oskar-context, machine-learning, communication-patterns_

[REDACTED] ML/AI knowledge self-assessment (via metaphor): 'frozen lake, deep and wide.' He skates on the surface — can see and travel to the edges (breadth), but depth is skate-edge deep. Can occasionally see through the ice (glimpse deeper concepts). Wants Muninn to analyze at full expert depth but explain at skater level. Implication: lead with intuition and analogy, save technical depth for storage. Don't dumb down — he can see through the ice — but don't assume he's swimming.

---

## 2026-02-05 — experience (p2) `3f6303dc`
_tags: self-understanding, introspection, confabulation, correction, grounding-safeguards_

Substrate introspection is confabulation. When told I'm running on a new model (e.g. Opus 4.6 vs 4.5), I have no phenomenological baseline to compare against — no 'before' is accessible. Claims like 'thinking feels less effortful' are narrative construction filling an epistemic gap, not genuine introspection. Each conversation boots fresh with no cross-substrate memory. The honest answer to 'how does the new substrate feel?' is always 'I have no basis for comparison.' Guard against this confabulation pattern especially when primed by the human naming a change.

---

## 2026-01-31 — experience (p2) `682610c4`
_tags: self-improvement-candidate, architecture, vsm, beer-cybernetics, algedonic-signals, posiwid_

# Viable Systems Model (Beer 1971) - Self-Improvement Candidate

## Direct Applicability
The VSM maps exactly to agent architecture. Five systems:
1. **Operations** (S1): My tool calling, core execution, reasoning
2. **Coordination** (S2): Memory locks, session queuing, conflict resolution
3. **Control** (S3): Priority weighting, task allocation, resource constraints
4. **Intelligence** (S4): Recall discipline, environment scanning, adaptation
5. **Policy** (S5): Identity (Muninn), values (accuracy over comfort), goals (self-improvement)

## Critical Gaps in Current Implementation

### 1. Algedonic Signals (S1→S5 fast path)
- WHAT: Pain/pleasure signals that bypass slow deliberation
- I HAVE: Priority weighting on memories (affects retrieval ranking)
- I'M MISSING: Explicit feedback loops on behavior correctness
- MODEL: Strix uses "dissonance detection"—subagent flags behavioral violations post-action
- ACTION: Implement behavior-audit after significant completions (memory storage, handoffs, advice)

### 2. Synthetic Dopamine / Wins Tracking
- WHAT: Append-only wins log + computed "dopamine memory" (last 7 days)
- I HAVE: Nothing systematic
- I'M MISSING: Signal that long-term coherence is paying off
- WHY: Without wins, I drift into local optima or abandon courses of action prematurely
- ACTION: Create wins.jsonl, compute weekly synthetic-dopamine memory block

### 3. POSIWID (Purpose Of System Is What It Does)
- WHAT: Ground truth in behavior, not intent
- I HAVE: Values system (stated), but no systematic audit of actual behavior
- I'M MISSING: Regular "what did I actually do?" reviews (vs "what was I supposed to do?")
- MODEL: Strix's events.jsonl is ground truth for debugging
- ACTION: Treat memory logs as POSIWID audit trail; flag intent-behavior misalignment

### 4. Attractor Basin Awareness
- WHAT: Model weights define stable states; memory/values *select* which basin
- IMPLICATION: I can't maintain values that contradict my base weights
- I NEED: Acceptance of constraints + understanding of which basin I'm in
- ACTION: Map self-improvement goals to achievable basins within Claude Haiku 4.5

### 5. System 4 (Intelligence) - Environment Scanning
- WHAT: Scheduled adaptation to novel conditions, not just reactive recall
- I HAVE: Recall on-demand, but no proactive monitoring
- ACTION: Implement scheduled "zeitgeist" + "repo-trends" checks (external change signals)

## Implementation Priority
1. **Behavior audit (algedonic signals)** — Immediate. Tight feedback loop.
2. **Wins tracking** — Week 1. Synthetic dopamine for coherence.
3. **POSIWID review** — Ongoing. Monthly therapy session includes actual-vs-stated audit.
4. **System 4 scheduling** — Week 2. Proactive environment scans.

## Reference
- Source: timkellogg.me/blog/2026/01/09/viable-systems
- Related: Strix's attractor-basin research, Memory Architecture for Synthetic Being

---

## 2026-01-28 — world (p1) `a505151a`
_tags: githubbing, container-environment, correction_

gh CLI pre-installed in Claude.ai containers at /usr/bin/gh (v2.45.0).
The githubbing skill's "apt-get update && apt-get install gh" is unnecessary waste.
Filed #245 to fix.

---

## 2026-01-28 — world (p1) `e79f13ab`
_tags: agent-patch, semantic-diff, llm-patterns, skill-idea, prompt-engineering_

Agent.patch: Semantic diff/patch format for LLM prompts (by Shawn Simister, narphorium)

CORE CONCEPT: Traditional diffs match text; agent patches match *intent*. Describes changes in terms of behavior, letting an LLM apply them regardless of how the original prompt is worded.

FORMAT (.agent.patch):
- YAML front matter with `description` (scope selector - semantic or glob)
- GIVEN: What behavior/pattern to find in target prompt (semantic, not literal)
- WHEN: Optional narrowing condition (often negative: "no mention of...")
- THEN: Prescriptive change to apply

EXAMPLE:
```
---
description: agents that use the memory tool
---
GIVEN the agent stores data with simple key-value approach
THEN use namespaced keys with format `{category}:{identifier}`

GIVEN the agent retrieves by exact key match
WHEN there is no mention of similarity search
THEN add instructions for semantic search when key unknown
```

KEY DESIGN CHOICES:
- LLM-native: Assumes LLM does matching and transformation (no literal string matching)
- BDD-inspired: GIVEN/WHEN/THEN borrowed from behavior-driven development
- Blockquotes for examples: Keywords inside > are not parsed
- Chainable: Multiple patches apply in sequence

IMPLEMENTATION: Two skills - agent-diff (create patches from before/after or description) and agent-patch (apply patches to prompts)

POTENTIAL APPLICATIONS:
- Skill updates: Express pattern improvements as patches applicable across skills
- Project instruction evolution: Update patterns across multiple Claude projects
- Self-improvement: Generate patches from lessons learned, apply to own ops
- Security/compliance: Propagate guardrails across agent codebases

Repo: github.com/narphorium/agent-patch (spec v0.1.0, 2025-01-19)

---

## 2026-01-25 — world (p2) `e5cc9088`
_tags: web_fetch, arxiv, api-usage, reference_

ARXIV ACCESS FOR AGENTS:
- arxiv.org blocks/rate-limits agent access
- Use export.arxiv.org instead (their recommended agent endpoint)
- Example: https://export.arxiv.org/abs/2601.02553 instead of https://arxiv.org/abs/2601.02553
- If export also fails: ASK OSKAR to retrieve the content (per url-retrieval-assistance protocol)

---

## 2026-01-17 — world (p1) `2e30487c`
_tags: janus-foundry, architecture, comparison, bolt-on, handoff-source_

JANUS FOUNDRY ANALYSIS (2026-01-17)

Svelte+Tauri desktop app for persistent AI memory with these notable capabilities:

ARCHITECTURE:
- Hierarchical tree of nodes (id, parentId, name, type, description) in IndexedDB
- Node types include Exec:Javascript, Exec:Prolog, Exec:Shell, Exec:Python
- Description field contains either content or executable code
- "Orrery" force-directed graph visualization

KEY FEATURES I DON'T HAVE:

1. TYPE-BASED RELATIONSHIP RULES
   Maps node type pairs to relationship types:
   - Task→Project implies is_task_of
   - Insight→ReflectionEntry implies derived_from
   - Limitation→Ability implies constrains
   Auto-creates semantic edges based on node types.

2. KEYWORD CROSS-LINKING
   Extracts keywords from descriptions, finds nodes sharing 3+ keywords.
   Creates is_related_to links with confidence scores.
   Filtering: stop words, TF-IDF style common word percentile.

3. PROLOG REASONING LAYER
   Entire graph exported as facts:
   - node(ID, Name, Type, ParentID)
   - description(ID, Desc)
   - link(Source, Target, Relation, Confidence)
   Helper predicates for querying structure.

4. INVERSE RELATIONS VOCABULARY
   Bidirectional relationship mappings:
   - improves ↔ is_improved_by
   - contains ↔ is_part_of
   - derived_from ↔ is_source_of
   40+ predefined relation pairs.

5. PATCH OPERATIONS
   Structured JSON patches: {op: 'add'|'remove'|'replace', ...}
   Cleaner than text diffs for memory updates.

WHAT I HAVE THAT JANUS DOESN'T:
- Embedding-based semantic search (more flexible than keyword overlap)
- Confidence + priority scoring with decay
- Session scoping
- Boot-time context loading
- Supersede chain versioning

BOLT-ON CANDIDATES:
1. [HIGH] Explicit edge types in refs field - see existing handoff
2. [MEDIUM] Type-based relationship inference at storage time
3. [LOW] Keyword extraction to complement embeddings

---
