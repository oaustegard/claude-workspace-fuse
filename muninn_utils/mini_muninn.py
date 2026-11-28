"""mini-Muninn — a read-only CLI over the memory corpus, for subagents.

RECOVERED 2026-08-01 from memory 81b2dc92. The original was written in a Cowork container
on 2026-07-29, validated (~105k subagent tokens, 9 tool calls, 3m18s for a 4-part corpus
audit; it independently derived 7 GitHub blockers with first-appearance dates and caught a
date conflict between memories 869f4366 and dd729083), and then lost with the container
because it was never committed. This is a reconstruction from that record, committed.

WHY A CLI AND NOT THE PYTHON API. Native subagents share the container filesystem, so a
booted session's sideload is already importable by them — which is the problem. Handing a
subagent `remembering.scripts.memory` hands it `forget`. A CLI whose subcommands are
generated from a read-only capability expansion cannot be talked into a write: the
functions are not in the process.

That is the change from the original, which achieved the same end by being a hand-written
copy with the dangerous functions left out. Same surface, but now the guarantee is
`expand(..., allow_writes=False)` raising at import if anyone adds a writing id to the
bundle, rather than a reviewer noticing.

Told to propose writes in its output rather than perform them, the subagent does.

    python -m muninn_utils.mini_muninn recall "gh proxy 403" --n 8
    python -m muninn_utils.mini_muninn batch "inbox routine" "egress proxy" --n 5
    python -m muninn_utils.mini_muninn ops routine-inbox-review-v1
    python -m muninn_utils.mini_muninn ops-list --category procedure
    python -m muninn_utils.mini_muninn spokes
    python -m muninn_utils.mini_muninn capabilities
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .capability_model import BUNDLES, Resolved, describe, expand

BUNDLE = "mini-muninn"


def surface() -> Resolved:
    """The read-only expansion. `allow_writes=False` is the enforcement, not a preference —
    if someone adds a writing id to the bundle this raises here rather than shipping."""
    return expand(BUNDLES[BUNDLE], allow_writes=False)


def _emit(payload: Any, *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, default=str))
        return
    if isinstance(payload, str):
        print(payload)
        return
    if isinstance(payload, (list, tuple)) or hasattr(payload, "__iter__") and not isinstance(payload, (str, bytes)):
        for item in payload:
            # MemoryResult is dict-LIKE but not a dict; an isinstance check here silently
            # dropped every memory id, which is the one field a citing subagent needs.
            if hasattr(item, "get") and item.get("summary") is not None:
                mid = str(item.get("id", ""))[:8]
                tags = item.get("tags") or []
                print(f"[{mid}] {item.get('type', '')} | {tags}")
                print(item["summary"])
                print()
            else:
                print(item)
        return
    print(json.dumps(payload, indent=2, default=str))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mini-muninn",
        description="Read-only Muninn corpus access for subagents. No writes exist here; "
        "propose them in your report instead.",
    )
    parser.add_argument("--json", action="store_true", help="emit raw JSON")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("recall", help="search the corpus")
    p.add_argument("query")
    p.add_argument("--n", type=int, default=10)
    p.add_argument("--tags", nargs="*", default=None)

    p = sub.add_parser("batch", help="several searches in one call")
    p.add_argument("queries", nargs="+")
    p.add_argument("--n", type=int, default=10)

    p = sub.add_parser("get", help="fetch one memory by id")
    p.add_argument("memory_id")

    p = sub.add_parser("chain", help="supersession chain for a memory")
    p.add_argument("memory_id")
    p.add_argument("--depth", type=int, default=3)

    p = sub.add_parser("ops", help="read one ops entry by key")
    p.add_argument("key")

    p = sub.add_parser("ops-list", help="list ops entries")
    p.add_argument("--category", default=None)

    sub.add_parser("spokes", help="the spoke registry")
    sub.add_parser("capabilities", help="what this surface grants, and what was dropped")

    args = parser.parse_args(argv)
    api = surface()
    fn = api.functions

    if args.cmd == "capabilities":
        print(describe(BUNDLES[BUNDLE]))
        if api.dropped:
            print("\ndropped in this environment:")
            for cid, why in api.dropped:
                print(f"  {cid}: {why}")
        return 0

    missing = {
        "recall": "recall",
        "batch": "recall_batch",
        "get": "get",
        "chain": "get_chain",
        "ops": "config_get",
        "ops-list": "config_list",
        "spokes": "spokes_list",
    }[args.cmd]
    if missing not in fn:
        why = dict(api.dropped).get(
            "spokes-read" if args.cmd == "spokes" else "recall", "unavailable"
        )
        print(f"`{args.cmd}` is not available here: {why}", file=sys.stderr)
        return 2

    if args.cmd == "recall":
        result = fn["recall"](args.query, n=args.n, tags=args.tags)
    elif args.cmd == "batch":
        result = fn["recall_batch"](list(args.queries), n=args.n)
    elif args.cmd == "get":
        result = fn["get"](args.memory_id)
    elif args.cmd == "chain":
        result = fn["get_chain"](args.memory_id, depth=args.depth)
    elif args.cmd == "ops":
        result = fn["config_get"](args.key)
        if result is None:
            print(f"no ops entry {args.key!r}", file=sys.stderr)
            return 1
    elif args.cmd == "ops-list":
        result = fn["config_list"](args.category)
    else:
        result = fn["spokes_list"]()

    _emit(result, as_json=args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
