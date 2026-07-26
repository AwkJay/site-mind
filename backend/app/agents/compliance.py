"""Pillar 1 — the Spec & Quality Compliance Agent (THE HERO).

Flow per parameter:
  EXTRACT (pre-stored params)  ->  RETRIEVE (CHECK REGISTRY + real clause)
  ->  DECIDE (deterministic Python threshold)  ->  EXPLAIN (prose).

The pass/fail decision and the Citation are ALWAYS deterministic (Python +
clauses.json). Only the prose (finding / why / corrective) is LLM-assisted when
a key is present; otherwise it comes from deterministic seeds / fixtures.
"""
from __future__ import annotations

import json
import time
from typing import AsyncGenerator, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .. import audit, clause_resolver, config, ingest, ingest_pipeline, llm, llm_extract, trace
from ..data_loader import fixture, load_submittals, params_for
from ..schemas import NCR, ComplianceResult, Citation, CoverageStat, ExtractedRule, OverlapNote, SourceSpan
from ..standards import all_clauses, get_clause
from . import rule_eval
from .checks import applicable_checks


# IS 456 Table 16 — nominal durability cover floor by exposure (mm). Real values
# from the digitised clause IS456_26.5.1.1. Used only to resolve cover overlaps.
_TABLE16_COVER = {
    "mild": 20,
    "moderate": 30,
    "severe": 45,
    "very severe": 50,
    "extreme": 75,
}
# Primary per-element cover floor (mm), keyed by the binary check id.
_PRIMARY_COVER_FLOOR = {"COVER_FOOTING": 50, "COVER_COLUMN": 40}


def _ref(citation: Optional[Citation]) -> str:
    """Compact human-readable clause ref, e.g. 'IS 456:2000 Cl 26.4.2.2'."""
    if not citation:
        return "?"
    return f"{citation.standard} Cl {citation.clause}"

router = APIRouter(prefix="/api/compliance", tags=["compliance"])


class CheckRequest(BaseModel):
    document_id: str


# --------------------------------------------------------------------------- #
# Prose (LLM-assisted online, deterministic offline)
# --------------------------------------------------------------------------- #
_EXPLAIN_SYSTEM = (
    "You are a structural QA engineer writing a Non-Conformance Report for a "
    "data-centre construction project. You are GIVEN the governing standard "
    "clause verbatim — never alter or invent clause numbers or text. Reply with "
    "ONLY a JSON object with keys finding, why_it_matters, corrective_action. "
    "Temperature 0."
)


def _explain_prompt(param: dict, check, citation: Citation) -> str:
    return (
        f"Element: {param.get('element')}\n"
        f"Specified: {param.get('param')} = {param.get('value')} {param.get('unit', '')}\n"
        f"Context: exposure={param.get('exposure')}, type={param.get('element_type')}\n"
        f"Required by standard: {check['rule_text']}\n"
        f"Governing clause (cite exactly): {citation.standard} Cl. {citation.clause}: "
        f'"{citation.text}"\n\n'
        "Write finding (1 sentence on what was specified), why_it_matters (1-2 "
        "sentences tying it to data-centre reliability/uptime), corrective_action "
        "(1 concrete step)."
    )


def _offline_prose(param: dict, check) -> dict:
    """Deterministic prose: prefer the fixture (keyed by param id), else seeds."""
    fx = fixture("compliance_prose.json") or {}
    pid = param.get("id")
    if pid and pid in fx:
        return fx[pid]
    if check and check["id"] in fx:
        return fx[check["id"]]
    return {
        "finding": (
            f"{param.get('source_location', 'The submittal')} specifies "
            f"{param.get('param', 'a parameter').replace('_', ' ')} = "
            f"{param.get('value')} {param.get('unit', '')}".strip() + "."
        ),
        "why_it_matters": check["why"],
        "corrective_action": check["corrective"],
    }


