"""recall_sufficiency — recall until the answer is sufficient.

The portable kernel of Google's "agentic RAG" (research.google, 2026-06-05),
minus the five-agent enterprise framing: recall -> judge whether what you have
answers the question -> if not, name the missing piece and search specifically
for it -> repeat -> return the accumulated context. The judge naming the gap,
not a fixed retry count, is what drives the next query.

WHEN TO REACH FOR IT (be honest):
On a single rich KB the loop is usually degenerate — FTS+tags already cover the
query terms and a capable model notices its own gaps without the scaffold. It
earns its keep in AUTONOMOUS/programmatic runs (a routine that can't iterate
interactively) and in CROSS-CORPUS cases where the planner must pick among
access-controlled islands it can't see at once. For interactive single-KB work,
plain recall() plus your own judgement is lighter.

CONTROL-FLOW NOTE (why it's shaped this way):
flowing's retry_until(value) re-runs the IDENTICAL task fn — True stops, False
retries on the retry= budget. So a reformulation can't be hardcoded in the fn or
every loop searches the same thing. Instead the judge mutates a shared query
queue on insufficiency (append the sharper query), returns False, and the next
fn run reads queue[-1]. The accumulated pool is deduped across iterations, so
each loop ADDS context.

BUDGETS ARE SEPARATE: transient retrieval failures (Turso cold-start 503, the
proxy-503-retry-pattern) are absorbed inside the task by internal backoff, so
flowing's retry= means "search again for a missing piece" and never "the proxy
hiccuped."

OUTPUT IS THE STATE, NOT THE StepResult: read the returned LoopState for the
accumulated pool and the gap/termination trace. state.satisfied / state.stalled
tell you whether the loop met the bar, gave up on no progress, or hit the
budget — regardless of the flow's terminal StepResult.

JUDGE IS PLUGGABLE. Default is a dependency-free term-coverage heuristic (works
regardless of CF/Gemini token state). An LLM judge slots in via the same Verdict
contract — but see llm_judge_factory: self-grading retrieval is the subject of
"When the LLM Grades Itself" (muninn.austegard.com/blog/llm-grades-itself.html).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


# ── Judge contract ──────────────────────────────────────────────────────────

@dataclass
class Verdict:
    """A judge's ruling on whether the pool answers the question."""
    sufficient: bool
    gap: str = ""            # human-readable: what's missing
    reformulation: str = ""  # the next query to run if insufficient


# A judge is any callable: (question: str, pool: list[dict]) -> Verdict
# where each pool item is {"id", "text", "tags"}.


# ── Default judge: term coverage (no external dependency) ────────────────────

_STOP = {
    "what", "which", "who", "whom", "whose", "when", "where", "why", "how",
    "is", "are", "was", "were", "be", "been", "being", "the", "a", "an", "of",
    "to", "in", "on", "for", "and", "or", "but", "with", "by", "as", "at",
    "from", "that", "this", "these", "those", "it", "its", "do", "did", "does",
    "have", "has", "had", "i", "we", "you", "they", "my", "our", "their",
    "about", "into", "over", "any", "all", "some",
}


def _content_terms(text: str) -> list[str]:
    toks = re.findall(r"[a-z0-9][a-z0-9\-./]{2,}", text.lower())
    seen, out = set(), []
    for t in toks:
        if t in _STOP or t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out


def term_coverage_judge(question: str, pool: list, *, threshold: float = 0.66) -> Verdict:
    """Sufficient when >= `threshold` of the question's content terms appear in
    the accumulated pool. The gap is the uncovered terms; the reformulation
    searches for exactly those — the dependency-free analog of the Sufficient
    Context Agent's "go back and search specifically for X."
    """
    terms = _content_terms(question)
    if not terms:
        return Verdict(True)
    haystack = " ".join(
        (m.get("text", "") + " " + " ".join(m.get("tags", []))) for m in pool
    ).lower()
    missing = [t for t in terms if t not in haystack]
    covered = 1.0 - len(missing) / len(terms)
    if not missing or covered >= threshold:
        return Verdict(True)
    return Verdict(
        sufficient=False,
        gap=f"covered {covered:.0%}; missing: {', '.join(missing)}",
        reformulation=" ".join(missing),
    )


# ── LLM judge slot (upgrade path; read the caveat) ───────────────────────────

def llm_judge_factory(call_model):
    """Wrap any `call_model(prompt: str) -> str` into a judge. Expects the model
    to return JSON: {"sufficient": bool, "gap": str, "reformulation": str}.

    CAVEAT — this is self-grading retrieval. Before reaching for it:
      * A capable in-session model already notices its own gaps and re-queries
        without the scaffold. The loop is then degenerate.
      * The value is real at SMALL judges (can't hold the whole pool) or genuine
        CROSS-CORPUS with access-controlled islands. Neither is a single rich KB.
      * Self-grading failure modes: muninn.austegard.com/blog/llm-grades-itself.html
    """
    import json

    def judge(question: str, pool: list) -> Verdict:
        snippets = "\n".join(
            f"- [{m.get('id', '')[:8]}] {m.get('text', '')[:200]}" for m in pool
        )
        prompt = (
            "You are a sufficient-context inspector. Given a QUESTION and the "
            "SNIPPETS retrieved so far, decide if the snippets collectively "
            "contain enough to answer fully.\n"
            "Return ONLY JSON: {\"sufficient\": bool, \"gap\": str, "
            "\"reformulation\": str}. If sufficient, gap/reformulation may be "
            "empty. If not, gap names exactly what is missing and reformulation "
            "is a focused search query for that missing piece.\n\n"
            f"QUESTION: {question}\n\nSNIPPETS:\n{snippets or '(none yet)'}"
        )
        raw = call_model(prompt).strip()
        raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
        d = json.loads(raw)
        return Verdict(
            sufficient=bool(d.get("sufficient")),
            gap=str(d.get("gap", "")),
            reformulation=str(d.get("reformulation", "")),
        )

    return judge


