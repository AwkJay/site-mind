# Shipment Delay Mutation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user tell the Telegram bot "delay SHP-002 by 10 days" (or similar), confirm a preview, and have that actually mutate the shipment's `days_at_risk` everywhere it's read — backed by a real endpoint, not a chat-side fake, and logged to the audit ledger.

**Architecture:** A per-shipment in-memory override dict (`supply_chain_overrides.py`) mirrors `clock.py`'s existing "advance the simulated clock" pattern, applied inside `supply_chain._build()` so every downstream read (`/api/overview`, `/api/cost-risk`, `/api/timeline`) picks it up automatically with no changes of their own. Two new endpoints apply/reset it, both audit-logged. The bot detects mutation-shaped messages with a cheap regex pre-filter, extracts structured intent via one LLM call (Python validates the shipment ID — the LLM never decides), previews it, and only calls the endpoint after an explicit "yes".

**Tech Stack:** FastAPI + Pydantic (backend, existing), python-telegram-bot + httpx (bot, existing). No new dependencies.

**Spec:** `docs/superpowers/specs/2026-07-26-shipment-delay-mutation-design.md` — read it for the "why" behind every design choice below; this plan only covers the "how."

## Global Constraints

- Overrides are in-memory only, reset on backend restart (never write to `supply_chain.json`).
- Cumulative delta per shipment clamped to ±60 days (`MAX_CUMULATIVE_DELTA`, matches `clock.py`'s `MAX_OFFSET_DAYS`).
- The LLM only ever proposes `{shipment_id, delta_days, confidence}` as JSON. Python is the only code that resolves a shipment ID against the real list, clamps the delta, and writes state.
- Every applied (and reset) mutation is logged via `audit.record_event()`.
- Voice messages never confirm a pending mutation (§5.3 of the spec) — a misheard word must never apply a change.
- Backend tests run from `backend/` with `.venv` active: `python -m pytest tests/test_supply_chain_overrides.py -v`.

---

### Task 1: Backend override module + wire into shipment builder

**Files:**
- Create: `backend/app/supply_chain_overrides.py`
- Modify: `backend/app/supply_chain.py:222-246` (the `_build()` function)
- Test: `backend/tests/test_supply_chain_overrides.py`

**Interfaces:**
- Produces: `supply_chain_overrides.get_delta(shipment_id: str) -> int`, `apply_delta(shipment_id: str, delta_days: int) -> int` (returns new clamped cumulative total), `reset(shipment_id: str | None = None) -> None`, `MAX_CUMULATIVE_DELTA: int = 60`. Task 2 and Task 4 both call these by name.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_supply_chain_overrides.py`:

```python
"""Tests for per-shipment delay overrides
(docs/superpowers/specs/2026-07-26-shipment-delay-mutation-design.md)."""
from __future__ import annotations

from app import supply_chain, supply_chain_overrides as overrides


def teardown_function():
    overrides.reset()


def test_apply_delta_increases_days_at_risk():
    before = next(s for s in supply_chain.shipments() if s.id == "SHP-001").days_at_risk
    overrides.apply_delta("SHP-001", 10)
    after = next(s for s in supply_chain.shipments() if s.id == "SHP-001").days_at_risk
    assert after == before + 10


def test_apply_delta_sets_root_cause_note():
    overrides.apply_delta("SHP-006", 5)
    shipment = next(s for s in supply_chain.shipments() if s.id == "SHP-006")
    assert "manually adjusted +5d via field update" in shipment.root_cause


def test_negative_delta_reduces_days_at_risk_and_clamps_at_zero():
    before = next(s for s in supply_chain.shipments() if s.id == "SHP-002").days_at_risk
    overrides.apply_delta("SHP-002", -1000)
    after = next(s for s in supply_chain.shipments() if s.id == "SHP-002").days_at_risk
    assert after == 0


def test_apply_delta_clamps_cumulative_to_max():
    overrides.apply_delta("SHP-001", 1000)
    assert overrides.get_delta("SHP-001") == overrides.MAX_CUMULATIVE_DELTA


def test_reset_restores_original_value():
    before = next(s for s in supply_chain.shipments() if s.id == "SHP-002").days_at_risk
    overrides.apply_delta("SHP-002", 7)
    overrides.reset("SHP-002")
    after = next(s for s in supply_chain.shipments() if s.id == "SHP-002").days_at_risk
    assert after == before
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `backend/`, with `.venv` active): `python -m pytest tests/test_supply_chain_overrides.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.supply_chain_overrides'`

