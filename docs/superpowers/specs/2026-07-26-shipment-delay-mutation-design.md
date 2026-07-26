# Shipment Delay Mutation — chat-driven supply-chain updates via the Telegram bot

**Date:** 2026-07-26
**Status:** approved, ready for implementation
**Scope:** one new backend mutation endpoint + one new bot conversation flow. No existing read endpoint changes shape.

---

## 1. Goal

A field user tells the Telegram bot, in natural language, that a shipment's arrival has slipped or improved — e.g. "delay SHP-002 by 10 days" or "the DRUPS shipment is coming in 5 days early" — and the bot:

1. resolves which shipment and by how many days,
2. shows a preview and waits for explicit confirmation,
3. applies the change through a real backend endpoint (not a chat-side fake),
4. records it as a tamper-evident audit event,
5. reports back with the updated numbers.

Every other read (`/api/overview`, `/api/cost-risk`, `/api/schedule/risks` via `/api/timeline`) picks up the change automatically because they all recompute from the same in-memory `Shipment` objects — nothing downstream needs to be told separately.

## 2. Non-negotiable constraints (inherited from the project thesis)

| Constraint | How this feature honours it |
|---|---|
| The LLM never computes a verdict | The LLM only extracts `{shipment_id, delta_days}` as structured JSON. Python validates the shipment ID against the real list, does the arithmetic, and is the only thing that writes `_overrides`. |
| No asserted numbers | The bot's preview and confirmation numbers come from the same `Shipment.days_at_risk` computation everything else uses — never separately estimated. |
| Tamper-proof accountability | Every applied mutation is written to the existing `audit.record_event()` ledger — same mechanism as every other auditable event in the system. |
| OFFLINE_MODE is the safe default | The mutation endpoint itself needs no LLM or external API — it's pure Python arithmetic + cache invalidation. Only the bot's natural-language *parsing* step needs an LLM (it already requires one for every other message). |

## 3. Data model — what "delay by N days" actually changes

`Shipment.days_at_risk` (`backend/app/schemas.py:220-239`) is **computed, not stored**:
`days_at_risk = max(0, projected_arrival_day - required_on_site_by)`, rebuilt every time `supply_chain._build()` runs (`backend/app/supply_chain.py:222-246`). There is no field to "set" directly — a delay has to shift `projected_arrival_day` and let the existing computation redo the rest.

`root_cause` (`supply_chain.py:241`) is derived independently, from the *raw* milestone data only (`_root_cause()`, `supply_chain.py:109-118`) — it does not know about overrides. Left alone, a shipment pushed from 0 to 10 days at risk by an override would show `days_at_risk: 10` with `root_cause: null`, which reads as a bug. The build function must append an override note to `root_cause` when an override is active (§4.2).

## 4. Backend design

### 4.1 New module: `backend/app/supply_chain_overrides.py`

Mirrors `clock.py`'s existing pattern exactly — same file already does this for the whole project's simulated "today", so this isn't a new architectural idea, just the same one applied per-shipment instead of globally.

```python
_overrides: dict[str, int] = {}   # shipment_id -> cumulative delta_days (+ = later, - = earlier)
MAX_CUMULATIVE_DELTA = 60         # same bound clock.py uses for its own offset

def get_delta(shipment_id: str) -> int: ...
def apply_delta(shipment_id: str, delta_days: int) -> int:   # returns new cumulative total
    # clamps to [-MAX_CUMULATIVE_DELTA, +MAX_CUMULATIVE_DELTA], then clears caches
def reset(shipment_id: str | None = None) -> None:           # None = clear all overrides
```

