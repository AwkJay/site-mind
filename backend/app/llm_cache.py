"""Disk-backed, dependency-free cache for LLM prose/JSON responses.

Why: SiteMind's live Gemini free tier is roughly 20 requests/day, and a single
demo run of the hero document costs ~7 requests (1 extraction + ~6 prose
calls). Two rehearsals plus the live pitch would exhaust the quota, and a
quota error or flaky conference wifi mid-demo currently degrades straight to
the (visibly worse) deterministic fallback. This cache sits between
`app/llm.py` and the network: an identical (provider, model, system_prompt,
user_prompt) call is served from disk with zero network round-trips, and on a
LIVE call failure it serves a prior cached response for that same key before
`llm.py` gives up and lets its caller fall back to deterministic prose.

This module never decides a compliance verdict and never alters what a model
returned — it only memoizes it. Same integrity boundary as everything else
that touches an LLM in this repo.

Storage: one JSON file per cache key under `backend/data/.llm_cache/`
(`config.DATA_DIR / ".llm_cache"`), keyed by a sha256 hex digest so restarting
the backend does not lose the cache — that persistence is the entire point.
Writes are atomic (write to a .tmp file, then os.replace) so a crash mid-write
never leaves a half-written file for a later read to choke on. Any read that
fails for any reason (missing file, corrupt JSON, wrong shape) is treated as
a plain cache miss — never an exception that could take down a request.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Callable, Optional

from . import config

logger = logging.getLogger(__name__)

CACHE_DIR: Path = config.DATA_DIR / ".llm_cache"


# --------------------------------------------------------------------------- #
# Key derivation
# --------------------------------------------------------------------------- #
def cache_key(provider: str, model: str, system: str, user: str) -> str:
    """sha256 hex digest over (provider, model, system_prompt, user_prompt).

    Deterministic across process restarts and across machines — that's the
    whole point: a prompt warmed during rehearsal must still hit on stage
    even after a backend restart. Each field is length-delimited by a NUL
    separator so ("a", "bc") and ("ab", "c") never collide.
    """
    h = hashlib.sha256()
    for part in (provider or "", model or "", system or "", user or ""):
        h.update(part.encode("utf-8", errors="replace"))
        h.update(b"\x00")
    return h.hexdigest()


def _path_for(key: str) -> Path:
    return CACHE_DIR / f"{key}.json"


# --------------------------------------------------------------------------- #
# Low-level get/put — safe by construction (never raise into a caller).
# --------------------------------------------------------------------------- #
def get(key: str) -> Optional[dict]:
    """Returns the cached envelope ({"text": ..., "cached_at": ..., ...}), or
    None on a miss OR any unreadable/corrupt file. A bad cache file must
    degrade to a miss, never an exception — a hackathon demo can't crash on a
    torn write."""
    path = _path_for(key)
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or not isinstance(data.get("text"), str):
            logger.warning("llm_cache: cache file %s has unexpected shape — treating as miss.", path.name)
            return None
        return data
    except Exception:
        logger.warning("llm_cache: cache file %s is unreadable/corrupt — treating as miss.", path.name, exc_info=True)
        return None


def put(key: str, text: str, meta: Optional[dict] = None) -> None:
    """Best-effort atomic write. A disk hiccup here must not crash the request
    that just made a real, billable LLM call and is trying to return its
    result."""
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        payload: dict = {"text": text, "cached_at": time.time()}
        if meta:
            payload.update(meta)
        path = _path_for(key)
        tmp = path.with_suffix(".json.tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(payload, f)
        tmp.replace(path)  # atomic on POSIX — readers never see a half-written file
    except Exception:
        logger.warning("llm_cache: failed to write cache entry %s — continuing uncached.", key, exc_info=True)


# --------------------------------------------------------------------------- #
# High-level wrapper used by app/llm.py
# --------------------------------------------------------------------------- #
def cached_call(
    fn: Callable[[], str],
    provider: str,
    model: str,
    system: str,
    user: str,
) -> tuple[str, str]:
    """Cache-first wrapper around a zero-arg live-call closure `fn`.

    Fallback order (this is the whole resilience story for a flaky
    conference network / exhausted quota mid-demo):
      1. Cache HIT             -> serve it, `fn` is never invoked, zero network.
      2. Cache MISS            -> call `fn()`.
         a. `fn()` succeeds    -> cache the result, return it ("live").
         b. `fn()` raises      -> check the cache again for this exact key
                                   (covers a concurrent warm/write landing
                                   between the first check and the failed
                                   call); if found, serve it ("cache_fallback
                                   _after_error"); if still nothing, return
                                   "" and let the caller's own deterministic
                                   fallback take over ("error").

    Returns (text, source); `source` is one of:
      "cache_hit", "live", "cache_fallback_after_error", "error"
    Callers use `source` to update stats/logging — never to change behavior
    beyond that (the returned text is always what should be shown).
    """
    key = cache_key(provider, model, system, user)

    hit = get(key)
    if hit is not None:
        return hit["text"], "cache_hit"

    try:
        text = fn()
        if text:  # don't cache empty completions — nothing useful to replay
            put(key, text, {"provider": provider, "model": model})
        return text, "live"
    except Exception:
        logger.warning(
            "llm_cache: live call raised for provider=%s model=%s — checking cache fallback.",
            provider,
            model,
            exc_info=True,
        )
        fallback = get(key)
        if fallback is not None:
            return fallback["text"], "cache_fallback_after_error"
        return "", "error"