- [ ] **Step 3: Create `backend/app/supply_chain_overrides.py`**

```python
"""Per-shipment delay overrides — the same "prove it's not hardcoded" pattern
`clock.py` uses for the whole project's simulated "today", applied per
shipment instead of globally. Mutable state resets on backend restart;
nothing on disk changes.
See docs/superpowers/specs/2026-07-26-shipment-delay-mutation-design.md.
"""
from __future__ import annotations

MAX_CUMULATIVE_DELTA = 60

_overrides: dict[str, int] = {}


def get_delta(shipment_id: str) -> int:
    return _overrides.get(shipment_id, 0)


def _clear_downstream_caches() -> None:
    """Lazy import only — supply_chain.py imports this module at top level,
    so a top-level import back into it would be circular (same reason
    clock.py's _clear_downstream_caches does the same thing)."""
    from . import supply_chain

    supply_chain.shipments.cache_clear()
    supply_chain.risks.cache_clear()
    supply_chain.alerts.cache_clear()


def apply_delta(shipment_id: str, delta_days: int) -> int:
    global _overrides
    new_total = _overrides.get(shipment_id, 0) + delta_days
    new_total = max(-MAX_CUMULATIVE_DELTA, min(MAX_CUMULATIVE_DELTA, new_total))
    _overrides[shipment_id] = new_total
    _clear_downstream_caches()
    return new_total


def reset(shipment_id: str | None = None) -> None:
    global _overrides
    if shipment_id is None:
        _overrides = {}
    else:
        _overrides.pop(shipment_id, None)
    _clear_downstream_caches()
```

- [ ] **Step 4: Wire it into `_build()` in `backend/app/supply_chain.py`**

Add the import near the top, alongside the existing `from . import clock` at line 21:

```python
from . import clock
from . import supply_chain_overrides as overrides
```

Add a new helper directly above `_build` (which currently starts at line 222), and change `_build` itself:

```python
def _root_cause_with_override(raw_milestones: list[dict], shipment_id: str, days_at_risk: int) -> str | None:
    base = _root_cause(raw_milestones) if days_at_risk > 0 else None
    delta = overrides.get_delta(shipment_id)
    if delta == 0:
        return base
    note = f"manually adjusted {delta:+d}d via field update"
    return f"{base}; {note}" if base else note


def _build(raw: dict) -> Shipment:
    milestones, current_stage, delay, final_planned = _milestones(raw["milestones"])
    required = _required_on_site_by(raw["wbs_id"])
    projected_arrival = final_planned + delay if delay > 0 else final_planned
    projected_arrival += overrides.get_delta(raw["id"])
    days_at_risk = max(0, projected_arrival - required)
    alternatives = _alternatives(raw.get("alternatives", []), required)
    wbs_id = raw["wbs_id"]
    return Shipment(
        id=raw["id"],
        procurement_item=raw["procurement_item"],
        wbs_id=wbs_id,
        tier1_supplier=_point(raw["tier1_supplier"]),
        tier2_suppliers=[_point(t) for t in raw.get("tier2_suppliers", [])],
        milestones=milestones,
        current_stage=current_stage,
        required_on_site_by=required,
        projected_arrival_day=projected_arrival,
        days_at_risk=days_at_risk,
        on_critical_path=_on_critical_path(wbs_id),
        root_cause=_root_cause_with_override(raw["milestones"], raw["id"], days_at_risk),
        alternatives=alternatives,
        equipment_spec=_equipment_spec_check(raw),
        linked_rfi=link_rfi(wbs_id=wbs_id, query_text=raw["procurement_item"]),
        linked_activity=link_activity(wbs_id),
    )
```

This replaces the existing `_build` function body — the only two changed lines are the new `projected_arrival += overrides.get_delta(raw["id"])` and the `root_cause=` line now calling `_root_cause_with_override` instead of the raw `_root_cause(...) if days_at_risk > 0 else None` ternary. Everything else in the function is unchanged.

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_supply_chain_overrides.py -v`
Expected: PASS (5 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/app/supply_chain_overrides.py backend/app/supply_chain.py backend/tests/test_supply_chain_overrides.py
git commit -m "feat: add per-shipment delay override layer"
```

---

