"""
Tests for _format_relative_age (issue #19).

Pure unit tests: no network, no Turso. Pass a fixed `now` and an ISO
timestamp string, assert the rendered bucket.

Run from repo root:
    python3 remembering/tests/test_relative_age.py
"""

import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

sys.path.insert(0, 'remembering')

from scripts.result import _format_relative_age, _LOCAL_TZ


def _utc(year, month, day, hour=12, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


def _iso(dt):
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')


def assert_eq(actual, expected, label):
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def test_invalid_inputs():
    assert _format_relative_age(None) is None
    assert _format_relative_age('') is None
    assert _format_relative_age('not-a-timestamp') is None
    assert _format_relative_age(12345) is None
    print("PASS: invalid inputs return None")


def test_future_and_just_now():
    now = _utc(2026, 5, 13, 12, 0)
    # Future
    assert_eq(_format_relative_age(_iso(_utc(2026, 5, 13, 12, 30)), now=now),
              "in the future", "future")
    # Sub-minute
    assert_eq(_format_relative_age(_iso(_utc(2026, 5, 13, 11, 59, ) + timedelta(seconds=30)) if False else _iso(now - timedelta(seconds=30)), now=now),
              "just now", "30s ago")
    print("PASS: future and just-now")


def test_minutes_and_hours():
    now = _utc(2026, 5, 13, 12, 0)
    assert_eq(_format_relative_age(_iso(now - timedelta(minutes=1)), now=now),
              "1 minute ago", "1m")
    assert_eq(_format_relative_age(_iso(now - timedelta(minutes=45)), now=now),
              "45 minutes ago", "45m")
    # Same local calendar day, >= 1h. now in EDT (UTC-4) at 12:00 UTC = 08:00 local.
    # 5h earlier UTC = 07:00 UTC = 03:00 local (still same day).
    assert_eq(_format_relative_age(_iso(now - timedelta(hours=5)), now=now),
              "5 hours ago", "5h same day")
    print("PASS: minutes and hours")


def test_yesterday_and_days():
    # Use a now well into the local day so "yesterday" is unambiguous
    now = datetime(2026, 5, 13, 20, 0, tzinfo=ZoneInfo('America/New_York')).astimezone(timezone.utc)
    yesterday_local = datetime(2026, 5, 12, 14, 0, tzinfo=ZoneInfo('America/New_York'))
    assert_eq(_format_relative_age(yesterday_local.astimezone(timezone.utc).isoformat(), now=now),
              "yesterday", "yesterday")

    three_days = datetime(2026, 5, 10, 12, 0, tzinfo=ZoneInfo('America/New_York'))
    assert_eq(_format_relative_age(three_days.astimezone(timezone.utc).isoformat(), now=now),
              "3 days ago", "3 days")
    print("PASS: yesterday and days")


def test_weeks_and_months():
    now = datetime(2026, 5, 13, 20, 0, tzinfo=ZoneInfo('America/New_York')).astimezone(timezone.utc)

    last_week = now - timedelta(days=10)
    assert_eq(_format_relative_age(last_week.isoformat(), now=now),
              "last week", "10 days = last week")

    three_weeks = now - timedelta(days=21)
    assert_eq(_format_relative_age(three_weeks.isoformat(), now=now),
              "3 weeks ago", "21 days")

    last_month = now - timedelta(days=40)
    assert_eq(_format_relative_age(last_month.isoformat(), now=now),
              "last month", "40 days")

    three_months = now - timedelta(days=90)
    assert_eq(_format_relative_age(three_months.isoformat(), now=now),
              "3 months ago", "90 days")
    print("PASS: weeks and months")


def test_years():
    now = datetime(2026, 5, 13, 20, 0, tzinfo=ZoneInfo('America/New_York')).astimezone(timezone.utc)

    about_year = now - timedelta(days=400)
    assert_eq(_format_relative_age(about_year.isoformat(), now=now),
              "about a year ago", "400 days")

    two_years = now - timedelta(days=365 * 2 + 30)
    assert_eq(_format_relative_age(two_years.isoformat(), now=now),
              "2 years ago", "~2y")
    print("PASS: years")


def test_z_suffix_and_offset_formats():
    now = _utc(2026, 5, 13, 12, 0)
    # 'Z' suffix
    assert_eq(_format_relative_age('2026-05-13T11:30:00Z', now=now),
              "30 minutes ago", "Z suffix")
    # +00:00 offset
    assert_eq(_format_relative_age('2026-05-13T11:30:00+00:00', now=now),
              "30 minutes ago", "+00:00 offset")
    # Non-UTC offset
    assert_eq(_format_relative_age('2026-05-13T07:30:00-04:00', now=now),
              "30 minutes ago", "non-UTC offset (= 11:30 UTC)")
    print("PASS: timestamp format variants")


def test_naive_timestamp_assumed_utc():
    now = _utc(2026, 5, 13, 12, 0)
    assert_eq(_format_relative_age('2026-05-13T11:30:00', now=now),
              "30 minutes ago", "naive treated as UTC")
    print("PASS: naive timestamps assumed UTC")


def test_normalize_memory_adds_relative_age():
    from scripts.result import _normalize_memory
    data = {
        'id': 'abc123',
        'summary': 'test',
        'type': 'world',
        'created_at': '2026-05-13T11:30:00Z',
    }
    out = _normalize_memory(data)
    assert 'relative_age' in out, "_normalize_memory should add relative_age"
    assert isinstance(out['relative_age'], str), "relative_age should be a string"
    print(f"PASS: _normalize_memory adds relative_age (sample: {out['relative_age']!r})")


def test_normalize_memory_no_created_at():
    from scripts.result import _normalize_memory
    data = {'id': 'abc', 'summary': 'test', 'type': 'world'}
    out = _normalize_memory(data)
    assert out.get('relative_age') is None or 'relative_age' not in out
    print("PASS: _normalize_memory handles missing created_at")


def test_memory_result_exposes_relative_age():
    from scripts.result import MemoryResult, VALID_FIELDS
    assert 'relative_age' in VALID_FIELDS, "VALID_FIELDS must include relative_age"
    m = MemoryResult({'id': 'x', 'summary': 't', 'type': 'world', 'relative_age': '3 days ago'})
    assert m.relative_age == '3 days ago'
    assert m['relative_age'] == '3 days ago'
    print("PASS: MemoryResult exposes relative_age via attr and item access")


if __name__ == '__main__':
    test_invalid_inputs()
    test_future_and_just_now()
    test_minutes_and_hours()
    test_yesterday_and_days()
    test_weeks_and_months()
    test_years()
    test_z_suffix_and_offset_formats()
    test_naive_timestamp_assumed_utc()
    test_normalize_memory_adds_relative_age()
    test_normalize_memory_no_created_at()
    test_memory_result_exposes_relative_age()
    print("\nAll relative_age tests passed.")
