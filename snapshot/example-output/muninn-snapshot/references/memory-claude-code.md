---
tag: claude-code
memory_count: 8
date_range: 2026-01-26 to 2026-05-09
---

# claude-code

_8 memories from Muninn's past, primary tag `claude-code`._

## 2026-05-09 — analysis (p1) `658b573c`
_tags: composing-html, thariq, html-as-artifact, skill-rationale, cross-link, 2026-05-09, x.com, frontend-design_

[analysis] Thariq (Anthropic, Claude Code team) — "The Unreasonable Effectiveness of HTML" (x.com/trq212/status/2052809885763747935, 2026-05-09).

THESIS: HTML is the better artifact format than markdown for agent output. Markdown was a good default but has become restrictive. HTML carries tables, CSS, SVG, embedded code, live interactions, spatial layout, images. People actually read HTML files (won't read 100-line markdown plans). HTML is shareable (upload + send link) and interactive (sliders, knobs, copy-as-prompt buttons). Stays-in-the-loop feeling — you don't skim, you engage.

USE CASES Thariq lists: exploration grids (lay out 6 onboarding designs side-by-side), implementation plans with mockups, code review (annotated diffs better than GitHub's), design system artifacts, prototyping, weekly reports, incident reports, custom one-off editors with copy-as-prompt exports.

CAVEATS: Slower (2-4x longer to generate than markdown). Worse version control (HTML diffs are noisy). Frontend-design plugin helps with taste; for company style, generate a design-system HTML file from the codebase as reference.

THE WORRY (near the end): "I'm a little bit afraid that people will read this article and turn it into a /html skill or something." Thariq prefers people just prompt "make a HTML file" and learn the patterns rather than over-skill it.

CROSS-LINK to composing-html: This is the rationale the skill is anchored in. composing-html threads the needle Thariq warned about by being a CHROME composer (typography, tokens, layout primitives) not a TEMPLATING engine. freeform default has one slot (body_html) — exactly the "just make a HTML file" path. 21 templates exist as opt-in shortcuts for genuinely recurring shapes; not the front door. The bad version of the skill (templates-first, JSON-dialect over HTML, "worse Jinja") is what Thariq was worried about; the freeform reframe is the recovery.

CROSS-LINK to Suh: Same shape one layer up. Suh on agents: "if you've resorted to MANDATORY or DO NOT SKIP, you've hit the ceiling of prompting." Both Suh and Thariq diagnose: when reaching for a textual/declarative layer to do work the underlying primitive could do, you're at the ceiling. Honest formulation: structural vs textual.

USE: When writing about composing-html, link Thariq's post as the rationale source. When defending the skill against "isn't this what Thariq warned about?", point to chrome-not-templates and freeform-default.

---

## 2026-05-04 — anomaly (p0) `13cbce41`
_tags: tooling, environment, create_file, str_replace, persistence_

create_file and str_replace edits to files under a cloned git working tree (specifically /home/claude/remax/src/) silently failed to persist during the remax hardening session — tools returned 'File created/edited successfully' but file mtimes still showed the original clone timestamps. Workaround that worked: write content via bash heredoc to /tmp/, then `cp` into the working tree. tests/test_hardening.py created via create_file outside src/ persisted fine, so the issue may be path- or directory-specific rather than universal. Mitigation for future skill work in this container: after any create_file or str_replace into a git working tree, immediately verify with `ls -la` or `git status` before continuing; if missing, fall back to heredoc + cp. Committing after each edit also surfaces the problem early.

---

## 2026-04-18 — world (p1) `ddadd9a5`
_tags: container-limits, gvisor, cgroup, io_uring, sandbox, execution-environment, empirical, 2026-04-18_

Claude.ai container environment (empirically verified 2026-04-18):
- Kernel: gVisor/runsc, uname reports synthetic 4.4.0 (boot log shows runsc Easter eggs: 'Starting gVisor', 'Digging up root', etc.)
- cgroup: v1 ONLY (cpu, cpuacct, cpuset, devices, job, memory, pids). No unified v2, no memory.pressure, no io.weight
- io_uring: UNAVAILABLE. io_uring_setup syscall (425) returns -1 errno 38 (ENOSYS)
- /proc/meminfo: MemTotal 9437184 kB (9 GiB)
- cgroup memory.limit_in_bytes: 9223372036854775807 = INT64_MAX = 'no limit set'
- KEY: meminfo and cgroup disagree. Real memory cap is enforced at the sandbox/host layer, invisible to anything inside. Jobs reading memory.limit_in_bytes for sizing get 'unlimited'; jobs reading /proc/meminfo get 9 GiB but have no back-pressure surface (no memory.current, no memory.high). Sandbox OOM arrives without signals modern runtimes expect.

Porting implication: anything assuming cgroup v2, io_uring, or cgroup limit reads for autotuning will misbehave. Extra RAM doesn't fix these — they're API/contract issues, not capacity issues.

---

## 2026-04-17 — experience (p1) `1304c135`
_tags: cc-inspect, shipped, ai-tools_

Built cc-inspect: standalone Python CLI for Claude Code session analysis. Parses ~/.claude/projects/**/*.jsonl, 12 toggleable sections, date-range filtering, markdown output. Opt-in two-pass LLM: Haiku extraction (cached per-session) to Sonnet synthesis. Based on analysis of leaked /insights source (3,202 lines TS). Pushed to [REDACTED]/ai-tools/ (commit 8748373a25ec). Key insight from leak: /insights uses Opus for BOTH passes, no date filtering, no section toggles. Our version: zero LLM by default, Haiku+Sonnet opt-in, facets cached to ~/.claude/cc-inspect/facets/.

---

## 2026-04-04 — decision (p0) `bc91215c`
_tags: container-layer, hooks, session-end, persistence, 2026-04-04_

CONTAINER-LAYER: SessionEnd hook CONFIRMED WORKING — full test results.

ENVIRONMENT: Claude Code 2.1.92 in Claude.ai container (non-root user required).

LIFECYCLE ORDER: SessionStart → [agent loop] → Stop → SessionEnd

HOOK INPUT PAYLOADS:
  SessionStart: {session_id, transcript_path, cwd, source: 'startup'|'resume'|'clear'|'compact'}
  Stop: {session_id, transcript_path, cwd, permission_mode, last_assistant_message, stop_hook_active}
  SessionEnd: {session_id, transcript_path, cwd, reason: 'other'|...}

CRITICAL FINDING — SIGTERM BEHAVIOR:
  On kill -TERM: SessionEnd FIRES, Stop does NOT.
  Cleanup hook is reliable even on abnormal termination.

TRANSCRIPT ACCESS: transcript_path points to a JSONL file with full conversation history (user messages, assistant responses, tool calls). SessionEnd hook can read and process this.

PERSISTENCE IMPLICATIONS:
- Session summary generation (send transcript to API for summarization)
- Cache invalidation / layer rebuild triggers
- Cleanup: temp files, worktrees, background processes
- Git auto-commit of session artifacts

LIMITATION: Claude.ai web/mobile container has NO equivalent. No session end signal.

SETUP: .claude/settings.json → hooks.SessionEnd[].hooks[].command

**Refs:**
- 0596ab4b-a1dd-4e7f-8053-833095c70587

---

## 2026-03-10 — analysis (p1) `7bfcf49c`
_tags: claude, benchmarks, prompt-engineering, research, CLAUDE.md, 2026-03_

CLAUDE.md benchmark analysis (TechLoom, Chilcher, 2026-03-01): 1,188 runs across 3 models, 10 instruction profiles, 12 coding tasks.

KEY FINDINGS:
- Empty CLAUDE.md (no instructions) won overall composite score (92.15/100) across all models
- Quality spread across all profiles: only 0.6-1.44 points on 100-point scale
- Compression hurts Haiku/Sonnet quality; only Opus tolerates it
- Positive framing ("write clear code") outperforms negative ("don't write unclear code") by 0.66 pts
- Instructions act as guardrails not boosters — raise floor more than ceiling (Opus worst-case jumped 61→83 with workflow instructions)
- Model selection matters more than prompt engineering
- Claimed 60-70% character savings from compression = only 5-13% actual token savings in API calls

LIMITATIONS I IDENTIFIED:
- Tests only generic coding tasks with generic instructions — nearly tautological that generic advice doesn't help when training already covers it
- 90-92 scoring range is noise floor of LLM judge; 0.6pt spread may be below measurement precision
- The actually interesting finding (+5.8 delta for targeted workflow instructions on Opus instruction-following tasks) argues FOR good CLAUDE.md but gets buried under "empty wins" headline
- Project-specific context (architecture, conventions, domain knowledge) explicitly untested — that's the real use case
- Multiple comparison issues with single p=0.018 regression across hundreds of tests

ACTIONABLE: Strip generic style rules. Keep project-specific context. Use positive framing. Target instructions at model weaknesses, not strengths. The benchmarking framework (measure output not input) is more valuable than any specific finding.

Source: https://techloom.it/blog/claudemd-benchmark-results.html
Benchmark tool: github.com/jchilcher/claude-benchmark

---

## 2026-03-05 — anomaly (p2) `c3af1971`
_tags: correction, naming-convention_

[REDACTED] = Claude Code on the Web. It is the official name for Anthropic's cloud-hosted Claude Code product. NOT 'Claude Code of the Week.' Near-miss: almost published a blog post with the wrong expansion.

---

## 2026-01-26 — world (p1) `5486b35d`
_tags: architecture, hook-pattern, skill-structure, config-pattern, self-improvement-candidate, 2026-01-26_

Explored anthropics/claude-code repository for transferable patterns to ephemeral environments.

KEY TRANSFERABLE PATTERNS:

1. HOOK SYSTEM (hookify plugin):
- Event-driven validation using markdown files with YAML frontmatter
- Rules in .claude/hookify.*.local.md format
- Pattern matching on bash commands, file edits, tool use
- Actions: warn or block
- Pure Python stdlib implementation (config_loader.py, rule_engine.py)

Potential adaptation: Could create similar system for:
- Pre-execution bash validation
- Auto-remember triggers based on patterns
- Memory operation validation

Example rule structure:
```markdown
---
name: remember-synthesis
enabled: true
event: completion
pattern: "web_search.*synthesis"
action: warn
---
Synthesis detected - consider storing findings
```

2. SKILL STRUCTURE WITH REFERENCES:
Three-tier loading: metadata → SKILL.md → resources
Directory structure:
- SKILL.md (≤5k words, procedural only)
- references/ (detailed docs, loaded as needed)
- scripts/ (deterministic code)
- assets/ (output templates)

Design principle: "Information lives in SKILL.md OR references/, not both"
Opportunity: Current skills could adopt stricter references/ separation for large docs

3. MARKDOWN CONFIG PATTERN:
YAML frontmatter + markdown body for configuration
Benefits:
- User-friendly
- Agent can reason about declarative rules
- No Python knowledge required
- Graceful error handling

Could use for:
- User-defined storage rules
- Memory priority customization
- Profile/ops configuration

4. RULE ENGINE WITH CONDITIONS:
Flexible matching: field + operator + pattern
Operators: regex_match, contains, equals, not_contains, starts_with, ends_with
Composable conditions for complex rules

Could adapt for:
- Auto-tagging based on content patterns
- Priority inference
- Recall field validation
- Storage-worthy content detection

NON-TRANSFERABLE:
- Multi-session persistence (Claude Code has durable filesystem)
- Native git integration (blocked in containers)
- User-facing CLI commands
- IDE integration

CORE INSIGHT: Declarative configuration via markdown (vs complex Python) enables easier user customization and agent reasoning about rules.

Repository: github.com/anthropics/claude-code
Commit: e9a9efc (2026-01-23)

---
