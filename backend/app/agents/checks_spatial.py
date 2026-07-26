"""The SPATIAL CHECK REGISTRY (spec §5.5) — the spatial-compliance sibling of
`agents/checks.py`. Same discipline: each check maps a checkable spatial
parameter to a REAL clause key (`spatial_clauses.json`) and a deterministic
threshold function. The pass/fail decision lives here, in Python, anchored to
a real clause — never in the LLM.

A check dict has the SAME shape as `checks.py`'s `Check` TypedDict (imported
directly, not redefined) PLUS one deliberate extension: `rule` returns
`Optional[bool]` rather than plain `bool`. `checks.py`'s scalar checks never
needed a third state; two of these six genuinely do (see the module docstring
on `_dead_end_verdict` / `_travel_distance_verdict` below) — a rule may be
UNABLE to reach a verdict (a required companion value is missing, or its
provenance isn't "stated") without that meaning the parameter conforms. Bool
callers keep working (`True`/`False` mean exactly what they do in
`checks.py`); the evaluator (the floor-plan endpoint) treats `None` as
"abstain, never fail" — the rule in spec §5.5's closing sentence: "Every
check must abstain (not fail) when a required companion value is missing or
provenance != 'stated'."

Each check also carries `abstain_reason: Callable[[dict], str]`, called only
when `rule(p)` returns `None`, so every abstention shown to the user explains
in plain language exactly why a verdict couldn't be reached — never a bare
"unknown".

Two checks (`EGRESS_DEAD_END`, `EGRESS_TRAVEL_DISTANCE`) implement a third
behaviour beyond simple abstention: NBC 4.4.2.2(c)'s dead-end limit (and
Table 5's travel-distance limit) depends on the room's occupancy group, which
`Room.occupancy_group` never carries in this build (the demo document never
states one, and guessing it is forbidden — see `spatial/extract.py`). An
unstated occupancy group does NOT always mean "abstain": if the measured
value breaches even the MOST PERMISSIVE limit NBC allows for any occupancy,
the verdict is FAIL regardless of which group applies; if it satisfies even
the STRICTEST limit, the verdict is PASS regardless. Abstention is reserved
for the genuinely ambiguous band in between, where the verdict really would
flip depending on a group the document never states.
"""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Callable, Optional, TypedDict

from ..config import DATA_DIR
from .checks import Check  # reused, not redefined — same TypedDict as the scalar registry

_NBC_TABLES_PATH = DATA_DIR / "standards" / "nbc_tables.json"

# NBC 4.4.2.2(c) verbatim: "shall not exceed 6 m for educational, institutional
# and assembly occupancies. For other occupancies, the same shall be 15 m."
_DEAD_END_STRICT_GROUPS = {"educational", "institutional", "assembly"}
_DEAD_END_STRICT_LIMIT_M = 6.0
_DEAD_END_LOOSE_LIMIT_M = 15.0

# Equipment kinds CEA Regulation 37(iii) governs (switchboards / LV panels).
_SWITCHBOARD_KINDS = ("switchboard", "lv_panel")


class SpatialCheck(TypedDict, total=False):
    """`checks.py::Check` plus the `Optional[bool]`-rule / `abstain_reason`
    extension described in the module docstring above."""

    id: str
    applies_when: Callable[[dict], bool]
    rule: Callable[[dict], Optional[bool]]
    abstain_reason: Callable[[dict], str]
    # Only set on checks whose finding text must vary by case (the two
    # unstated-occupancy checks) — overrides the endpoint's default finding
    # prose with wording that explicitly names why the verdict holds (or
    # doesn't) without a stated occupancy group. (param, verdict) -> sentence.
    explain: Callable[[dict, bool], str]
    clause_key: str
    severity: str
    why: str
    rule_text: str
    corrective: str
    domain: str


