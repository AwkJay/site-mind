"""Deterministic shelf-packing layout (spec §5.3) — turns a `SpatialSpec` into
2D floor-plan geometry. No randomness anywhere: `place()` called twice on the
same spec must produce byte-identical output, which is exactly what the demo
UI (and `tests/test_spatial_layout.py`) require to be trustworthy.

Algorithm: sort rooms by (area desc, id asc) — a total order, so no two rooms
ever tie without a deterministic tiebreaker — then pack them left-to-right
into rows bounded by the widest room's width, with a fixed 2 m gap between
rooms and between rows.

Rooms with no stated dimensions never get a real geometry: they are given a
nominal 6x6 m placeholder box, `dimension_source="inferred"`, and are excluded
from every check (checks read `params.py`'s flat dicts, which only ever come
from a stated `Extracted` value — an inferred nominal box never emits a
param).

Positions are `"inferred"` by shelf packing UNLESS `extract.py` recorded a
verified `Room.adjacent_to` (a stated "X is <side> of Y" relation) — see
`_resolve_adjacency()` below. A room with a resolved adjacency is placed
FLUSH (zero gap, shared edge) against its anchor and marked
`position_source="stated"`; every other room keeps the original deterministic
shelf-packing behaviour and stays `"inferred"`. The two populations are
placed in two passes: shelf-packing runs first, on exactly the rooms with no
resolvable adjacency (this is the deterministic "anchor root" set — every
adjacency chain ultimately terminates at one of these rooms, since a cycle or
an unresolvable anchor is stripped out before packing even starts); flush
placement then walks the remaining rooms outward from their anchors.
"""
from __future__ import annotations

from pydantic import BaseModel

from .schemas import Provenance, Room, SpatialSpec

GAP_M = 2.0
NOMINAL_SIDE_M = 6.0


class PlacedRoom(BaseModel):
    id: str
    name: str
    zone: str
    x_m: float
    y_m: float
    width_m: float
    length_m: float
    dimension_source: Provenance
    position_source: Provenance


class PlacedEquipment(BaseModel):
    id: str
    room_id: str
    kind: str
    x_m: float
    y_m: float
    front_clearance_m: float | None = None
    rear_clearance_m: float | None = None
    rear_passage_height_m: float | None = None
    position_source: Provenance = "inferred"


class PlacedExit(BaseModel):
    id: str
    room_id: str
    wall: str | None
    x_m: float
    y_m: float
    width_mm: float | None
    position_source: Provenance


class TravelPath(BaseModel):
    room_id: str | None
    distance_m: float
    source_quote: str


class Rect(BaseModel):
    x_m: float
    y_m: float
    width_m: float
    length_m: float


class ClearanceZone(BaseModel):
    """One entry per equipment clearance a spatial check evaluated (spec
    extension, endpoint §3) — lets the UI draw the provided clearance band
    against the required envelope, so a fail like NCR-1 (0.8 m provided vs
    1.0 m required) is visible as geometry, not just a citation. Populated by
    `agents/floor_plan.py`, not by `place()` itself, since it needs the check
    verdicts (`checks_spatial.py`) that only exist after `place()` returns —
    see that module for how `required_rect` is derived and why it is `None`
    whenever asserting one would mean fabricating a value the document never
    states (an abstained check, or a rule with no single-number threshold)."""

    equipment_id: str
    kind: str  # "front" | "rear"
    provided_m: float
    required_m: float | None
    status: str  # "pass" | "fail" | "abstain"
    clause_key: str
    provided_rect: Rect | None = None
    required_rect: Rect | None = None


class FloorPlan(BaseModel):
    rooms: list[PlacedRoom]
    equipment: list[PlacedEquipment]
    exits: list[PlacedExit]
    travel_paths: list[TravelPath]     # only for STATED travel distances
    extent_m: tuple[float, float]
    notes: list[str]                   # e.g. "Positions are inferred; see legend."
    clearance_zones: list[ClearanceZone] = []


def _room_dims(room) -> tuple[float, float, Provenance]:
    """(width, length, dimension_source) for one Room. Falls back to the
    nominal 6x6 m inferred box only when EITHER dimension is missing or was
    dropped by the extraction span gate (never a stated-but-unverified box)."""
    w = room.width_m
    l = room.length_m
    if w is not None and l is not None and w.verified and l.verified:
        return w.value, l.value, "stated"
    return NOMINAL_SIDE_M, NOMINAL_SIDE_M, "inferred"