`apply_delta` calls a `_clear_downstream_caches()` that clears exactly the three caches `clock.py:46-49` already clears for `supply_chain`: `shipments.cache_clear()`, `risks.cache_clear()`, `alerts.cache_clear()`. (`schedule.risks` and `timeline.all_events` are **not** cleared here — they don't depend on supply-chain data; confirmed `schedule.py` has no supply_chain import.)

### 4.2 One-line change to `_build()` (`supply_chain.py:222-246`)

```python
projected_arrival = final_planned + delay if delay > 0 else final_planned
projected_arrival += overrides.get_delta(raw["id"])                     # NEW
days_at_risk = max(0, projected_arrival - required)
...
root_cause=_root_cause_with_override(raw, days_at_risk, overrides.get_delta(raw["id"]))  # NEW wrapper
```

`_root_cause_with_override` calls the existing `_root_cause()` and, if an override is active, appends `f"; manually adjusted {delta:+d}d via field update"` (or returns that string standalone if `_root_cause()` returned `None`).

### 4.3 New endpoint — `backend/app/supply_chain.py`

```
POST /api/supply-chain/shipments/{shipment_id}/adjust-delay
Body: {"delta_days": int, "note": str | None = None}
```

1. 404 if `shipment_id` isn't in `shipments()`.
2. Calls `overrides.apply_delta(shipment_id, delta_days)`.
3. Records `audit.record_event("supply_chain", "shipment_delay_adjusted", shipment_id, {"delta_days": delta_days, "new_cumulative_delta": <total>, "new_days_at_risk": <int>, "note": note}, dedup_key=None)` — no dedup key, since repeat identical adjustments are legitimate distinct events, not duplicates of one action.
4. Returns the updated `Shipment` (same shape as `GET /api/supply-chain/shipments/{id}`, so the bot can read `days_at_risk` straight off the response).

### 4.4 Reset

`POST /api/supply-chain/shipments/{shipment_id}/reset-delay` — clears that shipment's override, same cache-clear + audit-event treatment (`kind="shipment_delay_reset"`). Needed for demo repeatability (undo a mutation without restarting the backend) and for the test suite.

## 5. Bot design

### 5.0 Message handling order

Every incoming text message is checked in this order, top to bottom, stopping at the first match:

1. **Pending mutation exists for this `chat_id` and hasn't expired?** → handled as yes/no per §5.3. This takes priority even if the new message also happens to look like a fresh mutation request — a reply to "confirm?" is answered as a reply, never re-parsed as a new command. Voice messages skip this check entirely (§5.3).
2. **No pending mutation. Keyword pre-filter (§5.1) hits?** → run extraction (§5.2).
3. **Neither** → normal Q&A pipeline, unchanged.

### 5.1 Keyword pre-filter (no LLM call)

`telegram-bot/mutation_intent.py`, checked at the top of `handle_text`/`handle_voice` before the normal Q&A pipeline:

- Delay-verb regex: `\b(delay|late|early|push(ed)? back|move(d)? up|slip(ped)?|advance)\b`
- Shipment-reference regex: `SHP-\d+` **or** any known procurement-item keyword (drups, switchgear, busway, cladding, ...) pulled from the already-cached context, not hardcoded.

Only if **both** match does the extraction step (§5.2) run — every other message takes the existing, unchanged path, so normal Q&A latency is untouched.

### 5.2 Structured extraction (one LLM call, only on a pre-filter hit)

Reuses `llm_client.generate()` (already the bot's only LLM interface) with a dedicated system prompt: given the real shipment list (id + procurement_item, pulled from the existing cached context), extract `{"shipment_id": "<id or best-guess name>", "delta_days": <signed int>, "confidence": "high"|"low"}` as strict JSON, nothing else.

Python then does the actual resolution, never the LLM:
- Exact `SHP-\d+` match against the real ID list → use it.
- Otherwise fuzzy-match the guessed text against known `procurement_item` strings (simple substring/token-overlap match, not another LLM call).
- No confident match, or `confidence: "low"` → reply asking which shipment, listing the candidates it considered, and stop (no pending state set).

### 5.3 Preview + confirmation (per-chat pending state)

`telegram-bot/bot.py` gets one new module-level dict: `_pending_mutations: dict[int, PendingMutation]` keyed by `chat_id`, where `PendingMutation = {shipment_id, delta_days, created_at}`. TTL 5 minutes, checked on every use (not a background sweep — simplest correct approach for in-memory, single-process state).

- On a resolved mutation intent: look up the shipment's **current** `days_at_risk` from the bot's own cached context (already fetched every message; no extra network call), compute the preview total (`current + delta_days`, clamped ≥ 0), store it in `_pending_mutations[chat_id]`, and reply:
  `"SHP-002 — DRUPS 2.5MW: 5d at risk → 15d at risk. Confirm? (yes/no)"`
- **Every** incoming text message first checks: is there a live (non-expired) pending mutation for this `chat_id`? If yes, the message is interpreted as yes/no (simple keyword match: yes/y/confirm/correct vs. no/n/cancel/nvm), **not** run through the normal Q&A or a new mutation-intent check. Anything that isn't a recognizable yes/no clears the pending state and falls through to the normal pipeline (treated as "never mind, new question"), rather than blocking the user.
- **Voice messages never confirm a pending mutation** — a misheard "yes" applying an unintended shipment change is exactly the failure mode confirmation exists to prevent. A voice note while a mutation is pending gets transcribed and treated as a fresh message (clearing the pending state), with a one-line note that the pending confirmation was cancelled.

### 5.4 Applying it

On "yes": `POST` to the new endpoint, force-refresh the bot's own context cache (`fetch_context(BACKEND_URL, force=True)` — already exists, used today by `/status`), and reply with the confirmed before/after plus "logged to the audit trail." On any request failure, report it plainly and leave the shipment unchanged (no partial-apply state possible — the endpoint call either succeeds or it doesn't touch `_overrides` at all).

## 6. Error handling

| Case | Behavior |
|---|---|
| Unknown/unresolvable shipment reference | Ask for clarification, list real shipment IDs + names it considered. No pending state set. |
| `delta_days` would push cumulative total past ±60 | Endpoint clamps and returns the clamped value; bot reports the actual applied number, not the requested one. |
| Backend unreachable when applying | Report the failure plainly; pending state is cleared (no silent retry). |
| Second mutation-shaped message arrives while one is already pending | New request replaces the old pending one (last-intent-wins) with a fresh preview — no stacking. |
| Voice note arrives while a mutation is pending | Pending mutation is cancelled (see §5.3); transcribed message handled as a normal new message. |

## 7. Testing

- **Backend** (`backend/tests/test_supply_chain_overrides.py`, matching existing test file conventions): apply a delta → assert `days_at_risk` and `root_cause` both reflect it; assert `/api/cost-risk` and `/api/overview` (called directly, not mocked) reflect the new number with no separate cache-clear needed; assert clamping at ±60; assert `reset-delay` restores the original computed value; assert an audit event is recorded via `audit.get_events`.
- **Bot**: manual verification only, consistent with how the rest of the bot was verified — no existing test harness for Telegram interactions in this repo, and building one is out of scope here.

## 8. Out of scope

- Multi-shipment batch updates in one message ("delay all switchgear shipments").
- Editing anything other than the delay (e.g., changing `current_stage`, `root_cause` text directly, supplier info).
- Undo via chat ("actually revert that") beyond the explicit reset endpoint — not wired into the bot's conversation flow in this pass.
- Persisting overrides across a backend restart (explicitly rejected in brainstorming — in-memory only, same lifetime as `clock.py`'s offset).
