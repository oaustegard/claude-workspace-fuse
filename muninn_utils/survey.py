"""Survey: the whole memory corpus at a fixed line budget.

recall() is CONVERGENT — you name a topic and get matches. This is the
DIVERGENT operator: it renders every memory under a fixed budget, verbatim at
the recent end and progressively collapsed with age. It answers questions
recall cannot: "what happened in March", "what has this corpus been about",
"where are the gaps".

USAGE:
    from muninn_utils.survey import survey

    print(survey())                         # whole corpus, 120 lines
    print(survey(budget=200))               # finer
    print(survey(lo=400, hi=900))           # drill into a range (zoom)
    print(survey(tags=['blog-writing']))    # survey one thread

    rows = survey(as_rows=True)             # programmatic

PROVENANCE AND THE ONE DELIBERATE DIVERGENCE
--------------------------------------------
The block-cover algorithm is taken from Victor Taelin's OptMem
(github.com/VictorTaelin/OptMem, MIT): tile [0,T) with aligned power-of-two
blocks, keep a block whole iff its size is at most `alpha` times its age,
binary-search `alpha` so the tile count hits the budget. Detail decays with
age; the output is always exactly `budget` lines regardless of T.

OptMem renders each block by ABSTRACTIVE summarization — an LLM merges two
halves into one line, recursively. Measured on 2026-07-28 over a 64-memory
corpus with 63 real merges: every planted operational rule survived 16:1,
three of six were gone by 32:1, and only a bare identifier survived 64:1. One
merge at 32:1 fused two unrelated facts into a claim neither source made,
despite the merge prompt saying "Invent nothing."

So this renders blocks EXTRACTIVELY instead: a block line is its date span,
its count, its most frequent tags, and the verbatim head of its
highest-priority member. Extraction loses coverage at the same ratio but
cannot fabricate, and needs no LLM call — a survey of 2,509 memories costs one
query, not 2,508 merges. That trade is the whole reason this is a separate
implementation rather than a port.
"""

from collections import Counter

DEFAULT_BUDGET = 120
DEFAULT_WIDTH = 180


# ---------------------------------------------------------------- block math

def _cover(T, alpha):
    """Tile [0,T) with aligned power-of-two blocks; keep a block whole iff its
    size is at most `alpha` times its age. Bigger alpha = coarser."""
    root = 1
    while root < T:
        root *= 2
    out, stack = [], [(0, root)]
    while stack:
        lo, hi = stack.pop()
        if lo >= T:
            continue
        size = hi - lo
        if size > 1 and (hi > T or size > alpha * (T - lo)):
            mid = (lo + hi) // 2
            stack.append((mid, hi))
            stack.append((lo, mid))
        else:
            out.append((lo, hi))
    out.sort()
    return out


def cover(T, budget):
    """At most `budget` blocks over [0,T), finest at the recent end."""
    if T <= 0:
        return []
    if T <= budget:
        return [(i, i + 1) for i in range(T)]
    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if len(_cover(T, mid)) > budget:
            lo = mid
        else:
            hi = mid
    out = _cover(T, hi)
    # Block sizes jump in powers of two, so alpha alone undershoots. Spend the
    # remainder on the present, where detail is worth most.
    while len(out) < budget:
        i = max((i for i, b in enumerate(out) if b[1] - b[0] > 1), default=None)
        if i is None:
            break
        lo_, hi_ = out[i]
        mid = (lo_ + hi_) // 2
        out[i:i + 1] = [(lo_, mid), (mid, hi_)]
    return out


# ---------------------------------------------------------------- corpus

def _tags(m):
    t = m.get("tags")
    if isinstance(t, list):
        return [x for x in t if x]
    if isinstance(t, str):
        return [x.strip() for x in t.split(",") if x.strip()]
    return []


def _day(m):
    return (m.get("created_at") or m.get("valid_from") or "")[:10]


def _pri(m):
    try:
        return int(m.get("priority") or 0)
    except (TypeError, ValueError):
        return 0


_CACHE = []


