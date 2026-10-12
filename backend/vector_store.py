"""FAISS index per student, plus the lookup list that maps FAISS positions to chunks.

FAISS only returns positions (numbers). `ids` is the lookup list: ids[p] is the
chunk id stored at position p. Both are built from the same ordered list of
rows, so the order can never drift apart.
"""
import threading
from dataclasses import dataclass
from typing import Optional

import faiss
import numpy as np

from . import config, db
from .embeddings import get_embedder

_lock = threading.RLock()
_cache: dict = {}


@dataclass
class UserIndex:
    index: "faiss.Index"
    ids: list      # lookup list: FAISS position -> chunk id
    meta: dict     # chunk id -> chunk row (text, material title, timestamps, ...)


def invalidate(user_id: int) -> None:
    with _lock:
        _cache.pop(user_id, None)


def _build(user_id: int) -> Optional[UserIndex]:
    emb = get_embedder()
    rows = db.get_chunks(user_id)
    if not rows:
        return None

    stale = [r for r in rows if r["embedding"] is None or r["embed_model"] != emb.name
             or len(r["embedding"]) != emb.dim * 4]
    if stale:
        vecs = emb.encode([r["text"] for r in stale])
        db.update_embeddings([(r["id"], emb.name, v.tobytes()) for r, v in zip(stale, vecs)])
        rows = db.get_chunks(user_id)

    matrix = np.vstack([np.frombuffer(r["embedding"], dtype="float32") for r in rows])
    index = faiss.IndexFlatIP(emb.dim)   # inner product on unit vectors = cosine similarity
    index.add(matrix)
    ids = [r["id"] for r in rows]        # same order as the matrix
    meta = {r["id"]: {k: v for k, v in r.items() if k != "embedding"} for r in rows}
    return UserIndex(index, ids, meta)


def _get(user_id: int) -> Optional[UserIndex]:
    with _lock:
        if user_id not in _cache:
            _cache[user_id] = _build(user_id)
        return _cache[user_id]


def add_material_chunks(user_id: int) -> None:
    """Call after new chunks were stored: rebuild the index for this student."""
    invalidate(user_id)
    _get(user_id)


def search(user_id: int, query: str, k: int = config.TOP_K,
           material_ids: Optional[list] = None, kinds: Optional[list] = None) -> list:
    ui = _get(user_id)
    if ui is None or ui.index.ntotal == 0:
        return []
    q = get_embedder().encode([query])
    n = ui.index.ntotal
    flt = bool(material_ids or kinds)
    scores, positions = ui.index.search(q, n if flt else min(k, n))
    hits = []
    for s, p in zip(scores[0], positions[0]):
        if p < 0:
            continue
        m = ui.meta[ui.ids[p]]            # position -> chunk via the lookup list
        if material_ids and m["material_id"] not in material_ids:
            continue
        if kinds and m["kind"] not in kinds:
            continue
        hits.append({**m, "chunk_id": m["id"], "score": float(s)})
        if len(hits) >= k:
            break
    return hits
