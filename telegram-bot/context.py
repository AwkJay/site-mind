"""SiteMind project-context fetcher — pulls live project state from the
FastAPI backend's REST endpoints and assembles a structured context block
that the Gemini answerer can reference.

Caches aggressively (60 s TTL by default) so rapid-fire Telegram messages
don't hammer the backend.  Every fetch is best-effort: a single endpoint
failing just omits that section from the context rather than crashing.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

import httpx

log = logging.getLogger("sitemind-bot.context")

# How long a cached context stays fresh before we re-fetch.
_CACHE_TTL_SECONDS = 60


@dataclass
class _CachedContext:
    """In-memory cache entry for a fetched context block."""
    text: str = ""
    fetched_at: float = 0.0

    def is_stale(self) -> bool:
        return time.monotonic() - self.fetched_at > _CACHE_TTL_SECONDS


# Module-level singleton — one per bot process.
_cache = _CachedContext()


# ───────────────────────────────────────────────────────────────────── #
# Individual endpoint fetchers — each returns a human-readable section
# string, or "" on any error.
# ───────────────────────────────────────────────────────────────────── #

def _fetch_json(client: httpx.Client, url: str) -> dict | list | None:
    try:
        r = client.get(url, timeout=10.0)
        r.raise_for_status()
        return r.json()
    except Exception:
        log.warning("Failed to fetch %s", url, exc_info=True)
        return None


def _fmt_overview(data: dict | None) -> str:
    if not data:
        return ""
    lines = [
        "## PROJECT OVERVIEW",
        f"Project: {data.get('project', 'N/A')}",
        f"Issues caught: {data.get('issues_caught', '?')}",
        f"Engineer-hours saved: {data.get('engineer_hours_saved', '?')}",
        f"Rework avoided: ₹{data.get('rework_avoided_inr', '?'):,}" if isinstance(data.get('rework_avoided_inr'), (int, float)) else f"Rework avoided: ₹{data.get('rework_avoided_inr', '?')}",
        f"Schedule activities at risk: {data.get('schedule_at_risk', '?')}",
    ]
    ncrs = data.get("open_ncrs_by_severity") or {}
    if ncrs:
        parts = [f"{sev}: {cnt}" for sev, cnt in ncrs.items()]
        lines.append(f"Open NCRs by severity: {', '.join(parts)}")
    ms = data.get("machine_scale") or {}
    if ms:
        lines.append(
            f"Machine scale: {ms.get('documents_read', '?')} docs read, "
            f"{ms.get('clauses_checked', '?')} clauses checked, "
            f"{ms.get('cross_references_found', '?')} cross-refs found, "
            f"{ms.get('conflicts_surfaced', '?')} conflicts surfaced"
        )
    by_pillar = data.get("by_pillar") or []
    if by_pillar:
        lines.append("Per-pillar breakdown:")
        for p in by_pillar:
            name = p.get("pillar", "?")
            hrs = p.get("hours", 0)
            inr = p.get("inr", 0)
            basis = p.get("basis", "")
            inr_str = f"₹{inr:,}" if isinstance(inr, (int, float)) else f"₹{inr}"
            lines.append(f"  - {name}: {hrs} hrs, {inr_str} | {basis}")
    return "\n".join(lines)


def _fmt_supply_chain_risks(data: list | None) -> str:
    if not data:
        return ""
    lines = ["## SUPPLY CHAIN — AT-RISK SHIPMENTS"]
    for r in data:
        sid = r.get("shipment_id", "?")
        item = r.get("procurement_item", "?")
        days = r.get("days_at_risk", "?")
        root = r.get("root_cause", "?")
        crit = " [CRITICAL PATH]" if r.get("on_critical_path") else ""
        alt = r.get("recommended_alternative") or {}
        alt_str = ""
        if alt and alt.get("supplier"):
            alt_str = f" → alternative: {alt['supplier']} ({alt.get('lead_time_days', '?')}d, +{alt.get('cost_premium_pct', '?')}%)"
        lines.append(f"- {sid} ({item}): {days} days at risk{crit}. Root cause: {root}{alt_str}")
    return "\n".join(lines)


def _fmt_supply_chain_alerts(data: list | None) -> str:
    if not data:
        return ""
    lines = ["## SUPPLY CHAIN — ALERTS"]
    for a in data:
        sev = a.get("severity", "?")
        msg = a.get("message", "?")
        days = a.get("days_at_risk", "?")
        crit = " [CRITICAL PATH]" if a.get("on_critical_path") else ""
        lines.append(f"- [{sev}]{crit} {msg} (days at risk: {days})")
    return "\n".join(lines)


def _fmt_schedule_risks(data: list | None) -> str:
    if not data:
        return ""
    lines = ["## SCHEDULE RISKS"]
    for r in data:
        act = r.get("activity", "?")
        wbs = r.get("wbs_id", "?")
        slip = r.get("predicted_slip_days", "?")
        impact = r.get("project_impact_days", "?")
        crit = " [CRITICAL PATH]" if r.get("on_critical_path") else ""
        drivers = r.get("drivers") or []
        driver_str = "; ".join(drivers) if drivers else "unknown"
        lines.append(
            f"- {act} ({wbs}): slip {slip}d, project impact {impact}d{crit}. "
            f"Drivers: {driver_str}"
        )
        mit = r.get("mitigation")
        if mit:
            lines.append(f"  Mitigation: {mit}")
        mit_opts = r.get("mitigation_options") or []
        for opt in mit_opts[:3]:
            viable = "✅ viable" if opt.get("viable") else "❌ not viable"
            lines.append(
                f"  Option [{opt.get('type', '?')}]: {opt.get('summary', '?')} "
                f"({viable}, recovers {opt.get('days_recovered', '?')}d)"
            )
    return "\n".join(lines)


def _fmt_timeline(data: dict | None) -> str:
    if not data:
        return ""
    today = data.get("today_day", "?")
    events = data.get("events") or []
    lines = [f"## PROJECT TIMELINE (today = day {today})"]
    # Show only the most recent 15 events to keep context size reasonable.
    recent = sorted(events, key=lambda e: e.get("day", 0), reverse=True)[:15]
    for ev in recent:
        day = ev.get("day", "?")
        pillar = ev.get("pillar", "?")
        kind = ev.get("kind", "?")
        sev = ev.get("severity", "")
        title = ev.get("title", "?")
        detail = ev.get("detail", "")
        sev_tag = f" [{sev}]" if sev else ""
        lines.append(f"- Day {day} | {pillar}/{kind}{sev_tag}: {title}")
        if detail:
            lines.append(f"  {detail[:200]}")
    if len(events) > 15:
        lines.append(f"  ... and {len(events) - 15} more events")
    return "\n".join(lines)


def _fmt_cost_risk(data: dict | None) -> str:
    if not data:
        return ""
    lines = ["## COST-AT-RISK"]
    total = data.get("total_inr")
    if total is not None:
        lines.append(f"Total cost-at-risk: ₹{total:,}" if isinstance(total, (int, float)) else f"Total cost-at-risk: ₹{total}")
    for component in ("schedule_delay", "expedite_premium", "rework_exposure"):
        comp = data.get(component) or {}
        if comp:
            amt = comp.get("amount_inr", "?")
            amt_str = f"₹{amt:,}" if isinstance(amt, (int, float)) else f"₹{amt}"
            basis = comp.get("basis", "")
            lines.append(f"- {component.replace('_', ' ').title()}: {amt_str}")
            if basis:
                lines.append(f"  Basis: {basis}")
    return "\n".join(lines)


# ───────────────────────────────────────────────────────────────────── #
# Public API
# ───────────────────────────────────────────────────────────────────── #

def fetch_context(backend_url: str, *, force: bool = False) -> str:
    """Return a structured project-context string, cached with a 60 s TTL.

    If *force* is True the cache is bypassed (useful for /status command).
    Returns "" if the backend is entirely unreachable — callers handle that
    gracefully.
    """
    global _cache
    if not force and not _cache.is_stale():
        return _cache.text

    sections: list[str] = []
    with httpx.Client(base_url=backend_url) as client:
        overview = _fetch_json(client, "/api/overview")
        sc_risks = _fetch_json(client, "/api/supply-chain/risks")
        sc_alerts = _fetch_json(client, "/api/supply-chain/alerts")
        sched_risks = _fetch_json(client, "/api/schedule/risks")
        timeline = _fetch_json(client, "/api/timeline")
        cost_risk = _fetch_json(client, "/api/cost-risk")

    for fmt, data in [
        (_fmt_overview, overview),
        (_fmt_supply_chain_risks, sc_risks),
        (_fmt_supply_chain_alerts, sc_alerts),
        (_fmt_schedule_risks, sched_risks),
        (_fmt_timeline, timeline),
        (_fmt_cost_risk, cost_risk),
    ]:
        section = fmt(data)
        if section:
            sections.append(section)

    text = "\n\n".join(sections)
    _cache = _CachedContext(text=text, fetched_at=time.monotonic())
    log.info("Project context refreshed (%d chars, %d sections)", len(text), len(sections))
    return text


def fetch_supply_chain_summary(backend_url: str) -> str:
    """Quick supply-chain-only summary for the /supply command."""
    with httpx.Client(base_url=backend_url) as client:
        risks = _fetch_json(client, "/api/supply-chain/risks")
        alerts = _fetch_json(client, "/api/supply-chain/alerts")
        shipments = _fetch_json(client, "/api/supply-chain/shipments")

    parts: list[str] = []

    # Shipment overview
    if shipments:
        parts.append(f"**Tracked shipments:** {len(shipments)}")
        for s in shipments:
            sid = s.get("id", "?")
            item = s.get("procurement_item", "?")
            stage = s.get("current_stage", s.get("stage", "?"))
            status = s.get("status", "?")
            parts.append(f"  • {sid} — {item} | stage: {stage} | status: {status}")

    r_section = _fmt_supply_chain_risks(risks)
    a_section = _fmt_supply_chain_alerts(alerts)
    if r_section:
        parts.append(r_section)
    if a_section:
        parts.append(a_section)

    return "\n".join(parts) if parts else "No supply chain data available."


def fetch_schedule_risks_summary(backend_url: str) -> str:
    """Quick schedule-risk summary for the /risks command."""
    with httpx.Client(base_url=backend_url) as client:
        risks = _fetch_json(client, "/api/schedule/risks")

    section = _fmt_schedule_risks(risks)
    return section if section else "No schedule risks flagged."
