"""Append-only audit ledger (plan §D) — the project memory flat-file
recomputation never had. Persists every finalized compliance decision (NCR +
cited clause + source span + provenance + timestamp + content hash) so *when*
a finding first appeared is recorded, not just recomputed fresh each request.

Two backends, same shape:
  - MongoDB Atlas (`config.MONGODB_URI` set): a real `audit_events` collection
    with a unique index on `content_hash` — inserting the identical decision
    twice is a no-op (returns the existing doc), never a duplicate.
  - Local JSONL fallback (`backend/data/audit_events.jsonl`): used
    automatically when `MONGODB_URI` is unset OR the connection fails at
    startup. Same content_hash idempotency, same doc shape, so callers and the
    UI never need to know which backend answered. Checked once per process
    (never retried per-request) — a hung Mongo must never slow down a
    compliance ingest.

Append-only discipline: nothing here ever updates or deletes `payload` or
`content_hash` after insert. `update_solana()` is the only mutation this
module exposes, and it touches ONLY the `solana` sub-doc (workstream E's
notarization status) — the decision record itself stays immutable.
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
import uuid
from typing import Optional

from . import config

logger = logging.getLogger(__name__)

_JSONL_PATH = config.DATA_DIR / "audit_events.jsonl"
_lock = threading.Lock()

_collection = None
_mongo_checked = False


def backend_name() -> str:
    """Which backend is actually answering — reflects REAL connectivity (a
    Mongo connection attempt/ping), not just whether MONGODB_URI is set."""
    return "mongodb" if _mongo_collection() is not None else "local_jsonl"


def content_hash(payload: dict) -> str:
    """SHA-256 over CANONICAL JSON (sorted keys, no whitespace) — deterministic,
    so the same decision always hashes the same way. This is exactly what
    Solana (workstream E) anchors on-chain."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _mongo_collection():
    """Lazy pymongo client — returns None (-> JSONL fallback) if MONGODB_URI is
    unset or the connection fails. Checked exactly once per process."""
    global _collection, _mongo_checked
    if _mongo_checked:
        return _collection
    _mongo_checked = True
    if not config.MONGODB_URI:
        return None
    try:
        import pymongo

        client = pymongo.MongoClient(config.MONGODB_URI, serverSelectionTimeoutMS=3000)
        client.admin.command("ping")  # fail fast if unreachable
        collection = client[config.MONGODB_DB]["audit_events"]
        collection.create_index("content_hash", unique=True)
        _collection = collection
    except Exception:
        logger.warning("audit: MongoDB unreachable; falling back to local JSONL.", exc_info=True)
        _collection = None
    return _collection


def _jsonl_lines() -> list[dict]:
    if not _JSONL_PATH.exists():
        return []
    return [json.loads(line) for line in _JSONL_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]


def _jsonl_record(doc: dict) -> dict:
    """Idempotent append: returns the existing doc if this content_hash is
    already present, else appends and returns the new doc. `seq` is assigned
    under the same lock so it reflects the JSONL ledger's own line count."""
    with _lock:
        existing_lines = _jsonl_lines()
        for existing in existing_lines:
            if existing.get("content_hash") == doc["content_hash"]:
                return existing
        doc = {**doc, "seq": len(existing_lines) + 1}
        _JSONL_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _JSONL_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(doc) + "\n")
        return doc


def event_exists(payload: dict, dedup_key: Optional[dict] = None) -> bool:
    """Whether this exact decision (by content_hash) is already recorded —
    lets a caller like `seed_preloaded()` report an honest new-vs-already-seen
    count instead of a raw "NCRs processed" tally. See `record_event` for what
    `dedup_key` is for."""
    h = content_hash(dedup_key if dedup_key is not None else payload)
    collection = _mongo_collection()
    if collection is not None:
        try:
            return collection.find_one({"content_hash": h}) is not None
        except Exception:
            logger.warning("audit: Mongo read failed; falling back to local JSONL.", exc_info=True)
    return any(d.get("content_hash") == h for d in _jsonl_lines())


