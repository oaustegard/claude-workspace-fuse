"""Tests for muninn_utils.run_gate.

The runner is injectable, so everything below the shell is exercised without
spawning processes. Three tests at the bottom do spawn a real /bin/sh, because
the whole point of the module is what the shell's exit code does to the output.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from muninn_utils.run_gate import (
    FAIL_MARK,
    PASS_MARK,
    format_gate,
    format_stage,
    main,
    run_gate,
    run_stage,
)


def fake_runner(script):
    """Build a runner from {command: (returncode, output)}."""

    def _run(command, out_path, **kwargs):
        rc, text = script[command]
        out_path.write_text(text)
        return rc, kwargs.get("timeout") == "expire"

    return _run


def test_passing_stage_reports_one_line(tmp_path):
    runner = fake_runner({"pytest -q": (0, "x" * 5000 + "\n41 passed\n")})
    stage = run_stage("unit", "pytest -q", log_dir=tmp_path, runner=runner)
    line = format_stage(stage)
    assert line.startswith(f"  {PASS_MARK} unit")
    assert "passed" not in line
    assert len(line) < 40


def test_full_dumps_everything(tmp_path):
    body = "\n".join(f"line {i}" for i in range(300))
    runner = fake_runner({"pytest -q": (1, body)})
    stage = run_stage("unit", "pytest -q", log_dir=tmp_path, runner=runner)
    out = format_stage(stage, full=True)
    assert out.startswith(f"  {FAIL_MARK} unit (exit 1")
    assert "line 0" in out and "line 299" in out
    assert "$ pytest -q" in out


def test_failure_extracts_the_error_region_by_default(tmp_path):
    """The default keeps the anchored error, not a slice by position."""
    body = "\n".join(
        [f"[INFO] downloading dep-{i}" for i in range(200)]
        + ["ERROR: undefined reference to `resolve_timeout`"]
        + [f"[INFO] module-{i} SKIPPED" for i in range(200)]
    )
    runner = fake_runner({"make": (2, body)})
    stage = run_stage("build", "make", log_dir=tmp_path, runner=runner)
    out = format_stage(stage)
    assert "undefined reference to `resolve_timeout`" in out
    assert "dep-5" not in out
    assert "module-150" not in out
    assert stage.log_path in out
    assert len(out.splitlines()) < 32  # 401 captured lines in


def test_tail_truncates_and_keeps_the_log_path(tmp_path):
    body = "\n".join(f"line {i}" for i in range(300))
    runner = fake_runner({"c": (1, body)})
    stage = run_stage("unit", "c", log_dir=tmp_path, runner=runner)
    out = format_stage(stage, tail=10)
    assert "line 299" in out
    assert "line 0" not in out
    assert "290 lines elided (lines 1-290)" in out
    assert stage.log_path in out


def test_exit_127_is_named_not_reported_as_a_result(tmp_path):
    runner = fake_runner({"nosuchtool --check": (127, "")})
    stage = run_stage("lint", "nosuchtool --check", log_dir=tmp_path, runner=runner)
    out = format_stage(stage)
    assert "command not found" in out
    assert "did not run" in out


def test_empty_output_on_failure_is_stated(tmp_path):
    runner = fake_runner({"c": (2, "   \n")})
    stage = run_stage("build", "c", log_dir=tmp_path, runner=runner)
    assert "no output captured" in format_stage(stage)


def test_stops_at_first_failure(tmp_path):
    runner = fake_runner({"a": (0, "ok"), "b": (1, "boom"), "c": (0, "never")})
    result = run_gate(
        [("lint", "a"), ("unit", "b"), ("build", "c")],
        log_dir=tmp_path,
        runner=runner,
    )
    assert [s.label for s in result.stages] == ["lint", "unit", "build"]
    assert result.stages[2].skipped
    assert "(skipped)" in format_gate(result)
    assert result.returncode == 1
    assert not result.ok


def test_keep_going_runs_every_stage(tmp_path):
    runner = fake_runner({"a": (1, "first"), "b": (3, "second")})
    result = run_gate(
        [("lint", "a"), ("unit", "b")],
        keep_going=True,
        log_dir=tmp_path,
        runner=runner,
    )
    assert not any(s.skipped for s in result.stages)
    assert result.returncode == 1  # first failure wins
    out = format_gate(result)
    assert "first" in out and "second" in out


def test_all_passing_gate_is_quiet(tmp_path):
    runner = fake_runner({"a": (0, "A" * 9000), "b": (0, "B" * 9000)})
    result = run_gate([("lint", "a"), ("unit", "b")], log_dir=tmp_path, runner=runner)
    out = format_gate(result)
    assert result.ok and result.returncode == 0
    assert "A" not in out and "B" not in out
    assert out.count(PASS_MARK) == 2
    assert len(out) < 80


def test_zero_returncode_with_output_still_hides_it(tmp_path):
    """A warning-laden but successful stage stays silent — exit code is the gate."""
    runner = fake_runner({"a": (0, "WARNING: deprecated\n" * 50)})
    stage = run_stage("build", "a", log_dir=tmp_path, runner=runner)
    assert "WARNING" not in format_stage(stage)


# --- real shell, because the exit code is the contract -----------------------


def test_real_shell_pass(tmp_path):
    stage = run_stage("echo", "echo hello", log_dir=tmp_path)
    assert stage.ok
    assert stage.output.strip() == "hello"
    assert "hello" not in format_stage(stage)


def test_real_shell_captures_stderr_on_failure(tmp_path):
    stage = run_stage("boom", "echo out; echo err >&2; exit 3", log_dir=tmp_path)
    assert stage.returncode == 3
    out = format_stage(stage)
    assert "out" in out and "err" in out


def test_real_shell_missing_command(tmp_path):
    stage = run_stage("missing", "definitely-not-a-command", log_dir=tmp_path)
    assert stage.returncode == 127
    assert "command not found" in format_stage(stage)


def test_timeout_is_a_failure_with_partial_output(tmp_path):
    stage = run_stage("slow", "echo starting; sleep 5", timeout=0.5, log_dir=tmp_path)
    assert stage.timed_out
    assert not stage.ok
    out = format_stage(stage)
    assert "timed out" in out
    assert "starting" in out


def test_main_exit_code_and_json(tmp_path, capsys):
    rc = main(["--stage", "ok", "true", "--stage", "bad", "exit 4", "--json"])
    assert rc == 4
    payload = capsys.readouterr().out
    assert '"returncode": 4' in payload
    assert '"skipped": false' in payload


def test_main_with_no_stages_is_a_usage_error(capsys):
    assert main([]) == 2
    assert "no stages" in capsys.readouterr().err


def test_unlabelled_command_takes_its_first_word(capsys):
    assert main(["echo hi"]) == 0
    line = capsys.readouterr().out.strip()
    assert line.startswith(f"{PASS_MARK} echo")
    assert "hi" not in line


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
