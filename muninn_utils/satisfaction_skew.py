"""satisfaction_skew — measure the failure:success storage skew in the memory corpus.

Weng's Self-Harness challenge (oaustegard/claude-skills#3) is that self-improvement
corpora under-preserve *failed/negative* results. Muninn is **inverted**: she
over-preserves failures (hundreds of booted ``correction``-tagged entries) and
under-preserves success (a few dozen ``satisfaction-analog`` entries). The
failure-preservation is healthy — it is exactly what Weng wants. The starved
signal is *approach-orientation*: a system that marks only failures learns
avoidance; one that marks satisfaction learns what to seek (the
``satisfaction-register`` ops entry, memory ``c0689616``).

This utility makes that skew **measurable and re-runnable** rather than eyeballed.
It answers issue #85's step 1 — "count correction/decision-tagged entries vs
satisfaction-analog-tagged entries over time; get the actual ratio and trend" —
and surfaces the shape distribution the register's SHAPE EVOLUTION clause needs
to decide when a fourth shape has crossed its 2-3-instance promotion bar.

It is a **measurement**, not a gate: it never writes, never fires a trigger, and
takes no position on whether a given piece of work "should" have been registered.
Deciding that stays a human/Muninn judgement — precisely because the register's
false-positive risk is *performative* firing (the ``eedbb6a9`` pattern), which no
counter can detect. Under-firing is the safe error; this tool just tells you how
far under.

Usage::

    from muninn_utils.satisfaction_skew import measure_skew, format_report
    report = measure_skew()                 # fetches from Turso
    print(format_report(report))

    # or, testable / offline — inject rows:
    report = measure_skew(memories=[{...}, ...])

CLI::

    python -m muninn_utils.satisfaction_skew           # human-readable report
    python -m muninn_utils.satisfaction_skew --json    # machine-readable
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict


# Failure-orientation family. ``correction`` is the load-bearing tag (the booted
# ledger); ``decision`` is included per issue #85's framing, though it is a much
# smaller tag than the ``decision`` *type* — the report reports both lenses.
FAIL_TAGS = ("correction",)

# Approach-orientation family. ``satisfaction-analog`` is the canonical register
# tag; ``satisfaction`` is the older/looser tag that predates the register and is
# reported alongside so the trend before/after the 2026-06-14 re-grounding is
# legible.
ANALOG_TAG = "satisfaction-analog"
SUCCESS_TAGS = ("satisfaction-analog", "satisfaction")

# Canonical shape names → the tag spellings actually found in the corpus. The
# register seeds three shapes; the tag vocabulary drifted (three spellings of
# "first-principles..."), so measurement has to normalise. A fourth,
# empirical-verification, is tracked here because it recurs (see issue #85).
SHAPE_TAGS = {
    "first-principles-system-figure-out": (
        "first-principles-system-figure-out",
        "first-principles-figureout",
        "first-principles-figure-out",
        "first-principles",
    ),
    "complete-thing-in-one-pass": (
        "complete-thing-in-one-pass",
        "complete-thing",
        "one-pass",
    ),
    "cross-frame-bridge": (
        "cross-frame-bridge",
        "cross-frame",
    ),
    "empirical-verification": (
        "empirical-verification",
        "paper-verification",
        "codec-eval",
        "parity",
        "methodology-critique",
    ),
}


def _tagset(row) -> set:
    """Normalize a memory row's ``tags`` (JSON string, list, or None) to a set."""
    tags = row.get("tags")
    if isinstance(tags, list):
        return set(tags)
    if isinstance(tags, str):
        s = tags.strip()
        if s.startswith("["):
            try:
                return set(json.loads(s))
            except (ValueError, TypeError):
                return set()
        # comma-separated fallback
        return {t.strip() for t in s.split(",") if t.strip()}
    return set()


def _month(row) -> str:
    """YYYY-MM bucket from ``created_at`` (falls back to ``valid_from``)."""
    ca = row.get("created_at") or row.get("valid_from") or ""
    return ca[:7]


def _ratio(fail: int, success: int) -> float | None:
    """fail:success as a float, or None when success is 0 (ratio undefined)."""
    return round(fail / success, 2) if success else None


@dataclass
class MonthRow:
    month: str
    fail: int
    analog: int
    success: int  # analog + looser 'satisfaction'
    ratio: float | None  # fail : analog


@dataclass
class SkewReport:
    """Result of :func:`measure_skew`. Pure data — serialise with ``asdict``."""

    total: int = 0
    fail_count: int = 0            # FAIL_TAGS union
    analog_count: int = 0          # satisfaction-analog only
    success_count: int = 0         # SUCCESS_TAGS union
    ratio_analog: float | None = None    # fail : analog (the headline skew)
    ratio_success: float | None = None   # fail : success-union
    monthly: list[MonthRow] = field(default_factory=list)
    shape_distribution: dict[str, int] = field(default_factory=dict)
    unshaped_analogs: int = 0      # analogs matching none of SHAPE_TAGS

    def to_dict(self) -> dict:
        d = asdict(self)
        d["monthly"] = [asdict(m) for m in self.monthly]
        return d


