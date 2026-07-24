# Theory notes — what the search does *not* need to test

## Lemma (lower bound on counterexample order)

**Lemma.** Let D be a weakly connected simple DAG in which every source has
out-degree ≥ k and every sink has in-degree ≥ k, and suppose some source s
does not reach some sink t. Then |V(D)| ≥ 2k + 2.

*Proof.* Let R be the set of vertices reachable from s. R is closed under
successors (every out-neighbour of a vertex of R is in R), so
R ⊇ {s} ∪ N⁺(s) and |R| ≥ k + 1 (D simple). By hypothesis t ∉ R, and no
in-neighbour of t lies in R — an arc p→t with p ∈ R would put t in R. Hence
V∖R ⊇ {t} ∪ N⁻(t) and |V∖R| ≥ k + 1. ∎

**Corollary.** Every simple-DAG counterexample to Woodall's conjecture with
τ ≥ 3 has at least 8 vertices.

*Proof.* For a DAG, δ⁺(ancestor-closure of a source v) and δ⁻ of the
descendant-closure of a sink are dicuts; in a simple DAG τ ≥ 3 therefore
forces every source out-degree and sink in-degree ≥ 3. A counterexample is
not source-sink-connected (Schrijver 1982; Feofiloff–Younger 1987), i.e.,
it has a source s and sink t with no s→t path. Apply the lemma with k = 3. ∎

The exhaustive n ≤ 7 scan (`exhaustive.py`) independently machine-verifies
this: across all 2 097 152 adjacency codes at n = 7 (and everything
smaller), no DAG passes the degree conditions while failing source-sink
connectivity (`not_ssc = 0` in every run log).

## Why n = 8 is left to the machine

At n = 8 the lemma is tight and its proof pins the structure: R is exactly
{s} ∪ N⁺(s) (4 vertices), V∖R is exactly {t} ∪ N⁻(t) (4 vertices), there
are no arcs R → V∖R, so V∖R is a closed set whose dicut (the arcs
V∖R → R) must have ≥ 3 arcs, R contains a second sink t′ with three
predecessors drawn from a 3-element ground set plus V∖R, and V∖R contains a
second source s′ symmetric-ly. Eliminating (or finding!) the n = 8
candidates from these constraints is a finite but fiddly case analysis;
the exhaustive scan settles it without case-analysis risk.

**Settled (2026-07-24): the n = 8 scan came back clean.** 338 932 of the
268 435 456 codes fail source-sink connectivity, 323 622 reach τ ≥ 3, and
all of them pack 3 disjoint dijoins. Combined with the lemma: any
simple-DAG counterexample has ≥ 9 vertices.

## Structural guidance not (yet) encoded as filters

Schrijver's discussion notes (*Observations on Woodall's conjecture*,
homepages.cwi.nl/~lex/files/woodall.pdf) show a minimal counterexample may
be assumed **reduced**: acyclic, weakly 3-arc-connected, every dicut of
size k determined by a single sink or complement of a single source, every
internal vertex of degree exactly 3, and every internal arc alone in some
small cut. These are theorems about *minimal* counterexamples of the
uncapacitated conjecture — safe to use as generator biases, unsafe as hard
filters on arbitrary instances (a non-minimal counterexample would still
refute the conjecture and could be reduced afterwards).
