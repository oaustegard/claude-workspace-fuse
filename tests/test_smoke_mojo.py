"""Regression tests for issue #63: mojo_check must not call `mojo --version`.

Previously the smoke check ran `mojo --version` inside a 30s subprocess,
which routinely timed out on first-invoke licensing probes and surfaced
a red `mojo_check` failure on every UserPromptSubmit. The fix replaces
the subprocess with `shutil.which("mojo")`.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
# flowing import lives next to the smoke test
sys.path.insert(0, "/mnt/skills/user/flowing/scripts")

import smoke_test  # noqa: E402


def _unwrap(task_obj):
    """Reach past @task and @_safe wrappers to the underlying behavior."""
    fn = task_obj
    while hasattr(fn, "fn"):
        fn = fn.fn
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    return fn


def test_mojo_check_does_not_call_mojo_version():
    """The fix is structural: mojo --version subprocess must be gone."""
    src = (REPO / "scripts" / "smoke_test.py").read_text()
    assert '"mojo", "--version"' not in src, (
        "mojo --version subprocess reintroduced — issue #63 regression"
    )
    assert "shutil.which" in src, "shutil.which probe missing"


def test_mojo_check_raises_when_binary_missing():
    """When mojo is not on PATH, mojo_check returns ok=False with a clear error."""
    with patch.object(smoke_test.shutil, "which", return_value=None):
        result = smoke_test.mojo_check()
    assert result["ok"] is False
    assert "mojo not found on PATH" in result["error"]


def test_mojo_check_uses_path_from_which(monkeypatch, tmp_path):
    """When mojo IS on PATH, mojo_check runs the smoke program and returns its path."""
    fake_mojo = tmp_path / "mojo"
    fake_mojo.write_text("#!/bin/sh\nexit 0\n")
    fake_mojo.chmod(0o755)

    class FakeCompleted:
        returncode = 0
        stdout = "ok\n"
        stderr = ""

    monkeypatch.setattr(smoke_test.shutil, "which", lambda _: str(fake_mojo))
    monkeypatch.setattr(smoke_test.subprocess, "run", lambda *a, **kw: FakeCompleted())

    result = smoke_test.mojo_check()
    assert result["ok"] is True
    assert result["path"] == str(fake_mojo)


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