_SIDE_DELTA: dict[str, str] = {"north": "south", "south": "north", "east": "west", "west": "east"}


def _resolve_adjacency(rooms: list[Room]) -> tuple[dict[str, "object"], list[str]]:
    """Validates every room's stated `Room.adjacent_to` and returns the subset
    safe to place flush against its anchor (`{room_id: Adjacency}`), plus
    human-readable notes explaining anything dropped. Never raises, never
    picks an arbitrary winner among conflicting claims — deterministic
    tie-breaks only:

      - self-reference (a room adjacent to itself) -> dropped.
      - an anchor not among this document's rooms -> dropped.
      - a cycle (A -> B -> ... -> A) -> every room on the cycle is dropped
        (no single room is picked to "break" it).
      - a conflict — two rooms both claim the same (anchor, side) slot -> the
        lexicographically-smallest room id wins (deterministic first-by-id,
        never arbitrary); the rest fall back to shelf packing.

    A dropped room simply has no entry in the returned map, so `place()`
    treats it exactly like a room with no stated adjacency at all: shelf
    packed, `position_source="inferred"`.
    """
    room_ids = {r.id for r in rooms}
    candidates: dict[str, object] = {}
    notes: list[str] = []

    for room in sorted(rooms, key=lambda r: r.id):
        adj = room.adjacent_to
        if adj is None or not adj.verified:
            continue
        if adj.anchor_room_id == room.id:
            notes.append(f"'{room.name}' states an adjacency to itself — ignored.")
            continue
        if adj.anchor_room_id not in room_ids:
            notes.append(
                f"'{room.name}' states an adjacency to a room not otherwise described in this "
                "document — ignored."
            )
            continue
        candidates[room.id] = adj

    # Cycle detection: walk each candidate's anchor chain; a room revisited
    # before the chain reaches a non-candidate (an acyclic root) means every
    # room on that chain has no safe measurement origin.
    cyclic: set[str] = set()
    for start in sorted(candidates):
        seen: list[str] = []
        current = start
        while current in candidates:
            if current in seen:
                cyclic.update(seen[seen.index(current):])
                break
            seen.append(current)
            current = candidates[current].anchor_room_id
    if cyclic:
        notes.append(
            "a cyclic adjacency chain was found among rooms: " + ", ".join(sorted(cyclic)) + " — "
            "every room in the cycle keeps its deterministic shelf-packed (inferred) position "
            "instead of an arbitrarily chosen one."
        )
    for room_id in cyclic:
        candidates.pop(room_id, None)

    # Conflict detection: at most one room may occupy a given (anchor, side)
    # slot. Iterate in room-id order so the winner is always the same room.
    claimed: dict[tuple[str, str], str] = {}
    resolved: dict[str, object] = {}
    for room_id in sorted(candidates):
        adj = candidates[room_id]
        slot = (adj.anchor_room_id, adj.side)
        holder = claimed.get(slot)
        if holder is not None:
            notes.append(
                f"'{room_id}' and '{holder}' both claim the {adj.side} side of "
                f"'{adj.anchor_room_id}' — only '{holder}' (first by room id) is placed flush "
                f"there; '{room_id}' keeps its deterministic shelf-packed (inferred) position."
            )
            continue
        claimed[slot] = room_id
        resolved[room_id] = adj

    return resolved, notes


def _shelf_pack(rooms: list[Room]) -> tuple[list[PlacedRoom], dict[str, tuple[float, float, float, float]]]:
    """The original deterministic shelf-packing algorithm (spec §5.3),
    unchanged, run over exactly the rooms passed in. `place()` below calls
    this ONLY on rooms with no resolvable stated adjacency — the "anchor
    root" set that every flush-placed room ultimately measures from."""
    entries = []
    for room in rooms:
        w, l, dsrc = _room_dims(room)
        entries.append((room, w, l, dsrc))

    # Total order: area desc, then id asc — no tie is ever broken by
    # incidental list/dict ordering.
    entries.sort(key=lambda e: (-(e[1] * e[2]), e[0].id))

    max_row_width = max((w for _, w, _, _ in entries), default=0.0)

    placed_rooms: list[PlacedRoom] = []
    room_geom: dict[str, tuple[float, float, float, float]] = {}  # id -> x, y, w, l

    x = 0.0
    y = 0.0
    row_used_width = 0.0
    row_height = 0.0

    for room, w, l, dsrc in entries:
        if row_used_width > 0.0 and row_used_width + GAP_M + w > max_row_width + 1e-9:
            # start a new row
            y += row_height + GAP_M
            row_used_width = 0.0
            row_height = 0.0

        x = row_used_width + GAP_M if row_used_width > 0.0 else 0.0
        placed_rooms.append(
            PlacedRoom(
                id=room.id,
                name=room.name,
                zone=room.zone,
                x_m=x,
                y_m=y,
                width_m=w,
                length_m=l,
                dimension_source=dsrc,
                position_source="inferred",
            )
        )
        room_geom[room.id] = (x, y, w, l)
        row_used_width = x + w
        row_height = max(row_height, l)

    return placed_rooms, room_geom