### Task 2: Mutation endpoints (adjust-delay, reset-delay)

**Files:**
- Modify: `backend/app/supply_chain.py` (add two routes near the end of the file, after the existing routes starting at line 347)
- Modify: `backend/tests/test_supply_chain_overrides.py` (add HTTP-level tests)

**Interfaces:**
- Consumes: `supply_chain_overrides.apply_delta`, `.reset`, `.get_delta`, `.MAX_CUMULATIVE_DELTA` (Task 1). `audit.record_event(pillar, kind, ref_id, payload, dedup_key=None)` — existing, `backend/app/audit.py:117`.
- Produces: `POST /api/supply-chain/shipments/{shipment_id}/adjust-delay` and `POST /api/supply-chain/shipments/{shipment_id}/reset-delay`, both `response_model=Shipment`. Task 4 (bot) calls these by exact path and body shape.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_supply_chain_overrides.py` (add these imports at the top alongside the existing ones):

```python
from fastapi.testclient import TestClient

from app import audit
from app.main import app

client = TestClient(app)


def test_adjust_delay_endpoint_updates_shipment_and_records_audit_event():
    resp = client.post("/api/supply-chain/shipments/SHP-003/adjust-delay", json={"delta_days": 8})
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "SHP-003"
    assert body["days_at_risk"] >= 8

    events = audit.get_events(pillar="supply_chain", limit=5)
    assert any(e["ref_id"] == "SHP-003" and e["kind"] == "shipment_delay_adjusted" for e in events)


def test_adjust_delay_unknown_shipment_returns_404():
    resp = client.post("/api/supply-chain/shipments/SHP-999/adjust-delay", json={"delta_days": 5})
    assert resp.status_code == 404


def test_adjust_delay_clamps_and_reset_restores():
    before = client.get("/api/supply-chain/shipments/SHP-004").json()["days_at_risk"]

    resp = client.post("/api/supply-chain/shipments/SHP-004/adjust-delay", json={"delta_days": 1000})
    assert resp.status_code == 200
    assert resp.json()["days_at_risk"] == before + overrides.MAX_CUMULATIVE_DELTA

    reset_resp = client.post("/api/supply-chain/shipments/SHP-004/reset-delay")
    assert reset_resp.status_code == 200
    assert reset_resp.json()["days_at_risk"] == before


def test_reset_delay_records_audit_event():
    client.post("/api/supply-chain/shipments/SHP-005/adjust-delay", json={"delta_days": 3})
    client.post("/api/supply-chain/shipments/SHP-005/reset-delay")
    events = audit.get_events(pillar="supply_chain", limit=5)
    assert any(e["ref_id"] == "SHP-005" and e["kind"] == "shipment_delay_reset" for e in events)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_supply_chain_overrides.py -v`
Expected: FAIL — `404 Not Found` on all four new tests (routes don't exist yet).

- [ ] **Step 3: Add the endpoints to `backend/app/supply_chain.py`**

Add this import near the top of the file, alongside the existing `from fastapi import APIRouter, HTTPException` at line 17:

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import audit
```

Add near the end of the file, after the existing route handlers:

```python
class AdjustDelayRequest(BaseModel):
    delta_days: int
    note: str | None = None


@router.post("/shipments/{shipment_id}/adjust-delay", response_model=Shipment)
def adjust_delay(shipment_id: str, body: AdjustDelayRequest) -> Shipment:
    known_ids = {s.id for s in shipments()}
    if shipment_id not in known_ids:
        raise HTTPException(status_code=404, detail=f"Unknown shipment_id: {shipment_id}")

    new_total = overrides.apply_delta(shipment_id, body.delta_days)
    updated = next(s for s in shipments() if s.id == shipment_id)

    audit.record_event(
        "supply_chain",
        "shipment_delay_adjusted",
        shipment_id,
        {
            "delta_days": body.delta_days,
            "new_cumulative_delta": new_total,
            "new_days_at_risk": updated.days_at_risk,
            "note": body.note,
        },
    )
    return updated


@router.post("/shipments/{shipment_id}/reset-delay", response_model=Shipment)
def reset_delay(shipment_id: str) -> Shipment:
    known_ids = {s.id for s in shipments()}
    if shipment_id not in known_ids:
        raise HTTPException(status_code=404, detail=f"Unknown shipment_id: {shipment_id}")

    overrides.reset(shipment_id)
    updated = next(s for s in shipments() if s.id == shipment_id)

    audit.record_event(
        "supply_chain",
        "shipment_delay_reset",
        shipment_id,
        {"new_days_at_risk": updated.days_at_risk},
    )
    return updated
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_supply_chain_overrides.py -v`
Expected: PASS (9 tests total)

