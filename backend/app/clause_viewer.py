"""In-app clause viewer — replaces the dead `http://gaudi.local/...` verify_url
link with a proper in-app popup showing the real source document/page.

CitedClauseBox.tsx used to send an engineer clicking "View standard" straight
to an external link. For most clauses that link is dead (gaudi.local was a
dev-machine-only host); for the rest it's a huge generic scanned book on
archive.org, not the specific clause. Neither shows "the actual document" the
way an engineer would want.

This module reads the REAL digitised source `.md` file directly off disk
(the same files `structural_standard_codes` indexes, see
`app/retrieval/filesystem_corpora.py`) and extracts the verbatim section
around the cited clause number, using the file's own markdown headings as
section boundaries — no re-derivation, no paraphrasing, exactly the bytes on
disk. Deliberately does NOT depend on RETRIEVAL_ENABLED: this reads files
directly, so it works whether or not the retrieval package is mounted,
keeping OFFLINE_MODE's zero-flag path intact.

Honesty rule: only 3 of the ~10 standards cited across clauses.json /
commissioning_clauses.json have a locally digitised `.md` source under
standards-service/data/structural_corpus/ today (IS 456:2000, IS 1893
(Part 1):2016, IS 875 (Part 3):2015 — see _STANDARD_TO_FILE below). The rest
(CEA regs, IS 3043, IS 732, IS 8623, the ASHRAE-derived commissioning
envelope) have no local source file, and this module says so explicitly
(`has_context=False` + a plain-language `note`) rather than ever fabricating
or guessing a path.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from . import config

router = APIRouter(prefix="/api", tags=["clause-viewer"])

_STRUCTURAL_CORPUS_DIR = config.BACKEND_DIR.parent / "standards-service" / "data" / "structural_corpus"

# Only standards with a real, locally digitised `.md` file (verified against
# the actual directory listing before writing this dict — see
# standards-service/data/structural_corpus/*/*.md).
_STANDARD_TO_FILE = {
    "IS 456:2000": "is456_2000/is.456.2000.md",
    "IS 1893 (Part 1):2016": "is1893_part1_2016/irc.gov.in.1893.2016.md",
    "IS 875 (Part 3):2015": "is875_part3_2015/IS-875-Part-III.md",
}

_HEADING_RE = re.compile(r"^(#{1,6})\s+([0-9]+(?:\.[0-9]+)*)\b")

MAX_CONTEXT_LINES = 80


class ClauseContext(BaseModel):
    has_context: bool
    standard: str
    clause: str
    heading: Optional[str] = None
    filename: Optional[str] = None
    context_text: Optional[str] = None
    note: str


@lru_cache(maxsize=8)
def _read_lines(rel_path: str) -> tuple:
    path = _STRUCTURAL_CORPUS_DIR / rel_path
    return tuple(path.read_text(encoding="utf-8", errors="replace").splitlines())


def _find_heading(lines: tuple, number: str):
    """First heading line whose leading numeric token exactly equals `number`."""
    for i, line in enumerate(lines):
        m = _HEADING_RE.match(line)
        if m and m.group(2) == number:
            return i, len(m.group(1)), line.lstrip("#").strip()
    return None, 0, None


def get_clause_context(standard: str, clause: str) -> ClauseContext:
    rel_path = _STANDARD_TO_FILE.get(standard)
    if not rel_path:
        return ClauseContext(
            has_context=False,
            standard=standard,
            clause=clause,
            note="No locally digitised source document is mapped for this standard in "
            "this environment — showing the cited clause text only.",
        )

    full_path = _STRUCTURAL_CORPUS_DIR / rel_path
    if not full_path.exists():
        return ClauseContext(
            has_context=False,
            standard=standard,
            clause=clause,
            filename=rel_path,
            note="The mapped source document is missing on disk — showing the cited "
            "clause text only.",
        )

    lines = _read_lines(rel_path)
    target = clause.strip()

    # Pass 1: exact heading match on the clause number itself. Pass 2: the
    # nearest parent heading (e.g. "26.4.2" for a target of "26.4.2.2"), so a
    # citation to a numbered sub-item still resolves to its containing section.
    match_idx, match_level, match_heading = _find_heading(lines, target)
    if match_idx is None and "." in target:
        match_idx, match_level, match_heading = _find_heading(lines, target.rsplit(".", 1)[0])

    if match_idx is None:
        return ClauseContext(
            has_context=False,
            standard=standard,
            clause=clause,
            filename=rel_path,
            note="Could not locate this clause number as a heading in the source "
            "document — showing the cited clause text only.",
        )

    end_idx = len(lines)
    for j in range(match_idx + 1, len(lines)):
        m = _HEADING_RE.match(lines[j])
        if m and len(m.group(1)) <= match_level:
            end_idx = j
            break
    end_idx = min(end_idx, match_idx + MAX_CONTEXT_LINES)

    return ClauseContext(
        has_context=True,
        standard=standard,
        clause=clause,
        heading=match_heading,
        filename=rel_path,
        context_text="\n".join(lines[match_idx:end_idx]).strip(),
        note="Verbatim excerpt from the real digitised source document, read directly "
        "from disk — the same file structural_standard_codes indexes.",
    )


@router.get("/clause-context", response_model=ClauseContext)
def clause_context(standard: str, clause: str) -> ClauseContext:
    return get_clause_context(standard, clause)