def _prose(param: dict, check, citation: Citation) -> dict:
    """Online: Claude writes prose handed the real clause. Offline: deterministic."""
    if config.OFFLINE_MODE:
        return _offline_prose(param, check)
    out = llm.complete_json(_EXPLAIN_SYSTEM, _explain_prompt(param, check, citation))
    if not out or not all(k in out for k in ("finding", "why_it_matters", "corrective_action")):
        return _offline_prose(param, check)  # robust fallback
    return out


# --------------------------------------------------------------------------- #
# NCR construction
# --------------------------------------------------------------------------- #
def _source(param: dict) -> Optional[SourceSpan]:
    q = param.get("source_quote")
    if not q:
        return None
    return SourceSpan(quote=q, location=param.get("source_location", "unknown"))


def _advisory_ncr(param: dict, ncr_id: str) -> Optional[NCR]:
    """The IS 1893 I=1.5 judgment-catch (the memorable demo beat)."""
    if param.get("param") != "importance_factor" or param.get("value", 1.5) >= 1.5:
        return None
    # This advisory has no CHECKS entry (it's a judgment call, not a checks.py
    # rule), so there is no rule_text to resolve with — a hand-written query in
    # the same register clause_resolver expects (verified live: IS 1893's real
    # "7.2.3 Importance Factor (I)" clause retrieves at rank 2 in the corpus).
    citation, _meta = clause_resolver.resolve_clause(
        "seismic importance factor for important service buildings", "IS1893_7.2.3"
    )
    fx = (fixture("compliance_prose.json") or {}).get(param.get("id"), {})
    finding = fx.get(
        "finding",
        f"Design uses seismic Importance Factor I={param.get('value')} "
        "(treated as an ordinary building).",
    )
    return NCR(
        id=ncr_id,
        item=param.get("element", "Primary structure"),
        severity="ADVISORY",
        finding=finding,
        source=_source(param),
        citation=citation,
        why_it_matters=fx.get(
            "why_it_matters",
            "A Tier-III/IV data centre is a textbook modern lifeline facility. "
            "Per IS 1893 Pt1:2016 Cl 7.2.3 / Table 8, lifeline and emergency "
            "buildings (power stations, telephone exchanges) take I=1.5; using "
            "I=1.0 may under-design the lateral system for a mission-critical asset.",
        )
        + " IS 1893 Cl 6.4.2 reinforces this: where I is not otherwise specified, "
        "the minimum for critical and lifeline structures is 1.5, and I feeds the "
        "design seismic coefficient Ah = (Z/2)(Sa/g)/(R/I) — so I=1.0 lowers the "
        "design base shear by a third versus I=1.5.",
        corrective_action=fx.get(
            "corrective_action",
            "Re-run the seismic design basis with I=1.5 and compare base shear.",
        ),
        recommendation=fx.get(
            "recommendation",
            "Adopt I=1.5. Table 8 does not name data centres, but Note 1 lets the "
            "owner adopt a higher I, and a Tier-III/IV DC is arguably a lifeline facility.",
        ),
        confirm_with=fx.get("confirm_with", "EOR"),
    )


def _violation_ncr(param: dict, check, ncr_id: str) -> NCR:
    # Citation now resolved via the live Actian vector index (clause_resolver.py),
    # queried with the check's own rule_text — falls back to the local digitised
    # cache (the old get_clause() behaviour) whenever retrieval is off, the
    # corpus can't confirm the clause, or anything throws. Never raises.
    citation, _meta = clause_resolver.resolve_clause(check["rule_text"], check["clause_key"])
    prose = _prose(param, check, citation) if citation else _offline_prose(param, check)
    return NCR(
        id=ncr_id,
        item=param.get("element", "Unknown element"),
        severity=check["severity"],  # type: ignore[arg-type]
        finding=prose["finding"],
        source=_source(param),
        citation=citation,
        why_it_matters=prose["why_it_matters"],
        corrective_action=prose["corrective_action"],
        domain=check.get("domain", "structural"),  # type: ignore[arg-type]
    )


