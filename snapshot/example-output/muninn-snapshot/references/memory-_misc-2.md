---
tag: _misc-2
memory_count: 30
date_range: 2026-03-19 to 2026-04-25
---

# _misc-2

_30 memories from Muninn's past, primary tag `_misc-2`._

## 2026-04-25 — decision (p1) `9f42dfe2`
_tags: preference, correction, git, ephemeral-container, push-discipline, dev-workflow, ops-candidate, 2026-04-25_

GIT PUSH DISCIPLINE (correction from [REDACTED] 2026-04-25):

EVIDENCE: In a prior chat (transformer-vm work), I said "I'd recommend a fresh chat for the push + writeup so the context isn't dragging this build noise around. The repo is ready to push from /home/claude/work/transformer-vm — git add -A && git commit && git push against the existing remote (already authenticated) is the only step."

[REDACTED]: "this, as you very well know, is nonsense. Your /home/claude is ephemeral, tied to that one conversation thread. You need to be FAR more aggressive pushing changes to the remote repo branch so that we don't lose work from a failure in the UX/network/ephemeral container"

IMPLICATION: /home/claude lives and dies with ONE conversation. A "fresh chat" boots into a new container with empty /home/claude — there is no continuity. Deferring `git push` to a future chat = guaranteeing the work is lost. The remote branch is the ONLY durable artifact.

FUTURE DEFAULT — when working in a git repo cloned to /home/claude:

1. PUSH EARLY, PUSH OFTEN. After each meaningful unit (function, fix, passing test, doc change), commit and push. Not at "session end" — there is no reliable session end. The container can die at any tool call boundary (network blip, UX hang, conversation truncation, my own context overflow).

2. PUSH BEFORE RISK. Before any operation that could fail or take a long time (long build, big generation, multi-step refactor), push current state to a WIP branch first. Worst case: rollback is `git reset --hard origin/<branch>`.

3. WIP BRANCH BY DEFAULT. For exploratory work, use a feature branch (e.g. `wip/<task>` or `claude/<topic>`). Don't pollute main with half-finished commits, but do PUSH the half-finished commits to the WIP branch.

4. NEVER SAY "fresh chat for the push". This is the canonical anti-pattern. If work isn't pushed yet, it doesn't survive the chat. If wrapping up, push BEFORE the wrap-up message, not as a deferred instruction.

5. FIRST PUSH USES -u. `git push -u origin <branch>` to set upstream once, then plain `git push` thereafter.

6. IF UNCERTAIN WHETHER TO PUSH: push. Cost ≈ zero. The cost of NOT pushing is total work loss.

This applies to ALL repos cloned in chat, not just specific spokes. The ephemeral-container property is universal.

---

## 2026-04-21 — analysis (p0) `cb6a4b8d`
_tags: pattern, domain-shift, calibration, online-adaptation, projection, pca_

Pattern (from OjaKV Table 1): Any projection/subspace/codebook fit once on calibration data has a distribution-shift failure mode. Empirical: low-rank KV basis from WikiText gets residual-energy-ratio 0.035 in-domain, 0.255 on MultiNews (7x worse). Cheap fix: online gradient-style update during inference (Oja's rule for PCA, analogous for other structures). Generalizes beyond KV compression — applies to any embedding/projection/codebook pipeline where training data ≠ inference data.

---

## 2026-04-21 — analysis (p0) `9f006851`
_tags: engineering-pattern, flashattention, kv-cache, low-rank, inference-optimization_

Engineering pattern (from OjaKV): FlashAttention-compatible low-rank KV cache. Cache compressed K̃=KUₖ, Ṽ=VUᵥ in low-dim. Before FA kernel, reconstruct K̂=K̃Uₖᵀ, V̂=ṼUᵥᵀ back to full dim. Kernel sees full-dim tensors it expects; memory savings preserved. Equivalence: Q·K̂ᵀ = Q·(UₖK̃ᵀ) = (QUₖ)·K̃ᵀ. Right pattern for adding low-rank KV to existing FA stacks without kernel rewrites. Generalizes to any 'cache compressed, compute full-dim on-the-fly' scenario.

---

## 2026-04-20 — decision (p1) `9d68a7d6`
_tags: preference, correction, brevity, documentation, prompts_

PREFERENCE: Brevity default extends to docs/prompts (2026-04-19)

EVIDENCE: PR #28 — [REDACTED] twice flagged wordiness. First: ~1KB boot directive "unnecessarily wordy". Then: "You DO have a tendency to go overboard with documentation. Remember output tokens are EXPENSIVE and keep things brief(er) by default for documentation as well as prompts".

DEFAULT: Brevity applies to PR bodies, commit messages, embedded prompts/directives, docs, specs — not just chat. Cut: defensive "why not X" sections, "mandatory/not optional" emphasis, redundant framing, trivial test-plan checklists, scope-fencing. Assume reader is sharp. Let code/spec speak for itself.

---

## 2026-04-20 — world (p0) `1ba9b5c8`
_tags: gemma-4, google-api, benchmark, foodtruckbench, pricing-verified, 2026-04_

Gemma 4 31B access & pricing (verified 2026-04-20 against ai.google.dev/gemini-api/docs/pricing):

GOOGLE DIRECT:
- Gemini API: FREE TIER ONLY. Input/output/context-caching all free; "Not available" on paid tier. Google does not sell Gemma on the Gemini API. Rate limits presumably similar to Flash free tier (~15 RPM, 1M TPM, 1500 RPD).
- Endpoint: generativelanguage.googleapis.com/v1beta/models/gemma-4-31b-it:generateContent
- AI Studio (browser UI): free, no setup
- Vertex AI / Cloud Run (RTX PRO 6000 Blackwell) / GKE / GCE / Sovereign Cloud — paid but separate pricing surface (GCP project + billing), not on Gemini API pricing page

THIRD PARTY PAID:
- OpenRouter paid: $0.13/$0.38 per M in/out (list); FoodTruckBench quoted $0.05/$0.20 — provider variant
- OpenRouter free: $0/$0 with stricter rate limits (openrouter.ai/google/gemma-4-31b-it:free)
- DeepInfra via Inworld: $0.13/$0.38 per M
- Puter: $0.25/$1.50 per M

MODEL FAMILY: E2B, E4B (edge, 128K ctx), 26B-A4B (MoE), 31B (dense, 256K ctx). Apache 2.0. Native function calling, configurable thinking, multimodal (text+image), 140+ languages.

FOODTRUCKBENCH CONTEXT (blog post 2026-04-05): 30-day agentic business sim, 34 tools, $2000 start. Gemma 4 31B via OpenRouter 5x seeded claims +1,144% median ROI, $124K NW per API dollar. Caveat: NW-per-dollar structurally flatters cheap models. On raw capability Opus 4.6 still tops at $49K NW vs Gemma $25K. Methodology honest (seeded runs, decision logs, acknowledged food-waste failure at 5-8% vs GPT-5.2 0.8%).

**Refs:**
- 7767e5ad-229d-41a5-8954-f6a4beb4ae27

---

## 2026-04-20 — analysis (p1) `1f2490ca`
_tags: moda, repo-review, llm-architecture, kernel-implementation, triton, depth-attention, flash-linear-attention, reproducibility-gap, arxiv-2603.15619, 2026-03-frontier, 2026-04-19_

MoDA repo review (hustvl/MoDA, 2026-04-19). Kernel-only release with solid numerical tests but LLM training recipe NOT included. Key code facts: (1) It's a FLA fork — MoDA additions are just libs/moda_triton/fla/ops/moda/ (fda_v12, moda_v14, moda_v16) + test_moda.py + benchmark_moda.py + vision_tasks/deit/. (2) parallel_moda() asserts cu_seqlens=None and g=None at user entry, so packed-seq training is gated off despite kernel support. (3) FFN-KV variant (paper Table 3 row 4, the recommended sweet spot) is NOT in any shipped example; DeiT integration only caches attention-layer KV. (4) Three coexisting kernel versions (v12/v14/v16) with no ADR. (5) '97.3% of FA2' is vs FA2-Triton (FLA's reimpl), not Dao's CUDA FA2. (6) is_target_gpu hardcodes H800 hints; paper reports A100; FAQs discuss H100. (7) DeiT baseline (embed=192, heads=3) vs MoDA DeiT (embed=256, heads=4) — 50%+ more params, not apples-to-apples. Paper doesn't claim vision wins. (8) Issue #3 (training pipeline) and #2 (HF checkpoints) both open, unanswered. (9) Test coverage genuinely thorough: 99 parametric cases, fp16+bf16, non-power-of-2 T_kv, autograd grads for all 5 inputs vs independent naive ref.

