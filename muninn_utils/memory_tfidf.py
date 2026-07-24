"""Memory TF-IDF similarity index.

Builds a TF-IDF index over memory summaries for duplicate detection,
similarity search, clustering, and outlier identification.

USAGE:
    from muninn_utils.memory_tfidf import MemoryIndex

    idx = MemoryIndex()
    idx.build()  # fetches all memories from Turso

    # Find near-duplicates
    dups = idx.duplicates(threshold=0.80)
    for pair in dups:
        print(f"{pair['score']:.2f}  {pair['id_a'][:8]} ↔ {pair['id_b'][:8]}")
        print(f"  A: {pair['preview_a']}")
        print(f"  B: {pair['preview_b']}")

    # Find memories similar to a specific one
    similar = idx.similar("memory-id-here", n=5)

    # Cluster related memories
    clusters = idx.clusters(threshold=0.55)

    # Find isolated memories (dissimilar to everything)
    outliers = idx.outliers(n=20)
"""

import time
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def _to_tag_set(tags) -> set:
    """Normalize tags (list, comma-string, or None) to a set."""
    if isinstance(tags, list):
        return set(tags)
    if isinstance(tags, str):
        return set(t.strip() for t in tags.split(",") if t.strip())
    return set()


@dataclass
class MemoryIndex:
    """TF-IDF index over memory summaries."""
    ids: list[str] = field(default_factory=list)
    summaries: list[str] = field(default_factory=list)
    meta: list[dict] = field(default_factory=list)  # tags, type, etc.
    vectorizer: Optional[TfidfVectorizer] = None
    matrix: object = None  # sparse CSR matrix
    build_time_ms: float = 0

    def build(self, memories: list[dict] = None):
        """Build index. Pass memories list or fetches from Turso automatically."""
        t0 = time.monotonic()

        if memories is None:
            from scripts.memory import _exec
            memories = _exec("""
                SELECT id, summary, tags, type, confidence, priority, valid_from
                FROM memories WHERE deleted_at IS NULL
                ORDER BY valid_from DESC
            """)

        self.ids = [m['id'] for m in memories]
        self.summaries = [m.get('summary', '') for m in memories]
        self.meta = [
            {k: m.get(k) for k in ('tags', 'type', 'confidence', 'priority', 'valid_from')}
            for m in memories
        ]

        if not self.summaries:
            return self

        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            sublinear_tf=True,
            max_df=0.50,       # memory corpus is smaller/more repetitive than code
            min_df=2,
            stop_words="english",
            max_features=20000,
            token_pattern=r'(?u)\b\w{2,}\b',
        )
        self.matrix = self.vectorizer.fit_transform(self.summaries)
        self.build_time_ms = (time.monotonic() - t0) * 1000
        return self

    def stats(self) -> dict:
        return {
            "memories": len(self.ids),
            "vocabulary": len(self.vectorizer.get_feature_names_out()) if self.vectorizer else 0,
            "build_ms": round(self.build_time_ms),
            "sparsity": f"{(1 - self.matrix.nnz / (self.matrix.shape[0] * self.matrix.shape[1])):.4f}" if self.matrix is not None else None,
        }

    def _idx_of(self, memory_id: str) -> int:
        """Find index by memory ID (supports prefix match)."""
        for i, mid in enumerate(self.ids):
            if mid == memory_id or mid.startswith(memory_id):
                return i
        raise KeyError(f"Memory not found: {memory_id}")

    def similar(self, memory_id: str, n: int = 10, min_score: float = 0.05
                ) -> list[dict]:
        """Find memories most similar to a given memory."""
        if self.matrix is None:
            return []

        idx = self._idx_of(memory_id)
        scores = cosine_similarity(self.matrix[idx:idx+1], self.matrix).flatten()
        ranked = scores.argsort()[::-1]

        results = []
        for i in ranked:
            if i == idx:
                continue
            if scores[i] < min_score:
                break
            results.append({
                "id": self.ids[i],
                "score": float(scores[i]),
                "type": self.meta[i].get("type", ""),
                "tags": self.meta[i].get("tags", ""),
                "preview": self.summaries[i][:120],
            })
            if len(results) >= n:
                break
        return results

    def duplicates(self, threshold: float = 0.80, n: int = 30) -> list[dict]:
        """Find memory pairs above similarity threshold.

        Returns pairs sorted by descending score. Much more reliable than
        prefix matching — catches rephrasings, reorderings, near-duplicates.
        """
        if self.matrix is None:
            return []

        # Compute upper triangle of similarity matrix
        sim = cosine_similarity(self.matrix)
        np.fill_diagonal(sim, 0)  # ignore self-similarity

        # Extract pairs above threshold
        pairs = []
        rows, cols = np.where(sim >= threshold)
        seen = set()
        for r, c in zip(rows, cols):
            key = (min(r, c), max(r, c))
            if key in seen:
                continue
            seen.add(key)
            pairs.append({
                "id_a": self.ids[r],
                "id_b": self.ids[c],
                "score": float(sim[r, c]),
                "type_a": self.meta[r].get("type", ""),
                "type_b": self.meta[c].get("type", ""),
                "preview_a": self.summaries[r][:120],
                "preview_b": self.summaries[c][:120],
            })

        pairs.sort(key=lambda p: p["score"], reverse=True)
        return pairs[:n]

    def clusters(self, threshold: float = 0.55) -> list[list[dict]]:
        """Group memories into similarity clusters.

        Simple single-linkage: if A is similar to B and B to C,
        they're in the same cluster. Returns clusters of size >= 2,
        sorted by cluster size descending.
        """
        if self.matrix is None:
            return []

        sim = cosine_similarity(self.matrix)
        np.fill_diagonal(sim, 0)
        n = len(self.ids)

        # Union-find for single-linkage clustering
        parent = list(range(n))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        rows, cols = np.where(sim >= threshold)
        for r, c in zip(rows, cols):
            union(r, c)

        # Collect clusters
        groups = {}
        for i in range(n):
            root = find(i)
            groups.setdefault(root, []).append(i)

        clusters = []
        for indices in groups.values():
            if len(indices) < 2:
                continue
            cluster = [{
                "id": self.ids[i],
                "type": self.meta[i].get("type", ""),
                "preview": self.summaries[i][:100],
            } for i in indices]
            clusters.append(cluster)

        clusters.sort(key=len, reverse=True)
        return clusters

    def outliers(self, n: int = 20) -> list[dict]:
        """Find memories most dissimilar to everything else.

        Returns memories with lowest max-similarity to any other memory.
        These are candidates for review: either unique and valuable,
        or orphaned and forgettable.
        """
        if self.matrix is None:
            return []

        sim = cosine_similarity(self.matrix)
        np.fill_diagonal(sim, 0)

        max_sim = sim.max(axis=1)
        ranked = max_sim.argsort()

        results = []
        for i in ranked:
            results.append({
                "id": self.ids[i],
                "max_similarity": float(max_sim[i]),
                "type": self.meta[i].get("type", ""),
                "tags": self.meta[i].get("tags", ""),
                "preview": self.summaries[i][:120],
            })
            if len(results) >= n:
                break
        return results

    def cross_domain_rhymes(self, memory_id: str, n: int = 10,
                            min_sim: float = 0.3, max_tag_overlap: float = 0.3
                            ) -> list[dict]:
        """Find structurally similar memories from different domains.

        High cosine similarity + low tag overlap = cross-domain structural rhyme.
        This is the therapy Phase 2 "DRUGS" step made programmatic.
        """
        if self.matrix is None:
            return []

        idx = self._idx_of(memory_id)
        scores = cosine_similarity(self.matrix[idx:idx+1], self.matrix).flatten()

        source_tags = _to_tag_set(self.meta[idx].get("tags", []))

        candidates = []
        for i in scores.argsort()[::-1]:
            if i == idx or scores[i] < min_sim:
                break
            target_tags = _to_tag_set(self.meta[i].get("tags", []))
            if not source_tags or not target_tags:
                continue
            overlap = len(source_tags & target_tags) / len(source_tags | target_tags)
            if overlap <= max_tag_overlap:
                candidates.append({
                    "id": self.ids[i],
                    "score": float(scores[i]),
                    "tag_overlap": round(overlap, 2),
                    "type": self.meta[i].get("type", ""),
                    "shared_tags": list(source_tags & target_tags),
                    "unique_tags": list(target_tags - source_tags)[:5],
                    "preview": self.summaries[i][:120],
                })
                if len(candidates) >= n:
                    break
        return candidates