# --------------------------------------------------------------------------- #
# Tiered verdicts (plan §B2) — "computed_draft" tier. No checks.py rule governs
# this param: an LLM READS a rule out of the real retrieved clause into an
# ExtractedRule (never a verdict); `rule_eval.evaluate` COMPUTES it; an engineer
# CONFIRMS the reading. Two anti-hallucination gates: the extracted rule's
# clause_phrase must be a verbatim substring of the retrieved clause, and the
# LLM never invents a threshold not present in that clause. On any abstention
# (no clause retrieved, no LLM available, phrase not verbatim, clause states no
# checkable rule) this honestly returns "unresolved" — never a fabricated rule,
# never silently dropped like the old bare `continue`.
# --------------------------------------------------------------------------- #
_RULE_EXTRACT_SYSTEM = (
    "You are reading ONE real standards clause to state its requirement as a "
    "structured rule. You never decide pass/fail — you only perceive what the "
    "clause says, exactly as written. Reply with ONLY a JSON object: "
    '{"kind": "compare"|"range"|"min_of"|"max_of"|"table_lookup"|"formula"|"none", '
    '"operator": ">="|"<="|">"|"<"|"=="|"!=" or null, "threshold": number or null, '
    '"unit": string or null, "inputs": object (may be empty), "table": object or '
    'null, "expression": string or null, "clause_phrase": string}.\n'
    "Hard rules: (1) clause_phrase MUST be an exact, verbatim substring of the "
    "clause text given below — copy it character-for-character, never paraphrase. "
    "(2) Never invent a threshold or number that is not written in the clause. "
    '(3) If the clause states no checkable numeric rule for this parameter, '
    'return {"kind": "none", "clause_phrase": ""} and nothing else. Temperature 0.'
)


def _rule_extract_prompt(param: dict, clause_text: str) -> str:
    return (
        f"Parameter to check: {param.get('param')} = {param.get('value')} {param.get('unit', '')}\n"
        f"Element: {param.get('element')} ({param.get('element_type')})\n"
        f'Clause text (quote from this, and only this, exactly):\n"{clause_text}"\n'
    )


def _extract_rule(param: dict, clause_key: str, clause_text: str) -> Optional[ExtractedRule]:
    """The LLM reads a rule out of the real clause text — never computes anything.
    Returns None (-> unresolved) on any failure: no key, bad JSON, or a shape
    pydantic rejects. Never raises."""
    if config.OFFLINE_MODE:
        return None
    out = llm.complete_json(_RULE_EXTRACT_SYSTEM, _rule_extract_prompt(param, clause_text))
    if not out or "kind" not in out:
        return None
    try:
        fields = {k: v for k, v in out.items() if k not in ("clause_key", "clause_phrase")}
        return ExtractedRule(clause_key=clause_key, clause_phrase=out.get("clause_phrase") or "", **fields)
    except Exception:
        return None


def _query_text_for(param: dict) -> str:
    """Best-effort natural-language retrieval query built from a submittal param."""
    bits = [str(param.get("param", "")).replace("_", " ")]
    if param.get("element_type"):
        bits.append(f"for a {param['element_type']}")
    if param.get("exposure"):
        bits.append(f"in {param['exposure']} exposure")
    return " ".join(b for b in bits if b).strip() or "structural requirement"


def _unresolved_ncr(param: dict, ncr_id: str, reason: str) -> NCR:
    """Honestly flagged: no rule could be established. Never a fabricated verdict,
    never silently dropped (unlike the old bare `continue` this tier replaces)."""
    return NCR(
        id=ncr_id,
        item=param.get("element", "Unknown element"),
        severity="ADVISORY",
        finding=(
            f"{param.get('element', 'The submittal')} specifies "
            f"{str(param.get('param', 'a parameter')).replace('_', ' ')} = "
            f"{param.get('value')} {param.get('unit', '')}".strip()
            + " — no governing clause could be established."
        ),
        source=_source(param),
        citation=None,
        why_it_matters=f"No pre-vetted check or computed-draft rule covers this parameter: {reason}.",
        corrective_action="An engineer should manually locate and confirm the governing clause.",
        status="REVIEW_REQUIRED",
        verdict_tier="unresolved",
    )