def _place_flush(
    adj_map: dict[str, object],
    rooms_by_id: dict[str, Room],
    room_geom: dict[str, tuple[float, float, float, float]],
) -> tuple[list[PlacedRoom], list[str]]:
    """Second pass: place every room with a resolved adjacency flush (zero
    gap, shared edge) against its anchor, in a deterministic fixed-point
    order so a chain (e.g. corridor -> lv_switchroom -> data_hall_1) resolves
    once its anchor has a geometry, however many links deep. `_resolve_adjacency`
    already stripped cycles and unknown anchors, so every entry here is
    guaranteed to terminate at a room already in `room_geom` — the loop below
    is bounded by `len(adj_map)` rounds and the safety-net branch at the end
    is defensive, not expected to ever fire."""
    pending = dict(adj_map)
    placed: list[PlacedRoom] = []
    notes: list[str] = []

    progress = True
    while pending and progress:
        progress = False
        for room_id in sorted(pending):
            adj = pending[room_id]
            anchor_geom = room_geom.get(adj.anchor_room_id)
            if anchor_geom is None:
                continue  # anchor not resolved yet this round — try again next round
            room = rooms_by_id[room_id]
            w, l, dsrc = _room_dims(room)
            ax, ay, aw, al = anchor_geom
            if adj.side == "west":
                x, y = ax - w, ay
            elif adj.side == "east":
                x, y = ax + aw, ay
            elif adj.side == "north":
                x, y = ax, ay - l
            else:  # "south"
                x, y = ax, ay + al
            placed.append(
                PlacedRoom(
                    id=room.id, name=room.name, zone=room.zone, x_m=x, y_m=y,
                    width_m=w, length_m=l, dimension_source=dsrc, position_source="stated",
                )
            )
            room_geom[room.id] = (x, y, w, l)
            del pending[room_id]
            progress = True

    if pending:
        # Defensive fallback only — should be unreachable given the
        # validation in `_resolve_adjacency`. Never crash, never guess a
        # placement that looks stated: mark it plainly inferred instead.
        fallback_y = max((g[1] + g[3] for g in room_geom.values()), default=0.0) + GAP_M
        fallback_x = 0.0
        for room_id in sorted(pending):
            room = rooms_by_id[room_id]
            w, l, dsrc = _room_dims(room)
            placed.append(
                PlacedRoom(
                    id=room.id, name=room.name, zone=room.zone, x_m=fallback_x, y_m=fallback_y,
                    width_m=w, length_m=l, dimension_source=dsrc, position_source="inferred",
                )
            )
            room_geom[room.id] = (fallback_x, fallback_y, w, l)
            fallback_x += w + GAP_M
        notes.append(
            "a stated adjacency could not be resolved to a placed anchor and fell back to a "
            "deterministic inferred position rather than being guessed."
        )

    return placed, notes


