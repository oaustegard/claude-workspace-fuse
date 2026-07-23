"""Search driver: hunt for tau >= 3 digraphs with no 3 disjoint dijoins.

Any UNSAT hit is cross-verified (both CEGAR backends + full enumeration)
before being reported. Everything is logged as JSONL to woodall/runs/.

Usage:
    python3 -m woodall.search liftings [--base D1|D2|D3] [--limit N]
    python3 -m woodall.search random [--n N] [--count N] [--seed S]
"""

from __future__ import annotations

import argparse
import collections
import json
import pathlib
import random
import sys
import time

from .digraph import Digraph
from .examples import schrijver_d1, cg_d2, cg_d3
from .generator import (GADGETS, enumerate_liftings, passes_filters,
                        random_structured_dag)
from .pack import pack, cross_verify_candidate

RUNS = pathlib.Path(__file__).parent / "runs"


def check_instance(G: Digraph, k: int = 3) -> dict:
    """Filter, then test for a k-packing. Returns a result record."""
    ok, reason = passes_filters(G, min_tau=k)
    if not ok:
        return {"filtered": reason}
    res = pack(G, k, solver="cpsat")
    rec = {"filtered": None, "tau_reason": reason, "n": G.n, "m": G.m,
           "packs": res.feasible, "iters": res.iterations}
    if not res.feasible:
        # candidate counterexample: cross-verify everything
        rec["CANDIDATE"] = True
        rec["arcs"] = G.arcs
        rec["verdicts"] = cross_verify_candidate(G, k)
        rec["dicuts_used"] = [sorted(c) for c in res.dicuts_used]
    return rec


def run_liftings(base_name: str, limit: int | None, log):
    base = {"D1": schrijver_d1, "D2": cg_d2, "D3": cg_d3}[base_name]()
    stats = collections.Counter()
    seen = set()
    candidates = []
    t0 = time.time()
    for choices, G in enumerate_liftings(base, GADGETS, limit=limit):
        stats["generated"] += 1
        if G is None:
            stats["degenerate"] += 1
            continue
        key = G.canonical_key()
        if key in seen:
            stats["iso-dup"] += 1
            continue
        seen.add(key)
        rec = check_instance(G)
        if rec["filtered"]:
            stats["filter:" + rec["filtered"]] += 1
            continue
        stats["tested"] += 1
        if rec.get("CANDIDATE"):
            stats["CANDIDATES"] += 1
            candidates.append((choices, rec))
            log.write(json.dumps({"family": f"lift/{base_name}",
                                  "choices": choices, **rec}) + "\n")
            log.flush()
        elif rec["packs"]:
            stats["packs-ok"] += 1
    elapsed = time.time() - t0
    summary = {"family": f"lift/{base_name}", "elapsed_s": round(elapsed, 1),
               "stats": dict(stats)}
    log.write(json.dumps(summary) + "\n")
    print(json.dumps(summary, indent=2))
    for choices, rec in candidates:
        print("CANDIDATE:", choices, rec["verdicts"])
    return candidates


def run_random(n: int, count: int, seed: int, log):
    rng = random.Random(seed)
    stats = collections.Counter()
    seen = set()
    candidates = []
    t0 = time.time()
    for _ in range(count):
        stats["generated"] += 1
        G = random_structured_dag(n, rng, p_arc=rng.uniform(0.12, 0.4))
        if G is None:
            stats["degenerate"] += 1
            continue
        key = G.canonical_key()
        if key in seen:
            stats["iso-dup"] += 1
            continue
        seen.add(key)
        rec = check_instance(G)
        if rec["filtered"]:
            stats["filter:" + rec["filtered"]] += 1
            continue
        stats["tested"] += 1
        if rec.get("CANDIDATE"):
            stats["CANDIDATES"] += 1
            candidates.append(rec)
            log.write(json.dumps({"family": f"random(n={n})", **rec}) + "\n")
            log.flush()
        elif rec["packs"]:
            stats["packs-ok"] += 1
    elapsed = time.time() - t0
    summary = {"family": f"random(n={n},seed={seed})",
               "elapsed_s": round(elapsed, 1), "stats": dict(stats)}
    log.write(json.dumps(summary) + "\n")
    print(json.dumps(summary, indent=2))
    return candidates


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("liftings")
    p1.add_argument("--base", default="D1", choices=["D1", "D2", "D3"])
    p1.add_argument("--limit", type=int, default=None)
    p2 = sub.add_parser("random")
    p2.add_argument("--n", type=int, default=12)
    p2.add_argument("--count", type=int, default=2000)
    p2.add_argument("--seed", type=int, default=163)
    args = ap.parse_args(argv)

    RUNS.mkdir(exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    logpath = RUNS / f"{args.cmd}-{stamp}.jsonl"
    with open(logpath, "w") as log:
        if args.cmd == "liftings":
            run_liftings(args.base, args.limit, log)
        else:
            run_random(args.n, args.count, args.seed, log)
    print(f"log: {logpath}", file=sys.stderr)


if __name__ == "__main__":
    main()
