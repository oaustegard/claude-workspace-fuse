"""Core digraph machinery for the Woodall/Edmonds-Giles counterexample search.

Conventions
-----------
- Vertices are 0..n-1. Arcs are (tail, head) pairs stored in a list; an arc's
  identity is its index in that list (parallel arcs allowed).
- Capacities: caps[i] in {0, 1}. cap 0 = "null arc" (Edmonds-Giles), cap 1 =
  "active arc". The uncapacitated (Woodall) case is caps == all ones.
- A set S of vertices is *closed* if no arc enters it (every arc with head in
  S has its tail in S). For a proper nonempty closed S in a weakly connected
  digraph, delta_out(S) is nonempty and is a *dicut*.
- A *dijoin* is an arc set J meeting every dicut; equivalently, adding the
  reversals of J's arcs makes the digraph strongly connected.

Sets of vertices are represented as int bitmasks throughout.
"""

from __future__ import annotations

from typing import Iterator, Optional, Sequence


class Digraph:
    """Immutable-ish digraph with {0,1} arc capacities."""

    def __init__(self, n: int, arcs: Sequence[tuple[int, int]],
                 caps: Optional[Sequence[int]] = None,
                 name: str = "", vnames: Optional[Sequence[str]] = None):
        self.n = n
        self.arcs = [(int(u), int(v)) for (u, v) in arcs]
        self.m = len(self.arcs)
        self.caps = list(caps) if caps is not None else [1] * self.m
        if len(self.caps) != self.m:
            raise ValueError("caps length != number of arcs")
        if any(c not in (0, 1) for c in self.caps):
            raise ValueError("only {0,1} capacities supported")
        for (u, v) in self.arcs:
            if not (0 <= u < n and 0 <= v < n):
                raise ValueError(f"arc ({u},{v}) out of range for n={n}")
            if u == v:
                raise ValueError("self-loops not allowed")
        self.name = name
        self.vnames = list(vnames) if vnames is not None else [str(i) for i in range(n)]
        # adjacency
        self.out = [[] for _ in range(n)]   # vertex -> list of arc indices
        self.inn = [[] for _ in range(n)]
        for i, (u, v) in enumerate(self.arcs):
            self.out[u].append(i)
            self.inn[v].append(i)
        self.active = [i for i in range(self.m) if self.caps[i] == 1]

    # ---------- basic structure ----------

    def arc_label(self, i: int) -> str:
        u, v = self.arcs[i]
        return f"{self.vnames[u]}->{self.vnames[v]}"

    def is_dag(self) -> bool:
        indeg = [0] * self.n
        for (_, v) in self.arcs:
            indeg[v] += 1
        stack = [v for v in range(self.n) if indeg[v] == 0]
        seen = 0
        while stack:
            v = stack.pop()
            seen += 1
            for i in self.out[v]:
                w = self.arcs[i][1]
                indeg[w] -= 1
                if indeg[w] == 0:
                    stack.append(w)
        return seen == self.n

    def weakly_connected(self) -> bool:
        if self.n == 0:
            return True
        adj = [[] for _ in range(self.n)]
        for (u, v) in self.arcs:
            adj[u].append(v)
            adj[v].append(u)
        seen = {0}
        stack = [0]
        while stack:
            v = stack.pop()
            for w in adj[v]:
                if w not in seen:
                    seen.add(w)
                    stack.append(w)
        return len(seen) == self.n

    def sources(self) -> list[int]:
        return [v for v in range(self.n) if not self.inn[v]]

    def sinks(self) -> list[int]:
        return [v for v in range(self.n) if not self.out[v]]

    def topo_order(self) -> list[int]:
        indeg = [len(self.inn[v]) for v in range(self.n)]
        stack = [v for v in range(self.n) if indeg[v] == 0]
        order = []
        while stack:
            v = stack.pop()
            order.append(v)
            for i in self.out[v]:
                w = self.arcs[i][1]
                indeg[w] -= 1
                if indeg[w] == 0:
                    stack.append(w)
        if len(order) != self.n:
            raise ValueError("not a DAG")
        return order

    # ---------- reachability / filters ----------

    def _reach_from(self, v: int, adj: list[list[int]]) -> set[int]:
        seen = {v}
        stack = [v]
        while stack:
            x = stack.pop()
            for y in adj[x]:
                if y not in seen:
                    seen.add(y)
                    stack.append(y)
        return seen

    def source_sink_connected(self) -> bool:
        """True iff every source vertex reaches every sink vertex.

        Schrijver 1982 / Feofiloff-Younger 1987: such DAGs satisfy
        Edmonds-Giles (hence Woodall). Any counterexample must FAIL this.
        """
        adj = [[self.arcs[i][1] for i in self.out[v]] for v in range(self.n)]
        sinks = set(self.sinks())
        for s in self.sources():
            if not sinks <= self._reach_from(s, adj):
                return False
        return True

    # ---------- SCC / strong connectivity (iterative Tarjan) ----------

    @staticmethod
    def _scc(n: int, adj: list[list[int]]) -> list[int]:
        """Return comp[] labels, components numbered in reverse topological
        order of the condensation (comp 0 has no arcs into it... not
        guaranteed; use condensation() for structure)."""
        index = [-1] * n
        low = [0] * n
        oncur = [False] * n
        cur = []
        comp = [-1] * n
        counter = [0]
        ncomp = [0]
        for root in range(n):
            if index[root] != -1:
                continue
            stack = [(root, 0)]
            while stack:
                v, pi = stack[-1]
                if pi == 0:
                    index[v] = low[v] = counter[0]
                    counter[0] += 1
                    cur.append(v)
                    oncur[v] = True
                advanced = False
                while pi < len(adj[v]):
                    w = adj[v][pi]
                    pi += 1
                    if index[w] == -1:
                        stack[-1] = (v, pi)
                        stack.append((w, 0))
                        advanced = True
                        break
                    elif oncur[w]:
                        low[v] = min(low[v], index[w])
                if advanced:
                    continue
                stack[-1] = (v, pi)
                if low[v] == index[v]:
                    while True:
                        w = cur.pop()
                        oncur[w] = False
                        comp[w] = ncomp[0]
                        if w == v:
                            break
                    ncomp[0] += 1
                stack.pop()
                if stack:
                    p = stack[-1][0]
                    low[p] = min(low[p], low[v])
        return comp

    def strongly_connected_with_reversals(self, rev_arcs: Sequence[int]) -> bool:
        """Is D + {reversals of the given arc indices} strongly connected?"""
        adj = [[] for _ in range(self.n)]
        for (u, v) in self.arcs:
            adj[u].append(v)
        for i in rev_arcs:
            u, v = self.arcs[i]
            adj[v].append(u)
        comp = self._scc(self.n, adj)
        return max(comp) == 0 if self.n else True

    def condensation_with_reversals(self, rev_arcs: Sequence[int]):
        """SCC condensation of D + reversals(rev_arcs).

        Returns (comp, comp_adj_out, ncomp) where comp_adj_out[c] is a set of
        component successors (in the augmented digraph).
        """
        adj = [[] for _ in range(self.n)]
        for (u, v) in self.arcs:
            adj[u].append(v)
        for i in rev_arcs:
            u, v = self.arcs[i]
            adj[v].append(u)
        comp = self._scc(self.n, adj)
        ncomp = max(comp) + 1
        cadj = [set() for _ in range(ncomp)]
        cin = [set() for _ in range(ncomp)]
        for u in range(self.n):
            for v in adj[u]:
                if comp[u] != comp[v]:
                    cadj[comp[u]].add(comp[v])
                    cin[comp[v]].add(comp[u])
        return comp, cadj, cin, ncomp

    # ---------- closed sets and dicuts ----------

    def closed_sets(self) -> Iterator[int]:
        """Yield all proper nonempty closed vertex sets as bitmasks.

        S is closed iff no arc enters S. Enumeration walks a topological
        order; a vertex may join S only if all its in-neighbours are in S.
        Runs in O(#closed_sets * degree) — fine for n <= ~24 on the DAGs we
        search (the count is what it is; calibration instances are tiny).
        """
        order = self.topo_order()
        n = self.n
        in_nbr_mask = [0] * n
        for v in range(n):
            for i in self.inn[v]:
                in_nbr_mask[v] |= (1 << self.arcs[i][0])
        full = (1 << n) - 1

        def rec(pos: int, S: int) -> Iterator[int]:
            if pos == n:
                if S != 0 and S != full:
                    yield S
                return
            v = order[pos]
            # v not in S
            yield from rec(pos + 1, S)
            # v in S, allowed only if closure holds
            if in_nbr_mask[v] & ~S == 0:
                yield from rec(pos + 1, S | (1 << v))

        yield from rec(0, 0)

    def dicut_arcs(self, S: int) -> list[int]:
        """Arc indices leaving closed set S."""
        res = []
        for i, (u, v) in enumerate(self.arcs):
            if (S >> u) & 1 and not (S >> v) & 1:
                res.append(i)
        return res

    def tau(self) -> tuple[int, Optional[int]]:
        """Capacitated min dicut: (min over dicuts of cap(delta_out(S)), argmin S).

        Requires weak connectivity (so delta_out(S) != empty for closed S).
        Returns (inf-like large, None) if there are no dicuts (strongly
        connected — impossible for a DAG with n >= 2).
        """
        best, argmin = None, None
        for S in self.closed_sets():
            c = 0
            for i, (u, v) in enumerate(self.arcs):
                if (S >> u) & 1 and not (S >> v) & 1:
                    c += self.caps[i]
            if best is None or c < best:
                best, argmin = c, S
        if best is None:
            return (1 << 30), None
        return best, argmin

    def all_dicuts(self) -> list[frozenset[int]]:
        """All dicuts as frozensets of arc indices (deduped; different closed
        sets can induce the same arc set)."""
        seen = set()
        for S in self.closed_sets():
            fs = frozenset(self.dicut_arcs(S))
            seen.add(fs)
        return list(seen)

    def principal_dicuts(self) -> list[frozenset[int]]:
        """Initial dicut pool for CEGAR: dicuts of ancestor-closures of single
        vertices and complements of descendant-closures."""
        out_adj = [[self.arcs[i][1] for i in self.out[v]] for v in range(self.n)]
        in_adj = [[self.arcs[i][0] for i in self.inn[v]] for v in range(self.n)]
        full = (1 << self.n) - 1
        pool = set()
        for v in range(self.n):
            anc = self._reach_from(v, in_adj)     # v and its ancestors: closed
            S = 0
            for x in anc:
                S |= 1 << x
            if S != full:
                pool.add(frozenset(self.dicut_arcs(S)))
            desc = self._reach_from(v, out_adj)   # complement of descendants: closed
            T = full
            for x in desc:
                T &= ~(1 << x)
            if T != 0:
                pool.add(frozenset(self.dicut_arcs(T)))
        pool.discard(frozenset())
        return list(pool)

    # ---------- dijoins ----------

    def is_dijoin(self, J: Sequence[int]) -> bool:
        """Is the arc-index set J a dijoin? (reversal characterisation)"""
        return self.strongly_connected_with_reversals(list(J))

    def violated_dicuts(self, J: Sequence[int]) -> list[frozenset[int]]:
        """Dicuts disjoint from J (nonempty iff J is not a dijoin).

        From the condensation of D + rev(J): every source component and every
        complement-of-sink-component is closed in D and its dicut avoids J.
        """
        comp, cadj, cin, ncomp = self.condensation_with_reversals(list(J))
        if ncomp == 1:
            return []
        res = set()
        full = (1 << self.n) - 1
        masks = [0] * ncomp
        for v in range(self.n):
            masks[comp[v]] |= 1 << v
        for c in range(ncomp):
            if not cin[c]:      # source component: closed
                res.add(frozenset(self.dicut_arcs(masks[c])))
            if not cadj[c]:     # sink component: complement is closed
                S = full & ~masks[c]
                if S:
                    res.add(frozenset(self.dicut_arcs(S)))
        res.discard(frozenset())
        return list(res)

    # ---------- misc ----------

    def contract_sccs(self) -> "Digraph":
        """Contract strongly connected components (drops intra-SCC arcs,
        keeps parallel arcs between components). WLOG step for the search."""
        adj = [[] for _ in range(self.n)]
        for (u, v) in self.arcs:
            adj[u].append(v)
        comp = self._scc(self.n, adj)
        ncomp = max(comp) + 1 if self.n else 0
        arcs, caps = [], []
        for i, (u, v) in enumerate(self.arcs):
            if comp[u] != comp[v]:
                arcs.append((comp[u], comp[v]))
                caps.append(self.caps[i])
        return Digraph(ncomp, arcs, caps, name=self.name + "/scc")

    def canonical_key(self) -> tuple:
        """Cheap isomorphism-invariant key (iterated degree refinement over
        (out-active, out-null, in-active, in-null) profiles). Not a full
        canonical form: collisions possible, so use for bucketing + confirm
        with exact check when it matters."""
        cols = [0] * self.n
        for _ in range(self.n.bit_length() + 2):
            sigs = []
            for v in range(self.n):
                oa = sorted((self.caps[i], cols[self.arcs[i][1]]) for i in self.out[v])
                ia = sorted((self.caps[i], cols[self.arcs[i][0]]) for i in self.inn[v])
                sigs.append((cols[v], tuple(oa), tuple(ia)))
            ranks = {s: r for r, s in enumerate(sorted(set(sigs)))}
            newcols = [ranks[s] for s in sigs]
            if newcols == cols:
                break
            cols = newcols
        edge_profile = sorted((cols[u], cols[v], self.caps[i])
                              for i, (u, v) in enumerate(self.arcs))
        return (self.n, self.m, tuple(sorted(cols)), tuple(edge_profile))
