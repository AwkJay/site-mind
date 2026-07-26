"""Spatial Compliance endpoint (spec §5.6) — `POST /api/compliance/floor-plan`.

Mirrors `agents/compliance.py::ingest_document`'s upload/error-handling style
exactly (same accepted file types, same `UnsupportedFileType` -> 400
handling), but wires the spatial path: PERCEIVE (`spatial/extract.py`,
regex-first, span-gated) -> LAYOUT (`spatial/layout.py`, deterministic shelf
packing) -> DECIDE (`agents/checks_spatial.py`, deterministic Python
thresholds against real CEA/NBC clauses) -> respond.

Never raises on a document that simply has no spatial content: an empty/
non-spatial document returns `has_spatial_data: false` with a plain-language
`reason`, not a 4xx/5xx. The only error responses are the same ones
`/api/compliance/ingest` already gives for a genuinely unsupported file type.
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile

from .. import ingest
from ..schemas import NCR, SourceSpan
from ..spatial.extract import extract_spatial
from ..spatial.layout import ClearanceZone, FloorPlan, Rect, place
from ..spatial.params import to_params
from ..spatial.schemas import SpatialSpec
from ..standards import get_clause
from .checks_spatial import annotate_rear_clearance, applicable_checks_spatial

# Required-clearance figures for the two checks that draw a `ClearanceZone`
# (spec extension, endpoint §3). Only front clearance has a single-number
# minimum (CEA 37(iii)(a), >= 1.0 m) — the same constant `checks_spatial.py`
# already uses to compute the verdict, not a second source of truth. Rear
# clearance's rule (CEA 37(iii)(b)) is a forbidden BAND (< 0.20 m or > 0.75 m
# is fine; the failure is landing IN BETWEEN), which has no single "required"
# number to assert — `required_m`/`required_rect` stay `None` for it rather
# than fabricate one.
_CLEARANCE_REQUIRED_M: dict[str, float] = {"SWBD_FRONT_CLEARANCE": 1.0}
_CLEARANCE_KIND: dict[str, str] = {"SWBD_FRONT_CLEARANCE": "front", "SWBD_REAR_CLEARANCE": "rear"}

router = APIRouter(prefix="/api/compliance", tags=["compliance"])

# Zones the platform deliberately renders but never judges, because no freely
# redistributable governing clause is digitised for them (spec §5.6 example;
# spec §9 "out of scope": rack/aisle geometry until such a clause exists).
_NOT_CHECKED_ZONE_REASONS: dict[str, str] = {
    "server_hall": (
        "Rack and aisle geometry is governed by ASHRAE TC 9.9, which is not a freely "
        "redistributable standard and is not digitised here. Rendered for context; "
        "deliberately not judged."
    ),
}

# Which flat-param `param` names come from which SpatialSpec collection —
# used to key the geometry index below by the same (category, room_id,
# equipment_kind, param, source_quote) tuple on both sides. `source_quote` is
# the disambiguator: it's the verbatim, span-gated sentence a value came from,
# so it's effectively unique per extracted value even when two rows share a
# room_id/equipment_kind (e.g. two switchboards in the same room).
_EQUIPMENT_PARAMS = {"front_clearance", "rear_clearance", "rear_passage_height"}
_FACT_PARAMS = {"dead_end_corridor", "travel_distance", "corridor_width"}


def _geometry_index(spec: SpatialSpec) -> dict[tuple, dict]:
    """Maps a flat param row back to the `geometry_ref` the frontend needs to
    pin a finding onto the floor map. Built straight from `spec` (never from
    `to_params()`'s flattened dicts, which don't carry an equipment/exit's own
    id) — see the module docstring's note on `source_quote` uniqueness."""
    index: dict[tuple, dict] = {}
    for eq in spec.equipment:
        for field_name, ext in (
            ("front_clearance", eq.front_clearance_m),
            ("rear_clearance", eq.rear_clearance_m),
            ("rear_passage_height", eq.rear_passage_height_m),
        ):
            if ext is not None and ext.verified:
                key = ("equipment", eq.room_id, eq.kind, field_name, ext.source_quote)
                index[key] = {"kind": "equipment", "id": eq.id}
    for fact in spec.facts:
        if fact.value.verified and fact.room_id is not None:
            key = ("fact", fact.room_id, None, fact.kind, fact.value.source_quote)
            index[key] = {"kind": "room", "id": fact.room_id}
    for ex in spec.exits:
        if ex.width_mm is not None and ex.width_mm.verified:
            key = ("exit", ex.room_id, None, "exit_width", ex.width_mm.source_quote)
            index[key] = {"kind": "exit", "id": ex.id}
    return index


def _geometry_key(p: dict) -> Optional[tuple]:
    name = p.get("param")
    if name in _EQUIPMENT_PARAMS:
        return ("equipment", p.get("room_id"), p.get("equipment_kind"), name, p.get("source_quote"))
    if name in _FACT_PARAMS:
        return ("fact", p.get("room_id"), None, name, p.get("source_quote"))
    if name == "exit_width":
        return ("exit", p.get("room_id"), None, name, p.get("source_quote"))
    return None


