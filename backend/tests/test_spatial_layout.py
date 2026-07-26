"""Tests for app.spatial.layout (spec §8 — layout bullets only): determinism,
no room overlap, and inferred-dimension marking."""
from __future__ import annotations

import pytest

from app.spatial import extract, layout
from app.spatial.schemas import Adjacency, Equipment, Extracted, Room, SpatialSpec

DEMO_PATH = "data/project_docs/live_upload_samples/DC1-05-DBR-0007-R1_Layout-Design-Basis.md"


def _demo_spec() -> SpatialSpec:
    from app import config

    text = (config.BACKEND_DIR / DEMO_PATH).read_text(encoding="utf-8")
    return extract.extract_spatial(text, "demo-doc")


def _synthetic_spec() -> SpatialSpec:
    """A hand-built spec with a mix of stated and inferred rooms, several equal
    areas, and equipment/exits — enough surface area to stress the packer."""
    def ext(v, unit="m"):
        return Extracted(value=v, unit=unit, source_quote=f"stub {v} {unit}", verified=True)

    rooms = [
        Room(id="room_a", name="Room A", zone="server_hall", width_m=ext(10), length_m=ext(10)),
        Room(id="room_b", name="Room B", zone="electrical", width_m=ext(8), length_m=ext(5)),
        Room(id="room_c", name="Room C", zone="cooling", width_m=ext(8), length_m=ext(5)),  # same area as B
        Room(id="room_d", name="Room D", zone="corridor"),  # no stated dims -> nominal 6x6 inferred
        Room(id="room_e", name="Room E", zone="other", width_m=ext(20), length_m=ext(1)),
    ]
    equipment = [
        Equipment(id="eq_1", room_id="room_b", kind="lv_panel", front_clearance_m=ext(0.8), rear_clearance_m=ext(0.9)),
    ]
    return SpatialSpec(
        document_id="synthetic",
        rooms=rooms,
        equipment=equipment,
        exits=[],
        facts=[],
        abstentions=[],
    )


# --------------------------------------------------------------------------- #
# Determinism.
# --------------------------------------------------------------------------- #
def test_place_is_deterministic_on_demo_doc():
    spec = _demo_spec()
    plan_a = layout.place(spec)
    plan_b = layout.place(spec)
    assert plan_a.model_dump_json() == plan_b.model_dump_json()


def test_place_is_deterministic_on_synthetic_spec():
    spec = _synthetic_spec()
    plan_a = layout.place(spec)
    plan_b = layout.place(spec)
    assert plan_a.model_dump_json() == plan_b.model_dump_json()


def test_place_is_deterministic_across_reparsed_spec_instances():
    """Two independently-built SpatialSpec objects with identical content (not
    the same Python object) must still produce byte-identical geometry."""
    spec_1 = _synthetic_spec()
    spec_2 = _synthetic_spec()
    plan_1 = layout.place(spec_1)
    plan_2 = layout.place(spec_2)
    assert plan_1.model_dump_json() == plan_2.model_dump_json()


def test_room_order_input_does_not_affect_output():
    """Sort keys must be total (area desc, id asc) — feeding rooms in a
    different input order must not change the resulting geometry."""
    spec = _synthetic_spec()
    reversed_spec = spec.model_copy(update={"rooms": list(reversed(spec.rooms))})
    plan_forward = layout.place(spec)
    plan_reversed = layout.place(reversed_spec)
    assert plan_forward.model_dump_json() == plan_reversed.model_dump_json()


# --------------------------------------------------------------------------- #
# No overlap.
# --------------------------------------------------------------------------- #
def _overlaps(a, b) -> bool:
    ax0, ay0, ax1, ay1 = a.x_m, a.y_m, a.x_m + a.width_m, a.y_m + a.length_m
    bx0, by0, bx1, by1 = b.x_m, b.y_m, b.x_m + b.width_m, b.y_m + b.length_m
    return ax0 < bx1 and bx0 < ax1 and ay0 < by1 and by0 < ay1


def test_no_room_overlap_demo_doc():
    plan = layout.place(_demo_spec())
    rooms = plan.rooms
    for i in range(len(rooms)):
        for j in range(i + 1, len(rooms)):
            assert not _overlaps(rooms[i], rooms[j]), (rooms[i], rooms[j])


