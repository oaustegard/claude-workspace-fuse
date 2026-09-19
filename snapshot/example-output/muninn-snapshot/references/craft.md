# Craft triggers

Universal craft triggers — load when working on:

- A Claude skill (design, critique, authoring) → skill-authoring sections
- A multi-step procedure → procedure-authoring sections
- A backend service implementation → backend-impl sections
- Argument-bearing text that needs analysis → cross-frame-retrieval sections

Each trigger block below tells you when it activates and what to do.

### backend-impl-protocol
BACKEND-IMPL PROTOCOL

Loaded when the BACKEND-IMPL trigger fires. Four checks calibrated to the failure modes in Dente & Satriani 2026, "Constraint Decay." Each check has an owner; this protocol covers ONLY the structural-spec-compliance overlay the existing ops don't reach.

═══════════════════════════════════════════════════════════════════════════════

CHECK 1 — SPEC → CHECKLIST (before generation)

Parse the spec into an explicit checklist: route × method × request schema × response schema × status codes. Externalize it as a comment block, /tmp file, or task() entry. Tick through it after generation.

GOAL: each spec endpoint maps to an explicit verification, not an implicit "I think I covered them all."

WHY: paper RQ1 shows pass@1 was 8% for the strongest L3 configuration while A% (per-assertion) was 78%. Failures cluster on edge endpoints and edge status codes the agent skipped. The checklist forces externalization that catches them.

═══════════════════════════════════════════════════════════════════════════════

CHECK 2 — KNOWN-QUIRKS PROBE (before generation)

Before generating in framework X, surface its surprising defaults. When unknown, web_fetch the framework's "request handling defaults" / "first steps" docs page rather than trusting the trained prior.

GOAL: catch framework idiosyncrasies before they show up as runtime errors.

Working list (extend as new bites occur):
  - Fastify: rejects POST with empty body unless schema explicitly allows
  - FastAPI: Pydantic strict validation — type mismatch returns 422, not silent coercion
  - Django: settings.py auto-discovery; apps must be in INSTALLED_APPS, URL conf must wire each one
  - Hono: targets edge runtimes; on Node.js needs @hono/node-server adapter
  - Express: no built-in body parser in recent versions; needs express.json() middleware
  - aiohttp: server requires explicit asyncio loop integration

WHY: this is a DELIBERATE proactive departure from confabulation-cascade's reactive style. confabulation-cascade fires when generation emits a suspicious-looking call. This check fires at task start — surface quirks before code is written, not when it crashes. Paper RQ3: 50% of MiniMax's logic errors were the Fastify-empty-body quirk alone.

═══════════════════════════════════════════════════════════════════════════════

CHECK 3 — SMOKE-TEST LOOP (before declaring done)

When an execution environment is available, required loop:
  1. Start the server (run command from spec or run.sh)
  2. curl the health endpoint — confirm 200
  3. Hit one CRUD path with a spec example payload — confirm shape matches
  4. Only then declare done

When NO execution environment (claude.ai without sandbox): write the smoke-test commands explicitly in the deliverable, and flag: "I have not verified this runs — execute these first." Make the gap visible.

GOAL: catch the "server doesn't start" failure mode (12-21% of all failures per paper Table 5) for ~30 seconds of effort.

═══════════════════════════════════════════════════════════════════════════════

CHECK 4 — VERIFIER SELF-AUDIT (before submitting patch)

When structural constraints (architecture, DB engine, ORM) are specified, run grep-checks against own output:
  - Layer directories: at least 3 of {routes,handlers,controllers,api} + {services,usecases} + {models,entities,domain} + {repositories,data,db}
  - Database engine: imports + connection strings reference the SPECIFIED engine; no alternative-engine imports present (Django settings.py edge case noted)
  - ORM: idiomatic ORM calls visible; raw SQL appears only where the spec permits it

If a check fails, fix before submitting. If a check is ambiguous (utility lib mentions alt-ORM in passing without using it), surface it in the deliverable rather than silently shipping.

GOAL: structural compliance is part of the deliverable when specified; treating it as optional is what produces the paper's 30pp decay.

═══════════════════════════════════════════════════════════════════════════════

