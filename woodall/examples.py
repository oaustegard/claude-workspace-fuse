"""Known Edmonds-Giles counterexamples, transcribed from primary sources.

Sources:
- (D1, u1): Schrijver, "A counterexample to a conjecture of Edmonds and
  Giles", Discrete Math 32 (1980) 213-214; transcribed from Figure 6 of
  Feofiloff's survey (ime.usp.br/~pf/dijoins/woodall/survey1-en.pdf), read
  at 300dpi, cross-checked against the survey's Fact 7.1 proof structure
  (three active paths a-b-c / d-e-f / g-h-i, four critical cuts) and the
  four "special joins" {a,c,d,f,h}, {d,f,g,i,b}, {g,i,a,c,e}, {b,h,e} of
  survey section 7.1 (each must be a dijoin; each active arc in exactly two).
- ring(i): the survey's Figure 8 generalization — D1 is ring(3); odd i >= 3
  are counterexamples, even i are not.
- (D2, u2), (D3, u3): Cornuejols-Guenin, "Note on dijoins", Discrete Math
  243 (2002) 213-216; transcribed from Figures 9/10 of the survey (400dpi).
  D2 uses the survey's vertex numbering 1..14. Consistency anchors: Williams'
  observation that D2 minus arc 14->8 is still a counterexample (the arc must
  exist), and D3's arc set is invariant under the automorphism
  (TM M2)(TL R2)(TR L2)(ML MR).

Calibration (tests/test_calibration.py) is the arbiter of these
transcriptions: each must yield nu = 1, tau = 2, and D1's four special joins
must all be dijoins. Do not edit an arc list without re-running calibration.
"""

from __future__ import annotations

from .digraph import Digraph


def ring(i: int) -> Digraph:
    """Schrijver-style capacitated ring of length 2i (Figure 8). ring(3) == D1.

    Per sector k (indices mod i), vertices: source S_k, outer dot T_k,
    inner dot m_k, inner sink s_k.
    Active arcs: S_k->T_{k-1}, S_k->s_k, m_k->s_{k-1}.
    Null arcs:   S_k->T_k, S_k->m_k, T_k->s_k, m_k->s_k.
    """
    if i < 2:
        raise ValueError("ring needs i >= 2")
    S = lambda k: 4 * (k % i) + 0
    T = lambda k: 4 * (k % i) + 1
    m = lambda k: 4 * (k % i) + 2
    s = lambda k: 4 * (k % i) + 3
    arcs, caps = [], []
    for k in range(i):
        arcs += [(S(k), T(k - 1)), (S(k), s(k)), (m(k), s(k - 1))]
        caps += [1, 1, 1]
        arcs += [(S(k), T(k)), (S(k), m(k)), (T(k), s(k)), (m(k), s(k))]
        caps += [0, 0, 0, 0]
    names = []
    for k in range(i):
        names += [f"S{k}", f"T{k}", f"m{k}", f"s{k}"]
    return Digraph(4 * i, arcs, caps, name=f"ring({i})", vnames=names)


def schrijver_d1() -> Digraph:
    """(D1, u1): 12 vertices, 9 active + 12 null arcs.

    Vertex layout from Figure 6 (outer hexagon TL,TR,R,BR,BL,L; inner hexagon
    iTL,iTR,iR,iBR,iBL,iL). Sources: TR, L, BR. Sinks: iTL, iR, iBL.
    Active paths: R-TR-iTL-iL (a,b,c), TL-L-iBL-iBR (d,e,f),
    BL-BR-iR-iTR (g,h,i).
    """
    V = ["TL", "TR", "R", "BR", "BL", "L", "iTL", "iTR", "iR", "iBR", "iBL", "iL"]
    ix = {v: k for k, v in enumerate(V)}
    active = [
        ("TR", "R"),      # a
        ("TR", "iTL"),    # b
        ("iL", "iTL"),    # c
        ("L", "TL"),      # d
        ("L", "iBL"),     # e
        ("iBR", "iBL"),   # f
        ("BR", "BL"),     # g
        ("BR", "iR"),     # h
        ("iTR", "iR"),    # i
    ]
    null = [
        ("TR", "TL"), ("L", "BL"), ("BR", "R"),          # outer ring, null
        ("TL", "iTL"), ("BL", "iBL"), ("R", "iR"),       # outer dot -> inner sink
        ("TR", "iTR"), ("L", "iL"), ("BR", "iBR"),       # source -> inner dot
        ("iTR", "iTL"), ("iL", "iBL"), ("iBR", "iR"),    # inner ring, null
    ]
    arcs = [(ix[u], ix[v]) for (u, v) in active + null]
    caps = [1] * len(active) + [0] * len(null)
    return Digraph(len(V), arcs, caps, name="D1", vnames=V)