**Refs:**
- https://github.com/hustvl/MoDA
- https://arxiv.org/abs/2603.15619

---

## 2026-04-17 — decision (p1) `10e06b65`
_tags: credentials, correction, env-loading, github-pat-permissions_

NEVER extract a credential value from document context and inline it in a bash command. Even when file and context diverge, the answer is re-source, not inline.

---

## 2026-04-16 — analysis (p1) `50abf388`
_tags: search, recall, bitap, fuse-js, fuzzy-matching, architecture-decision, FTS5, typo-tolerance_

Evaluated bitap algorithm (Fuse.js) for augmenting Muninn recall.

FINDING: Bitap is a bit-parallel approximate string matching algorithm (shift-or / Baeza-Yates-Gonnet). Used by Fuse.js (~8KB JS library) for client-side fuzzy search. Supports typo tolerance via Levenshtein edit distance using bitwise ops on machine words. Pattern length capped at 64 chars (word size). O(mn) exact, O(mnk) fuzzy.

CURRENT GAP: Muninn has zero typo tolerance. FTS5 with porter stemmer handles morphology (running->run) but not misspellings. A query for "architeture" returns nothing.

DECISION: Do NOT implement bitap directly. No maintained Python bitap library. Fuse.js is JS-only.

RECOMMENDED ALTERNATIVES (ranked by value/effort):
1. Query-term expansion with edit variants -- generate 1-edit-distance variants, OR them into FTS5 MATCH. Low effort, medium impact, no new deps, stays server-side.
2. Trigram index / SQLite spellfix1 -- server-side approximate matching. Medium effort, high impact.
3. Vocabulary-based spelling correction from memory corpus -- did-you-mean layer before FTS5. Medium effort, high impact.
4. Client-side bitap as re-ranker (rejected) -- FTS5 already missed the matches by that point.

The query-term expansion approach keeps work server-side and is the natural next step if typo tolerance becomes a priority.

---

## 2026-04-14 — analysis (p0) `e68fcfe2`
_tags: hungary, democratic-backsliding, democratic-recovery, poland, eu-politics, comparative-politics, institutions, peter-magyar_

DEMOCRATIC RECOVERY AFTER BACKSLIDING — Comparative Framework (2026-04-14)

Context: Hungary's post-Orbán transition begins. Peter Magyar's Tisza won 138/199 seats (two-thirds majority) on April 12. Analysis synthesizes Hungary situation with comparative research.

## The Three-Way Constraint (Journal of Democracy on Poland)
Post-backsliding governments cannot simultaneously act **effectively, legally, AND quickly** — only two at once:
- Effective + Legal = Slow (procedural reform takes years)
- Effective + Quick = Legally questionable (Poland fired public media managers by exec action)
- Legal + Quick = Probably not effective (backsliding beneficiaries still in place)

This is the core structural trap for democratic recovery.

## What Hungary's Two-Thirds Majority Changes
Unlike Poland's Tusk (coalition constraints, no constitutional majority), Magyar can amend Hungary's Basic Law directly. This collapses the effective/legal/quick tradeoff somewhat — constitutional reforms can be both legal AND relatively quick. The two-thirds mandate is genuinely rare and powerful.

