"""Tests for `POST /api/compliance/floor-plan` (spec §5.6 / §8) — end-to-end
via the demo document, the "no spatial content" honest-abstention path, and
the flag-off import-isolation guarantee."""
from __future__ import annotations

import sys

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

DEMO_PATH = "data/project_docs/live_upload_samples/DC1-05-DBR-0007-R1_Layout-Design-Basis.md"


def _post_demo_md():
    with open(DEMO_PATH, "rb") as f:
        return client.post(
            "/api/compliance/floor-plan",
            files={"file": ("DC1-05-DBR-0007-R1_Layout-Design-Basis.md", f, "text/markdown")},
        )


def test_demo_doc_end_to_end():
    resp = _post_demo_md()
    assert resp.status_code == 200
    body = resp.json()

    assert body["has_spatial_data"] is True
    assert body["reason"] is None
    assert body["document_id"]

    plan = body["floor_plan"]
    room_ids = {r["id"] for r in plan["rooms"]}
    assert "data_hall_1" in room_ids
    assert "lv_switchroom" in room_ids
    assert "cooling_plant_room" in room_ids
    assert "corridor" in room_ids

    findings = {f["item"]: f for f in body["findings"]}
    # NCR-1: LV panel front clearance 0.8 m vs CEA's 1.0 m -> FAIL
    front = next(f for f in body["findings"] if "front" in f["finding"].lower())
    assert front["citation"]["clause"] == "37(iii)(a)"
    assert front["severity"] == "HIGH"
    assert front["domain"] == "spatial"

    # NCR-2: dead-end corridor 18 m vs NBC's 15 m -> FAIL, explicitly noting
    # the verdict holds without a stated occupancy group.
    dead_end = next(f for f in body["findings"] if "dead-end" in f["finding"].lower())
    assert dead_end["citation"]["clause"] == "4.4.2.2(c)"
    assert "without the occupancy group being stated" in dead_end["finding"]

    # No FAIL for rear clearance (0.9 m passes CEA's 20cm/75cm envelope) or
    # rear passage height (2.1 m passes the 1.8 m minimum) -> only the two
    # FAILs above should be present.
    assert len(body["findings"]) == 2

    # At least one visible abstention (travel distance / exit width never
    # computable in this doc).
    assert len(body["abstentions"]) >= 1
    reasons = " ".join(a["why"] for a in body["abstentions"])
    assert "travel distance" in reasons.lower() or "occupant load" in reasons.lower()

    # server_hall rendered but flagged not_checked.
    zones = {z["zone"] for z in body["not_checked_zones"]}
    assert "server_hall" in zones

    coverage = body["coverage"]
    assert coverage["params_extracted"] > 0
    assert coverage["params_checked"] > 0
    assert coverage["abstained"] >= 1


def test_exit_width_abstention_is_not_duplicated():
    """Regression test: the demo doc has an exit door but no stated occupant
    load, which both `spatial/extract.py` (a document-level always-abstain)
    and `checks_spatial.py`'s EGRESS_EXIT_WIDTH (a per-item abstain_reason)
    independently flag. The endpoint must show this exactly once — the more
    specific check-stage wording — not once from each stage, and
    `coverage['abstained']` must equal the de-duplicated list's length."""
    resp = _post_demo_md()
    assert resp.status_code == 200
    body = resp.json()

    exit_related = [a for a in body["abstentions"] if "exit width" in a["what"].lower()]
    assert len(exit_related) == 1, f"expected exactly one exit-width abstention, got {exit_related}"
    assert "EGRESS_EXIT_WIDTH" in exit_related[0]["what"]

    assert body["coverage"]["abstained"] == len(body["abstentions"])


def test_no_spatial_content_returns_false_not_error():
    resp = client.post(
        "/api/compliance/floor-plan",
        files={"file": ("notes.txt", b"This document has no rooms or clearances at all.", "text/plain")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["has_spatial_data"] is False
    assert body["reason"]
    assert body["floor_plan"] is None
    assert body["findings"] == []


def test_empty_file_returns_false_not_error():
    resp = client.post(
        "/api/compliance/floor-plan",
        files={"file": ("empty.txt", b"   \n\n  ", "text/plain")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["has_spatial_data"] is False
    assert "No extractable text" in body["reason"]


def test_unsupported_file_type_is_400_not_500():
    resp = client.post(
        "/api/compliance/floor-plan",
        files={"file": ("layout.zip", b"PK\x03\x04fake", "application/zip")},
    )
    assert resp.status_code == 400


def test_flag_off_no_llm_import_via_endpoint():
    """The whole floor-plan request path, exercised through the real FastAPI
    endpoint with SPATIAL_LLM_EXTRACTION_ENABLED off (the default), must not
    newly import any LLM SDK / network client module."""
    for name in list(sys.modules):
        if "app.spatial" in name or name == "app.llm_extract":
            del sys.modules[name]

    from app import config as app_config

    assert app_config.SPATIAL_LLM_EXTRACTION_ENABLED is False

    before = set(sys.modules)
    resp = _post_demo_md()
    assert resp.status_code == 200
    newly_imported = set(sys.modules) - before

    forbidden_substrings = (
        "claude_agent_sdk",
        "anthropic",
        "openai",
        "google.generativeai",
        "langgraph",
        "langchain",
        "genai",
    )
    hits = {name for name in newly_imported if any(s in name.lower() for s in forbidden_substrings)}
    assert hits == set(), f"unexpected LLM SDK modules newly imported: {hits}"