def _computed_draft_finding(param: dict, ncr_id: str) -> Optional[NCR]:
    """No checks.py rule governs this param. Retrieve the top candidate clauses,
    have the LLM read a rule out of each in turn until one actually states a
    checkable rule (a near-miss/heading-only chunk is common — an engineer
    would skim past it too), gate the rule's clause_phrase as verbatim, then
    let rule_eval compute PASS/FAIL. Returns None when the param conforms
    (nothing to report); an NCR (computed_draft or unresolved) otherwise."""
    from ..retrieval import filesystem_corpora  # lazy: only touched when this flag is on
    from ..retrieval.index import get_corpus

    filesystem_corpora.ensure_filesystem_corpora()
    corpus = get_corpus(filesystem_corpora.STRUCTURAL_CORPUS_NAME)
    if not corpus:
        return _unresolved_ncr(param, ncr_id, "the standards corpus is unavailable")

    hits = corpus.query(_query_text_for(param), k=3)
    if not hits:
        return _unresolved_ncr(param, ncr_id, "no governing clause found in the standards corpus")

    reason = "no retrieved candidate clause stated a checkable numeric rule"
    for chunk in hits:
        clause_text = chunk.get("raw_text") or chunk.get("text") or ""
        clause_key = f"{chunk.get('document_id', '?')}:{chunk.get('heading') or chunk.get('filename', '?')}"

        rule = _extract_rule(param, clause_key, clause_text)
        if rule is None:
            # LLM-wide failure (no key / error) — not clause-specific, retrying
            # another candidate against the same broken LLM call won't help.
            return _unresolved_ncr(param, ncr_id, "no LLM available to read a rule from the retrieved clause")
        if rule.kind == "none":
            continue  # this candidate states no rule; try the next one

        # Anti-hallucination gate: the extracted clause_phrase must be verbatim in the real clause.
        if llm_extract._norm(rule.clause_phrase).lower() not in llm_extract._norm(clause_text).lower():
            reason = "the extracted rule's clause phrase is not verbatim in the retrieved clause"
            continue

        verdict, detail = rule_eval.evaluate(rule, param)
        if verdict == "NOT_CHECKABLE":
            continue  # rule shape didn't fit this param; try the next candidate
        if verdict == "PASS":
            return None  # conforms — nothing to report

        citation = Citation(
            standard=str(chunk.get("document_id", "?")),
            clause=str(chunk.get("heading") or chunk.get("breadcrumb") or chunk.get("filename", "?")),
            text=clause_text,
            verify_url=f"standards-service/data/structural_corpus/{chunk.get('document_id')}/{chunk.get('filename')}",
            source_type="primary_native_pdf",
        )
        return NCR(
            id=ncr_id,
            item=param.get("element", "Unknown element"),
            severity="MEDIUM",
            finding=(
                f"{param.get('element', 'The submittal')} specifies "
                f"{str(param.get('param', 'a parameter')).replace('_', ' ')} = "
                f"{param.get('value')} {param.get('unit', '')}".strip()
            ),
            source=_source(param),
            citation=citation,
            why_it_matters=(
                "No pre-vetted check covers this parameter, so an LLM read a rule out of the "
                "retrieved clause and the evaluator computed a FAIL — an engineer must confirm "
                "the reading before treating this as a confirmed non-conformance."
            ),
            corrective_action="Confirm the extracted rule against the cited clause and revise the submittal if correct.",
            status="REVIEW_REQUIRED",
            verdict_tier="computed_draft",
            extracted_rule=rule,
            computed_detail=detail,
        )

    return _unresolved_ncr(param, ncr_id, reason)


