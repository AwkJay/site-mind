"""Vector-store abstraction for Corpus's dense index (plan §C — Actian VectorAI DB).

Two backends share one shape — `search(...)` returns a ranked list of
`(chunk_index, cosine_score)`, best-first — so `Corpus.query()`'s floor gate,
BM25 fusion (`_rrf_fuse`), and result-chunk assembly in `index.py` stay
completely untouched regardless of which store answered the dense half:

  - `NumpyVectorStore` (default, `RETRIEVAL_VECTOR_STORE=numpy`): the original
    `self._matrix @ q` brute-force cosine search, extracted here so it's the
    one call site both backends share. This is what every retrieval eval is
    calibrated against (exact cosine scores, exact abstention floors, exact
    chunk counts) — it must stay byte-identical, so nothing about its math
    changed in this extraction.
  - `ActianVectorStore` (`RETRIEVAL_VECTOR_STORE=actian`): a real, offline
    production vector database (gRPC, Docker container on `config.ACTIAN_URL`)
    — proven correct by its OWN parity eval (`eval/run_actian_parity_eval.py`),
    never by the numpy-calibrated evals (an ANN backend can legitimately
    reorder near-tied results). The `actian-vectorai-client` package is a lazy,
    optional import: `NumpyVectorStore` — and the whole numpy/eval path — works
    with it uninstalled. The caller (`index.py`) is responsible for catching a
    connection failure and falling back to numpy with a logged warning; this
    module never silently swallows one into a wrong answer.
"""
from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)


class NumpyVectorStore:
    """Wraps the original brute-force `matrix @ q` cosine search. Stateless:
    the matrix is owned by `Corpus` and passed in on every call, exactly as
    `Corpus.query()` used it before this extraction."""

    def search(self, matrix: np.ndarray, query_vector: np.ndarray, limit: int) -> list[tuple[int, float]]:
        if matrix.shape[0] == 0:
            return []
        sims = matrix @ query_vector
        order = sims.argsort()[::-1][:limit]
        return [(int(i), float(sims[i])) for i in order]


class ActianVectorStore:
    """A real, offline Actian VectorAI DB reached over gRPC. Connects lazily —
    importing/instantiating this class never requires the container to be up
    or `actian-vectorai-client` to be installed; only calling its methods does."""

    def __init__(self, url: str):
        self.url = url
        self._client = None

    def _connect(self):
        if self._client is None:
            from actian_vectorai_client import VectorAIClient  # lazy: optional dependency

            client = VectorAIClient(self.url)
            client.health_check()
            self._client = client
        return self._client

    def ensure_collection(self, name: str, dim: int = 384) -> None:
        """Idempotent: swallow "already exists", re-raise anything else."""
        from actian_vectorai_client import Distance, VectorParams  # lazy

        client = self._connect()
        try:
            client.collections.create(name, vectors_config=VectorParams(size=dim, distance=Distance.Cosine))
        except Exception as exc:
            if "already exists" not in str(exc).lower():
                raise

    def upsert(self, name: str, ids: list[int], vectors: np.ndarray, payloads: list[dict]) -> None:
        from actian_vectorai_client import PointStruct  # lazy

        client = self._connect()
        points = [
            PointStruct(id=point_id, vector=vectors[idx].tolist(), payload=payloads[idx])
            for idx, point_id in enumerate(ids)
        ]
        client.points.upsert(name, points=points)

    def search(self, name: str, query_vector: np.ndarray, limit: int) -> list[tuple[int, float]]:
        client = self._connect()
        results = client.points.search(name, vector=query_vector.tolist(), limit=limit)
        return [(int(r.payload["chunk_index"]), float(r.score)) for r in results]


_numpy_store = NumpyVectorStore()
_actian_store: ActianVectorStore | None = None


def numpy_store() -> NumpyVectorStore:
    return _numpy_store


def actian_store(url: str) -> ActianVectorStore:
    """One shared client per process (matches `embeddings_provider`'s own
    process-lifetime caching discipline) rather than one per Corpus."""
    global _actian_store
    if _actian_store is None:
        _actian_store = ActianVectorStore(url)
    return _actian_store
