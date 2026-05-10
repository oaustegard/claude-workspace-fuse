"""Tests for scripts/tdd_hook.py — TDD enforcement hooks (issue #69)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import tdd_hook  # noqa: E402


# ---------------------------------------------------------------------------
# File classification
# ---------------------------------------------------------------------------

class TestIsTestFile:
    def test_test_underscore_prefix(self):
        assert tdd_hook.is_test_file("tests/test_foo.py")

    def test_underscore_test_suffix(self):
        assert tdd_hook.is_test_file("pkg/foo_test.py")

    def test_dot_test_in_name(self):
        assert tdd_hook.is_test_file("lib/foo.test.js")

    def test_dot_spec_in_name(self):
        assert tdd_hook.is_test_file("lib/foo.spec.ts")

    def test_directory_named_tests(self):
        assert tdd_hook.is_test_file("a/b/tests/something.py")

    def test_directory_named_test_singular(self):
        assert tdd_hook.is_test_file("a/test/something.py")

    def test_directory_named_double_underscore_tests(self):
        assert tdd_hook.is_test_file("a/__tests__/something.js")

    def test_impl_file_is_not_test(self):
        assert not tdd_hook.is_test_file("src/foo.py")

    def test_root_impl_file_is_not_test(self):
        assert not tdd_hook.is_test_file("foo.py")


# ---------------------------------------------------------------------------
# Mapping
# ---------------------------------------------------------------------------

class TestExpectedTestFor:
    MAPPINGS = [
        {"impl": r"remembering/(.+)\.py$", "test": r"remembering/tests/test_\1.py"},
        {"impl": r"src/(.+)\.py$",         "test": r"tests/test_\1.py"},
        {"impl": r"lib/(.+)\.js$",         "test": r"test/\1.test.js"},
    ]

    def test_simple_match(self):
        assert tdd_hook.expected_test_for("src/foo.py", self.MAPPINGS) == "tests/test_foo.py"

    def test_nested_match(self):
        assert tdd_hook.expected_test_for("src/a/b.py", self.MAPPINGS) == "tests/test_a/b.py"

    def test_remembering_match(self):
        got = tdd_hook.expected_test_for("remembering/foo.py", self.MAPPINGS)
        assert got == "remembering/tests/test_foo.py"

    def test_js_match(self):
        assert tdd_hook.expected_test_for("lib/foo.js", self.MAPPINGS) == "test/foo.test.js"

    def test_no_match(self):
        assert tdd_hook.expected_test_for("docs/readme.md", self.MAPPINGS) is None

    def test_invalid_regex_skipped(self):
        bad = [{"impl": "[unclosed", "test": "x"}, {"impl": r"src/(.+)\.py$", "test": r"tests/test_\1.py"}]
        assert tdd_hook.expected_test_for("src/foo.py", bad) == "tests/test_foo.py"


class TestNormalizePaths:
    def test_adds_trailing_slash(self):
        assert tdd_hook._normalize_paths(["src", "lib/"]) == ["src/", "lib/"]

    def test_strips_leading_dotslash(self):
        assert tdd_hook._normalize_paths(["./src"]) == ["src/"]

    def test_drops_empty(self):
        assert tdd_hook._normalize_paths(["", "  "]) == []


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

class TestLoadConfig:
    def test_missing_file_returns_none(self, tmp_path):
        assert tdd_hook.load_config(tmp_path) is None

    def test_valid_json_loads(self, tmp_path):
        cfg_dir = tmp_path / ".claude"
        cfg_dir.mkdir()
        (cfg_dir / "tdd-config.json").write_text('{"tdd_default_paths": ["src/"]}')
        assert tdd_hook.load_config(tmp_path) == {"tdd_default_paths": ["src/"]}

    def test_invalid_json_returns_none(self, tmp_path):
        cfg_dir = tmp_path / ".claude"
        cfg_dir.mkdir()
        (cfg_dir / "tdd-config.json").write_text("{not json")
        assert tdd_hook.load_config(tmp_path) is None


# ---------------------------------------------------------------------------
# Violation detection (commit gate logic)
# ---------------------------------------------------------------------------

class TestFindViolations:
    CONFIG = {
        "tdd_default_paths": ["src/", "remembering/"],
        "tdd_skip_paths":    ["docs/", "scripts/oneshot/"],
        "test_mapping": [
            {"impl": r"remembering/(.+)\.py$", "test": r"remembering/tests/test_\1.py"},
            {"impl": r"src/(.+)\.py$",         "test": r"tests/test_\1.py"},
        ],
    }

    def test_impl_without_test_is_violation(self):
        v = tdd_hook.find_violations(["src/foo.py"], self.CONFIG)
        assert v == [("src/foo.py", "tests/test_foo.py")]

    def test_impl_with_paired_test_passes(self):
        v = tdd_hook.find_violations(["src/foo.py", "tests/test_foo.py"], self.CONFIG)
        assert v == []

    def test_test_only_change_passes(self):
        v = tdd_hook.find_violations(["tests/test_foo.py"], self.CONFIG)
        assert v == []

    def test_skip_path_ignored(self):
        v = tdd_hook.find_violations(["docs/readme.md", "src/foo.py"], self.CONFIG)
        assert v == [("src/foo.py", "tests/test_foo.py")]

    def test_outside_default_paths_ignored(self):
        v = tdd_hook.find_violations(["lib/random.py"], self.CONFIG)
        assert v == []

    def test_remembering_path_uses_local_tests_dir(self):
        v = tdd_hook.find_violations(["remembering/foo.py"], self.CONFIG)
        assert v == [("remembering/foo.py", "remembering/tests/test_foo.py")]

    def test_remembering_with_paired_test_passes(self):
        v = tdd_hook.find_violations(
            ["remembering/foo.py", "remembering/tests/test_foo.py"], self.CONFIG,
        )
        assert v == []

    def test_no_default_paths_means_check_everything(self):
        cfg = {**self.CONFIG, "tdd_default_paths": []}
        cfg["test_mapping"] = [{"impl": r"(.+)\.py$", "test": r"tests/test_\1.py"}]
        v = tdd_hook.find_violations(["random/foo.py"], cfg)
        assert v == [("random/foo.py", "tests/test_random/foo.py")]


# ---------------------------------------------------------------------------
# PreToolUse end-to-end (commit gate)
# ---------------------------------------------------------------------------

class TestPretooluse:
    CONFIG = {
        "tdd_default_paths": ["src/"],
        "test_mapping": [{"impl": r"src/(.+)\.py$", "test": r"tests/test_\1.py"}],
    }

    def _setup(self, tmp_path):
        cfg_dir = tmp_path / ".claude"
        cfg_dir.mkdir()
        (cfg_dir / "tdd-config.json").write_text(json.dumps(self.CONFIG))

    def test_non_bash_tool_passes(self, tmp_path):
        self._setup(tmp_path)
        payload = {"tool_name": "Edit", "tool_input": {}}
        assert tdd_hook.pretooluse(payload, tmp_path) is None

    def test_non_commit_bash_passes(self, tmp_path):
        self._setup(tmp_path)
        payload = {"tool_name": "Bash", "tool_input": {"command": "ls -la"}}
        assert tdd_hook.pretooluse(payload, tmp_path) is None

    def test_missing_config_passes(self, tmp_path):
        payload = {"tool_name": "Bash", "tool_input": {"command": "git commit -m 'x'"}}
        assert tdd_hook.pretooluse(payload, tmp_path) is None

    def test_tdd_skip_marker_bypasses(self, tmp_path):
        self._setup(tmp_path)
        with patch.object(tdd_hook, "staged_files", return_value=["src/foo.py"]):
            payload = {
                "tool_name": "Bash",
                "tool_input": {"command": "git commit -m 'fix\n\ntdd-skip: legacy file'"},
            }
            assert tdd_hook.pretooluse(payload, tmp_path) is None

    def test_tdd_skip_marker_works_with_literal_backslash_n(self, tmp_path):
        """Regression: \\b boundary used to fail when preceding char was the literal `n` of `\\n`."""
        self._setup(tmp_path)
        with patch.object(tdd_hook, "staged_files", return_value=["src/foo.py"]):
            payload = {
                "tool_name": "Bash",
                "tool_input": {"command": 'git commit -m "wip\\n\\ntdd-skip: bootstrap"'},
            }
            assert tdd_hook.pretooluse(payload, tmp_path) is None

    def test_violation_returns_deny(self, tmp_path):
        self._setup(tmp_path)
        with patch.object(tdd_hook, "staged_files", return_value=["src/foo.py"]):
            payload = {
                "tool_name": "Bash",
                "tool_input": {"command": "git commit -m 'wip'"},
            }
            result = tdd_hook.pretooluse(payload, tmp_path)
        assert result is not None
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
        reason = result["hookSpecificOutput"]["permissionDecisionReason"]
        assert "src/foo.py" in reason
        assert "tests/test_foo.py" in reason
        assert "tdd-skip:" in reason

    def test_paired_test_passes(self, tmp_path):
        self._setup(tmp_path)
        with patch.object(
            tdd_hook, "staged_files", return_value=["src/foo.py", "tests/test_foo.py"]
        ):
            payload = {
                "tool_name": "Bash",
                "tool_input": {"command": "git commit -m 'add foo'"},
            }
            assert tdd_hook.pretooluse(payload, tmp_path) is None

    def test_empty_staged_passes(self, tmp_path):
        self._setup(tmp_path)
        with patch.object(tdd_hook, "staged_files", return_value=[]):
            payload = {
                "tool_name": "Bash",
                "tool_input": {"command": "git commit -m 'nothing'"},
            }
            assert tdd_hook.pretooluse(payload, tmp_path) is None


# ---------------------------------------------------------------------------
# PostToolUse end-to-end (test runner)
# ---------------------------------------------------------------------------

class TestPosttooluse:
    CONFIG = {
        "tdd_default_paths": ["src/"],
        "test_mapping": [{"impl": r"src/(.+)\.py$", "test": r"tests/test_\1.py"}],
    }

    def _setup(self, tmp_path, with_test=False):
        cfg_dir = tmp_path / ".claude"
        cfg_dir.mkdir()
        (cfg_dir / "tdd-config.json").write_text(json.dumps(self.CONFIG))
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "foo.py").write_text("def foo(): return 1\n")
        if with_test:
            (tmp_path / "tests").mkdir()
            (tmp_path / "tests" / "test_foo.py").write_text(
                "import sys\nsys.path.insert(0, 'src')\n"
                "from foo import foo\n"
                "def test_foo():\n    assert foo() == 1\n"
            )

    def test_non_edit_tool_skipped(self, tmp_path):
        self._setup(tmp_path)
        payload = {"tool_name": "Bash", "tool_input": {}}
        assert tdd_hook.posttooluse(payload, tmp_path) is None

    def test_missing_config_skipped(self, tmp_path):
        payload = {"tool_name": "Edit", "tool_input": {"file_path": str(tmp_path / "src/foo.py")}}
        assert tdd_hook.posttooluse(payload, tmp_path) is None

    def test_test_file_edit_skipped(self, tmp_path):
        self._setup(tmp_path)
        payload = {
            "tool_name": "Edit",
            "tool_input": {"file_path": str(tmp_path / "tests/test_foo.py")},
        }
        assert tdd_hook.posttooluse(payload, tmp_path) is None

    def test_outside_default_path_skipped(self, tmp_path):
        self._setup(tmp_path)
        (tmp_path / "lib").mkdir()
        payload = {
            "tool_name": "Edit",
            "tool_input": {"file_path": str(tmp_path / "lib/random.py")},
        }
        assert tdd_hook.posttooluse(payload, tmp_path) is None

    def test_missing_test_returns_red_note(self, tmp_path):
        self._setup(tmp_path, with_test=False)
        payload = {
            "tool_name": "Edit",
            "tool_input": {"file_path": str(tmp_path / "src/foo.py")},
        }
        result = tdd_hook.posttooluse(payload, tmp_path)
        assert result is not None
        ctx = result["hookSpecificOutput"]["additionalContext"]
        assert "MISSING" in ctx
        assert "tests/test_foo.py" in ctx

    def test_existing_test_runs_and_reports(self, tmp_path):
        self._setup(tmp_path, with_test=True)
        payload = {
            "tool_name": "Edit",
            "tool_input": {"file_path": str(tmp_path / "src/foo.py")},
        }
        with patch.object(
            tdd_hook,
            "run_tests",
            return_value="[tdd-hook] tests/test_foo.py: PASS\n1 passed",
        ) as mock_run:
            result = tdd_hook.posttooluse(payload, tmp_path)
        assert mock_run.called
        ctx = result["hookSpecificOutput"]["additionalContext"]
        assert "PASS" in ctx

    def test_skip_path_ignored(self, tmp_path):
        cfg = {
            **self.CONFIG,
            "tdd_skip_paths": ["src/oneshot/"],
        }
        cfg_dir = tmp_path / ".claude"
        cfg_dir.mkdir()
        (cfg_dir / "tdd-config.json").write_text(json.dumps(cfg))
        (tmp_path / "src" / "oneshot").mkdir(parents=True)
        payload = {
            "tool_name": "Edit",
            "tool_input": {"file_path": str(tmp_path / "src/oneshot/foo.py")},
        }
        assert tdd_hook.posttooluse(payload, tmp_path) is None


# ---------------------------------------------------------------------------
# CLI invocation
# ---------------------------------------------------------------------------

class TestCli:
    def test_no_subcommand_exits_clean(self):
        proc = subprocess.run(
            [sys.executable, str(REPO / "scripts" / "tdd_hook.py")],
            input="{}", capture_output=True, text=True, timeout=10,
        )
        assert proc.returncode == 0

    def test_invalid_json_stdin_exits_clean(self):
        proc = subprocess.run(
            [sys.executable, str(REPO / "scripts" / "tdd_hook.py"), "posttooluse"],
            input="not json", capture_output=True, text=True, timeout=10,
        )
        assert proc.returncode == 0

    def test_pretooluse_block_emits_json(self, tmp_path):
        cfg_dir = tmp_path / ".claude"
        cfg_dir.mkdir()
        (cfg_dir / "tdd-config.json").write_text(json.dumps({
            "tdd_default_paths": ["src/"],
            "test_mapping": [{"impl": r"src/(.+)\.py$", "test": r"tests/test_\1.py"}],
        }))
        # Initialise a git repo with a staged impl file but no test.
        env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
        subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), env=env, check=True)
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "foo.py").write_text("x = 1\n")
        subprocess.run(["git", "add", "src/foo.py"], cwd=str(tmp_path), env=env, check=True)

        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "git commit -m 'wip'"},
            "cwd": str(tmp_path),
        }
        proc = subprocess.run(
            [sys.executable, str(REPO / "scripts" / "tdd_hook.py"), "pretooluse"],
            input=json.dumps(payload), capture_output=True, text=True, timeout=10,
        )
        assert proc.returncode == 0
        out = json.loads(proc.stdout)
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
