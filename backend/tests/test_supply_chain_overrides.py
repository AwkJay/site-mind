"""Tests for per-shipment delay overrides
(docs/superpowers/specs/2026-07-26-shipment-delay-mutation-design.md)."""
from __future__ import annotations

from app import supply_chain, supply_chain_overrides as overrides


def teardown_function():
    overrides.reset()


def test_apply_delta_increases_days_at_risk():
    before = next(s for s in supply_chain.shipments() if s.id == "SHP-001").days_at_risk
    overrides.apply_delta("SHP-001", 10)
    after = next(s for s in supply_chain.shipments() if s.id == "SHP-001").days_at_risk
    assert after == before + 10


def test_apply_delta_sets_root_cause_note():
    overrides.apply_delta("SHP-006", 5)
    shipment = next(s for s in supply_chain.shipments() if s.id == "SHP-006")
    assert "manually adjusted +5d via field update" in shipment.root_cause


def test_negative_delta_reduces_days_at_risk_and_clamps_at_zero():
    before = next(s for s in supply_chain.shipments() if s.id == "SHP-002").days_at_risk
    overrides.apply_delta("SHP-002", -1000)
    after = next(s for s in supply_chain.shipments() if s.id == "SHP-002").days_at_risk
    assert after == 0


def test_apply_delta_clamps_cumulative_to_max():
    overrides.apply_delta("SHP-001", 1000)
    assert overrides.get_delta("SHP-001") == overrides.MAX_CUMULATIVE_DELTA


def test_reset_restores_original_value():
    before = next(s for s in supply_chain.shipments() if s.id == "SHP-002").days_at_risk
    overrides.apply_delta("SHP-002", 7)
    overrides.reset("SHP-002")
    after = next(s for s in supply_chain.shipments() if s.id == "SHP-002").days_at_risk
    assert after == before
