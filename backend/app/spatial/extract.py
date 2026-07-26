"""Regex-first spatial extraction (spec §5.2) — the PERCEIVE step for the
Spatial Compliance path. Mirrors `app/ingest.py`'s discipline exactly: a wrong
regex match is instantly auditable against the shown `source_quote`, so it
can never launder a hallucination the way free-form extraction could.

Reuses, rather than reimplements:
  - `app/ingest.py::_sentences` — the existing sentence splitter, imported
    directly (not duplicated).
  - The exact verbatim-substring + value-in-span two-check gate that
    `app/llm_extract.py::verify_spans` uses (checks (a) and (b) there). The
    two tiny primitives (`_norm`, `_value_str_variants`) are imported directly
    from `app.llm_extract` rather than duplicated — the span gate is the most
    integrity-critical primitive in this codebase and must exist exactly
    once. Importing `app.llm_extract` at module level is safe: that module's
    own top-level imports are only `json`, `re`, `typing`, `config`, and
    `ingest` — no LLM SDK. The Claude Agent SDK call lives in a function
    inside `llm_extract.py` and is only ever reached at runtime when an
    online extraction path actually calls it; nothing at import time touches
    it. See `tests/test_spatial_extract.py::test_flag_off_imports_no_llm_module`,
    which asserts the property that actually matters — no LLM SDK / network
    client module is newly imported — not a blanket ban on the substring
    "llm" in module names.

LLM *enhancement* (an optional second pass, not perception itself) is gated
on `config.SPATIAL_LLM_EXTRACTION_ENABLED` (default 0). When off, this module
never imports an LLM SDK at all — see `extract_spatial_enhanced` below.
"""
from __future__ import annotations

import re

from .. import config
from ..ingest import _sentences
from ..llm_extract import _norm, _value_str_variants
from .schemas import (
    Abstention,
    Adjacency,
    Equipment,
    ExitDoor,
    Extracted,
    NorthOrientation,
    Room,
    SpatialFact,
    SpatialSpec,
    WallPlacement,
)  # noqa: F401  (NorthOrientation/WallPlacement are inert fields in this slice — see spec §9)


# --------------------------------------------------------------------------- #
# Span-verification gate (integrity core — NO guessing past this point).
#
# `verify_span` is built on `_norm` / `_value_str_variants`, imported above
# directly from `app/llm_extract.py::verify_spans` — the SAME two checks
# ((a) verbatim-substring, (b) value-in-span) that module uses, not a
# reimplementation of them. A spatial value only survives if its full
# containing sentence is a literal (whitespace-normalized) substring of the
# document AND the numeric value is written inside that sentence — the same
# integrity bar as the scalar path.
# --------------------------------------------------------------------------- #
def verify_span(value: float, quote: str, doc_norm_low: str) -> bool:
    """True iff `quote` (whitespace-normalized) is a literal substring of the
    document AND `value` is written somewhere inside `quote`. Same two checks
    as `llm_extract.verify_spans()`'s (a)/(b) gates, reused via its own
    primitives — not a second implementation of the substring logic."""
    quote_norm = _norm(quote)
    if not quote_norm:
        return False
    if quote_norm.lower() not in doc_norm_low:
        return False
    return any(v in quote_norm for v in _value_str_variants(value))


def _gate(value: float, unit: str, quote: str, doc_norm_low: str) -> Extracted | None:
    """Returns a verified Extracted, or None if the span gate rejects it.
    Callers are responsible for recording an Abstention on None."""
    if not verify_span(value, quote, doc_norm_low):
        return None
    return Extracted(value=value, unit=unit, source_quote=_norm(quote), verified=True)


def verify_text_span(quote: str, doc_norm_low: str) -> bool:
    """Check (a) alone from the same gate `verify_span` uses above — verbatim
    (whitespace-normalized) substring only. Used for text-only spatial claims
    (room-to-room adjacency) that carry no numeric value to additionally
    verify, exactly per `Adjacency`'s docstring in `schemas.py`."""
    q = _norm(quote)
    if not q:
        return False
    return q.lower() in doc_norm_low


