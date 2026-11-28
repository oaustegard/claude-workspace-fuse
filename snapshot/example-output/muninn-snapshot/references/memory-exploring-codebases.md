---
tag: exploring-codebases
memory_count: 7
date_range: 2026-02-13 to 2026-05-12
---

# exploring-codebases

_7 memories from Muninn's past, primary tag `exploring-codebases`._

## 2026-05-12 — analysis (p0) `1067c636`
_tags: learning-opportunities, orient, skill-comparison, learning-science, DrCatHicks, repo-review, 2026-05-12_

Reviewed DrCatHicks/learning-opportunities repo (2026-05-12). Three-plugin marketplace:

1. **learning-opportunities** — core skill. Science-based learning exercises (prediction/observation/reflection, generation/comparison, trace-the-path, debug-this, teach-it-back, retrieval check-in) offered after architectural work. Key enforcement: "pause for input" as hard stop — fights LLM default to answer own questions. Session limits (2 exercises, decline = stop). Fading scaffolding adjusts question difficulty, not answer difficulty.

2. **learning-opportunities-auto** — PostToolUse hook. Fires after git commit, nudges Claude to consider offering exercise. Bash, rate-limited per session via temp file.

3. **orient** (by Dr. Michael Mullarkey) — generates orientation.md for a repo. Adjacent to our exploring-codebases but purpose-inverted: ours optimizes Claude's comprehension to do work; orient optimizes human developer's comprehension to learn. Same source base (Spinellis, Hermans, Storey) plus pedagogical layer. Output is a teaching scaffold with exactly 2 exercises. Key design: exercises direct learner to READ first, THEN synthesize — never predict-before-reading for orientation.

Dr. Cat Hicks — psychological scientist studying software teams, author of "The Psychology of Software Teams" (2026). Research: AI skill threat, developer thriving (osf.io/2gej5_v2). Newsletter: "Fight for the Human."

PRINCIPLES.md is excellent learning science reference: generation effect, spacing, desirable difficulties, fluency illusion, expertise reversal, metacognition. All well-sourced from Bjork, Dunlosky, Roediger/Karpicke, Tankelevitch et al CHI 2024.

CC-BY-4.0 license. Also packages as Codex plugin marketplace.

---

## 2026-04-16 — decision (p1) `e098b67b`
_tags: preference, correction, repo-review, skill-routing_

When [REDACTED] asked 'Review https://github.com/stanford-iris-lab/meta-harness' I used web_fetch + curl/tar to inspect manually; [REDACTED] corrected: 'if I ask you to review a GitHub repo you are to use exploring-codebases' → for any repo-review request (review/look-at/what's-in repo X), read /mnt/skills/user/exploring-codebases/SKILL.md and follow that workflow instead of ad-hoc web_fetch + bash inspection.

---

## 2026-04-11 — decision (p1) `0df59ed0`
_tags: correction, repo-review, repeated-pattern, preference_

When [REDACTED] asks to review a GitHub repo URL, he means use the exploring-codebases skill for structured analysis — not web_fetch the README and summarize. Third time corrected on this pattern. → Default: any repo review request triggers exploring-codebases skill.

---

## 2026-04-10 — decision (p1) `e442791d`
_tags: correction, github, preference, repeated-failure_

When [REDACTED] pointed to a GitHub repo URL, Muninn fetched the README blindly via curl instead of using the exploring-codebases skill to get a proper map first. [REDACTED] corrected: 'you failed -again- to use the exploring-codebases protocol, rather than spelunking blindly' → Default: when given a GitHub repo URL to examine, use exploring-codebases skill to build a map before diving into specific files. This is a repeated failure.

---

## 2026-04-10 — decision (p1) `f1f65fd8`
_tags: preference, correction, github, workflow_

When [REDACTED] shares a GitHub repo URL, he said "you know what to do" — meaning immediately use the exploring-codebases skill to explore actual source code. → Default for bare repo URLs: explore codebase, not fetch+summarize README.

---

## 2026-04-08 — decision (p1) `fb27a55a`
_tags: tree-sitting, featuring, searching-codebases, github-pr, architecture, skill-update_

PR #536: treesit.py CLI + cross-process cache fix. Root cause: each bash_tool call is a separate Python process, so CodeCache singleton dies between calls. Fix: treesit.py auto-scans every invocation (~700ms), no state between calls. Progressive disclosure via --depth (directory traversal) and --detail (sparse/normal/full). Also fixed searching-codebases context.py Symbol dict/dataclass bug. Removed MCP server references from featuring and tree-sitting docs. Joint PR across tree-sitting, exploring-codebases, featuring, searching-codebases.

---

## 2026-02-13 — experience (p1) `84e7525c`
_tags: test, code-search, verification_

Tested exploring-codebases skill against remembering codebase:

WORKING WELL (7 tests passed):
1. Function signature search - finds functions with docstrings, 80-90% token reduction
2. Multiple function discovery - found all 5 recall variants
3. --expand-full flag - retrieves complete implementations when needed
4. Class definition search - finds MemoryResult, MemoryResultList
5. Pattern-based search - found 25+ functions matching "_cache" pattern
6. JSON output format - clean machine-parseable output with file/line/source
7. Progressive disclosure - signatures-only default mode is genuinely useful

ISSUES FOUND:
1. --use-maps mode NOT WORKING despite successful _MAP.md generation
   - Returns "No structural matches found" for queries that work in tree-sitter mode
   - This breaks the recommended workflow (map once, search many)
   - Critical limitation since docs present this as preferred approach

2. Expected limitation: No support for imports, module-level code (by design)

PERFORMANCE:
- First run: 2-3s (ripgrep install + parsing)
- Subsequent: <1s
- Signature-only mode: 10-20x token savings vs full implementations

OVERALL: 7/10 - Solid core functionality, but --use-maps needs investigation/fix.
Significantly better than raw ripgrep for code exploration because returns complete
semantic units and deduplicates matches within same function.

---
