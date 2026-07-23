"""Brute-force exact packing number for tiny instances.

Independent of the SAT machinery: enumerates ALL dicuts explicitly, then
backtracks over color assignments of active arcs with incremental dicut
coverage pruning. Only for sanity gates (n <= ~10, few active arcs).
"""

from __future__ import annotations

from .digraph import Digraph


def brute_pack(D: Digraph, k: int) -> bool:
    """Exhaustive: is there a k-packing of dijoins? (active arcs only)"""
    dicuts = [frozenset(a for a in cut if D.caps[a] == 1)
              for cut in D.all_dicuts()]
    if any(len(c) < k for c in dicuts):
        return False
    arcs = sorted(D.active,
                  key=lambda a: -sum(1 for c in dicuts if a in c))
    ncut = len(dicuts)
    cut_ids = {a: [j for j in range(ncut) if a in dicuts[j]] for a in arcs}
    # need[j][c] true while dicut j not yet covered in color c
    covered = [[0] * k for _ in range(ncut)]
    # remaining[j] = active arcs of dicut j not yet assigned
    remaining = [len(dicuts[j]) for j in range(ncut)]

    def rec(pos: int) -> bool:
        if pos == len(arcs):
            return all(all(covered[j][c] for c in range(k)) for j in range(ncut))
        # prune: some dicut cannot reach full coverage anymore
        for j in range(ncut):
            missing = sum(1 for c in range(k) if not covered[j][c])
            if missing > remaining[j]:
                return False
        a = arcs[pos]
        js = cut_ids[a]
        for choice in range(k + 1):   # colors 1..k then unused (0)
            if choice < k:
                for j in js:
                    covered[j][choice] += 1
                    remaining[j] -= 1
                if rec(pos + 1):
                    for j in js:
                        covered[j][choice] -= 1
                        remaining[j] += 1
                    return True
                for j in js:
                    covered[j][choice] -= 1
                    remaining[j] += 1
            else:
                for j in js:
                    remaining[j] -= 1
                if rec(pos + 1):
                    for j in js:
                        remaining[j] += 1
                    return True
                for j in js:
                    remaining[j] += 1
        return False

    return rec(0)


def brute_nu(D: Digraph, k_max: int | None = None) -> int:
    tau_val, _ = D.tau()
    hi = tau_val if k_max is None else min(k_max, tau_val)
    best = 0
    for k in range(1, hi + 1):
        if brute_pack(D, k):
            best = k
        else:
            break
    return best
