"""Resolve a Compliance check's cited clause via the live Actian-backed vector
index instead of a hardcoded clause_key lookup — with a transparent,
always-safe fallback to the local digitised cache (`app/standards.py`).

WHY THIS EXISTS
----------------
Before this module, every Compliance NCR's citation came straight from
`standards.get_clause(check["clause_key"])` — a hardcoded string key into
`backend/data/standards/clauses.json`. Actian VectorAI DB was live and
healthy (6,206 vectors, corpus `structural_standard_codes`) but NOTHING in
the pillar ever queried it. This module makes retrieval the primary path:
each check's `rule_text` (a plain-English statement of the requirement,
already present on every `Check` in `agents/checks.py`) is used as the
search query, and the top-ranked hit that can be VERIFIED as genuinely the
same clause `clause_key` points at is accepted.

QUERY-PHRASING FINDING (this is why `rule_text`, not the param description)
-----------------------------------------------------------------------
Probing showed retrieval quality is almost entirely about query phrasing:
a terse param-derived query like "nominal cover for a footing in severe
exposure" does not surface IS456_26.4.2.2 in the top 10, but the check's own
`rule_text` ("For footings the minimum nominal cover shall be 50 mm.") ranks
it #1 at score 0.876-0.901. `rule_text` is close in register to how the
standard itself states the requirement, so it is the query used here.

ACCEPTANCE GATE (never trust a topical neighbour)
--------------------------------------------------
A retrieved hit is accepted only if EITHER:
  (a) its `heading` starts with the curated clause's own number
      (`get_clause(clause_key).clause`, e.g. "26.4.2.2"), OR
  (b) the curated clause's `text`, whitespace-collapsed and casefolded, is a
      substring of the hit's `raw_text` (also normalised the same way).
The FIRST hit (in rank order, k=10) that passes either test is accepted.
Measured against every real check in `agents/checks.py` (2026-07-25, live
Actian index): all 10 structural checks accept (ranks 1-8); all 7 electrical
checks fall back to `local_cache`, honestly, because `structural_standard_codes`
does not index any IS 732/IS 3043/CEA electrical text at all (there is
nothing there to find — not a gate failure).

CITATION CONTENT: WHAT COMES FROM WHERE (the honesty call)
------------------------------------------------------------
On acceptance, `standard` / `clause` / `text` / `verify_url` / `source_type`
are ALL kept as the curated clause's own values (`get_clause(clause_key)`) —
NOT reconstructed from the retrieved chunk's own heading/raw_text. This is a
deliberate deviation from the pattern used elsewhere in this codebase
(`agents/compliance.py`'s `_computed_draft_finding`, which builds a Citation
directly from an unvetted retrieved chunk because it has no curated
citation to fall back on). Here we DO have one, and the acceptance gate has
just proven the retrieved chunk really is that same real-world clause — so
the citation shown to a judge stays the clean, pre-vetted rendering (never a
raw chunk that might span a heading-only fragment, a multi-clause section,
or an OCR artifact), while every fact about HOW it was found (rank, score,
the exact query, which file, how many vectors were searched) is attached
separately as `retrieval` provenance. The quoted clause text a judge reads
is therefore always trustworthy and never a mangled chunk boundary — the
vector index's job here is to prove the clause is really in the live index
and say where, not to supply the text that gets displayed.

FALLBACK CONTRACT: NEVER RAISE, NEVER RETURN NONE
---------------------------------------------------
Falls back to `standards.get_clause(clause_key)` (today's original behaviour)
whenever: retrieval is disabled (`config.RETRIEVAL_ENABLED` is False), the
corpus is unavailable, the query throws for any reason, or no hit in the top
10 passes the acceptance gate. The fallback Citation carries
`retrieval.resolved_via == "local_cache"` plus a human-readable `note` — this
is treated as a FEATURE (an honest, visible label), never papered over, per
the repo owner's explicit instruction. If even the local cache has no entry
for `clause_key` (should not happen for any real `Check`), a clearly-broken
but non-crashing placeholder Citation is returned rather than raising or
returning None — the demo must never break on a citation lookup.

CACHING
-------
Resolutions are cached in-process by `(rule_text, curated_clause_key)` —
embedding + hybrid search on every single NCR would be wasteful and slow
down the SSE stream, and the SAME check is re-resolved on every re-run of
`compliance.evaluate()` (there is no reason its answer should change).
"""
from __future__ import annotations

import logging
import re

from . import config
from .schemas import Citation, ClauseRetrievalProvenance
from .standards import get_clause

logger = logging.getLogger(__name__)

ResolutionMeta = ClauseRetrievalProvenance  # the name this brief refers to it by

