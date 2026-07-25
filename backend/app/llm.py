"""Provider-dispatching LLM wrapper.

SiteMind's compliance pass/fail + citations are ALWAYS deterministic (Python +
clauses.json) — this module only produces *prose* (NCR wording) and *copilot
answers*, and only when a provider is configured (OFFLINE_MODE is False).

Providers (set LLM_PROVIDER in backend/.env):
  offline   — never calls out; callers use deterministic seeds / cached fixtures.
  codex     — OpenAI Codex SDK via local ChatGPT login (no API key). See docs/CODEX_SETUP.md.
  openai    — OpenAI API (needs OPENAI_API_KEY).
  anthropic — Anthropic API (needs ANTHROPIC_API_KEY).
  gemini    — Google Gemini API via google-genai (needs GEMINI_API_KEY, plus
              optional GEMINI_API_KEY_2/_3 for multi-account quota rotation —
              see gemini_key_pool.py). The HexaFalls default provider.

Every backend is best-effort: on import error, auth failure, or any exception we
return "" so the caller falls back to the offline path. Nothing here can crash a
request — important for a live demo. The clause TEXT is always handed to the model
and the Citation is filled programmatically from the cache, so citations are real
regardless of which provider (or none) writes the prose.

Caching (see llm_cache.py): every call is cache-first, keyed by
(provider, model, system_prompt, user_prompt). A cache HIT never touches the
network. A cache MISS calls the provider live; on success the response is
cached for next time. On a LIVE CALL ERROR (quota exhaustion, dead wifi,
timeout) we fall back to a prior cached response for that exact key before
giving up and returning "" (the caller's existing deterministic fallback).
This is the resilience story for demoing on a conference network with a
~20/day free-tier quota: rehearsals warm the cache, so the pitch mostly hits
cache and is immune to a dead network or an exhausted quota. `get_stats()`
below is surfaced on `GET /api/health` so a viewer (or the presenter) can
always tell whether a given run was served live or from cache.
"""
from __future__ import annotations

import atexit
import json
import logging
from typing import Optional

from . import config, gemini_key_pool, llm_cache

logger = logging.getLogger(__name__)

# Per-process counters, surfaced at GET /api/health as the `llm` sub-object.
# Deliberately NOT persisted — this is "since this backend process started",
# meant to make live-vs-cached visible during a demo, not a historical ledger
# (the cache files themselves, plus each miss/fallback log line, are that).
_STATS: dict[str, int] = {
    "live_calls": 0,
    "cache_hits": 0,
    "cache_fallbacks_after_error": 0,
    "errors": 0,
}

# Model id per provider — part of the cache key so switching GEMINI_MODEL (or
# any other provider's model) never serves a stale response from a different
# model as if it were this one.
_MODEL_BY_PROVIDER = {
    "codex": lambda: config.CODEX_MODEL,
    "openai": lambda: config.OPENAI_MODEL,
    "anthropic": lambda: config.ANTHROPIC_MODEL_SMART,
    "gemini": lambda: config.GEMINI_MODEL,
    "iamhc": lambda: "iamhc-fallback-chain",
}


def get_stats() -> dict:
    """The per-process LLM call counters plus (for gemini) key-rotation
    status — safe to hand straight to a JSON response (GET /api/health's
    `llm` block). Rotation fields are indices/counts only, never a key
    value; see gemini_key_pool.health_state()."""
    stats = dict(_STATS)
    try:
        stats.update(gemini_key_pool.health_state())
    except Exception:
        logger.warning("llm: failed to read gemini key pool health state", exc_info=True)
    return stats


# --------------------------------------------------------------------------- #
# Codex backend (OpenAI Codex SDK, ChatGPT login). Reuse one app-server.
# --------------------------------------------------------------------------- #
_codex_cm = None  # the Codex() context manager
_codex = None     # the entered Codex instance


def _get_codex():
    global _codex_cm, _codex
    if _codex is None:
        from openai_codex import Codex  # lazy: only needed for this provider

        _codex_cm = Codex()
        _codex = _codex_cm.__enter__()

        @atexit.register
        def _close():  # pragma: no cover - process teardown
            try:
                _codex_cm.__exit__(None, None, None)
            except Exception:
                pass

    return _codex


def _codex_complete(system: str, user: str) -> str:
    from openai_codex import Sandbox

    codex = _get_codex()
    # read_only sandbox => the coding agent cannot edit files or mutate the repo;
    # we only want pure text generation.
    thread = codex.thread_start(model=config.CODEX_MODEL, sandbox=Sandbox.read_only)
    prompt = (
        f"{system}\n\n{user}\n\n"
        "Respond with ONLY the requested content (text or JSON). Do not run "
        "commands, do not edit files, do not explain your process."
    )
    result = thread.run(prompt)
    return (getattr(result, "final_response", "") or "").strip()


