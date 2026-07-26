"""Rotation state for SiteMind's Gemini API key pool.

Why: the Gemini free tier is roughly 20 requests/day *per Google account*.
`config.GEMINI_API_KEYS` may hold up to three independent keys (three
accounts), so this module tracks, per key, how many live requests it has
served today and whether it is unusable — either because it hit the daily
cap (self-imposed, `GEMINI_ROTATE_AFTER`, with the 20th request as headroom)
or because the provider rejected it with a real quota error (429 /
RESOURCE_EXHAUSTED).

This module never talks to the network and never sees a key's contents
beyond passing the exact string `config.GEMINI_API_KEYS[i]` back to the
caller that asked for "the key at index i" — it stores and reports indices
and counts only. Nothing here ever logs, returns, or persists a key value.

Two kinds of "this key is out" are tracked *separately*, because the
operator's remedy differs completely between them (see `health_state()`):
  - "exhausted" (persisted, resets daily at Pacific midnight): the key hit
    its request cap or a live 429/RESOURCE_EXHAUSTED. Remedy: wait for the
    daily reset, or use a different account's key.
  - "invalid" (in-memory only, NOT persisted, cleared by a process restart):
    the provider rejected the key outright (401/403/API_KEY_INVALID/
    UNAUTHENTICATED/PERMISSION_DENIED) — a bad/typo'd/revoked credential,
    not a quota condition. Remedy: fix the key in `.env` and restart; a
    restart deliberately gives it another chance rather than blacklisting it
    forever, in case the fix was exactly that restart.

Counters persist to disk (`backend/data/.llm_cache/key_usage.json`, the
existing gitignored cache dir) so a backend restart mid-demo does not
silently re-burn an already-spent key. The reset boundary is midnight
US/Pacific — where Google's free tier actually rolls over, not UTC.
"""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from . import config

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Pacific-midnight clock. Prefer real tzdata; fall back to a fixed UTC-8
# approximation (no DST) only if the venv lacks a tzdata package, and say so
# via TZ_SOURCE so callers/reports can flag the degraded accuracy instead of
# silently pretending it's exact.
# --------------------------------------------------------------------------- #
try:
    from zoneinfo import ZoneInfo

    _PACIFIC = ZoneInfo("America/Los_Angeles")
    TZ_SOURCE = "zoneinfo:America/Los_Angeles"
except Exception:  # pragma: no cover - only hit when tzdata is missing
    _PACIFIC = timezone(timedelta(hours=-8))
    TZ_SOURCE = "fixed_utc-8_fallback (tzdata unavailable — DST not accounted for)"
    logger.warning(
        "gemini_key_pool: zoneinfo 'America/Los_Angeles' unavailable — falling back to "
        "a fixed UTC-8 approximation for the daily quota reset boundary. This drifts by "
        "an hour during US daylight saving time."
    )

USAGE_FILE: Path = config.DATA_DIR / ".llm_cache" / "key_usage.json"

_LOCK = threading.Lock()
_state: Optional[dict] = None  # lazily loaded/refreshed, see _ensure_loaded()

# In-memory only, deliberately NOT persisted — see module docstring. A key
# rejected as invalid (bad credential, not a quota condition) stays skipped
# for the rest of THIS process only; a restart gives it another chance.
_invalid_keys: set[int] = set()


def _today_pacific() -> str:
    return datetime.now(_PACIFIC).strftime("%Y-%m-%d")


def _next_midnight_pacific_iso() -> str:
    now = datetime.now(_PACIFIC)
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return tomorrow.isoformat()


def _fresh_state(n_keys: int) -> dict:
    return {
        "date": _today_pacific(),
        "keys": [{"count": 0, "exhausted": False} for _ in range(n_keys)],
    }


def _load() -> dict:
    n_keys = len(config.GEMINI_API_KEYS)
    state: Optional[dict] = None
    try:
        with USAGE_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        keys = data.get("keys") if isinstance(data, dict) else None
        if not isinstance(data, dict) or not isinstance(keys, list) or not isinstance(data.get("date"), str):
            raise ValueError("key_usage.json has an unexpected shape")
        normalized = []
        for i in range(n_keys):
            entry = keys[i] if i < len(keys) and isinstance(keys[i], dict) else {}
            count = entry.get("count", 0)
            normalized.append(
                {
                    "count": int(count) if isinstance(count, (int, float)) else 0,
                    "exhausted": bool(entry.get("exhausted", False)),
                }
            )
        state = {"date": data["date"], "keys": normalized}
    except Exception:
        # Missing file, corrupt JSON, or unexpected shape -> treat as a fresh
        # day. Never raise: a corrupt counter file must not take down the
        # backend or block a live call.
        state = _fresh_state(n_keys)

    if state["date"] != _today_pacific():
        state = _fresh_state(n_keys)
    return state