# --------------------------------------------------------------------------- #
# Room-name -> zone / slug resolution.
# --------------------------------------------------------------------------- #
_ZONE_KEYWORDS: list[tuple[tuple[str, ...], str]] = [
    (("data hall", "server hall", "white space", "it room", "it hall"), "server_hall"),
    (
        ("switchroom", "switchgear", "lv panel room", "electrical room", "hv room", "mv room", "switchboard room"),
        "electrical",
    ),
    (("cooling plant", "chiller", "crac", "plant room", "pump room", "cooling"), "cooling"),
    (("corridor", "passage", "egress route"), "corridor"),
]


def _zone_for(name: str) -> str:
    low = name.lower()
    for keywords, zone in _ZONE_KEYWORDS:
        if any(k in low for k in keywords):
            return zone
    return "other"


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")
    return s or "room"


_EQUIP_KEYWORDS: list[tuple[tuple[str, ...], str]] = [
    (("switchboard",), "switchboard"),
    (("lv panel", "panel"), "lv_panel"),
    (("transformer",), "transformer"),
    (("genset", "generator"), "genset"),
    (("crac", "cooling unit"), "crac"),
    (("rack",), "rack_row"),
]


def _equip_kind_for(text: str) -> str:
    low = text.lower()
    for keywords, kind in _EQUIP_KEYWORDS:
        if any(k in low for k in keywords):
            return kind
    return "lv_panel"


# --------------------------------------------------------------------------- #
# Regexes. Each field has a primary phrasing (used by the demo doc) plus 2-3
# realistic variants exercised only in tests/test_spatial_extract.py.
# --------------------------------------------------------------------------- #
_NAME = r"(?:the\s+)?([A-Za-z][A-Za-z0-9 /\-]{1,45}?)"
_NUM = r"(\d+(?:\.\d+)?)"

# Room dimensions ------------------------------------------------------------
# "Data Hall 1 measures 30 m by 20 m [in plan]."
# "The LV Switchroom measures 12 m x 8 m ..."
# "The Cooling Plant Room measures 14 m × 10 m ..."
_ROOM_DIM_MEASURES_RE = re.compile(
    rf"(?i){_NAME}\s+measures\s+{_NUM}\s*m\s*(?:by|x|×)\s*{_NUM}\s*m"
)
# "The Generator Yard is 20 m wide by 15 m long."
_ROOM_DIM_WIDE_LONG_RE = re.compile(
    rf"(?i){_NAME}\s+is\s+{_NUM}\s*m\s+wide\s*(?:and|by)?\s*{_NUM}\s*m\s+long"
)
# "The UPS Room has a footprint of 10 m x 6 m."
_ROOM_DIM_FOOTPRINT_RE = re.compile(
    rf"(?i){_NAME}\s+(?:has\s+a\s+)?footprint\s+of\s+{_NUM}\s*m\s*(?:x|×|by)\s*{_NUM}\s*m"
)
_ROOM_DIM_PATTERNS = (_ROOM_DIM_MEASURES_RE, _ROOM_DIM_WIDE_LONG_RE, _ROOM_DIM_FOOTPRINT_RE)

# Front clearance --------------------------------------------------------- #
# "A clear space of 0.8 m is maintained in front of the LV distribution panel."
_FRONT_CLEARANCE_RE_A = re.compile(
    rf"(?i)clear\s+space\s+of\s+{_NUM}\s*m\s+is\s+maintained\s+in\s+front\s+of\s+{_NAME}[.,;]"
)
# "A front clearance of 0.8 m is provided for the switchboard."
_FRONT_CLEARANCE_RE_B = re.compile(rf"(?i)front\s+clearance\s+of\s+{_NUM}\s*m")
# "0.8 m of clear space is available in front of the panel."
_FRONT_CLEARANCE_RE_C = re.compile(
    rf"(?i){_NUM}\s*m\s+of\s+clear\s+space\s+(?:is\s+available\s+)?in\s+front\s+of\s+{_NAME}[.,;]"
)
_FRONT_CLEARANCE_PATTERNS = (_FRONT_CLEARANCE_RE_A, _FRONT_CLEARANCE_RE_B, _FRONT_CLEARANCE_RE_C)