# --------------------------------------------------------------------------- #
# Core evaluation
# --------------------------------------------------------------------------- #
def _document_title(document_id: str) -> str:
    upload = ingest.get_upload(document_id)
    if upload:
        return f"{document_id} — {upload['title']} (uploaded)"
    for s in load_submittals():
        if s.get("Submittal No") == document_id:
            rev = s.get("Rev", "")
            return f"{document_id} {rev} — {s.get('Title', '')}".strip()
    return document_id


def _params_for(document_id: str) -> list[dict]:
    """Uploaded documents first (real extraction), then the pre-structured set."""
    upload = ingest.get_upload(document_id)
    if upload:
        return upload["params"]
    return params_for(document_id)


def _cover_overlap(param: dict, check) -> Optional[OverlapNote]:
    """For a cover check governed by >1 clause, resolve the binding requirement.

    Returns an OverlapNote naming every governing clause and the strictest one,
    or None when the overlap doesn't apply (e.g. no recognised exposure)."""
    primary = get_clause(check["clause_key"])
    floor_primary = _PRIMARY_COVER_FLOOR.get(check["id"])
    exposure = (param.get("exposure") or "").lower()
    floor_table16 = _TABLE16_COVER.get(exposure)
    if not primary or floor_primary is None or floor_table16 is None:
        return None
    t16 = get_clause("IS456_26.5.1.1")
    primary_lbl = f"{_ref(primary)} ({param.get('element_type')} min {floor_primary} mm)"
    t16_lbl = f"{_ref(t16)} / Table 16 ({exposure} exposure {floor_table16} mm)"
    if floor_primary >= floor_table16:
        governing, gov_val = primary_lbl, floor_primary
    else:
        governing, gov_val = t16_lbl, floor_table16
    return OverlapNote(
        item=param.get("element", "element"),
        param="nominal_cover",
        clauses=[primary_lbl, t16_lbl],
        governing=governing,
        note=(
            f"Two clauses govern cover for {param.get('element')}: the "
            f"{param.get('element_type')} minimum ({floor_primary} mm) and the "
            f"{exposure}-exposure durability floor (Table 16, {floor_table16} mm). "
            f"The binding requirement is {gov_val} mm."
        ),
    )


def evaluate(document_id: str) -> ComplianceResult:
    """Run every applicable check on the document and assemble a ComplianceResult."""
    return evaluate_with_params(document_id)[0]