def place(spec: SpatialSpec) -> FloorPlan:
    """Deterministic layout. Same `spec` in -> byte-identical `FloorPlan` out,
    every time, no exceptions. Two passes: rooms with no resolvable stated
    adjacency are shelf-packed exactly as before; rooms with one are then
    placed flush against their (already-placed) anchor."""
    adj_map, adjacency_notes = _resolve_adjacency(spec.rooms)
    rooms_by_id = {r.id: r for r in spec.rooms}

    root_rooms = [r for r in spec.rooms if r.id not in adj_map]
    placed_root, room_geom = _shelf_pack(root_rooms)
    placed_dependent, fallback_notes = _place_flush(adj_map, rooms_by_id, room_geom)
    adjacency_notes += fallback_notes

    placed_rooms = placed_root + placed_dependent

    # Normalize: a flush placement can extend north/west of its anchor into
    # negative coordinates (e.g. the corridor sits north of the LV
    # Switchroom). Shift the whole plan — rooms, and (via `room_geom`, which
    # equipment/exits below are placed relative to) everything else — so the
    # plan's bounding box starts at (0, 0), exactly like the original
    # shelf-packing-only output always did.
    if placed_rooms:
        min_x = min(r.x_m for r in placed_rooms)
        min_y = min(r.y_m for r in placed_rooms)
    else:
        min_x = min_y = 0.0
    if min_x != 0.0 or min_y != 0.0:
        for r in placed_rooms:
            r.x_m -= min_x
            r.y_m -= min_y
        room_geom = {rid: (x - min_x, y - min_y, w, l) for rid, (x, y, w, l) in room_geom.items()}

    overall_max_x = max((r.x_m + r.width_m for r in placed_rooms), default=0.0)
    overall_max_y = max((r.y_m + r.length_m for r in placed_rooms), default=0.0)
    extent_m = (overall_max_x, overall_max_y)

    # Equipment glyphs: placed at a fixed, deterministic offset inside the
    # parent room (front-centre of the room footprint) — always "inferred"
    # (spec §5.3: only a stated wall on an ExitDoor can ever earn "stated").
    placed_equipment: list[PlacedEquipment] = []
    for eq in spec.equipment:
        geom = room_geom.get(eq.room_id)
        if geom is None:
            continue
        rx, ry, rw, rl = geom
        placed_equipment.append(
            PlacedEquipment(
                id=eq.id,
                room_id=eq.room_id,
                kind=eq.kind,
                x_m=rx + rw / 2.0,
                y_m=ry + rl * 0.1,
                front_clearance_m=eq.front_clearance_m.value if eq.front_clearance_m else None,
                rear_clearance_m=eq.rear_clearance_m.value if eq.rear_clearance_m else None,
                rear_passage_height_m=eq.rear_passage_height_m.value if eq.rear_passage_height_m else None,
                position_source="inferred",
            )
        )

    # Exit glyphs: placed at the midpoint of the stated wall (or the room's
    # south edge as a deterministic default when no wall was stated).
    _WALL_OFFSET = {
        "north": (0.5, 0.0),
        "south": (0.5, 1.0),
        "east": (1.0, 0.5),
        "west": (0.0, 0.5),
    }
    placed_exits: list[PlacedExit] = []
    for ex in spec.exits:
        geom = room_geom.get(ex.room_id)
        if geom is None:
            continue
        rx, ry, rw, rl = geom
        fx, fy = _WALL_OFFSET.get(ex.wall or "south", (0.5, 1.0))
        placed_exits.append(
            PlacedExit(
                id=ex.id,
                room_id=ex.room_id,
                wall=ex.wall,
                x_m=rx + rw * fx,
                y_m=ry + rl * fy,
                width_mm=ex.width_mm.value if ex.width_mm else None,
                # A wall was explicitly stated in the document -> the position
                # along that wall is grounded in text, not shelf-packing guesswork.
                position_source="stated" if ex.wall else "inferred",
            )
        )

    # Travel paths: only ever drawn for a STATED travel-distance fact (never
    # for an inferred/nominal room) — spec §5.3.
    travel_paths: list[TravelPath] = []
    for fact in spec.facts:
        if fact.kind != "travel_distance":
            continue
        if fact.room_id is not None and fact.room_id not in room_geom:
            continue
        if not fact.value.verified:
            continue
        travel_paths.append(
            TravelPath(room_id=fact.room_id, distance_m=fact.value.value, source_quote=fact.value.source_quote)
        )

    notes: list[str] = []
    if any(r.dimension_source == "inferred" for r in placed_rooms):
        notes.append(
            "Some rooms have no stated dimensions in the source document and are drawn as a "
            "nominal 6 m x 6 m placeholder (hatched) — never used in a compliance check."
        )
    stated_positions = [r for r in placed_rooms if r.position_source == "stated"]
    if stated_positions:
        stated_names = ", ".join(sorted(r.name for r in stated_positions))
        notes.append(
            f"Positions are stated (solid, flush against a named anchor room) for: {stated_names} "
            "— the source document gives an explicit room-to-room adjacency for these. Every "
            "other room's position is inferred by deterministic shelf packing and is drawn "
            "hatched; see the legend."
        )
    else:
        notes.append(
            "All room positions are inferred by deterministic shelf packing; no document in "
            "this slice states an explicit room-to-room spatial relation."
        )
    notes.extend(adjacency_notes)

    return FloorPlan(
        rooms=placed_rooms,
        equipment=placed_equipment,
        exits=placed_exits,
        travel_paths=travel_paths,
        extent_m=extent_m,
        notes=notes,
    )
