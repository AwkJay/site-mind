"""Shared embedder for semantic retrieval (Pillar 2 Copilot).

Replaces TF-IDF term-overlap retrieval with real semantic similarity — a
paraphrased question (different words, same meaning) can now match a chunk it
shares no vocabulary with. Calls the same model (all-MiniLM-L6-v2) hosted on
the Hugging Face Inference API rather than loading it in-process: this is
inference with a pretrained model, not training, so it doesn't touch the
project's "no ML training anywhere" rule — same category as calling an LLM
API. Previously ran the model locally via sentence-transformers/torch, but
that pulls ~181 MB (torch) into the process and pushes memory past the 512 MB
free-tier ceiling on every host we tested (Render, InsForge/Fly) the moment
Copilot's first query loads it — confirmed by watching both crash and
auto-restart on that exact code path. The API call is a few hundred ms over
the network instead, with no local model weights and no torch dependency.
Requires HF_TOKEN (a free Hugging Face access token); the same model, same
output contract (L2-normalized, 384-dim) either way.
"""
from __future__ import annotations

import logging
from functools import lru_cache

import httpx
import numpy as np

logger = logging.getLogger(__name__)

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
_HF_URL = f"https://router.huggingface.co/hf-inference/models/{MODEL_NAME}/pipeline/feature-extraction"


@lru_cache(maxsize=1)
def _local_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(MODEL_NAME.removeprefix("sentence-transformers/"))


def _embed_local(texts: list[str]) -> np.ndarray:
    return _local_model().encode(list(texts), normalize_embeddings=True, show_progress_bar=False)


def embed(texts: list[str]) -> np.ndarray:
    """L2-normalized embeddings, so a plain dot product equals cosine similarity.

    Mirrors `retrieval/embeddings_provider.py`'s resilience pattern: any HF
    Inference API failure (missing token, quota, network) falls back to a
    local sentence-transformers model rather than raising, so a quota hiccup
    degrades Copilot's retrieval quality instead of 500ing the whole endpoint.
    """
    if not texts:
        return np.zeros((0, 384), dtype=np.float32)

    from . import config

    if config.HF_TOKEN:
        try:
            resp = httpx.post(
                _HF_URL,
                headers={"Authorization": f"Bearer {config.HF_TOKEN}"},
                json={"inputs": list(texts)},
                timeout=30.0,
            )
            resp.raise_for_status()
            return np.array(resp.json(), dtype=np.float32)
        except Exception as exc:
            logger.warning(
                "embeddings: HF Inference API call failed (%s); falling back to local sentence-transformers model.",
                exc,
            )

    return _embed_local(texts)
