"""correction_gate — a regression gate for boot-loaded self-corrections.

Sibling to ``skill_lint``. ``skill_lint`` is a forcing function against a class
of YAML-frontmatter bug; ``correction_gate`` is a forcing function against
*unvalidated self-corrections*. Therapy mines weaknesses (stage 1) and proposes
bounded edits — new desire-triggers, ops entries, voice-signature scans —
(stage 2), but nothing validated a correction before it became permanent
boot-loaded context. This is Weng's Self-Harness **stage 3**: held-in +
held-out regression, run before a correction merges into boot config.

Only the three *objectively measurable* slices are gated (issue #83); voice and
relevance stay hand-evolved:

  * **trigger-firing accuracy** — an input maps to the trigger(s) that should
    fire. Fully implemented here and pure (no Turso): it re-derives the config
    fallback match in ``remembering/scripts/hints.py`` (term ∩ trigger-set).
  * **recall precision** — a query maps to an expected memory-id set. The gate
    logic is evaluator-agnostic; pass a ``query -> {id}`` runner (live
    ``recall()`` in production, a stub in tests).
  * **reindex verification** — already has a verify path (``search_reindex``);
    wrap it as a boolean case.

The gate is two checks:

  1. **Held-in** — does the proposed correction catch the failure that
     motivated it? The motivating input must FAIL under the baseline config and
     PASS under the candidate. A "correction" that doesn't fix its own
     motivating case is not a correction.
  2. **Held-out** — replay N past inputs (seeded from **real transcripts**, per
     ``eval-realism`` — synthetic scenarios train for the inferred grader).
     Behaviour must be unchanged where no change was intended: for every
     held-out case the candidate's behaviour must still equal the recorded
     correct behaviour. A new trigger that fires on an unrelated past input
     (false-positive / trigger bloat) is a regression, and the gate rejects it.

Definition of done (issue #83): adding a trigger runs the gate; a
deliberately-regressing trigger is rejected; a genuine fix passes.

Wiring: ``remembering/scripts/config.py``'s ``set_rule`` (the drift-classified,
deliberate rule-change path — i.e. the therapy write path) calls
``gate_config_correction`` before committing a boot-loaded change. The
dependency is soft (lazy import, skip when absent), so ``remembering`` still
runs without ``muninn_utils`` present.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Callable, Iterable


# ── term extraction ──────────────────────────────────────────────────────────
# Mirrors the intent of hints.py's config-fallback trigger match: extract
# content terms from the input, intersect with the trigger set. Tokenisation is
# hyphen-aware so a hyphenated trigger/tag ("tree-sitter", "fuse-mount") matches
# as a whole token in addition to its split parts.

_STOP = {
    "the", "and", "but", "not", "you", "all", "can", "had", "her", "was",
    "one", "our", "out", "are", "has", "have", "been", "being", "some",
    "than", "then", "them", "this", "that", "these", "those", "what",
    "when", "where", "which", "while", "who", "whom", "why", "will",
    "with", "would", "could", "should", "each", "other", "into", "for",
    "from", "does", "did", "how", "get", "set", "use", "used", "about",
}


def extract_terms(text: str) -> set[str]:
    """Content terms from ``text``: hyphen-aware whole tokens plus their
    snake/camel/hyphen split parts, lowercased, ≥3 chars, minus stop words.
    Quoted phrases are kept whole (a trigger can be a multi-word phrase)."""
    if not text:
        return set()
    terms: set[str] = set()
    # Whole tokens, allowing internal hyphens/underscores: "tree-sitter", "fuse_mount".
    for tok in re.findall(r"[a-zA-Z][a-zA-Z0-9_\-]*", text):
        low = tok.lower()
        if len(low) >= 3 and low not in _STOP:
            terms.add(low)
        for part in re.split(r"[-_]|(?<=[a-z])(?=[A-Z])", tok):
            p = part.lower()
            if len(p) >= 3 and p not in _STOP:
                terms.add(p)
    for q in re.findall(r"[\"']([^\"']+)[\"']", text):
        if 3 <= len(q) <= 60:
            terms.add(q.lower())
    return terms


def fired_triggers(input_text: str, triggers: Iterable[str]) -> set[str]:
    """The trigger(s) that fire on ``input_text``: the intersection of the
    input's content terms with the (lowercased) trigger set. Pure — this is the
    measurable behaviour the gate protects."""
    trig = {t.lower() for t in triggers if t}
    return extract_terms(input_text) & trig


# ── cases ────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Case:
    """One benchmark case, seeded from a real transcript.

    ``expected`` is the recorded-correct behaviour:
      * trigger  → frozenset of trigger names that should fire on ``input``
      * recall   → frozenset of memory-ids the query should surface
      * reindex  → frozenset with the single expected chunk-id (or empty)

    For a **held-in** (motivating) case ``expected`` drives the pass check: the
    candidate must satisfy it, the baseline must not. For a **held-out** case
    the gate is differential (candidate behaviour vs baseline behaviour), so
    ``expected`` documents intent and is used only for a benchmark-staleness
    warning — set ``intended=True`` on the rare held-out case whose behaviour is
    *meant* to change, to suppress its differential regression.
    """
    name: str
    input: str
    expected: frozenset
    kind: str = "trigger"
    source: str = ""       # transcript / session id the case was mined from
    intended: bool = False  # held-out: this case is allowed to change

    @staticmethod
    def from_dict(d: dict) -> "Case":
        return Case(
            name=d["name"],
            input=d["input"],
            expected=frozenset(d.get("expected", [])),
            kind=d.get("kind", "trigger"),
            source=d.get("source", ""),
            intended=bool(d.get("intended", False)),
        )


def cases_from_json(items: Iterable[dict]) -> list[Case]:
    return [Case.from_dict(d) for d in items]


# ── result ───────────────────────────────────────────────────────────────────

@dataclass
class GateResult:
    passed: bool
    held_in_passed: bool
    held_in_reason: str
    regressions: list = field(default_factory=list)  # list[dict], hard failures
    stale: list = field(default_factory=list)        # list[dict], warnings only
    checked: int = 0
    summary: str = ""

    def __bool__(self) -> bool:  # `if gate:` reads as "did it pass"
        return self.passed


# ── the gate ─────────────────────────────────────────────────────────────────

def _default_satisfies(expected: frozenset, actual: set) -> bool:
    """Held-in is satisfied when every expected item is present in actual
    (subset). The correction may legitimately do more than the one thing that
    motivated it; it must at least do that."""
    return set(expected).issubset(set(actual))


def run_gate(
    *,
    held_in: Case | None,
    held_out: Iterable[Case],
    before: Callable[[Case], set],
    after: Callable[[Case], set],
    satisfies: Callable[[frozenset, set], bool] = _default_satisfies,
) -> GateResult:
    """Evaluator-agnostic core.

    ``before``/``after`` map a Case to the behaviour (a set) under the baseline
    and candidate configs respectively.

    * **Held-in**: the motivating case must FAIL ``satisfies`` under the
      baseline and PASS it under the candidate.
    * **Held-out**: differential — the candidate's behaviour must equal the
      baseline's for every case not flagged ``intended``. Any change is a
      regression (a new trigger firing on an unrelated past input, or an
      established trigger no longer firing). Differential rather than absolute
      so the check is self-consistent against whatever the live config is.

    When a held-out case carries an ``expected`` set that the baseline does not
    reproduce, that's benchmark drift — recorded as a ``stale`` warning, never a
    hard failure.
    """
    held_in_passed = True
    held_in_reason = "no motivating case supplied"
    if held_in is not None:
        base_ok = satisfies(held_in.expected, before(held_in))
        cand_ok = satisfies(held_in.expected, after(held_in))
        if base_ok:
            held_in_passed = False
            held_in_reason = (
                f"motivating case '{held_in.name}' already passes under the "
                f"baseline — this correction fixes nothing"
            )
        elif not cand_ok:
            held_in_passed = False
            held_in_reason = (
                f"motivating case '{held_in.name}' still fails under the "
                f"candidate — correction does not catch its own failure"
            )
        else:
            held_in_reason = f"motivating case '{held_in.name}' now passes"

    regressions: list[dict] = []
    stale: list[dict] = []
    checked = 0
    for case in held_out:
        checked += 1
        base = set(before(case))
        cand = set(after(case))
        if case.expected and base != set(case.expected):
            stale.append({
                "case": case.name,
                "recorded": sorted(case.expected),
                "baseline": sorted(base),
            })
        if case.intended:
            continue
        if cand != base:
            regressions.append({
                "case": case.name,
                "kind": case.kind,
                "source": case.source,
                "baseline": sorted(base),
                "candidate": sorted(cand),
                "added": sorted(cand - base),
                "removed": sorted(base - cand),
            })

    passed = held_in_passed and not regressions
    if passed:
        summary = (
            f"PASS — {held_in_reason}; {checked} held-out case(s) unchanged"
        )
        if stale:
            summary += f" ({len(stale)} stale-benchmark warning(s))"
    else:
        bits = []
        if not held_in_passed:
            bits.append(f"held-in FAILED ({held_in_reason})")
        if regressions:
            names = ", ".join(r["case"] for r in regressions[:5])
            more = "" if len(regressions) <= 5 else f" (+{len(regressions) - 5} more)"
            bits.append(f"{len(regressions)} held-out regression(s): {names}{more}")
        summary = "REJECT — " + "; ".join(bits)

    return GateResult(
        passed=passed,
        held_in_passed=held_in_passed,
        held_in_reason=held_in_reason,
        regressions=regressions,
        stale=stale,
        checked=checked,
        summary=summary,
    )


# ── slice adapters ───────────────────────────────────────────────────────────

def gate_trigger_correction(
    *,
    before_triggers: Iterable[str],
    after_triggers: Iterable[str],
    held_in: Case | None,
    held_out: Iterable[Case],
) -> GateResult:
    """Gate a change to the trigger set (e.g. ``recall-triggers``). Pure."""
    before_set = list(before_triggers)
    after_set = list(after_triggers)
    return run_gate(
        held_in=held_in,
        held_out=held_out,
        before=lambda c: fired_triggers(c.input, before_set),
        after=lambda c: fired_triggers(c.input, after_set),
    )


def gate_recall_correction(
    *,
    before_recall: Callable[[str], Iterable[str]],
    after_recall: Callable[[str], Iterable[str]],
    held_in: Case | None,
    held_out: Iterable[Case],
) -> GateResult:
    """Gate a recall-precision correction. ``before_recall``/``after_recall``
    are ``query -> ids`` runners (live ``recall()`` in production, stubs in
    tests). The gate never touches Turso itself."""
    return run_gate(
        held_in=held_in,
        held_out=held_out,
        before=lambda c: set(before_recall(c.input)),
        after=lambda c: set(after_recall(c.input)),
    )


# ── boot-budget guard (trigger-bloat / context-crowding regression) ──────────

def check_budget(before_chars: int, after_chars: int, *,
                 max_chars: int, max_growth: int | None = None) -> str | None:
    """Guard against a correction bloating boot-loaded context. Returns a
    human-readable reason if the candidate exceeds ``max_chars`` total, or grows
    by more than ``max_growth`` chars; otherwise ``None`` (within budget)."""
    if after_chars > max_chars:
        return (f"boot config would be {after_chars} chars, over the "
                f"{max_chars}-char budget")
    if max_growth is not None and (after_chars - before_chars) > max_growth:
        return (f"boot config would grow by {after_chars - before_chars} chars, "
                f"over the {max_growth}-char per-change cap")
    return None


# ── benchmark loading ────────────────────────────────────────────────────────

_DEFAULT_BENCHMARK = os.path.join(
    os.path.dirname(__file__), "correction_gate_benchmark.json"
)


def load_benchmark(path: str | None = None) -> dict:
    """Load the seed benchmark. Shape: ``{"trigger": [case,...], "recall":
    [...], "reindex": [...]}``. Missing file → empty benchmark (gate skips)."""
    path = path or _DEFAULT_BENCHMARK
    if not os.path.exists(path):
        return {"trigger": [], "recall": [], "reindex": []}
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    return {slice_: cases_from_json(raw.get(slice_, []))
            for slice_ in ("trigger", "recall", "reindex")}


# ── therapy write-path entry point ───────────────────────────────────────────

def gate_config_correction(
    key: str,
    category: str,
    before_value: str | None,
    after_value: str,
    *,
    motivating: Case | None = None,
    benchmark: dict | None = None,
    max_boot_chars: int = 120_000,
) -> GateResult | None:
    """Entry point invoked from ``set_rule``. Returns ``None`` when there is
    nothing objectively gateable (no benchmark, non-measurable slice) so the
    caller proceeds; returns a ``GateResult`` for a measurable correction so the
    caller can block on ``.passed``.

    Trigger corrections (``recall-triggers``) run the full trigger gate against
    the benchmark's held-out trigger cases. Other boot-loaded corrections get a
    budget guard against trigger-bloat.
    """
    bench = benchmark if benchmark is not None else load_benchmark()

    if key == "recall-triggers":
        before_triggers = _parse_trigger_list(before_value)
        after_triggers = _parse_trigger_list(after_value)
        held_out = bench.get("trigger", [])
        if motivating is None and not held_out:
            return None  # nothing to measure against
        return gate_trigger_correction(
            before_triggers=before_triggers,
            after_triggers=after_triggers,
            held_in=motivating,
            held_out=held_out,
        )

    # Non-trigger boot-loaded rule (ops/profile prose): budget guard only.
    reason = check_budget(
        len(before_value or ""), len(after_value), max_chars=max_boot_chars
    )
    if reason is None:
        return None
    return GateResult(
        passed=False,
        held_in_passed=True,
        held_in_reason="n/a (budget guard)",
        regressions=[{"case": "boot-budget", "kind": "budget", "reason": reason}],
        summary=f"REJECT — {reason}",
    )


def _parse_trigger_list(value: str | None) -> list[str]:
    """Triggers are stored as a JSON list in ``recall-triggers``. Tolerate a
    plain comma/space-separated string too."""
    if not value:
        return []
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(t) for t in parsed]
    except (json.JSONDecodeError, TypeError):
        pass
    return [t.strip() for t in re.split(r"[,\s]+", value) if t.strip()]


# ── demo ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # A genuine fix vs a deliberately-regressing trigger, over the seed bench.
    bench = load_benchmark()
    held_out = bench.get("trigger", [])
    # A plausible current trigger set (in production this is the live
    # `recall-triggers` config value).
    base = ["fuse", "memfs", "boot-recovery", "turso", "whtwnd", "reindex"]

    # Real diagnosed miss: a tree-sitter grammar was written without checking
    # the mount, which would have surfaced tree-sitter memories (CLAUDE.md,
    # session 854f6b7c). The correction adds a `tree-sitter` trigger.
    motivating = Case(
        name="tree-sitter-miss (session 854f6b7c)",
        input="writing a tree-sitter grammar, does the scanner.cc link?",
        expected=frozenset({"tree-sitter"}),
        source="854f6b7c",
    )

    good = gate_trigger_correction(
        before_triggers=base,
        after_triggers=base + ["tree-sitter"],
        held_in=motivating,
        held_out=held_out,
    )
    print("genuine fix    :", good.summary)

    bad = gate_trigger_correction(
        before_triggers=base,
        after_triggers=base + ["files"],  # fires on the fuse-mount held-out input
        held_in=Case("bloat", "reading the markdown files", frozenset({"files"})),
        held_out=held_out,
    )
    print("regressing add :", bad.summary)