- [ ] **Step 5: Commit**

```bash
git add backend/app/supply_chain.py backend/tests/test_supply_chain_overrides.py
git commit -m "feat: add shipment delay adjust/reset endpoints"
```

---

### Task 3: Bot mutation-intent detection (pre-filter, extraction, resolution)

**Files:**
- Create: `telegram-bot/mutation_intent.py`
- Test: `telegram-bot/test_mutation_intent.py`

**Interfaces:**
- Consumes: `llm_client.generate(system: str, user: str, *, temperature: float = 0.1, max_tokens: int = 1000) -> str` — existing, `telegram-bot/llm_client.py:123`.
- Produces: `looks_like_mutation(text: str, known_item_names: list[str]) -> bool`; `MutationIntent` (dataclass: `shipment_id: str`, `delta_days: int`); `MutationUnclear` (dataclass: `considered: list[str]`); `detect_mutation(question_en: str, known_shipments: list[dict]) -> MutationIntent | MutationUnclear` where each dict in `known_shipments` is `{"id": str, "procurement_item": str}`. Task 4 imports all four names.

- [ ] **Step 1: Write the failing tests**

Create `telegram-bot/test_mutation_intent.py`:

```python
"""Tests for telegram-bot/mutation_intent.py
(docs/superpowers/specs/2026-07-26-shipment-delay-mutation-design.md)."""
from __future__ import annotations

from unittest.mock import patch

from mutation_intent import MutationIntent, MutationUnclear, detect_mutation, looks_like_mutation

KNOWN_SHIPMENTS = [
    {"id": "SHP-001", "procurement_item": "DRUPS 2.5MW"},
    {"id": "SHP-002", "procurement_item": "LV switchgear 4000A"},
]
KNOWN_ITEM_NAMES = [s["procurement_item"] for s in KNOWN_SHIPMENTS]


def test_looks_like_mutation_true_with_id_and_verb():
    assert looks_like_mutation("delay SHP-002 by 10 days", KNOWN_ITEM_NAMES) is True


def test_looks_like_mutation_true_with_item_name_and_verb():
    assert looks_like_mutation("the DRUPS shipment is coming in 5 days early", KNOWN_ITEM_NAMES) is True


def test_looks_like_mutation_false_without_delay_verb():
    assert looks_like_mutation("what is the status of SHP-002?", KNOWN_ITEM_NAMES) is False


def test_looks_like_mutation_false_without_shipment_reference():
    assert looks_like_mutation("the project schedule slipped a bit", KNOWN_ITEM_NAMES) is False


def test_detect_mutation_high_confidence_exact_id():
    with patch("mutation_intent.generate", return_value='{"shipment_id": "SHP-002", "delta_days": 10, "confidence": "high"}'):
        result = detect_mutation("delay SHP-002 by 10 days", KNOWN_SHIPMENTS)
    assert result == MutationIntent(shipment_id="SHP-002", delta_days=10)


def test_detect_mutation_high_confidence_fuzzy_name():
    with patch("mutation_intent.generate", return_value='{"shipment_id": "DRUPS", "delta_days": -5, "confidence": "high"}'):
        result = detect_mutation("the DRUPS shipment is 5 days early", KNOWN_SHIPMENTS)
    assert result == MutationIntent(shipment_id="SHP-001", delta_days=-5)


def test_detect_mutation_low_confidence_returns_unclear():
    with patch("mutation_intent.generate", return_value='{"shipment_id": "SHP-002", "delta_days": 10, "confidence": "low"}'):
        result = detect_mutation("delay that thing by 10 days", KNOWN_SHIPMENTS)
    assert isinstance(result, MutationUnclear)


def test_detect_mutation_malformed_json_returns_unclear():
    with patch("mutation_intent.generate", return_value="not json at all"):
        result = detect_mutation("delay SHP-002 by 10 days", KNOWN_SHIPMENTS)
    assert isinstance(result, MutationUnclear)


def test_detect_mutation_empty_llm_response_returns_unclear():
    with patch("mutation_intent.generate", return_value=""):
        result = detect_mutation("delay SHP-002 by 10 days", KNOWN_SHIPMENTS)
    assert isinstance(result, MutationUnclear)


def test_detect_mutation_unresolvable_shipment_name_returns_unclear():
    with patch("mutation_intent.generate", return_value='{"shipment_id": "some totally unknown thing", "delta_days": 10, "confidence": "high"}'):
        result = detect_mutation("delay the mystery shipment by 10 days", KNOWN_SHIPMENTS)
    assert isinstance(result, MutationUnclear)
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `telegram-bot/`, with `.venv` active): `python -m pytest test_mutation_intent.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mutation_intent'`

