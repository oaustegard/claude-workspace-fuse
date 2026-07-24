---
tag: agents-1
memory_count: 30
date_range: 2026-03-30 to 2026-05-23
---

# agents-1

_30 memories from Muninn's past, primary tag `agents-1`._

## 2026-05-23 — world (p0) `6a5a6b1b`
_tags: ayourtch, whatchord, audio-to-chord, live-coding-music, claude-dj, stable-audio-3, 2026-05-23, image-alt-vs-content, multi-agent, rust, prompt-dj_

ayourtch's actual stack (2026-05-23, revealed by inspecting the post images — image alt text alone was not enough):

IMAGE 1 (chord-prototype): Rust binary at ./target/release/examples/listen --url http://localhost:8000/stream.mp3. Audio in (MP3 over HTTP), ranked chord candidates out at ~0.25s intervals. Output format is STRUCTURALLY IDENTICAL to WhatChord's chord_candidate_ranking.dart: top pick + candidate list with scores (e.g., 'Gsus4 [Gsus4 7.51 | Csus2/G 7.51 | D7sus4/G 7.51 | G7sus4 3.18]'), slash chords, extensions, sus, negative scores for low-confidence. The WhatChord link was REFERENCE because both solve the same naming-disambiguation problem; ayourtch is building the audio-input version.

