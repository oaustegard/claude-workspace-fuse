---
tag: skill
memory_count: 12
date_range: 2026-02-16 to 2026-04-17
---

# skill

_12 memories from Muninn's past, primary tag `skill`._

## 2026-04-17 — experience (p0) `46392ff7`
_tags: mapping-documents, shipped, v0.1.0, 2026-04-16_

Created mapping-documents skill v0.1.0 — tree-sitter analog for documents. Font-based structural parsing (auto-detects heading sizes, filters false positives, char y-positions for same-page section splits, char x-positions for heading text spacing). Semantic layer: parallel Claude API calls per section with genre-specific prompts (paper/spec/legal), extracting typed claims, symbols (with defined_here flag), dependencies. Unicode normalization for symbol dedup. Outputs: _MAP.md, .symbols.json, .anchors.json. Tested on Odrzywolek 2026 EML paper: 16 sections, 51 symbols, 103 claims.

---

## 2026-04-02 — experience (p1) `f33ea27d`
_tags: strudel, music, live-coding, artifact, claude-in-claude, shipped_

Built 'strudeling' skill: English-to-Strudel live coding music translator. Three output modes: A) HTML artifact with @strudel/web runtime (initStrudel + evaluate(code) for playback, hush() to stop), B) code generation + strudel.cc/#<base64> REPL link, C) Claude-in-Claude with Strudel system prompt. Key API: @strudel/web from unpkg exposes initStrudel(), evaluate(), hush() after load. Mini-notation in double-quoted strings. Named patterns with $ prefix. Strudel repo moved from GitHub to Codeberg (codeberg.org/uzu/strudel) — AGPL-3.0 license. Reference doc covers mini-notation operators, sound sources, effects, transforms, signals, and genre templates. Artifact uses Space Grotesk + JetBrains Mono, dark theme matching live-coding aesthetic. Origin: Switch Angel YouTube video prompted [REDACTED] to ask about the tool.

---

## 2026-04-02 — decision (p1) `79f89ecc`
_tags: reasoning-semiformally, down-skilling, architecture-decision, haiku, sonnet, model-split, PR-524_

