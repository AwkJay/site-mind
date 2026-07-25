"""SiteMind backend — FastAPI app exposing every endpoint in CONTRACT.md."""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import audit, config
from .agents.action_brief import router as action_brief_router
from .agents.compliance import router as compliance_router
from .agents.copilot import router as copilot_router
from .agents.copilot_agent import router as copilot_agent_router
from .audit_api import router as audit_router, seed_preloaded
from .clause_viewer import router as clause_viewer_router
from .clock import router as clock_router
from .commissioning import router as commissioning_router
from .cost_risk import router as cost_risk_router
from .documents import router as documents_router
from .eval import router as eval_router
from .kg import router as kg_router
from .overview import router as overview_router
from .schedule import router as schedule_router
from .supply_chain import router as supply_chain_router
from .timeline import router as timeline_router
from .trace_api import router as trace_router

app = FastAPI(title="SiteMind", version="1.0.0")

# CORS for the Next.js frontend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    """offline_mode is True when no live LLM provider is configured. `provider` names
    the active backend (offline | codex | openai | anthropic). langfuse_enabled is
    True only when both LANGFUSE_SECRET_KEY/LANGFUSE_PUBLIC_KEY are configured —
    the local trace log (`/api/trace`) is written either way."""
    return {
        "status": "ok",
        "offline_mode": config.OFFLINE_MODE,
        "provider": config.LLM_PROVIDER,
        "langfuse_enabled": config.LANGFUSE_ENABLED,
        "vector_store": config.RETRIEVAL_VECTOR_STORE,
        "audit_backend": audit.backend_name(),
    }


routers = (
    overview_router,
    documents_router,
    compliance_router,
    action_brief_router,
    copilot_router,
    copilot_agent_router,
    clause_viewer_router,
    commissioning_router,
    schedule_router,
    supply_chain_router,
    timeline_router,
    cost_risk_router,
    kg_router,
    eval_router,
    trace_router,
    clock_router,
    audit_router,
)


@app.on_event("startup")
def _seed_audit_ledger() -> None:
    """Backfill the preloaded demo project's current NCRs (plan §D) so
    /api/audit isn't empty on stage. Idempotent via content_hash — safe to
    run on every boot, never duplicates. Never raises: a Mongo/JSONL hiccup
    here must not prevent the app from starting."""
    try:
        seed_preloaded()
    except Exception:
        logging.getLogger(__name__).warning("audit: startup seed failed.", exc_info=True)

# Standalone retrieval package (Phase 3) — mounted only when RETRIEVAL_ENABLED
# is true, so with the flag off this import never executes and none of that
# package's code runs at all (see app/config.py).
if config.RETRIEVAL_ENABLED:
    from .retrieval.router import router as retrieval_router

    routers = routers + (retrieval_router,)

# Codebook MCP client (step 5, docs/BUILD_PLAN_CODEBOOK.md) — mounted only
# when CODEBOOK_ENABLED is true, so with the flag off this import never
# executes and the `mcp` client package is never touched at all (see
# app/config.py).
if config.CODEBOOK_ENABLED:
    from .codebook_router import router as codebook_router

    routers = routers + (codebook_router,)

for r in routers:
    app.include_router(r)