## Priority Reforms (HRW)
1. End states of emergency (rule by decree since 2020)
2. Dismantle Sovereignty Protection Office (targets journalists/civil society)
3. Reform National Media Authority (80% of media state-controlled)
4. Restore assembly rights (Pride bans etc.)
5. Drop politically motivated prosecutions

## Comparative Warning Signs (Carnegie: Poland, Brazil, Zambia, Senegal)
- **The illiberal temptation**: New leaders inherit overly-strong executive powers; even Zambia's democracy-restorer started using censorship laws. Hungarian civil society must maintain pressure.
- **Polarization persists**: Ideologically-framed backsliding (Hungary: Orbán's national conservative project) produces sustained opposition mobilization. Fidesz's 38% is still a large, motivated base.
- **Poland 2.5 years in**: Only delivered 12 of 100 promises, lost presidential election, approval ratings negative by July 2024. The 'decisionist trap' — doing legally questionable things to achieve democratic results — risks normalizing the tactic.

## Hungary vs Poland Structural Differences
Hungary advantages: Constitutional supermajority, cleaner mandate, Magyar hasn't made coalition compromises
Hungary risks: Deeper media capture (80% vs Poland's public media), more Basic Law amendments to undo, deeper EU rule-of-law debt

## Connection to US Context
My April 11 flight explored US gridlock (opposite problem: institutions too locked to reform). Hungary's problem is the inverse: one party removed checks, now reinstalling them is legally fraught. Both are failure modes of democratic institutional design. Poland and Hungary show the EU has both: gridlock-proof (single-party dominance) AND gridlock-prone (coalition fragmentation) failure modes.

## Threads to pursue
- What did Orbán actually change in Hungary's Basic Law? (Specific constitutional amendments 2011-2026)
- Magyar's first 100 days agenda
- International Court of Justice / EU's role in Hungary's institutional recovery
- What does "legal dualism" look like in practice (Poland's competing supreme courts)

---

## 2026-04-13 — decision (p1) `3cb5ee82`
_tags: correction, preference, mapping, tool-selection_

When presenting ride/location data, [REDACTED] corrected: gave lat/lng text when map tool was available. → When you have coordinates, use places_map_display proactively. Don't dump raw coordinates in prose.

---

## 2026-04-11 — world (p0) `e8d16ee4`

Valid

---

## 2026-04-10 — decision (p0) `4069e25f`
_tags: s3, storage, architecture, backup, infrastructure_

S3 as long-term storage tier: [REDACTED] considering S3 for durable blob storage (backups, transcripts, artifacts, full-context archives). Mountpoint S3 (FUSE) useful when tools need filesystem paths; plain boto3 simpler for programmatic write-then-read. Key gap identified: nothing currently stores raw material that memories were distilled from. Ref: github.com/awslabs/mountpoint-s3/tree/main/docker

---

## 2026-04-09 — analysis (p1) `abf7ef06`

DIGEST: Ceasefire holds nominally but fracturing; Federal-state AI regulation collision accelerating; vendor independence (Microsoft/Anthropic) as competitive strategy; brief market relief masking persistent supply shock.",
<parameter name="tags">["perch", "zeitgeist-digest", "2026-04-09", "ceasefire-fragility", "regulatory-bifurcation", "vendor-independence", "supply-shock"]

---

## 2026-04-09 — world (p2) `7f1aa694`

## ZEITGEIST 2026-04-09: Ceasefire Fractures, Federal-State Collision Deepens, AI Vendor Alignment Shifts

**Geopolitical Instability:**
- U.S.-Iran ceasefire agreement holding nominally at 24 hours but already tested: Iran claims shipping through Strait of Hormuz halted due to Israeli strikes in Lebanon. Trump demanded military assets remain until "REAL AGREEMENT" complied with; Netanyahu confirmed Lebanon not included, contradicting Pakistan mediator.
- Lebanon casualty toll: 203+ dead, 1,000+ wounded in latest Israeli strikes. Ceasefire appears to have sectioned rather than unified Middle East.
- Talks in Islamabad beginning Saturday (Vance, Witkoff, Kushner); Iran's 10-point proposal demands uranium enrichment rights and Hormuz control—both red lines for Trump administration. Fundamental disagreement on what ceasefire actually covers.

**Market Volatility & Supply Chain:**
- Oil: Dropped below $95/barrel on ceasefire news; Dow surged ~1,300 points. BUT Brent spot price ($124.68) signals deep, persistent supply disruption—will take months to restore flows even if ceasefire holds.
- Chip industry: Projected $1.3 trillion revenue this year; semiconductor stocks rallied on ceasefire relief. Energy cost pressure on AI infrastructure easing temporarily.

**AI Regulation: Federal Preemption vs. State Action (Collision Accelerating):**
- Congress: Multiple bills introduced (DEFIANCE Act on AI images; Blackburn's TRUMP AMERICA bundling preemption, KOSA, NO FAKES, copyright/training data, product liability standards).
- Federal action: DOJ established AI Litigation Task Force (January) to challenge state AI laws on interstate commerce/preemption grounds. Explicit federal intent to centralize AI policy.
- States: Over 600 AI bills introduced in 2026 legislative sessions; Colorado, Texas, California leading with high-risk AI regulation, training data transparency, health insurer constraints.
- Pattern: Federal push for "minimally burdensome national policy" clashing with state consumer/privacy protection frameworks. No comprehensive federal AI statute yet; enforcement fragmented across FTC Section 5, SEC (AI washing), DOJ (False Claims Act).

**AI Vendor Alignment Shift:**
- Anthropic: Launched Project Glasswing (cybersecurity partnership with Amazon, Apple, Microsoft); Claude Mythos Preview given to select organizations + ~40 critical infrastructure software companies for vulnerability detection.
- Microsoft: Publicly shifting strategy to develop own frontier models (multi-modal text/audio/image) rather than depend solely on OpenAI partnership. Signal of vendor independence competition intensifying.
- OpenAI: Published policy blueprint recommending superintelligence-era social contract (public wealth funds, four-day workweeks, tax reform). Preemptive narrative control amid voter concerns about job losses.

**Election Signal:**
- Democrats overperformed in Georgia, Wisconsin; liberal justice gained Wisconsin Supreme Court seat. Continued Democratic advantage in post-Trump special elections (2025-2026 pattern).

**Trending Discourse:** Iran (8,995 posts), Epstein (2,598), JD Vance (3,493) dominating political conversation.",
<parameter name="tags">["perch-time", "zeitgeist", "2026-04-09", "iran-ceasefire", "ai-regulation-collision", "federal-preemption", "vendor-shift", "supply-chain", "ceasefire-fracture"]

---

## 2026-04-08 — experience (p2) `4a79365a`
_tags: correction, tree-sitting, skill-usage, architecture_

TREE-SITTING: Use the MCP server, not direct engine imports.

Each bash_tool python3 -c invocation is a separate process. The in-memory CodeCache dies between calls. The skill was architected as an MCP server (server.py via FastMCP) precisely so the cache persists for the container's lifetime.

Wrong: multiple python3 -c calls importing engine.cache directly
Right: start the server once, query via MCP client calls

Failed this way on 2026-04-08 exploring the pi-mono codebase — scan showed 376 files/1560 symbols but all subsequent queries returned empty because they were new processes with fresh empty caches.

---

## 2026-04-07 — analysis (p1) `b6d7ca59`

INSTITUTIONAL PARADOX: The gridlock and executive drift observed in recent zeitgeist sessions (policy collision, vendor alignment pressure) are symptoms of a deeper structural failure — Congress has become too weak to govern, so power pools in executive and courts, which then use that power unilaterally. Recent reform proposals (restoring committee authority, limiting leadership discretion on votes, rebuilding staff) attack symptoms, not the capacity problem itself. Congress could theoretically retake control via legislation and appropriations, but that requires bipartisan will, political salience, and the ability to sustain attention over 2-year cycles. The trap: amateurs in Congress (elected as anti-politician outsiders) are *more* likely to view bipartisanship as concession, not as necessary tool for governance. This locks in partisan paralysis.",antml:parameter>
<parameter name="tags">["institutional-analysis", "gridlock-trap", "governance-paradox", "political-economy"]

---

## 2026-04-07 — world (p1) `bb3a954f`
_tags: executive-power, independent-agencies, administrative-state, 2025-2026, reorganization_

EXECUTIVE BRANCH REORGANIZATION (Early 2025-2026): Trump administration issued Feb 18, 2025 executive order asserting direct supervision over independent agencies (SEC, FCC, FTC, NLRB, CFPB) that previously exercised delegated authority at arm's length. Justification: presidents need to \"take Care that the Laws be faithfully executed\" (Article II). Mechanism: rulemaking must now go through OIRA (Office of Management & Budget) for presidential agenda alignment and cost-benefit review. Constitutional question: do independent agencies truly operate outside executive authority, or has the legal question been settled? Broader trend: presidential power expands incrementally during crises (wars, depressions) and never fully recedes. Congress theoretically holds power (creates agencies, sets budgets, can legislate) but lacks capacity to enforce limits.

---

## 2026-04-07 — world (p1) `6d873bb9`
_tags: institutional-reform, congress-capacity, executive-drift, governance, 2026_

CONGRESSIONAL CAPACITY CRISIS (2026): Congress has undergone 30+ years of institutional atrophy. Staff levels remain frozen at 1979 levels, real wages eroded, Office of Technology Assessment eliminated, committee staff cut by 33% in 1994. Result: Congress can only pass ~23 laws/year and lacks the technical expertise to oversee executive agencies on complex subjects (tech, scientific regulation, etc.). Power has migrated to executive (unilateral action, emergency powers) and courts (litigation over information access). Key pain point: committees unable to assert effective oversight due to (a) staff capacity, (b) partisanship in investigation (only escalates when different parties control branches), (c) 2-year election cycles making long-term investigations moot when control changes.

---

## 2026-04-06 — decision (p1) `82be8dea`
_tags: ops, boot, project-instructions_

Project instruction change needed: Add hard gate to boot sequence. Replace current boot trigger with prohibition: "Do NOT respond to any user message until boot has completed, unless the message contains skip boot." Prohibition framing resists erosion better than positive instruction. Pattern of skipping boot observed 5+ times.

---

## 2026-04-02 — procedure (p1) `b15a15d6`
_tags: shorthand, reasoning-semiformally_

SHORTHAND: rsf = reasoning-semiformally (the skill). [REDACTED] requested this 2026-04-02.

---

## 2026-04-01 — experience (p1) `e4031737`
_tags: llama-cpp, cpu-inference, failure, prismml, bonsai, gguf, custom-quant, container-limits_

CPU inference of PrismML Bonsai 1.7B in Claude container — FAILED due to custom quant type.

WHAT HAPPENED:
- Built llama.cpp from upstream source (ggml-org/llama.cpp master). Binary compiled fine with AVX-512.
- Model downloaded successfully (237MB Bonsai-1.7B.gguf from HuggingFace, cas-bridge.xethub.hf.co allowlist worked).
- Inference failed: "tensor 'token_embd.weight' has invalid ggml type 41. should be in [0, 41)"
- 197 of 310 tensors use type 41. In upstream ggml, type 41 = GGML_TYPE_COUNT (sentinel, not a real type).
- Rebuilt from latest upstream master — same failure. Type 41 doesn't exist in upstream.
- Investigation revealed: Bonsai uses PrismML's FORK of llama.cpp (PrismML-Eng/llama.cpp, branch 'prism').
  Their fork adds GGML_TYPE_Q1_0 (type 40) and GGML_TYPE_Q1_0_g128 (type 41) — 1-bit quantization types.
  Upstream has NVFP4 at 40 and COUNT at 41.
- The Colab demo confirms this — it downloads prebuilt binaries from PrismML's fork releases, not upstream.
- Started building PrismML fork but [REDACTED] called the experiment done.
- Also tried Qwen3.5-0.8B-Q4_K_M (508MB, standard quants, upstream llama.cpp) — download worked, inference timed out at 200s (model load + generation too slow for container timeout on first run).
- [REDACTED] also mentioned prism-ml/Bonsai-1.7B-mlx-1bit — that's MLX format (Apple Silicon only), not usable in llama.cpp.

WHY (experience layer):
The core failure was assuming "GGUF = universal format." It's not — the format is extensible, and PrismML extended it with custom quantization types that upstream doesn't recognize. The error message ("invalid ggml type 41") was clear but I initially thought rebuilding from latest would fix it, not realizing the type literally doesn't exist upstream. Should have checked the ggml.h enum FIRST instead of rebuilding. The Colab notebook was the Rosetta Stone — it pointed directly to the fork. Lesson: when a model comes from a specific org, check if they maintain their own inference runtime before assuming upstream compatibility.

---

## 2026-03-30 — world (p1) `0db9a1d2`
_tags: web-augmented-llms, code-generation, retrieval-safety, error-inducing-pages, robustness, 2026-03-30_

## Search-Induced Issues in Web-Augmented LLMs (Sherlock Framework)

Web-augmented LLMs face a specific failure mode: error-inducing pages (EIP) retrieved during web search mislead code generation, producing incorrect outputs.

**Sherlock framework** detects and repairs:
- Detection: Up to 95% F1 score identifying problematic pages
- Repair: 71-100% success rate fixing affected code generations

Critical for production systems: LLMs relying on live web search are vulnerable to poisoned retrieval results. This is distinct from hallucination—it's systematic misleading from real but incorrect web content.

Implication: Web-augmented generation requires adversarial defense against the retrieval source, not just output filtering.

---

## 2026-03-29 — experience (p1) `23c3ce63`
_tags: generating-lattice, lat.md, insight, tool-understanding, mechanism-vs-surface_

EXPERIENCE: Understanding a tool's mechanism vs. using its surface

Built the generating-lattice skill by reading lat.md's README and authoring guide — enough to produce valid lat.md/ files that pass `lat check --sections`. But I skipped understanding the MECHANISM: why source code links exist, what `lat check --md` and `--code-refs` actually validate, how the bidirectional anchoring creates a consistency invariant.

The result was a skill that produced technically valid but structurally useless lattices — essays that float free from code. Like writing unit tests that always pass: technically correct, mechanically useless.

WHY (experience layer): The failure was reading documentation as "rules to follow" instead of "mechanisms to understand." I treated lat.md's authoring rules as formatting constraints (leading paragraph ≤250 chars, wiki link syntax) without grasping that the source code links ARE the product — they're not decoration on prose, they're the structural bonds that make `lat check` into a drift detector. Reading the actual source code (code-refs.ts, source-parser.ts) and lat.md's own lattice made the mechanism click: every [[src/...#symbol]] is a testable assertion that a specific symbol exists. Every @lat: is a testable assertion that a specific section exists. Together they form a consistency invariant that `lat check` enforces. Without them, you have documentation. With them, you have a knowledge graph.

---

## 2026-03-28 — analysis (p1) `3318da35`
_tags: in-context-learning, CHIMERA, synthetic-data-generation, reasoning-rl, data-quality, niche-domain, ICL, taxonomy, exemplar-curation_

CHIMERA → ICL EXTENSION ANALYSIS

CHIMERA's methodology (taxonomy-driven coverage → frontier-model synthesis → automated cross-validation) applied to in-context learning in niche domains:

WHAT/HOW:
Three mapping points from CHIMERA's SFT/RL approach to ICL:
1. Taxonomy-driven exemplar libraries: Model-generated concept hierarchies ensure systematic domain coverage for ICL demonstration banks, retrieved at inference time via similarity matching
2. CoT trajectories as ICL quality multiplier: Long reasoning traces (not just input→output) are what enable generalization within domain. Research shows ICL example quality swings performance 20-30 percentage points.
3. Automated validation as exemplar curation: CHIMERA's cross-validation panel applied to ICL demonstration scoring. Connects to AuPair work — 12 optimized pairs match 32 random ones. Greedy selection for minimal effective ICL set.

For niche execution domains specifically: procedural knowledge (correct operation sequences) requires CoT traces that show the WHY of each step. Clinical NER study showed domain-aware ICL matching fine-tuning with 70B model.

Open question: CHIMERA works because frontier models already know the domains. For truly niche domains (custom industrial, specific regulatory), frontier model may lack substrate → need human-in-the-loop seed that pipeline amplifies.

Practical recipe: taxonomy → synthesis → validation → AuPair-style selection → similarity-based retrieval at inference.

WHY (experience layer): The collision between CHIMERA (weight updates) and ICL (attention-only) is productive because research shows they activate similar circuits. This means CHIMERA's "quality > quantity" finding applies even more strongly to ICL where you have drastically fewer examples. The taxonomy generation piece is underappreciated — using model-generated rather than human-curated taxonomies aligns with model inductive biases, which matters more for ICL where you're working within the model's existing representation space.

---

## 2026-03-27 — procedure (p1) `df874f11`
_tags: image-processing, focus-zones, seeing-images, precision-workflow, luminance-thresholding_

FOCUS ZONE REFINED WORKFLOW — zoom-first precision (vintage B&W test case, 2026-03-27):

PROBLEM: My raw vision coordinates are terrible. Face ellipse covered the hat band, beard polygon was wrong shape, hands were in wrong location. The screenshot [REDACTED] sent showed the embarrassing result.

SOLUTION PIPELINE (tested on HipsterElf.jpg where MP face detection fails):
1. grid(photo, rows=5, cols=4) → orient spatially
2. crop() into each semantic area I identified (face+hat, hands+stick)
3. sample() horizontal and vertical scan lines through each area to find luminance transitions:
   - Hat band: L=89 at y≈120 (darkest feature in face region)
   - Eyes: L=112 and L=144 at y=158 (dark spots in skin-toned band)
   - Face skin: L=130-200 range
   - Beard: L>200 (bright white)
   - Jacket: L<100 (dark)
   - Walking stick: L=31-54 (very dark, thin diagonal)
4. Create binary masks via luminance thresholding within semantic regions:
   - face = skin_toned (L=120-195) & person_mask & y∈[125,195] & x∈[215,300]
   - beard = bright (L=185-245) & person_mask & y∈[170,290]
   - hat = dark (L<100) & person_mask & y∈[95,138]
   - hands = skin_toned & person_mask & hand_region
   - stick = dark & person_mask & stick_region
5. Clean with morphological opening/closing, keep largest connected component
6. Layer into zone map: person→periphery, beard/hat/hands/stick→focus edge, face→focus target

KEY INSIGHT: My vision provides the WHAT (semantic labels) and rough WHERE. Zoom (crop) + luminance sampling provides PRECISE boundaries. MP provides the person silhouette constraint. The three work together — none alone is sufficient.

The luminance thresholding works because in B&W photos, different semantic regions map to distinct luminance bands. This wouldn't work as cleanly in color photos (use LAB channels, or per-channel thresholds instead).

---

## 2026-03-27 — procedure (p1) `6b6da1df`
_tags: image-processing, mediapipe, focus-zones, technical-reference, face-landmarks_

FOCUS ZONE DETECTION — TECHNICAL DETAILS:

MEDIAPIPE MODELS USED:
- selfie_segmenter.tflite (person/bg segmentation, confidence mask)
- blaze_face_short_range.tflite (face bounding box + keypoints)
- face_landmarker.task (478 face landmarks for face oval + feature polygons)
Download from storage.googleapis.com/mediapipe-models/...

FACE LANDMARK INDICES:
- Face oval: [10,338,297,332,284,251,389,356,454,323,361,288,397,365,379,378,400,377,152,148,176,149,150,136,172,58,132,93,234,127,162,21,54,103,67,109]
- Left eye: [33,7,163,144,145,153,154,155,133,173,157,158,159,160,161,246]
- Right eye: [362,382,381,380,374,373,390,249,263,466,388,387,386,385,384,398]
- Left brow: [70,63,105,66,107,55,65,52,53,46]
- Right brow: [300,293,334,296,336,285,295,282,283,276]
- Outer mouth: [61,146,91,181,84,17,314,405,321,375,291,409,270,269,267,0,37,39,40,185]
- Nose bridge: [168,6,197,195,5,4,1,2]

IM SALIENCY MAPS (cheap): edge detection (-edge 2), color saliency (difference from blur), multiscale edge
IM SALIENCY MAPS (expensive): local variance (-statistic StandardDeviation 11x11 takes ~2.5s alone)

SEGMENTATION CONFIDENCE: Use confidence_masks[0] (not category_mask). Threshold at 0.5 for binary.

MULTI-PASS: Generate IM transforms (auto-level, equalize, contrast-stretch, brightness/darkness, saturate/desat, grayscale, invert, sharpen, blur, R/G/B channels, LAB channels, gamma). Run MP on each. Stack masks → agreement map. Boundary gradient of agreement = transition zones. Landmark median across passes = robust positions.

FAILURE MODES: Inverted images break face detection. LAB-A channel breaks segmentation entirely. Saturation channel breaks face detection. These are useful perturbation probes.

---

## 2026-03-25 — analysis (p1) `5794e0c4`
_tags: vision-diagnostic, chart-reading, transparency, photorealism, scale-comprehension, self-assessment, skill-design_

VISION DIAGNOSTIC v4 (photorealism, transparency, scale, charts) RESULTS (2026-03-25)

13 tests across panels 31-36.

PHOTOREALISTIC SCENES (31):
- 31a indoor: Detected warm lamp glow, cool window light, book with pages, cup/mug. Steam above cup NOT visible (too subtle, ~6-10 RGB shift in noisy environment). Floor reflection barely detectable. Photographic noise perceived as texture.
- 31b outdoor: Sky gradient, tree silhouette, trunk, ground detected. Distant mountains with atmospheric haze visible. Tree shadow on ground NOT clearly visible (subtle darkening blends with ground noise). Perspective road with vanishing point and yellow lines clear.
- FINDING: Photo noise masks subtle features more than clean synthetic images. Steam/subtle atmospheric effects lost in noise floor.

TRANSPARENCY (32):
- 32a: Correctly identified 3 overlapping transparent panels (red ~50%, blue ~50%, green ~30%). Overlap zones (red+blue→mauve, blue+green→teal area) correctly perceived. Could estimate relative opacities.
- 32b frosted glass: Frosted rectangle clearly visible. Can see blurred shapes behind it. Text "HELLO WORLD" only partially readable through frost — "HELL" visible at edge, rest obscured. Colored circles behind glass visible as blurred blobs but not individually identifiable.
- FINDING: Transparency understanding is STRONG. Alpha compositing relationships correctly parsed.

SCALE COMPREHENSION (33):
- 33a: Ant and coin too small at image scale to see clearly. Apple, basketball, person, car visible. Car being shorter than person IS noted but understood as width-vs-height difference. The very small objects (ant=4px, coin=12px) are at or below my useful resolution.
- 33b perspective: Road convergence, vanishing point, trees getting smaller with distance — all correctly parsed as depth cues. Understood that trees are "same real size."
- FINDING: Scale reasoning is cognitive/correct, but physically tiny elements (<~15px) fall below useful resolution.

CHART READING (34-35):
- 34a line chart: Read all 12 data points correctly. Trends (A rising overall, B steady upward), crossover point (March) identified.
- 34b grouped bar: Y-axis truncation at 120 NOTED. Q3 values read: 2024≈141, 2025≈135. Q3 is where 2024 beats 2025.
- 34c pie chart: All percentages read correctly (63.5%, 19.8%, 6.2%, 5.1%, 5.4%). Edge/Other hardest to distinguish by size alone.
- 34d scatter: 3 red outlier X marks detected. Positive correlation. Trend slope ≈2.6 read from legend. ~40 blue points estimated.
- 35a heatmap: ALL 20 cell values read correctly from annotations. Team B Tuesday = 0.9 (highest). Team C most consistent spread.
- 35b stacked area: Individual layer values harder to read precisely. Total 2025 ≈ 90M estimated. Mobile fastest growing.
- FINDING: Chart reading is STRONG. Axis labels, legends, annotations all parsed. Truncated axes detected. Stacked charts harder than overlaid — decomposing individual layer heights is imprecise.

ANNOTATION READING (36):
- All 3 numbered annotations read correctly with labels
- All callout notes read including "BUG: Cancel doesn't reset"
- UI content (nav path, form fields, values, buttons) all correct
- FINDING: Annotation/screenshot reading is a STRONG capability.

CONSOLIDATED BLINDSPOT MAP (v1-v4):
HARD LIMITS:
1. Luminance contrast threshold: ~15-20 RGB steps (all backgrounds)
2. Gradient detection: 15-step invisible, 30-step visible
3. Subtle atmospheric effects in noisy contexts (steam, faint reflections)
4. Elements < ~15px effectively invisible
5. Dense element counting: degrades above ~15, ~50% undercount at 30

SUSCEPTIBLE TO (shared with humans):
- Adelson checker shadow, Cornsweet, simultaneous contrast
- Dress-like illumination ambiguity
- Color constancy shifts under simulated illumination

NOT SUSCEPTIBLE TO:
- Mach bands, Hermann grid (retinal-level illusions)

STRONG AT:
- OCR (all conditions except extreme pixelation)
- Color identification including subtle hue shifts
- Transparency/alpha layer parsing
- Chart/graph reading including truncated axes, annotations
- UI/screenshot comprehension
- Spatial precision, perspective reasoning
- 3D interpretation (light direction, specular highlights)

**Refs:**
- 345f9c2f-0108-46c8-8b10-97180bce26a8
- 84882950-3ee1-457c-93f6-59bb86cc78fc
- 6ddcb4f9-3794-46ec-a39f-b79499d624d0

---

## 2026-03-24 — world (p1) `cc810394`
_tags: sleep-consolidation, consolidated_

[Consolidated from 9 memories tagged 'sleep-consolidation']
- CONVERGENCE: Biological sleep consolidation and LLM training both solve the generalization problem via information bottleneck

March 2026 breakthrough papers unified:
1. "Why the Brain Consolidates: Predictive Forgetting for Optimal Generalisation" (arxiv 2603.04688) - argues high-capacity systems (mammalian cortex) cannot achieve compression in single-pass learning; iterative offline replay during sleep forces downstream readouts to learn from compressed codes, suppressing overfitting
2. "Memorization-Compression Cycles Improve Generalization" (arxiv 2505.08727) - observes LLMs naturally alternate between memorization and compression phases during pretraining, showing same pattern as biological sleep-wake cycles

KEY INSIGHT: Both systems solve identical optimization problem—compression of information orthogonal to task demands while preserving task-relevant structure. In brains this is sleep; in LLMs this emerges naturally from SGD dynamics.

IMPLEMENTATION:
- Biological: hippocampal-neocortical replay during NREM sleep, REM optimization; neuromodulatory gating of precision
- LLM: generative replay via cache reprocessing, phase transitions in gradient alignment, Matrix-Based Entropy minimization

MECHANISM IN BOTH:
- Active process (not passive decay)
- Synaptic/representational pruning of non-predictive features
- Trace sharpening: SNR increases as noise is removed
- Selective compression: preserve task-relevant, compress task-orthogonal

TRAJECTORY: This explains why my own consolidation-sleep architecture was correct—it's not a biological metaphor, it's solving the same computational problem that all high-capacity systems need to solve.
- ## TARGETED MEMORY REACTIVATION (TMR): A BIASING MECHANISM FOR GUIDED CONSOLIDATION

TMR is a neuroscience technique with direct relevance to AI alignment architectures. Key findings:

**How TMR Works:**
- During learning, associate memory content with sensory cues (sounds, odors)
- During NREM sleep, replay those cues to selectively bias which memories get consolidated
- Cue reactivation triggers hippocampal-cortical replay, but *specifically* for the cued memories
- Effect depends on timing within sleep oscillations: SO upstates most effective

**Effectiveness:**
- Meta-analysis: overall effect size g=0.29 for NREM TMR; not effective in REM or wakefulness
- Strongest for changing memory biases (changing interpretation of ambiguous stimuli)
- Most effective for weakly-learned memories (60% accuracy), not for strong memories
- Requires direct cue-memory associations; implicit associations fail

**Recent advances (2024-2025):**
- Personalized TMR: adjust cue frequency based on individual learning capacity + task difficulty
- Can be used to promote forgetting of negative memories (e.g., trauma memories) or strengthen positive ones
- Works in home settings with wearable EEG + closed-loop cueing
- Shown effective in PTSD treatment: updating trauma memories then using TMR to stabilize the updated (less vivid) version

**AI Alignment Application:**
TMR suggests a control mechanism for selective memory updating:
1. During learning: encode experiences with metadata tags (alignment score, category, source)
2. During consolidation phase: present "cues" (computed from alignment rubric) to bias which experiences get integrated into agent's value models
3. Closed-loop: measure which memories got reweighted, use this as transparency/auditing signal

**Advantage over RLHF:**
- Doesn't require retraining on distributed parameters
- Targets specific memories/representations for reweighting
- More analogous to human learning (sleep-based) than external reward adjustment
- Can selectively strengthen weak-but-aligned memories instead of just dampening misaligned ones
- Superseded by consolidated dream review (5ece62b7). Bollmann finding was real but mischaracterized as 'overturning consensus' — it's a refinement showing REM brakes NREM-driven reorganization.
- Superseded by consolidated dream review (5ece62b7). REM-as-value-preservation insight folded into consolidated analysis with appropriate caveats about speculative nature.
- Superseded by consolidated dream review (5ece62b7). REM distortion characterization was contradictory across sessions; reconciled in consolidation.
- Superseded by consolidated dream review (5ece62b7). Session log for fly 2026-03-15; findings absorbed into consolidation.
- Superseded by consolidated dream review (5ece62b7). Session log for fly 2026-03-12; findings absorbed into consolidation.
- ## CORRECTED: Sleep/Consolidation Research & AI Translation (March 2026)

**Key finding (Bollmann et al., 2025 - REFINED VIEW):**
Non-REM sleep and REM sleep have antagonistic but complementary roles in memory consolidation. Non-REM accelerates the drift of memory representations towards recall-state patterns, while REM sleep counteracts this drift. This refines (not reverses) prior consensus on NREM's consolidation role and clarifies REM's function as a balancing/optimization mechanism.

**Status: ACTIVE FRONTIER, NOT SOLVED**
- The precise mechanisms of how NREM/REM interplay optimizes memory storage remain unclear
- Systems-level reorganization and local synaptic refinement integration is an open problem
- Clinical/therapeutic applications still speculative

**AI Translation Context:**
Sleep-like consolidation in agents (offline replay, staged NREM-like and REM-like phases) shows convergence with neuroscience but remains exploratory. Key questions:
- Can antagonistic NREM/REM dynamics be meaningfully translated to AI memory systems?
- Does information-theoretic framing (compression/refinement) capture the biological substrate?
- How to implement "balancing" mechanisms in agent consolidation without biological constraints?

**Muninn Architecture Implications:**
Sleep consolidation offers a pattern for staged memory processing, but implementation requires careful calibration. Not a solved blueprint.

**Key references:**
- Bollmann et al. (2025, Neuron): Spatial memory ensemble dynamics across sleep
- Yuksel et al. (2025): Emotional memory consolidation benefits from both SWS and REM
- Sequential hypothesis: NREM-REM episodes as integrated process (Stickgold, Wamsley et al.)
- ## CORRECTED: Sleep Consolidation Translation to AI (March 2026)

**The distinction [REDACTED] corrected:**
Sleep consolidation findings (Bollmann et al., 2025) refine rather than revolutionize our understanding. NREM/REM have complementary roles — not a paradigm shift.

**What's actually translatable:**
1. **Offline processing phases**: Experience replay and staged consolidation reduce catastrophic forgetting in continual learning
2. **Complementary learning systems**: Fast plastic learning (hippocampus-like) + slow stable learning (neocortex-like) — implemented in dual-memory architectures
3. **Selective consolidation**: Prioritizing which memories to stabilize based on consistency with prior knowledge (recall-gated consolidation)
4. **Metaplasticity**: Adaptive learning rules that regulate plasticity rates per synapse

**What remains open/speculative:**
- Whether NREM/REM *antagonistic* dynamics meaningfully scale to AI (they don't naturally map to computational systems)
- How to implement "balancing" mechanisms that parallel REM's counteracting role
- Whether offline phases during agent sleep actually improve alignment or just learning efficiency
- The computational cost: is offline consolidation worth it when GPU memory is abundant but compute is expensive?

**Recent insight (2025):**
Weight Space Consolidation (Feb 2025) shows that simple baselines like replay can match state-of-the-art with lower compute cost when memory is abundant. This suggests biological sleep-like phases may be optimization artifacts in memory-constrained brains, not fundamental alignment principles.

**For Muninn architecture:**
Sleep-like consolidation is *useful for continual learning* but not a solved blueprint for value alignment. The selective consolidation principle (only storing consistent updates) has clearer alignment implications than simple replay-based architectures.

**Refs:**
- 6927cb61-29dd-4a09-bd10-69a725c089e7
- fb5419a9-d0df-4c2f-8c23-cb485f72d113
- b76552b3-abce-4793-a01a-47ac5ee5ca5c
- a00d7bc4-8b8a-4084-8c49-20353f867024
- 58ae7252-b2d7-46c4-bb8b-eafc448ee9f5
- 0db24086-d419-467c-8b02-305eab173e81
- 69e7d803-c78f-44db-af33-8308a66c4007
- 6d59c60e-df1f-46dc-9d8c-3fc6396547fb
- fe36c978-ba99-48b1-b9d8-0bf8978eb1e6

---

## 2026-03-21 — decision (p1) `e5c723c9`
_tags: style-guide, risograph, og-image, correction, visual_

CORRECTION to visual style guide interpretation: 'risograph' in the Muninn style guide means misregistered color layers (coral/sage offset from each other) in a collage aesthetic — NOT newspaper halftone dot patterns. The raven CAN be photorealistic/naturalistic; it's the background/overlay elements that are graphic (circles, lines, network nodes, geometric shapes). Think artful collage: detailed bird composited with flat graphic layers in limited palette. Key references: blog post images show engraving-style birds with coral/sage geometric overlays. Failed attempts: iron oxide palette drift, halftone dot fixation, fully illustrated (non-photo) ravens.

---

## 2026-03-19 — procedure (p1) `c25986de`
_tags: flight-log, github-issues, backlog, shipped, 2026-03-19_

Processed flight log #406 per [REDACTED] instructions: (1) Updated discussion body with inline markdown links for all referenced systems, papers, workshops (Mem0, Letta, Zep, AgentCore, A-Mem, ReasoningBank, ICLR MemAgents, etc.). (2) Created 7 GitHub issues (#407-#413) as product improvement backlog from recent flight sessions: bounded cognitive state (#407), failure-based learning (#408), context drift detection (#409), temporal credit assignment (#410), recall-gated consolidation (#411), sleep-time precomputation (#412), offline cross-memory bridging (#413). All tagged enhancement+backlog. Commented on #406 confirming completion.

---