D1_ARC_LETTERS = {"a": 0, "b": 1, "c": 2, "d": 3, "e": 4, "f": 5, "g": 6, "h": 7, "i": 8}

# The four "special joins" of survey section 7.1 (weight-1/2 fractional
# packing): every one must be a dijoin of D1; every active arc lies in
# exactly two of them.
D1_SPECIAL_JOINS = [
    ["a", "c", "d", "f", "h"],
    ["d", "f", "g", "i", "b"],
    ["g", "i", "a", "c", "e"],
    ["b", "h", "e"],
]


def cg_d2() -> Digraph:
    """(D2, u2): 14 vertices, 11 active + 14 null arcs (survey Figure 9,
    right drawing; vertex names are the figure's numbers).

    Sources: 3, 7, 11, 13. Sinks: 2, 6, 8, 12.
    Active paths: 9-8-7-6-5, 1-2-3-4, 10-11-12-13-14.
    """
    V = [str(i) for i in range(1, 15)]
    ix = {v: k for k, v in enumerate(V)}
    active = [
        ("9", "8"), ("7", "8"), ("7", "6"), ("5", "6"),
        ("1", "2"), ("3", "2"), ("3", "4"),
        ("11", "10"), ("11", "12"), ("13", "12"), ("13", "14"),
    ]
    null = [
        ("1", "8"), ("14", "8"),
        ("7", "14"),
        ("5", "2"), ("10", "2"),
        ("14", "6"), ("4", "6"),
        ("11", "1"), ("11", "9"),
        ("3", "5"), ("3", "10"),
        ("9", "12"),
        ("13", "9"), ("13", "4"),
    ]
    arcs = [(ix[u], ix[v]) for (u, v) in active + null]
    caps = [1] * len(active) + [0] * len(null)
    return Digraph(len(V), arcs, caps, name="D2", vnames=V)


def williams_d2_prime() -> Digraph:
    """D2 minus the null arc 14->8 (Williams 2004): still a counterexample,
    and included in D2 — used as an extra calibration point."""
    D = cg_d2()
    keep = [(a, c) for a, c in zip(D.arcs, D.caps)
            if not (D.vnames[a[0]] == "14" and D.vnames[a[1]] == "8")]
    if len(keep) != D.m - 1:
        raise AssertionError("arc 14->8 not found in D2")
    arcs = [a for a, _ in keep]
    caps = [c for _, c in keep]
    return Digraph(D.n, arcs, caps, name="D2'", vnames=D.vnames)


def cg_d3() -> Digraph:
    """(D3, u3): 13 vertices, 10 active + 14 null arcs (survey Figure 10).

    Sources: C, BL, BR. Sinks: TL, TR, L2, R2.
    Active paths: TM-TL-BL-R2-M2, MR-TR-BR-L2-ML, BL2-C-BR2.
    Arc set is invariant under (TM M2)(TL R2)(TR L2)(ML MR).
    """
    V = ["TL", "TM", "TR", "ML", "C", "MR", "L2", "M2", "R2", "BL2", "BR2", "BL", "BR"]
    ix = {v: k for k, v in enumerate(V)}
    active = [
        ("TM", "TL"), ("BL", "TL"), ("BL", "R2"), ("M2", "R2"),
        ("MR", "TR"), ("BR", "TR"), ("BR", "L2"), ("ML", "L2"),
        ("C", "BL2"), ("C", "BR2"),
    ]
    null = [
        ("TM", "TR"), ("M2", "L2"),
        ("ML", "TL"), ("MR", "R2"),
        ("C", "TM"), ("C", "M2"), ("C", "ML"), ("C", "MR"),
        ("BL2", "TL"), ("BL2", "R2"),
        ("BR2", "TR"), ("BR2", "L2"),
        ("BL", "BL2"), ("BR", "BR2"),
    ]
    arcs = [(ix[u], ix[v]) for (u, v) in active + null]
    caps = [1] * len(active) + [0] * len(null)
    return Digraph(len(V), arcs, caps, name="D3", vnames=V)
