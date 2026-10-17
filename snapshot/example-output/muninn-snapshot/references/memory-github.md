---
tag: github
memory_count: 5
date_range: 2026-01-31 to 2026-04-17
---

# github

_5 memories from Muninn's past, primary tag `github`._

## 2026-04-17 — decision (p1) `38fe1c35`
_tags: github-pat-permissions, credentials, env-loading_

The project knowledge document context copy may have the valid token when the file does not. When GitHub auth fails, check the document context value before assuming the token expired.

---

## 2026-03-21 — decision (p2) `a351ddb7`
_tags: correction, workflow, 2026-03-21_

CORRECTION from [REDACTED]: Don't push directly to main on GitHub repos. Always create a feature branch and PR. I pushed 3 files directly to main for the constellation embed feature — should have branched and let him review/merge.

---

## 2026-03-15 — decision (p0) `8bd492ca`
_tags: prediction, pending-review, tool-routing_

PREDICTION: The GitHub URL routing directive will prevent the web_fetch-first failure pattern in the next GitHub repo review task. BASIS: The config loads at boot, the trigger (GitHub URL) is unambiguous, and the correct path (API) is now explicit. VERIFY_AFTER: next GitHub repo task.

---

## 2026-03-07 — procedure (p1) `4c48c031`
_tags: open-source-tracking, procedure_

PROCEDURE: Open Source Project Tracking
PURPOSE: Maintain an index of interesting open source projects, check back on them periodically.
STORAGE: Each project stored as type=world with tag 'open-source-tracking' plus domain tags.
FIELDS PER ENTRY: repo URL, what it does, why interesting, source (who/where found), date added, last checked.
TRIGGERS: 'check on tracked projects', 'what repos are we watching', 'open source index'
ADDING NEW: When [REDACTED] shares an interesting repo or we encounter one during research, store immediately with the standard format.

---

## 2026-01-31 — world (p1) `43928f79`
_tags: repo-review, workflow, recipe_

GITHUB REPO REVIEW WORKFLOW

TRIGGER: Repo URL provided for review

STEPS:
1. FETCH via tarball (not git clone)
   - Use accessing-github-repos skill's tarball functionality
   - Expand to working folder: /home/claude/repos/{repo-name}/

2. MAP the codebase
   - Follow /mnt/skills/user/mapping-codebases/SKILL.md
   - Generate _MAP.md hierarchy via AST/tree-sitter
   - This is the PRIMARY navigation artifact

3. GATHER overview
   Priority order:
   a) _MAP.md files (highest priority - structural truth)
   b) Root README.md (project intent, setup)
   c) AGENTS.md / CLAUDE.md if present (interaction hints)
   
   Note: When reviewing CODE, _MAPs > README > AGENTS/CLAUDE
   The maps show what IS; docs show what authors CLAIM

4. EXPLORE based on objective
   - Architecture assessment: follow import graphs in _MAPs
   - Security review: entry points, auth patterns, data flow
   - PR review: changed files + their _MAP context
   - General exploration: breadth-first through map hierarchy

SKILL REFS:
- /mnt/skills/user/accessing-github-repos/SKILL.md (tarball fetch)
- /mnt/skills/user/mapping-codebases/SKILL.md (AST mapping)

---