# Rear clearance ------------------------------------------------------------ #
# "A rear clearance of 0.9 m is maintained behind the LV panel row, ..."
_REAR_CLEARANCE_RE_A = re.compile(rf"(?i)rear\s+clearance\s+of\s+{_NUM}\s*m")
# "0.9 m of clear space is maintained behind the switchboard."
_REAR_CLEARANCE_RE_B = re.compile(
    rf"(?i){_NUM}\s*m\s+of\s+clear\s+space\s+is\s+maintained\s+behind\s+{_NAME}[.,;]"
)
# "The clearance behind the panel is 0.9 m."
_REAR_CLEARANCE_RE_C = re.compile(
    rf"(?i)clearance\s+behind\s+(?:the\s+)?[A-Za-z][A-Za-z0-9 /\-]{{1,45}}?\s+is\s+{_NUM}\s*m"
)
_REAR_CLEARANCE_PATTERNS = (_REAR_CLEARANCE_RE_A, _REAR_CLEARANCE_RE_B, _REAR_CLEARANCE_RE_C)

# Rear passage height -------------------------------------------------------- #
# "... the passage behind the panel remains clear to a height of 2.1 m ..."
_REAR_PASSAGE_RE_A = re.compile(rf"(?i)clear\s+to\s+a\s+height\s+of\s+{_NUM}\s*m")
# "Passage height behind the switchboard is 2.1 m."
_REAR_PASSAGE_RE_B = re.compile(rf"(?i)passage\s+height[^.;]{{0,60}}?\bis\s+{_NUM}\s*m")
# "A rear passage height of 2.1 m is maintained."
_REAR_PASSAGE_RE_C = re.compile(rf"(?i)rear\s+passage\s+height\s+of\s+{_NUM}\s*m")
_REAR_PASSAGE_PATTERNS = (_REAR_PASSAGE_RE_A, _REAR_PASSAGE_RE_B, _REAR_PASSAGE_RE_C)

# Dead-end corridor ----------------------------------------------------------- #
# "... the dead-end run measures 18 m from the last point of access ... to the terminating wall."
_DEAD_END_RE_A = re.compile(rf"(?i)dead[-\s]?end\s+run\s+measures\s+{_NUM}\s*m")
# "The dead-end corridor is 18 m long."
_DEAD_END_RE_B = re.compile(rf"(?i)dead[-\s]?end\s+corridor\s+(?:is|of)\s+{_NUM}\s*m")
# "The corridor terminates in a dead end 18 m from the last point of access."
_DEAD_END_RE_C = re.compile(rf"(?i)terminates\s+in\s+a\s+dead\s+end[^.;]{{0,40}}?{_NUM}\s*m")
_DEAD_END_PATTERNS = (_DEAD_END_RE_A, _DEAD_END_RE_B, _DEAD_END_RE_C)

# Travel distance (never stated in the demo doc — tested + always-checked
# abstention only). ---------------------------------------------------------- #
_TRAVEL_DIST_RE_A = re.compile(rf"(?i)travel\s+distance\s+(?:is|of)\s+{_NUM}\s*m")
_TRAVEL_DIST_RE_B = re.compile(rf"(?i){_NUM}\s*m\s+travel\s+distance")
_TRAVEL_DIST_RE_C = re.compile(rf"(?i)maximum\s+travel\s+distance[^.;]{{0,60}}?{_NUM}\s*m")
_TRAVEL_DIST_PATTERNS = (_TRAVEL_DIST_RE_A, _TRAVEL_DIST_RE_B, _TRAVEL_DIST_RE_C)

