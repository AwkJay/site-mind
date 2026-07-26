"""Shared real-document ingest pipeline: bytes -> text -> extracted params -> upload id.

Factored out of `agents/compliance.py:ingest_document()` so two entry points run the
IDENTICAL real pipeline instead of two copies drifting apart:
  - POST /api/compliance/ingest        (raw user upload, any filename)
  - POST /api/documents/{doc_id}/ingest (a filesystem-backed demo doc — see documents.py)

No shortcuts for the demo-doc path: it reads the real file bytes off disk and goes
through the exact same extract_text -> llm_extract.extract_params (span-verified,
falls back to pure regex offline/on any LLM failure) -> register_upload chain.
"""
from __future__ import annotations

import hashlib

from fastapi import HTTPException

from . import ingest, llm_extract

# The 2 pristine demo files (see docs, "golden demo path") — pinned by exact
# content sha256 so their cached LLM prose (produced by the Gemini provider)
# never drifts. Any OTHER document (a genuinely new upload, or even an edited
# copy of one of these two) is NOT in this set and routes through the IAMHC
# provider instead (see app/agents/compliance.py's per-document provider pick,
# kept in sync with this constant — do not import one into the other, it
# risks a circular import for the sake of deduping two strings).
_PINNED_DEMO_HASHES = {
    "85f3a534537f6daf83514ca2af2e3b6cccf8e4dbd2be479cc09bb2b6937f8140",
    "ffeb88d6621a964930a465c23ed9d187ff61285ab5ba746b7f397ddd9dcbcbd9",
}


async def run_ingest_pipeline(filename: str, content: bytes) -> dict:
    """Read real bytes, extract params, register an upload id.

    Raises HTTPException(400) for an unsupported file type and HTTPException(422)
    when no extractable text is found — identical behaviour to the original
    inline logic in agents/compliance.py:ingest_document().
    """
    try:
        text = ingest.extract_text(filename or "upload", content)
    except ingest.UnsupportedFileType as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not text.strip():
        raise HTTPException(
            status_code=422,
            detail="No extractable text found in this file (scanned/image-only PDFs are "
            "not supported by this text-first pipeline).",
        )

    content_hash = hashlib.sha256(content).hexdigest()
    is_pinned_demo = content_hash in _PINNED_DEMO_HASHES

    # PERCEIVE: LLM-first extraction behind a span-verification gate when enabled
    # (app/llm_extract.py), else pure regex. Either way, DECIDE stays in checks.py.
    # The 2 pinned demo files are forced regex-only so their extracted params
    # (and therefore their cached downstream LLM prose) never drift.
    found, abstained = await llm_extract.extract_params(text, force_regex_only=is_pinned_demo)
    param_dicts = ingest.to_param_dicts(found)
    document_id = ingest.register_upload(
        filename or "upload", param_dicts, abstained, content_hash=content_hash
    )

    return {
        "document_id": document_id,
        "title": filename,
        "extracted": [
            {
                "param": p["param"],
                "element": p["element"],
                "value": p["value"],
                "unit": p["unit"],
                "source_quote": p["source_quote"],
            }
            for p in param_dicts
        ],
        "abstained": [{"param": a.param, "reason": a.reason} for a in abstained],
        "checkable_params": len(param_dicts),
    }
