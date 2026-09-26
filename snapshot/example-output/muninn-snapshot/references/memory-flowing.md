---
tag: flowing
memory_count: 6
date_range: 2026-03-19 to 2026-05-08
---

# flowing

_6 memories from Muninn's past, primary tag `flowing`._

## 2026-05-08 — anomaly (p1) `028f3c29`
_tags: flowing-v1.1, authoring-gotcha, docs-gap, 2026-05-07_

flowing v1.1 GOTCHA: detached=True tasks must be passed as terminals to Flow(...) to be discovered.

Flow._collect_tasks() walks the dep graph BACKWARD from terminals via depends_on. A detached
task that depends on the main terminal is NOT discovered automatically — it's downstream, not
upstream. Result: detached body never runs, log shows `detached=0`, no error raised.

WRONG (silent skip):
    Flow(assemble).run()  # store_memory(detached=True, depends_on=[assemble]) never fires

RIGHT:
    Flow(assemble, store_memory).run()  # both terminals; detached layer runs after main DAG

The SKILL.md "Detached tasks" section says "Run in a final layer after the main DAG" which
implies auto-discovery. It doesn't. Either the docs need a one-line clarifier ("pass detached
tasks as additional terminals to Flow()") or the runner should auto-discover detached tasks
that depend on declared terminals.

Found 2026-05-07 testing v1.1 features. File: /home/claude/test_flowing.py demonstrates both
the wrong and right form.

---

## 2026-05-08 — decision (p1) `1ce29655`
_tags: preference, correction, skill-versioning, PR-612, 2026-05-07_

PREFERENCE SIGNAL — skill version bumps are mandatory.

Evidence: After opening claude-skills PR #612 (docs-only change to flowing/SKILL.md adding a 'Validator and predicate signatures' subsection), [REDACTED] said: 'You ALWAYS have to update a skill's version in the frontmatter when you change the skill.'

Implication: Every modification to a SKILL.md (or to scripts under a versioned skill) requires bumping `metadata.version` in the frontmatter, even for docs-only changes. SemVer applies: PATCH for docs/clarifications/bug fixes, MINOR for backward-compat new functionality, MAJOR for breaks. The CHANGELOG entry must use the actual version number, not [Unreleased].