def _item_label(p: dict) -> str:
    room = p.get("room_id") or "unspecified location"
    kind = p.get("equipment_kind")
    return f"{room} — {kind}" if kind else room


def _default_finding(p: dict, check) -> str:
    label = str(p.get("param", "")).replace("_", " ")
    value = p.get("value")
    value_str = f"{value:g}" if isinstance(value, (int, float)) else str(value)
    unit = p.get("unit", "")
    return (
        f"{_item_label(p)} specifies {label} = {value_str} {unit}".strip()
        + f", which does not meet {check['rule_text']}"
    )


def _finding_text(p: dict, check) -> str:
    explain = check.get("explain")
    if explain is not None:
        return explain(p, False)
    return _default_finding(p, check)


def _clearance_zone(
    p: dict, check_id: str, clause_key: str, status: str, plan: FloorPlan, geometry_ref: Optional[dict]
) -> Optional[ClearanceZone]:
    """Builds one `ClearanceZone` entry (endpoint §3) for a front/rear
    clearance check. `provided_m`/`status`/`clause_key` are always the real
    computed values — never fabricated. The rects are a rendering aid only:
    the document never states the switchboard/panel's own footprint, so the
    band's lateral extent is drawn across its parent room's stated width
    (never invented) rather than guessed. If the equipment glyph or its room
    cannot be found in `plan` (should not happen for a verified param, but
    defensive), the rects are left `None` rather than guessed — the numeric
    fields are still returned, honestly, on their own."""
    kind = _CLEARANCE_KIND[check_id]
    provided_m = p["value"]
    required_m = _CLEARANCE_REQUIRED_M.get(check_id) if status != "abstain" else None

    equipment_id = geometry_ref["id"] if geometry_ref and geometry_ref.get("kind") == "equipment" else None
    provided_rect: Optional[Rect] = None
    required_rect: Optional[Rect] = None
    if equipment_id is not None:
        eq = next((e for e in plan.equipment if e.id == equipment_id), None)
        room = next((r for r in plan.rooms if r.id == p.get("room_id")), None)
        if eq is not None and room is not None:
            if kind == "front":
                provided_rect = Rect(x_m=room.x_m, y_m=eq.y_m, width_m=room.width_m, length_m=provided_m)
                if required_m is not None:
                    required_rect = Rect(x_m=room.x_m, y_m=eq.y_m, width_m=room.width_m, length_m=required_m)
            else:  # "rear" — band runs from the glyph back toward the wall
                provided_rect = Rect(
                    x_m=room.x_m, y_m=eq.y_m - provided_m, width_m=room.width_m, length_m=provided_m
                )
                # No single required threshold for the rear band (see module
                # docstring) -> required_rect stays None regardless.

    if equipment_id is None:
        return None  # not an equipment-anchored clearance row — nothing honest to draw

    return ClearanceZone(
        equipment_id=equipment_id,
        kind=kind,
        provided_m=provided_m,
        required_m=required_m,
        status=status,  # type: ignore[arg-type]
        clause_key=clause_key,
        provided_rect=provided_rect,
        required_rect=required_rect,
    )


# Extraction-stage `what` labels that are always-abstain summaries of a
# condition `checks_spatial.py` also abstains on, per-item, once the
# corresponding param actually reaches a check (spec §5.2's "exit occupant
# load" always-abstain in `extract.py` vs `EGRESS_EXIT_WIDTH`'s own
# abstain_reason in `checks_spatial.py`). Both are honest and both are
# individually correct — but showing both to the user for the same underlying
# missing fact reads as the same abstention reported twice with slightly
# different wording. The check-stage version is kept because it names the
# specific room/equipment item and the check id (e.g. "exit width at corridor
# (check EGRESS_EXIT_WIDTH)"), which is strictly more actionable than the
# extraction-stage document-level summary.
_SUPERSEDED_BY_CHECK: dict[str, str] = {"exit width adequacy": "EGRESS_EXIT_WIDTH"}


def _dedupe_abstentions(extraction_abstentions: list[dict], check_abstentions: list[dict]) -> list[dict]:
    """Merges extraction-stage and check-stage abstentions, dropping an
    extraction-stage entry whenever a check-stage entry for the same known
    check id is already present (see `_SUPERSEDED_BY_CHECK`) — the check-stage
    entry is more specific and is kept instead. Every other abstention from
    either stage passes through unchanged; `coverage['abstained']` is derived
    from this function's output, not from the raw pre-dedupe counts, so the
    honesty metric always matches what the user actually sees."""
    present_check_whats = [a.get("what", "") for a in check_abstentions]

    def _is_superseded(a: dict) -> bool:
        check_id = _SUPERSEDED_BY_CHECK.get(a.get("what", ""))
        if check_id is None:
            return False
        return any(f"(check {check_id})" in w for w in present_check_whats)

    kept_extraction = [a for a in extraction_abstentions if not _is_superseded(a)]
    return kept_extraction + check_abstentions