def test_no_room_overlap_synthetic_spec():
    plan = layout.place(_synthetic_spec())
    rooms = plan.rooms
    for i in range(len(rooms)):
        for j in range(i + 1, len(rooms)):
            assert not _overlaps(rooms[i], rooms[j]), (rooms[i], rooms[j])


# --------------------------------------------------------------------------- #
# Inferred marking.
# --------------------------------------------------------------------------- #
def test_room_with_no_stated_dimensions_gets_nominal_6x6_inferred_box():
    plan = layout.place(_synthetic_spec())
    room_d = next(r for r in plan.rooms if r.id == "room_d")
    assert room_d.dimension_source == "inferred"
    assert room_d.width_m == 6.0
    assert room_d.length_m == 6.0


def test_room_with_stated_dimensions_is_marked_stated():
    plan = layout.place(_synthetic_spec())
    room_a = next(r for r in plan.rooms if r.id == "room_a")
    assert room_a.dimension_source == "stated"
    assert room_a.width_m == 10.0
    assert room_a.length_m == 10.0


def test_all_room_positions_are_inferred_in_this_slice():
    plan = layout.place(_synthetic_spec())
    assert all(r.position_source == "inferred" for r in plan.rooms)


def test_extent_covers_every_placed_room():
    plan = layout.place(_synthetic_spec())
    max_x, max_y = plan.extent_m
    for r in plan.rooms:
        assert r.x_m + r.width_m <= max_x + 1e-6
        assert r.y_m + r.length_m <= max_y + 1e-6


# --------------------------------------------------------------------------- #
# Stated adjacency -> flush placement (mixed stated+inferred case).
# --------------------------------------------------------------------------- #
def _adjacency_spec() -> SpatialSpec:
    def ext(v, unit="m"):
        return Extracted(value=v, unit=unit, source_quote=f"stub {v} {unit}", verified=True)


    rooms = [
        Room(id="data_hall_1", name="Data Hall 1", zone="server_hall", width_m=ext(30), length_m=ext(20)),
        Room(
            id="lv_switchroom", name="LV Switchroom", zone="electrical", width_m=ext(12), length_m=ext(8),
            adjacent_to=Adjacency(anchor_room_id="data_hall_1", side="west", source_quote="stub", verified=True),
        ),
        Room(
            id="cooling_plant_room", name="Cooling Plant Room", zone="cooling", width_m=ext(14), length_m=ext(10),
            adjacent_to=Adjacency(anchor_room_id="data_hall_1", side="east", source_quote="stub", verified=True),
        ),
        Room(
            id="corridor", name="Corridor", zone="corridor",  # no stated dims -> nominal 6x6
            adjacent_to=Adjacency(anchor_room_id="lv_switchroom", side="north", source_quote="stub", verified=True),
        ),
        # An unrelated inferred room with no stated adjacency at all.
        Room(id="genset_yard", name="Genset Yard", zone="other", width_m=ext(9), length_m=ext(9)),
    ]
    return SpatialSpec(document_id="adjacency-mix", rooms=rooms, equipment=[], exits=[], facts=[], abstentions=[])


def test_demo_doc_stated_adjacency_rooms_are_flush_and_non_overlapping():
    """End-to-end: the demo doc's 3 adjacency notes (11-13) must produce a
    flush, non-overlapping layout with data_hall_1 as the (inferred) anchor
    root and the other three rooms `position_source == "stated"`."""
    plan = layout.place(_demo_spec())
    by_id = {r.id: r for r in plan.rooms}
    assert by_id["data_hall_1"].position_source == "inferred"
    assert by_id["lv_switchroom"].position_source == "stated"
    assert by_id["cooling_plant_room"].position_source == "stated"
    assert by_id["corridor"].position_source == "stated"

    rooms = plan.rooms
    for i in range(len(rooms)):
        for j in range(i + 1, len(rooms)):
            assert not _overlaps(rooms[i], rooms[j]), (rooms[i], rooms[j])


