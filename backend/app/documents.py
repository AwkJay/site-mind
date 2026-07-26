"""GET /api/documents — the submittal / document register.

Filesystem-backed: every row corresponds to a REAL file on disk under
backend/data/project_docs/demo_docs/. There is no fabricated register entry
without bytes behind it — selecting a document and running a compliance check
reads those actual bytes (see POST /api/documents/{doc_id}/ingest below, which
runs the identical real pipeline as POST /api/compliance/ingest).

Metadata (id / title / discipline / type / status) for each filename is a small
explicit manifest below — deliberately not regex-parsed out of the filename,
because a manifest is honest and auditable at a glance.
"""
from __future__ import annotations

import hashlib

from fastapi import APIRouter, HTTPException

from .config import DATA_DIR
from .ingest_pipeline import run_ingest_pipeline

router = APIRouter(prefix="/api", tags=["documents"])

DEMO_DOCS_DIR = DATA_DIR / "project_docs" / "demo_docs"

# Explicit manifest: filename -> display metadata. Add a row here whenever a new
# real file is dropped into demo_docs/ — the register only lists files that both
# (a) exist on disk and (b) have a manifest entry, so nothing shows up half-described.
_MANIFEST: dict[str, dict] = {
    "DC1-02-DBR-0009-R0_Structural-Design-Basis-Report.pdf": {
        "id": "DC1-02-DBR-0009-R0",
        "title": "Structural Design Basis Report",
        "discipline": "Structural",
        "type": "design_basis",
        "status": "Pending",
    },
    "DC1-16-DBR-0201-R0_Generator-Earthing-Addendum.docx": {
        "id": "DC1-16-DBR-0201-R0",
        "title": "Generator Earthing Addendum",
        "discipline": "Electrical",
        "type": "submittal",
        "status": "Pending",
    },
}


@router.get("/documents")
def get_documents() -> list[dict]:
    """Enumerate demo_docs/ — one entry per real file that also has a manifest
    row. Each entry carries filename/size_bytes/has_file so the UI can show the
    real file as proof, not a synthetic row."""
    out = []
    if not DEMO_DOCS_DIR.is_dir():
        return out
    for path in sorted(DEMO_DOCS_DIR.iterdir()):
        if not path.is_file():
            continue
        meta = _MANIFEST.get(path.name)
        if not meta:
            continue  # a stray file with no manifest entry — not listed, not guessed
        out.append(
            {
                "id": meta["id"],
                "title": meta["title"],
                "type": meta["type"],
                "status": meta["status"],
                "discipline": meta["discipline"],
                "filename": path.name,
                "size_bytes": path.stat().st_size,
                "has_file": True,
            }
        )
    return out


def _find_file(doc_id: str) -> "tuple[str, bytes]":
    for filename, meta in _MANIFEST.items():
        if meta["id"] == doc_id:
            path = DEMO_DOCS_DIR / filename
            if not path.is_file():
                raise HTTPException(
                    status_code=404,
                    detail=f"Manifest lists '{filename}' for {doc_id} but the file is missing on disk.",
                )
            return filename, path.read_bytes()
    raise HTTPException(status_code=404, detail=f"Unknown document_id: {doc_id}")


# In-process cache keyed by sha256 of the file bytes: clicking the same demo
# document twice must not re-run extraction (extraction can call an LLM and
# quota is scarce). Not persisted — matches ingest.py's own in-memory upload
# store, which is fine for a single-process demo server.
_INGEST_CACHE: dict[str, dict] = {}


@router.post("/documents/{doc_id}/ingest")
async def ingest_registered_document(doc_id: str) -> dict:
    """Read the real bytes for a demo_docs/ file and run them through the SAME
    ingest pipeline POST /api/compliance/ingest uses (extract_text ->
    llm_extract.extract_params -> register_upload). Returns the identical
    response shape, including a fresh upload document_id that
    /api/compliance/check and /check/stream accept."""
    filename, content = _find_file(doc_id)
    sha = hashlib.sha256(content).hexdigest()
    cached = _INGEST_CACHE.get(sha)
    if cached is not None:
        return cached
    result = await run_ingest_pipeline(filename, content)
    _INGEST_CACHE[sha] = result
    return result