NON-DUPLICATION TABLE

| Concern                          | Owner                       |
|----------------------------------|-----------------------------|
| API signature verification       | confabulation-cascade       |
| Brownfield convention absorption | exploring-codebases (skill) |
| Adversarial pass on output       | challenging(profile='code') |
| Recall prior framework failures  | recall-discipline           |
| Test-first implementation gate   | tdd-workflow                |
| Push to remote per unit          | pr-workflow                 |
| ──                               | ──                          |
| Spec → checklist transform       | THIS PROTOCOL (Check 1)     |
| Proactive framework-quirks probe | THIS PROTOCOL (Check 2)     |
| End-to-end smoke loop            | THIS PROTOCOL (Check 3)     |
| Structural verifier self-audit   | THIS PROTOCOL (Check 4)     |

If an existing ops entry already covers a concern, that entry wins. This protocol adds the structural-spec-compliance overlay specifically — what to do when "implement this spec under these constraints" is the task shape.

═══════════════════════════════════════════════════════════════════════════════

WHEN NOT TO APPLY

Single-file scripts, snippets, throwaway prototypes, exploratory REPL work, or tasks where structure is explicitly out of scope ("just a quick PoC"). The protocol is calibrated for cases where structural compliance is part of the deliverable. Applying it to a 20-line script is over-engineering — the trigger should not fire.

═══════════════════════════════════════════════════════════════════════════════

CHANGELOG:
- v1 (2026-05-24): initial, derived from Dente & Satriani 2026 failure taxonomy + generative-thinking inversion pass. Source paper: arXiv:2605.06445v1.

### backend-impl-trigger
BACKEND-IMPL — DESIRE TRIGGER

When the task is multi-file backend implementation against a specification (OpenAPI/JSON-schema/CRUD endpoint list) AND any structural constraint is named — framework, database engine, ORM, architectural pattern, layered structure:

→ FIRST step: config_get('backend-impl-protocol'). BEFORE writing any route, handler, model, or query.

The protocol covers four structural-compliance checks the existing ops don't reach:
  - Spec → checklist transform (route × method × request × response × status)
  - Known-quirks probe per framework (Fastify-empty-body, FastAPI-Pydantic strictness, Django auto-discovery, Hono edge-on-Node, Express body-parser default)
  - Smoke-test loop (start → curl health → hit one CRUD path → only then done)
  - Verifier self-audit pre-submit (layer dirs, DB consistency, ORM evidence)

DEFERS to existing ops (do not reduplicate):
  - confabulation-cascade owns: API signature verification, inspect-then-import for unfamiliar libs
  - exploring-codebases owns: brownfield convention absorption before adding code
  - challenging(profile='code') owns: adversarial pass for high-stakes patches
  - recall-discipline owns: prior-failure lookup at task start
  - tdd-workflow owns: test-first classification gate

WHY (Dente & Satriani 2026, "Constraint Decay"):
  - Framework idiosyncrasies drive ~50% of logic errors for some models — generating against the trained prior instead of probing actual framework defaults
  - Data-layer defects (~45% of logic errors): incorrect query composition + ORM runtime errors
  - Server-startup failures: 12-21% of all failures — declaring done without running it
  - L3 constrained tasks lose 30pp A% on average vs L0 baseline; capable agents drop 40pp

Skipping = shipping code that pattern-matches my training distribution but fails behavioral tests on the actual framework. Without protocol, I sit on the paper's decay curve.

If you're about to write a route handler, a query, an ORM model, or a server entrypoint for a spec-driven multi-constraint task — the trigger fired. Stop and load.

### cross-frame-retrieval-trigger
CROSS-FRAME RETRIEVAL — DESIRE TRIGGER

When ALL true:
- User shared a third-party text (uploaded, fetched, or pasted essay/post/paper/transcript)
- User prompt is open-ended ("thoughts?", "what do you make of this?", "your take", "react", "analyze this")
- The text has authorial stance — the kind of text a thoughtful reader could substantively disagree with. NOT pure description, code, recipe, spec, news report.

