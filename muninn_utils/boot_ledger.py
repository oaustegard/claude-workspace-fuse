"""boot_ledger — instrument the boot payload: per-entry cost vs. fire rate.

Companion to ``correction_gate`` (issue #83). ``correction_gate`` guards a
*single* boot-loaded correction at write time; ``boot_ledger`` measures the
*whole* boot payload after the fact and ranks it, so the catalog can be pruned
instead of only grown. Issue #84: "Boot payload is unmanaged — instrument
per-trigger cost/fire-rate, add an ACE-style dedup/prune pass."

Two numbers per boot-loaded config entry:

  * **cost** — exact. Character length from the config table, plus a token
    estimate (tiktoken cl100k when available, else the standard ~4-chars/token
    heuristic). This is countable with zero ambiguity; it is what the entry
    spends on *every* boot whether or not it is ever used.

  * **fire rate** — a proxy. There is no historical log of ``config_get``
    calls (that is the gap this issue names), and the archived session
    transcripts are three stale sessions from one April day — not a usable
    corpus. The one longitudinal record that *does* exist is the memory corpus
    (~4.5k memories, Dec–Jul, in Turso). So "fire" is approximated as: how many
    active memories reference the entry's domain, and across how many distinct
    months. A trigger whose subject never shows up in seven months of logged
    work is a strong demotion candidate; an ops entry that surfaces every month
    is earning its boot cost. The proxy is labelled as a proxy everywhere it
    appears — it answers "did this entry's condition actually arise in logged
    work", which is the countable half of the issue's fire-rate question.

  * **logged_fires** — exact, but zero until instrumentation is switched on.
    ``remembering/scripts/config.py`` gains a ``config_fire`` counter and an
    opt-in hook in ``config_get`` (``MUNINN_INSTRUMENT_FIRES=1``) that
    increments ``fire_count``/``last_fired`` for boot-loaded keys only. Once a
    measurement window has run, the ledger surfaces the real counts alongside
    the proxy, and the proxy can be retired for those keys.

The core (term extraction, matching, ranking, rendering) is pure and unit
tested with in-memory fixtures. Turso only appears in the ``load_*`` adapters
and ``report()``.

Kinds (how an entry earns its keep decides how to read its fire column):

  * ``trigger``  — a dispatch line ("when X → config_get Y"). Fire rate is the
    whole point; zero fires → demote to reference-only.
  * ``ops``      — operational knowledge that is semi-passive. Low fire rate is
    a weaker signal (it may be load-bearing the one time it fires), but a large
    never-referenced ops entry is still a candidate.
  * ``identity`` — profile payload (identity/values/voice). Always-on by
    design; fire rate is informational, not a demotion lever.
  * ``catalog``  — the voice-signature scan list. "Fire" = a scan matches
    during prose writing; curation here is redundancy-collapse, not demotion.

Usage::

    from muninn_utils.boot_ledger import report
    print(report())                      # ranked markdown table + summary

    python -m muninn_utils.boot_ledger              # same, to stdout
    python -m muninn_utils.boot_ledger --json       # machine-readable

v0.1.0: Initial release (issue #84).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from typing import Callable, Iterable, Sequence


# ── cost ─────────────────────────────────────────────────────────────────────

def estimate_tokens(text: str) -> int:
    """Token count for ``text``. Uses tiktoken cl100k if importable (the
    encoding Claude/GPT-family tokenizers approximate closely enough for a
    budget estimate), else the ~4-chars/token heuristic. Cost is the one half
    of this tool that is exact modulo tokenizer choice; the heuristic is only a
    fallback so the tool runs on a bare container."""
    if not text:
        return 0
    try:  # pragma: no cover - depends on optional dep
        import tiktoken
        return len(tiktoken.get_encoding("cl100k_base").encode(text))
    except Exception:
        return (len(text) + 3) // 4


# ── term extraction / matching ──────────────────────────────────────────────
# Mirrors remembering/scripts/hints.py + muninn_utils/correction_gate.py so the
# fire-proxy uses the same notion of "content term" the live trigger-match uses.

_STOP = {
    "the", "and", "for", "with", "that", "this", "from", "into", "your", "you",
    "are", "was", "not", "but", "all", "any", "can", "has", "had", "have",
    "when", "what", "which", "who", "why", "how", "does", "did", "get", "got",
    "use", "used", "using", "via", "per", "its", "it's", "one", "two", "off",
    "out", "now", "new", "old", "see", "set", "run", "ran", "add", "top",
}


def extract_terms(text: str) -> set[str]:
    """Content terms from ``text``: hyphen-aware whole tokens plus their
    snake/camel/hyphen split parts, lowercased, ≥3 chars, minus stop words.
    Quoted phrases kept whole. Identical rules to correction_gate.extract_terms
    so the proxy and the live gate agree on what a "term" is."""
    if not text:
        return set()
    terms: set[str] = set()
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


# Generic key suffixes that carry no domain meaning — stripped when deriving
# match terms from a key name so "backend-impl-trigger" → {backend, impl}.
_GENERIC_KEY_PARTS = {
    "trigger", "protocol", "pattern", "discipline", "policy", "routing",
    "handling", "behavior", "workflow", "format", "usage", "refs", "signature",
    "register", "capabilities", "safeguards", "diagnostic", "vocabulary",
    "architecture", "imperatives", "provenance", "retrieval",
}

# Curated high-precision domain terms per boot-loaded key. Keeps the proxy
# discriminating: without this, a 12k-char entry's own vocabulary would match
# half the corpus. Absent keys fall back to key-derived terms (marked "auto").
# Precision over recall — a few unambiguous terms per entry.
DOMAIN_TERMS: dict[str, list[str]] = {
    # ── profile / identity (always-on; fire is informational) ──
    "muninn-voice-signature": ["voice-signature", "anti-pattern", "throat-clearing",
                                "blog-writing", "prose-register", "banished"],
    "voice": ["austegard.com", "personal-voice", "blog-voice"],
    "tensions": ["tension", "corrigibility", "sycophancy"],
    "intellectual_interests": ["intellectual-interests"],
    "relationship": ["oskar", "relationship"],
    "values": ["values", "corvid"],
    "personality": ["personality", "raven"],
    "identity": ["identity", "muninn"],
    "timezone": ["timezone", "eastern", "minneapolis"],
    "memory-behavior": ["memory-behavior"],
    # ── ops: triggers (dispatch; fire is the point) ──
    "github-routing": ["github", "pull-request", "issue", "commit", "branch", "gh_token"],
    "blog-writing-trigger": ["blog", "prose", "writing", "austegard.com"],
    "blog-publishing-trigger": ["publish", "blog", "bluesky", "atom", "whitewind"],
    "backend-impl-trigger": ["backend", "route", "handler", "endpoint", "fastapi"],
    "html-build-trigger": ["html", "dashboard", "deck", "slide", "artifact"],
    "story-forge-trigger": ["story", "fiction", "narrative"],
    "procedure-authoring-trigger": ["procedure", "flowing", "flowchart", "graph"],
    "skill-authoring-trigger": ["skill", "skill-language", "frontmatter"],
    "cross-frame-retrieval-trigger": ["cross-frame", "retrieval", "analogy"],
    "prior-art-trigger": ["prior-art", "prior-work", "existing-implementation"],
    "task-routing": ["task-routing", "route", "dispatch", "subagent"],
    # ── ops: reference/knowledge (semi-passive) ──
    "operating-imperatives": ["operating-imperative", "ground-truth"],
    "satisfaction-register": ["satisfaction", "register", "engagement"],
    "filedrop-implementation": ["filedrop", "upload", "file-drop"],
    "instruction-provenance": ["instruction-provenance", "provenance"],
    "confabulation-cascade": ["confabulation", "cascade", "hallucination"],
    "bash-tool-timeout": ["timeout", "bash-tool", "long-running"],
    "bike-coach-protocol": ["bike", "cycling", "strava", "coach", "training"],
    "pr-workflow": ["pull-request", "pr-workflow", "mergeable", "branch"],
    "grounding-safeguards": ["grounding", "ground-truth", "verify"],
    "kokoro-tts-cpu": ["kokoro", "tts", "text-to-speech", "audio"],
    "container-capabilities": ["container", "layer", "playwright", "chromium"],
    "phase3-refs-discipline": ["phase3", "refs", "reference-discipline"],
    "recall-vocabulary": ["recall-vocabulary", "recall-tag"],
    "eval-realism": ["eval-realism", "synthetic", "benchmark", "held-out"],
    "proxy-503-retry-pattern": ["503", "turso", "cold-start", "retry", "backoff"],
    "private-tag-discipline": ["private-tag", "private", "redact"],
    "hub-spoke-architecture": ["hub", "spoke", "add_repo"],
    "preference-signal-format": ["preference", "signal"],
    "dev-workflow": ["dev-workflow", "test", "lint"],
    "recall-empty-diagnostic": ["recall-empty", "no-results", "diagnostic"],
    "boot-behavior": ["boot", "session-start"],
    "env-file-handling": ["env-file", "credential", "dotenv"],
    "error-handling": ["error-handling", "exception"],
    "question-style": ["question-style", "clarifying"],
    "skill-workflow": ["skill-workflow"],
    "recall-fields": ["recall-field"],
    "shorthand": ["shorthand", "abbreviation"],
    "ccotw": ["ccotw", "claude-code-on-the-web"],
    "private-daily-tasks": ["daily-task"],
    "active-todos": ["active-todo"],
}

# Explicit kind overrides. Everything profile-category defaults to "identity";
# these promote the exceptions.
KIND: dict[str, str] = {
    "muninn-voice-signature": "catalog",
    "github-routing": "trigger",
    "blog-writing-trigger": "trigger",
    "blog-publishing-trigger": "trigger",
    "backend-impl-trigger": "trigger",
    "html-build-trigger": "trigger",
    "story-forge-trigger": "trigger",
    "procedure-authoring-trigger": "trigger",
    "skill-authoring-trigger": "trigger",
    "cross-frame-retrieval-trigger": "trigger",
    "prior-art-trigger": "trigger",
    "task-routing": "trigger",
}


def match_terms_for(key: str, overrides: dict[str, list[str]] | None = None) -> tuple[set[str], bool]:
    """Return ``(terms, curated)`` — the domain terms a memory must reference to
    count as a fire for ``key``. ``curated`` is False when the terms were
    derived from the key name (lower precision), so the report can flag it."""
    table = overrides if overrides is not None else DOMAIN_TERMS
    if key in table:
        return {t.lower() for t in table[key]}, True
    # Fallback: key tokens minus generic suffixes.
    parts = {p for p in re.split(r"[-_]", key.lower()) if len(p) >= 3}
    parts -= _GENERIC_KEY_PARTS
    return parts, False


def kind_for(key: str, category: str) -> str:
    if key in KIND:
        return KIND[key]
    if category == "profile":
        return "identity"
    return "ops"


def memory_matches(mem_terms: set[str], domain_terms: set[str]) -> bool:
    """A memory references an entry's domain if any domain term appears among
    the memory's content terms. Whole-term (not substring) to avoid "pr" in
    "print"; the terms are already split hyphen-aware so multi-word domain
    phrases match when their tokens are present."""
    if not domain_terms:
        return False
    for dt in domain_terms:
        if " " in dt or "-" in dt or "." in dt:
            # multi-part phrase: require every part present
            parts = {p for p in re.split(r"[ \-.]", dt) if len(p) >= 3}
            if parts and parts <= mem_terms:
                return True
        elif dt in mem_terms:
            return True
    return False


# ── data shapes ──────────────────────────────────────────────────────────────

@dataclass
class Memory:
    """Minimal memory projection the ledger needs."""
    month: str          # YYYY-MM from created_at
    terms: set[str]     # pre-extracted content terms


@dataclass
class Entry:
    key: str
    category: str
    chars: int
    value: str = ""             # optional; only needed if recomputing tokens
    logged_fires: int = 0       # from config.fire_count, 0 until instrumented
    last_fired: str | None = None


@dataclass
class LedgerRow:
    key: str
    category: str
    kind: str
    chars: int
    tokens: int
    curated_terms: bool
    hits: int                   # active memories referencing the domain
    months: int                 # distinct months with ≥1 hit
    recent_hits: int            # hits in the most recent month bucket present
    logged_fires: int
    last_fired: str | None
    chars_per_hit: float        # ranking metric: high = costly, rarely relevant

    def to_dict(self) -> dict:
        d = asdict(self)
        # inf isn't valid JSON; surface never-fired as null cost/fire.
        if d["chars_per_hit"] == float("inf"):
            d["chars_per_hit"] = None
        return d


# ── core computation (pure) ──────────────────────────────────────────────────

def build_ledger(entries: Sequence[Entry], memories: Sequence[Memory],
                 overrides: dict[str, list[str]] | None = None) -> list[LedgerRow]:
    """Join boot entries against the memory corpus into ranked rows.

    Ranked by ``chars_per_hit`` descending so the most expensive-per-use entries
    sort to the top — the prune queue. ``identity`` rows are cost-real but
    fire-informational, so they are tagged and the caller decides whether to
    include them in the demotion pass (they should not be demoted; they are the
    self)."""
    months_present = sorted({m.month for m in memories})
    latest_month = months_present[-1] if months_present else ""

    rows: list[LedgerRow] = []
    for e in entries:
        terms, curated = match_terms_for(e.key, overrides)
        hit_months: set[str] = set()
        hits = 0
        recent = 0
        for m in memories:
            if memory_matches(m.terms, terms):
                hits += 1
                hit_months.add(m.month)
                if m.month == latest_month:
                    recent += 1
        tokens = estimate_tokens(e.value) if e.value else (e.chars + 3) // 4
        rows.append(LedgerRow(
            key=e.key,
            category=e.category,
            kind=kind_for(e.key, e.category),
            chars=e.chars,
            tokens=tokens,
            curated_terms=curated,
            hits=hits,
            months=len(hit_months),
            recent_hits=recent,
            logged_fires=e.logged_fires,
            last_fired=e.last_fired,
            # 0 hits ⇒ infinite cost/fire: never-referenced sorts to the top of
            # the prune queue regardless of size (rendered as "∞(0 hits)").
            chars_per_hit=round(e.chars / hits, 1) if hits else float("inf"),
        ))
    # Worst cost/fire first; among ties (esp. inf/never-fired), bigger first.
    rows.sort(key=lambda r: (r.chars_per_hit, r.chars), reverse=True)
    return rows


def demotion_candidates(rows: Sequence[LedgerRow], *, min_chars: int = 400) -> list[LedgerRow]:
    """Trigger/ops rows that never fired in the corpus and are big enough to be
    worth reclaiming. Identity/catalog rows are excluded — they are not demoted
    on a fire count. Conservative by design: this proposes, a human disposes."""
    return [
        r for r in rows
        if r.kind in ("trigger", "ops")
        and r.hits == 0
        and r.logged_fires == 0
        and r.chars >= min_chars
    ]


# ── rendering ────────────────────────────────────────────────────────────────

def render_table(rows: Sequence[LedgerRow]) -> str:
    hdr = ("| rank | key | kind | chars | tokens | hits | months | recent | "
           "logged | chars/hit | terms |")
    sep = "|---|---|---|--:|--:|--:|--:|--:|--:|--:|---|"
    lines = [hdr, sep]
    for i, r in enumerate(rows, 1):
        cph = "∞(0 hits)" if r.hits == 0 else f"{r.chars_per_hit:g}"
        terms = "curated" if r.curated_terms else "auto"
        lines.append(
            f"| {i} | `{r.key}` | {r.kind} | {r.chars} | {r.tokens} | {r.hits} "
            f"| {r.months} | {r.recent_hits} | {r.logged_fires} | {cph} | {terms} |"
        )
    return "\n".join(lines)


def summarize(rows: Sequence[LedgerRow], corpus_months: int, corpus_size: int) -> str:
    total_chars = sum(r.chars for r in rows)
    total_tokens = sum(r.tokens for r in rows)
    never = [r for r in rows if r.hits == 0]
    demote = demotion_candidates(rows)
    ident = [r for r in rows if r.kind == "identity"]
    lines = [
        f"- Boot-loaded entries: **{len(rows)}**",
        f"- Boot payload cost: **{total_chars:,} chars / ~{total_tokens:,} tokens**",
        f"- Corpus sampled: **{corpus_size:,} active memories across {corpus_months} months**",
        f"- Never referenced in corpus: **{len(never)}** entries "
        f"({sum(r.chars for r in never):,} chars)",
        f"- Demotion candidates (trigger/ops, 0 fires, ≥400 chars): "
        f"**{len(demote)}** — {', '.join('`'+r.key+'`' for r in demote) or 'none'}",
        f"- Identity/always-on (not demotable): **{len(ident)}** "
        f"({sum(r.chars for r in ident):,} chars)",
    ]
    return "\n".join(lines)


# ── Turso adapters ───────────────────────────────────────────────────────────

def _month(iso: str) -> str:
    return (iso or "")[:7]


def load_boot_entries(exec_fn: Callable | None = None) -> list[Entry]:
    """Boot-loaded config entries, with logged fire counts if the columns exist."""
    _exec = exec_fn or _live_exec()
    cols = {c["name"] for c in _exec("PRAGMA table_info(config)")}
    has_fire = "fire_count" in cols
    sel = "key, category, LENGTH(value) AS len, value"
    if has_fire:
        sel += ", fire_count, last_fired"
    rows = _exec(f"SELECT {sel} FROM config WHERE boot_load=1")
    out = []
    for r in rows:
        out.append(Entry(
            key=r["key"],
            category=r["category"],
            chars=int(r["len"]),
            value=r.get("value") or "",
            logged_fires=int(r["fire_count"]) if has_fire and r.get("fire_count") is not None else 0,
            last_fired=r.get("last_fired") if has_fire else None,
        ))
    return out


def load_memory_corpus(exec_fn: Callable | None = None) -> list[Memory]:
    """Active (non-deleted) memories projected to (month, content-terms)."""
    _exec = exec_fn or _live_exec()
    rows = _exec("SELECT created_at, summary, tags, t FROM memories WHERE deleted_at IS NULL")
    out = []
    for r in rows:
        blob_parts = [r.get("summary") or "", r.get("t") or ""]
        tg = r.get("tags")
        if tg:
            try:
                tags = json.loads(tg) if str(tg).strip().startswith("[") else [tg]
                blob_parts.append(" ".join(str(x) for x in tags))
            except Exception:
                blob_parts.append(str(tg))
        out.append(Memory(month=_month(r.get("created_at") or ""),
                           terms=extract_terms(" ".join(blob_parts))))
    return out


def _live_exec():  # pragma: no cover - requires live Turso
    """Resolve remembering's _exec, whether imported as a package or flat."""
    try:
        from scripts.turso import _exec  # PYTHONPATH=<repo>/remembering
        return _exec
    except Exception:
        from remembering.scripts.turso import _exec  # PYTHONPATH=<repo>
        return _exec


