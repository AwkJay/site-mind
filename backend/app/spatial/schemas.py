"""Data contracts for the spatial-compliance path (spec §5.1). Mirrors the
style of `app/schemas.py` — plain pydantic models, no extra behaviour. Do not
add fields beyond the spec; `checks_spatial.py` and the floor-plan endpoint
(owned separately) are written against exactly this shape.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

Provenance = Literal["stated", "inferred"]


class Extracted(BaseModel):
    value: float
    unit: str                 # "m" | "mm"
    source_quote: str         # verbatim sentence from the document
    verified: bool            # span gate result; False values are dropped before checks


class Adjacency(BaseModel):
    """A STATED room-to-room spatial relation (spec extension, layout §7): the
    owning `Room` sits on `side` of `anchor_room_id`, e.g. anchor="data_hall_1",
    side="east" means "this room is to the east of Data Hall 1". Same
    span-gate discipline as `Extracted` — `verified` is only True when
    `source_quote` is a literal (whitespace-normalised) substring of the
    document. An unverified Adjacency is dropped by the extractor and recorded
    as an Abstention, exactly like a dropped `Extracted` value."""

    anchor_room_id: str
    side: Literal["north", "south", "east", "west"]
    source_quote: str
    verified: bool


class WallPlacement(BaseModel):
    """Which wall of its room a piece of equipment stands against — same
    span-gate discipline as `Adjacency` (verbatim-substring only; there is no
    numeric value to additionally check, so the gate is check (a) alone)."""

    wall: Literal["north", "south", "east", "west"]
    source_quote: str
    verified: bool


class NorthOrientation(BaseModel):
    """A stated true/plan-north orientation statement for the drawing. Text
    claim, not a numeric one — span-gated on verbatim-substring only."""

    source_quote: str
    verified: bool


class Room(BaseModel):
    id: str                   # slug, e.g. "data_hall_1"
    name: str
    zone: Literal["server_hall", "electrical", "cooling", "corridor", "other"]
    width_m: Extracted | None = None
    length_m: Extracted | None = None
    occupancy_group: str | None = None      # NBC group, e.g. "industrial"
    occupant_load: Extracted | None = None
    adjacent_to: Adjacency | None = None    # stated relation to another room; None -> position stays inferred


class Equipment(BaseModel):
    id: str
    room_id: str
    kind: Literal["switchboard", "lv_panel", "transformer", "genset", "crac", "rack_row"]
    count: int | None = None
    front_clearance_m: Extracted | None = None
    rear_clearance_m: Extracted | None = None
    rear_passage_height_m: Extracted | None = None
    row_length_m: Extracted | None = None          # rack_row: stated run length of each row
    footprint_length_m: Extracted | None = None    # stated footprint length (along the wall it stands against)
    footprint_depth_m: Extracted | None = None      # stated footprint depth (out from that wall)
    wall_placement: WallPlacement | None = None     # which wall of room_id this equipment stands against


class ExitDoor(BaseModel):
    id: str
    room_id: str
    width_mm: Extracted | None = None
    wall: Literal["north", "south", "east", "west"] | None = None


class SpatialFact(BaseModel):
    kind: Literal["travel_distance", "dead_end_corridor", "corridor_width"]
    room_id: str | None
    value: Extracted


class Abstention(BaseModel):
    what: str                 # "travel distance for Data Hall 1"
    why: str                  # plain-language reason, shown in the UI


class SpatialSpec(BaseModel):
    document_id: str
    rooms: list[Room]
    equipment: list[Equipment]
    exits: list[ExitDoor]
    facts: list[SpatialFact]
    abstentions: list[Abstention]
    north_orientation: NorthOrientation | None = None
