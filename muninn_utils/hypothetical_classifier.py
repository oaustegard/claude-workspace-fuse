"""hypothetical_classifier — hallucinate a label, then snap it to the legal vocabulary.

The pattern is Doug Turnbull's (softwaredoug.com, 2026-08-10, "Don't classify.
Hallucinate!"): instead of shipping a closed label set to the model and asking it to
pick, ask a cheap model to INVENT a plausible label for the item, then resolve that
invention against the real vocabulary with an embedder. The model never sees the
schema; the embedder does the constraining.

Measured on two corpora (`oaustegard/experiments/hypothetical-classification`,
gemini-3.5-flash-lite). Read the second table before reaching for this, and read the
prompt note before writing your own prompt.

WANDS query -> product_class. 860 labels, 468 queries, ONE gold label.

    arm                                       acc@1  acc@3   input tok/query
    char-ngram TF-IDF: query -> label         0.316  0.453        0
    MiniLM:            query -> label         0.417  0.564        0    <- no-LLM control
    MiniLM:  hallucination, novelty prompt    0.489  0.613      100
    MiniLM:  hallucination, register prompt   0.564  0.690      100    <- the pattern
    MiniLM:  hallucination, BATCHED x40         "      "          6
    structured output (ship all 860 labels)   0.701  0.744     5265

Muninn memory -> tag. 1,273 labels, 250 memories of 300-2000 chars, mean 4.8 gold tags.

    arm                                        @1     @3     @5
    tfidf: summary -> tag                    0.416  0.628  0.712   <- no-LLM control
    tfidf: 5 tags, novelty prompt            0.208  0.352  0.424
    tfidf: 5 tags, register prompt           0.508  0.700  0.792
    tfidf: control + register, interleaved   0.672  0.852  0.888   <- direct_union=True

THE PROMPT IS THE LARGEST SINGLE VARIABLE, AND THE SOURCE POST GETS IT WRONG.
Its prompt opens "create a novel, never-seen-before classification". That instruction is
safe only with a model too weak to follow it. A Haiku 4.5 subagent obeyed it and scored
0.100 acc@1 on WANDS against a 0.500 no-model control, writing `Hydraulic Styling Thrones`
and `Weathered Branch-Frame Reflectors`; re-anchored on register it scored 0.525/0.750.
Gemini flash-lite half-ignores the same instruction, so on WANDS it merely cost 7.5pp
(0.489 vs 0.564) - but on the tag corpus, where the vocabulary is distinctive, it cost 30
(0.208 vs 0.508) and turned a win into a loss against doing nothing. The pattern wants a
novel INSTANCE in the vocabulary's register; "never-seen-before" asks for novel WORDING.
`_PROMPT` below is register-anchored. If you replace it, keep that.

SHIPPING THE VOCABULARY IS STILL 14 POINTS BETTER WHEN YOU CAN AFFORD IT.
Structured output over all 860 WANDS labels scores 0.701 against this pattern's 0.564, at
5,265 input tokens per query against 6. The post does not report that arm. So:

    Vocabulary fits in a prompt (a few thousand labels)  -> ship it, use structured
    output, take the 0.701. This module is the wrong tool.

    Vocabulary is too big to ship, hits a provider enum cap, or per-call token cost
    dominates at volume -> this module. Muninn's own case is tag assignment: 5,575
    distinct tags is ~30k tokens on every single call.

`direct_union=True` interleaves the direct snap of the item with the snap of the written
label. It is worth +16.4pp on the tag corpus (0.672 vs 0.508) because the two rankings are
complementary, and it is the right default for long documents. It is not a rescue for a
bad prompt - fix the prompt first.

Three defaults here are measured rather than chosen:
  - `batch=40` costs nothing. Batched 0.496/0.641 vs unbatched 0.489/0.613, at 1/17
    the input tokens and 1/9 the wall-clock. Never send one item per call.
  - `blend=True` averages the item's own embedding with the hallucination's, worth
    +1.1pp on WANDS short items. For long documents use `direct_union=True` instead —
    it interleaves two full rankings rather than averaging two vectors, and the averaging
    drowns a one-word label in a 1,500-character summary.
  - `backend="tfidf"` needs no model download and lands 0.528 on WANDS against MiniLM's
    0.564. If you can ship an encoder, `thenlper/gte-small` scores 0.455 acc@1 snapping
    the raw query against MiniLM-L6's 0.417, for 33 MB of int8 ONNX against 23 MB. It BEATS MiniLM on the direct half of the tag corpus (0.416 vs 0.356), because
    a memory summary usually contains its own tag words literally. Pass `backend="minilm"`
    when sentence-transformers plus a 90 MB download are available and the items share no
    wording with the labels.

    from muninn_utils.hypothetical_classifier import Vocabulary, classify

    vocab = Vocabulary(known_tags, backend="tfidf")
    out = classify(summaries, vocab, domain="topic tag for an engineering memory store",
                   examples=["ccotw", "correction", "atproto"],
                   blend=False, direct_union=True)
    out[0].label, out[0].score, out[0].hallucination, out[0].alternatives
"""