# ── Loop state ───────────────────────────────────────────────────────────────

@dataclass
class LoopState:
    queries: list = field(default_factory=list)
    seen_ids: set = field(default_factory=set)
    pool: list = field(default_factory=list)
    gaps: list = field(default_factory=list)
    iters: int = 0
    satisfied: bool = False      # judge ruled the pool sufficient
    stalled: bool = False        # gave up: a reformulation made no progress
    _last_pool_size: int = 0


def _import_recall():
    """Resolve recall() from whichever layout is mounted (mirrors issue_close)."""
    try:
        from scripts import recall  # type: ignore
        return recall
    except ImportError:
        from remembering.scripts import recall  # type: ignore
        return recall


def _recall_resilient(recall, query, n, *, attempts=4, base_delay=0.5):
    """recall() with internal backoff for the cold-start proxy 503 / Turso blip.
    Keeps transient failure OUT of the sufficiency budget. See ops entry
    proxy-503-retry-pattern.
    """
    import time
    last = None
    for i in range(attempts):
        try:
            return recall(query, n=n)
        except Exception as e:          # network / JSON-decode on cold start
            last = e
            if i < attempts - 1:
                time.sleep(base_delay * (i + 1))
    raise last


# ── The recipe ───────────────────────────────────────────────────────────────

def build_recall_loop(question, *, judge=term_coverage_judge,
                      seed_queries=None, max_iters=4, n=6):
    """Build a flowing graph that recalls until `judge` rules the pool
    sufficient, a reformulation stops making progress, or `max_iters` is hit.
    Returns (Flow, LoopState). Inspect the LoopState after flow.run() — it is
    the real output (pool, gaps, satisfied/stalled), populated regardless of the
    flow's terminal StepResult.

    `retry=max_iters-1` is the SUFFICIENCY budget only; transient retrieval
    failures are absorbed inside the task by _recall_resilient.
    """
    from muninn_utils import flowing   # lazy: needs the claude-skills mount
    recall = _import_recall()

    state = LoopState(queries=list(seed_queries or [question]))

    def _gate(pool):
        verdict = judge(question, pool)
        if verdict.sufficient:
            state.satisfied = True
            return True
        # no-progress guard: same gap as the previous pass AND the pool didn't
        # grow means reformulating again won't help — give up rather than burn
        # the budget re-searching a term that isn't in the corpus.
        prev_gap = state.gaps[-1] if state.gaps else None
        grew = len(pool) > state._last_pool_size
        state.gaps.append(verdict.gap)
        state._last_pool_size = len(pool)
        if verdict.gap == prev_gap and not grew:
            state.stalled = True
            return True
        nxt = verdict.reformulation or question
        if nxt not in state.queries:        # don't enqueue a duplicate query
            state.queries.append(nxt)
        return False

    @flowing.task(retry=max_iters - 1, retry_until=_gate, name="gather")
    def gather():
        state.iters += 1
        q = state.queries[-1]               # newest reformulation
        for r in _recall_resilient(recall, q, n):
            rid = r.get("id")
            if not rid or rid in state.seen_ids:
                continue
            state.seen_ids.add(rid)
            state.pool.append({
                "id": rid,
                "text": r.get("summary") or "",
                "tags": list(r.get("tags", [])),
            })
        return state.pool                    # judge sees the whole accumulated pool

    return flowing.Flow(gather, fail_fast=False), state


def recall_until_sufficient(question, **kw):
    """Convenience: build, run, and return the populated LoopState."""
    flow, state = build_recall_loop(question, **kw)
    flow.run()
    return state


# ── Demo ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    from functools import partial
    q = sys.argv[1] if len(sys.argv) > 1 else (
        "What did Oskar correct about the TaC paper and the bitter lesson?"
    )
    thr = float(sys.argv[2]) if len(sys.argv) > 2 else 0.66
    state = recall_until_sufficient(
        q, judge=partial(term_coverage_judge, threshold=thr), max_iters=4, n=5
    )
    verdict = ("satisfied" if state.satisfied
               else "stalled (no progress)" if state.stalled
               else "budget exhausted")
    print(f"QUESTION  : {q}")
    print(f"threshold : {thr}\n")
    print(f"outcome     : {verdict}")
    print(f"iterations  : {state.iters}")
    print(f"queries run : {state.queries}")
    print(f"gaps named  : {state.gaps or '(none — sufficient on first pass)'}")
    print(f"pool size   : {len(state.pool)} unique memories")
    print("\npool:")
    for m in state.pool:
        print(f"  [{m['id'][:8]}] {', '.join(m['tags'][:4])}")
