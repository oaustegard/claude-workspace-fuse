"""gemini-mini-Muninn — inverted delegation: main-Muninn scopes the slice, Gemini reasons.

RECOVERED 2026-08-01 from memory 81b2dc92, alongside `mini_muninn`. Lost the same way, in
the same container.

The shape is the mirror of the native subagent. Gemini has no tools and no container, so it
cannot recall for itself; main-Muninn does the recall and ships the slice into the prompt.
Read-only by construction — it never touches Turso, because it cannot reach it. One API
call, seconds, cents.

ROUTING (memory 81b2dc92, measured on the same corpus): native subagent when the question
is causal, temporal or adversarial (what is stale, what contradicts what, what is still
broken); Gemini when it is extraction or classification at volume over a slice already
scoped. Gemini flattened three distinct blockers into one story, wrongly marked 61eb79d1
stale rather than incomplete, and credited gh-api-proxy with a fix that came from 098a7b2e
— it conflates "a later memory mentions a fix" with "that fix addresses this cause". Trust
its coverage; do not trust its supersession judgments without a native pass.

Both are cheap enough to run together and diff. The disagreements are themselves signal
about which memories are ambiguously worded.

A NOTE ON THE SCHEMA. The original ran against invoking-gemini before 0.7.1, whose
`_pydantic_to_schema` emitted `$defs`/`$ref` that Gemini's `responseSchema` rejects — a bare
400 for any nested model, three wasted retries, then None. `Finding` nested inside `Report`
is exactly that shape, so some of the original's weak attribution may have been truncation
rather than reasoning. Requires invoking-gemini >= 0.7.1.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from .capability_model import expand

MODEL = "gemini-3.6-flash"  # explicit string: the `flash` alias resolves stale
_MAX_SLICE = 60


class Finding(BaseModel):
    claim: str = Field(description="One thing the slice establishes, stated plainly.")
    memory_ids: list[str] = Field(
        default_factory=list, description="Short ids of the memories supporting it."
    )
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class Contradiction(BaseModel):
    description: str
    memory_ids: list[str] = Field(default_factory=list)


class Report(BaseModel):
    findings: list[Finding] = Field(default_factory=list)
    contradictions: list[Contradiction] = Field(default_factory=list)
    gaps: list[str] = Field(
        default_factory=list, description="What the slice does not answer."
    )
    recommended_writes: list[str] = Field(
        default_factory=list,
        description="Memories worth storing. Proposals only — this agent cannot write.",
    )


_INSTRUCTIONS = """You are analyzing a slice of an agent's long-term memory corpus.

Each memory carries an id, a timestamp, tags, and a summary. Answer the task using ONLY
the slice — you have no tools and cannot search for more.

Rules that matter here:
- Cite memory ids for every finding. An uncited claim is worthless to the caller.
- A later memory mentioning a fix does NOT establish that the fix addressed a given cause.
  Keep distinct causes distinct; say so in `gaps` if the slice cannot connect them.
- "Incomplete" and "stale" are different. Do not mark a record stale unless something in
  the slice contradicts it.
- `recommended_writes` are proposals. You cannot write; the caller decides."""


def build_slice(
    query: str, *, n: int = 30, tags: list[str] | None = None
) -> list[dict[str, Any]]:
    """Main-Muninn's half: recall through the read-only capability surface."""
    api = expand(["recall"], allow_writes=False, strict_requires=True)
    rows = api.functions["recall"](query, n=min(n, _MAX_SLICE), tags=tags)
    out = []
    for row in rows:
        # dict() on a MemoryResult works via keys(); isinstance(row, dict) does not, and
        # falling back to str(row) would strip the ids the prompt requires it to cite.
        item = dict(row) if hasattr(row, "keys") else {"summary": str(row)}
        out.append(
            {
                "id": str(item.get("id", ""))[:8],
                "t": item.get("t") or item.get("valid_from"),
                "tags": item.get("tags") or [],
                "summary": item.get("summary", ""),
            }
        )
    return out


def analyze(
    task: str,
    *,
    query: str | None = None,
    n: int = 30,
    tags: list[str] | None = None,
    memories: list[dict[str, Any]] | None = None,
    model: str = MODEL,
) -> Report:
    """Ship a scoped slice to Gemini, get back a validated Report.

    Pass `memories` to analyze a slice you already have; otherwise `query` is recalled.
    """
    if memories is None:
        memories = build_slice(query or task, n=n, tags=tags)
    if not memories:
        return Report(gaps=["recall returned nothing for this query"])

    from invoking_gemini import generate_structured  # type: ignore

    prompt = (
        f"{_INSTRUCTIONS}\n\nTASK:\n{task}\n\nSLICE ({len(memories)} memories):\n"
        + json.dumps(memories, indent=2, default=str)
    )
    return generate_structured(
        prompt, schema=Report, model=model, thinking_level="medium"
    )


def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="gemini-mini-muninn")
    p.add_argument("task")
    p.add_argument("--query", default=None, help="recall query (defaults to the task)")
    p.add_argument("--n", type=int, default=30)
    p.add_argument("--tags", nargs="*", default=None)
    args = p.parse_args(argv)
    report = analyze(args.task, query=args.query, n=args.n, tags=args.tags)
    print(report.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
