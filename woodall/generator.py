"""Instance generators for the tau=3 counterexample search.

Families (issue #163 priority order):
1. Null-arc resolutions of D1/D2/D3: replace each null arc with an
   uncapacitated gadget (drop / keep / subdivide-1 / subdivide-2 / contract).
   Naive drop and keep are known-failing liftings but are kept in the grammar
   so their collapse is *measured*, not assumed.
2. Structure-guided random DAGs failing source-sink connectivity.

All generated instances are uncapacitated (caps all 1) after lifting.
"""

from __future__ import annotations

import itertools
import random
from typing import Iterator, Optional, Sequence

from .digraph import Digraph

GADGETS = ("drop", "keep", "sub1", "sub2", "contract")


def lift_null_arcs(D: Digraph, choices: Sequence[str]) -> Optional[Digraph]:
    """Apply one gadget per null arc of D; return uncapacitated digraph.

    choices[i] applies to the i-th null arc (order of D's arc list).
    'contract' merges endpoints (then SCC-contraction cleans any circuits);
    'sub1'/'sub2' subdivide with 1/2 fresh vertices (all pieces active);
    'keep' promotes the null arc to capacity 1; 'drop' deletes it.
    Returns None if the result degenerates (not weakly connected, or fewer
    than 2 vertices after contraction).
    """
    nulls = [i for i in range(D.m) if D.caps[i] == 0]
    if len(choices) != len(nulls):
        raise ValueError("one choice per null arc required")
    # union-find for contractions
    parent = list(range(D.n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    arcs: list[tuple[int, int]] = []
    extra = 0  # subdivision vertices appended after original ids
    new_vertex_arcs: list[tuple] = []  # (kind, u, v) resolved later
    for i in range(D.m):
        u, v = D.arcs[i]
        if D.caps[i] == 1:
            arcs.append((u, v))
    for i, ch in zip(nulls, choices):
        u, v = D.arcs[i]
        if ch == "drop":
            continue
        elif ch == "keep":
            arcs.append((u, v))
        elif ch == "sub1":
            w = D.n + extra
            extra += 1
            arcs.append((u, w))
            arcs.append((w, v))
        elif ch == "sub2":
            w1 = D.n + extra
            w2 = D.n + extra + 1
            extra += 2
            arcs.append((u, w1))
            arcs.append((w1, w2))
            arcs.append((w2, v))
        elif ch == "contract":
            ru, rv = find(u), find(v)
            if ru != rv:
                parent[max(ru, rv)] = min(ru, rv)
        else:
            raise ValueError(f"unknown gadget {ch}")
    # apply contractions / renumber
    total = D.n + extra
    rep = {}
    for x in range(total):
        r = find(x) if x < D.n else x
        rep.setdefault(r, len(rep))
    final_arcs = []
    for (u, v) in arcs:
        ru = rep[find(u)] if u < D.n else rep[u]
        rv = rep[find(v)] if v < D.n else rep[v]
        if ru != rv:
            final_arcs.append((ru, rv))
    n2 = len(rep)
    if n2 < 2 or not final_arcs:
        return None
    G = Digraph(n2, final_arcs, name=f"{D.name}/lift")
    G = G.contract_sccs()          # WLOG: kill circuits created by contraction
    if G.n < 2 or G.m == 0 or not G.weakly_connected():
        return None
    return G


def enumerate_liftings(D: Digraph, gadgets: Sequence[str] = GADGETS,
                       limit: Optional[int] = None,
                       rng: Optional[random.Random] = None) -> Iterator[tuple[tuple[str, ...], Optional[Digraph]]]:
    """Yield (choices, lifted digraph) over the gadget grammar.

    Exhaustive when len(gadgets)**#nulls <= limit (or limit is None);
    otherwise uniform random sampling without dedup (caller dedups by
    canonical_key)."""
    nulls = sum(1 for c in D.caps if c == 0)
    space = len(gadgets) ** nulls
    if limit is None or space <= limit:
        for choices in itertools.product(gadgets, repeat=nulls):
            yield choices, lift_null_arcs(D, choices)
    else:
        rng = rng or random.Random(163)
        for _ in range(limit):
            choices = tuple(rng.choice(gadgets) for _ in range(nulls))
            yield choices, lift_null_arcs(D, choices)


def random_structured_dag(n: int, rng: random.Random,
                          p_arc: float = 0.25) -> Optional[Digraph]:
    """Random DAG biased toward the counterexample-necessary shape:
    >= 2 sources, >= 2 sinks, and at least one source/sink pair with no
    directed path (checked by the caller via filters; this generator just
    makes layered sparse DAGs)."""
    if n < 6:
        return None
    order = list(range(n))
    rng.shuffle(order)
    arcs = []
    for ai in range(n):
        for bi in range(ai + 1, n):
            if rng.random() < p_arc:
                arcs.append((order[ai], order[bi]))
    if not arcs:
        return None
    G = Digraph(n, arcs, name=f"rand(n={n})")
    if not G.weakly_connected():
        return None
    return G


def passes_filters(G: Digraph, min_tau: int = 3) -> tuple[bool, str]:
    """Hard pruning filters from issue #163. Returns (passes, reason)."""
    if not G.is_dag():
        return False, "not-dag"
    if not G.weakly_connected():
        return False, "disconnected"
    if len(G.sources()) < 2:
        return False, "single-source"
    if len(G.sinks()) < 2:
        return False, "single-sink"
    if G.source_sink_connected():
        return False, "source-sink-connected"
    t, _ = G.tau()
    if t < min_tau:
        return False, f"tau={t}"
    return True, f"tau={t}"
