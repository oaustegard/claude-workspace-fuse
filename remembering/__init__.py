"""Public surface of the remembering package.

`scripts/__init__.py` already re-exports the memory API, and the boot-written
`.pth` puts this directory on `sys.path`, so `from scripts import remember`
works. The natural spelling — `from remembering import remember` — did not,
because this package had no `__init__.py` at all and resolved as a namespace
package. That failure mode is silent about the fix: the ImportError names the
symbol, not the module that actually holds it, so the reader's next move is to
guess a second path, then a third, then grep. Measured cost of exactly that on
2026-08-11: three tool calls and several minutes, for an API used every session.

Delegation is lazy (PEP 562) rather than a top-level `from .scripts import *`,
so `import remembering` still costs nothing until an attribute is touched.
`scripts` pulls `requests` and opens the Turso config path on import, and boot
imports this package before credentials are necessarily sourced.
"""

from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "_exec",
    "boot",
    "config_get",
    "config_set",
    "forget",
    "recall",
    "remember",
    "supersede",
    "task",
]


def __getattr__(name: str) -> Any:
    """Resolve public names from `.scripts` on first access, then cache.

    Dunders are refused outright: the import machinery probes `__path__`,
    `__all__`, and friends on partially-initialized modules, and answering
    those through `scripts` would turn a missing attribute into an import of
    the whole memory stack at interpreter startup.
    """
    if name.startswith("__") and name.endswith("__"):
        raise AttributeError(name)
    scripts = importlib.import_module(".scripts", __name__)
    try:
        value = getattr(scripts, name)
    except AttributeError:
        raise AttributeError(
            f"module 'remembering' has no attribute {name!r}; "
            f"it is not re-exported by remembering.scripts either"
        ) from None
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(__all__) | set(globals()))