def fetch(refresh=False):
    """The corpus, oldest first — fetched once per session.

    Truncation happens in SQL, not in Python. Measured 2026-07-28: the store
    holds 4.0 MB of summary text (avg 1,602 chars, max 73 KB) and fetching it
    whole exceeds the 30s read timeout. The renderer clips to ~180 chars, so
    nothing visible is lost; 300 leaves headroom for a wider `width`.

    Even truncated the read runs 7-14s and occasionally still times out, so it
    retries (proxy-503-retry-pattern) and the result is cached — drilling with
    lo/hi must not pay a second full fetch.
    """
    import time

    from scripts.memory import _exec
    if _CACHE and not refresh:
        return _CACHE[0]
    # No ORDER BY: `created_at` is unindexed, so the engine sorts the whole
    # table (4,976 rows, 4 MB of text) before applying anything. Measured
    # 2026-07-28: `SELECT id ... ORDER BY created_at LIMIT 50` took 26.6s
    # against 0.8s for a bare COUNT. Sorting 2.5k dicts client-side is free.
    sql = """
        SELECT id, substr(summary, 1, 300) AS summary, tags, type,
               priority, created_at
        FROM memories
        WHERE deleted_at IS NULL AND COALESCE(is_superseded, 0) = 0
    """
    last = None
    for attempt in range(4):
        try:
            rows = sorted(_exec(sql), key=lambda m: m.get("created_at") or "")
            _CACHE[:] = [rows]
            return rows
        except Exception as e:  # noqa: BLE001 — retried, then re-raised below
            last = e
            time.sleep(0.5 * (attempt + 1))
    raise RuntimeError(f"survey: corpus fetch failed after 4 attempts: {last}")


def load(tags=None, include_confidential=False, memories=None):
    """Every live memory, oldest first. Position IS the chronological index.

    Confidential memories are excluded by default: a survey is a broad read,
    and private-tag-discipline says scoped projects must not surface in one.
    """
    if memories is None:
        memories = fetch()
    out = []
    want = set(tags or [])
    for m in memories:
        mt = set(_tags(m))
        if not include_confidential and "confidential" in mt:
            continue
        if want and not (want & mt):
            continue
        out.append(m)
    return out


# ---------------------------------------------------------------- rendering

def _clip(s, n):
    s = " ".join((s or "").split())
    if len(s) <= n:
        return s
    return s[:n - 1].rstrip() + "…"


def _block_line(mems, lo, hi, width):
    """One line for a range, built only from what the members actually say."""
    days = [d for d in (_day(m) for m in mems) if d]
    span = f"{days[0]}→{days[-1]}" if days else "?"
    common = [t for t, _ in Counter(
        t for m in mems for t in _tags(m)
        if not t[:4].isdigit()          # date tags carry no topic signal
    ).most_common(4)]
    # The exemplar is chosen, never synthesized: highest priority, newest wins.
    top = max(mems, key=lambda m: (_pri(m), _day(m)))
    head = f"#{lo}-{hi - 1}  {span}  n={hi - lo}"
    tagstr = f"[{' '.join(common)}]" if common else ""
    body = _clip(top.get("summary"),
                 max(40, width - len(head) - len(tagstr) - 3))
    return f"{head:<46} {tagstr} {body}"


def _leaf_line(m, i, width):
    head = f"#{i:<6} {_day(m)}"
    return f"{head}  {_clip(m.get('summary'), width - len(head) - 2)}"


def survey(budget=DEFAULT_BUDGET, lo=None, hi=None, tags=None,
           include_confidential=False, width=DEFAULT_WIDTH, memories=None,
           as_rows=False):
    """Render the corpus (or the slice [lo,hi)) in at most `budget` lines.

    Recent memories appear verbatim; older ones collapse into range lines whose
    resolution decays with age. Drilling in is the same call with lo/hi set.
    """
    mems = load(tags=tags, include_confidential=include_confidential,
                memories=memories)
    total = len(mems)
    a = 0 if lo is None else max(0, lo)
    b = total if hi is None else min(total, hi)
    window = mems[a:b]
    if not window:
        return [] if as_rows else "No memories in range."

    rows = []
    for blo, bhi in cover(len(window), budget):
        chunk = window[blo:bhi]
        rows.append({
            "lo": a + blo, "hi": a + bhi - 1, "n": bhi - blo,
            "from": _day(chunk[0]), "to": _day(chunk[-1]),
            "ids": [m["id"] for m in chunk] if bhi - blo == 1 else None,
            "line": (_leaf_line(chunk[0], a + blo, width) if bhi - blo == 1
                     else _block_line(chunk, a + blo, a + bhi, width)),
        })
    if as_rows:
        return rows

    coarsest = max(r["n"] for r in rows)
    header = (f"{len(window)} memories, #{a}-{b - 1}, "
              f"{_day(window[0])}→{_day(window[-1])} — "
              f"{len(rows)} lines, coarsest block {coarsest}:1")
    foot = ("Drill: survey(lo=<a>, hi=<b>). Exact text: recall(). "
            "Block lines are extracted, never summarized — the exemplar is one "
            "real memory, not a merge of the block.")
    return "\n".join([header, "-" * len(header)]
                     + [r["line"] for r in rows] + ["", foot])


if __name__ == "__main__":
    import sys
    kw = {}
    for arg in sys.argv[1:]:
        k, _, v = arg.partition("=")
        kw[k] = int(v) if v.isdigit() else v
    print(survey(**kw))
