"""Tests for app.gemini_key_pool (rotation/persistence/reset) and its
integration into app.llm._gemini_complete (429 -> rotate, auth error ->
rotate-and-skip-permanently-for-this-process, all-exhausted -> fall through).

Zero live network calls anywhere in this file: the Gemini client is never
imported/constructed; every "live call" is a monkeypatched stub that either
returns canned text or raises a synthetic error shaped like a real
google-genai APIError (has `.code` + `.status`, same as the SDK). Never
prints/logs/asserts on a key VALUE — only on pool indices/counts, matching
the module's own contract (see gemini_key_pool.py's docstring).
"""
from __future__ import annotations

import json
import threading

import pytest

from app import config, gemini_key_pool, llm, llm_cache


class _FakeAPIError(Exception):
    """Shaped like google.genai.errors.APIError: exposes `.code` (int HTTP
    status) and `.status` (string), and embeds both in str(exc) too — the
    same two detection surfaces app.llm._classify_gemini_error checks."""

    def __init__(self, code: int, status: str):
        self.code = code
        self.status = status
        super().__init__(f"{code} {status}. {{}}")


def _quota_error() -> _FakeAPIError:
    return _FakeAPIError(429, "RESOURCE_EXHAUSTED")


def _invalid_key_error() -> _FakeAPIError:
    return _FakeAPIError(403, "PERMISSION_DENIED")


