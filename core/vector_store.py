"""
Semantic matching / content-linking layer.

Wraps a sentence-transformer embedding model and does simple, dependency-light
cosine-similarity search over in-memory numpy arrays. This is what lets the
system find the *relevant* schema tables and the *relevant* past queries for
an arbitrary natural-language question, rather than dumping the whole schema
and whole history into every prompt.

No external vector DB is required, which keeps the project easy to run; swap
in FAISS/Chroma/pgvector here later without touching the rest of the app.
"""
import threading
from typing import List, Tuple

import numpy as np

import config

_model = None
_model_lock = threading.Lock()


def _get_model():
    """Lazily load the embedding model once per process (it's not tiny)."""
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                from sentence_transformers import SentenceTransformer
                _model = SentenceTransformer(config.EMBEDDING_MODEL)
    return _model


class VectorIndex:
    """A minimal in-memory semantic index: id -> text -> embedding."""

    def __init__(self):
        self.ids: List[str] = []
        self.texts: List[str] = []
        self.embeddings: np.ndarray | None = None

    def build(self, documents: List[dict]):
        """documents: list of {"id": str, "text": str}"""
        self.ids = [d["id"] for d in documents]
        self.texts = [d["text"] for d in documents]
        if not self.texts:
            self.embeddings = np.zeros((0, 384), dtype=np.float32)
            return
        model = _get_model()
        vecs = model.encode(self.texts, normalize_embeddings=True, show_progress_bar=False)
        self.embeddings = np.asarray(vecs, dtype=np.float32)

    def is_empty(self) -> bool:
        return self.embeddings is None or len(self.ids) == 0

    def search(self, query: str, top_k: int = 5) -> List[Tuple[str, str, float]]:
        """Returns [(id, text, similarity_score), ...] sorted best-first."""
        if self.is_empty():
            return []
        model = _get_model()
        q_vec = model.encode([query], normalize_embeddings=True, show_progress_bar=False)[0]
        # embeddings are already L2-normalised -> dot product == cosine similarity
        scores = self.embeddings @ q_vec
        top_k = min(top_k, len(self.ids))
        top_idx = np.argsort(-scores)[:top_k]
        return [(self.ids[i], self.texts[i], float(scores[i])) for i in top_idx]