_CACHE: dict[tuple[str, str], tuple[Citation, ResolutionMeta]] = {}


def _norm(s: str) -> str:
    """Collapse whitespace + casefold — used on both sides of the substring
    acceptance test so real but cosmetic differences (line wraps, curly vs
    straight quotes-adjacent spacing) never cause a false rejection."""
    return re.sub(r"\s+", " ", s or "").strip().casefold()


def _local_fallback(curated_clause_key: str, query: str, note: str) -> tuple[Citation, ResolutionMeta]:
    """The original, pre-retrieval behaviour — always available, never raises."""
    citation = get_clause(curated_clause_key)
    meta = ResolutionMeta(resolved_via="local_cache", query=query, note=note)
    if citation is None:
        # Not expected for any real Check in agents/checks.py, but this module's
        # contract is "never raise, never return None" — hand back a visibly
        # broken placeholder rather than crashing the compliance run.
        citation = Citation(
            standard="Unknown",
            clause=curated_clause_key,
            text="(No cached clause text found for this key — neither the vector "
            "index nor the local cache could resolve it.)",
            verify_url="",
        )
    return citation.model_copy(update={"retrieval": meta}), meta


def resolve_clause(rule_text: str, curated_clause_key: str) -> tuple[Citation, ResolutionMeta]:
    """Resolve `curated_clause_key`'s Citation via the Actian-backed vector
    index, querying with `rule_text`. Always returns a usable (Citation,
    ResolutionMeta) pair — see the module docstring's fallback contract.
    Cached by (rule_text, curated_clause_key)."""
    cache_key = (rule_text, curated_clause_key)
    cached = _CACHE.get(cache_key)
    if cached is not None:
        return cached
    result = _resolve_uncached(rule_text, curated_clause_key)
    _CACHE[cache_key] = result
    return result


def _citation_from_curated(curated: Citation) -> Citation:
    """A fresh copy of the curated citation (never mutate the lru_cache'd
    object standards.py hands back)."""
    return curated.model_copy()


def _resolve_uncached(rule_text: str, curated_clause_key: str) -> tuple[Citation, ResolutionMeta]:
    if not rule_text:
        return _local_fallback(
            curated_clause_key, rule_text or "",
            "no rule_text available to query the vector index with",
        )
    if not config.RETRIEVAL_ENABLED:
        return _local_fallback(
            curated_clause_key, rule_text, "retrieval is disabled (RETRIEVAL_ENABLED=0)"
        )

    curated = get_clause(curated_clause_key)
    if curated is None:
        return _local_fallback(
            curated_clause_key, rule_text, "no local clause is cached for this key either"
        )

    try:
        # Lazy imports: this module must be importable (and OFFLINE_MODE-safe)
        # even when the retrieval package's own dependencies aren't touched by
        # any other code path — mirrors _computed_draft_finding's own lazy
        # import of the same two modules.
        from .retrieval import filesystem_corpora
        from .retrieval.index import get_corpus

        filesystem_corpora.ensure_filesystem_corpora()
        corpus = get_corpus(filesystem_corpora.STRUCTURAL_CORPUS_NAME)
        if not corpus or not corpus.chunk_count:
            return _local_fallback(
                curated_clause_key, rule_text,
                "the structural_standard_codes vector corpus is empty or unavailable",
            )

        hits = corpus.query(rule_text, k=10)
        vectors_searched = corpus.chunk_count
        curated_num = (curated.clause or "").strip()
        curated_text_norm = _norm(curated.text)

        for rank, hit in enumerate(hits, start=1):
            heading = (hit.get("heading") or "").strip()
            raw_text = hit.get("raw_text") or hit.get("text") or ""
            heading_ok = bool(curated_num) and heading.startswith(curated_num)
            text_ok = bool(curated_text_norm) and curated_text_norm in _norm(raw_text)
            if not (heading_ok or text_ok):
                continue

            meta = ResolutionMeta(
                resolved_via="vector_index",
                rank=rank,
                score=round(float(hit.get("score", 0.0)), 4),
                query=rule_text,
                chunk_source=hit.get("filename"),
                vectors_searched=vectors_searched,
            )
            citation = _citation_from_curated(curated).model_copy(update={"retrieval": meta})
            return citation, meta

        return _local_fallback(
            curated_clause_key, rule_text,
            f"the vector index did not surface this clause in the top {len(hits)} "
            "results; citing the locally cached digitised clause instead",
        )
    except Exception:
        logger.warning(
            "clause_resolver: retrieval failed for clause_key=%s; falling back to the local cache.",
            curated_clause_key,
            exc_info=True,
        )
        return _local_fallback(
            curated_clause_key, rule_text,
            "the vector index raised an error; citing the locally cached digitised clause instead",
        )