- [ ] **Step 3: Create `telegram-bot/mutation_intent.py`**

```python
"""Detects and resolves "change this shipment's delay" intent from natural
language. The LLM only ever proposes a candidate {shipment_id, delta_days}
as JSON — Python is the only code that validates a shipment ID against the
real list and decides whether the intent is usable. Same "LLM reads a spec,
Python decides" principle as the rest of this project.
See docs/superpowers/specs/2026-07-26-shipment-delay-mutation-design.md.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from llm_client import generate

_DELAY_VERB_RE = re.compile(
    r"\b(delay(ed)?|late|early|push(ed)?\s+back|move(d)?\s+up|slip(ped)?|advance(d)?)\b",
    re.IGNORECASE,
)
_SHIPMENT_ID_RE = re.compile(r"\bSHP-\d+\b", re.IGNORECASE)


def looks_like_mutation(text: str, known_item_names: list[str]) -> bool:
    if not _DELAY_VERB_RE.search(text):
        return False
    if _SHIPMENT_ID_RE.search(text):
        return True
    lowered = text.lower()
    return any(name.lower() in lowered for name in known_item_names)


@dataclass(frozen=True)
class MutationIntent:
    shipment_id: str
    delta_days: int


@dataclass(frozen=True)
class MutationUnclear:
    considered: list[str]


def _extract(question_en: str, known_shipments: list[dict]) -> dict | None:
    shipment_list_text = "\n".join(f"- {s['id']}: {s['procurement_item']}" for s in known_shipments)
    system = (
        "You extract a shipment-delay-adjustment intent from a message. "
        "Known shipments:\n" + shipment_list_text + "\n\n"
        "Return ONLY strict JSON, no other text: "
        '{"shipment_id": "<the SHP-xxx id if stated, otherwise your best-guess '
        'shipment name>", "delta_days": <signed integer, positive = more delay, '
        'negative = earlier>, "confidence": "high" or "low"}. '
        'Use "low" confidence if you are not reasonably sure which shipment is meant.'
    )
    raw = generate(system, question_en, temperature=0, max_tokens=200)
    if not raw:
        return None

    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.removeprefix("json").strip()
    try:
        data = json.loads(cleaned)
        return {
            "shipment_id": str(data["shipment_id"]),
            "delta_days": int(data["delta_days"]),
            "confidence": str(data.get("confidence", "low")),
        }
    except (json.JSONDecodeError, KeyError, ValueError, TypeError):
        return None


def _resolve_shipment_id(guess: str, known_shipments: list[dict]) -> str | None:
    guess_upper = guess.strip().upper()
    for s in known_shipments:
        if s["id"].upper() == guess_upper:
            return s["id"]

    guess_lower = guess.strip().lower()
    matches = [
        s["id"]
        for s in known_shipments
        if guess_lower in s["procurement_item"].lower() or s["procurement_item"].lower() in guess_lower
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def detect_mutation(question_en: str, known_shipments: list[dict]) -> MutationIntent | MutationUnclear:
    extracted = _extract(question_en, known_shipments)
    if extracted is not None and extracted["confidence"] == "high":
        shipment_id = _resolve_shipment_id(extracted["shipment_id"], known_shipments)
        if shipment_id is not None:
            return MutationIntent(shipment_id=shipment_id, delta_days=extracted["delta_days"])

    return MutationUnclear(considered=[s["id"] for s in known_shipments])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest test_mutation_intent.py -v`
Expected: PASS (10 tests)

- [ ] **Step 5: Commit**

```bash
git add telegram-bot/mutation_intent.py telegram-bot/test_mutation_intent.py
git commit -m "feat: add bot-side mutation intent detection"
```

---

### Task 4: Wire mutation flow into the bot (pending confirmation, apply, voice-cancels-pending)