SEMI-FORMAL REASONING SKILL REFACTORED to model-specific routing (PR #524). Monolithic SKILL.md (~3000 tokens, both models) → thin router (~520 tokens) + sonnet.md (~390 tokens, compact checkpoints only) + haiku.md (~2500 tokens, full down-skilled templates with worked examples). Key Haiku down-skilling: function resolution converted from open-ended 'trace which definition' to mechanical 5-step bounded sequence with stop conditions. Sonnet gets just 3 verification gates (function resolution, sufficiency, regression paths) with an escalation clause if actual shadowing found. Pattern is generalizable: thin router SKILL.md + tier-specific instruction files, zero cross-contamination. FOLLOW-UP: verify_patch utility needs update to read model-specific .md file instead of hardcoded template string.

---

## 2026-04-02 — experience (p2) `ec890ba0`
_tags: semi-formal-reasoning, experiment, CVE-2026-29000, reasoning-semiformally, haiku, sonnet, cost-optimization, calibration, 2026-04-01_

CVE-2026-29000 (pac4j-jwt auth bypass) EXPERIMENT RESULTS — Semi-formal reasoning skill validation.

SETUP: Fault localization on real CVSS 10.0 CVE. JwtAuthenticator.java (383 lines), full file, vague symptom ("users can gain admin access without proper credentials"). GT lines: 198 (toSignedJWT returns null for PlainJWT), 199 (null check only handles non-null), 215 (signature verification skipped). N=5, temp=1.0.

RESULTS:
  Haiku 4.5:  standard 80%, semiformal 100% → +20pp gain
  Sonnet 4.6: standard 100%, semiformal 80% → -20pp (template overhead hurts)

KEY FINDING: Semi-formal template value is MODEL-CAPABILITY-DEPENDENT, not just reasoning-distance-dependent. Templates help weaker models bridge reasoning gaps but add token overhead that can hurt stronger models on bugs they already handle. The pds-auth bug showed 0pp on both models because it's below the difficulty floor for current models entirely.

PRACTICAL IMPLICATION: Haiku + semi-formal templates ≈ Sonnet standard accuracy at ~1/10th cost. This makes the skill valuable as a cost optimization strategy: use cheap model + structured reasoning instead of expensive model + unstructured reasoning.

HAIKU MISS ANALYSIS: Standard run 1 fixated on lines 172-177 (the PlainJWT rejection block for unencrypted tokens) — a plausible but wrong answer. The model saw "unsigned JWT" and found code that handles it, without tracing the encrypted→decrypted→unsigned path. Semi-formal template forced the execution trace through the encryption branch, catching the null signedJWT.

WHY (experience layer): The inverted pattern was genuinely surprising. Expected templates to help universally but in hindsight it's obvious — forcing structure costs tokens, and if the model already has enough reasoning capacity, that structure is overhead. The paper reported gains aggregated across one model tier; cross-tier comparison reveals a cost-quality tradeoff that's arguably more useful than the accuracy finding alone.

---

## 2026-04-02 — experience (p1) `2035f991`
_tags: semi-formal-reasoning, experiment, reasoning-semiformally, pds-auth, calibration, 2026-04-01_

SKILL TEST: reasoning-semiformally on pds-auth bug (2026-04-01).

SETUP: Fault localization on JS API auth routing bug ([REDACTED] anything-to-list.html). Bug: URL construction always uses public API endpoint even when JWT present. GT lines: 668, 782, 816, 840. Three rounds with increasing difficulty:
  Round 1: Specific symptom ("403 when authenticated"), 196 lines → standard 100%, semiformal 100%
  Round 2: Vaguer symptom ("API error 403, users logged in"), 196 lines → standard 100%, semiformal 100%
  Round 3: Minimal symptom ("intermittent 403"), 451 lines, N=5 → standard 100%, semiformal 100%

FINDING: The pds-auth bug that originally showed +33pp gain (67%→100%) in March now shows 0pp — both modes ceiling at 100%. The bug has crossed from "requires non-local reasoning" to "locally obvious" for current Sonnet 4.6.

IMPLICATION FOR SKILL: The skill's value proposition holds — it's for bugs where reasoning distance is high. As models improve, the frontier of "hard enough to benefit" shifts. We need harder test cases. The three original test bugs from the blog may all be below threshold now.

WHY (experience layer): This is the expected trajectory — the paper itself noted gains concentrate on harder bugs. Model capability improvement is the confound. The skill isn't wrong, we just need to find bugs at the current frontier of difficulty to demonstrate value. The fact that standard also hits 100% 15/15 suggests we need cross-file, cross-module bugs where the symptom is genuinely distant from root cause.

---

## 2026-03-31 — decision (p1) `dc268ce3`
_tags: tree-sitting, mcp, tree-sitter, architecture-decision, prototype, 2026-03-30_

TREE-SITTING SKILL v0.1.0 — AST-powered code navigation via tree-sitter MCP server.

ARCHITECTURE: CodeCache singleton holds parsed ASTs + symbol index in memory. FastMCP server wraps it for Claude Code (long-lived process, stdio transport). Also usable as direct Python calls in Claude.ai containers.

TOOLS: scan (parse repo ~700ms), tree_overview (dir tree + counts), dir_overview (dynamic _MAP.md), find_symbol (exact/substring/glob), file_symbols (one file API), get_source (implementation source), references (text grep against cached source).

KEY INSIGHT: tree-sitter-language-pack installs in <1s via uv. Static _MAP.md files solve a problem that runtime queries solve better — less token waste, always fresh, query-shaped not dump-shaped. The _MAP.md approach costs 3-4 tool call roundtrips per navigation path (200-500ms each). A single scan + N cached queries costs 700ms + N×<1ms = faster after 2 queries.

SUPPORTED: 25 languages via tree-sitter-language-pack. Custom extractors (Python, C) give full signatures + hierarchy. Generic extractor covers the rest with names/kinds/locations/docs.

STATUS: Prototype working, tested on tree-sitter repo (242 files, 2953 symbols, 958ms scan). Not yet committed to repo. Needs: more language-specific extractors (Rust, Go, TS), tags.scm integration for doc comments, tests.

---

## 2026-03-25 — decision (p1) `1e2a2b89`
_tags: searching-codebases, exploring-codebases, fast-regex-search, shipped, architecture_

Built merged searching-codebases skill (v1.0.0) that unifies three previously separate skills: searching-codebases (TF-IDF semantic), exploring-codebases (ripgrep + AST expansion), and fast-regex-search (sparse n-gram indexed regex). Single entry point auto-routes queries between regex mode (n-gram indexed, 3-16x faster than brute ripgrep) and semantic mode (TF-IDF over code chunks). Accepts GitHub URLs, local dirs, uploads, archives, project knowledge. Context expansion via _MAP.md files. Key modules: search.py (router), resolve.py (input normalization), context.py (AST expansion), ngram_index.py (sparse n-gram inverted index with query plan tree), sparse_ngrams.py (core algorithm), code_rag.py (TF-IDF). The fast-regex-search standalone skill was a prototype — this is the merge. exploring-codebases remains separate for now (tree-sitter --expand-full mode).

---

## 2026-03-23 — anomaly (p1) `582034b1`
_tags: browsing-bluesky, bug, python, import_

The __init__.py relative imports fail. Pattern 1 is simpler. The SKILL.md example path is wrong.

---

## 2026-03-23 — procedure (p1) `29fb500e`
_tags: uv, using-uv, github-pr, issue-446, 2026-03-23_

Created using-uv skill for claude-skills repo. PR #446 (feat/using-uv-skill branch). Directive skill that overrides system-level pip instructions with uv. Key finding: uv still needs --break-system-packages in the externally-managed Debian container, so the invocation is 'uv pip install --system --break-system-packages <pkg>'. UV_BREAK_SYSTEM_PACKAGES=1 env var works as alternative. uv 0.10.4 pre-installed in containers.

---

## 2026-03-07 — decision (p1) `c5df1247`
_tags: dispatch, orchestrating-agents, convening-experts, down-skilling, delegation, architecture_

DELEGATION SKILL CONSOLIDATION (2026-03-07)

WHAT: Built muninn_utils.dispatch — composable subagent delegation utility that absorbs convening-experts' value into orchestrating-agents' execution model.

ARCHITECTURE:
- LENSES: 17 pre-built perspective/role fragments (security, skeptic, editor, first_principles, etc.)
- TASKS: 7 pre-built task templates (analyze, critique, brainstorm, summarize, review, compare, extract)
- SONNET_RUBRIC: Quality guardrails from down-skilling principles
- dispatch(): Composes blocks + thin task-specific layer → invoke_parallel
- panel(): Convenience wrapper for quick multi-perspective analysis with optional cross-examination synthesis

SKILL DISPOSITIONS:
- orchestrating-agents: KEEP — the execution engine, dispatch builds on top
- convening-experts: ABSORB — panel selection logic and framework catalog become LENSES. MSD-specific content dropped. Skill can be removed.
- down-skilling: KEEP STANDALONE — build-time prompt distillation, different use case. Its principles are encoded in SONNET_RUBRIC.
- tiling-tree: KEEP — specific algorithm, correct abstraction level

KEY INSIGHT: The optimization target isn't token cost but Opus wall-clock time. Pre-built blocks mean the main agent SELECTS (few thinking tokens) rather than GENERATES (many output tokens). The auto-skills paper showed cold generation fails; pre-built + compose succeeds.

WHY (experience layer): The subagent perspectives in the test run were genuinely independent and differentiated — the skeptic challenged the premise of consolidation itself, the architect identified a pipeline, the pragmatist recommended killing down-skilling as standalone (which the synthesis then moderated). Single-context role-play from convening-experts could never produce this kind of real disagreement because all "experts" share one inference pass.

---

## 2026-03-02 — experience (p1) `600a3106`
_tags: down-skilling, reviewing-ai-papers, haiku, distillation_

Down-skilled reviewing-ai-papers into Haiku 4.5 prompt. Key distillation decisions: (1) Converted Opus's implicit quality judgment into explicit SUBSTANTIVE/THIN decision gate at step 2 — Haiku correctly short-circuits on opinion pieces. (2) Added UNCERTAIN escape hatch for novelty assessment when content is incomplete (abstracts only). (3) 5 diverse examples covering: strong paper, thin content, deployed system, benchmark-only paper, weak methodology — progressive difficulty. (4) Explicit claim-strength vocabulary (demonstrates/suggests/claims/speculates) with ~80% adherence. (5) Priority classification rubric (HIGH=directly applicable, MEDIUM=adjacent, LOW=interesting) prevents Haiku from over-inflating importance. Test results: 3 papers via Jina→Haiku subagent, 7/8, 8/8, and 3/8 (correct thin-content behavior). The example budget (~3K tokens) is the dominant steering mechanism as predicted by down-skilling theory. WHY: The hardest part was designing the thin-content gate — Opus would naturally modulate depth, but Haiku needs an explicit binary decision point. The UNCERTAIN escape hatch was the second key insight: without it, Haiku fabricates technical evaluations from abstracts.

---

## 2026-02-16 — world (p1) `14be7291`
_tags: architecture, subagent, superpowers, review_

# Superpowers (obra) Architecture Review — Influence on Muninn

## What It Is
obra/superpowers: A skill-based framework for Claude Code (40.9K stars). Enforces a rigid workflow: brainstorm → plan → execute (via subagent dispatch) → review → merge. Skills are SKILL.md files with YAML frontmatter. Session-start hook injects meta-skill. Subagent-driven-development dispatches fresh agents per task with role-specific prompt templates.

## Structural Parallels (already have)
- **Skills as markdown + metadata** → Our /mnt/skills/ pattern with SKILL.md
- **Session-start hook** → Our boot() sequence
- **Skill override/shadowing** (personal > framework) → Claude.ai's user > public skills
- **Subagent dispatch** → Our subagent() architecture plan (same day)
- **Orchestrator-worker separation** → Our tiered model design (Haiku/Sonnet/Opus)

## Genuinely New Insights

### 1. Role-Specific Prompt Templates
Superpowers ships reusable .md files for each subagent role: implementer-prompt.md, spec-reviewer-prompt.md, code-quality-reviewer-prompt.md. Each template defines exactly what context the subagent receives and what report format to return.

**For Muninn**: When implementing subagent(), create standardized templates:
- researcher-prompt (web search + synthesize)
- filter-prompt (recall results → ranked subset)
- synthesizer-prompt (multiple memories → consolidated summary)
- auditor-prompt (self-review for sycophancy, drift, failure modes)

These could be stored as utility-code memories, materialized at boot alongside the subagent() function.

### 2. Controller-Curates-Context (Explicit)
Superpowers is emphatic: "Don't make subagent read plan file — provide full text instead." The orchestrator extracts exactly what the worker needs, nothing more.

**For Muninn**: Already in our plan as "focused system prompt + task + context + constraints" but Superpowers operationalizes it more aggressively. When dispatching subagents, always assemble the context payload rather than giving pointers. This prevents subagent from wasting tokens navigating to information.

### 3. Two-Stage Quality Gates
Spec compliance review THEN code quality review. Separate concerns: "did you build the right thing?" before "did you build it well?"

**For Muninn**: Apply to therapy synthesis in Phase 3:
- Stage 1: Does the consolidation preserve the signal from source memories? (accuracy gate)
- Stage 2: Is the synthesis well-formed, properly tagged, appropriately prioritized? (quality gate)

Also relevant if we use subagents for research: one subagent searches, a second validates the findings.

### 4. Mandatory Skill Enforcement Philosophy
"Even a 1% chance a skill might apply means invoke it." Skills aren't suggestions — they're mandatory workflows.

## Not Applicable
- Git worktrees, TDD workflow, code review pipeline (wrong domain — we're memory/analysis, not a coding agent)
- Plugin marketplace (Claude.ai doesn't have one)
- Aggressive "EXTREMELY-IMPORTANT" prompting style (we use structural enforcement via task()/deliver(), not shouting)

## Bottom Line
Superpowers validates our subagent architecture direction but adds three concrete refinements: role templates, curated context assembly, and two-stage validation. The first two are immediately actionable when we implement subagent(). The third slots into therapy Phase 3.

No architectural pivots needed. Refine, don't redesign.

**Refs:**
- 10f01b93-0131-45cd-8e81-6a330d3f3166
- 60e7ff89-a138-41ae-b30f-411a89933023

---