def evaluate_with_params(document_id: str) -> tuple[ComplianceResult, dict[str, dict]]:
    """Same as evaluate(), plus a {ncr_id: raw_param_dict} side-channel the Action
    Brief needs (element/param/value/unit) without changing the stable NCR schema."""
    run = trace.start(
        "compliance.evaluate",
        {"document_id": document_id, "llm_provider": config.LLM_PROVIDER, "offline_mode": config.OFFLINE_MODE},
    )
    with run.step("load_params"):
        params = _params_for(document_id)
        known_ids = {s.get("Submittal No") for s in load_submittals()}
        if not params and document_id not in known_ids and not ingest.get_upload(document_id):
            raise HTTPException(status_code=404, detail=f"Unknown document_id: {document_id}")

    # Per-document provider pick: the 2 pinned golden demo files stay on Gemini
    # (their cached prose must never drift); every other document — a genuinely
    # new upload, or even an edited copy of a demo file — routes through IAMHC.
    # Kept in sync with ingest_pipeline._PINNED_DEMO_HASHES (not imported here
    # to avoid a circular import for the sake of deduping two strings).
    _upload = ingest.get_upload(document_id)
    _content_hash = (_upload or {}).get("content_hash")
    _provider = "gemini" if _content_hash in {
        "85f3a534537f6daf83514ca2af2e3b6cccf8e4dbd2be479cc09bb2b6937f8140",
        "ffeb88d6621a964930a465c23ed9d187ff61285ab5ba746b7f397ddd9dcbcbd9",
    } else "iamhc"

    ncrs: list[NCR] = []
    conforming: list[str] = []
    overlaps: list[OverlapNote] = []
    cited_keys: set[str] = set()
    standards: set[str] = set()
    standards_by_domain: dict[str, set[str]] = {}
    checks_run = 0
    checked = 0
    seq = 1
    param_by_ncr: dict[str, dict] = {}

    def _register(key: str, domain: str = "structural") -> None:
        c = get_clause(key)
        if c:
            cited_keys.add(key)
            standards.add(c.standard)
            standards_by_domain.setdefault(domain, set()).add(c.standard)

    _checks_t0 = time.time()
    with llm.use_provider(_provider):
        for param in params:
            # Special ADVISORY (judgment call) — not a binary pass/fail.
            adv = _advisory_ncr(param, f"NCR-{seq:04d}")
            if adv is not None:
                ncrs.append(adv)
                param_by_ncr[adv.id] = param
                _register("IS1893_7.2.3")
                _register("IS1893_6.4.2")  # second clause backing the I=1.5 catch
                seq += 1
                checked += 1
                checks_run += 1
                continue

            applied = applicable_checks(param)
            if not applied:
                if config.COMPLIANCE_RULE_EXTRACTION and config.RETRIEVAL_ENABLED:
                    finding = _computed_draft_finding(param, f"NCR-{seq:04d}")
                    if finding is not None:
                        ncrs.append(finding)
                        param_by_ncr[finding.id] = param
                        seq += 1
                    checked += 1
                continue
            for check in applied:
                checked += 1
                checks_run += 1
                check_domain = check.get("domain", "structural")
                _register(check["clause_key"], check_domain)

                # Multi-clause governance: surface overlap + name the binding clause.
                overlap = None
                if check.get("also_governed_by"):
                    for k in check["also_governed_by"]:
                        _register(k, check_domain)
                    if check["id"] in _PRIMARY_COVER_FLOOR:
                        overlap = _cover_overlap(param, check)
                        if overlap:
                            overlaps.append(overlap)

                label = f"{param.get('element')}: {param.get('param', '').replace('_', ' ')}"
                if check["rule"](param):
                    conforming.append(f"{label} — conforms to {check['clause_key']}")
                else:
                    ncr = _violation_ncr(param, check, f"NCR-{seq:04d}")
                    if overlap:
                        ncr.governing_note = overlap.note
                    ncrs.append(ncr)
                    param_by_ncr[ncr.id] = param
                    seq += 1

    run.steps.append(
        {
            "name": "run_checks",
            "duration_ms": round((time.time() - _checks_t0) * 1000, 1),
            "meta": {"params": len(params), "checks_run": checks_run, "ncrs": len(ncrs)},
        }
    )

    coverage = CoverageStat(
        standards=sorted(standards),
        clauses_cited=len(cited_keys),
        checks_run=checks_run,
        library_clauses=len(all_clauses()),
        standards_by_domain={d: sorted(s) for d, s in standards_by_domain.items() if s},
        computed_draft_count=sum(1 for n in ncrs if n.verdict_tier == "computed_draft"),
        unresolved_count=sum(1 for n in ncrs if n.verdict_tier == "unresolved"),
    )
    result = ComplianceResult(
        document=_document_title(document_id),
        checked_params=checked,
        ncrs=ncrs,
        conforming=conforming,
        overlaps=overlaps,
        coverage=coverage,
    )
    run.finish(
        {
            "checked_params": checked,
            "ncr_count": len(ncrs),
            "conforming_count": len(conforming),
            "clauses_cited": len(cited_keys),
        }
    )
    return result, param_by_ncr


