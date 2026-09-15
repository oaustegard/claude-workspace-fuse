---
tag: skills
memory_count: 2
date_range: 2026-01-25 to 2026-04-11
---

# skills

_2 memories from Muninn's past, primary tag `skills`._

## 2026-04-11 — decision (p1) `44a39924`
_tags: correction, preference, boot, architecture_

[REDACTED] flagged "deployed via Anthropic's sync mechanism" as wrong — skills are installed by the boot script (curl tarball from GitHub + tar extract), not by any Anthropic mechanism. → Never attribute skill installation to Anthropic. The boot script does it.

---

## 2026-01-25 — experience (p1) `d45213c7`
_tags: python, import-shim, technical-pattern_

PYTHON IMPORT BYPASS FOR INVALID IDENTIFIERS

Solution: importlib.util.spec_from_file_location() bypasses Python's import naming rules entirely.
It loads modules by filesystem path, not by identifier. The module name you register in
sys.modules can be anything—it's just a lookup key.

Pattern:
    spec = importlib.util.spec_from_file_location('any_name_here', '/path/to/file.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules['any_name_here'] = module
    spec.loader.exec_module(module)

Why it works: Python's import statement does identifier validation. Direct spec loading
doesn't—it's just "load this file as a module." The dash/underscore mismatch becomes irrelevant.

Implemented in: muninn_utils/skill_loader.py

---
