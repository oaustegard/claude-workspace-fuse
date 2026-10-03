"""Run verification stages so a passing one costs a line and a failing one costs everything.

A test, lint or build command that passes emits hundreds of lines that say
nothing. Those lines land in the session context and stay there. This runs each
stage with its output captured to a file, prints one line when it exits 0, and
dumps the whole capture when it does not.

    python3 -m muninn_utils.run_gate --stage lint "ruff check ." --stage unit "pytest -q"

      ✓ lint (0.8s)
      ✗ unit (exit 1, 3.2s)

      FAILED tests/test_parse.py::test_empty - AssertionError
      ...

The failing dump is FULL by default. `--tail N` exists for genuinely enormous
output and always prints the log path alongside, because a wrapper that
discards a diagnostic signal is the failure this is meant to avoid, not a
feature of it (claude-workspace CLAUDE.md: "no wrapper that swallows an exit
code the hook signals with").

Two exit conditions get named rather than dumped, since an empty capture and a
command that never ran look identical in stdout (ops confabulation-cascade,
"empty output is not a result"):

  - exit 127 → reported as command-not-found; the stage did not run.
  - nonzero with an empty capture → reported as such, explicitly.

No fail-fast flag is injected into the commands. `-x` / `--bail` belongs in the
iterate loop and not in a pre-push gate, where a suite cut short at the first
red can leave a regression green behind it.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from muninn_utils.log_extract import extract

PASS_MARK = "\u2713"
FAIL_MARK = "\u2717"

#: Returned by the shell when the command could not be found at all.
NOT_FOUND = 127

#: Returned by `timeout`-style termination in this module.
TIMED_OUT = 124


@dataclass
class StageResult:
    label: str
    command: str
    returncode: int
    output: str
    seconds: float
    log_path: str | None = None
    skipped: bool = False
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.skipped


@dataclass
class GateResult:
    stages: list[StageResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(s.ok for s in self.stages)

    @property
    def returncode(self) -> int:
        for s in self.stages:
            if not s.ok and not s.skipped:
                return s.returncode or 1
        return 0


def _shell_runner(
    command: str,
    out_path: Path,
    *,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    timeout: float | None = None,
    shell_path: str | None = None,
) -> tuple[int, bool]:
    """Run `command`, streaming stdout+stderr into `out_path`.

    Returns (returncode, timed_out). Interleaving is preserved because both
    streams share one file descriptor.
    """
    with out_path.open("wb") as fh:
        proc = subprocess.Popen(
            command,
            shell=True,
            stdout=fh,
            stderr=subprocess.STDOUT,
            cwd=cwd,
            env=env,
            executable=shell_path,
        )
        try:
            return proc.wait(timeout=timeout), False
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            return TIMED_OUT, True


def run_stage(
    label: str,
    command: str,
    *,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    timeout: float | None = None,
    shell_path: str | None = None,
    log_dir: str | Path | None = None,
    runner: Callable[..., tuple[int, bool]] = _shell_runner,
) -> StageResult:
    """Run one command with its output captured to a file."""
    log_dir = Path(log_dir) if log_dir else Path(tempfile.mkdtemp(prefix="run_gate-"))
    log_dir.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in label)[:40] or "stage"
    out_path = log_dir / f"{safe}.log"

    started = time.monotonic()
    rc, timed_out = runner(
        command,
        out_path,
        cwd=cwd,
        env=env,
        timeout=timeout,
        shell_path=shell_path,
    )
    elapsed = time.monotonic() - started

    output = ""
    if out_path.exists():
        output = out_path.read_text(errors="replace")

    return StageResult(
        label=label,
        command=command,
        returncode=rc,
        output=output,
        seconds=elapsed,
        log_path=str(out_path),
        timed_out=timed_out,
    )


def run_gate(
    stages: Sequence[tuple[str, str]],
    *,
    keep_going: bool = False,
    **kwargs,
) -> GateResult:
    """Run stages in order. Stops at the first failure unless `keep_going`."""
    result = GateResult()
    stopped = False
    for label, command in stages:
        if stopped:
            result.stages.append(
                StageResult(label, command, 0, "", 0.0, skipped=True)
            )
            continue
        stage = run_stage(label, command, **kwargs)
        result.stages.append(stage)
        if not stage.ok and not keep_going:
            stopped = True
    return result


def _diagnose(stage: StageResult) -> str | None:
    """Name the failures whose empty output would otherwise read as a result."""
    if stage.timed_out:
        return ("timed out; output below is whatever it had written when killed")
    if stage.returncode == NOT_FOUND:
        return "command not found — the stage did not run, so its output proves nothing"
    if not stage.output.strip():
        return "no output captured — the command exited nonzero without writing anything"
    return None


def format_stage(stage: StageResult, *, tail: int = 0, full: bool = False) -> str:
    """One line for a pass, the failure region for a failure.

    `full` dumps the whole capture. Otherwise log_extract keeps the anchored
    error regions verbatim and replaces the rest with counted line ranges, so
    the epilogue a build tool prints AFTER the error stops costing anything.
    """
    if stage.skipped:
        return f"  - {stage.label} (skipped)"
    if stage.ok:
        return f"  {PASS_MARK} {stage.label} ({stage.seconds:.1f}s)"

    head = f"  {FAIL_MARK} {stage.label} (exit {stage.returncode}, {stage.seconds:.1f}s)"
    lines = [head, f"    $ {stage.command}"]

    note = _diagnose(stage)
    if note:
        lines.append(f"    {note}")

    body = stage.output.rstrip("\n")
    if not body:
        return "\n".join(lines)

    if full:
        lines.append("")
        lines.extend(body.splitlines())
        lines.append("")
        return "\n".join(lines)

    ex = extract(body, tail=tail or 6)
    lines.append("")
    lines.extend(ex.text.splitlines())
    for note in ex.notes:
        lines.append(f"    ({note})")
    if ex.kept_lines < ex.total_lines:
        lines.append(
            f"    [{ex.kept_lines} of {ex.total_lines} lines shown \u2014 full log: {stage.log_path}]"
        )
    lines.append("")
    return "\n".join(lines)


def format_gate(result: GateResult, *, tail: int = 0, full: bool = False) -> str:
    return "\n".join(format_stage(s, tail=tail, full=full) for s in result.stages)


def _as_json(result: GateResult) -> str:
    return json.dumps(
        {
            "ok": result.ok,
            "returncode": result.returncode,
            "stages": [
                {
                    "label": s.label,
                    "command": s.command,
                    "returncode": s.returncode,
                    "seconds": round(s.seconds, 3),
                    "skipped": s.skipped,
                    "timed_out": s.timed_out,
                    "log_path": s.log_path,
                    "output": s.output if not s.ok else "",
                }
                for s in result.stages
            ],
        },
        indent=2,
    )


def _label_for(command: str) -> str:
    try:
        parts = shlex.split(command)
    except ValueError:
        parts = command.split()
    return parts[0] if parts else command[:20]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        prog="run_gate",
        description="Run verification stages; one line per pass, full output per failure.",
    )
    ap.add_argument(
        "--stage",
        nargs=2,
        action="append",
        metavar=("LABEL", "COMMAND"),
        default=[],
        help="A labelled stage. Repeatable; runs in the order given.",
    )
    ap.add_argument(
        "commands",
        nargs="*",
        help="Unlabelled commands; the label is the first word.",
    )
    ap.add_argument("--cwd", default=None, help="Directory to run stages in.")
    ap.add_argument("--timeout", type=float, default=None, help="Per-stage seconds.")
    ap.add_argument(
        "--keep-going",
        action="store_true",
        help="Run every stage even after one fails (default: stop at the first).",
    )
    ap.add_argument(
        "--tail",
        type=int,
        default=0,
        help="Trailing lines always kept alongside the extracted regions (default 6).",
    )
    ap.add_argument(
        "--full",
        action="store_true",
        help="Dump the entire capture on failure instead of extracting the error regions.",
    )
    ap.add_argument(
        "--bash",
        action="store_true",
        help="Run under /bin/bash — /bin/sh is dash here and eats bashisms.",
    )
    ap.add_argument("--log-dir", default=None, help="Where to write capture files.")
    ap.add_argument("--json", action="store_true", help="Emit a JSON report instead.")
    return ap.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    stages: list[tuple[str, str]] = [(lab, cmd) for lab, cmd in args.stage]
    stages += [(_label_for(c), c) for c in args.commands]
    if not stages:
        print("run_gate: no stages given", file=sys.stderr)
        return 2

    result = run_gate(
        stages,
        keep_going=args.keep_going,
        cwd=args.cwd,
        timeout=args.timeout,
        shell_path="/bin/bash" if args.bash else None,
        log_dir=args.log_dir,
        env=os.environ.copy(),
    )
    print(
        _as_json(result)
        if args.json
        else format_gate(result, tail=args.tail, full=args.full)
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
