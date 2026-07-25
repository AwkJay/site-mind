"""SiteMind LLM client — unified interface for all LLM calls in the
Telegram bot, with automatic model fallback.

Fallback chain:
  1. MiniMax-M3    (IAMHC API, primary — best quality, 1M context)
  2. Qwen3.6-35B-A3B (IAMHC API, backup — fast, cheap)
  3. Gemini         (Google AI, last resort)

All IAMHC models are called via the OpenAI-compatible API at
https://api.iamhc.cn/v1.  Gemini uses google-genai.  The caller never
needs to know which model answered — the interface is just
``generate(system, user) -> str``.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger("sitemind-bot.llm")

# ───────────────────────── env ───────────────────────── #
IAMHC_API_KEY = os.getenv("IAMHC_API_KEY", "")
IAMHC_BASE_URL = os.getenv("IAMHC_BASE_URL", "https://api.iamhc.cn/v1")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")

# ───────────────────── model definitions ─────────────── #

@dataclass(frozen=True)
class _Model:
    name: str         # human label for logs
    provider: str     # "iamhc" | "gemini"
    model_id: str     # model string sent to the API


# Ordered by priority — first success wins.
_FALLBACK_CHAIN: list[_Model] = [
    _Model("MiniMax-M3",       "iamhc",  "MiniMax-M3"),
    _Model("Qwen3.6-35B-A3B",  "iamhc",  "Qwen3.6-35B-A3B"),
    _Model("Gemini",           "gemini", GEMINI_MODEL),
]


# ─────────────────── provider callables ──────────────── #

def _call_iamhc(
    model_id: str,
    system: str,
    user: str,
    *,
    temperature: float = 0.1,
    max_tokens: int = 1000,
) -> str:
    """Call an IAMHC model via the OpenAI-compatible API."""
    if not IAMHC_API_KEY:
        raise RuntimeError("IAMHC_API_KEY not set")

    from openai import OpenAI

    client = OpenAI(
        api_key=IAMHC_API_KEY,
        base_url=IAMHC_BASE_URL,
        max_retries=0,
        timeout=90.0,
    )

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user})

    resp = client.chat.completions.create(
        model=model_id,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    content = resp.choices[0].message.content or ""
    return content.strip()


def _call_gemini(
    model_id: str,
    system: str,
    user: str,
    *,
    temperature: float = 0.1,
    max_tokens: int = 1000,
) -> str:
    """Call Gemini via google-genai."""
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not set")

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=GEMINI_API_KEY)
    resp = client.models.generate_content(
        model=model_id,
        contents=user,
        config=types.GenerateContentConfig(
            system_instruction=system if system else None,
            temperature=temperature,
            max_output_tokens=max_tokens,
        ),
    )
    return (resp.text or "").strip()


_PROVIDER_FN = {
    "iamhc": _call_iamhc,
    "gemini": _call_gemini,
}


# ─────────────────── public API ──────────────────────── #

def generate(
    system: str,
    user: str,
    *,
    temperature: float = 0.1,
    max_tokens: int = 1000,
) -> str:
    """Generate a completion using the fallback chain.

    Tries each model in order; on any error, logs it and moves to the
    next.  Returns "" only if every model in the chain fails — callers
    should handle that as an abstention.
    """
    for model in _FALLBACK_CHAIN:
        # Skip providers with no key configured
        if model.provider == "iamhc" and not IAMHC_API_KEY:
            log.debug("Skipping %s — no IAMHC_API_KEY", model.name)
            continue
        if model.provider == "gemini" and not GEMINI_API_KEY:
            log.debug("Skipping %s — no GEMINI_API_KEY", model.name)
            continue

        fn = _PROVIDER_FN[model.provider]
        try:
            result = fn(
                model.model_id,
                system,
                user,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if result:
                log.info("LLM answered via %s (%s)", model.name, model.provider)
                return result
            log.warning("%s returned empty — trying next", model.name)
        except Exception:
            log.exception("LLM call failed on %s — trying next", model.name)
            continue

    log.error("All models in the fallback chain failed")
    return ""


def translate(system: str, text: str) -> str:
    """Convenience wrapper for translation — lower temperature, shorter output."""
    return generate(system, text, temperature=0, max_tokens=400)