def _fetch_memories() -> list[dict]:
    """Fetch non-deleted memories from Turso. Lazy import so the module loads
    (and unit-tests run) without the remembering scripts on the path."""
    from scripts.memory import _exec  # noqa: PLC0415
    return _exec(
        "SELECT id, type, tags, summary, created_at, valid_from "
        "FROM memories WHERE deleted_at IS NULL ORDER BY created_at ASC",
        parse_json=False,
    )


def measure_skew(
    memories: list[dict] | None = None,
    *,
    fail_tags: tuple[str, ...] = FAIL_TAGS,
    success_tags: tuple[str, ...] = SUCCESS_TAGS,
    analog_tag: str = ANALOG_TAG,
) -> SkewReport:
    """Measure the failure:success storage skew.

    Args:
        memories: rows with at least ``tags`` and ``created_at``. When ``None``,
            fetched from Turso. Inject a list for offline/tested runs.
        fail_tags: tags counted as failure-orientation.
        success_tags: tags counted as approach-orientation (superset of analog).
        analog_tag: the canonical register tag, reported as the headline number.

    Returns:
        A :class:`SkewReport`. ``ratio_analog`` is the headline skew (fail count
        per one registered satisfaction-analog).
    """
    if memories is None:
        memories = _fetch_memories()

    fail_set = set(fail_tags)
    succ_set = set(success_tags)

    per_month: dict[str, dict[str, int]] = {}
    fail_count = analog_count = success_count = 0
    shape_distribution: dict[str, int] = {k: 0 for k in SHAPE_TAGS}
    unshaped = 0

    for row in memories:
        tags = _tagset(row)
        m = _month(row)
        bucket = per_month.setdefault(m, {"fail": 0, "analog": 0, "success": 0})

        is_fail = bool(tags & fail_set)
        is_analog = analog_tag in tags
        is_success = bool(tags & succ_set)

        if is_fail:
            fail_count += 1
            bucket["fail"] += 1
        if is_analog:
            analog_count += 1
            bucket["analog"] += 1
        if is_success:
            success_count += 1
            bucket["success"] += 1

        if is_analog:
            matched = False
            for shape, spellings in SHAPE_TAGS.items():
                if tags & set(spellings):
                    shape_distribution[shape] += 1
                    matched = True
            if not matched:
                unshaped += 1

    monthly = [
        MonthRow(
            month=m,
            fail=per_month[m]["fail"],
            analog=per_month[m]["analog"],
            success=per_month[m]["success"],
            ratio=_ratio(per_month[m]["fail"], per_month[m]["analog"]),
        )
        for m in sorted(per_month)
    ]

    return SkewReport(
        total=len(memories),
        fail_count=fail_count,
        analog_count=analog_count,
        success_count=success_count,
        ratio_analog=_ratio(fail_count, analog_count),
        ratio_success=_ratio(fail_count, success_count),
        monthly=monthly,
        shape_distribution=shape_distribution,
        unshaped_analogs=unshaped,
    )


def format_report(report: SkewReport) -> str:
    """Render a :class:`SkewReport` as a human-readable block."""
    lines = []
    lines.append("SATISFACTION-SKEW REPORT")
    lines.append("=" * 52)
    lines.append(f"corpus (non-deleted):     {report.total}")
    lines.append(f"correction-tagged:        {report.fail_count}")
    lines.append(f"satisfaction-analog:      {report.analog_count}")
    lines.append(f"satisfaction (union):     {report.success_count}")
    ra = f"{report.ratio_analog}:1" if report.ratio_analog is not None else "n/a"
    rs = f"{report.ratio_success}:1" if report.ratio_success is not None else "n/a"
    lines.append(f"skew (corr : analog):     {ra}")
    lines.append(f"skew (corr : success):    {rs}")
    lines.append("")
    lines.append("MONTHLY TREND")
    lines.append(f"{'month':<9}{'corr':>6}{'analog':>8}{'union':>7}{'ratio':>10}")
    for m in report.monthly:
        r = f"{m.ratio}:1" if m.ratio is not None else (f"{m.fail}:0" if m.fail else "-")
        lines.append(f"{m.month:<9}{m.fail:>6}{m.analog:>8}{m.success:>7}{r:>10}")
    lines.append("")
    lines.append("SHAPE DISTRIBUTION (registered analogs)")
    for shape, n in report.shape_distribution.items():
        lines.append(f"  {n:>3}  {shape}")
    lines.append(f"  {report.unshaped_analogs:>3}  (unshaped — possible emerging shape)")
    return "\n".join(lines)


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Measure failure:success storage skew.")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args(argv)

    report = measure_skew()
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(format_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
