"""Tests for app.clause_viewer — the in-app clause context viewer that
replaces the dead gaudi.local verify_url link. Covers: a real mapped standard
resolves real verbatim context (exact clause AND parent-heading fallback),
an unmapped standard honestly reports has_context=False, and a bogus clause
number on a mapped standard also honestly reports has_context=False rather
than returning something misleading.
"""
from __future__ import annotations

from app.clause_viewer import get_clause_context


def test_exact_clause_heading_found():
    ctx = get_clause_context("IS 456:2000", "26.4.2.2")
    assert ctx.has_context is True
    assert ctx.filename == "is456_2000/is.456.2000.md"
    assert "26.4.2" in (ctx.heading or "")
    assert "footings minimum cover shall be 50 mm" in ctx.context_text


def test_sub_clause_falls_back_to_parent_heading():
    # "26.4.2.2" itself is not a markdown heading (it's a numbered sentence
    # inside the "26.4.2" section) — this must still resolve via the parent.
    ctx = get_clause_context("IS 456:2000", "26.4.2.1")
    assert ctx.has_context is True
    assert "26.4.2.1" in ctx.context_text


def test_second_mapped_standard_resolves():
    ctx = get_clause_context("IS 1893 (Part 1):2016", "7.2.3")
    assert ctx.has_context is True
    assert "Importance Factor" in (ctx.heading or "")


def test_unmapped_standard_is_honest():
    ctx = get_clause_context("IS 3043:1987 (First Revision)", "1.1")
    assert ctx.has_context is False
    assert ctx.context_text is None
    assert "No locally digitised source document" in ctx.note


def test_bogus_clause_number_is_honest():
    ctx = get_clause_context("IS 456:2000", "999.999.999")
    assert ctx.has_context is False
    assert "Could not locate" in ctx.note
