"""`from remembering import remember` must work, and must stay lazy.

Both halves are load-bearing. Without the re-export the import fails and the
caller guesses paths; with an eager `from .scripts import *` it succeeds but
drags `requests` and the Turso config path into every `import remembering`,
including boot's, before credentials are necessarily sourced.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

PUBLIC = ["remember", "recall", "supersede", "forget", "config_get", "config_set", "_exec"]


def _run(snippet: str) -> str:
    """Run in a clean interpreter — laziness is a property of a fresh import."""
    out = subprocess.run(
        [sys.executable, "-c", snippet],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert out.returncode == 0, out.stderr
    return out.stdout.strip()


def test_public_names_resolve():
    got = _run(
        "import remembering as m;"
        f"print(all(callable(getattr(m, n)) for n in {PUBLIC!r}))"
    )
    assert got == "True"


def test_from_import_spelling_works():
    got = _run(
        "from remembering import remember, recall, config_get;"
        "print(remember.__name__, recall.__name__, config_get.__name__)"
    )
    assert got == "remember recall config_get"


def test_bare_import_does_not_load_scripts():
    got = _run("import sys, remembering; print('remembering.scripts' in sys.modules)")
    assert got == "False"


def test_attribute_access_loads_scripts():
    got = _run("import sys, remembering; remembering.remember; print('remembering.scripts' in sys.modules)")
    assert got == "True"


def test_unknown_attribute_raises_attribute_error():
    got = _run(
        "import remembering\n"
        "try:\n"
        "    remembering.definitely_not_here\n"
        "except AttributeError as e:\n"
        "    print('AttributeError' if 'no attribute' in str(e) else 'wrong')\n"
    )
    assert got == "AttributeError"


def test_dunder_probe_does_not_import_scripts():
    """Import machinery probes dunders; answering them must not load the stack."""
    got = _run(
        "import sys, remembering\n"
        "for n in ('__path__', '__all__', '__wrapped__'):\n"
        "    getattr(remembering, n, None)\n"
        "print('remembering.scripts' in sys.modules)\n"
    )
    assert got == "False"


def test_submodule_import_still_works():
    got = _run("from remembering.scripts.memory import remember; print(remember.__name__)")
    assert got == "remember"