# --------------------------------------------------------------------------- #
# OpenAI API backend
# --------------------------------------------------------------------------- #
def _openai_complete(system: str, user: str, max_tokens: int) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=config.OPENAI_API_KEY)
    resp = client.chat.completions.create(
        model=config.OPENAI_MODEL,
        temperature=0,
        max_tokens=max_tokens,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    return (resp.choices[0].message.content or "").strip()


# --------------------------------------------------------------------------- #
# IAMHC API backend with Fallback Chain
# --------------------------------------------------------------------------- #
def _iamhc_complete(system: str, user: str, max_tokens: int) -> str:
    """Uses the IAMHC API with fallback chain:
    MiniMax-M3 -> DeepSeek-V4-Flash -> Qwen3.6-35B-A3B -> Gemini
    """
    from openai import OpenAI, RateLimitError, APIConnectionError, APIError

    client = OpenAI(
        api_key=config.IAMHC_API_KEY,
        base_url=config.IAMHC_BASE_URL,
        max_retries=0,
        timeout=90.0,
    )

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user})

    fallback_chain = ["MiniMax-M3", "DeepSeek-V4-Flash", "Qwen3.6-35B-A3B"]
    last_exc = None

    for model in fallback_chain:
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0,
                max_tokens=max_tokens,
            )
            content = resp.choices[0].message.content or ""
            return content.strip()
        except (RateLimitError, APIConnectionError, APIError) as exc:
            logger.warning("llm: IAMHC %s failed (%s) — trying next model.", model, type(exc).__name__)
            last_exc = exc
        except Exception as exc:
            logger.warning("llm: IAMHC %s failed unexpectedly — trying next.", model, exc_info=True)
            last_exc = exc
            
    logger.error("llm: All IAMHC models failed, falling back to Gemini.")
    # If IAMHC chain fails entirely, try Gemini
    if config.GEMINI_API_KEY:
        try:
            return _gemini_complete(system, user, max_tokens)
        except Exception:
            logger.exception("llm: Gemini fallback also failed.")
            
    if last_exc:
        raise last_exc
    raise RuntimeError("llm: All IAMHC models and Gemini fallback failed.")


