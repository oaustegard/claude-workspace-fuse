#!/usr/bin/env python3
"""Post-build smoke test for the Muninn container layer.

Runs independent validators against the freshly-built container and
aggregates a pass/fail report. Each validator owns one capability;
failures land independently — one broken capability doesn't mask the others.

Wired as a `flowing` graph: validators fan out in parallel, `report`
aggregates. fail_fast=False so a failure in (e.g.) Mojo doesn't stop
the PyTorch / PySR / gh checks from running and reporting.

Exit codes:
    0 — all validators passed
    1 — one or more validators failed (details in /tmp/.smoke-failures)

Issue: https://github.com/oaustegard/claude-workspace/issues/52
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SKILLS_DIR = Path(os.environ.get("SKILLS_DIR", "/mnt/skills/user"))
sys.path.insert(0, str(SKILLS_DIR / "flowing" / "scripts"))

from flowing import Flow, task  # noqa: E402

FAILURES_MARKER = Path("/tmp/.smoke-failures")


def _safe(fn):
    """Catch any exception in a validator, return {ok: False, error: ...}.

    Validators must never raise — a raised exception would mark the task
    FAILED and skip downstream `report`, masking the other capability checks.
    Convert exceptions to data so the aggregator sees every check's outcome.
    """
    def wrapped():
        t0 = time.monotonic()
        try:
            payload = fn() or {}
            payload.setdefault("ok", True)
        except BaseException as e:
            payload = {"ok": False, "error": f"{type(e).__name__}: {e}"}
        payload["ms"] = int((time.monotonic() - t0) * 1000)
        payload["check"] = fn.__name__
        return payload
    wrapped.__name__ = fn.__name__
    return wrapped


@task
@_safe
def torch_check():
    import torch
    s = torch.tensor([1, 2, 3]).sum().item()
    if s != 6:
        raise AssertionError(f"torch.tensor sum mismatch: {s} != 6")
    return {"version": torch.__version__}


@task
@_safe
def pysr_check():
    import pysr
    _ = pysr.PySRRegressor
    return {"version": getattr(pysr, "__version__", "unknown")}


@task
@_safe
def mojo_check():
    ver = subprocess.run(
        ["mojo", "--version"], capture_output=True, text=True, timeout=30,
    )
    if ver.returncode != 0:
        raise RuntimeError(f"mojo --version exit {ver.returncode}: {ver.stderr.strip()}")

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".mojo", delete=False,
    ) as f:
        f.write('fn main():\n    print("ok")\n')
        prog_path = f.name
    try:
        prog = subprocess.run(
            ["mojo", "run", prog_path],
            capture_output=True, text=True, timeout=120,
        )
    finally:
        os.unlink(prog_path)
    if prog.returncode != 0 or "ok" not in prog.stdout:
        raise RuntimeError(
            f"mojo run failed: exit={prog.returncode} "
            f"stdout={prog.stdout!r} stderr={prog.stderr.strip()[:200]!r}"
        )
    return {"version": ver.stdout.strip().splitlines()[0]}


@task
@_safe
def tree_sitter_check():
    # The 1.6.3 wheel was broken — it shipped only _native/ and missed the
    # python module, so `import tree_sitter_language_pack` raised
    # ModuleNotFoundError. Touching the python surface (importing the module
    # and resolving an attribute) catches that regression. We deliberately
    # don't call `get_language` here: it fetches parsers.json over the
    # network, which fails under gVisor's TLS sandbox and would conflate a
    # network problem with a broken wheel.
    import tree_sitter  # noqa: F401
    import tree_sitter_language_pack as tslp
    if not hasattr(tslp, "get_language"):
        raise RuntimeError("tree_sitter_language_pack missing get_language attribute")
    return {"version": getattr(tslp, "__version__", "unknown")}


@task
@_safe
def gh_check():
    ver = subprocess.run(
        ["gh", "--version"], capture_output=True, text=True, timeout=10,
    )
    if ver.returncode != 0:
        raise RuntimeError(f"gh --version exit {ver.returncode}: {ver.stderr.strip()}")

    auth_ok = None
    if os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN"):
        rate = subprocess.run(
            ["gh", "api", "/rate_limit"], capture_output=True, text=True, timeout=15,
        )
        if rate.returncode != 0:
            raise RuntimeError(f"gh api /rate_limit failed: {rate.stderr.strip()[:200]}")
        auth_ok = True
    return {
        "version": ver.stdout.splitlines()[0] if ver.stdout else "",
        "auth_ok": auth_ok,
    }


@task
@_safe
def py_deps_check():
    import httpx
    import libsql_experimental  # noqa: F401
    import pandas
    import scipy
    import sklearn
    return {
        "scipy": scipy.__version__,
        "sklearn": sklearn.__version__,
        "pandas": pandas.__version__,
        "httpx": httpx.__version__,
    }


VALIDATORS = [
    torch_check, pysr_check, mojo_check,
    tree_sitter_check, gh_check, py_deps_check,
]


@task(depends_on=VALIDATORS)
def report(**checks):
    failed = {n: r for n, r in checks.items() if not r.get("ok")}
    return {
        "ok": not failed,
        "n_checks": len(checks),
        "n_failed": len(failed),
        "failed_names": sorted(failed),
        "checks": checks,
    }


def run_smoke() -> dict:
    """Run the smoke graph and return the aggregated report dict.

    Importable so `drift_workflow.py` can call it without re-shelling.
    """
    flow = Flow(report, fail_fast=False)
    results = flow.run()
    return results["report"].value


def main(argv):
    rep = run_smoke()
    print(json.dumps(rep, indent=2))
    if rep["ok"]:
        FAILURES_MARKER.unlink(missing_ok=True)
        return 0
    FAILURES_MARKER.write_text(json.dumps(rep, indent=2))
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