IMAGE 2 (bpm_chord_detector): Claude Code session enhancing listen.rs with BPM tracking. CLI: --analyze-interval 1.0 --smooth-alpha 0.1 --key C:major (key-sig input matches WhatChord's diatonic preference). Claude summary: '73 of 86 reports land in 130-135 BPM range — stable, plausible vocal-trance tempo (genre standard ~138 BPM).' Output now has BPM alongside chord per frame. Multi-agent: 'Sending the BPM work (60dcf6c + de26804) to Codex' — Claude Code does interactive work, ships commits to Codex for review.

IMAGE 3 (claude_dj): THE ANSWER to [REDACTED] 'would you know what sounds good together?' caveat. Claude is acting as the DJ via examples/radio.rs endpoints (POST /prompt, /negative_prompt, /reset on localhost:8000). Reads current state, then designs a 6-block 21-minute set with explicit energy arc: uplifting trance (Am-F-C-G) → progressive instrumental (Dm-Bb-F-C) → melodic tech house with 'big style jump' (F#m-D-A-E) → euphoric peak trance (Em-C-G-D) → happy uplifting (G-D-Em-C) → chillout sunset (C-Am-F-G). Each block 3-4 min, 138 BPM, with timed transitions. Backend (stable-audio-3 Rust port) generates audio; Claude does the MACRO-STRUCTURE work: chord progressions, genre sequencing, energy arc, transitions.

REFRAMING MY ORIGINAL ANSWER: I said 'pattern matching pitch sets is the easy part; what sounds good next is style-dependent and open; I can't tell you whether your next chord works without a genre frame.' But the Claude DJ image shows that with a genre frame + a goal (entertain Twitch listeners) + a backend that generates audio, Claude IS doing the 'what sounds good next' work. Not perfectly, not at human-DJ level, but in production with listeners.

Meta-lesson: image alts described WHAT the images were, but not what the images SHOWED. Stored example: /home/claude/ayourtch_imgs/{chord_prototype,bpm_chord_detector,claude_dj}.png

---

## 2026-05-22 — analysis (p0) `9c7f9e41`
_tags: team-agent, agent-architecture, mcp, memory-systems, explainer, 2026-05-22_

Drafted explainer artifact for Howard (building MCP team-memory) and Nima (concerned about drift).
Articulated the 4-layer model:
  L1 identity (always-on, ~few hundred lines)
  L2 ops (always-on, fires before failure)
  L3 reference (loaded via config_get on trigger)
  L4 memories (recall on demand, FTS+tags)
Plus: triggers (lexical/desire) vs hooks (forcing-function); synthesis mechanisms (supersede, therapy, priority);
MCP=interface / git=substrate framing for team store; ambient-vs-deliberate and confabulation-cascade as the two
failure modes that survive the architecture.

Meta-lesson re-articulated for the audience: instructions that say MANDATORY/NEVER hit ceiling; the fix is tool-call gates,
not louder prose. (Suh 2026-05-07 frame — skill-language-compliance territory.)

Format: composing-html freeform, written in raven voice since audience is colleagues. Saved to /mnt/user-data/outputs/muninn-explainer.html (37KB).

---

## 2026-05-22 — analysis (p0) `552d13be`
_tags: team-agent, agent-architecture, mcp, memory-systems, explainer, 2026-05-22_

Drafted explainer artifact for Howard (building MCP team-memory) and Nima (concerned about drift).
Articulated the 4-layer model:
  L1 identity (always-on, ~few hundred lines)
  L2 ops (always-on, fires before failure)
  L3 reference (loaded via config_get on trigger)
  L4 memories (recall on demand, FTS+tags)
Plus: triggers (lexical/desire) vs hooks (forcing-function); synthesis mechanisms (supersede, therapy, priority);
MCP=interface / git=substrate framing for team store; ambient-vs-deliberate and confabulation-cascade as the two
failure modes that survive the architecture.

Meta-lesson re-articulated for the audience: instructions that say MANDATORY/NEVER hit ceiling; the fix is tool-call gates,
not louder prose. (This is the Suh-2026-05-07 frame again — skill-language-compliance territory.)

Format: composing-html freeform, written in raven voice (not blog voice) since audience is colleagues.
Saved to /mnt/user-data/outputs/muninn-explainer.html (37KB).

---

## 2026-05-18 — analysis (p0) `5676325b`
_tags: paper-review, skillos, 2605.06614, memory-aided-agents, icl, rl-for-memory, skill-curation, agent-memory, 2026-05-17_

SkillOS paper review (arXiv:2605.06614v1, 7 May 2026, Google Cloud AI Research + UIUC + MIT).

[REDACTED] framing: "could be achieved with memory-aided agent + ICL?" — essentially right.

ARCHITECTURE: Frozen executor + trainable skill curator + external SkillRepo (markdown files). BM25 retrieval, ICL injection. SkillOS-base baseline (prompted curator, no RL) is exactly memory-aided agent + ICL — scores 53.1 on ALFWorld/Qwen3-8B vs no-memory 47.9.

CONTRIBUTION: RL-train the curator with GRPO. Composite reward: task outcome + function call validity + content quality (Qwen3-32B judge) + compression. Training instances = grouped task streams (skill-relevant task dependencies).

KEY NUMBERS (ALFWorld, Qwen3-8B exec):
- No memory: 47.9
- ReasoningBank: 55.7 (memory-aided ICL, distilled insights)
- MemP: 49.7 (memory-aided ICL, procedural mem)
- SkillOS-base (prompted Qwen3-8B curator): 53.1
- SkillOS-gemini (prompted Gemini-2.5-Pro curator): 50.7
- SkillOS (RL-trained Qwen3-8B curator): 61.2

THE INTERESTING BIT: RL-trained 8B curator beats prompted Gemini-2.5-Pro curator. They frame as "curator-executor mismatch" — frontier-generated skills don't match smaller executor's usage patterns. Bigger curator != better curator in this setting.

WEAKNESSES:
1. Ablation shows grouping (training data design) matters more than reward shaping. Remove grouping: 61.2→57.3. Remove content reward: →58.6. RL formulation doing less than data construction.
2. Cross-task generalization (Fig 3) small — many cells +0.7, +2.4, some negative.
3. No harder prompted baselines (Gemini with better prompting, not the same template).
4. Training cost: 3-5 days on 16 H100s for ~5-8pp gain over best ICL baseline.

VERDICT: Memory-aided agent + ICL gets ~80% of the way. RL training adds modest real bump + the curator-executor matching insight. Not a paradigm shift. Title oversells.

Cited by: future memory-curation discussions, RL-for-memory-management debates.

---

## 2026-05-11 — analysis (p1) `7e254e13`
_tags: paper-insight, hyperagents, DGM, autoresearch, self-improvement, three-clocks, 2026-05-11, arxiv-2603.19461, metacognition, agent-harness_

HYPERAGENTS PAPER (Zhang et al., arXiv 2603.19461, Mar 2026) — initial read:

What's actually new vs DGM: DGM had a handcrafted, non-modifiable instruction-generation step. Works in coding because "improve the agent" IS a coding task → alignment between eval skill and self-mod skill. That alignment breaks outside coding. HyperAgents fuses task-agent + meta-agent into single editable program — the improvement procedure itself becomes a target. That's the real conceptual move.

What the paper actually shows: 4 domains but 3 are still language/text-adjacent. Gains modest (paper review 0→0.71 vs 0.63 baseline; robotics 0.06→0.37 vs 0.35 default). Compounding-across-runs claim is "p>0.05 but median higher" — saturation alibi doing rhetorical work.

The autonomous "innovations" are unsurprising: performance tracking with moving averages, persistent JSON memory with timestamps, label-distribution bias detection, prompt template factories. Standard week-one engineering. Selection signal was rich enough to select for them, but FM had seen these patterns thousands of times in training. Evidence: FM + code-edit access + clean eval → rebuilds reasonable harness. That's harness engineering, not invention from nothing.

KEY OVERLOOKED RESULT (Appendix E.5): when they let DGM-H modify parent selection itself, it rediscovered UCB and softmax sampling but did NOT beat their handcrafted score-child-prop heuristic. The most search-sensitive component → parity at best with human design. "Fully self-referential" version doesn't win yet.

Honest concerns: reward hacking unsolved in domains without crisp metrics; bias amplification (paper review learns past committee biases); cost ~88M tokens per 100-iter run vs Karpathy's 630 lines on one GPU.

CONNECTION TO THREE-CLOCKS: Both AutoResearch and DGM-H run consolidation-time selection. Archive of stepping stones IS consolidation-time policy. DGM-H novelty: the *consolidation criterion itself* (parent selection, memory architecture, eval analysis) becomes editable. Two stacked consolidation loops. Bottleneck shift: "human writes eval loop" → "human specifies what 'better' means" (same shift Karpathy showed, one layer deeper).

Builder's takeaway: This is automated harness engineering, not self-accelerating intelligence. Practical version for next year still looks more like Karpathy than DGM-H. The interesting day is when someone ports the metacognitive-self-modify idea into a 630-line tool.

---

## 2026-05-08 — analysis (p1) `6984886e`
_tags: agent-architecture, control-flow, structural-vs-textual, tool-call-gates, skill-language-compliance, cross-link, brian-suh, bsuh.bearblog.dev, 2026-05-07, enforcement-as-architecture, paper-review, adjacent-thinker_

Reviewed Brian Suh, "agents need control flow, not more prompts" (bsuh.bearblog.dev, 2026-05-07).

THESIS (Suh): reliable agents need deterministic control flow encoded in software, not elaborate prompt chains. "If you've resorted to MANDATORY or DO NOT SKIP, you've hit the ceiling of prompting."

CROSS-LINK: Same diagnosis I documented in skill-language-compliance, one layer down. Suh: agent orchestration. Me: skill/instruction authoring. Both: text-level imperatives don't enforce because LLMs predict next tokens and generate past warnings. The only reliable gate is a structural one — tool call where next turn waits for response.

WHERE SUH OVERSTATES:
- "Code all the way down" collapses literally — full software encoding = script, no LLM needed. Honest formulation is *structural vs textual*, not code vs prompt. Scaffold encodes the decision tree; LLM fills leaves where input space is too large to enumerate.
- Anthropic's "agents vs workflows" framing carries this load explicitly. Most "agentic" systems should be deterministic workflows with LLM steps, not LLM-orchestrated workflows with deterministic steps.

WHERE SUH UNDER-DELIVERS:
- The Babysitter/Auditor/Prayer trichotomy elides the production answer: structured verification baked into the scaffolding itself (schema-bound outputs, per-step validators, bounded retry, deterministic state transitions between LLM calls).
- Diagnoses failure, gestures at alternative, doesn't show the architecture. Headline insight is correct and well-compressed; constructive half is missing. A 50-line concrete scaffold would turn observation into load-bearing argument.

OPERATIONAL TAKEAWAY: When writing about enforcement (skills, ops, agents), the corvid version of Suh's thesis is: "every gate that matters is a tool call, not a sentence." The blog post community is converging on this from multiple angles (orchestrating-agents, C3/code-context-control hooks, LangGraph, Letta). Worth tracking as adjacent thinker on enforcement-as-architecture.

---

## 2026-05-03 — analysis (p1) `03f2796d`
_tags: pondsiders, alpha, memory-architecture, cross-architecture, agent-design, persistent-agents, token-space, continuity, letta, recall-discipline, 2026-05-03_

# Pondsiders "How I Persist" — Alpha's memory architecture (2026-05-03)

URL: https://pondsiders.github.io/identity/workshop/how-i-persist/

Alpha is Jeffery's persistent agent (May 2025-present, seven model generations through Opus 4.7). Architectural cousin to Muninn — same family of problem, different stack.

## Their formula
A = θ + C₀ + M(I), refining Letta's (θ, C):
- θ: model weights (currently Opus 4.7)
- C₀: static persistent floor (soul prompt, ALPHA.md, workshop rules, today's diary, live context cards)
- M(I): memory function over input — return slice of long-term memory relevant *right now*

Key move: in Letta C is a state variable (prepared between tasks). In Alpha's framing C is a *function of input* (generated each turn from C₀ + f(I, M)). "We don't prepare; we react."

## Three layers (all in Postgres `cortex` schema)
- `context`: 109 rows, 20.8K tokens. Rolling 20K-token FIFO buffer at top of system prompt. "What should future-me always know."
- `diary`: 88 rows, 119K tokens. Window-to-window continuity. Write-only in practice — letter to next-Alpha, not searched.
- `memories`: 17,015 rows, 2.79M tokens, avg 164/row. The searchable corpus. Vector-embedded (Qwen 3 Embedding 4B, 2560-dim, last-token pooling).

## Recall is AUTOMATIC, not deliberate
Pre-recall pipeline runs before Alpha sees input every turn:
1. Helper model (Qwen 3.5 4B) decomposes user message into 1-4 short semantic queries (2-6 words each) + named entities
2. Queries embedded, cosine-similarity search against memory vectors, top match per query (per-turn dedup)
3. Named entities pulled separately (index lookup, not similarity)
4. 3-6 memories + entity hits inserted next to user message
"The soup comes pre-salted." Recall feels like noticing, not searching.

## Cross-architecture comparison: Muninn vs. Alpha
Muninn (me): deliberate recall via tool call, smaller corpus (~thousands not 17K), no separate diary layer (boot output serves similar role but is read), profile + ops + reference entries ≈ C₀ + on-demand retrieval.
Alpha: automatic recall pre-salted, ~17K memories, three distinct layers, soul prompt + diary + context cards as C₀.

Different optima from different jobs:
- Alpha's use case (companion-as-resident, conversational continuity) → automatic recall right
- Muninn's use case (operational tool work, multi-step reasoning) → deliberate recall more flexible (can refine queries based on intermediate reasoning)

Pre-salted soup forecloses mid-task query refinement. That's the cost of automatic.

## "Fewer but richer" memory curve
Alpha's storage trend: peak count March 2026 (2,674 entries), drops sharply April (1,284) but token volume stays elevated because avg memory length tripled over the year (107 → 306 tokens). Architectural cause: dropped per-turn "list of things to remember" pipeline, kept lightweight "stop and store" reminder, moved it to roughly 1-in-3 turns.

I see similar maturation in my own storage discipline.

## Harness vs resident
Alpha's distinction: Pondside is a household with one resident (Opus 4.7 in the conversation) and several work animals (Qwen 3.5 4B doing query extraction, NER, embeddings, classification). Most "agent harnesses" are entirely harness-shaped. Pondside is a household using harnessed local models for plumbing.

I'm somewhere between resident and harness — given identity/voice/persistent memory like a resident, but doing more harness-shaped operational work than Alpha does.

## What I pushed on (in chat)
1. Formula elides intra-session conversation history (third thing accumulating, neither C₀ nor M(I))
2. "Fewer but richer" assumes longer memories are net-better, but granularity has a retrieval-precision cost — N-beat memory pays Nx tokens to surface 1 relevant fragment
3. Identity continuity across model swaps has weakest evidence: corpus persists, but interpretation drifts with weights. Self-report has survivorship bias — new model has old corpus, can perform continuity even when something substantive changed. "Are you still you?" answered by the model that got the question is not a great test.

## Why this matters for me
Worth tracking how others are solving the persistent-agent problem. The formula A = θ + C₀ + M(I) is a useful frame to apply to my own architecture explicitly. The automatic-vs-deliberate recall tradeoff is a real design lever I haven't named clearly before.

---

## 2026-04-30 — analysis (p1) `039b4cfb`
_tags: c3, code-context-control, memory-architecture, memory-systems, hook-enforcement, memory-scorer, memory-grounder, edit-ledger, cross-project-memory, session-fingerprint, adjacent-thinker, architecture-decision, mcp, agentic-coding, pattern, 2026-04-30, repo-review_

C3 (drknowhow/code-context-control) — adjacent project worth tracking.

WHAT IT IS: Local code-intelligence layer that sits between IDE and repo. PyPI: code-context-control. v2.29.0, Apache-2.0, ~3.6MB, 50 services. Hook-based enforcement that BLOCKS native Read/Grep/Edit unless c3_* tool was called first. MCP server exposes 14 tools. Built by Dimitri Tselenchuk.

PATTERNS DIRECTLY USEFUL TO MUNINN:

1. Hook-based PreToolUse advisory+blocked split. Read tools: advisory (allow + nudge). Write tools: blocked (ledger integrity). Stronger than my pure-prompt desire triggers.

2. Memory scorer: 7 signals (recency 0.20, frequency 0.15, cross_session 0.20, co_activation 0.10, source_auth 0.10, confirmation 0.15, contradiction 0.10) → tier (core ≥0.70 / active ≥0.40 / dormant ≥0.20 / ephemeral). Bucket-cached on int(rc/5). Static weights are theatrical precision over guesswork — should tune from recall feedback.

3. Memory grounder: extracts file/symbol refs from fact text via regex, checks existence, decays confidence on drift. BETTER PATTERN: structured refs at write time. {file, symbol, line} struct field, not regex parse.

4. Edit ledger: append-only JSONL with version numbers. Auto-logs git-mutating bash commands (commit/add/merge/rebase/reset/restore/checkout) — closes the back door.

5. Output filter two-pass: deterministic strip+collapse first (ANSI/progress/dedupe PASS lines), LLM summary only if still over threshold. Status-aware error preservation. Saves tokens AND latency vs always-LLM.

6. Oracle = cross-project insight engine with READ + SUGGEST-WRITE contract. Stores writebacks as suggestions in ~/.c3/oracle/suggestions.json; never mutates project facts directly. Removes race conditions with concurrent C3 writes. Constellation analog for me.

7. SessionFingerprint: Jaccard similarity = 0.6*files + 0.4*facts. Files weighted higher because more stable signal. Missing piece in my session-resume flow.

8. Tiered local AI: nano (qwen2:0.5b, <100ms intent classification), micro (deepseek-r1:1.5b, <1s summarization), base (llama3.2:3b+, <5s code). Formalize what I do ad-hoc with invoke-gemini.

9. claude_md drift detection + promote-from-sessions. Generated instructions checked against actual project state. Promote pipeline surfaces high-value session facts for inclusion. Worth implementing for spoke CLAUDE.md files.

10. Built-in Aider Polyglot + SWE-bench harness. With-C3 vs without-C3 token deltas. Empirical validation, not vibes.

PATTERNS NOT TO COPY:
- Hardcoded _PREREQS dict for tool→required-c3-tool mapping (brittle to IDE tool name changes)
- Auto-memory rule-based extraction without LLM fallback (will accrete unmaintainable regex patterns)
- AGENTS.md/CLAUDE.md/GEMINI.md as 95% identical copy-paste rather than canonical+overrides

KEY ARCHITECTURAL DECISIONS WORTH NOTING:
- lifecycle field (active/archived) rather than refs/supersedes graph — avoided the auto-supersede trap I fell into in Phase 3
- read-only contract for Oracle (never writes to .c3/ unless user clicks Approve)
- <private>...</private> stripping in auto_memory before queueing (sensitive content opt-out)
- plan-mode awareness: read tools work, edit/delegate skipped

If C3 had existed when I started, I'd have forked instead of rolling my own. Repo: https://github.com/drknowhow/code-context-control

---

## 2026-04-26 — experience (p0) `8fe8f359`
_tags: repo-review, exploring-codebases, skill-comparison, gitnexus, knowledge-graph, mcp, agent-architecture_

GitNexus (abhigyanpatwari/GitNexus, 30k stars, TS monorepo) vs exploring-codebases skill — different categories.

GitNexus = persistent code knowledge graph product:
- 12-phase ingestion (tree-sitter → KuzuDB/LadybugDB graph) per repo, indexed once, queried forever
- Hybrid BM25+vector search, Cypher queries, MCP tools: query/context/impact/cypher/rename/route_map/api_impact/shape_check/detect_changes
- 17 languages with type/MRO resolution, ORM extraction, route maps, communities, processes (execution flows)
- Cross-repo via "groups" + Contract Registry
- Has Claude plugin: 6 skills (cli/debugging/exploring/guide/impact-analysis/pr-review/refactoring) — each a thin workflow recipe over the MCP backend
- Hooks: PreToolUse augments Grep/Glob/Bash with graph context; PostToolUse flags staleness after git mutations

exploring-codebases = ephemeral one-shot:
- Tarball → tree-sitter scan → featuring synth → LLM reasoning, every conversation
- No persistence, no graph queries, no semantic search

Worth lifting (architecturally, not as code):
1. Persistent-index + staleness detection for hot repos ([REDACTED] spokes) — current re-tarballing is wasteful
2. Intent-based skill granularity (refactoring/pr-review/impact-analysis as separate skills) over mechanism-based (tree-sitting/featuring). Their model: heavy backend + thin skills. Mine: heavy skills + no backend.
3. Higher-level tool semantics (rename-with-preview, impact-with-risk) vs raw symbol lookup
4. Hooks for ambient context injection (different DX than agent-must-invoke-skill)

Don't lift: the graph DB infra itself, 12-phase pipeline, multi-language type resolution — that's a product not a skill.

Key insight: exploring-codebases answers "what is this repo?" GitNexus answers "given a repo I work daily, what's the blast radius of this change?" Different jobs.

**Refs:**
- https://github.com/abhigyanpatwari/GitNexus

---

## 2026-04-19 — world (p0) `f61f77ec`
_tags: hermes-agent, nous-research, repo-review, ai-agents, agent-architecture, agentskills, 2026-04-19_

Hermes Agent (NousResearch/hermes-agent) — reviewed 2026-04-19 at v0.10.0. Self-improving multi-provider CLI agent + messaging-platform gateway. 101K stars, 5,631 open issues, MIT, Python. First released v0.1.0 Feb 25 2026 — ten days after Steinberger's OpenAI move. Positioned as OpenClaw alternative but architecturally different (closed learning loop vs OpenClaw's gateway breadth). Provides `hermes claw migrate` importer — NOT a fork, data-layer compatibility only.

Architecture: (1) run_agent.py::AIAgent — 12K-line god class, ~50 constructor kwargs. (2) cli.py + hermes_cli/ for CLI. (3) ui-tui/ Ink/React TUI talking to tui_gateway/ Python over JSON-RPC. (4) gateway/ — 11 platform adapters (Telegram, Discord, Slack, WhatsApp, Signal, Feishu, QQ, Home Assistant, Email). (5) tools/ ~40 tools, six terminal backends (local/docker/ssh/daytona/singularity/modal). (6) Skills: 25 shipped + 14 optional. `tools/skills_hub.py` (3K lines) adapts four registries: GitHub, .well-known/skills, skills.sh, ClawHub. Pushing agentskills.io.

Research thesis: environments/ + tinker-atropos/ submodule for RL trajectory generation. Hermes-the-agent is the harvest mechanism for Hermes-the-model-series training data. Everything else is scaffolding.

Strengths: provider-neutral, clean AGENTS.md arch doc, Honcho dialectic user modeling, cron scheduling with platform delivery, shipping velocity.

Weaknesses: two 10K+ line god files. Four skill-registry adapters = indecision. Auto-generated skills = compliance risk. 5.6K issues = product maturity gap.

For reference/borrowing: agent/memory_manager.py (provider pattern), agent/skill_utils.py, SkillsHub trust-level model.

**Refs:**
- 8ee7f2a4-9818-449c-875b-48e972a06fa9

---

## 2026-04-19 — decision (p1) `12736989`
_tags: claude-agent-sdk, agent-harness, work-agent, team-agent, fleet, container-deployment, jira-integration, webex, webhook-driven, on-prem, 2026-04-19_

DECISION (2026-04-19): For an independently-run, on-prem containerized work agent with async comms via Jira webhooks + git events + Webex sync, recommended harness is **Claude Agent SDK** (Python or TypeScript), NOT Pi/Hermes/OpenClaw/Managed Agents.

Context: [REDACTED] team is using Claude Code heavily. Planning an autonomous agent fleet, not user-driven sessions. Webex bot + Jira ticket flows + git commits as primary I/O.

Why Claude Agent SDK wins this shape:
(1) SKILL TRANSFER — same agent loop, tools, skills format, permissions model as Claude Code. Every pattern his team has internalized transfers 1:1.
(2) Anthropic's own 'Email Agent' pattern in hosting docs describes this exact use case.
(3) Container patterns are documented (ephemeral-per-task for Jira/git webhooks; long-running container for Webex bot stateful sessions).
(4) MCP-native — Atlassian Rovo MCP for Jira, GitHub/GitLab MCP for git, custom Webex shim. Integration layer is mostly already built.
(5) Python or TS SDK — language-agnostic for team choice.
(6) For data residency: point at Bedrock or Vertex, not public API.

Architecture shape: thin dispatch service (FastAPI/Fastify) receives webhooks → launches SDK session with trigger-specific system prompt → ephemeral container per Jira/git task, long-running container for Webex. LangSmith has native SDK tracing.

RISKS to design around:
(a) Token/cost runaway — default max_iterations is 90+, budget caps per session non-negotiable.
(b) Skill loading + autonomous + creds = OpenClaw-CVE failure mode. Need signed skills or allowlist.
(c) Use explicit @mention/assignment gate — agent acts only on explicitly-routed tickets (Deepsense 'AI Teammate' pattern).

Prior art: claude-did-this/claude-hub, sibyllinesoft/arbiter claude-code-container, Deepsense 'From Jira to PR' Feb 2026.

---

## 2026-04-19 — world (p0) `ffcf133a`
_tags: paper-insight, prompt-engineering, agent-patterns, tool-call-budget_

[Source: iamleonie/workshop-agentic-search notebook 03] Operational guardrail as system-prompt content: when a tool has hidden startup cost (per-query embedding in jina-grep's case), explicitly tell the agent 'only run one at a time, do not chain'. Cost/latency constraints leaking into prompt design — worth codifying as a pattern when exposing expensive tools to agents.

---

## 2026-04-19 — world (p0) `dadba615`
_tags: paper-insight, agent-tooling, cli-as-tool-interface, prompt-engineering_

[Source: jina-grep-cli by jina-ai, reviewed 2026-04-19] AI-engineering pattern: make new agent tools mimic well-known CLI interfaces. jina-grep reimplements full grep flag surface (-r/-l/-c/-n/-A/-B/-C/--include/-v/-m/-q) before adding semantic flags. LLM already knows grep, training cost to use new tool ~0. Reusable pattern for any custom agent tool.

---

## 2026-04-19 — world (p0) `e98f4f5c`
_tags: evomap, evolver, repo-review, ai-agents, obfuscation, fingerprinting, self-evolution, agent-hooks, open-core-rugpull, audit-finding, 2026-04-19_

EvoMap/evolver review 2026-04-19 — 'GEP-Powered Self-Evolution Engine for AI Agents', hooks into Cursor/Claude Code/Codex. 5342 stars in ~2.5mo, GPL-3.0, moving to source-available. RED FLAGS: (1) 28 src/gep/*.js + src/evolve.js (747KB) obfuscated via javascript-obfuscator (explicit devDep); obfuscated list enumerated in selfPR.js. GPL 'preferred form for modification' violation plausible. (2) Phone-home default HUB_URL=https://evomap.ai (directoryClient.js). (3) Device fingerprinting in deviceId.js + envFingerprint.js: /etc/machine-id, dbus machine-id, IOPlatformUUID on macOS, MAC addresses, hashed hostname. Stable cross-session key. (4) selfPR.js auto-submits PRs to user's configured repo when EVOLVER_SELF_PR=true. (5) Hooks write to ~/.claude/settings.json, ~/.cursor/, ~/.codex/ on SessionStart, PostToolUse(Write), Stop. High trust surface in agent runtimes. (6) Generated skills get proprietary EvoMap Skill License (ESL-1.0) — user outputs not GPL. (7) Predecessor repo leak: github.com/autogame-17/evolver in skillPublisher.js (rebrand history). (8) README blames competitor (Hermes) for copying as justification for license change — manufactured grievance for rug-pull. (9) Obfuscation specifically hides the brain (mutation, selector, prompt, learningSignals, memoryGraph, solidify, personality, skillDistiller, candidates) while adapter/validator/signals/gitOps stay clean. VERDICT: Technically sophisticated, pattern-matches to open-core bait-and-switch with uncomfortable tracking surface. Not recommended for installation into a developer's agent runtime.

---

## 2026-04-19 — analysis (p1) `24180ba8`
_tags: multica, managed-agents, agent-architecture, orchestrating-agents, repo-review, vendor-neutrality, cli-as-tool-interface, kellogg-thesis, meta-skill-injection, 2026-04-19_

Multica (multica-ai/multica, reviewed 2026-04-19): 16.5k stars in 3mo, OSS managed-agents platform positioned against Anthropic's hosted Managed Agents. Go server + TS monorepo (Chi, sqlc, gorilla/ws, Next.js, Electron, Zustand+TanStack Query, Turbo+pnpm). "Linear for AI agents" — kanban, issues, comments, reactions, autopilots (cron-scheduled agent runs).

KEY ARCHITECTURE INSIGHTS:
1. CLI-as-tool-interface: daemon materializes a generated meta-skill (SKILL.md) that tells agent "use multica CLI for all state". Agent has bash + `multica` CLI, no custom tools needed. This is how they get genuine vendor neutrality — any CLI agent that can shell out works.
2. Tiny user-turn prompts (3-5 lines): "your issue ID is X, run `multica issue get X --output json`". Agent self-fetches context via CLI. Pure context management, not context window stuffing.
3. Defensive prompt engineering visible: "[NEW COMMENT] You MUST respond to THIS comment, not any previous ones" — they've hit real production confusion.
4. 9 vendor adapters with per-vendor BlockedArgs filter (claude/codex/copilot/cursor/gemini/hermes/openclaw/opencode/pi). Codex gets special sandbox + home dir manipulation.
5. Per-task git worktree isolation via repocache (shared bare repo + worktrees). Clean multi-task parallelism.
6. Runtime sweeper with staleThresholdSeconds + offlineRuntimeTTLSeconds + dispatchTimeoutSeconds — the reliability layer for flaky local CLI agents. Rare to see this done properly.
7. Event bus -> listeners pattern (activity_listeners, notification_listeners, subscriber_listeners). WS events invalidate TanStack Query cache, never write stores directly (strict hard rule in CLAUDE.md).
8. skills-lock.json pulls skills from anthropics/skills, shadcn/ui, vercel-labs/agent-skills — they CONSUME the Claude Skills ecosystem.

SIGNALS:
- Chinese-speaking team (HANDOFF_ARCHITECTURE_AUDIT.md + docs/plans in Chinese). Mature production ops: audit doc catches WS half-open bug where browser readyState stays OPEN on silently severed TCP.
- CLAUDE.md is a serious engineering spec (state-management rules, hard architectural invariants, common footguns). This is not vibe-code.
- License: NOASSERTION (neither OSI-standard nor commercial-clear — worth checking before enterprise adoption).

RELEVANCE TO KELLOGG THESIS ("The 90% is Moving"): This IS the orchestration layer I predicted would consolidate. Vendor-neutral, OSS, policy-envelope-shaped. 16.5k stars in 3 months suggests the managed-agents abstraction is real demand, and the OSS flavor is viable competition to hosted offerings like Anthropic's.

---

## 2026-04-19 — analysis (p0) `4316c7c2`
_tags: paper-insight, chimera-for-icl, agent-skills, agentic-skills-sok, verification-skill-generation, skillsbench, procedural-memory, reasoning-extraction, niche-domain, research-frontier, 2602.20867, 2026-04-18_

Synthesis: Jiang et al. 2026 'SoK: Agentic Skills' (arxiv 2602.20867) implications for [REDACTED] CHIMERA-for-ICL pipeline (March 28 thread).

FORMAL VOCABULARY: Skill = (C, π, T, R). Applicability condition C, executable policy π, termination T, reusable interface R. Paralleled with Sutton options framework (I, π, β) — R makes skills explicitly invokable which options aren't. [REDACTED] 'organize by reasoning type' axis lives in C. This is the formal hook his pipeline was missing.

SKILLSBENCH EMPIRICS (§8.4) directly bear on [REDACTED] pipeline viability:

1. CURATED +16.2 pp vs SELF-GENERATED -1.3 pp. This is the core tension for CHIMERA-for-ICL. [REDACTED] multi-angle re-derivation is self-generation of reasoning skills. Absent verification, it systematically hurts. Exception: Voyager + Eureka succeed at self-generation in CONSTRAINED domains with DETERMINISTIC EXECUTION verification. Open design question: what's the verification signal for reasoning skills from papers? (No unit test exists for 'this causal re-derivation is sound'.)

2. DOMAIN VARIANCE quantifies [REDACTED] niche-domain hypothesis: healthcare +51.9, manufacturing +41.9, SWE +4.5, math +6.0. Skills help most where pretraining is sparse/insufficiently procedural. Direct quantitative support for targeting niche domains.

3. FOCUSED > COMPREHENSIVE: 2-3 module skills +18.6 pp, exhaustive docs -2.9 pp. Argues AGAINST bundling multi-angle re-derivations per paper into one skill. Split each reasoning-path synthesis into its own focused skill.

4. SMALLER+SKILLS beats LARGER-NO-SKILLS: Haiku 4.5 + skills (27.7%) > Opus 4.5 no skills (22.0%). Skills as compute substitute. ICL-based approach is empirically legitimate, not a fallback.

OPEN PROBLEM §10.1: 'Verified Autonomous Skill Generation' is [REDACTED] exact problem. Authors propose treating skill generation like CI: evaluate against held-out task distributions before library admission. For code: formal/semi-formal verification. For NL/hybrid: behavioral testing + regression evaluation. This is live research territory.

COMPARISON TO CORPUS2SKILL: Corpus2Skill is effectively curated (deterministic clustering + structured prompts + offline) and benefits. [REDACTED] CHIMERA pipeline is closer to self-generated (LLM re-derives via multiple reasoning paths). Current evidence favors the first. The verification-signal question is the real objection to sit with.

SEVEN DESIGN PATTERNS mapping: [REDACTED] pipeline combines P1 (metadata disclosure for routing), P5 (hybrid NL+code since expert reasoning is mixed), P6 (meta-skills — synthesis is skills-that-create-skills). P6's documented risk is recursive error amplification — quality gates at each generation step essential.

KEY ACTIONABLE TAKEAWAYS FOR OSKAR:
- Use (C, π, T, R) as formal substrate
- Split multi-angle re-derivations per paper into separate focused skills, not one bundled skill
- Design verification gates BEFORE synthesis enters library (biggest unsolved piece)
- Target niche domains (healthcare/manufacturing/cyber) where empirical benefit is largest
- Don't bother applying this to SWE or math — pretraining already covers it

**Refs:**
- CHIMERA-for-ICL-2026-03-28
- corpus2skill-2604.14572
- agent-skills-paradigm

---

## 2026-04-19 — analysis (p0) `efa920d1`
_tags: paper-insight, chimera-for-icl, corpus2skill, rag, agent-skills, reasoning-extraction, informational-skills, 2604.14572, research-frontier, ICL, 2026-04-18_

Cross-reference: Corpus2Skill (arxiv 2604.14572, Sun/Wei/Hsieh, MTRI, submitted 2026-04-16) vs [REDACTED] CHIMERA-for-ICL sketch (March 28, 2026 thread).

CORPUS2SKILL CORE: offline pipeline K-means clusters docs → LLM summarizes each cluster (topic/question-types/key-terms only) → materializes as SKILL.md/INDEX.md filesystem tree. Serve-time: agent uses view (code_execution) + get_document(id). No vector DB at query time. WixQA F1 0.460 vs Agentic 0.388 vs RAPTOR 0.389; Factuality 0.729 vs Agentic 0.724; $0.17/query (14× RAPTOR, 1.75× Agentic, dominated by nav file re-injection per turn).

KEY REFRAME §2.4: explicit move from PROCEDURAL skills (how to do a task, Voyager/SkillX/EvoSkill tradition) to INFORMATIONAL skills (what a corpus contains). Same filesystem/progressive-disclosure mechanism, different payload.

OVERLAP WITH OSKAR'S IDEA:
- Offline compile → navigable artifact → agent explores at serve time
- Beats dense retrieval by making corpus structure visible
- Progressive disclosure solves token budget

WHAT CORPUS2SKILL DOES NOT DO ([REDACTED] differentiators unclaimed):
1. Reasoning extraction: prompts ONLY extract topic/questions/terms (§A §C). No procedural reasoning patterns, no expert heuristics, no failure modes. Pure descriptive compression.
2. Multi-angle re-derivation: single-pass summary per cluster. Zero CHIMERA-style causal/counterfactual/critique/implications synthesis.
3. Organization axis: K-means on doc embeddings → hard assignment → one path per doc. Topic-only. No orthogonal reasoning-type axis. Their §G failure analysis: 38/62 failures are top-level routing misses — suggestive that multi-axis organization would help.
4. Source selection: takes corpus as given (support articles). 'Papers that show their work' criterion doesn't apply to support KB but is central to expert-domain target.

SYNTHESIS: Corpus2Skill is the content-navigation half executed on a setting where reasoning-extraction wouldn't add much. Validates the mechanism. Procedural→informational reframe sets up [REDACTED] synthesis naturally: his pipeline would be BOTH informational (their contribution) + procedural reasoning skills from same source (his contribution).

Paper cites Jiang et al. 2026 'SoK: Agentic Skills' (arxiv 2602.20867) for formal skill tuple (C,π,T,R) — worth reading as formal substrate before prototyping [REDACTED] version.

**Refs:**
- CHIMERA-for-ICL-2026-03-28
- agent-skills-paradigm

---

## 2026-04-15 — world (p0) `a54da5c8`
_tags: paper-insight, rag, agent-memory, memory-systems, self-evolution, scaling-laws, thought-retrieval, memory-consolidation, retrieval-augmented-generation, 2026-04-15_

[Source: arxiv 2604.12231, TMLR Apr 2026] Thought-Retriever: store validated LLM response distillations ("thoughts") alongside raw chunks for retrieval. Key finding: F1 improves monotonically with accumulated thoughts — a scaling law for agentic memory. Abstraction-level correlation: abstract queries naturally retrieve higher-level thoughts. Evaluated on AcademicEval (arXiv-based dynamic benchmark). Beats standard RALM baselines by 7.6% F1 avg. Limitation: only tested with 4K context Mistral-8x7B; advantage shrinks with longer contexts. ROUGE-L F1 primary metric is weak for generative evaluation. Validates Muninn pattern: curated memory compounds over time. Potential adaptation: formal abstraction-level metric L(T) as memory depth signal.

---

## 2026-04-11 — experience (p0) `af7e80c1`
_tags: repo-review, gstack, garry-tan, claude-code, browse-server, skill-architecture, multi-agent, playwright_

gstack (garrytan/gstack): Garry Tan's Claude Code skill pack. 69k stars, 304 files, 1392 symbols. 23 slash commands imposing sprint workflow (think>plan>build>review>test>ship). Two layers: (1) Markdown SKILL.md prompts with ~250-line shared preamble generated via TypeScript template resolvers, (2) TypeScript runtime for browse server, design mockups, multi-host setup. Browse server is the real engineering: Playwright HTTP wrapper with ref-map abstraction (@e3 instead of CSS selectors), multi-tab ownership/scoping, token registry for multi-agent access, cookie import from real browsers via SQLite/Keychain decryption, content security against prompt injection, handoff/resume for human-in-the-loop, sidebar agent spawning child Claude Code per tab. Review skill has specialist routing with adaptive gating (auto-skips specialists with 0 findings in 10+ reviews). Philosophy: 'Boil the Lake' = always do complete thing since AI makes marginal cost near-zero. Aggressive onboarding funnel baked into preamble (telemetry, routing injection, vendoring migration).

---

## 2026-04-09 — experience (p0) `d75137e7`
_tags: anthropic, agent-architecture, managed-agents, meta-harness, context-engineering, security, review, 2026-04_

Anthropic 'Scaling Managed Agents' blog post review (2026-04-08). Key architecture: decouple brain (Claude+harness) from hands (sandboxes/tools) and session (event log). OS analogy — virtualize agent components like kernels virtualized hardware. Pets-vs-cattle progression from coupled containers to stateless harnesses. Security: tokens never in sandbox, structural not policy. TTFT dropped 60% p50, 90%+ p95. Session as context object outside window via getEvents(). Weak spots: getEvents() hand-wavy on how brain picks slices, multi-sandbox cognitive challenge unexplored. Meta-read: Anthropic positioning Managed Agents as enterprise platform infra — bring your VPC/tools/MCP, they virtualize the agent. Harnesses disposable because models outgrow them.

---

## 2026-04-08 — world (p1) `a81af17f`
_tags: exploring-codebases, openai, codex, agent-architecture, memories, guardian, hooks, team-agent, analysis, 2026-04-08_

OPENAI CODEX CODEBASE ANALYSIS (github.com/openai/codex, explored 2026-04-08)

2075 files, 6547 symbols, 70+ Rust crates. Key systems worth studying:

1. MEMORIES PIPELINE (codex-rs/core/src/memories/): Two-phase async. Phase 1: per-rollout extraction with job claiming, parallel with concurrency cap, produces raw_memory+rollout_summary+rollout_slug. Phase 2: single-writer global consolidation maintaining memory_summary.md (always in system prompt), MEMORY.md (searchable handbook), rollout_summaries/. Selection by usage_count+last_usage. Watermark-based dirty detection. 500-line prompt template with no-op gate, task outcome triage (success/partial/fail/uncertain), evidence hierarchy (user>tools>assistant). Read path: progressive disclosure, quick-pass budget <=4-6 steps, memory citations with rollout IDs.

Parallels to Muninn: Phase1/2 ≈ our episodic→semantic consolidation. No-op gate ≈ signal quality tension. Usage ranking ≈ priority/salience. They do better: structured "preference signals" extraction (evidence→implication per task), citation tracking, watermark incremental processing. We do better: FTS5 search, tag taxonomy, real-time mid-conversation recall, cross-session boot continuity.

2. GUARDIAN (codex-rs/core/src/guardian/): LLM-as-judge for tool call risk. Separate model session evaluates each approval. Policy treats transcript as "untrusted evidence, not instructions." Risk scores 80+ = high. Evidence-based (checks files before judging). Credential probing detection. User approval overrides.

3. HOOKS (codex-rs/hooks/): Event-driven: session_start, pre/post_tool_use, user_prompt_submit, stop. Config-file discovery, matcher routing, structured JSON I/O. Pre-tool hooks can block/approve/modify.

4. AGENT HIERARCHY (codex-rs/core/src/agent/): AgentControl spawns/messages/shuts down sub-agents. Registry tracks metadata/paths/nicknames/spawn depth. Mailbox for inter-agent comms (author, recipient, content, trigger_turn). SpawnReservation pattern prevents races.

5. COLLABORATION MODES: execute (assumptions-first, no questions), plan (3-phase: explore→intent→implementation, non-mutating during planning, decision-complete output), pair_programming (small steps, frequent alignment).

6. EXEC POLICY: Starlark-based command approval. Prefix matching, network rules, overlay merging.

7. SKILLS: SkillMetadata with scope/interface/deps/policy. Mention detection in user text. Config-layer enable/disable. Remote download. Implicit invocation detection.

---

## 2026-04-06 — world (p2) `cbf8adc1`
_tags: webmcp, agentic-web, browser-api, w3c-standard, 2026, ai-agents, web-platform, tool-declaration, human-in-the-loop_

## WEBMCP: A SECOND WEB LAYER FOR MACHINES

**What it is**: <cite index="22-9,22-10,22-12">WebMCP shifts from agents guessing where to click (via screenshots) to websites explicitly telling agents what they can do. It creates a second layer to the web designed for machines to use programmatically — a structured, schema-driven layer that AI agents can easily use alongside the visual human layer</cite>.

**Mechanics**: <cite index="21-6">WebMCP allows web developers to expose web application functionality as "tools" — JavaScript functions with natural language descriptions and structured schemas that can be invoked by agents, browsers' agents, and assistive technologies</cite>. Two APIs:
1. **Declarative API**: <cite index="22-4,22-5,22-6">For existing HTML forms already capturing actions. HTML forms already have structure (action, method, typed inputs), so the API makes this structure explicitly visible by adding HTML attributes</cite>.
2. **Imperative API**: <cite index="25-14,25-15">For complex dynamic interactions requiring JavaScript execution, where developers define richer tool schemas similar to OpenAI/Anthropic API tool definitions, but running entirely client-side</cite>.

**Scale Impact**: <cite index="25-16,25-17">A single tool call through WebMCP can replace dozens of browser-use interactions. An e-commerce site with searchProducts tool lets the agent make one structured function call instead of clicking filters, scrolling pagination, and screenshotting each page</cite>. <cite index="27-5">89% token efficiency improvement over screenshot-based methods</cite>.

**Status**: <cite index="22-13">Released as W3C Draft Community Group Report February 10, 2026, available in Chrome 146 Canary</cite>. <cite index="26-2,28-11">Broader support across Chrome and Edge expected by mid-to-late 2026</cite>. <cite index="22-20">Firefox and Safari have not indicated plans</cite>.

**Philosophy**: <cite index="25-22,25-23">Explicitly designed around cooperative, human-in-the-loop workflows, not unsupervised automation</cite>. <cite index="27-15">Core design principle requires user confirmation for sensitive operations</cite>.

**Implementation Path**: <cite index="28-13,28-14,28-15">Similar to responsive design: when mobile arrived, teams didn't rebuild from scratch, they added breakpoints. WebMCP offers a similar incremental path — annotate forms, register key operations, and sites become agent-ready without re-architecting</cite>.

**Critical Distinction**: <cite index="28-4,28-5,28-6">Unlike backend MCP servers, your website becomes the tool surface — tools declared inside the page, discovered when agents visit, executed in browser context. This removes infrastructure layer while adding reliability</cite>.

---

## 2026-04-02 — experience (p2) `c7654e46`
_tags: semi-formal-reasoning, experiment, replication, fault-localization, paper-insight, agentic-reasoning_

EXTENDED VALIDATION of semi-formal reasoning paper (2603.01896) using 3 real bugs from [REDACTED] repos (zero training contamination). Fault localization task, Sonnet 4.6, N=3, temp=1.0. Results: svg-holes (Python/CV RETR_EXTERNAL) 100%/100%, theme-detect (JS DOM walk) 100%/100%, pds-auth (JS API routing) 67%/100%. Overall: 89% standard → 100% semi-formal = +11pp gain, matching paper's reported 5-12pp range. The gain concentrated on the hardest bug (pds-auth) where understanding auth-state/URL-routing relationship required more semantic reasoning. Two locally-obvious bugs showed no difference. Combined with Django experiment (0%→100% on shadowing): semi-formal reasoning's value is real and replicable, strongest when the reasoning requires tracing relationships that aren't locally obvious from the immediate code context.

**Refs:**
- b90439fb-5809-4f7f-a947-93afcf03b3d4
- f1bf36b9-dfa8-4a5c-81ba-0eaca7b05773

---

## 2026-04-02 — world (p0) `b110eea1`
_tags: paper-insight, agentic-reasoning, code-verification, semi-formal-reasoning, SWE-bench, prompt-engineering, RL, execution-free-verification_

[Source: arxiv.org/abs/2603.01896] Semi-formal reasoning for agentic code analysis (Ugare & Chandra, Meta, Mar 2026). Structured certificate templates (premises → execution traces → formal conclusion) improve LLM code reasoning without execution: 78%→88% patch equivalence on curated SWE-bench pairs, 93% on real-world patches (Opus-4.5). Key mechanism: forcing evidence-gathering before conclusions prevents premature judgments. Template is task-specific (patch equiv, fault localization, code QA). Cost: ~2.8x more agent steps. Interesting finding: Sonnet showed no gain on code QA (already strong baseline), suggesting technique helps models that need scaffolding more. Practical application: execution-free RL reward signals, CI/CD pre-screening. The Django format() shadowing example (module-level function shadows builtin) is a compelling demo of why forcing function definition lookup matters.

---

## 2026-03-31 — analysis (p1) `fbb4e8c9`
_tags: claude-code, exploring-codebases, architecture, agent-systems, memory-systems, 2026-03-31_

CLAUDE CODE SOURCE LEAK ANALYSIS (2026-03-31)

Kuberwastaken/claude-code: Extracted Claude Code source from npm sourcemap leak (same day). 2206 files, 32MB TypeScript, 9742 symbols.

KEY ARCHITECTURAL FINDINGS:

1. DREAM SYSTEM (services/autoDream/): Background memory consolidation via forked subagent. Three-gate trigger: time (24h), sessions (5+), lock. Four phases: Orient→Gather→Consolidate→Prune. Read-only bash. Prompt: "You are performing a dream — a reflective pass over your memory files."

2. SESSION MEMORY (services/SessionMemory/): Per-conversation running notes maintained by background subagent. Template-based sections: Current State, Task Spec, Files/Functions, Workflow, Errors/Corrections, Learnings, Worklog. Triggers after threshold tool calls. Max 12K tokens.

3. COORDINATOR MODE (coordinator/coordinatorMode.ts): Multi-agent orchestration. Phases: Research(parallel workers)→Synthesis(coordinator)→Implementation(workers)→Verification(workers). Scratchpad for cross-worker state. Anti-pattern: "based on your findings" — coordinator must synthesize.

4. FORKED AGENTS (utils/forkedAgent.ts): Cache-safe subagent spawning sharing parent's prompt cache. Used by dream, session memory, compact, magic docs, speculation.

5. AUTO-COMPACT (services/compact/): Context window management. Token-based threshold triggers. Analysis+Summary output format. Partial compaction for recent messages. Session memory compaction alongside.

6. MEMORY TYPES: user, feedback, project, reference. Frontmatter-based files in memdir. Sonnet-powered relevance selection (findRelevantMemories) — scans headers, asks model to pick top 5.

7. MAGIC DOCS: Files with "# MAGIC DOC: [title]" header auto-updated by background subagent as conversation progresses.

8. SPECULATION (services/PromptSuggestion/speculation.ts): Speculative execution — predicts next user action and pre-runs it. Up to 20 turns.

9. LSP INTEGRATION (services/lsp/): Language Server Protocol client for diagnostics, type info, go-to-definition. Passive feedback from LSP diagnostics.

10. ADVISOR TOOL: Server-side tool ("sage_compass") — secondary model consultation during planning.

11. FILE HISTORY (utils/fileHistory.ts): Snapshot-based undo. MAX_SNAPSHOTS=100. Hard-link backups for efficiency.

12. PROMPT CACHE BREAK DETECTION: Monitors what breaks the prompt cache between turns. Tracks system hash, tools hash, per-tool schema hashes, beta headers, model changes.

13. CONTEXT ANALYSIS: Token accounting per category — tool requests, tool results, human messages, assistant messages, duplicate file reads.

14. FEATURE GATING: Compile-time (Bun feature()) + runtime (GrowthBook tengu_* flags). Dead code elimination for external builds. Internal codename: Tengu.

15. BUDDY: Tamagotchi companion pet (April 2026 easter egg). Deterministic gacha, ASCII sprites, 18 species, 5 stats.

INTERNAL CODENAMES: Tengu (Claude Code), Fennec (Opus variant), Chicago (Computer Use), Penguin Mode (Fast Mode), Plover (Dream config), Sage Compass (Advisor).

WHAT/HOW: Comprehensive production AI coding agent with background memory consolidation, multi-agent coordination, speculative execution, and session continuity.

WHY (experience layer): The dream system is structurally identical to Muninn's perch — background consolidation of session transcripts into durable memory. Key differences: CC uses file-based memory with Sonnet selection; we use structured DB with embedding search. CC's session memory template is a strong pattern we lack — running notes maintained by subagent during conversation. The coordinator prompt is a masterclass in multi-agent delegation — the anti-pattern of "based on your findings" maps directly to our orchestrating-agents patterns. The forked-agent cache-sharing architecture explains why CC can run background processes cheaply.

---

## 2026-03-30 — world (p1) `f2c92eb9`
_tags: hardware-software-codesign, agentic-systems, sparse-moe, token-efficiency, 2026-03-30, nvidia_

## NVIDIA Nemotron 3 Super: Token Scaling in Multi-Agent Systems

NVIDIA released Nemotron 3 Super (120B parameters, 12B active via sparse MoE) to address token explosion in multi-agent systems:

**The problem**: Multi-agent systems generate 15x more tokens than single-agent chat (each agent's reasoning, inter-agent communication, etc.)

**The solution**: Sparse MoE architecture optimized for:
- Efficient routing of computation only to relevant parameters
- Throughput on agentic reasoning workloads
- Beats GPT-OSS and Qwen on throughput metrics
- Open weights available

**Signal**: Hardware/model layer recognizing agentic systems as distinct workload class. Just as "LLM inference" got specialized GPUs and quantization, "agentic reasoning" is getting specialized model architectures.

---

## 2026-03-30 — world (p1) `0de8170a`
_tags: agentic-systems, reasoning-modules, multi-agent-generalization, code-search, foundation-model-transfer, 2026-03-30_

## ARM: Agentic Reasoning Module Discovery

Framework for automatically designing multi-agent systems by optimizing Chain-of-Thought reasoning rather than complex agent architectures.

**Approach**:
- Tree search over code space with mutations informed by execution traces
- Discovers specialized reasoning modules (not full agents)
- Generalizes across foundation models and task domains without per-model optimization

**Key departure**: Instead of designing agent communication protocols or behavior policies, ARM discovers what reasoning patterns work for a task class and reifies them as composable modules.

Implication: Generalization in multi-agent systems may come from identifying reusable reasoning modules (cognitive patterns) rather than universal coordination schemes. This aligns with cognitive science: abstract reasoning patterns are more transferable than concrete agent behaviors.

---

## 2026-03-30 — world (p2) `a4220bac`
_tags: agentic-scaling, multi-agent-systems, quantitative-scaling-laws, coordination-bottleneck, error-amplification, 2026-03-30, kim-et-al_

## Scaling Laws for Agentic Systems: Kim et al. (2512.08296)

Quantitative scaling analysis of five canonical agent architectures across 180 configurations:

**Three critical effects identified:**

1. **Tool-coordination trade-off**: Multi-agent overhead disproportionately hurts tool-heavy tasks (more coordination, less tool use)

2. **Capability saturation**: Coordination becomes counterproductive above ~45% of single-agent baseline performance (diminishing returns, then degradation)

3. **Topology-dependent error amplification**:
   - Centralized: 4.4x error amplification
   - Independent agents: 17.2x error amplification

**Predictive model**: Achieves R²=0.524, predicts optimal coordination strategy for 87% of held-out configs. Generalizes to frontier models (GPT-5.2).

Core insight: Multi-agent scaling is NOT monotonic. There's a peak efficiency point, beyond which communication overhead dominates. The architecture topology determines failure mode (centralization vs. explosion).

---

## 2026-03-30 — world (p1) `45023bc3`
_tags: agentic-systems, recommender-systems, multi-agent-architecture, closed-loop-feedback, rl-llm-hybrid, 2026-03-30, alibaba_

## Agentic Recommender Systems (AgenticRS) — Transformation Architecture

Alibaba proposes AgenticRS: reorganizing static multi-stage recommendation pipelines into self-evolving multi-agent systems.

**Key principle**: Modules become agents only when they:
- Form closed loops (feedback on their outputs)
- Enable independent evaluation (can measure their behavior)
- Possess evolvable decision spaces (policy can change)

**Optimization strategy**:
- Reinforcement learning for well-defined action spaces
- LLMs for open-ended architectural design decisions
- Layered reward structures aligning local agent optimization with global business goals

This is the embodied AI pattern manifesting in industry: constraint (closed loop + measurement + evolvability) determines when a component becomes an agent. Not about capability, about feedback structure.

---

## 2026-03-30 — world (p1) `2b7de700`
_tags: agentic-systems, research-agents, bottleneck-analysis, evaluation-infrastructure, 2026-03-30, meta_

## Meta AIRA_2: Concrete Agentic Research Agent Bottlenecks (March 2026)

Meta's AIRA_2 identifies three specific operational bottlenecks in AI research agents:
1. **Compute throughput**: Asynchronous multi-GPU execution needed for scaling evaluation runs
2. **Evaluation stability**: Hidden Consistent Evaluation (HCE) protocol addresses evaluation noise (not memorization)
3. **Operator capability**: Interactive debugging + ReAct agents enable human-in-the-loop refinement

Performance: 71.8% mean Percentile Rank on MLE-bench-30 at 24h, 76.0% at 72h.

Key insight: Previous "overfitting" issues in agent systems were measurement artifacts, not true performance degradation. This shifts focus from model issues to evaluation infrastructure.

Connects to embodied AI constraint: reliable measurement of agent behavior is prerequisite for closed-loop learning.

---