# --------------------------------------------------------------------------- #
# Anthropic backend
# --------------------------------------------------------------------------- #
def _anthropic_complete(system: str, user: str, max_tokens: int) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    resp = client.messages.create(
        model=config.ANTHROPIC_MODEL_SMART,
        max_tokens=max_tokens,
        temperature=0,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()


# --------------------------------------------------------------------------- #
# Gemini backend (Google AI Studio / google-genai SDK) — multi-key rotation.
#
# config.GEMINI_API_KEYS may hold 1-3 keys (independent Google accounts, each
# with its own ~20/day free-tier quota). gemini_key_pool.py tracks per-key
# usage/exhaustion (persisted, resets at Pacific midnight) and per-key
# validity (in-memory only, a process-lifetime skip for a rejected
# credential). _gemini_complete never branches on a key's *content* — every
# key uses the identical client/auth/endpoint path; rotation is purely which
# credential string gets passed to that one path.
# --------------------------------------------------------------------------- #
_QUOTA_ERROR_MARKERS = (
    "resource_exhausted",
    "quota exceeded",
    "quota_exceeded",
    "rate limit",
    "resourceexhausted",
)
_INVALID_KEY_MARKERS = (
    "api_key_invalid",
    "api key not valid",
    "permission_denied",
    "unauthenticated",
    "invalid api key",
)


def _classify_gemini_error(exc: Exception) -> str:
    """"quota" (real 429/RESOURCE_EXHAUSTED — this key is out for today),
    "invalid_key" (401/403/API_KEY_INVALID/UNAUTHENTICATED/PERMISSION_DENIED
    — this credential is simply bad, not a quota condition), or "other" (a
    transient/unrelated failure — not worth burning through the whole pool
    for). google-genai's APIError exposes `.code` (int HTTP status) and
    `.status` (a string like "RESOURCE_EXHAUSTED"); str(exc) already embeds
    both, so the marker scan below covers SDK versions that don't expose the
    structured attributes too."""
    code = getattr(exc, "code", None)
    if not isinstance(code, int):
        code = getattr(exc, "status_code", None)
    if code == 429:
        return "quota"
    if code in (401, 403):
        return "invalid_key"
    msg = str(exc).lower()
    if any(marker in msg for marker in _QUOTA_ERROR_MARKERS):
        return "quota"
    if any(marker in msg for marker in _INVALID_KEY_MARKERS):
        return "invalid_key"
    return "other"


def _gemini_complete_with_key(api_key: str, system: str, user: str, max_tokens: int) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    resp = client.models.generate_content(
        model=config.GEMINI_MODEL,
        contents=user,
        config=types.GenerateContentConfig(
            system_instruction=system,
            temperature=0,
            max_output_tokens=max_tokens,
        ),
    )
    return (resp.text or "").strip()


def _gemini_complete(system: str, user: str, max_tokens: int) -> str:
    """Tries the current active key from the rotation pool. A quota error
    marks that key exhausted (persisted, resets at Pacific midnight); an
    auth-rejection marks it invalid (in-memory, this process only) — either
    way, rotates to the next available key and transparently retries the
    SAME request. At most one attempt per configured key (no infinite loop).
    A non-quota/non-auth error (network blip, etc.) is raised immediately
    without cycling the pool, same as the pre-rotation behaviour, so
    llm_cache.cached_call's single-retry-via-cache-fallback story is
    unchanged for that case. If every key is unavailable (or the pool is
    empty), raises so the caller falls back to cache, then ""."""
    tried: set[int] = set()
    last_exc: Optional[Exception] = None
    for _ in range(max(len(config.GEMINI_API_KEYS), 1)):
        index = gemini_key_pool.get_next_available(tried)
        if index is None:
            break
        tried.add(index)
        try:
            text = _gemini_complete_with_key(config.GEMINI_API_KEYS[index], system, user, max_tokens)
            gemini_key_pool.record_success(index)
            return text
        except Exception as exc:
            kind = _classify_gemini_error(exc)
            if kind == "quota":
                logger.warning("llm: gemini key #%d hit quota — rotating to next key.", index + 1)
                gemini_key_pool.record_quota_error(index)
                last_exc = exc
                continue
            if kind == "invalid_key":
                logger.error(
                    "llm: gemini key #%d rejected (auth error, not quota) — rotating to next key.", index + 1
                )
                gemini_key_pool.record_invalid_key(index)
                last_exc = exc
                continue
            raise  # unrelated failure (network/timeout/etc.) — don't cycle the whole pool for it
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("gemini: no available API key in the pool (all exhausted/invalid/unconfigured)")


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def _dispatch_live(provider: str, system: str, user: str, max_tokens: int) -> str:
    """The actual network call for `provider`. Unlike the old complete_text,
    this RAISES on failure instead of swallowing the exception — llm_cache.
    cached_call needs to see the error to know when to fall back to a cached
    response instead of the deterministic path."""
    if provider == "codex":
        return _codex_complete(system, user)
    if provider == "openai":
        return _openai_complete(system, user, max_tokens)
    if provider == "anthropic":
        return _anthropic_complete(system, user, max_tokens)
    if provider == "gemini":
        return _gemini_complete(system, user, max_tokens)
    if provider == "iamhc":
        return _iamhc_complete(system, user, max_tokens)
    return ""  # unknown provider string — nothing to call


def complete_text(system: str, user: str, max_tokens: int = 800) -> str:
    """Single-turn completion (temperature 0). Returns "" on any failure so the
    caller can fall back to the deterministic/offline path.

    Cache-first (see module docstring + llm_cache.py): OFFLINE_MODE / an
    unconfigured provider never touches the cache or the network at all —
    that guarantee predates this cache and must keep holding. A configured
    provider checks the on-disk cache before ever calling out; on a live-call
    error it falls back to a cached response for the same key before
    returning "" to the caller's own deterministic fallback."""
    # Belt-and-suspenders: every current caller already gates on
    # config.OFFLINE_MODE before reaching here, but this module is the single
    # choke point for "does a network call happen", so it enforces the
    # invariant itself too — OFFLINE_MODE=1 (no usable provider) must never
    # touch the network OR the cache, full stop.
    if config.OFFLINE_MODE:
        return ""

    provider = config.LLM_PROVIDER
    if provider not in _MODEL_BY_PROVIDER:
        return ""  # unknown/unconfigured provider string — zero network calls, zero cache I/O

    model = _MODEL_BY_PROVIDER[provider]()

    def _live() -> str:
        return _dispatch_live(provider, system, user, max_tokens)

    text, source = llm_cache.cached_call(_live, provider, model, system, user)

    if source == "cache_hit":
        _STATS["cache_hits"] += 1
        logger.info("llm: cache HIT (provider=%s model=%s) — served from disk, no network call.", provider, model)
    elif source == "live":
        _STATS["live_calls"] += 1
        logger.info("llm: LIVE call (provider=%s model=%s) — response cached for next time.", provider, model)
    elif source == "cache_fallback_after_error":
        _STATS["cache_fallbacks_after_error"] += 1
        logger.warning(
            "llm: LIVE CALL FAILED (provider=%s model=%s) — served a CACHED fallback response. "
            "This output is NOT live for this request.",
            provider,
            model,
        )
    else:  # "error" — live call failed AND no cache entry exists for this key
        _STATS["errors"] += 1
        logger.error(
            "llm: LIVE CALL FAILED (provider=%s model=%s) with no cache entry for this prompt — "
            "caller falls back to the deterministic path.",
            provider,
            model,
        )
    return text


def complete_json(system: str, user: str, max_tokens: int = 800) -> Optional[dict]:
    """complete_text + parse JSON; None on failure (tolerates ```json fences)."""
    txt = complete_text(system, user, max_tokens).strip()
    if not txt:
        return None
    if txt.startswith("```"):
        txt = txt.strip("`")
        txt = txt[txt.find("{") :]
    try:
        return json.loads(txt[txt.find("{") : txt.rfind("}") + 1])
    except (json.JSONDecodeError, ValueError):
        return None
