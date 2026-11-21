"""Ettin-17m on the CPU: the local embedder Muninn uses instead of an embedding API.

Copied from the site repo (oaustegard/muninn.austegard.com, scripts/ettin_embedder.py), which
embeds the muninn.austegard.com search index with the same model package. The copy is
deliberate: Perch and other sessions import muninn_utils without cloning the private site
repo, and the model package is pinned by sha256, so both copies produce the same vectors.
Keep EttinEmbedder in step with the site file if either changes.

The model package (model.onnx, manifest.json, tokenizer.json, meta.json) is release asset
web-e17c-t4-w8L63.zip of oaustegard/experiments tag ettin-native-20261021, cached under
~/.cache/muninn-search/ (the cache the site's index build uses) and checked by sha256.
onnxruntime runs with graph optimizations off: its default fusions quantize activations,
and the search Worker computes the graph exactly.

The model was trained at 128 tokens and EttinEmbedder truncates there. ``encode_long``
embeds texts of any length by cutting them into 128-token windows on token boundaries and
averaging the window vectors, so a long section is compared on all of its text, not its
first ~100 words.

Requires numpy, onnxruntime and tokenizers; get_embedder() pip-installs the last two if
they are missing, as search_reindex does.
"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import subprocess
import sys
import urllib.request
import zipfile
from functools import lru_cache
from pathlib import Path

import numpy as np

RELEASE_URL = ("https://github.com/oaustegard/experiments/releases/download/"
               "ettin-native-20261021/web-e17c-t4-w8L63.zip")
MODEL_SHA256 = "c651ae63ce5da707"          # prefix of model.onnx's sha256 (ettin-native ARTIFACTS.md)
CACHE = Path.home() / ".cache" / "muninn-search" / "e17c-t4-w8L63"
MAX_TOKENS = 128


def ensure_package(cache: Path = CACHE) -> Path:
    if not (cache / "model.onnx").exists():
        cache.mkdir(parents=True, exist_ok=True)
        data = urllib.request.urlopen(RELEASE_URL, timeout=120).read()
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for n in z.namelist():
                base = n.rsplit("/", 1)[-1]
                if base in ("model.onnx", "manifest.json", "tokenizer.json", "meta.json"):
                    (cache / base).write_bytes(z.read(n))
    sha = hashlib.sha256((cache / "model.onnx").read_bytes()).hexdigest()
    if not sha.startswith(MODEL_SHA256):
        raise RuntimeError(f"ettin model.onnx sha256 {sha[:16]} != expected {MODEL_SHA256}")
    return cache


class EttinEmbedder:
    """remax_kb embedder protocol: fingerprint() + encode(texts, prompt=...)."""

    def __init__(self, package: Path | None = None, batch_size: int = 32):
        import onnxruntime as ort
        from tokenizers import Tokenizer
        self.dir = Path(package) if package else ensure_package()
        meta = json.loads((self.dir / "meta.json").read_text())
        self._prompts = {"query": meta["prompts"]["query"], "document": meta["prompts"]["document"]}
        self.tok = Tokenizer.from_file(str(self.dir / "tokenizer.json"))
        self.tok.no_padding()
        self.tok.enable_truncation(MAX_TOKENS)
        so = ort.SessionOptions()
        so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL
        self.sess = ort.InferenceSession(str(self.dir / "model.onnx"), so,
                                         providers=["CPUExecutionProvider"])
        self.sha256 = hashlib.sha256((self.dir / "model.onnx").read_bytes()).hexdigest()
        self._batch = batch_size

    @property
    def full_dim(self) -> int:
        return 768

    @property
    def normalize_l2(self) -> bool:
        return True

    @property
    def prompts(self) -> dict:
        return dict(self._prompts)

    @property
    def release_url(self):
        return RELEASE_URL

    @property
    def release_sha256(self):
        return self.sha256

    @property
    def model_revision(self):
        return "ettin-native-20261021/e17c-t4-w8L63"

    def fingerprint(self) -> dict:
        return {"model_id": "oaustegard/ettin-native e17c-t4-w8L63", "task_adapter": "retrieval",
                "pooling": "mean", "full_dim": 768, "sha256": self.sha256}

    def ids(self, text: str, prompt: str = "document") -> list[int]:
        return self.tok.encode(self._prompts[prompt] + text).ids

    def encode(self, texts, *, prompt: str = "document"):
        out = np.zeros((len(texts), 768), dtype=np.float32)
        seqs = [self.ids(t, prompt) for t in texts]
        order = sorted(range(len(seqs)), key=lambda i: len(seqs[i]))
        for b in range(0, len(order), self._batch):
            idx = order[b: b + self._batch]
            L = max(len(seqs[i]) for i in idx)
            ids = np.zeros((len(idx), L), np.int64)
            att = np.zeros((len(idx), L), np.int64)
            for r, i in enumerate(idx):
                ids[r, : len(seqs[i])] = seqs[i]
                att[r, : len(seqs[i])] = 1
            # one sequence at a time when lengths differ: the exported graph pools over every position
            if att.min() == 1:
                vecs = self.sess.run(None, {"input_ids": ids, "attention_mask": att})[0]
            else:
                vecs = np.stack([self.sess.run(None, {"input_ids": ids[r: r + 1, : len(seqs[i])],
                                                      "attention_mask": att[r: r + 1, : len(seqs[i])]})[0][0]
                                 for r, i in enumerate(idx)])
            vecs = vecs / (np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-12)
            for r, i in enumerate(idx):
                out[i] = vecs[r]
        return out

    def windows(self, text: str, size: int = MAX_TOKENS - 2) -> list[str]:
        """Cut ``text`` into pieces of at most ``size`` tokens, on token boundaries.

        ``size`` leaves room for the two special tokens the tokenizer adds to each piece.
        """
        self.tok.no_truncation()
        try:
            enc = self.tok.encode(text, add_special_tokens=False)
        finally:
            self.tok.enable_truncation(MAX_TOKENS)
        offs = enc.offsets
        if len(offs) <= size:
            return [text]
        pieces = []
        for s in range(0, len(offs), size):
            chunk = offs[s: s + size]
            pieces.append(text[chunk[0][0]: chunk[-1][1]])
        return pieces

    def encode_long(self, texts, *, prompt: str = "document"):
        """Embed texts of any length: mean of the 128-token window vectors, L2-normalized."""
        spans, flat = [], []
        for t in texts:
            w = self.windows(t)
            spans.append((len(flat), len(flat) + len(w)))
            flat.extend(w)
        vecs = self.encode(flat, prompt=prompt)
        out = np.stack([vecs[a:b].mean(axis=0) for a, b in spans]) if texts else vecs
        return out / (np.linalg.norm(out, axis=1, keepdims=True) + 1e-12)


def _ensure_deps() -> None:
    """Install onnxruntime and tokenizers iff either is missing."""
    missing = [m for m in ("onnxruntime", "tokenizers") if importlib.util.find_spec(m) is None]
    if missing:
        subprocess.run([sys.executable, "-m", "pip", "install", "--break-system-packages", "-q",
                        *missing], check=True)


@lru_cache(maxsize=1)
def get_embedder() -> EttinEmbedder:
    """One shared embedder per process (loading the session takes ~0.5 s)."""
    _ensure_deps()
    return EttinEmbedder()