def record_event(pillar: str, kind: str, ref_id: str, payload: dict, dedup_key: Optional[dict] = None) -> dict:
    """Record one finalized decision. Idempotent via content_hash over
    `dedup_key` (or `payload` itself if `dedup_key` is omitted) — recording
    the identical decision twice returns the SAME stored doc. Never raises:
    any Mongo failure at write time falls back to the JSONL ledger.

    `dedup_key` exists because `payload` may legitimately contain non-
    deterministic prose (an LLM's restatement of a finding can differ,
    word-for-word, across two calls with the exact same underlying decision)
    — callers whose payload mixes deterministic decision fields with LLM
    prose should pass a `dedup_key` containing only the deterministic fields,
    so re-evaluating the SAME decision is correctly recognised as a repeat,
    not hashed (and stored) as a new event every time the LLM rephrases it."""
    hashed_fields = dedup_key if dedup_key is not None else payload
    h = content_hash(hashed_fields)
    doc = {
        "_id": f"AUD-{uuid.uuid4().hex[:12]}",
        "seq": None,
        "created_at": time.time(),
        "pillar": pillar,
        "kind": kind,
        "ref_id": ref_id,
        "payload": payload,
        # The EXACT dict content_hash was computed over — kept separately
        # from `payload` (which may carry non-deterministic prose) so
        # `verify_integrity()` can recompute the same hash later and get a
        # real match, not a guaranteed mismatch from hashing a superset.
        "hashed_fields": hashed_fields,
        "content_hash": h,
        "solana": {"status": "pending"},
    }

    collection = _mongo_collection()
    if collection is not None:
        try:
            existing = collection.find_one({"content_hash": h})
            if existing:
                return existing
            doc["seq"] = collection.count_documents({}) + 1
            collection.insert_one(dict(doc))
            return doc
        except Exception:
            logger.warning("audit: Mongo write failed; falling back to local JSONL.", exc_info=True)

    return _jsonl_record(doc)


def verify_integrity(event_id: str) -> Optional[bool]:
    """The Mongo-side half of workstream E's anti-corruption proof:
    recompute content_hash over the STORED `hashed_fields` and compare to
    the STORED `content_hash`. True unless someone has directly edited
    `hashed_fields` or `content_hash` in the database since insert (the
    ledger is append-only in normal operation, so this should never go false
    except via an out-of-band tamper). Returns None if the event doesn't
    exist. Note: fields deliberately excluded from `hashed_fields` (LLM
    prose, e.g. NCR `finding`/`why_it_matters`) are NOT covered by this
    check — the guarantee is over the DECISION, not its wording."""
    doc = get_event(event_id)
    if doc is None:
        return None
    return content_hash(doc.get("hashed_fields", doc["payload"])) == doc["content_hash"]


def get_events(pillar: Optional[str] = None, limit: int = 100) -> list[dict]:
    collection = _mongo_collection()
    if collection is not None:
        try:
            query = {"pillar": pillar} if pillar else {}
            return list(collection.find(query).sort("seq", -1).limit(limit))
        except Exception:
            logger.warning("audit: Mongo read failed; falling back to local JSONL.", exc_info=True)

    docs = [d for d in _jsonl_lines() if not pillar or d.get("pillar") == pillar]
    docs.sort(key=lambda d: d.get("seq", 0), reverse=True)
    return docs[:limit]


def get_event(event_id: str) -> Optional[dict]:
    collection = _mongo_collection()
    if collection is not None:
        try:
            doc = collection.find_one({"_id": event_id})
            if doc:
                return doc
        except Exception:
            logger.warning("audit: Mongo read failed; falling back to local JSONL.", exc_info=True)

    for d in _jsonl_lines():
        if d.get("_id") == event_id:
            return d
    return None


def update_solana(event_id: str, solana: dict) -> Optional[dict]:
    """Mutate ONLY the `solana` sub-doc (workstream E's notary). `payload` and
    `content_hash` are never touched here — append-only stays true."""
    collection = _mongo_collection()
    if collection is not None:
        try:
            collection.update_one({"_id": event_id}, {"$set": {"solana": solana}})
            return collection.find_one({"_id": event_id})
        except Exception:
            logger.warning("audit: Mongo update failed; falling back to local JSONL.", exc_info=True)

    with _lock:
        lines = _jsonl_lines()
        updated = None
        for d in lines:
            if d.get("_id") == event_id:
                d["solana"] = solana
                updated = d
        if updated is None:
            return None
        with _JSONL_PATH.open("w", encoding="utf-8") as fh:
            for d in lines:
                fh.write(json.dumps(d) + "\n")
        return updated