def _save(state: dict) -> None:
    try:
        USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = USAGE_FILE.with_suffix(".json.tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(state, f)
        tmp.replace(USAGE_FILE)  # atomic on POSIX
    except Exception:
        logger.warning("gemini_key_pool: failed to persist key_usage.json — continuing in-memory only.", exc_info=True)


def _ensure_loaded_locked() -> dict:
    """Must be called while holding _LOCK."""
    global _state
    if _state is None:
        _state = _load()
    elif _state["date"] != _today_pacific():
        # Process has been running across a Pacific midnight boundary.
        _state = _fresh_state(len(config.GEMINI_API_KEYS))
        _invalid_keys.clear()  # a new day is also a fair reason to retry a previously-rejected key
        _save(_state)
    return _state


def _available_locked(index: int, state: dict) -> bool:
    if index in _invalid_keys:
        return False
    k = state["keys"][index]
    return (not k["exhausted"]) and k["count"] < config.GEMINI_ROTATE_AFTER


def reset_for_tests() -> None:
    """Test-only: drop in-memory state so the next call reloads from disk
    (or builds fresh state if the file is absent/stale)."""
    global _state
    with _LOCK:
        _state = None
        _invalid_keys.clear()


# --------------------------------------------------------------------------- #
# Public API used by app/llm.py
# --------------------------------------------------------------------------- #
def get_next_available(exclude: "set[int]") -> Optional[int]:
    """First key index (pool order) not in `exclude` that is currently
    available (not quota-exhausted, not invalid, under the rotation cap).
    None if the pool is empty or every key is unavailable."""
    with _LOCK:
        state = _ensure_loaded_locked()
        for i in range(len(state["keys"])):
            if i not in exclude and _available_locked(i, state):
                return i
        return None


def record_success(index: int) -> None:
    """One more successful live request served by key `index`. Cache-first:
    callers must only call this after an actual network call succeeded —
    never for a cache hit."""
    with _LOCK:
        state = _ensure_loaded_locked()
        if 0 <= index < len(state["keys"]):
            state["keys"][index]["count"] += 1
            _save(state)


def record_quota_error(index: int) -> None:
    """Key `index` returned a real quota error (429/RESOURCE_EXHAUSTED).
    Persisted: this key is done until the next Pacific-midnight reset."""
    with _LOCK:
        state = _ensure_loaded_locked()
        if 0 <= index < len(state["keys"]):
            state["keys"][index]["exhausted"] = True
            _save(state)
    logger.warning("gemini_key_pool: key #%d marked exhausted (quota error) for %s.", index + 1, _today_pacific())


def record_invalid_key(index: int) -> None:
    """Key `index` was rejected outright (401/403/API_KEY_INVALID/
    UNAUTHENTICATED/PERMISSION_DENIED) — a bad credential, not a quota
    condition. In-memory only, for this process's lifetime; NOT written to
    key_usage.json, so a restart (e.g. after the operator fixes .env) gives
    it another chance instead of blacklisting it forever."""
    with _LOCK:
        _invalid_keys.add(index)
    logger.error("gemini_key_pool: key #%d rejected as INVALID (auth error, not quota) — skipped for this process.", index + 1)


def health_state() -> dict:
    """Rotation status for GET /api/health's `llm` block. Indices and counts
    only — never a key value or prefix."""
    with _LOCK:
        state = _ensure_loaded_locked()
        n = len(state["keys"])
        active: Optional[int] = None
        for i in range(n):
            if _available_locked(i, state):
                active = i
                break
        keys_exhausted = sum(
            1 for i in range(n) if state["keys"][i]["exhausted"] or state["keys"][i]["count"] >= config.GEMINI_ROTATE_AFTER
        )
        keys_invalid = len(_invalid_keys)
        requests_on_active = state["keys"][active]["count"] if active is not None else None

    return {
        "keys_configured": n,
        "active_key_index": (active + 1) if active is not None else None,
        "requests_on_active_key": requests_on_active,
        "keys_exhausted": keys_exhausted,
        "keys_invalid": keys_invalid,
        "quota_resets_at": _next_midnight_pacific_iso(),
        "quota_reset_tz_source": TZ_SOURCE,
    }