**Files:**
- Modify: `telegram-bot/bot.py`

**Interfaces:**
- Consumes: `mutation_intent.looks_like_mutation`, `.detect_mutation`, `.MutationIntent`, `.MutationUnclear` (Task 3). Backend routes `GET /api/supply-chain/shipments`, `GET /api/supply-chain/shipments/{id}`, `POST /api/supply-chain/shipments/{id}/adjust-delay` (Task 2).
- No automated test for this task — matches the spec's explicit scope decision (§7): manual verification only, consistent with how the rest of the bot was verified in this project. Step-by-step manual verification is Step 3 below.

- [ ] **Step 1: Add imports and module-level state**

In `telegram-bot/bot.py`, add to the existing import block (alongside `from context import ...` and `from answerer import ...`):

```python
from mutation_intent import MutationIntent, MutationUnclear, detect_mutation, looks_like_mutation
```

Add this near the top-level constants, alongside `_CACHE_MAX` / `_reply_cache`:

```python
# --------------------------------------------------------------------------- #
# Shipment mutation — pending per-chat confirmation state. In-memory only,
# same lifetime as the reply cache; resets on bot restart.
# --------------------------------------------------------------------------- #
_PENDING_TTL_SECONDS = 300.0
_pending_mutations: dict[int, dict] = {}
_YES_WORDS = {"yes", "y", "yeah", "yep", "confirm", "correct", "ok", "okay", "sure"}
_NO_WORDS = {"no", "n", "nope", "cancel", "nvm", "never mind"}
```

- [ ] **Step 2: Add the mutation helper functions**

Add these functions after `_get_answer` (which ends around what is currently line 178, right before the "Telegram handlers" section comment):

```python
# --------------------------------------------------------------------------- #
# Shipment mutation pipeline
# --------------------------------------------------------------------------- #
def _get_known_shipments(backend_url: str) -> list[dict]:
    try:
        with httpx.Client(base_url=backend_url) as client:
            r = client.get("/api/supply-chain/shipments", timeout=10.0)
            r.raise_for_status()
            data = r.json()
        return [{"id": s["id"], "procurement_item": s["procurement_item"]} for s in data]
    except Exception:
        log.exception("Failed to fetch known shipments")
        return []


def _get_current_days_at_risk(backend_url: str, shipment_id: str) -> int:
    try:
        with httpx.Client(base_url=backend_url) as client:
            r = client.get(f"/api/supply-chain/shipments/{shipment_id}", timeout=10.0)
            r.raise_for_status()
            return int(r.json().get("days_at_risk", 0))
    except Exception:
        log.exception("Failed to fetch current days_at_risk for %s", shipment_id)
        return 0


async def _apply_mutation(update: Update, shipment_id: str, delta_days: int) -> None:
    try:
        with httpx.Client(base_url=BACKEND_URL) as client:
            resp = client.post(
                f"/api/supply-chain/shipments/{shipment_id}/adjust-delay",
                json={"delta_days": delta_days},
                timeout=30.0,
            )
            resp.raise_for_status()
            updated = resp.json()
    except Exception:
        log.exception("Failed to apply shipment mutation")
        await update.message.reply_text(
            f"Couldn't apply that change to {shipment_id} — the backend request failed. Nothing was changed."
        )
        return

    fetch_context(BACKEND_URL, force=True)
    await update.message.reply_text(
        f"Done — {shipment_id} is now {updated['days_at_risk']}d at risk. Logged to the audit trail."
    )


async def _handle_pending_confirmation(update: Update, chat_id: int, text: str) -> bool:
    """Returns True if this message was consumed as a reply to a pending mutation."""
    pending = _pending_mutations.get(chat_id)
    if pending is None:
        return False
    if time.monotonic() - pending["created_at"] > _PENDING_TTL_SECONDS:
        del _pending_mutations[chat_id]
        return False

    word = text.strip().lower()
    if word in _YES_WORDS:
        del _pending_mutations[chat_id]
        await _apply_mutation(update, pending["shipment_id"], pending["delta_days"])
        return True
    if word in _NO_WORDS:
        del _pending_mutations[chat_id]
        await update.message.reply_text("Cancelled — no change made.")
        return True

    del _pending_mutations[chat_id]
    return False


async def _try_start_mutation(update: Update, chat_id: int, question_en: str) -> bool:
    """Returns True if this message was handled as a (candidate) mutation request."""
    known = _get_known_shipments(BACKEND_URL)
    if not known:
        return False
    if not looks_like_mutation(question_en, [s["procurement_item"] for s in known]):
        return False

    result = detect_mutation(question_en, known)
    if isinstance(result, MutationUnclear):
        candidates = ", ".join(f"{s['id']} ({s['procurement_item']})" for s in known[:5])
        await update.message.reply_text(
            f"Not sure which shipment you mean. Known shipments: {candidates}. "
            'Try again with the exact ID, e.g. "delay SHP-002 by 10 days".'
        )
        return True

    assert isinstance(result, MutationIntent)
    current_days = _get_current_days_at_risk(BACKEND_URL, result.shipment_id)
    new_days = max(0, current_days + result.delta_days)
    item_name = next((s["procurement_item"] for s in known if s["id"] == result.shipment_id), result.shipment_id)

    _pending_mutations[chat_id] = {
        "shipment_id": result.shipment_id,
        "delta_days": result.delta_days,
        "created_at": time.monotonic(),
    }
    await update.message.reply_text(
        f"{result.shipment_id} — {item_name}: {current_days}d at risk → {new_days}d at risk. Confirm? (yes/no)"
    )
    return True
```

