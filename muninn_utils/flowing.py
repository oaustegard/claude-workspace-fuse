"""muninn_utils.flowing — thin re-export of the canonical flowing skill module.

Historically a frozen Turso copy of the flowing source, which drifted from the
canonical /mnt/skills/user/flowing/ skill (e.g. v1.0 here while v1.1+ shipped in
the skill, with the older copy shadowing the newer via .pth order).

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
