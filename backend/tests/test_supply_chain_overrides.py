"""Tests for per-shipment delay overrides
(docs/superpowers/specs/2026-07-26-shipment-delay-mutation-design.md)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app import audit
from app import supply_chain, supply_chain_overrides as overrides
from app.main import app

client = TestClient(app)


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


def test_adjust_delay_endpoint_updates_shipment_and_records_audit_event():
    # NOTE: days_at_risk = max(0, projected_arrival_day - required_on_site_by),
    # so it floors at 0 and isn't a reliable ">= delta" signal for shipments
    # with negative baseline slack (e.g. SHP-003 in the current fixture data).
    # projected_arrival_day is unclamped and moves by exactly delta_days, so we
    # assert against that instead of hardcoding an absolute days_at_risk value.
    before = client.get("/api/supply-chain/shipments/SHP-003").json()

    resp = client.post("/api/supply-chain/shipments/SHP-003/adjust-delay", json={"delta_days": 8})
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "SHP-003"
    assert body["projected_arrival_day"] == before["projected_arrival_day"] + 8

    events = audit.get_events(pillar="supply_chain", limit=5)
    assert any(e["ref_id"] == "SHP-003" and e["kind"] == "shipment_delay_adjusted" for e in events)


def test_adjust_delay_unknown_shipment_returns_404():
    resp = client.post("/api/supply-chain/shipments/SHP-999/adjust-delay", json={"delta_days": 5})
    assert resp.status_code == 404


def test_adjust_delay_clamps_and_reset_restores():
    # Same days_at_risk-floors-at-0 caveat as above: assert the clamp via
    # projected_arrival_day (unclamped by the max(0, ...) floor), and assert
    # reset-restores via days_at_risk (safe here since it returns to baseline).
    before = client.get("/api/supply-chain/shipments/SHP-004").json()

    resp = client.post("/api/supply-chain/shipments/SHP-004/adjust-delay", json={"delta_days": 1000})
    assert resp.status_code == 200
    assert resp.json()["projected_arrival_day"] == before["projected_arrival_day"] + overrides.MAX_CUMULATIVE_DELTA

    reset_resp = client.post("/api/supply-chain/shipments/SHP-004/reset-delay")
    assert reset_resp.status_code == 200
    assert reset_resp.json()["days_at_risk"] == before["days_at_risk"]


def test_reset_delay_records_audit_event():
    client.post("/api/supply-chain/shipments/SHP-005/adjust-delay", json={"delta_days": 3})
    client.post("/api/supply-chain/shipments/SHP-005/reset-delay")
    events = audit.get_events(pillar="supply_chain", limit=5)
    assert any(e["ref_id"] == "SHP-005" and e["kind"] == "shipment_delay_reset" for e in events)