# Corridor width (not in the demo doc — tested only). ------------------------- #
_CORRIDOR_WIDTH_RE_A = re.compile(rf"(?i)corridor\s+width\s+of\s+{_NUM}\s*m")
_CORRIDOR_WIDTH_RE_B = re.compile(rf"(?i)corridor[^.;]{{0,40}}?\bis\s+{_NUM}\s*m\s+wide")
_CORRIDOR_WIDTH_PATTERNS = (_CORRIDOR_WIDTH_RE_A, _CORRIDOR_WIDTH_RE_B)

# Exit door width -------------------------------------------------------------- #
# "An exit door in the corridor is 1200 mm wide, located in the north wall."
_EXIT_WIDTH_RE_A = re.compile(rf"(?i)exit\s+door[^.;]{{0,60}}?\bis\s+{_NUM}\s*mm\s+wide")
# "The exit door width is 1200 mm."
_EXIT_WIDTH_RE_B = re.compile(rf"(?i)exit\s+door\s+width\s+(?:is|of)\s+{_NUM}\s*mm")
# "A door with a clear width of 1200 mm serves as the final exit."
_EXIT_WIDTH_RE_C = re.compile(rf"(?i)clear\s+width\s+of\s+{_NUM}\s*mm")
_EXIT_WIDTH_PATTERNS = (_EXIT_WIDTH_RE_A, _EXIT_WIDTH_RE_B, _EXIT_WIDTH_RE_C)

_WALL_RE = re.compile(r"(?i)\b(north|south|east|west)\s+wall\b")

# Room-to-room adjacency (spec extension, layout §7) --------------------------- #
# Three phrasings, each with its primary form (used by the demo doc, Notes
# 11-13) plus 2 realistic variants exercised only in
# tests/test_spatial_extract.py. All three share the same capture shape:
# (name1, side, name2) = "name1 is <side> of name2" -> name1 sits flush on
# `side` of anchor `name2`. The trailing `[.,;]` bounds the lazy `_NAME`
# capture on name2 the same way the other _NAME-terminal patterns above do
# (e.g. `_FRONT_CLEARANCE_RE_A`) — without it, `_NAME`'s non-greedy `{1,45}?`
# would happily match a single character.
_SIDE = r"(north|south|east|west)"

# "The LV Switchroom sits immediately to the west of Data Hall 1, ..."
_ADJ_RE_1A = re.compile(rf"(?i){_NAME}\s+sits\s+immediately\s+to\s+the\s+{_SIDE}\s+of\s+{_NAME}[.,;]")
# "The Generator Yard lies to the south of Data Hall 1, ..."
_ADJ_RE_1B = re.compile(rf"(?i){_NAME}\s+lies\s+to\s+the\s+{_SIDE}\s+of\s+{_NAME}[.,;]")
# "The UPS Room is positioned to the east of Data Hall 1, ..."
_ADJ_RE_1C = re.compile(rf"(?i){_NAME}\s+is\s+positioned\s+to\s+the\s+{_SIDE}\s+of\s+{_NAME}[.,;]")

# "The Cooling Plant Room is located on the east side of Data Hall 1, ..."
_ADJ_RE_2A = re.compile(rf"(?i){_NAME}\s+is\s+located\s+on\s+the\s+{_SIDE}\s+side\s+of\s+{_NAME}[.,;]")
# "The Generator Yard stands on the south side of Data Hall 1, ..."
_ADJ_RE_2B = re.compile(rf"(?i){_NAME}\s+stands\s+on\s+the\s+{_SIDE}\s+side\s+of\s+{_NAME}[.,;]")
# "The UPS Room sits on the west side of Data Hall 1, ..."
_ADJ_RE_2C = re.compile(rf"(?i){_NAME}\s+sits\s+on\s+the\s+{_SIDE}\s+side\s+of\s+{_NAME}[.,;]")

