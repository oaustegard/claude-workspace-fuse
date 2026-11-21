"""
memory_histogram() must age rows whose created_at carries no offset.

Pure unit test: _exec is patched, no Turso. Before the fix a single naive
created_at raised TypeError (naive vs aware datetime) and the Perch Sleep
step lost its histogram every run.

Run from repo root:
    python3 remembering/tests/test_histogram_tz.py
"""

import sys
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

sys.path.insert(0, 'remembering')

from scripts import memory


def test_mixed_naive_and_aware_created_at():
    now = datetime.now(UTC)
    rows = [
        # naive, SQLite datetime('now') form
        {"type": "world", "priority": 0,
         "created_at": (now - timedelta(days=2)).strftime('%Y-%m-%d %H:%M:%S')},
        # aware, Z suffix
        {"type": "decision", "priority": 1,
         "created_at": (now - timedelta(days=20)).strftime('%Y-%m-%dT%H:%M:%SZ')},
        # aware, explicit offset
        {"type": "analysis", "priority": 0,
         "created_at": (now - timedelta(days=200)).isoformat()},
    ]
    with patch.object(memory, "_exec", return_value=rows):
        hist = memory.memory_histogram()
    assert hist["total"] == 3
    assert hist["by_age_days"] == {"0-7d": 1, "8-30d": 1, "31-90d": 0, "90d+": 1}


if __name__ == "__main__":
    test_mixed_naive_and_aware_created_at()
    print("PASS: memory_histogram handles naive and aware created_at")