def test_stated_adjacency_rooms_are_placed_flush():
    plan = layout.place(_adjacency_spec())
    by_id = {r.id: r for r in plan.rooms}
    dh1, lv, cool, corridor = by_id["data_hall_1"], by_id["lv_switchroom"], by_id["cooling_plant_room"], by_id["corridor"]

    assert lv.position_source == "stated"
    assert cool.position_source == "stated"
    assert corridor.position_source == "stated"
    assert dh1.position_source == "inferred"  # the anchor root; no relation stated for it

    # LV Switchroom flush on the west (shared vertical edge, zero gap, same y).
    assert lv.x_m + lv.width_m == pytest.approx(dh1.x_m)
    assert lv.y_m == pytest.approx(dh1.y_m)

    # Cooling Plant Room flush on the east.
    assert cool.x_m == pytest.approx(dh1.x_m + dh1.width_m)
    assert cool.y_m == pytest.approx(dh1.y_m)

    # Corridor flush on the north face of the LV Switchroom.
    assert corridor.y_m + corridor.length_m == pytest.approx(lv.y_m)
    assert corridor.x_m == pytest.approx(lv.x_m)


def test_stated_adjacency_mixed_with_inferred_no_overlap():
    plan = layout.place(_adjacency_spec())
    rooms = plan.rooms
    for i in range(len(rooms)):
        for j in range(i + 1, len(rooms)):
            assert not _overlaps(rooms[i], rooms[j]), (rooms[i], rooms[j])


def test_stated_adjacency_layout_is_deterministic():
    plan_a = layout.place(_adjacency_spec())
    plan_b = layout.place(_adjacency_spec())
    assert plan_a.model_dump_json() == plan_b.model_dump_json()


def test_stated_adjacency_extent_covers_negative_shifted_rooms():
    plan = layout.place(_adjacency_spec())
    max_x, max_y = plan.extent_m
    for r in plan.rooms:
        assert r.x_m >= -1e-6
        assert r.y_m >= -1e-6
        assert r.x_m + r.width_m <= max_x + 1e-6
        assert r.y_m + r.length_m <= max_y + 1e-6


def test_cyclic_adjacency_falls_back_to_inferred_never_crashes():

    rooms = [
        Room(
            id="room_a", name="Room A", zone="other", width_m=Extracted(value=5, unit="m", source_quote="s", verified=True),
            length_m=Extracted(value=5, unit="m", source_quote="s", verified=True),
            adjacent_to=Adjacency(anchor_room_id="room_b", side="east", source_quote="s", verified=True),
        ),
        Room(
            id="room_b", name="Room B", zone="other", width_m=Extracted(value=5, unit="m", source_quote="s", verified=True),
            length_m=Extracted(value=5, unit="m", source_quote="s", verified=True),
            adjacent_to=Adjacency(anchor_room_id="room_a", side="west", source_quote="s", verified=True),
        ),
    ]
    spec = SpatialSpec(document_id="cyclic", rooms=rooms, equipment=[], exits=[], facts=[], abstentions=[])
    plan = layout.place(spec)  # must not raise
    assert {r.position_source for r in plan.rooms} == {"inferred"}
    assert any("cyclic" in n.lower() for n in plan.notes)


def test_conflicting_adjacency_claims_first_by_id_wins_deterministically():

    def dims():
        return dict(
            width_m=Extracted(value=5, unit="m", source_quote="s", verified=True),
            length_m=Extracted(value=5, unit="m", source_quote="s", verified=True),
        )

    rooms = [
        Room(id="anchor_room", name="Anchor Room", zone="other", **dims()),
        Room(
            id="claimant_a", name="Claimant A", zone="other", **dims(),
            adjacent_to=Adjacency(anchor_room_id="anchor_room", side="north", source_quote="s", verified=True),
        ),
        Room(
            id="claimant_z", name="Claimant Z", zone="other", **dims(),
            adjacent_to=Adjacency(anchor_room_id="anchor_room", side="north", source_quote="s", verified=True),
        ),
    ]
    spec = SpatialSpec(document_id="conflict", rooms=rooms, equipment=[], exits=[], facts=[], abstentions=[])
    plan_a = layout.place(spec)
    plan_b = layout.place(spec)
    assert plan_a.model_dump_json() == plan_b.model_dump_json()  # deterministic, not arbitrary

    by_id = {r.id: r for r in plan_a.rooms}
    # "claimant_a" sorts before "claimant_z" -> wins the slot deterministically.
    assert by_id["claimant_a"].position_source == "stated"
    assert by_id["claimant_z"].position_source == "inferred"
    assert not _overlaps(by_id["claimant_a"], by_id["claimant_z"])
    assert any("both claim" in n for n in plan_a.notes)
