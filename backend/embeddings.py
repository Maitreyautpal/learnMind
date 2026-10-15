"""Text -> vector. Sentence Transformers by default, hash fallback when offline.

The same embedder must be used for chunks and for questions, otherwise the
distances between vectors mean nothing. vector_store re-embeds stored chunks
automatically if the embedder changes.
"""
import hashlib
import logging
import re
from functools import lru_cache

import numpy as np

from . import config

log = logging.getLogger("learnmind.embeddings")
_TOKEN = re.compile(r"[a-z0-9]+")


class HashEmbedder:
    """Offline fallback: hashed bag of words and bigrams. Matches words, not meaning."""
    name = "hash-384"
    dim = config.EMBED_DIM

    def encode(self, texts) -> np.ndarray:
        texts = list(texts)
        out = np.zeros((len(texts), self.dim), dtype="float32")
        for i, t in enumerate(texts):
            toks = _TOKEN.findall(t.lower())
            for f in toks + [a + "_" + b for a, b in zip(toks, toks[1:])]:
                h = int.from_bytes(hashlib.md5(f.encode()).digest()[:8], "little")
                out[i, h % self.dim] += 1.0 if (h >> 63) & 1 else -1.0
        out = np.sign(out) * np.log1p(np.abs(out))
        norms = np.linalg.norm(out, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return (out / norms).astype("float32")


class STEmbedder:
    """Pretrained Sentence Transformers model (not trained by the team)."""

    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(model_name)
        self.name = model_name
        self.dim = int(self.model.get_sentence_embedding_dimension())

    def encode(self, texts) -> np.ndarray:
        vecs = self.model.encode(list(texts), normalize_embeddings=True, show_progress_bar=False)
        return np.asarray(vecs, dtype="float32")


class FastEmbedder:
    """Same pretrained model, run with ONNX (no PyTorch): about 200 MB RAM, fits small servers."""

    def __init__(self, model_name: str):
        from fastembed import TextEmbedding
        self.model = TextEmbedding(model_name, threads=1)
        self.name = model_name
        self.dim = len(next(iter(self.model.embed(["warm up"]))))

    def encode(self, texts) -> np.ndarray:
        vecs = np.asarray(list(self.model.embed(list(texts), batch_size=8)), dtype="float32")
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return (vecs / norms).astype("float32")


@lru_cache(maxsize=1)
def get_embedder():
    """EMBEDDER=auto: Sentence Transformers, then FastEmbed (ONNX), then the hash fallback.
    EMBEDDER=fastembed or hash forces one of them."""
    order = {"hash": [], "fastembed": [FastEmbedder],
             "st": [STEmbedder]}.get(config.EMBEDDER, [STEmbedder, FastEmbedder])
    for cls in order:
        try:
            emb = cls(config.EMBED_MODEL)
            log.info("Using %s with model %s", cls.__name__, config.EMBED_MODEL)
            return emb
        except Exception as exc:  # missing package, no internet for first download, ...
            log.warning("%s unavailable (%s).", cls.__name__, exc)
    log.warning("Falling back to the offline hash embedder: search will match words, not meaning.")
    return HashEmbedder()