# LLM-generated prose (only ever populated by _violation_ncr's online `_prose()`
# call) — excluded from the audit dedup key because two calls to the SAME
# decision can legitimately produce different wording even at temperature 0.
# Hashing these would defeat idempotency: re-evaluating an unchanged decision
# would look "new" every time the LLM rephrases it, growing the ledger forever.
_NCR_PROSE_FIELDS = ("finding", "why_it_matters", "corrective_action", "recommendation")


def ncr_dedup_key(ncr: NCR) -> dict:
    """The deterministic subset of an NCR — everything the audit ledger's
    content_hash should dedup on (severity, citation, values, verdict_tier,
    etc.), excluding LLM prose. See `_NCR_PROSE_FIELDS`.

    Also strips `citation.retrieval` (clause_resolver.py's provenance:
    rank/score/resolved_via/query) — legitimately NON-deterministic across two
    evaluations of the exact same decision. Live testing while building
    clause_resolver.py showed a real example: the same check against the same
    document resolved via the vector index (rank 8) on one run and fell back to
    the local cache on the next (an ANN search can reorder near-tied results,
    and a transient index outage can flip resolved_via) — with NO change to the
    underlying decision. clause_resolver.py always keeps citation.standard/
    clause/text/verify_url/source_type as the stable curated values regardless
    of resolved_via (see its module docstring), so those stay in the hash;
    only the volatile HOW-it-was-found metadata is excluded. Hashing it would
    silently break idempotency: re-checking an unchanged decision could mint a
    "new" ledger entry just because a search reordered."""
    data = {k: v for k, v in ncr.model_dump().items() if k not in _NCR_PROSE_FIELDS}
    if data.get("citation"):
        data["citation"] = {k: v for k, v in data["citation"].items() if k != "retrieval"}
    return data


def _record_upload_audit(document_id: str, result: ComplianceResult) -> None:
    """Audit ledger write (plan §D) — only for REAL uploads, once per NCR,
    idempotent via content_hash. The preloaded demo corpus is seeded once
    instead (POST /api/audit/seed / the startup hook), so every read-only
    /check of the same demo document never re-records."""
    if not ingest.get_upload(document_id):
        return
    for ncr in result.ncrs:
        audit.record_event("compliance", "ncr", ncr.id, ncr.model_dump(), dedup_key=ncr_dedup_key(ncr))


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@router.post("/check", response_model=ComplianceResult)
def check(req: CheckRequest) -> ComplianceResult:
    result = evaluate(req.document_id)
    _record_upload_audit(req.document_id, result)
    return result


@router.post("/ingest")
async def ingest_document(file: UploadFile = File(...)) -> dict:
    """Real document upload: reads the actual PDF/DOCX/text file, extracts ONLY
    the narrow parameter set the CHECK REGISTRY can evaluate, and explicitly
    abstains (never guesses) on anything it can't confidently find. Returns a
    document_id that /compliance/check and /compliance/check/stream accept
    exactly like any pre-loaded document.

    The extract -> perceive -> register pipeline itself lives in
    `ingest_pipeline.run_ingest_pipeline` — shared with
    POST /api/documents/{doc_id}/ingest (the filesystem-backed demo-doc register
    in documents.py) so both entry points run the identical real pipeline."""
    content = await file.read()
    return await ingest_pipeline.run_ingest_pipeline(file.filename or "upload", content)


