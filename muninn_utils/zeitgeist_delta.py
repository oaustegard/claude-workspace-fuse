"""
Zeitgeist deduplication: semantic delta check before storage.

Compares each topic section of a draft zeitgeist against recent entries
using the local Ettin-17m embedder (muninn_utils.ettin_embed, CPU, no API
or gateway). Flags duplicative sections and produces a compressed
delta-only version.

Usage:
    from muninn_utils.zeitgeist_delta import check_delta
    report = check_delta(draft_text)
    print(report)             # summary with per-section verdicts
    print(report.delta_text)  # compressed version to store
"""

import re
from dataclasses import dataclass


@dataclass
class SectionVerdict:
    topic: str
    similarity: float
    matched_date: str
    matched_topic: str
    verdict: str  # "new" | "delta" | "duplicate"

    def __repr__(self):
        icon = {"new": "+", "delta": "~", "duplicate": "="}[self.verdict]
        return f"[{icon}] {self.topic}: {self.similarity:.3f} vs {self.matched_topic} ({self.matched_date})"


@dataclass
class DeltaReport:
    verdicts: list[SectionVerdict]
    delta_text: str
    dup_count: int
    delta_count: int
    new_count: int
    total_recent: int

    def __repr__(self):
        lines = [
            f"Zeitgeist delta: {self.new_count} new, {self.delta_count} delta, "
            f"{self.dup_count} duplicate (vs {self.total_recent} recent entries)"
        ]
        for v in self.verdicts:
            lines.append(f"  {v}")
        return "\n".join(lines)


def _normalize_topic(topic: str) -> str:
    """Normalize topic header for matching: lowercase, strip day numbers, parens."""
    t = topic.lower()
    t = re.sub(r'\s*[\-—]\s*day\s*\d+', '', t)
    t = re.sub(r'\s*\(.*?\)', '', t)
    t = re.sub(r'\s*day\s*\d+', '', t)
    return t.strip()


def _split_sections(text: str) -> list[tuple[str, str]]:
    """Split zeitgeist into (topic_name, content) tuples.

    Handles:  ## Topic Header  |  **Topic**: description  |  **Topic — detail**:
    """
    pattern = r'(?:^|\n)\s*(?:##\s+(.+?)(?:\n|$)|\*\*(.+?)\*\*\s*[:\-—])'
    splits = list(re.finditer(pattern, text))

    if not splits:
        return [("full", text.strip())]

    sections = []
    for i, match in enumerate(splits):
        topic = (match.group(1) or match.group(2)).strip()
        start = match.start()
        end = splits[i + 1].start() if i + 1 < len(splits) else len(text)
        content = text[start:end].strip()
        if len(content) > 20:
            sections.append((topic, content))

    return sections


def check_delta(draft: str, n_recent: int = 5,
                dup_threshold: float = 0.82,
                delta_threshold: float = 0.55) -> DeltaReport:
    """Compare draft zeitgeist sections against recent entries semantically.

    Sections are embedded with Ettin-17m (encode_long: 128-token windows,
    averaged), so the scale is not Gemini's. Calibrated 2026-11-15 on 147
    sections from zeitgeist entries May-Nov 2026, each against the 5 entries
    before it:
      - 0.82+ = same facts restated (UK local elections eve vs 3 days out, 0.83);
        the closest section with new facts scored 0.80
      - 0.55-0.82 = same running story, new developments (Iran/Gulf, Ukraine)
      - <0.55 = new topic (no new topic scored above 0.55)

    Args:
        draft: Full draft zeitgeist text.
        n_recent: Number of recent zeitgeist entries to compare against.
        dup_threshold: Semantic similarity >= this -> duplicate (compress).
        delta_threshold: Similarity >= this but < dup -> delta (keep, but flag).
                         Below this -> new (keep entirely).

    Returns:
        DeltaReport with per-section verdicts and compressed delta_text.
    """
    from muninn_utils.ettin_embed import get_embedder
    from scripts import recall

    recent = recall(tags=['zeitgeist'], n=n_recent, type='world')
    draft_sections = _split_sections(draft)

    # Build pool of recent sections with normalized topic names
    recent_pool = []
    for entry in recent:
        date = entry.get('created_at', '?')[:10]
        for topic, content in _split_sections(entry['body']):
            recent_pool.append({
                'topic': topic,
                'norm_topic': _normalize_topic(topic),
                'content': content,
                'date': date,
            })

    if not recent_pool or not draft_sections:
        return DeltaReport(
            verdicts=[], delta_text=draft,
            dup_count=0, delta_count=0,
            new_count=len(draft_sections),
            total_recent=len(recent),
        )

    # Embed all sections in one batch
    all_texts = ([c for _, c in draft_sections]
                 + [s['content'] for s in recent_pool])
    embeddings = get_embedder().encode_long(all_texts)  # L2-normalized

    n_draft = len(draft_sections)
    sim = embeddings[:n_draft] @ embeddings[n_draft:].T

    verdicts = []
    delta_parts = []
    dup_count = delta_count = new_count = 0

    for i, (topic, content) in enumerate(draft_sections):
        norm = _normalize_topic(topic)

        # Find best match, preferring same-topic matches
        best_eff = float('-inf')
        best_sim = 0.0
        best_idx = 0
        for j, rp in enumerate(recent_pool):
            score = float(sim[i][j])
            # Boost same-topic matches (they're the real comparison)
            effective = score + (0.03 if rp['norm_topic'] == norm else 0)
            if effective > best_eff:
                best_eff = effective
                best_sim = score  # report raw score
                best_idx = j

        matched = recent_pool[best_idx]

        if best_sim >= dup_threshold:
            verdict = "duplicate"
            dup_count += 1
            delta_parts.append(
                f"**{topic}**: No significant change from {matched['date']}."
            )
        elif best_sim >= delta_threshold:
            verdict = "delta"
            delta_count += 1
            delta_parts.append(content)
        else:
            verdict = "new"
            new_count += 1
            delta_parts.append(content)

        verdicts.append(SectionVerdict(
            topic=topic, similarity=round(best_sim, 3),
            matched_date=matched['date'],
            matched_topic=matched['topic'],
            verdict=verdict,
        ))

    return DeltaReport(
        verdicts=verdicts,
        delta_text="\n\n".join(delta_parts),
        dup_count=dup_count, delta_count=delta_count,
        new_count=new_count, total_recent=len(recent),
    )
