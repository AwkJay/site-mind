"""GET /api/audit* — read access to the append-only audit ledger (`audit.py`),
POST /api/audit/seed to backfill the preloaded demo project's current NCRs so
the ledger isn't empty on stage, and (plan §E) POST .../anchor + .../verify to
notarize an event's content_hash on Solana devnet and independently confirm
it. Always mounted (no feature flag) — `audit.py` degrades to a local JSONL
ledger without MongoDB, and `notary.py` no-ops without SOLANA_ENABLED, so this
router works in every configuration.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from . import audit, notary
from .data_loader import load_submittals
from .schemas import AuditEvent

router = APIRouter(prefix="/api/audit", tags=["audit"])


def _to_event(doc: dict) -> AuditEvent:
    return AuditEvent(
        id=doc["_id"],
        seq=doc.get("seq") or 0,
        created_at=doc["created_at"],
        pillar=doc["pillar"],
        kind=doc["kind"],
        ref_id=doc["ref_id"],
        payload=doc["payload"],
        hashed_fields=doc.get("hashed_fields", doc["payload"]),
        content_hash=doc["content_hash"],
        solana=doc.get("solana") or {"status": "pending"},
    )


@router.get("", response_model=list[AuditEvent])
def list_events(pillar: str | None = None, limit: int = 100) -> list[AuditEvent]:
    return [_to_event(d) for d in audit.get_events(pillar=pillar, limit=limit)]


@router.get("/{event_id}", response_model=AuditEvent)
def get_event(event_id: str) -> AuditEvent:
    doc = audit.get_event(event_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Unknown audit event id: {event_id}")
    return _to_event(doc)


def seed_preloaded() -> int:
    """Idempotent (via content_hash): safe to call repeatedly (a startup hook
    AND a manual endpoint both call this). Records the preloaded project's
    CURRENT NCRs so the ledger has real content without waiting for a live
    upload. Returns the count of genuinely NEW records — several submittals
    legitimately re-produce the same underlying NCR (a param mirrored onto
    both the DBR and a specific shop drawing), and those are correctly
    deduped by content_hash, not double-counted here."""
    # local import: avoid a module cycle at import time
    from .agents.compliance import evaluate, ncr_dedup_key

    new_count = 0
    for s in load_submittals():
        document_id = s.get("Submittal No")
        if not document_id:
            continue
        try:
            result = evaluate(document_id)
        except HTTPException:
            continue
        for ncr in result.ncrs:
            dedup_key = ncr_dedup_key(ncr)
            is_new = not audit.event_exists(ncr.model_dump(), dedup_key=dedup_key)
            audit.record_event("compliance", "ncr", ncr.id, ncr.model_dump(), dedup_key=dedup_key)
            if is_new:
                new_count += 1
    return new_count


@router.post("/seed")
def seed() -> dict:
    return {"new_records": seed_preloaded()}


@router.post("/{event_id}/anchor", response_model=AuditEvent)
async def anchor_event(event_id: str) -> AuditEvent:
    """Anchor this event's content_hash on Solana devnet (on-demand, never on
    every write — devnet latency must never slow the core compliance flow).
    Updates ONLY the `solana` sub-doc; `payload`/`hashed_fields`/`content_hash`
    stay immutable."""
    doc = audit.get_event(event_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Unknown audit event id: {event_id}")
    result = await notary.anchor_hash(doc["content_hash"])
    updated = audit.update_solana(event_id, result)
    return _to_event(updated or doc)


@router.post("/anchor-pending")
async def anchor_pending() -> dict:
    """One-click demo action: anchor every event still `solana.status=="pending"`."""
    anchored = 0
    for doc in audit.get_events(limit=10_000):
        if (doc.get("solana") or {}).get("status") != "pending":
            continue
        result = await notary.anchor_hash(doc["content_hash"])
        audit.update_solana(doc["_id"], result)
        if result.get("status") == "anchored":
            anchored += 1
    return {"anchored": anchored}


@router.post("/{event_id}/verify")
async def verify_event(event_id: str) -> dict:
    """Two independent checks: has the STORED record been tampered with
    (Mongo/JSONL integrity — recompute content_hash from hashed_fields), and
    does the on-chain memo still match (chain integrity, only meaningful once
    anchored).

    `chain_status` is the field to render, not `chain_intact` alone:

      not_anchored — never anchored; there is nothing on-chain to check
      verified     — on-chain memo matches this record's hash
      mismatch     — we READ the chain and it disagrees. Real tamper evidence
      unreachable  — we could not reach the RPC. Says nothing about the record

    `chain_intact` stays for backwards compatibility, but it is null for BOTH
    "not anchored" and "unreachable", which is exactly the ambiguity that made
    a network timeout render as a red "chain mismatch" badge on valid data.
    Never colour a record red on anything but `mismatch`."""
    doc = audit.get_event(event_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Unknown audit event id: {event_id}")
    mongo_intact = audit.verify_integrity(event_id)
    solana = doc.get("solana") or {}
    chain_intact: bool | None = None
    chain_status = "not_anchored"
    if solana.get("status") == "anchored" and solana.get("tx_sig"):
        chain_intact = await notary.verify_anchor(doc["content_hash"], solana["tx_sig"])
        chain_status = {
            True: "verified",
            False: "mismatch",
            None: "unreachable",
        }[chain_intact]
    return {
        "mongo_intact": mongo_intact,
        "chain_intact": chain_intact,
        "chain_status": chain_status,
    }
