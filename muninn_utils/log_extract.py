"""Select the failure region out of command output, keeping every kept line verbatim.

The naive choices are truncate (head/tail) and summarize (hand it to a model).
Both are wrong for build and test output, in different ways.

Head and tail select by POSITION, and position does not predict where the error
is. Maven, Gradle, npm and most CI runners print the failure and then several
hundred lines of transaction epilogue — reactor summaries, dependency
resolution, timing tables. `tail -50` on that returns the epilogue and drops the
assertion.

Model summarization selects by MEANING, and paraphrase destroys the identifiers
that make a failure actionable. The gh-proxy diagnosis in this system turned on
two 403 bodies that differ only in wording; "GitHub returned 403" loses the
session. Gemini-as-extractor flattened three distinct blockers into one story
and misattributed the fix.

This selects by SIGNAL and keeps what it selects byte-for-byte. Lines matching
an error signature anchor a window; the windows are merged and rendered in
order; everything dropped is replaced by a count and a line range, so the log
file is addressable at the exact offset:

    … 412 lines elided (lines 88-499)

Every elision is recoverable. Nothing is rewritten.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

#: Lines that mark a real failure. Ordered most-specific first only for
#: readability; matching is a simple any().
ANCHOR_PATTERNS = [
    r"Traceback \(most recent call last\)",
    r"^E\s{3}",                      # pytest assertion detail
    r"^(FAILED|ERROR)\b",            # pytest short summary
    r"^\s*(FAIL|ERROR)\b",
    r"^---\s*FAIL:",                 # go test
    r"^\s*--- FAIL",
    r"\bpanic:",
    r"^\s*\S*Error\b.*:",            # TypeError: / AssertionError: / error:
    r"^\s*error(\[[A-Z]?\d+\])?:",   # rustc / tsc / ruff
    r"^npm ERR!",
    r"^\[ERROR\]",
    r"^\s*\u2717",                   # our own fail mark
    r"^\s*(Expected|Received|Actual)\b",
    r"^\s*assert\b",
    r"BUILD FAILURE",
    r"^Error:",
    r"^\s*at .*\((?!.*(node_modules|site-packages))",  # first-party frame
]

#: Lines that carry no diagnostic weight even inside a kept window.
NOISE_PATTERNS = [
    r"^[.sxXFEP]+\s*(\[\s*\d+%\])?$",       # pytest/jest progress dots
    r"^\s*\[INFO\] Download(ing|ed)",
    r"^Download(ing|ed)\b",
    r"^\s*Progress \(\d",
    r"^\s*\d+%\s",
    r"^\s*Resolving deps",
    r"^\s*\[INFO\] -{10,}",
    r"^\s*-{20,}$",
    r"^\s*={20,}$",
    # Reactor / summary tables: "module ....... SKIPPED". SUCCESS and SKIPPED
    # only — a FAILED row in the same table is the thing being looked for.
    r"\.{8,}\s*(SKIPPED|SUCCESS|PASSED|UP-TO-DATE)\s*$",
]

#: Section boundaries. A kept window snaps back to one of these so a traceback
#: arrives with the test name attached rather than starting mid-frame.
SECTION_PATTERNS = [
    r"^_{5,}.*_{5,}$",
    r"^={3,}.+={3,}$",
    r"^-{3,}.+-{3,}$",
    r"^\s*\d+\) ",
]

#: Stack frames from dependencies. Collapsed with a count, never silently cut.
VENDOR_FRAME = re.compile(
    r"(site-packages|dist-packages|node_modules|/usr/lib/python|<frozen |\.cargo/registry)"
)

#: A path alone is not a frame. `decoder.py:353: JSONDecodeError` names where the
#: failure happened and must survive; `at Object.<anonymous> (node_modules/...)`
#: is a frame and can be counted instead of shown.
FRAME_SHAPE = re.compile(r'^\s*(at |File ")')

_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


@dataclass
class Extract:
    text: str
    total_lines: int
    kept_lines: int
    anchors: int
    truncated: bool = False
    notes: list[str] = field(default_factory=list)

    @property
    def ratio(self) -> float:
        return self.kept_lines / self.total_lines if self.total_lines else 1.0


def _clean(raw: str) -> list[str]:
    """Strip ANSI and collapse carriage-return progress rewrites."""
    lines = []
    # split("\n"), not splitlines() — the latter also splits on \r, which turns
    # one progress line that rewrote itself 400 times into 400 lines.
    for line in raw.split("\n"):
        line = _ANSI.sub("", line)
        if "\r" in line:
            line = line.split("\r")[-1]
        lines.append(line.rstrip())
    return lines


def _compile(patterns) -> list[re.Pattern]:
    return [re.compile(p) for p in patterns]


def find_anchors(lines: list[str], patterns=None) -> list[int]:
    pats = _compile(patterns or ANCHOR_PATTERNS)
    return [i for i, ln in enumerate(lines) if any(p.search(ln) for p in pats)]


def _snap_back(lines: list[str], start: int, limit: int = 60) -> int | None:
    """Index of the nearest section header above `start`, if there is one.

    Returned as its own one-line window rather than by widening the region, so
    a traceback arrives with its test name attached and the docstring between
    them stays elided.
    """
    pats = _compile(SECTION_PATTERNS)
    for i in range(start, max(-1, start - limit) - 1, -1):
        if any(p.search(lines[i]) for p in pats):
            return i
    return None


def _merge(windows: list[tuple[int, int]]) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for start, end in sorted(windows):
        if out and start <= out[-1][1] + 1:
            out[-1] = (out[-1][0], max(out[-1][1], end))
        else:
            out.append((start, end))
    return out


def _collapse_vendor(block: list[str], line_no: int) -> list[str]:
    out: list[str] = []
    run = 0
    for ln in block:
        if VENDOR_FRAME.search(ln) and FRAME_SHAPE.search(ln):
            run += 1
            continue
        if run:
            out.append(f"    \u2026 {run} dependency frame{'s' if run > 1 else ''} elided")
            run = 0
        out.append(ln)
    if run:
        out.append(f"    \u2026 {run} dependency frame{'s' if run > 1 else ''} elided")
    return out


def _collapse_repeats(block: list[str], threshold: int = 4) -> list[str]:
    out: list[str] = []
    i = 0
    while i < len(block):
        j = i
        while j + 1 < len(block) and block[j + 1] == block[i]:
            j += 1
        run = j - i + 1
        out.append(block[i])
        if run >= threshold:
            out.append(f"    \u2026 {run - 1} identical lines elided")
        elif run > 1:
            out.extend(block[i + 1 : j + 1])
        i = j + 1
    return out


def extract(
    raw: str,
    *,
    before: int = 3,
    after: int = 12,
    tail: int = 6,
    max_lines: int = 140,
    strip_vendor: bool = True,
    drop_noise: bool = True,
) -> Extract:
    """Keep the anchored failure regions plus the final lines; elide the rest.

    `tail` lines are always kept because the exit summary usually lives there
    even when the diagnosis does not. With no anchor found, the result degrades
    to a tail — that case is reported in `notes` so it is not mistaken for a
    successful extraction.
    """
    lines = _clean(raw)
    while lines and not lines[-1]:
        lines.pop()
    n = len(lines)
    if n == 0:
        return Extract("", 0, 0, 0)

    noise = _compile(NOISE_PATTERNS) if drop_noise else []
    anchors = [
        i for i in find_anchors(lines) if not any(p.search(lines[i]) for p in noise)
    ]

    notes: list[str] = []
    windows: list[tuple[int, int]] = []
    for i in anchors:
        start = max(0, i - before)
        header = _snap_back(lines, start)
        if header is not None and header < start:
            windows.append((header, header))
        windows.append((start, min(n - 1, i + after)))
    if not anchors:
        notes.append("no error signature matched — showing the tail only")
    if tail:
        windows.append((max(0, n - tail), n - 1))
    merged = _merge(windows)

    # Budget: keep the first and last anchored regions when over budget, since
    # the first failure and the exit summary are the two that get read.
    total = sum(e - s + 1 for s, e in merged)
    truncated = False
    while total > max_lines and len(merged) > 2:
        drop = merged.pop(len(merged) // 2)
        total -= drop[1] - drop[0] + 1
        truncated = True
    if total > max_lines and merged:
        first = merged[0]
        merged[0] = (first[0], min(first[1], first[0] + max_lines - tail - 1))
        truncated = True

    out: list[str] = []
    cursor = 0
    kept = 0
    for start, end in merged:
        if start > cursor:
            gap = start - cursor
            out.append(f"    \u2026 {gap} lines elided (lines {cursor + 1}-{start})")
        block = lines[start : end + 1]
        if drop_noise:
            filtered = [ln for ln in block if not any(p.search(ln) for p in noise)]
            dropped = len(block) - len(filtered)
            block = filtered
            if dropped:
                block.append(f"    \u2026 {dropped} progress/summary lines filtered")
        if strip_vendor:
            block = _collapse_vendor(block, start)
        block = _collapse_repeats(block)
        out.extend(block)
        kept += len(block)
        cursor = end + 1
    if cursor < n:
        gap = n - cursor
        out.append(f"    \u2026 {gap} lines elided (lines {cursor + 1}-{n})")

    if truncated:
        notes.append(f"over the {max_lines}-line budget — middle regions dropped")

    return Extract(
        text="\n".join(out),
        total_lines=n,
        kept_lines=kept,
        anchors=len(anchors),
        truncated=truncated,
        notes=notes,
    )
