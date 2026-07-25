"""Solana devnet notarization (plan §E) — the anti-corruption proof. Anchors
an audit event's `content_hash` on-chain via the SPL Memo program (a tiny
transaction whose memo IS the hash, from a funded devnet keypair) so anyone
can independently verify a record wasn't altered after the fact, without
trusting SiteMind's own database.

Deliberately simple: no custom on-chain program to author/deploy. The Memo
program (`MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr`) is already deployed on
every cluster including devnet — we just send it a memo instruction. Devnet
only, zero real cost.

Gated on `config.SOLANA_ENABLED` (default off) — every function no-ops
`{"status": "disabled"}` when off, so the rest of the app never depends on a
Solana RPC being reachable.
"""
from __future__ import annotations

from typing import Any

from . import config

MEMO_PROGRAM_ID = "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr"


def _keypair():
    from solders.keypair import Keypair

    return Keypair.from_base58_string(config.SOLANA_SECRET_KEY)


async def anchor_hash(hash_hex: str) -> dict[str, Any]:
    """Send a single-instruction transaction (SPL Memo, data=hash_hex) from
    the configured devnet keypair. Returns {status:"anchored", tx_sig, slot,
    cluster} on success, {status:"error", detail} on any failure — never
    raises. {status:"disabled"} if SOLANA_ENABLED is off or no key is set."""
    if not config.SOLANA_ENABLED:
        return {"status": "disabled"}
    if not config.SOLANA_SECRET_KEY:
        return {"status": "error", "detail": "SOLANA_SECRET_KEY not configured"}

    try:
        from solana.rpc.async_api import AsyncClient
        from solana.rpc.commitment import Confirmed
        from solders.instruction import Instruction
        from solders.message import Message
        from solders.pubkey import Pubkey
        from solders.transaction import VersionedTransaction

        kp = _keypair()
        memo_program = Pubkey.from_string(MEMO_PROGRAM_ID)
        instruction = Instruction(memo_program, hash_hex.encode("utf-8"), [])

        async with AsyncClient(config.SOLANA_RPC_URL) as client:
            blockhash_resp = await client.get_latest_blockhash()
            blockhash = blockhash_resp.value.blockhash
            message = Message.new_with_blockhash([instruction], kp.pubkey(), blockhash)
            tx = VersionedTransaction(message, [kp])

            send_resp = await client.send_transaction(tx)
            tx_sig = send_resp.value
            await client.confirm_transaction(tx_sig, commitment=Confirmed)

            status_resp = await client.get_signature_statuses([tx_sig])
            slot = None
            info = status_resp.value[0] if status_resp.value else None
            if info is not None:
                slot = info.slot

        return {
            "status": "anchored",
            "tx_sig": str(tx_sig),
            "slot": slot,
            "cluster": config.SOLANA_CLUSTER,
        }
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


def _extract_memo_bytes_base64(tx_field) -> list[bytes]:
    """Extract every instruction's raw data from a `get_transaction(...,
    encoding="base64")` response's `.transaction.transaction` field. Verified
    live against a real anchored devnet transaction: solders' AsyncClient
    already parses this field into a `VersionedTransaction` object (NOT a
    base64 string/tuple, despite the RPC wire format) — handle that directly,
    with base64-string/bytes fallbacks for older client versions. Returns []
    (never raises) if nothing parses."""
    import base64

    from solders.transaction import VersionedTransaction

    txs: list[VersionedTransaction] = []
    if isinstance(tx_field, VersionedTransaction):
        txs.append(tx_field)
    else:
        candidates = []
        # (base64_str, "base64") tuple — solana-py's docs shape for base64 RPC responses.
        if isinstance(tx_field, (tuple, list)) and tx_field:
            candidates.append(tx_field[0])
        # The field IS the base64 string directly.
        if isinstance(tx_field, (str, bytes)):
            candidates.append(tx_field)
        for c in candidates:
            try:
                raw = base64.b64decode(c) if isinstance(c, str) else bytes(c)
                txs.append(VersionedTransaction.from_bytes(raw))
            except Exception:
                continue

    out: list[bytes] = []
    for tx in txs:
        out.extend(bytes(ix.data) for ix in tx.message.instructions)
    return out


def _extract_memo_from_logs(meta) -> list[str]:
    """Fallback: the Memo program logs the memo as `Memo (len N): "<memo>"` —
    verified live against a real anchored transaction. Not the base64 path's
    guaranteed-exact bytes match, so used only if that yields nothing."""
    import re

    logs = getattr(meta, "log_messages", None) or []
    out = []
    for log in logs:
        if "Program log: " not in log:
            continue
        text = log.split("Program log: ", 1)[1]
        m = re.match(r'Memo \(len \d+\): "(.*)"$', text)
        out.append(m.group(1) if m else text)
    return out


async def verify_anchor(hash_hex: str, tx_sig: str) -> bool:
    """Fetch the transaction by signature and confirm a memo instruction's
    RAW DATA equals hash_hex (preferred: decoded from the base64-encoded
    transaction bytes), falling back to string-matching the human-readable
    program log if that decoding doesn't yield a match. Returns False (never
    raises) on any lookup failure, a missing/malformed transaction, or a
    genuine mismatch — the caller treats False identically to "not
    verified", never distinguishing "couldn't check" from "verified false"."""
    if not config.SOLANA_ENABLED or not tx_sig:
        return False
    try:
        from solders.signature import Signature
        from solana.rpc.async_api import AsyncClient

        async with AsyncClient(config.SOLANA_RPC_URL) as client:
            resp = await client.get_transaction(
                Signature.from_string(tx_sig), encoding="base64", max_supported_transaction_version=0
            )
        if resp.value is None:
            return False

        target = hash_hex.encode("utf-8")
        for data in _extract_memo_bytes_base64(resp.value.transaction.transaction):
            if data == target:
                return True
        for memo_text in _extract_memo_from_logs(resp.value.transaction.meta):
            if memo_text == hash_hex:
                return True
        return False
    except Exception:
        return False
