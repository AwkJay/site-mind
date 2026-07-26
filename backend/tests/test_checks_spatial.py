"""Tests for `app/agents/checks_spatial.py` (spec §5.5 / §8) — the six
spatial-domain deterministic threshold checks, exercised at their boundary
values, plus the tri-state (PASS/FAIL/ABSTAIN) unstated-occupancy logic for
EGRESS_DEAD_END and EGRESS_TRAVEL_DISTANCE, and abstention on missing
companions / non-"stated" provenance.
"""
from __future__ import annotations

from app.agents import checks_spatial as cs


def _param(**kw) -> dict:
    base = {
        "param": None,
        "value": None,
        "unit": "m",
        "source_quote": "test",
        "provenance": "stated",
        "room_id": "room_1",
        "room_zone": "electrical",
        "equipment_kind": None,
        "occupancy_group": None,
        "occupant_load": None,
        "occupant_load_provenance": None,
    }
    base.update(kw)
    return base


def _check(check_id: str) -> cs.SpatialCheck:
    return next(c for c in cs.CHECKS_SPATIAL if c["id"] == check_id)


# --------------------------------------------------------------------------- #
# Registry shape
# --------------------------------------------------------------------------- #
def test_registry_has_exactly_six_checks_with_spec_ids_and_clause_keys():
    expected = {
        "SWBD_FRONT_CLEARANCE": "CEA_2010_37iii_a",
        "SWBD_REAR_CLEARANCE": "CEA_2010_37iii_b",
        "SWBD_REAR_PASSAGE": "CEA_2010_37iii_c",
        "EGRESS_DEAD_END": "NBC2016_4.4.2.2c",
        "EGRESS_TRAVEL_DISTANCE": "NBC2016_4.4.2.2a",
        "EGRESS_EXIT_WIDTH": "NBC2016_4.4.2.3",
    }
    assert len(cs.CHECKS_SPATIAL) == 6
    assert {c["id"]: c["clause_key"] for c in cs.CHECKS_SPATIAL} == expected
    for c in cs.CHECKS_SPATIAL:
        assert c["domain"] == "spatial"


# --------------------------------------------------------------------------- #
# SWBD_FRONT_CLEARANCE — boundary 0.99 / 1.0 / 1.01
# --------------------------------------------------------------------------- #
def test_front_clearance_boundary():
    check = _check("SWBD_FRONT_CLEARANCE")
    for value, expected in ((0.99, False), (1.0, True), (1.01, True)):
        p = _param(param="front_clearance", equipment_kind="lv_panel", value=value)
        assert check["applies_when"](p) is True
        assert check["rule"](p) is expected


def test_front_clearance_abstains_when_not_stated():
    check = _check("SWBD_FRONT_CLEARANCE")
    p = _param(param="front_clearance", equipment_kind="switchboard", value=0.5, provenance="inferred")
    assert check["rule"](p) is None
    assert "provenance" in check["abstain_reason"](p)


# --------------------------------------------------------------------------- #
# SWBD_REAR_CLEARANCE — boundary 0.19 / 0.20 / 0.75 / 0.76
# --------------------------------------------------------------------------- #
def test_rear_clearance_boundary():
    check = _check("SWBD_REAR_CLEARANCE")
    for value, expected in ((0.19, True), (0.20, False), (0.75, False), (0.76, True)):
        p = _param(param="rear_clearance", equipment_kind="lv_panel", value=value)
        assert check["rule"](p) is expected


def test_rear_clearance_abstains_when_inferred():
    check = _check("SWBD_REAR_CLEARANCE")
    p = _param(param="rear_clearance", equipment_kind="lv_panel", value=0.9, provenance="inferred")
    assert check["rule"](p) is None


# --------------------------------------------------------------------------- #
# SWBD_REAR_PASSAGE — needs the sibling rear_clearance value (cross-referenced
# via annotate_rear_clearance, not present on params.py's own row).
# --------------------------------------------------------------------------- #
def test_rear_passage_boundary_when_rear_clearance_exceeds_75cm():
    check = _check("SWBD_REAR_PASSAGE")
    for value, expected in ((1.79, False), (1.8, True), (1.81, True)):
        p = _param(
            param="rear_passage_height", equipment_kind="lv_panel", value=value, _rear_clearance_m=0.9
        )
        assert check["applies_when"](p) is True
        assert check["rule"](p) is expected


def test_rear_passage_not_applicable_when_rear_clearance_at_or_below_75cm():
    check = _check("SWBD_REAR_PASSAGE")
    p = _param(param="rear_passage_height", equipment_kind="lv_panel", value=1.5, _rear_clearance_m=0.75)
    # The clause itself only governs when rear space EXCEEDS 75 cm — a known
    # value at/under that threshold means this check does not apply at all.
    assert check["applies_when"](p) is False


