"""Flatten a `SpatialSpec` into the same flat param-dict shape `checks.py`
already consumes (spec §5.4), so `checks_spatial.py` (owned separately) can be
structurally identical to `checks.py` — same `applies_when(p)`/`rule(p)`
signature over a plain dict, no new evaluation machinery.

Every dict here comes from a value that already survived `extract.py`'s span
gate, so `provenance` is always `"stated"` — an inferred nominal room (no
stated dimensions) never has a real `Extracted` value to flatten, so it never
emits a param at all (see `layout.py`'s docstring). `checks_spatial.py`'s
"abstain when provenance != stated" branch is future-proofing for whenever
this module (or the optional LLM path) starts emitting a lower-confidence
provenance; today's regex-only extraction never does.
"""
from __future__ import annotations

from .schemas import Extracted, Room, SpatialSpec


def _room_context(room: Room | None) -> tuple[str | None, str | None, str | None]:
    if room is None:
        return None, None, None
    return room.id, room.zone, room.occupancy_group


def to_params(spec: SpatialSpec) -> list[dict]:
    """Every extracted spatial value, flattened to one dict per checkable
    param. Values that failed the span gate (and so never became an
    `Extracted`) are absent here entirely — they only ever appear in
    `spec.abstentions`."""
    rooms_by_id = {r.id: r for r in spec.rooms}
    out: list[dict] = []

    def emit(
        param: str,
        extracted: Extracted | None,
        room_id: str | None,
        equipment_kind: str | None = None,
    ) -> None:
        if extracted is None or not extracted.verified:
            return
        room = rooms_by_id.get(room_id) if room_id else None
        rid, room_zone, occupancy_group = _room_context(room)
        occupant_load = room.occupant_load if room and room.occupant_load and room.occupant_load.verified else None
        out.append(
            {
                "param": param,
                "value": extracted.value,
                "unit": extracted.unit,
                "source_quote": extracted.source_quote,
                "provenance": "stated",
                "room_id": rid,
                "room_zone": room_zone,
                "equipment_kind": equipment_kind,
                "occupancy_group": occupancy_group,
                # Convenience extras (beyond the spec's "at minimum" set) so a
                # rule that needs occupant load alongside exit_width doesn't
                # have to re-look-up the room itself.
                "occupant_load": occupant_load.value if occupant_load else None,
                "occupant_load_provenance": "stated" if occupant_load else None,
            }
        )

    for eq in spec.equipment:
        emit("front_clearance", eq.front_clearance_m, eq.room_id, eq.kind)
        emit("rear_clearance", eq.rear_clearance_m, eq.room_id, eq.kind)
        emit("rear_passage_height", eq.rear_passage_height_m, eq.room_id, eq.kind)

    for fact in spec.facts:
        emit(fact.kind, fact.value, fact.room_id)

    for ex in spec.exits:
        emit("exit_width", ex.width_mm, ex.room_id)

    for room in spec.rooms:
        emit("occupant_load", room.occupant_load, room.id)

    return out