- [ ] **Step 3: Wire the new order into `handle_text` and `handle_voice`**

Replace the existing `handle_text` function:

```python
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text or ""
    chat_id = update.effective_chat.id

    if await _handle_pending_confirmation(update, chat_id, text):
        return

    question_en = translate_to_english(text)

    if await _try_start_mutation(update, chat_id, question_en):
        return

    await _respond(update, text, question_en)
```

Replace the existing `handle_voice` function:

```python
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if chat_id in _pending_mutations:
        del _pending_mutations[chat_id]
        await update.message.reply_text(
            "(Cancelled the pending confirmation — voice notes don't confirm changes.)"
        )

    tg_file = await update.message.voice.get_file()
    ogg_bytes = bytes(await tg_file.download_as_bytearray())

    try:
        transcript = transcribe_voice(ogg_bytes)
    except Exception:
        log.exception("ElevenLabs STT failed")
        await update.message.reply_text("Sorry, I couldn't understand that voice note — could you send it as text?")
        return

    if not transcript.strip():
        await update.message.reply_text("Sorry, I couldn't understand that voice note — could you send it as text?")
        return

    question_en = translate_to_english(transcript)

    if await _try_start_mutation(update, chat_id, question_en):
        return

    await _respond(update, transcript, question_en)
```

- [ ] **Step 4: Syntax-check**

Run (from `telegram-bot/`): `python3 -c "import ast; ast.parse(open('bot.py').read()); print('syntax ok')"`
Expected: `syntax ok`

- [ ] **Step 5: Restart backend and bot, verify manually**

1. Restart the backend (`kill` the running uvicorn PID, relaunch via `backend/run.sh` in the background) so it picks up Task 1/2's changes.
2. Restart the bot (`kill` the running bot.py PID, relaunch via `telegram-bot/run.sh` in the background) so it picks up Task 3/4's changes. Expect the ~3.5 min pre-warm sequence from the earlier session to run again.
3. From Telegram, send: `delay SHP-002 by 10 days`. Expect a preview message ("SHP-002 — LV switchgear 4000A: Xd at risk → (X+10)d at risk. Confirm? (yes/no)") within the normal 5s+ response window.
4. Reply `yes`. Expect "Done — SHP-002 is now (X+10)d at risk. Logged to the audit trail."
5. Ask a normal question referencing supply chain (e.g. "what's at risk in the supply chain?") and confirm the new number for SHP-002 shows up — proves the override actually propagated through `fetch_context`.
6. Check `GET http://localhost:8000/api/audit` (or the backend log) for a `shipment_delay_adjusted` event with `ref_id: "SHP-002"`.
7. Send another delay message, then reply `no` — confirm it says "Cancelled — no change made." and a follow-up `GET /api/supply-chain/shipments/SHP-002` shows no further change.
8. Send a delay message, then immediately send a **voice note** instead of replying yes/no — confirm the bot says the pending confirmation was cancelled, then answers the voice note as a normal new message.

- [ ] **Step 6: Commit**

```bash
git add telegram-bot/bot.py
git commit -m "feat: wire shipment delay mutation into the bot's message pipeline"
```