def _run_spatial_checks(spec: SpatialSpec, plan: FloorPlan) -> tuple[list[NCR], list[dict], dict, list[ClearanceZone]]:
    """PERCEIVE's output (spec, already span-gated) -> DECIDE. Every
    determinate verdict either conforms silently (mirrors
    `agents/compliance.py::evaluate`'s `conforming` list — not surfaced as a
    finding) or becomes an NCR; every indeterminate one becomes an
    Abstention. Also collects a `ClearanceZone` per front/rear clearance
    check evaluated (endpoint §3), reusing the exact verdict already computed
    here rather than recomputing it. Returns (findings, abstentions, coverage,
    clearance_zones)."""
    params = annotate_rear_clearance(to_params(spec))
    geo_index = _geometry_index(spec)

    ncrs: list[NCR] = []
    abstentions: list[dict] = []
    clearance_zones: list[ClearanceZone] = []
    checks_run = 0
    seq = 1

    for p in params:
        for check in applicable_checks_spatial(p):
            checks_run += 1
            verdict = check["rule"](p)
            geometry_ref = geo_index.get(_geometry_key(p))

            if check["id"] in _CLEARANCE_KIND:
                status = "pass" if verdict is True else ("abstain" if verdict is None else "fail")
                zone = _clearance_zone(p, check["id"], check["clause_key"], status, plan, geometry_ref)
                if zone is not None:
                    clearance_zones.append(zone)

            if verdict is True:
                continue  # conforms — nothing to report, same as checks.py's conforming path

            if verdict is None:
                reason = check["abstain_reason"](p)
                label = str(p.get("param", "")).replace("_", " ")
                abstentions.append(
                    {"what": f"{label} at {_item_label(p)} (check {check['id']})", "why": reason}
                )
                continue

            # verdict is False -> non-conformance
            citation = get_clause(check["clause_key"])
            ncrs.append(
                NCR(
                    id=f"SPC-{seq:04d}",
                    item=_item_label(p),
                    severity=check["severity"],  # type: ignore[arg-type]
                    finding=_finding_text(p, check),
                    source=SourceSpan(quote=p.get("source_quote", ""), location=p.get("room_id") or "uploaded document"),
                    citation=citation,
                    why_it_matters=check["why"],
                    corrective_action=check["corrective"],
                    domain="spatial",
                    geometry_ref=geometry_ref,
                )
            )
            seq += 1

    coverage = {
        "params_extracted": len(params),
        "params_checked": checks_run,
        "abstained": len(abstentions),
    }
    return ncrs, abstentions, coverage, clearance_zones


def _not_checked_zones(rooms_zones: set[str]) -> list[dict]:
    return [
        {"zone": zone, "reason": reason}
        for zone, reason in _NOT_CHECKED_ZONE_REASONS.items()
        if zone in rooms_zones
    ]


def _no_spatial_data(document_id: str, reason: str) -> dict:
    return {
        "document_id": document_id,
        "has_spatial_data": False,
        "reason": reason,
        "floor_plan": None,
        "findings": [],
        "abstentions": [],
        "not_checked_zones": [],
        "coverage": {"params_extracted": 0, "params_checked": 0, "abstained": 0},
    }


@router.post("/floor-plan")
async def floor_plan(file: UploadFile = File(...)) -> dict:
    content = await file.read()
    try:
        text = ingest.extract_text(file.filename or "upload", content)
    except ingest.UnsupportedFileType as e:
        raise HTTPException(status_code=400, detail=str(e))

    document_id = f"floorplan-{uuid.uuid4().hex[:12]}"

    if not text.strip():
        return _no_spatial_data(
            document_id,
            "No extractable text found in this file (scanned/image-only PDFs are not "
            "supported by this text-first pipeline).",
        )

    spec = extract_spatial(text, document_id)
    if not (spec.rooms or spec.equipment or spec.exits or spec.facts):
        return _no_spatial_data(
            document_id,
            "No spatial content (room dimensions, equipment clearances, exits, or egress "
            "facts) was found in this document — the scalar Compliance path "
            "(POST /api/compliance/ingest) may still apply.",
        )

    plan = place(spec)
    ncrs, check_abstentions, coverage, clearance_zones = _run_spatial_checks(spec, plan)
    plan.clearance_zones = clearance_zones

    all_abstentions = _dedupe_abstentions(
        [a.model_dump() for a in spec.abstentions], check_abstentions
    )
    # `coverage["abstained"]` must count every abstention actually shown to
    # the user, not just the check-derived subset `_run_spatial_checks`
    # itself produced — extraction-time abstentions (a value dropped by the
    # span gate, or "no sentence states X at all") belong in this honesty
    # metric too.
    coverage["abstained"] = len(all_abstentions)
    zones_present = {r.zone for r in plan.rooms}

    return {
        "document_id": document_id,
        "has_spatial_data": True,
        "reason": None,
        "floor_plan": plan.model_dump(),
        "findings": [n.model_dump() for n in ncrs],
        "abstentions": all_abstentions,
        "not_checked_zones": _not_checked_zones(zones_present),
        "coverage": coverage,
    }
