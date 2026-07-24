"""CEGAR dijoin-packing verifier.

Question answered: does (D, u) admit k pairwise u-disjoint dijoins?
(u in {0,1}: null arcs may appear in no dijoin, active arcs in at most one.)

Loop (as specified in claude-workspace#163):
  1. Maintain a working set C of dicuts (init: principal dicuts).
  2. Solve: vars x[arc][color], color in {1..k} on active arcs; at-most-one
     color per arc; for each dicut in C and each color, some active arc of
     the dicut gets that color.
  3. SAT -> check each color class is a real dijoin (reversal + strong
     connectivity). All real: packing found. Otherwise extract violated
     dicuts for each failing class, add to C, loop.
  4. UNSAT -> no k-packing; C is a certificate (a set of dicuts that cannot
     be simultaneously k-covered by disjoint classes).

Two independent solver backends (cross-check any interesting verdict):
  - 'cpsat'  : OR-tools CP-SAT
  - 'pysat'  : python-sat (CaDiCaL 1.9.5, name 'cd19')
Plus solve_full(): one-shot solve against ALL dicuts (no CEGAR), viable on
small instances; used as an independent formulation in calibration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .digraph import Digraph


@dataclass
class PackResult:
    feasible: bool
    k: int
    solver: str
    packing: Optional[list[list[int]]] = None      # k lists of arc indices
    dicuts_used: list[frozenset[int]] = field(default_factory=list)
    iterations: int = 0
    note: str = ""

    def packing_labels(self, D: Digraph) -> list[list[str]]:
        assert self.packing is not None
        return [[D.arc_label(i) for i in cls] for cls in self.packing]


class _CpSatBackend:
    name = "cpsat"

    def solve(self, D: Digraph, k: int, dicuts: list[frozenset[int]]):
        from ortools.sat.python import cp_model
        model = cp_model.CpModel()
        x = {}
        for a in D.active:
            for c in range(k):
                x[a, c] = model.NewBoolVar(f"x_{a}_{c}")
            model.AddAtMostOne(x[a, c] for c in range(k))
        for cut in dicuts:
            act = [a for a in cut if D.caps[a] == 1]
            if len(act) < k:
                return None  # trivially UNSAT: some dicut has < k active arcs
            for c in range(k):
                model.AddBoolOr([x[a, c] for a in act])
        solver = cp_model.CpSolver()
        solver.parameters.num_search_workers = 4
        status = solver.Solve(model)
        if status == cp_model.INFEASIBLE:
            return None
        if status != cp_model.OPTIMAL and status != cp_model.FEASIBLE:
            raise RuntimeError(f"cpsat status {status}")
        classes = [[] for _ in range(k)]
        for a in D.active:
            for c in range(k):
                if solver.Value(x[a, c]):
                    classes[c].append(a)
        return classes


class _PySatBackend:
    name = "pysat"

    def solve(self, D: Digraph, k: int, dicuts: list[frozenset[int]]):
        from pysat.solvers import Solver
        # var id for (arc a, color c): 1 + idx(a)*k + c
        aidx = {a: i for i, a in enumerate(D.active)}
        def var(a, c):
            return 1 + aidx[a] * k + c
        cnf = []
        for a in D.active:
            for c1 in range(k):
                for c2 in range(c1 + 1, k):
                    cnf.append([-var(a, c1), -var(a, c2)])
        for cut in dicuts:
            act = [a for a in cut if D.caps[a] == 1]
            if len(act) < k:
                return None
            for c in range(k):
                cnf.append([var(a, c) for a in act])
        with Solver(name="cd19", bootstrap_with=cnf) as s:
            if not s.solve():
                return None
            model = set(l for l in s.get_model() if l > 0)
        classes = [[] for _ in range(k)]
        for a in D.active:
            for c in range(k):
                if var(a, c) in model:
                    classes[c].append(a)
        return classes


_BACKENDS = {"cpsat": _CpSatBackend(), "pysat": _PySatBackend()}


def pack(D: Digraph, k: int, solver: str = "cpsat",
         max_iters: int = 10000) -> PackResult:
    """CEGAR loop: k disjoint dijoins in (D, caps)?"""
    backend = _BACKENDS[solver]
    dicuts = D.principal_dicuts()
    seen = set(dicuts)
    for it in range(1, max_iters + 1):
        classes = backend.solve(D, k, dicuts)
        if classes is None:
            return PackResult(False, k, solver, None, list(dicuts), it,
                              "UNSAT over working dicut set")
        bad = False
        for cls in classes:
            if not D.is_dijoin(cls):
                bad = True
                for cut in D.violated_dicuts(cls):
                    if cut not in seen:
                        seen.add(cut)
                        dicuts.append(cut)
        if not bad:
            return PackResult(True, k, solver, classes, list(dicuts), it)
    raise RuntimeError(f"CEGAR did not converge in {max_iters} iterations")


def solve_full(D: Digraph, k: int, solver: str = "cpsat") -> PackResult:
    """One-shot solve against ALL dicuts (no CEGAR). Exponential dicut count;
    only for small instances. Independent formulation for cross-checking."""
    backend = _BACKENDS[solver]
    dicuts = D.all_dicuts()
    classes = backend.solve(D, k, dicuts)
    if classes is None:
        return PackResult(False, k, solver + "+full", None, dicuts, 1,
                          "UNSAT over full dicut enumeration")
    # classes cover every dicut by construction; sanity-check anyway
    for cls in classes:
        if not D.is_dijoin(cls):
            raise AssertionError("full-enumeration packing class is not a dijoin "
                                 "(dicut enumeration is broken)")
    return PackResult(True, k, solver + "+full", classes, dicuts, 1)


def nu(D: Digraph, solver: str = "cpsat", k_max: Optional[int] = None) -> int:
    """Exact packing number: largest k with a feasible k-packing.

    nu <= tau (Lucchesi-Younger), so the search is bounded by tau.
    """
    tau_val, _ = D.tau()
    hi = tau_val if k_max is None else min(k_max, tau_val)
    best = 0
    for k in range(1, hi + 1):
        if pack(D, k, solver=solver).feasible:
            best = k
        else:
            break
    return best


def cross_verify_candidate(D: Digraph, k: int) -> dict:
    """For a claimed nu < k candidate: run every backend and the full
    enumeration (when feasible) and report all verdicts."""
    verdicts = {}
    for name in _BACKENDS:
        verdicts[f"cegar/{name}"] = pack(D, k, solver=name).feasible
    if D.n <= 22:
        verdicts["full/cpsat"] = solve_full(D, k, solver="cpsat").feasible
        verdicts["full/pysat"] = solve_full(D, k, solver="pysat").feasible
    return verdicts
