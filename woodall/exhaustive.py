"""Exhaustive verification of Woodall's conjecture (tau=3 case) over ALL
simple DAGs with n <= N_MAX vertices.

Every DAG admits a topological labeling, so enumerating all upper-triangular
adjacency codes (arcs i->j only for i<j) covers every isomorphism class
(with repetition — we test rather than dedupe, so a canonical-key collision
can never silently drop an instance).

Cheap necessary conditions for tau >= 3 prune before the exact tau:
  - weakly connected, >= 2 sources, >= 2 sinks
  - every source has out-degree >= 3, every sink in-degree >= 3
    (principal dicuts)
  - NOT source-sink-connected (Schrijver/Feofiloff-Younger: else good)

Usage: python3 -m woodall.exhaustive [N_MAX]   (default 7)
"""

from __future__ import annotations

import json
import pathlib
import sys
import time

from .digraph import Digraph
from .pack import pack, cross_verify_candidate

RUNS = pathlib.Path(__file__).parent / "runs"


def scan_n(n: int, log, start: int = 0, end: int | None = None) -> dict:
    npairs = n * (n - 1) // 2
    pairs = [(i, j) for i in range(n) for j in range(i + 1, n)]
    stats = {"codes": 0, "connected": 0, "degree_ok": 0, "not_ssc": 0,
             "tau_ge_3": 0, "packs": 0, "CANDIDATES": 0}
    t0 = time.time()
    if end is None:
        end = 1 << npairs
    for code in range(start, end):
        stats["codes"] += 1
        out = [0] * n     # bitmask of out-neighbours
        inn = [0] * n
        c = code
        for k in range(npairs):
            if (c >> k) & 1:
                i, j = pairs[k]
                out[i] |= 1 << j
                inn[j] |= 1 << i
        # weak connectivity via bitmask BFS
        seen = 1
        frontier = 1
        while frontier:
            nxt = 0
            for v in range(n):
                if (frontier >> v) & 1:
                    nxt |= out[v] | inn[v]
            frontier = nxt & ~seen
            seen |= nxt
        if seen != (1 << n) - 1:
            continue
        stats["connected"] += 1
        sources = [v for v in range(n) if inn[v] == 0]
        sinks = [v for v in range(n) if out[v] == 0]
        if len(sources) < 2 or len(sinks) < 2:
            continue
        if any(bin(out[s]).count("1") < 3 for s in sources):
            continue
        if any(bin(inn[t]).count("1") < 3 for t in sinks):
            continue
        stats["degree_ok"] += 1
        # source-sink-connectivity (proven-good class)
        sink_mask = 0
        for t in sinks:
            sink_mask |= 1 << t
        ssc = True
        for s in sources:
            reach = 1 << s
            frontier = reach
            while frontier:
                nxt = 0
                for v in range(n):
                    if (frontier >> v) & 1:
                        nxt |= out[v]
                frontier = nxt & ~reach
                reach |= nxt
            if reach & sink_mask != sink_mask:
                ssc = False
                break
        if ssc:
            continue
        stats["not_ssc"] += 1
        arcs = [(i, j) for k, (i, j) in enumerate(pairs) if (code >> k) & 1]
        G = Digraph(n, arcs, name=f"exh(n={n},code={code})")
        tau, _ = G.tau()
        if tau < 3:
            continue
        stats["tau_ge_3"] += 1
        res = pack(G, 3, solver="cpsat")
        if res.feasible:
            stats["packs"] += 1
        else:
            stats["CANDIDATES"] += 1
            rec = {"n": n, "code": code, "arcs": arcs,
                   "verdicts": cross_verify_candidate(G, 3)}
            log.write(json.dumps({"CANDIDATE": True, **rec}) + "\n")
            log.flush()
            print("CANDIDATE:", rec)
    summary = {"family": f"exhaustive(n={n})", "range": [start, end],
               "elapsed_s": round(time.time() - t0, 1), "stats": stats}
    log.write(json.dumps(summary) + "\n")
    print(json.dumps(summary))
    return summary


def main():
    # usage: exhaustive.py N_MAX            — scan n=4..N_MAX fully
    #        exhaustive.py N chunk/nchunks  — scan one code-range chunk of n=N
    n_max = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    RUNS.mkdir(exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    if len(sys.argv) > 2:
        chunk, nchunks = map(int, sys.argv[2].split("/"))
        npairs = n_max * (n_max - 1) // 2
        total = 1 << npairs
        start = total * chunk // nchunks
        end = total * (chunk + 1) // nchunks
        with open(RUNS / f"exhaustive-n{n_max}-chunk{chunk}of{nchunks}.jsonl", "w") as log:
            scan_n(n_max, log, start, end)
        return
    with open(RUNS / f"exhaustive-{stamp}.jsonl", "w") as log:
        for n in range(4, n_max + 1):
            scan_n(n, log)


if __name__ == "__main__":
    main()