@pytest.fixture
def pool(tmp_path, monkeypatch):
    """Isolated 3-key pool backed by a tmp usage file. Also points
    llm_cache's CACHE_DIR at a tmp dir so these tests never touch (or get
    served by) the real on-disk prompt cache."""
    keys = ["key-a-fake", "key-b-fake", "key-c-fake"]
    monkeypatch.setattr(config, "GEMINI_API_KEYS", keys)
    monkeypatch.setattr(config, "GEMINI_ROTATE_AFTER", 19)
    monkeypatch.setattr(config, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(config, "OFFLINE_MODE", False)
    monkeypatch.setattr(gemini_key_pool, "USAGE_FILE", tmp_path / "key_usage.json")
    monkeypatch.setattr(llm_cache, "CACHE_DIR", tmp_path / "cache")
    gemini_key_pool.reset_for_tests()
    yield keys
    gemini_key_pool.reset_for_tests()


# --------------------------------------------------------------------------- #
# Pure key_pool behavior
# --------------------------------------------------------------------------- #
def test_single_key_pool_is_usable_and_byte_identical_semantics(monkeypatch):
    """With only GEMINI_API_KEY set, GEMINI_API_KEYS is a 1-element list and
    _provider_usable()'s truthiness matches bool(GEMINI_API_KEY) exactly —
    no regression for the pre-rotation single-key setup."""
    monkeypatch.setattr(config, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(config, "GEMINI_API_KEY", "solo-key")
    monkeypatch.setattr(config, "GEMINI_API_KEYS", ["solo-key"])
    assert config._provider_usable() is True

    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    monkeypatch.setattr(config, "GEMINI_API_KEYS", [])
    assert config._provider_usable() is False


def test_rotate_after_19_successes_moves_to_next_key(pool):
    idx = gemini_key_pool.get_next_available(set())
    assert idx == 0
    for _ in range(19):
        gemini_key_pool.record_success(0)
    # Key 0 has hit the rotate-after cap (headroom preserved, never spent).
    idx = gemini_key_pool.get_next_available(set())
    assert idx == 1
    state = gemini_key_pool.health_state()
    assert state["active_key_index"] == 2  # 1-based
    assert state["requests_on_active_key"] == 0
    assert state["keys_exhausted"] == 1


def test_quota_error_marks_exhausted_and_rotates(pool):
    gemini_key_pool.record_quota_error(1)  # key #2 (0-based index 1)
    idx = gemini_key_pool.get_next_available({0})  # simulate key 0 already tried this request
    assert idx == 2
    state = gemini_key_pool.health_state()
    assert state["keys_exhausted"] == 1


def test_invalid_key_skipped_but_not_persisted(pool, tmp_path):
    gemini_key_pool.record_invalid_key(0)
    assert gemini_key_pool.get_next_available(set()) == 1
    gemini_key_pool.record_success(1)  # force a disk write so there's a file to inspect
    on_disk = json.loads((tmp_path / "key_usage.json").read_text())
    assert "invalid" not in json.dumps(on_disk)  # the invalid flag is never written to disk

    # Simulated restart: in-memory state (including the invalid set) is
    # dropped; disk state is reloaded. Key 0 gets another chance.
    gemini_key_pool.reset_for_tests()
    assert gemini_key_pool.get_next_available(set()) == 0


def test_counters_persist_across_simulated_restart(pool, tmp_path):
    gemini_key_pool.record_success(0)
    gemini_key_pool.record_success(0)
    gemini_key_pool.record_quota_error(1)

    gemini_key_pool.reset_for_tests()  # drop in-memory state only

    state = gemini_key_pool.health_state()
    assert state["active_key_index"] == 1
    assert state["requests_on_active_key"] == 2
    assert state["keys_exhausted"] == 1  # key #2 stayed exhausted


def test_stale_date_triggers_full_reset(pool, tmp_path):
    stale = {"date": "2020-01-01", "keys": [{"count": 19, "exhausted": True}, {"count": 5, "exhausted": False}, {"count": 0, "exhausted": False}]}
    (tmp_path / "key_usage.json").write_text(json.dumps(stale))
    gemini_key_pool.reset_for_tests()

    state = gemini_key_pool.health_state()
    assert state["active_key_index"] == 1
    assert state["requests_on_active_key"] == 0
    assert state["keys_exhausted"] == 0


def test_corrupt_file_treated_as_fresh_day_never_raises(pool, tmp_path):
    (tmp_path / "key_usage.json").write_text("{not json")
    gemini_key_pool.reset_for_tests()
    state = gemini_key_pool.health_state()  # must not raise
    assert state["keys_configured"] == 3
    assert state["active_key_index"] == 1
    assert state["requests_on_active_key"] == 0


def test_concurrent_increments_are_not_lost(pool):
    """Guards the threading.Lock around the read-modify-write in
    record_success — without it, concurrent increments can clobber each
    other and undercount usage."""
    def hammer():
        for _ in range(50):
            gemini_key_pool.record_success(0)

    threads = [threading.Thread(target=hammer) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    state = gemini_key_pool.health_state()
    # 400 successes on key 0 far exceeds the rotate-after cap, so key 0 is no
    # longer "active" — read the persisted count directly instead.
    with gemini_key_pool.USAGE_FILE.open() as f:
        on_disk = json.load(f)
    assert on_disk["keys"][0]["count"] == 400


# --------------------------------------------------------------------------- #
# Integration through app.llm._gemini_complete / complete_text
# --------------------------------------------------------------------------- #
def test_llm_rotates_after_19_successes_to_key_2(pool, monkeypatch):
    calls: list[str] = []

    def fake_call(api_key, system, user, max_tokens):
        calls.append(api_key)
        return "ok"

    monkeypatch.setattr(llm, "_gemini_complete_with_key", fake_call)

    for _ in range(19):
        llm._gemini_complete("sys", "user", 800)
    assert all(k == pool[0] for k in calls)

    calls.clear()
    llm._gemini_complete("sys", "user", 800)
    assert calls == [pool[1]]  # 20th call used key #2


def test_llm_synthetic_429_switches_immediately_and_serves_result(pool, monkeypatch):
    attempts: list[str] = []

    def fake_call(api_key, system, user, max_tokens):
        attempts.append(api_key)
        if api_key == pool[1]:
            raise _quota_error()
        return "served-by-key-3"

    monkeypatch.setattr(llm, "_gemini_complete_with_key", fake_call)
    for _ in range(19):
        gemini_key_pool.record_success(0)  # exhaust key 0's headroom so key 1 is active

    text = llm._gemini_complete("sys", "user", 800)
    assert text == "served-by-key-3"
    assert attempts == [pool[1], pool[2]]
    assert gemini_key_pool.health_state()["keys_exhausted"] == 2  # key 0 (cap) + key 1 (quota)


def test_llm_invalid_key_rotates_and_is_distinct_from_quota(pool, monkeypatch):
    attempts: list[str] = []

    def fake_call(api_key, system, user, max_tokens):
        attempts.append(api_key)
        if api_key == pool[0]:
            raise _invalid_key_error()
        return "served-by-key-2"

    monkeypatch.setattr(llm, "_gemini_complete_with_key", fake_call)
    text = llm._gemini_complete("sys", "user", 800)
    assert text == "served-by-key-2"
    assert attempts == [pool[0], pool[1]]
    state = gemini_key_pool.health_state()
    assert state["keys_invalid"] == 1
    assert state["keys_exhausted"] == 0  # invalid, not quota-exhausted — distinct counters


def test_all_keys_exhausted_falls_through_to_empty_string_never_raises(pool, monkeypatch):
    def fake_call(api_key, system, user, max_tokens):
        raise _quota_error()

    monkeypatch.setattr(llm, "_gemini_complete_with_key", fake_call)

    text = llm.complete_text("sys", "user")  # full path: complete_text -> cache -> _gemini_complete
    assert text == ""
    state = gemini_key_pool.health_state()
    assert state["keys_exhausted"] == 3
    assert state["active_key_index"] is None


def test_cache_hit_costs_zero_quota_and_never_advances_rotation(pool, monkeypatch):
    calls = []
    monkeypatch.setattr(llm, "_gemini_complete_with_key", lambda *a, **k: calls.append(1) or "first")

    first = llm.complete_text("sys", "same prompt")
    assert first == "first"
    assert len(calls) == 1
    count_after_first = gemini_key_pool.health_state()["requests_on_active_key"]
    assert count_after_first == 1

    second = llm.complete_text("sys", "same prompt")  # identical key -> cache hit
    assert second == "first"
    assert len(calls) == 1  # provider never touched again
    assert gemini_key_pool.health_state()["requests_on_active_key"] == count_after_first  # unchanged


def test_health_endpoint_exposes_rotation_fields_without_leaking_key_values(pool):
    stats = llm.get_stats()
    for field in (
        "keys_configured",
        "active_key_index",
        "requests_on_active_key",
        "keys_exhausted",
        "keys_invalid",
        "quota_resets_at",
    ):
        assert field in stats
    dumped = json.dumps(stats)
    for key_value in pool:
        assert key_value not in dumped
