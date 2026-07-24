"""Calibration gates from claude-workspace#163 — ALL must pass before any
search result is trusted.

Run: python3 -m pytest woodall/tests/ -v
"""

import random

import pytest

from woodall.brute import brute_nu
from woodall.digraph import Digraph
from woodall.examples import (D1_ARC_LETTERS, D1_SPECIAL_JOINS, cg_d2, cg_d3,
                              ring, schrijver_d1, williams_d2_prime)
from woodall.generator import random_structured_dag
from woodall.pack import nu, pack, solve_full


# ---------- Gate 1: Fact 7.1 (Schrijver) ----------

class TestSchrijverD1:
    def setup_method(self):
        self.D = schrijver_d1()

    def test_shape(self):
        assert self.D.is_dag()
        assert self.D.weakly_connected()
        assert not self.D.source_sink_connected()
        assert sorted(self.D.vnames[v] for v in self.D.sources()) == ["BR", "L", "TR"]
        assert sorted(self.D.vnames[v] for v in self.D.sinks()) == ["iBL", "iR", "iTL"]

    def test_fact_7_1(self):
        tau, _ = self.D.tau()
        assert tau == 2
        assert nu(self.D) == 1
        assert nu(self.D, solver="pysat") == 1

    def test_special_joins_are_dijoins(self):
        # survey section 7.1: the four weight-1/2 joins of the fractional
        # packing; each active arc lies in exactly two of them
        count = {a: 0 for a in D1_ARC_LETTERS}
        for js in D1_SPECIAL_JOINS:
            assert self.D.is_dijoin([D1_ARC_LETTERS[x] for x in js])
            for x in js:
                count[x] += 1
        assert all(c == 2 for c in count.values())

    def test_full_enumeration_agrees(self):
        assert solve_full(self.D, 1).feasible
        assert not solve_full(self.D, 2).feasible
        assert not solve_full(self.D, 2, solver="pysat").feasible

    def test_d1_equals_ring3(self):
        assert self.D.canonical_key() == ring(3).canonical_key()


# ---------- Gate 2: Facts 8.1 / 8.2 (Cornuejols-Guenin) ----------

@pytest.mark.parametrize("factory", [cg_d2, cg_d3, williams_d2_prime])
def test_cornuejols_guenin(factory):
    D = factory()
    assert D.is_dag()
    assert D.weakly_connected()
    assert not D.source_sink_connected()
    tau, _ = D.tau()
    assert tau == 2
    assert nu(D) == 1
    assert not pack(D, 2, solver="pysat").feasible
    assert not solve_full(D, 2).feasible


def test_d3_advertised_symmetry():
    # the transcription's consistency anchor: (TM M2)(TL R2)(TR L2)(ML MR)
    D = cg_d3()
    ix = {v: k for k, v in enumerate(D.vnames)}
    perm = {ix[a]: ix[b] for a, b in
            [("TM", "M2"), ("M2", "TM"), ("TL", "R2"), ("R2", "TL"),
             ("TR", "L2"), ("L2", "TR"), ("ML", "MR"), ("MR", "ML")]}
    mapped = sorted(((perm.get(u, u), perm.get(v, v)), c)
                    for (u, v), c in zip(D.arcs, D.caps))
    orig = sorted(((u, v), c) for (u, v), c in zip(D.arcs, D.caps))
    assert mapped == orig


# ---------- Gate 3: ring generalizations ----------

@pytest.mark.parametrize("i,expect_counterexample",
                         [(3, True), (4, False), (5, True), (6, False), (7, True)])
def test_rings(i, expect_counterexample):
    D = ring(i)
    tau, _ = D.tau()
    assert tau == 2
    packs2 = pack(D, 2).feasible
    assert packs2 == (not expect_counterexample)


# ---------- Gate 4: random small DAGs vs brute force ----------

def test_random_small_dags_agree_with_brute_force():
    rng = random.Random(163)
    tested = 0
    for _ in range(300):
        n = rng.randint(4, 8)
        G = random_structured_dag(n, rng, p_arc=rng.uniform(0.2, 0.6))
        if G is None or not G.is_dag():
            continue
        tau, _ = G.tau()
        if tau > 4:
            continue
        nv_cegar = nu(G)
        nv_pysat = nu(G, solver="pysat")
        nv_brute = brute_nu(G)
        assert nv_cegar == nv_brute == nv_pysat, \
            f"disagreement on {G.arcs}: cegar={nv_cegar} pysat={nv_pysat} brute={nv_brute}"
        # conjecture-consistency: uncapacitated small DAGs should all
        # achieve nu == tau (a violation here would itself be a discovery,
        # caught as a test failure and escalated)
        assert nv_cegar == tau, f"nu<tau on small DAG {G.arcs}!"
        tested += 1
    assert tested >= 100


# ---------- verifier internals ----------

def test_dijoin_reversal_characterisation_against_definition():
    # J is a dijoin iff it meets every dicut: check the reversal shortcut
    # against the definitional test on a few small digraphs
    rng = random.Random(7)
    checked = 0
    for _ in range(50):
        G = random_structured_dag(rng.randint(4, 7), rng, p_arc=0.4)
        if G is None:
            continue
        dicuts = G.all_dicuts()
        for _ in range(10):
            J = [a for a in range(G.m) if rng.random() < 0.4]
            definitional = all(set(J) & set(c) for c in dicuts)
            assert G.is_dijoin(J) == definitional
            checked += 1
    assert checked > 100


def test_tau_capacitated_semantics():
    # a null arc contributes 0 to a dicut's capacity
    G = Digraph(3, [(0, 1), (0, 2), (1, 2)], caps=[0, 1, 1])
    tau, _ = G.tau()
    assert tau == 1  # dicut {0}: arcs 0->1 (cap 0) + 0->2 (cap 1)