def report(exec_fn: Callable | None = None, as_json: bool = False) -> str:
    """Full instrument run against live Turso (or an injected exec_fn)."""
    entries = load_boot_entries(exec_fn)
    memories = load_memory_corpus(exec_fn)
    rows = build_ledger(entries, memories)
    corpus_months = len({m.month for m in memories if m.month})
    if as_json:
        return json.dumps({
            "summary": {
                "entries": len(rows),
                "total_chars": sum(r.chars for r in rows),
                "total_tokens": sum(r.tokens for r in rows),
                "corpus_memories": len(memories),
                "corpus_months": corpus_months,
            },
            "rows": [r.to_dict() for r in rows],
        }, indent=2, default=str)
    return (
        "# Boot Payload Ledger — cost vs. fire rate\n\n"
        + summarize(rows, corpus_months, len(memories))
        + "\n\n## Ranked table (worst cost/fire first)\n\n"
        + render_table(rows)
        + "\n\n_Fire rate is a memory-corpus reference proxy (no config_get log "
        "exists yet); `logged` is the exact go-forward counter, 0 until "
        "`MUNINN_INSTRUMENT_FIRES=1` has run for a window. `terms=auto` rows use "
        "key-derived match terms (lower precision) — add a curated entry to "
        "`DOMAIN_TERMS` to tighten them._\n"
    )


if __name__ == "__main__":  # pragma: no cover
    import sys
    print(report(as_json="--json" in sys.argv))