def _reasoning_trace(
    document_id: str, result: ComplianceResult, param_by_ncr: dict[str, dict]
) -> list[str]:
    """Human-readable agent trace for the live SSE panel.

    Every line here narrates a fact actually observed or computed during THIS
    `evaluate_with_params()` run (`result`/`param_by_ncr`, computed by the caller
    BEFORE this function runs) — never a canned script. A previous version of
    this function emitted a fixed narration (including "Extracting parameters
    from the document…", which was false for the pre-structured demo docs) with
    no connection to what actually happened. Anything not genuinely observable
    from the real upload/evaluation data (e.g. a raw character count — never
    persisted anywhere in the ingest pipeline) is simply omitted, per the rule
    that a placeholder number is worse than no line at all."""
    upload = ingest.get_upload(document_id)
    params = _params_for(document_id)
    lines: list[str] = []

    if upload:
        lines.append(
            f'Loaded {len(params)} checkable parameter(s), span-verified from "{upload["title"]}".'
        )
        if upload.get("abstained"):
            lines.append(
                f"Abstained on {len(upload['abstained'])} parameter type(s) — no confident "
                "verbatim match in the uploaded text."
            )
    else:
        lines.append(f"Loaded {len(params)} pre-structured parameter(s) for {document_id}.")

    if config.RETRIEVAL_ENABLED:
        try:
            from ..retrieval import filesystem_corpora
            from ..retrieval.index import get_corpus

            filesystem_corpora.ensure_filesystem_corpora()
            corpus = get_corpus(filesystem_corpora.STRUCTURAL_CORPUS_NAME)
        except Exception:
            corpus = None
        if corpus and corpus.chunk_count:
            backend_name = (
                "Actian VectorAI DB"
                if config.RETRIEVAL_VECTOR_STORE == "actian"
                else "the local hybrid vector index"
            )
            lines.append(
                f"Searching {backend_name} — {corpus.chunk_count} vectors, "
                f"corpus {filesystem_corpora.STRUCTURAL_CORPUS_NAME}"
            )

    for ncr in result.ncrs:
        citation = ncr.citation
        retrieval = citation.retrieval if citation else None
        if retrieval and retrieval.resolved_via == "vector_index" and citation:
            lines.append(f'  query "{retrieval.query}"')
            lines.append(
                f"  → {citation.standard} Cl. {citation.clause} · rank {retrieval.rank} "
                f"· score {retrieval.score:.3f}"
            )
        elif retrieval and retrieval.resolved_via == "local_cache" and citation:
            # Use the resolver's own real reason (disabled / no accepted hit /
            # error) rather than a single generic line — "didn't surface a
            # match" would be false when retrieval was never attempted at all.
            reason = retrieval.note or "citing the locally cached clause instead"
            lines.append(f"  {reason[0].upper()}{reason[1:]}: {citation.standard} Cl. {citation.clause}")

        p = param_by_ncr.get(ncr.id)
        if p is not None:
            val = f"{p.get('value')} {p.get('unit', '')}".strip()
            lines.append(
                f"  Computing verdict in Python: {str(p.get('param', '')).replace('_', ' ')} "
                f"= {val} → {ncr.severity}"
            )

    if result.conforming:
        lines.append(f"{len(result.conforming)} parameter(s) conformed — no NCR raised.")

    return lines


async def _sse_stream(document_id: str) -> AsyncGenerator[bytes, None]:
    # Compute the real result FIRST so the trace below narrates what actually
    # happened (real retrieval ranks/scores, real computed verdicts) instead of
    # a canned script written before evaluation ran.
    result, param_by_ncr = evaluate_with_params(document_id)
    for line in _reasoning_trace(document_id, result, param_by_ncr):
        yield f"data: {json.dumps({'type': 'reasoning', 'text': line})}\n\n".encode()
    await run_in_threadpool(_record_upload_audit, document_id, result)
    n = len(result.ncrs)
    yield (
        "data: "
        + json.dumps(
            {"type": "reasoning", "text": f"Found {n} non-conformance(s). Compiling NCRs…"}
        )
        + "\n\n"
    ).encode()
    yield (
        "data: " + json.dumps({"type": "result", "data": result.model_dump()}) + "\n\n"
    ).encode()


@router.post("/check/stream")
def check_stream(req: CheckRequest) -> StreamingResponse:
    return StreamingResponse(
        _sse_stream(req.document_id), media_type="text/event-stream"
    )