from __future__ import annotations

import concurrent.futures as cf
import os
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Iterable, Sequence

import numpy as np

_MODEL = "gemini-3.5-flash-lite"   # explicit: the `lite` alias has resolved stale before
_BATCH = 40
_MAX_WORKERS = 3                   # the CF AI Gateway 429s above ~3 concurrent


# ── Vocabulary: the closed label set, plus the embedder that constrains to it ──

class Vocabulary:
    """A closed label set with its embedding matrix.

    Build once, reuse for every call — encoding the labels is the expensive half
    and it does not depend on the items being classified.
    """

    def __init__(self, labels: Iterable[str], *, backend: str = "tfidf",
                 model_name: str = "all-MiniLM-L6-v2"):
        self.labels = [str(x) for x in labels if str(x).strip()]
        if not self.labels:
            raise ValueError("Vocabulary needs at least one label")
        self.backend = backend
        self._model_name = model_name
        self._encoder = None
        self._matrix = self._fit()

    def _fit(self):
        if self.backend == "minilm":
            from sentence_transformers import SentenceTransformer
            self._encoder = SentenceTransformer(self._model_name)
            return _norm(np.asarray(self._encoder.encode(self.labels, batch_size=128,
                                                         show_progress_bar=False)))
        if self.backend == "tfidf":
            from sklearn.feature_extraction.text import TfidfVectorizer
            # char_wb 3-5 grams: label strings are short, and the hallucination differs
            # from the real label by morphology far more often than by meaning
            # ("Turquoise Pillows" vs "Accent Pillows"). Word tokens miss that.
            self._encoder = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5))
            return _norm(self._encoder.fit_transform(self.labels).toarray())
        raise ValueError(f"unknown backend {self.backend!r}; use 'tfidf' or 'minilm'")

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        safe = [t if t and t.strip() else " " for t in texts]
        if self.backend == "minilm":
            return _norm(np.asarray(self._encoder.encode(list(safe), batch_size=128,
                                                         show_progress_bar=False)))
        return _norm(self._encoder.transform(list(safe)).toarray())

    def snap(self, texts: Sequence[str], *, k: int = 1,
             blend_with: Sequence[str] | None = None) -> list[list[tuple[str, float]]]:
        """Nearest legal labels by cosine. `blend_with` averages a second set of
        embeddings (the original items) into the query vectors — see `blend`."""
        v = self.encode(texts)
        if blend_with is not None:
            v = _norm(v + self.encode(blend_with))
        sims = v @ self._matrix.T
        order = np.argsort(-sims, axis=1)[:, :k]
        return [[(self.labels[j], float(sims[i, j])) for j in row]
                for i, row in enumerate(order)]


def _norm(a: np.ndarray) -> np.ndarray:
    return a / np.clip(np.linalg.norm(a, axis=1, keepdims=True), 1e-9, None)


# ── The hallucination half ────────────────────────────────────────────────────

_PROMPT = """You are writing entries for a {domain} vocabulary.

For each item below, write the label that this vocabulary WOULD file that item under.
Write it the way the vocabulary writes labels — match the examples' register, length and
wording exactly.

Do not worry about whether the label already exists. Write the obvious one. Do not invent
novel or creative wording, do not use marketing adjectives, do not hedge, do not explain.

Examples of the register:
{examples}

Output one line per item, in the same order, formatted exactly as:
<n>. <label>

ITEMS:
{numbered}"""

_sem = threading.Semaphore(_MAX_WORKERS)


def _invoke(prompt: str, model: str, max_output_tokens: int) -> str | None:
    """Gemini through invoking-gemini, with the gateway's 429 backoff."""
    import sys
    if "/mnt/skills/user/invoking-gemini/scripts" not in sys.path:
        sys.path.append("/mnt/skills/user/invoking-gemini/scripts")
    from gemini_client import invoke_gemini
    for attempt in range(6):
        try:
            with _sem:
                return invoke_gemini(prompt=prompt, model=model,
                                     max_output_tokens=max_output_tokens,
                                     thinking_level="minimal", temperature=0.7)
        except Exception as exc:                       # noqa: BLE001
            if "429" not in str(exc) and "Rate limited" not in str(exc):
                raise
            time.sleep(1.5 * 2 ** attempt)
    return None