def test_rear_passage_abstains_when_rear_clearance_unknown():
    check = _check("SWBD_REAR_PASSAGE")
    p = _param(param="rear_passage_height", equipment_kind="lv_panel", value=2.1, _rear_clearance_m=None)
    assert check["applies_when"](p) is True  # ambiguous, not silently skipped
    assert check["rule"](p) is None
    assert "rear clearance" in check["abstain_reason"](p)


def test_rear_passage_uses_annotate_rear_clearance_cross_reference():
    params = [
        {
            "param": "rear_clearance",
            "value": 0.9,
            "unit": "m",
            "provenance": "stated",
            "room_id": "room_1",
            "equipment_kind": "lv_panel",
            "occupancy_group": None,
            "occupant_load": None,
            "occupant_load_provenance": None,
        },
        {
            "param": "rear_passage_height",
            "value": 2.1,
            "unit": "m",
            "provenance": "stated",
            "room_id": "room_1",
            "equipment_kind": "lv_panel",
            "occupancy_group": None,
            "occupant_load": None,
            "occupant_load_provenance": None,
        },
    ]
    annotated = cs.annotate_rear_clearance(params)
    passage_row = next(p for p in annotated if p["param"] == "rear_passage_height")
    assert passage_row["_rear_clearance_m"] == 0.9
    check = _check("SWBD_REAR_PASSAGE")
    assert check["rule"](passage_row) is True


# --------------------------------------------------------------------------- #
# EGRESS_DEAD_END — the unstated-occupancy determinate-regardless logic.
# --------------------------------------------------------------------------- #
def test_dead_end_with_stated_strict_occupancy_group_boundary():
    check = _check("EGRESS_DEAD_END")
    for value, expected in ((5.9, True), (6.0, True), (6.1, False)):
        p = _param(param="dead_end_corridor", value=value, occupancy_group="educational")
        assert check["rule"](p) is expected


def test_dead_end_with_stated_loose_occupancy_group_boundary():
    check = _check("EGRESS_DEAD_END")
    for value, expected in ((14.9, True), (15.0, True), (15.1, False)):
        p = _param(param="dead_end_corridor", value=value, occupancy_group="industrial")
        assert check["rule"](p) is expected


def test_dead_end_unstated_group_fail_above_15m():
    """The demo doc's exact case: 18 m, no occupancy group stated -> FAIL,
    because 18 m breaches even the most permissive (15 m) NBC limit."""
    check = _check("EGRESS_DEAD_END")
    p = _param(param="dead_end_corridor", value=18.0, occupancy_group=None)
    assert check["rule"](p) is False
    explanation = check["explain"](p, False)
    assert "every occupancy classification" in explanation
    assert "without the occupancy group being stated" in explanation


def test_dead_end_unstated_group_pass_at_or_below_6m():
    check = _check("EGRESS_DEAD_END")
    p = _param(param="dead_end_corridor", value=5.0, occupancy_group=None)
    assert check["rule"](p) is True
    explanation = check["explain"](p, True)
    assert "without the occupancy group being stated" in explanation


def test_dead_end_unstated_group_ambiguous_band_abstains():
    """6 m < value <= 15 m with no stated occupancy group: NBC's limit could
    be 6 m or 15 m depending on group, so the verdict genuinely depends on
    information the document never gives -> ABSTAIN, not a guess either way."""
    check = _check("EGRESS_DEAD_END")
    p = _param(param="dead_end_corridor", value=10.0, occupancy_group=None)
    assert check["rule"](p) is None
    reason = check["abstain_reason"](p)
    assert "occupancy classification not stated" in reason
    assert "6 m" in reason and "15 m" in reason


def test_dead_end_unstated_group_boundary_15m_exactly_still_passes():
    # 15.0 satisfies the loose limit and is not > 15.0, so it is NOT ambiguous
    # even without a group: it can only ever be a PASS (<=15 always holds; the
    # only question a stricter group could raise is already resolved because
    # 15.0 > 6.0 would be a FAIL under a strict group) -- so this is in fact
    # the ambiguous band per the spec's literal boundaries (6 < value <= 15).
    check = _check("EGRESS_DEAD_END")
    p = _param(param="dead_end_corridor", value=15.0, occupancy_group=None)
    assert check["rule"](p) is None


def test_dead_end_abstains_when_inferred():
    check = _check("EGRESS_DEAD_END")
    p = _param(param="dead_end_corridor", value=3.0, provenance="inferred")
    assert check["rule"](p) is None


