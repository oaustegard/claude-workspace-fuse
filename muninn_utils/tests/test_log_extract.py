"""Tests for muninn_utils.log_extract.

The invariant that matters most is at the bottom: every line the extractor
emits that is not an elision marker appears verbatim in the input. An extractor
that paraphrases has become a summarizer, which is the thing this exists to
avoid.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from muninn_utils.log_extract import extract, find_anchors

MARKER = "\u2026"


def maven_shaped(noise_before=120, noise_after=200):
    """Error in the middle, transaction epilogue after — the shape tail gets wrong."""
    lines = [f"[INFO] Downloading from central: artifact-{i}-1.0.jar" for i in range(noise_before)]
    lines += [
        "[INFO] Compiling 214 source files to /build/target/classes",
        "[ERROR] /build/src/main/java/com/acme/Widget.java:[88,23] cannot find symbol",
        "[ERROR]   symbol:   method resolveTimeout(int)",
        "[INFO] 1 error",
    ]
    lines += [f"[INFO] acme-module-{i} ............................ SKIPPED" for i in range(noise_after)]
    lines += ["[INFO] BUILD FAILURE", "[INFO] Total time:  01:42 min"]
    return "\n".join(lines)


def test_error_before_a_long_epilogue_survives():
    raw = maven_shaped()
    ex = extract(raw)
    assert "cannot find symbol" in ex.text
    assert "resolveTimeout" in ex.text
    assert "BUILD FAILURE" in ex.text
    assert ex.kept_lines < 30
    assert ex.total_lines > 300


def test_tail_would_have_missed_it():
    """The known-bad for the naive alternative, kept as a live check."""
    raw = maven_shaped()
    naive_tail = "\n".join(raw.splitlines()[-50:])
    assert "cannot find symbol" not in naive_tail
    assert "cannot find symbol" in extract(raw).text


def test_elision_ranges_point_at_the_real_lines():
    raw = maven_shaped()
    lines = raw.splitlines()
    ex = extract(raw)
    ranges = [
        ln for ln in ex.text.splitlines() if "lines elided (lines" in ln
    ]
    assert ranges
    first = ranges[0]
    span = first.split("(lines ")[1].rstrip(")")
    start, end = (int(x) for x in span.split("-"))
    dropped = lines[start - 1 : end]
    assert all("Downloading" in d for d in dropped)


def test_no_anchor_degrades_to_tail_and_says_so():
    raw = "\n".join(f"just chatter {i}" for i in range(200))
    ex = extract(raw)
    assert ex.anchors == 0
    assert any("no error signature" in n for n in ex.notes)
    assert "just chatter 199" in ex.text
    assert "just chatter 10" not in ex.text


def test_dependency_frames_collapse_but_the_location_survives():
    frames = [
            "Traceback (most recent call last):",
            '  File "/app/main.py", line 12, in run',
            '  File "/usr/lib/python3.12/site-packages/click/core.py", line 1157, in __call__',
            '  File "/usr/lib/python3.12/site-packages/click/core.py", line 1078, in main',
            '  File "/usr/lib/python3.12/site-packages/click/core.py", line 1434, in invoke',
            "ValueError: timeout must be positive",
            "/usr/lib/python3.12/json/decoder.py:353: JSONDecodeError",
    ]
    ex = extract("\n".join(frames))
    assert "ValueError: timeout must be positive" in ex.text
    assert "/app/main.py" in ex.text
    assert "3 dependency frames elided" in ex.text
    assert "core.py" not in ex.text
    # A path that names where the failure landed is not a frame.
    assert "decoder.py:353" in ex.text


def test_identical_repeats_collapse():
    raw = "\n".join(["ERROR: connection refused"] * 40 + ["done"])
    ex = extract(raw)
    assert "39 identical lines elided" in ex.text
    assert ex.kept_lines < 6


def test_ansi_and_carriage_returns_are_normalised():
    raw = "\x1b[31mERROR: boom\x1b[0m\nProgress: 10%\rProgress: 90%\rProgress: 100%"
    ex = extract(raw)
    assert "ERROR: boom" in ex.text
    assert "\x1b[" not in ex.text
    assert "Progress: 10%" not in ex.text


def test_section_header_is_pulled_down_to_its_traceback():
    body = ["_____________ test_widget _____________"]
    body += [f'        """docstring line {i}"""' for i in range(30)]
    body += [">       assert resolve(0) == 1", "E       AssertionError: 0 != 1"]
    ex = extract("\n".join(body))
    assert "test_widget" in ex.text
    assert "AssertionError: 0 != 1" in ex.text
    assert "docstring line 15" not in ex.text


def test_budget_is_respected_with_many_anchors():
    raw = "\n".join(f"ERROR: failure number {i}" for i in range(400))
    ex = extract(raw, max_lines=60)
    assert ex.kept_lines <= 80
    assert ex.truncated
    assert any("budget" in n for n in ex.notes)


def test_empty_input():
    ex = extract("")
    assert ex.text == "" and ex.total_lines == 0


def test_find_anchors_ignores_ordinary_lines():
    lines = ["building", "linking", "ERROR: undefined reference", "done"]
    assert find_anchors(lines) == [2]


@pytest.mark.parametrize(
    "raw",
    [
        maven_shaped(),
        "\n".join(["Traceback (most recent call last):", "ValueError: nope"] + ["noise"] * 50),
        "\n".join([f"test_{i} PASSED" for i in range(300)] + ["FAILED test_x - AssertionError"]),
    ],
)
def test_every_kept_line_is_verbatim(raw):
    """No paraphrase. Anything not a marker must appear in the input as-is."""
    source = set(raw.splitlines())
    for line in extract(raw).text.splitlines():
        if MARKER in line or line.strip().startswith("["):
            continue
        assert line in source, line


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