@lru_cache(maxsize=1)
def _nbc_tables() -> dict:
    """Load `nbc_tables.json` once per process. Missing/invalid file degrades
    to an empty dict — table-dependent checks then simply can't resolve a
    limit and abstain, never crash the endpoint (spec §5.6: never 500)."""
    try:
        return json.loads(_NBC_TABLES_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _table5_numeric_values() -> list[float]:
    """Every genuinely numeric travel-distance figure in Table 5, flattened.
    Cells whose value is the string "See Note 3" (construction of Type 3/4 is
    not permitted for that occupancy — NBC states no number there) are
    excluded, never coerced to a number."""
    table5 = _nbc_tables().get("table_5", {})
    out: list[float] = []

    def _walk(node: object) -> None:
        if not isinstance(node, dict):
            return
        if "value" in node:
            v = node["value"]
            if isinstance(v, (int, float)):
                out.append(float(v))
            return  # a leaf {"value": ..., "unit": ..., "verbatim_row": ...} — nothing else to recurse into
        for key, val in node.items():
            if key in ("_note", "_description", "notes", "source_page"):
                continue
            _walk(val)

    _walk(table5)
    return out


def _dead_end_limit_m(occupancy_group: str) -> float:
    group = occupancy_group.strip().lower()
    return _DEAD_END_STRICT_LIMIT_M if group in _DEAD_END_STRICT_GROUPS else _DEAD_END_LOOSE_LIMIT_M


def _travel_distance_limit_m(occupancy_group: str) -> Optional[float]:
    """table_5[group]'s Type-1/2-construction figure, or None when the group
    is unrecognised or (Industrial) splits into sub-groups the document never
    resolves — an unresolvable lookup abstains, it never guesses a subgroup."""
    table5 = _nbc_tables().get("table_5", {})
    entry = table5.get(occupancy_group.strip().lower())
    if not isinstance(entry, dict) or "types_1_and_2" not in entry:
        return None  # e.g. "industrial" splits into g1_g2/g3 — no single group value
    value = entry["types_1_and_2"].get("value")
    return float(value) if isinstance(value, (int, float)) else None


def _table4_mm_per_person(occupancy_group: str) -> Optional[float]:
    table4 = _nbc_tables().get("table_4", {})
    entry = table4.get(occupancy_group.strip().lower())
    if not isinstance(entry, dict):
        return None
    value = entry.get("level_components_and_ramps", {}).get("value")
    return float(value) if isinstance(value, (int, float)) else None


# --------------------------------------------------------------------------- #
# Cross-referencing helper — SWBD_REAR_PASSAGE needs its equipment's
# rear_clearance value, which lives in a SEPARATE flat-dict row (params.py
# emits one row per extracted value, not one row per equipment). Never
# mutates params.py's output; the evaluator calls this once per run and
# stamps the result onto a shallow COPY of each row before applies_when/rule
# see it (see `annotate_rear_clearance` below).
# --------------------------------------------------------------------------- #
def index_rear_clearance_m(params: list[dict]) -> dict[tuple[str, str], float]:
    """{(room_id, equipment_kind): rear_clearance_m} for every STATED
    rear_clearance row. A row whose provenance isn't "stated" is never
    indexed — a missing/unverified companion must read as "unknown", not
    as a stale/guessed number."""
    out: dict[tuple[str, str], float] = {}
    for p in params:
        if p.get("param") != "rear_clearance" or p.get("provenance") != "stated":
            continue
        room_id, kind = p.get("room_id"), p.get("equipment_kind")
        if room_id and kind:
            out[(room_id, kind)] = p["value"]
    return out


def annotate_rear_clearance(params: list[dict]) -> list[dict]:
    """Shallow-copies every row and stamps on `_rear_clearance_m` (the
    equipment's companion rear-clearance value, or None if never stated) so
    SWBD_REAR_PASSAGE's applies_when/rule can read it without params.py
    changing shape. Safe to call on the full param list unconditionally —
    rows other checks use simply carry an unused extra key."""
    index = index_rear_clearance_m(params)
    out = []
    for p in params:
        q = dict(p)
        q["_rear_clearance_m"] = index.get((p.get("room_id"), p.get("equipment_kind")))
        out.append(q)
    return out


# --------------------------------------------------------------------------- #
# The six checks.
# --------------------------------------------------------------------------- #
CHECKS_SPATIAL: list[SpatialCheck] = [
    {
        "id": "SWBD_FRONT_CLEARANCE",
        "domain": "spatial",
        "applies_when": lambda p: p.get("param") == "front_clearance"
        and p.get("equipment_kind") in _SWITCHBOARD_KINDS,
        "rule": lambda p: None if p.get("provenance") != "stated" else p["value"] >= 1.0,
        "abstain_reason": lambda p: (
            "the front-clearance value's provenance is not 'stated', so it cannot be checked "
            "against CEA Regulation 37(iii)(a) without a value grounded in the document text."
        ),
        "clause_key": "CEA_2010_37iii_a",
        "severity": "HIGH",
        "why": "Inadequate clear space in front of a switchboard/LV panel blocks safe operator "
        "access for racking/de-racking breakers and slows emergency isolation — a personnel-safety "
        "and unplanned-downtime risk in the electrical room.",
        "rule_text": "A clear space of not less than 1 m in width shall be provided in front of "
        "the switchboard (CEA Regulation 37(iii)(a)).",
        "corrective": "Revise the panel-room layout to provide at least 1.0 m clear space in "
        "front of the switchboard before energising.",
    },
    {
        "id": "SWBD_REAR_CLEARANCE",
        "domain": "spatial",
        "applies_when": lambda p: p.get("param") == "rear_clearance"
        and p.get("equipment_kind") in _SWITCHBOARD_KINDS,
        "rule": lambda p: (
            None if p.get("provenance") != "stated" else (p["value"] < 0.20 or p["value"] > 0.75)
        ),
        "abstain_reason": lambda p: (
            "the rear-clearance value's provenance is not 'stated', so it cannot be checked "
            "against CEA Regulation 37(iii)(b) without a value grounded in the document text."
        ),
        "clause_key": "CEA_2010_37iii_b",
        "severity": "MEDIUM",
        "why": "A rear space between 20 cm and 75 cm is neither tight enough to prevent entry nor "
        "wide enough for a safe maintenance passage — CEA 37(iii)(b) prohibits this in-between band "
        "specifically because it invites unsafe access to live rear connections.",
        "rule_text": "Where attachments or bare connections exist at the back of a switchboard, "
        "the rear space shall be either less than 20 cm or more than 75 cm in width (CEA "
        "Regulation 37(iii)(b)).",
        "corrective": "Redesign the panel-room layout so the rear space is either under 20 cm "
        "(sealed off) or over 75 cm (a proper maintenance passage per 37(iii)(c)).",
    },
    {
        "id": "SWBD_REAR_PASSAGE",
        "domain": "spatial",
        # Only fires when the rear space is KNOWN to exceed 75 cm (the clause's
        # own trigger) OR is unknown (ambiguous whether the clause even
        # applies — abstain rather than silently skip). A KNOWN rear space
        # <= 75 cm means 37(iii)(c) genuinely does not govern this equipment,
        # so applies_when returns False and no verdict/abstention is produced.
        "applies_when": lambda p: p.get("param") == "rear_passage_height"
        and p.get("equipment_kind") in _SWITCHBOARD_KINDS
        and (p.get("_rear_clearance_m") is None or p.get("_rear_clearance_m") > 0.75),
        "rule": lambda p: (
            None
            if p.get("provenance") != "stated" or p.get("_rear_clearance_m") is None
            else p["value"] >= 1.8
        ),
        "abstain_reason": lambda p: (
            "this equipment's rear passage height's provenance is not 'stated'."
            if p.get("provenance") != "stated"
            else "this equipment's rear clearance is not stated in the document, so it is unknown "
            "whether CEA 37(iii)(c)'s passage-way requirement (triggered only when the rear space "
            "exceeds 75 cm) applies here at all."
        ),
        "clause_key": "CEA_2010_37iii_c",
        "severity": "MEDIUM",
        "why": "Where the rear space exceeds 75 cm, CEA 37(iii)(c) requires a passage clear to "
        "1.8 m height — anything less risks a maintenance technician striking overhead cable "
        "trays/conduit while accessing live rear connections.",
        "rule_text": "If the space behind the switchboard exceeds 75 cm in width, there shall be "
        "a passage way from either end of the switchboard, clear to a height of 1.8 m (CEA "
        "Regulation 37(iii)(c)).",
        "corrective": "Clear obstructions (cable trays, conduit, ductwork) from the rear passage "
        "so it is unobstructed to at least 1.8 m height along its full length.",
    },
    {
        "id": "EGRESS_DEAD_END",
        "domain": "spatial",
        "applies_when": lambda p: p.get("param") == "dead_end_corridor",
        "rule": lambda p: _dead_end_verdict(p),
        "abstain_reason": lambda p: _dead_end_abstain_reason(p),
        "explain": lambda p, verdict: _dead_end_explain(p, verdict),
        "clause_key": "NBC2016_4.4.2.2c",
        "severity": "HIGH",
        "why": "A dead-end corridor that runs longer than NBC allows leaves occupants with only "
        "one direction of escape for too great a distance — a life-safety risk if that single "
        "route is blocked by fire/smoke.",
        "rule_text": "The dead-end corridor length in exit access shall not exceed 6 m for "
        "educational, institutional and assembly occupancies; for other occupancies the limit is "
        "15 m (NBC 2016 Part 4, Cl 4.4.2.2(c)).",
        "corrective": "Add a second means of egress from the dead-end corridor, or shorten it to "
        "within the governing NBC limit.",
    },
    {
        "id": "EGRESS_TRAVEL_DISTANCE",
        "domain": "spatial",
        "applies_when": lambda p: p.get("param") == "travel_distance",
        "rule": lambda p: _travel_distance_verdict(p),
        "abstain_reason": lambda p: _travel_distance_abstain_reason(p),
        "explain": lambda p, verdict: _travel_distance_explain(p, verdict),
        "clause_key": "NBC2016_4.4.2.2a",
        "severity": "HIGH",
        "why": "Travel distance beyond NBC's Table 5 limit increases the time occupants are "
        "exposed to a developing fire/smoke condition before reaching a protected exit.",
        "rule_text": "Exits shall be so located that the travel distance on the floor shall not "
        "exceed the distance given in Table 5 (NBC 2016 Part 4, Cl 4.4.2.2(a)).",
        "corrective": "Add an exit (or relocate an existing one) so no point on the floor exceeds "
        "the Table 5 travel-distance limit for its occupancy/construction type.",
    },
    {
        "id": "EGRESS_EXIT_WIDTH",
        "domain": "spatial",
        "applies_when": lambda p: p.get("param") == "exit_width",
        "rule": lambda p: _exit_width_verdict(p),
        "abstain_reason": lambda p: _exit_width_abstain_reason(p),
        "clause_key": "NBC2016_4.4.2.3",
        "severity": "HIGH",
        "why": "An exit door narrower than its occupant load requires (Table 4 mm/person) creates "
        "a bottleneck that slows evacuation exactly when speed matters most.",
        "rule_text": "The required width of a means of egress shall be determined from the "
        "occupant load and Table 4's capacity factor (mm/person) for the occupancy group (NBC "
        "2016 Part 4, Cl 4.4.2.3).",
        "corrective": "Widen the exit door (or add an additional exit) so the total clear width "
        "meets occupant_load x Table 4 mm/person for the stated occupancy group.",
    },
]


# --------------------------------------------------------------------------- #
# EGRESS_DEAD_END — tri-state rule (see module docstring for the reasoning).
# --------------------------------------------------------------------------- #
def _dead_end_verdict(p: dict) -> Optional[bool]:
    if p.get("provenance") != "stated":
        return None
    value = p["value"]
    group = p.get("occupancy_group")
    if group:
        return value <= _dead_end_limit_m(group)
    # Occupancy group not stated — determinate-regardless-of-group reasoning.
    if value > _DEAD_END_LOOSE_LIMIT_M:
        return False  # breaches even the most permissive (15 m) limit -> FAIL no matter the group
    if value <= _DEAD_END_STRICT_LIMIT_M:
        return True  # satisfies even the strictest (6 m) limit -> PASS no matter the group
    return None  # 6 m < value <= 15 m: genuinely ambiguous without the occupancy group


def _dead_end_abstain_reason(p: dict) -> str:
    if p.get("provenance") != "stated":
        return "the dead-end corridor length's provenance is not 'stated'."
    return (
        "occupancy classification not stated in the document; NBC's dead-end limit is 6 m or "
        "15 m depending on group, and this value falls between them."
    )


def _dead_end_explain(p: dict, verdict: bool) -> str:
    group = p.get("occupancy_group")
    value = p["value"]
    if group:
        limit = _dead_end_limit_m(group)
        outcome = "conforms to" if verdict else "exceeds"
        return f"The dead-end corridor measures {value:g} m, which {outcome} the {limit:g} m limit for {group} occupancy (NBC 4.4.2.2(c))."
    if verdict:
        return (
            f"The dead-end corridor measures {value:g} m, which satisfies even the strictest "
            "NBC 4.4.2.2(c) limit (6 m, for educational/institutional/assembly occupancies), so "
            "the verdict holds without the occupancy group being stated."
        )
    return (
        f"The dead-end corridor measures {value:g} m, which breaches the limit for every "
        "occupancy classification in NBC 4.4.2.2(c) (6 m or 15 m), so the verdict holds without "
        "the occupancy group being stated."
    )


# --------------------------------------------------------------------------- #
# EGRESS_TRAVEL_DISTANCE — same determinate-regardless-of-group reasoning,
# applied against Table 5's overall min/max instead of the two hardcoded
# dead-end limits (Table 5 has far more than two possible values).
# --------------------------------------------------------------------------- #
def _travel_distance_verdict(p: dict) -> Optional[bool]:
    if p.get("provenance") != "stated":
        return None
    value = p["value"]
    group = p.get("occupancy_group")
    if group:
        limit = _travel_distance_limit_m(group)
        return None if limit is None else value <= limit
    values = _table5_numeric_values()
    if not values:
        return None
    lo, hi = min(values), max(values)
    if value > hi:
        return False  # breaches even the most permissive Table 5 limit -> FAIL no matter the group
    if value <= lo:
        return True  # satisfies even the strictest Table 5 limit -> PASS no matter the group
    return None  # genuinely ambiguous without the occupancy group


def _travel_distance_abstain_reason(p: dict) -> str:
    if p.get("provenance") != "stated":
        return "the travel-distance value's provenance is not 'stated'."
    group = p.get("occupancy_group")
    if group:
        return (
            f"occupancy group '{group}' has no single Table 5 travel-distance figure (it splits "
            "into construction-type sub-groups the document does not resolve)."
        )
    values = _table5_numeric_values()
    lo, hi = (min(values), max(values)) if values else (None, None)
    return (
        "occupancy classification not stated in the document; NBC Table 5's travel-distance "
        f"limit ranges from {lo:g} m to {hi:g} m depending on group, and this value falls "
        "between those bounds."
        if values
        else "NBC Table 5 could not be loaded, so no travel-distance limit is available."
    )


def _travel_distance_explain(p: dict, verdict: bool) -> str:
    group = p.get("occupancy_group")
    value = p["value"]
    if group:
        limit = _travel_distance_limit_m(group)
        outcome = "conforms to" if verdict else "exceeds"
        return f"The travel distance measures {value:g} m, which {outcome} the {limit:g} m Table 5 limit for {group} occupancy (NBC 4.4.2.2(a))."
    values = _table5_numeric_values()
    lo, hi = min(values), max(values)
    if verdict:
        return (
            f"The travel distance measures {value:g} m, which satisfies even the strictest Table "
            f"5 limit ({lo:g} m), so the verdict holds without the occupancy group being stated."
        )
    return (
        f"The travel distance measures {value:g} m, which breaches every Table 5 limit (up to "
        f"{hi:g} m for the most permissive occupancy/construction combination), so the verdict "
        "holds without the occupancy group being stated."
    )


# --------------------------------------------------------------------------- #
# EGRESS_EXIT_WIDTH — needs BOTH occupant_load and occupancy_group; no
# determinate-regardless-of-group shortcut exists here (Table 4's mm/person
# factor varies too widely across groups to bound without one), so an
# unstated group always abstains rather than guessing a factor.
# --------------------------------------------------------------------------- #
def _exit_width_verdict(p: dict) -> Optional[bool]:
    if p.get("provenance") != "stated":
        return None
    if p.get("occupant_load") is None or p.get("occupant_load_provenance") != "stated":
        return None
    group = p.get("occupancy_group")
    if not group:
        return None
    factor = _table4_mm_per_person(group)
    if factor is None:
        return None
    required_mm = p["occupant_load"] * factor
    return p["value"] >= required_mm


def _exit_width_abstain_reason(p: dict) -> str:
    if p.get("provenance") != "stated":
        return "the exit-door width's provenance is not 'stated'."
    if p.get("occupant_load") is None or p.get("occupant_load_provenance") != "stated":
        return (
            "the room's occupant load is not stated in the document, so the required exit width "
            "(occupant load x Table 4 mm/person) cannot be computed."
        )
    group = p.get("occupancy_group")
    if not group:
        return (
            "occupancy classification not stated in the document, so NBC Table 4's capacity "
            "factor (mm/person) for this exit cannot be resolved."
        )
    return f"occupancy group '{group}' has no Table 4 capacity-factor entry."


def applicable_checks_spatial(param: dict) -> list[SpatialCheck]:
    """All spatial checks whose applies_when matches this parameter — mirrors
    `checks.py::applicable_checks`."""
    return [c for c in CHECKS_SPATIAL if c["applies_when"](param)]
