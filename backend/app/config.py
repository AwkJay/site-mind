"""Runtime configuration. Loads backend/.env and exposes the offline-mode flag.

OFFLINE_MODE is the single source of truth for "do we have a usable API key".
When it is True the whole demo runs from deterministic Python + cached fixtures,
which is exactly what we want on a hackathon stage with flaky wifi.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# backend/  (this file lives in backend/app/config.py)
BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"
FIXTURES_DIR = DATA_DIR / "fixtures"

# Load backend/.env if present (no error if it's missing).
load_dotenv(BACKEND_DIR / ".env")

ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "").strip()
ANTHROPIC_MODEL_SMART: str = os.getenv("ANTHROPIC_MODEL_SMART", "claude-sonnet-4-6").strip()

# LLM-powered PERCEIVE step for compliance uploads (app/llm_extract.py). OFF by
# default so the demo stays deterministic. When 1, POST /api/compliance/ingest
# calls Claude (via the Claude Agent SDK, Claude Code subscription auth — a
# CLAUDE_CODE_OAUTH_TOKEN from `claude setup-token`, NOT an API key) to extract
# parameters, then a pure-Python span-verification gate keeps only values quoted
# verbatim from the document. Regex stays as the floor + fallback, so this can
# only ever add coverage, never regress. The pass/fail DECISION stays in
# checks.py regardless — the LLM never decides.
LLM_EXTRACTION_ENABLED: bool = os.getenv("LLM_EXTRACTION_ENABLED", "0").strip() == "1"
# Read here only so load_dotenv() surfaces it into the environment the Agent SDK
# subprocess inherits; the SDK itself consumes the env var directly.
CLAUDE_CODE_OAUTH_TOKEN: str = os.getenv("CLAUDE_CODE_OAUTH_TOKEN", "").strip()

OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-5.1").strip()

IAMHC_API_KEY: str = os.getenv("IAMHC_API_KEY", "").strip()
IAMHC_BASE_URL: str = os.getenv("IAMHC_BASE_URL", "https://api.iamhc.cn/v1").strip()

# Gemini API (Google AI Studio) — the HexaFalls default prose provider. Prose
# only, same as every other provider here: compliance pass/fail stays in
# checks.py/rule_eval.py regardless of which (or no) provider writes the words.
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-flash-latest").strip()
GEMINI_VISION_ENABLED: bool = os.getenv("GEMINI_VISION_ENABLED", "0").strip() == "1"

# Multi-account key rotation (app/gemini_key_pool.py) — each Google account's
# free tier is ~20 requests/day, so a second/third key roughly multiplies the
# usable daily budget. GEMINI_API_KEYS is built in priority order, skipping
# unset/empty entries; with only GEMINI_API_KEY set this is a single-element
# list and every downstream consumer behaves byte-identically to before this
# existed (bool(GEMINI_API_KEYS) == bool(GEMINI_API_KEY) in that case).
GEMINI_API_KEY_2: str = os.getenv("GEMINI_API_KEY_2", "").strip()
GEMINI_API_KEY_3: str = os.getenv("GEMINI_API_KEY_3", "").strip()
GEMINI_API_KEYS: list[str] = [k for k in (GEMINI_API_KEY, GEMINI_API_KEY_2, GEMINI_API_KEY_3) if k]


def _parse_rotate_after(raw: str) -> int:
    try:
        value = int(raw)
        return value if value > 0 else 19
    except (TypeError, ValueError):
        return 19  # unset/unparseable -> the documented default


# Successful live requests to serve on one key before rotating to the next
# (the (N+1)th request onward on that key is deliberately left as headroom,
# never spent). Applies per key, per Pacific day.
GEMINI_ROTATE_AFTER: int = _parse_rotate_after(os.getenv("GEMINI_ROTATE_AFTER", "19"))

# Hugging Face Inference API — used only by app/embeddings.py for Copilot's
# semantic retrieval (a free token from https://huggingface.co/settings/tokens).
# Independent of LLM_PROVIDER/OFFLINE_MODE, which govern prose generation only.
HF_TOKEN: str = os.getenv("HF_TOKEN", "").strip()

# Codex SDK uses local ChatGPT login (no API key); we only need a model id.
CODEX_MODEL: str = os.getenv("CODEX_MODEL", "gpt-5.4").strip()

# Langfuse (real tracing, optional — see app/langfuse_sink.py). trace.py's local
# provenance log is always written regardless; when both keys are present it is
# ALSO mirrored to Langfuse. Missing keys -> LANGFUSE_ENABLED False, no-op sink.
LANGFUSE_SECRET_KEY: str = os.getenv("LANGFUSE_SECRET_KEY", "").strip()
LANGFUSE_PUBLIC_KEY: str = os.getenv("LANGFUSE_PUBLIC_KEY", "").strip()
LANGFUSE_BASE_URL: str = os.getenv("LANGFUSE_BASE_URL", "https://cloud.langfuse.com").strip()
LANGFUSE_ENABLED: bool = bool(LANGFUSE_SECRET_KEY and LANGFUSE_PUBLIC_KEY)

# Which LLM backend produces prose/answers. "offline" (default) uses deterministic
# seeds + cached fixtures — the safe, key-free demo path. Override in backend/.env.
#   offline | codex | openai | anthropic | gemini
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "").strip().lower()
if not LLM_PROVIDER:
    # Back-compat: infer from whichever key is present, else stay offline.
    # IAMHC is the primary default, Gemini is the fallback.
    if IAMHC_API_KEY:
        LLM_PROVIDER = "iamhc"
    elif GEMINI_API_KEY:
        LLM_PROVIDER = "gemini"
    elif ANTHROPIC_API_KEY:
        LLM_PROVIDER = "anthropic"
    elif OPENAI_API_KEY:
        LLM_PROVIDER = "openai"
    else:
        LLM_PROVIDER = "offline"


def _provider_usable() -> bool:
    if LLM_PROVIDER == "iamhc":
        return bool(IAMHC_API_KEY)
    if LLM_PROVIDER == "codex":
        return True  # auth is external (ChatGPT login); runtime calls fall back if not ready
    if LLM_PROVIDER == "openai":
        return bool(OPENAI_API_KEY)
    if LLM_PROVIDER == "anthropic":
        return bool(ANTHROPIC_API_KEY)
    if LLM_PROVIDER == "gemini":
        # A pool with >=1 key is usable. Per-key exhaustion is a call-path
        # concern (app/gemini_key_pool.py), not an OFFLINE_MODE concern — an
        # all-exhausted pool must NOT flip this flag (that would change
        # unrelated behaviour); complete_text()'s cache/"" fallback handles it.
        return bool(GEMINI_API_KEYS)
    return False


# Offline when no usable provider. Compliance pass/fail + citations are ALWAYS
# deterministic regardless of this flag; only prose/answers change.
OFFLINE_MODE: bool = not _provider_usable()

PROJECT_NAME = "Hyperscale DC — Chennai, 48 MW, Tier III (N+1)"

# CORS. Comma-separated list; defaults to local dev only. Set in production
# (e.g. Render env var) to the deployed frontend's origin, e.g.
# ALLOWED_ORIGINS=https://sitemind.vercel.app,http://localhost:3000
ALLOWED_ORIGINS: list[str] = [
    o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",") if o.strip()
]

# Standalone standards/company-upload retrieval package (Phase 3,
# backend/app/retrieval/) — OFF by default. When unset/0, main.py never even
# imports the retrieval router, so none of that package's code, models, or
# dependencies (rank_bm25, sentence-transformers) are touched at all. Set to
# 1 to mount /api/retrieval/* endpoints.
RETRIEVAL_ENABLED: bool = os.getenv("RETRIEVAL_ENABLED", "0").strip() == "1"

# Codebook (standards-service/, a separate process — see
# docs/BUILD_PLAN_CODEBOOK.md) MCP client — OFF by default. When unset/0,
# main.py never imports codebook_client.py/codebook_router.py, so the `mcp`
# client package is never touched at all (same import-gating discipline as
# RETRIEVAL_ENABLED above). Set to 1 to mount /api/codebook/* endpoints,
# which proxy to Codebook's own MCP server (standards-service/app/mcp_server.py)
# over CODEBOOK_MCP_URL — this backend becomes an MCP *client*, the browser UI
# still only ever talks to this backend, never to Codebook directly.
CODEBOOK_ENABLED: bool = os.getenv("CODEBOOK_ENABLED", "0").strip() == "1"
# standards-service/run.sh's own default port (8010 — 8000/8001 are already
# spoken for by manak-dev and this backend). Not hardcoded deeper than here.
CODEBOOK_MCP_URL: str = os.getenv("CODEBOOK_MCP_URL", "http://127.0.0.1:8010/mcp").strip()

# Tiered compliance verdicts (plan §B2) — OFF by default. When unset/0, the
# per-param loop in agents/compliance.py keeps today's behaviour (silently
# `continue` past any param matching no checks.py rule) so the ~17 hand-vetted
# "certified" checks and their evals stay byte-identical. Set to 1 (together
# with RETRIEVAL_ENABLED=1, since the computed_draft path retrieves a clause
# in-process via Corpus.query) to let an LLM read a rule out of the retrieved
# clause and rule_eval.py compute it as a "computed_draft" NCR an engineer
# confirms, instead of silently dropping the param.
COMPLIANCE_RULE_EXTRACTION: bool = os.getenv("COMPLIANCE_RULE_EXTRACTION", "0").strip() == "1"

# Dense vector-store backend for retrieval/index.py's Corpus (plan §C — Actian
# VectorAI DB). "numpy" (default) is the exhaustive in-memory matrix every
# retrieval eval is calibrated against — byte-identical, untouched. "actian"
# routes dense search to a real, offline Actian VectorAI DB (Docker, gRPC on
# ACTIAN_URL) instead — proven by its own parity eval, not the numpy ones. An
# unreachable Actian container falls back to numpy with a logged warning.
RETRIEVAL_VECTOR_STORE: str = os.getenv("RETRIEVAL_VECTOR_STORE", "numpy").strip().lower()
ACTIAN_URL: str = os.getenv("ACTIAN_URL", "localhost:6574").strip()

# MongoDB Atlas audit ledger (plan §D) — append-only project memory. Unset ->
# app/audit.py falls back to a local JSONL ledger (backend/data/audit_events.jsonl),
# same content_hash-based idempotency, never raises into a request either way.
MONGODB_URI: str = os.getenv("MONGODB_URI", "").strip()
MONGODB_DB: str = os.getenv("MONGODB_DB", "sitemind").strip()

# Solana devnet notarization (plan §E) — OFF by default. When unset/0,
# app/notary.py's functions no-op {"status": "disabled"} and nothing imports
# solana/solders at all. Devnet only, zero real cost — anchors an audit
# event's content_hash via the SPL Memo program (backend/scripts/solana_setup.py
# generates+airdrops a keypair once; paste its base58 secret here).
SOLANA_ENABLED: bool = os.getenv("SOLANA_ENABLED", "0").strip() == "1"
SOLANA_RPC_URL: str = os.getenv("SOLANA_RPC_URL", "https://api.devnet.solana.com").strip()
SOLANA_SECRET_KEY: str = os.getenv("SOLANA_SECRET_KEY", "").strip()
SOLANA_CLUSTER: str = os.getenv("SOLANA_CLUSTER", "devnet").strip()

# Copilot conversational edge — LangGraph (plan §F2). OFF by default. When
# unset/0 OR no GEMINI_API_KEY, app/agents/copilot_agent.py never imports
# langgraph/langchain-google-genai at all (lazy import inside the module,
# guarded by this flag) and POST /api/copilot/chat falls back to the
# existing single-shot cited-RAG copilot.answer(). LangGraph is permitted
# ONLY on this conversational edge — it never decides a compliance verdict;
# it routes, calls read-only tools, and phrases cited answers. Memory (when
# MONGODB_URI is set) reuses the same Mongo instance as the audit ledger
# (plan §D) via langgraph-checkpoint-mongodb; unset MONGODB_URI -> the agent
# still runs, just without cross-turn memory (each call is stateless).
COPILOT_AGENT_ENABLED: bool = os.getenv("COPILOT_AGENT_ENABLED", "0").strip() == "1"

# Spatial Compliance (docs/superpowers/specs/2026-07-25-spatial-compliance-design.md)
# LLM extraction enhancement — OFF by default. Extraction in app/spatial/extract.py
# is regex-first and works fully offline with zero API keys; when this flag is 0
# (the default), app/spatial/extract.py imports NO llm module at all, mirroring the
# import-gating discipline of RETRIEVAL_ENABLED/CODEBOOK_ENABLED above. Regex stays
# the floor even when this is on (same "can only add coverage" contract as
# LLM_EXTRACTION_ENABLED).
SPATIAL_LLM_EXTRACTION_ENABLED: bool = os.getenv("SPATIAL_LLM_EXTRACTION_ENABLED", "0").strip() == "1"
