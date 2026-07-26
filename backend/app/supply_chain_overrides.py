"""Per-shipment delay overrides — the same "prove it's not hardcoded" pattern
`clock.py` uses for the whole project's simulated "today", applied per
shipment instead of globally. Mutable state resets on backend restart;
nothing on disk changes.
See docs/superpowers/specs/2026-07-26-shipment-delay-mutation-design.md.
"""
from __future__ import annotations

MAX_CUMULATIVE_DELTA = 60

_overrides: dict[str, int] = {}


def get_delta(shipment_id: str) -> int:
    return _overrides.get(shipment_id, 0)


def _clear_downstream_caches() -> None:
    """Lazy import only — supply_chain.py imports this module at top level,
    so a top-level import back into it would be circular (same reason
    clock.py's _clear_downstream_caches does the same thing)."""
    from . import supply_chain

    supply_chain.shipments.cache_clear()
    supply_chain.risks.cache_clear()
    supply_chain.alerts.cache_clear()


def apply_delta(shipment_id: str, delta_days: int) -> int:
    global _overrides
    new_total = _overrides.get(shipment_id, 0) + delta_days
    new_total = max(-MAX_CUMULATIVE_DELTA, min(MAX_CUMULATIVE_DELTA, new_total))
    _overrides[shipment_id] = new_total
    _clear_downstream_caches()
    return new_total


def reset(shipment_id: str | None = None) -> None:
    global _overrides
    if shipment_id is None:
        _overrides = {}
    else:
        _overrides.pop(shipment_id, None)
    _clear_downstream_caches()