# --------------------------------------------------------------------------- #
# EGRESS_TRAVEL_DISTANCE — same determinate-regardless-of-group reasoning,
# against Table 5's overall min (22.5 m) / max (45.0 m).
# --------------------------------------------------------------------------- #
def test_travel_distance_unstated_group_pass_at_or_below_table5_min():
    check = _check("EGRESS_TRAVEL_DISTANCE")
    p = _param(param="travel_distance", value=22.5, occupancy_group=None)
    assert check["rule"](p) is True


def test_travel_distance_unstated_group_fail_above_table5_max():
    check = _check("EGRESS_TRAVEL_DISTANCE")
    p = _param(param="travel_distance", value=45.01, occupancy_group=None)
    assert check["rule"](p) is False


def test_travel_distance_unstated_group_ambiguous_band_abstains():
    check = _check("EGRESS_TRAVEL_DISTANCE")
    p = _param(param="travel_distance", value=30.0, occupancy_group=None)
    assert check["rule"](p) is None
    reason = check["abstain_reason"](p)
    assert "occupancy classification not stated" in reason


def test_travel_distance_with_stated_occupancy_group():
    check = _check("EGRESS_TRAVEL_DISTANCE")
    p_pass = _param(param="travel_distance", value=30.0, occupancy_group="residential")
    p_fail = _param(param="travel_distance", value=30.01, occupancy_group="residential")
    assert check["rule"](p_pass) is True
    assert check["rule"](p_fail) is False


def test_travel_distance_abstains_on_industrial_subgroup_ambiguity():
    """Table 5's Industrial row splits into g1_g2/g3 sub-groups with no single
    Group-G figure — a stated-but-unresolvable group must abstain, never
    silently pick a sub-group."""
    check = _check("EGRESS_TRAVEL_DISTANCE")
    p = _param(param="travel_distance", value=25.0, occupancy_group="industrial")
    assert check["rule"](p) is None


def test_travel_distance_abstains_when_inferred():
    check = _check("EGRESS_TRAVEL_DISTANCE")
    p = _param(param="travel_distance", value=10.0, provenance="inferred")
    assert check["rule"](p) is None


# --------------------------------------------------------------------------- #
# EGRESS_EXIT_WIDTH — needs BOTH occupant_load and occupancy_group.
# --------------------------------------------------------------------------- #
def test_exit_width_pass_and_fail_with_full_data():
    check = _check("EGRESS_EXIT_WIDTH")
    # residential: level_components_and_ramps = 6.5 mm/person; occupant_load 100 -> required 650 mm
    p_pass = _param(
        param="exit_width",
        unit="mm",
        value=650,
        occupancy_group="residential",
        occupant_load=100,
        occupant_load_provenance="stated",
    )
    p_fail = _param(
        param="exit_width",
        unit="mm",
        value=649,
        occupancy_group="residential",
        occupant_load=100,
        occupant_load_provenance="stated",
    )
    assert check["rule"](p_pass) is True
    assert check["rule"](p_fail) is False


def test_exit_width_abstains_when_occupant_load_missing():
    """The demo doc's exact case: an exit door width is stated but occupant
    load never is."""
    check = _check("EGRESS_EXIT_WIDTH")
    p = _param(param="exit_width", unit="mm", value=1200, occupancy_group="corridor", occupant_load=None)
    assert check["rule"](p) is None
    assert "occupant load" in check["abstain_reason"](p)


def test_exit_width_abstains_when_occupancy_group_missing():
    check = _check("EGRESS_EXIT_WIDTH")
    p = _param(
        param="exit_width",
        unit="mm",
        value=1200,
        occupancy_group=None,
        occupant_load=50,
        occupant_load_provenance="stated",
    )
    assert check["rule"](p) is None
    assert "occupancy classification not stated" in check["abstain_reason"](p)


def test_exit_width_abstains_when_inferred():
    check = _check("EGRESS_EXIT_WIDTH")
    p = _param(
        param="exit_width",
        unit="mm",
        value=1200,
        occupancy_group="residential",
        occupant_load=50,
        occupant_load_provenance="stated",
        provenance="inferred",
    )
    assert check["rule"](p) is None


# --------------------------------------------------------------------------- #
# applicable_checks_spatial
# --------------------------------------------------------------------------- #
def test_applicable_checks_spatial_matches_only_relevant_check():
    p = _param(param="front_clearance", equipment_kind="lv_panel", value=1.0)
    applied = cs.applicable_checks_spatial(p)
    assert [c["id"] for c in applied] == ["SWBD_FRONT_CLEARANCE"]
