"""remember(), supersede() and remember_batch() warn when the text shows a shell ate its `$`.

Bash expands `$7` to nothing inside double quotes and unquoted heredocs, so
"$7.2B" reaches Python as ".2B" and "$400B/yr" as "00B/yr" (22 memories in the
store, found 2026-10-11). The original is lost before the write, so the check
can only warn. Turso is mocked; nothing is written.

    python3 -m pytest remembering/tests/test_shell_damage.py
"""

import os
import sys
import warnings
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.memory import ShellDamageWarning, _warn_shell_damage

DAMAGED = [
    ("512 x ~5k = ~8M hardware = 0.25% of the .2B budget", [".2B"]),
    ("grid investment needs +50% by 2030 from 00B/yr", ["00B"]),
    ("NATO pledged €70B (~0B) for Ukraine", ["(~0B)"]),
    ("tariffs cost avg ,500/household in 2026", [",500"]),
    ("from 2024's 03.5B", ["03.5B"]),
]

CLEAN = [
    "raised $1.5B at a $61B valuation",
    "0.25% of the budget; 0.5M users",
    "€3.8M seed round, 1,500 users, 12,000 stars",
    "version 1.2.0 shipped; ratio 0.72",
    "costs 5 $ each, 0 bugs",
    "the 0B file was empty",  # a single 0 with no digit after it is not the signature
]


def test_damaged_text_warns_with_spans():
    for text, want in DAMAGED:
        with warnings.catch_warnings(record=True) as w:
            spans = _warn_shell_damage(text)
        assert spans == want, (text, spans)
        assert any(issubclass(x.category, ShellDamageWarning) for x in w), text


def test_clean_text_is_silent():
    for text in CLEAN:
        with warnings.catch_warnings(record=True) as w:
            assert _warn_shell_damage(text) == [], text
        assert not w, text


class _Called(Exception):
    pass


def test_remember_checks_before_writing():
    """remember() runs the check before any database work."""
    import pytest
    from scripts.memory import remember
    with patch("scripts.memory._warn_shell_damage", side_effect=_Called), \
         patch("scripts.memory._exec", side_effect=AssertionError("wrote before checking")), \
         pytest.raises(_Called):
        remember("Budget: .2B for AI", "world")


def test_supersede_checks_before_resolving():
    import pytest
    from scripts.memory import supersede
    with patch("scripts.memory._warn_shell_damage", side_effect=_Called), \
         patch("scripts.memory._resolve_memory_id", side_effect=AssertionError("resolved before checking")), \
         pytest.raises(_Called):
        supersede("abc", "spent 00B since 2006", "world")