def hallucinate(items: Sequence[str], *, domain: str = "category",
                examples: Sequence[str] = (), batch: int = _BATCH,
                model: str = _MODEL, invoke: Callable[..., str | None] | None = None,
                item_chars: int = 600) -> list[str]:
    """Invent one free-form label per item. Returns "" for items the model dropped.

    A dropped item degrades to "" and the caller sees `Classification.ok == False`;
    it never silently degrades to a neighbour's label, which is why the numbered
    format is parsed back by index rather than zipped positionally.
    """
    call = invoke or _invoke
    ex = "\n".join(f"  {e}" for e in (examples or ["Coffee Tables", "Throw Pillows"]))
    chunks = [list(items[i:i + batch]) for i in range(0, len(items), batch)]

    def one(chunk: list[str]) -> list[str]:
        numbered = "\n".join(
            f"{i + 1}. {str(t)[:item_chars]}" for i, t in enumerate(chunk))
        raw = call(_PROMPT.format(domain=domain, examples=ex, numbered=numbered),
                   model, max(400, 60 * len(chunk))) or ""
        got: dict[int, str] = {}
        for line in raw.splitlines():
            m = re.match(r"\s*(\d+)[.)]\s*(.+)", line)
            if m:
                got[int(m.group(1))] = m.group(2).strip().strip('"').strip("*")
        return [got.get(i + 1, "") for i in range(len(chunk))]

    with cf.ThreadPoolExecutor(max_workers=_MAX_WORKERS) as ex_:
        return [x for chunk in ex_.map(one, chunks) for x in chunk]


# ── The whole pattern ─────────────────────────────────────────────────────────

@dataclass
class Classification:
    item: str
    label: str | None
    score: float
    hallucination: str
    alternatives: list[tuple[str, float]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.label is not None


def classify(items: Sequence[str], vocabulary: Vocabulary, *,
             domain: str = "category", examples: Sequence[str] = (),
             k: int = 3, blend: bool = True, batch: int = _BATCH,
             model: str = _MODEL, min_score: float = 0.0, direct_union: bool = False,
             invoke: Callable[..., str | None] | None = None) -> list[Classification]:
    """Hallucinate a label for each item, then snap it into `vocabulary`.

    `blend=True` averages each item's own embedding with its hallucination's before
    snapping (+1.1pp on WANDS). `direct_union=True` instead snaps the item directly as
    well and interleaves both rankings. Use blend for short items in the labels' own
    register; use direct_union for long items, where the hallucination alone scores
    half the direct snap but the union beats either (0.496 vs 0.400 vs 0.200).

    A failed generation yields `label=None` rather than a guess: an in-band wrong
    label is indistinguishable from a right one downstream.
    """
    items = [str(x) for x in items]
    if not items:
        return []
    halls = hallucinate(items, domain=domain, examples=examples, batch=batch,
                        model=model, invoke=invoke)
    idx = [i for i, h in enumerate(halls) if h.strip()]
    out = [Classification(item=it, label=None, score=0.0, hallucination=halls[i])
           for i, it in enumerate(items)]
    if not idx:
        return out
    hits = vocabulary.snap([halls[i] for i in idx], k=max(1, k),
                           blend_with=[items[i] for i in idx] if blend else None)
    direct = (vocabulary.snap([items[i] for i in idx], k=max(1, k))
              if direct_union else None)
    for n, i in enumerate(idx):
        ranked = hits[n]
        if direct is not None:
            ranked = _interleave(direct[n], hits[n], k)
        label, score = ranked[0]
        if score >= min_score:
            out[i].label, out[i].score = label, score
        out[i].alternatives = ranked
    return out


def _interleave(a: list[tuple[str, float]], b: list[tuple[str, float]],
                k: int) -> list[tuple[str, float]]:
    """Round-robin the two rankings, deduped. Interleaving rather than rescoring
    because the two scores are not on a common scale — a direct-snap cosine and a
    hallucination-snap cosine measure different distances."""
    seen: set[str] = set()
    out: list[tuple[str, float]] = []
    for pair in range(max(len(a), len(b))):
        for src in (a, b):
            if pair < len(src) and src[pair][0] not in seen:
                seen.add(src[pair][0])
                out.append(src[pair])
                if len(out) >= k:
                    return out
    return out
