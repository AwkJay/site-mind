"""Spatial Compliance — floor-plan ingestion, deterministic layout, and flat
param dicts for `agents/checks_spatial.py` (owned separately).

Spec: docs/superpowers/specs/2026-07-25-spatial-compliance-design.md

This package extends the existing scalar Compliance pillar (`app/ingest.py` ->
`app/agents/checks.py`) with a parallel, additive path for room geometry,
equipment clearances, and egress facts. It never touches the scalar path.
"""
from __future__ import annotations