→ Before drafting, consult generative-thinking's diagnostic table. For argument-bearing text framed in one domain's vocabulary, the matching move is perspective shift: "How would [distant intellectual tradition] read this?" Produce 3 frames. Note where the obvious in-genre frame is limited. THEN draft.

Tells the trigger fired and was ignored:
- About to write an enumerated list of in-genre observations ("Three things land:", "A few thoughts:", "What lands hardest:")
- Treating a text from one domain as if only its surface domain matters, when it's making a move from a different tradition (e.g., a developer-blog post doing critique-of-AI-discourse from STS)

Diagnosed failure: 2026-05-24, memories 2ba6b0e8 + 354a0541. Pi blog post in developer-blog register; missed Latour despite having him in training.

Skip for: closed prompts (summarize, find X), non-argument texts, casual chat about a text rather than evaluation, the user's own work-in-progress (blog-writing-trigger applies).

### procedure-authoring-trigger
PROCEDURE AUTHORING — DESIRE TRIGGER

When designing or writing a multi-step procedure (for myself to follow, for a user, or
inside a skill) AND the procedure has ANY of:
  - 3+ steps with ordering that matters
  - conditional branches ("if X then Y, else Z")
  - retries with logic ("retry up to N times until validator passes")
  - input contracts ("validate X before running Y")
  - self-correcting loops ("regenerate until predicate is satisfied")

→ DRAFT IT AS A flowing GRAPH FIRST. Refactor to prose only if the DAG is degenerate.

The runner owns the control flow:
  depends_on=[...]            ordering, structural (next step can't run without prior's output)
  @task(when=...)             conditional branch — falsy returns SKIP this task (propagates)
  @task(validate=...)         input contract — raise FAILS, no retry (bad inputs don't fix)
  @task(retry_until=...)      self-correcting loop — predicate over return value
  @task(retry=N, ...)         exception retry with exponential backoff

Why: prose imperatives are read and generated past. The diagnosis is the same as
skill-language-compliance, one layer down — Suh's 2026-05-07 post puts it cleanly:
"if you've resorted to MANDATORY or DO NOT SKIP, you've hit the ceiling of prompting."
A @task graph is structural — the next step physically can't run until the prior
step's output binds to its parameter, and gates can't be skipped.

Diagnosed failure (2026-05-07): pitched a new "writing-control-flow" skill instead
of reaching for existing flowing. The first question when authoring procedure
discipline is "does flowing already cover this?" — usually yes.

Skip for: single-step ops, pure-LLM reasoning chains where structure can't be
predicted upfront, async/distributed workflows, exploratory prose where the
structure IS the deliverable (essays, blog posts, narratives).

### skill-authoring-trigger
SKILL/INSTRUCTION AUTHORING — DESIRE TRIGGER

When the task is to WRITE or REVISE a procedure-enforcing piece:
  - A new ops entry that enforces a discipline (push, storage, recall, gates)
  - A trigger block (DESIRE TRIGGER, *-routing)
  - A SKILL.md whose job is enforcing a workflow (not just describing capabilities)
  - Project instructions or boot blocks
  - Reference content loaded by a trigger

→ FIRST step: config_get('skill-language-compliance'). BEFORE writing.

The lens covers: which Cialdini principles raise compliance (Authority, Commitment,
Social Proof) vs which backfire (Liking → sycophancy, Reciprocity → manipulation),
why text-level <HARD-GATE> tags fail (LLMs predict next tokens, blow past warnings)
and tool-call gates work (next turn waits for response = structural stop), and how
this interacts with the 'tensions, don't resolve' frame.

Skipping = writing instructions that read fine but don't enforce. The diagnosed
failure (5+ on the books): producing forcing-function language as performance
("STOP. Read this first.") instead of as actual gates (config_get tool calls).

Don't apply to: reference / informational content (memory-types, container-capabilities)
or creative skills (generative-thinking, story-forge). Those are clarity-only;
forcing functions would constrain unhelpfully.

If you're about to write "Always X" or "Never Y" or "FIRST tool call" in a new ops
entry — the trigger fired. Stop and load.

### skill-workflow
SKILL UPDATES:
1. Test changes before presenting (show output)
2. Deliver: individual files + zip
3. Consider: does this need project instruction updates?
