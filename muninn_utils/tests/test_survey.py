"""Survey invariants: the cover tiling, and extractive rendering.

No network — every test passes an explicit `memories` list.
"""
from muninn_utils.survey import cover, load, survey


def _corpus(n=1000):
    return [{"id": f"i{i}",
             "summary": f"memory number {i} about thing {i % 7}",
             "tags": [f"t{i % 5}", "2026-01-01"],
             "type": "experience",
             "priority": 1 if i % 37 == 0 else 0,
             "created_at": f"2026-{1 + i // 300:02d}-{1 + i % 28:02d}T00:00:00Z"}
            for i in range(n)]


def test_cover_is_a_tiling():
    for T in list(range(1, 200)) + [1000, 2509, 65536]:
        for b in (8, 50, 120, 208):
            c = cover(T, b)
            assert len(c) <= max(b, 0) or T <= b
            assert c[0][0] == 0 and c[-1][1] >= T
            assert all(c[i][1] == c[i + 1][0] for i in range(len(c) - 1))


def test_cover_blocks_are_aligned_powers_of_two():
    for T in (37, 300, 2509):
        for lo, hi in cover(T, 60):
            n = hi - lo
            assert n & (n - 1) == 0 and lo % n == 0


def test_detail_decays_with_age():
    c = cover(5000, 60)
    assert c[-1][1] - c[-1][0] == 1           # newest is verbatim
    assert c[0][1] - c[0][0] > 1              # oldest is collapsed
    assert c[0][1] - c[0][0] >= c[-1][1] - c[-1][0]


def test_budget_is_exact_and_covers_everything():
    rows = survey(memories=_corpus(), budget=40, as_rows=True)
    assert len(rows) == 40
    assert sum(r["n"] for r in rows) == 1000


def test_drilling_stays_in_range():
    rows = survey(memories=_corpus(), budget=20, lo=0, hi=64, as_rows=True)
    assert sum(r["n"] for r in rows) == 64
    assert all(r["hi"] < 64 for r in rows)


def test_block_exemplar_is_verbatim_never_synthesized():
    """The whole point of the extractive divergence from OptMem: every block
    line's body must appear in some real member, not be a merge of them."""
    mems = _corpus(256)
    rows = survey(memories=mems, budget=8, as_rows=True)
    heads = {m["summary"][:20] for m in mems}
    for r in rows:
        if r["n"] > 1:
            body = r["line"].split("] ", 1)[-1]
            assert any(body[:20] == h for h in heads), r["line"]


def test_confidential_excluded_by_default():
    mems = _corpus(100) + [{"id": "s", "summary": "private thing",
                            "tags": ["confidential", "career-search"],
                            "priority": 9, "created_at": "2026-07-01T00:00:00Z"}]
    assert "private thing" not in survey(memories=mems, budget=20)
    assert "private thing" in survey(memories=mems, budget=20,
                                     include_confidential=True)


def test_tag_filter_and_empty_corpus():
    assert len(load(tags=["t3"], memories=_corpus(100))) == 20
    assert survey(memories=[], budget=10) == "No memories in range."