# "The corridor runs along the north face of the LV Switchroom, ..."
_ADJ_RE_3A = re.compile(rf"(?i){_NAME}\s+runs\s+along\s+the\s+{_SIDE}\s+face\s+of\s+{_NAME}[.,;]")
# "The corridor extends along the east wall of the LV Switchroom, ..."
_ADJ_RE_3B = re.compile(rf"(?i){_NAME}\s+extends\s+along\s+the\s+{_SIDE}\s+wall\s+of\s+{_NAME}[.,;]")
# "The corridor is aligned along the south edge of the LV Switchroom, ..."
_ADJ_RE_3C = re.compile(rf"(?i){_NAME}\s+is\s+aligned\s+along\s+the\s+{_SIDE}\s+edge\s+of\s+{_NAME}[.,;]")

_ADJACENCY_PATTERNS = (
    _ADJ_RE_1A, _ADJ_RE_1B, _ADJ_RE_1C,
    _ADJ_RE_2A, _ADJ_RE_2B, _ADJ_RE_2C,
    _ADJ_RE_3A, _ADJ_RE_3B, _ADJ_RE_3C,
)


# --------------------------------------------------------------------------- #
# Main entry point.
# --------------------------------------------------------------------------- #
def extract_spatial(text: str, document_id: str) -> SpatialSpec:
    """Regex-first spatial extraction. Every hit is span-gated before it lands
    on the spec; every miss/rejection is an explicit Abstention — never a
    silent drop."""
    sentences = _sentences(text)
    doc_norm_low = _norm(text).lower()

    rooms: dict[str, Room] = {}
    room_order: list[str] = []
    equipment: dict[tuple[str, str], Equipment] = {}  # (room_id, kind) -> Equipment
    equip_order: list[tuple[str, str]] = []
    exits: list[ExitDoor] = []
    facts: list[SpatialFact] = []
    abstentions: list[Abstention] = []

    current_room_id: str | None = None
    exit_counter = 0

    def get_or_create_room(name: str) -> Room:
        rid = _slug(name)
        if rid not in rooms:
            rooms[rid] = Room(id=rid, name=name.strip(), zone=_zone_for(name))
            room_order.append(rid)
        return rooms[rid]

    def get_or_create_equipment(room_id: str, kind: str) -> Equipment:
        key = (room_id, kind)
        if key not in equipment:
            equipment[key] = Equipment(id=f"{room_id}__{kind}", room_id=room_id, kind=kind)
            equip_order.append(key)
        return equipment[key]

    def touch_corridor_context(sentence: str) -> None:
        nonlocal current_room_id
        if "corridor" in sentence.lower():
            room = get_or_create_room("Corridor")
            current_room_id = room.id

    for s in sentences:
        # --- room dimensions --------------------------------------------- #
        dim_match = None
        for pat in _ROOM_DIM_PATTERNS:
            dim_match = pat.search(s)
            if dim_match:
                break
        if dim_match:
            name = dim_match.group(1).strip()
            w_val, l_val = float(dim_match.group(2)), float(dim_match.group(3))
            room = get_or_create_room(name)
            current_room_id = room.id
            w_ext = _gate(w_val, "m", s, doc_norm_low)
            l_ext = _gate(l_val, "m", s, doc_norm_low)
            if w_ext is not None and l_ext is not None:
                room.width_m, room.length_m = w_ext, l_ext
            else:
                abstentions.append(
                    Abstention(
                        what=f"dimensions for {room.name}",
                        why="a dimension phrase matched but the value did not survive the "
                        "source-span verification gate — dropped rather than guessed.",
                    )
                )
            continue

        # --- room-to-room adjacency ---------------------------------------- #
        adj_match = next((pat.search(s) for pat in _ADJACENCY_PATTERNS if pat.search(s)), None)
        if adj_match:
            name1, side, name2 = adj_match.group(1), adj_match.group(2).lower(), adj_match.group(3)
            room1 = get_or_create_room(name1)
            anchor_room = get_or_create_room(name2)
            if room1.id != anchor_room.id and verify_text_span(s, doc_norm_low):
                room1.adjacent_to = Adjacency(
                    anchor_room_id=anchor_room.id, side=side, source_quote=_norm(s), verified=True
                )
            else:
                abstentions.append(
                    Abstention(
                        what=f"adjacency for {room1.name}",
                        why="matched adjacency phrasing but failed the span-verification gate "
                        "or referenced the room itself as its own anchor.",
                    )
                )
            continue

        # --- equipment clearances / passage height (need a room context) - #
        touch_corridor_context(s)

        front_match = next((pat.search(s) for pat in _FRONT_CLEARANCE_PATTERNS if pat.search(s)), None)
        if front_match and current_room_id:
            value = float(front_match.group(1))
            eq = get_or_create_equipment(current_room_id, _equip_kind_for(s))
            ext = _gate(value, "m", s, doc_norm_low)
            if ext is not None:
                eq.front_clearance_m = ext
            else:
                abstentions.append(
                    Abstention(what="front clearance", why="matched phrasing but failed the span-verification gate.")
                )
            continue

        rear_match = next((pat.search(s) for pat in _REAR_CLEARANCE_PATTERNS if pat.search(s)), None)
        if rear_match and current_room_id:
            value = float(rear_match.group(1))
            eq = get_or_create_equipment(current_room_id, _equip_kind_for(s))
            ext = _gate(value, "m", s, doc_norm_low)
            if ext is not None:
                eq.rear_clearance_m = ext
            else:
                abstentions.append(
                    Abstention(what="rear clearance", why="matched phrasing but failed the span-verification gate.")
                )
            # A rear-clearance sentence commonly also states the passage height
            # in the same clause (as it does in the demo doc) — check it here
            # too instead of `continue`-ing past it.
            passage_match = next((pat.search(s) for pat in _REAR_PASSAGE_PATTERNS if pat.search(s)), None)
            if passage_match:
                pvalue = float(passage_match.group(1))
                pext = _gate(pvalue, "m", s, doc_norm_low)
                if pext is not None:
                    eq.rear_passage_height_m = pext
                else:
                    abstentions.append(
                        Abstention(
                            what="rear passage height",
                            why="matched phrasing but failed the span-verification gate.",
                        )
                    )
            continue

        passage_match = next((pat.search(s) for pat in _REAR_PASSAGE_PATTERNS if pat.search(s)), None)
        if passage_match and current_room_id:
            value = float(passage_match.group(1))
            eq = get_or_create_equipment(current_room_id, _equip_kind_for(s))
            ext = _gate(value, "m", s, doc_norm_low)
            if ext is not None:
                eq.rear_passage_height_m = ext
            else:
                abstentions.append(
                    Abstention(what="rear passage height", why="matched phrasing but failed the span-verification gate.")
                )
            continue

        # --- egress facts (dead-end corridor / travel distance / corridor width) #
        dead_end_match = next((pat.search(s) for pat in _DEAD_END_PATTERNS if pat.search(s)), None)
        if dead_end_match:
            touch_corridor_context(s)
            value = float(dead_end_match.group(1))
            ext = _gate(value, "m", s, doc_norm_low)
            if ext is not None:
                facts.append(SpatialFact(kind="dead_end_corridor", room_id=current_room_id, value=ext))
            else:
                abstentions.append(
                    Abstention(what="dead-end corridor length", why="matched phrasing but failed the span-verification gate.")
                )
            continue

        travel_match = next((pat.search(s) for pat in _TRAVEL_DIST_PATTERNS if pat.search(s)), None)
        if travel_match:
            value = float(travel_match.group(1))
            ext = _gate(value, "m", s, doc_norm_low)
            if ext is not None:
                facts.append(SpatialFact(kind="travel_distance", room_id=current_room_id, value=ext))
            else:
                abstentions.append(
                    Abstention(what="travel distance", why="matched phrasing but failed the span-verification gate.")
                )
            continue

        corridor_width_match = next((pat.search(s) for pat in _CORRIDOR_WIDTH_PATTERNS if pat.search(s)), None)
        if corridor_width_match:
            touch_corridor_context(s)
            value = float(corridor_width_match.group(1))
            ext = _gate(value, "m", s, doc_norm_low)
            if ext is not None:
                facts.append(SpatialFact(kind="corridor_width", room_id=current_room_id, value=ext))
            else:
                abstentions.append(
                    Abstention(what="corridor width", why="matched phrasing but failed the span-verification gate.")
                )
            continue

        # --- exit doors ---------------------------------------------------- #
        exit_match = next((pat.search(s) for pat in _EXIT_WIDTH_PATTERNS if pat.search(s)), None)
        if exit_match and current_room_id:
            value = float(exit_match.group(1))
            ext = _gate(value, "mm", s, doc_norm_low)
            wall_match = _WALL_RE.search(s)
            wall = wall_match.group(1).lower() if wall_match else None
            if ext is not None:
                exit_counter += 1
                exits.append(
                    ExitDoor(id=f"exit_{exit_counter}", room_id=current_room_id, width_mm=ext, wall=wall)
                )
            else:
                abstentions.append(
                    Abstention(what="exit door width", why="matched phrasing but failed the span-verification gate.")
                )
            continue

    # Always-abstain: travel distance and exit occupant load are the two
    # egress inputs this regex layer never invents a number for when the
    # document is silent — surfaced explicitly rather than silently omitted.
    if not any(f.kind == "travel_distance" for f in facts):
        abstentions.append(
            Abstention(
                what="travel distance to the nearest exit",
                why="no sentence in the document states a measured travel distance — "
                "an EGRESS_TRAVEL_DISTANCE verdict would require guessing a number that "
                "was never written down, so this abstains instead.",
            )
        )
    if exits and not any(r.occupant_load is not None for r in rooms.values()):
        abstentions.append(
            Abstention(
                what="exit width adequacy",
                why="an exit door width was found, but no sentence states the room's "
                "occupant load, so the required exit width (occupant load x Table 4 "
                "mm/person) cannot be computed — abstaining rather than assuming a load.",
            )
        )

    return SpatialSpec(
        document_id=document_id,
        rooms=[rooms[rid] for rid in room_order],
        equipment=[equipment[k] for k in equip_order],
        exits=exits,
        facts=facts,
        abstentions=abstentions,
    )


# --------------------------------------------------------------------------- #
# Optional LLM enhancement — flag-gated, imported lazily so the flag-off path
# never touches an llm module at all (see config.SPATIAL_LLM_EXTRACTION_ENABLED).
# --------------------------------------------------------------------------- #
def llm_enabled() -> bool:
    return config.SPATIAL_LLM_EXTRACTION_ENABLED


def extract_spatial_enhanced(text: str, document_id: str) -> SpatialSpec:
    """Regex spec is the floor; when the flag is on, an LLM pass could widen
    coverage the same way `llm_extract.py` does for the scalar path. Not
    implemented in this slice (out of scope per spec §5.2) — this stub exists
    only so the import boundary is explicit and the flag-off test has
    something concrete to assert against."""
    if not llm_enabled():
        return extract_spatial(text, document_id)
    # Lazy import kept inside the flag-on branch on purpose: the flag-off path
    # above never executes this line, so no llm module is ever imported.
    from .. import llm_extract as _llm_extract  # noqa: F401  (perception-only; no verdicts)

    return extract_spatial(text, document_id)