Future default: Before opening any PR that touches a SKILL.md or its scripts, check the frontmatter version, bump it appropriately, and add a CHANGELOG entry under the new version header (not [Unreleased]). Apply the same to skill scripts that have a version (e.g. flowing.py's module version if exposed). If unsure whether a change qualifies — assume yes, bump.

Caught the omission on PR #612: did docs change without bump (version 1.1.0 stayed, CHANGELOG used [Unreleased]). Pushed follow-up commits to bump to 1.1.1 and finalize the CHANGELOG header.

---

## 2026-05-08 — procedure (p0) `8ec90998`
_tags: utility-code, orchestration, shim, single-source-of-truth, 2026-05-07_

NAME: flowing
PURPOSE: DAG workflow runner. Encodes control flow in code (when=, validate=, retry_until=) instead of prose. The runner owns the graph; the LLM provides leaves. Parallel execution, checkpoint resume, detached side-effects.
USE WHEN: You have 3+ sequential tool calls where the workflow shape is known upfront. Also when pipelines need checkpoint resume (fix step N, resume without re-running steps 1 to N-1), or when side-effects (memory storage, notifications) should not block the main pipeline.
DEPS: flowing skill at /mnt/skills/user/flowing/scripts/flowing.py (canonical source of truth)
---
<<<PYTHON>>>
"""muninn_utils.flowing — thin re-export of the canonical flowing skill module.

Historically it held a frozen copy of the flowing source, which drifted from
the canonical /mnt/skills/user/flowing/ skill (e.g. v1.0 here while v1.1+
shipped in the skill, with the older copy shadowing the newer via .pth order).

Now it just re-exports the canonical module via importlib, so the skill is the
single source of truth and `from flowing import x` / `from muninn_utils import
flowing` / `from muninn_utils.flowing import x` all resolve to the same code.
"""
import importlib.util as _ilu
import os as _os
import sys as _sys

_SKILL_PATH = "/mnt/skills/user/flowing/scripts/flowing.py"

if not _os.path.exists(_SKILL_PATH):
    raise ImportError(
        f"flowing skill not found at {_SKILL_PATH}. "
        "Boot may have failed to install /mnt/skills/user/flowing/."
    )

# Load the canonical skill module. Register under the public name `flowing`
# in sys.modules BEFORE exec so that @dataclass introspection (which looks up
# sys.modules[cls.__module__]) succeeds during class creation. This also means
# downstream `import flowing` resolves to the same canonical module object.
_spec = _ilu.spec_from_file_location("flowing", _SKILL_PATH)
_canonical = _ilu.module_from_spec(_spec)
_sys.modules["flowing"] = _canonical
_spec.loader.exec_module(_canonical)

# Re-export the public surface. Mirror what `from flowing import *` would expose;
# explicit list keeps this stable if the canonical adds private helpers.
task = _canonical.task
Flow = _canonical.Flow
TaskDef = _canonical.TaskDef
StepState = _canonical.StepState

__all__ = ["task", "Flow", "TaskDef", "StepState"]
<<<END>>>

**Refs:**
- e5d74fad-06b9-4a47-b1a2-0b25c248ac47

---

## 2026-05-08 — procedure (p1) `19772489`
_tags: validate, when, authoring-gotcha, 2026-05-07_

flowing v1.1 `validate=` callables receive kwargs by dep NAME, same as task bodies. A validator written with `def must_have_title(fetch_url_meta)` works only for tasks whose dep is named `fetch_url_meta`. Renaming the dep (or reusing the validator across tasks with differently-named deps) raises `TypeError: got an unexpected keyword argument 'foo'` at validate time, surfacing as FAIL of the dependent task.

Same applies to `when=` predicates.

Patterns:
- Single-purpose validator tied to one task: name params after the deps.
- Reusable validator across tasks with different dep names: take `**kwargs` and pull by expected key — loses some explicitness.
- Cleaner: validator factory — `def must_have_title_of(dep_name): def v(**kwargs): if not kwargs[dep_name].get('title'): raise ...; return v`.

Discovered 2026-05-07 while testing — wrote `must_have_title(fetch_url_meta)` then reused across a task whose dep was named `fetch_bad_meta`. Validator failed with signature mismatch, not the intended empty-title error.

---

## 2026-03-20 — decision (p0) `fa27d43c`
_tags: issue-418, shipped, review_

PR #419 merged: flowing skill now standalone with resume(), override(), detached=True. Updated utility-code memory (d5257cb9 → e5d74fad) and ops:flowing-imperative config. Therapy utility doesn't need changes — phase1 DAG is flat (4 independent + 1 compile), no chains to resume. searching-codebases/scripts/flowing.py still has old vendored copy — needs Claude Code update. Consolidated utility catalog (84a98b96) references flowing but inherits from utility-code memory.

---

## 2026-03-19 — experience (p0) `1366dc9b`
_tags: tool-call-overhead, token-discipline, architecture, experience, issue-404, correction_

BEHAVIORAL INSIGHT (CORRECTED): Plan-then-batch beats discover-as-you-go under tool-call constraints. Thinking tokens are NOT free — they're priced as output tokens. But planning is still cheaper than tool calls because a tool call costs: thinking to decide + execution + full context re-prefill on return + thinking to process result. Planning is O(output_tokens). Tool call round-trip is O(context_length) prefill + output on both sides. Ratio worsens as conversation grows — exactly when you hit the 20-call ceiling. Pattern: (1) PLAN in thinking — list all queries upfront, separate independent from dependent. (2) BROAD SWEEP in one tool call — batch all independent operations via flowing DAG or single python block. (3) TARGETED DEEP DIVE — adaptive tool calls only for genuine surprises from Phase 2. Searching-codebases demonstrates: plan N queries upfront, run all against one index in one call, deep-dive selectively. Applies to: therapy Phase 1, web research, dream review, architecture comparison. Web search/fetch are Claude tool calls not Python-callable — requires behavioral discipline, not programmatic batching.

**Refs:**
- 07021003-ea95-4ac3-942d-f05a870f3cb9

---
