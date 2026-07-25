"""Copilot conversational edge — LangGraph (plan §F2). The ONLY place in this
codebase a general agent-orchestration framework is allowed to run: it routes
a question across pillars, remembers the conversation, and phrases cited
answers. It NEVER decides a compliance pass/fail — every tool below is a
thin, READ-ONLY caller of an existing, already-deterministic function.
Verdicts still come only from the B2 pipeline (`agents/compliance.py` /
`agents/rule_eval.py`); this module cannot reach that code path at all.

Gated on `config.COPILOT_AGENT_ENABLED` AND a present `GEMINI_API_KEY`. Every
langgraph/langchain import is LAZY, inside functions, so a keyless/flag-off
boot never even attempts to import this heavy dependency stack — the
POST /api/copilot/chat route defined at the bottom of this file falls back
to the existing single-shot `copilot.answer()` in that case. This mirrors
every other optional-integration flag in this project (Actian, Mongo,
Solana): unreachable/unconfigured -> graceful fallback, never a crash.
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from . import compliance
from .. import config
from ..overview import _evaluate_all
from ..schedule import risks as schedule_risks
from ..schemas import RFIAnswer
from ..supply_chain import alerts as supply_chain_alerts
from ..supply_chain import risks as supply_chain_risks
from .copilot import _hybrid_retrieve, answer as single_shot_answer

_SYSTEM_PROMPT = """You are SiteMind's project copilot for a hyperscale data-centre \
construction project. Answer using ONLY the tool results you receive — never invent a \
fact, a clause, a number, or a citation.

Rules:
- Always call at least one tool before answering a substantive question.
- If a retrieval tool (search_codebook / query_knowledge_base) returns an empty result, \
that means the project corpus has no confident answer — reply exactly: "No confident \
answer in the project corpus for that — this looks like it needs a new RFI." Do not \
guess or fall back on general knowledge.
- When you do have tool results, cite them by name/label in your answer (e.g. the \
standard clause, the NCR id, the shipment id).
- You never compute or state a compliance pass/fail verdict yourself — you may only \
report NCRs/verdicts that a tool already returned, exactly as returned.
- Be concise: a few sentences, not an essay.
"""


def _corpus_chunk_summary(chunks: list[dict]) -> list[dict]:
    out = []
    for c in chunks:
        src = c.get("source", {})
        out.append(
            {
                "label": src.get("label"),
                "detail": src.get("detail"),
                "verify_url": src.get("verify_url"),
            }
        )
    return out


def _make_tools():
    """Built lazily (only when the agent is actually constructed) so plain
    function objects here don't force an import of langchain_core at module
    load time. Each tool is a thin read-only wrapper — see module docstring."""
    from langchain_core.tools import tool

    @tool
    def search_codebook(query: str) -> list[dict]:
        """Search the digitised standards/codebook corpus (BM25 + dense hybrid
        retrieval, same engine as the Copilot page) for clauses relevant to
        `query`. Returns a list of {label, detail, verify_url} citations, or
        an empty list if nothing clears the confidence floor — an empty list
        means abstain, not 'try harder'."""
        chunks = _hybrid_retrieve(query)
        return _corpus_chunk_summary(chunks)

    @tool
    def query_knowledge_base(corpus: str, query: str) -> list[dict]:
        """Search a named knowledge-base corpus built from company-uploaded
        or filesystem documents (e.g. "structural_standard_codes",
        "sitemind_existing_standards" — only available when RETRIEVAL_ENABLED=1).
        Returns matching chunks as {document_id, text, score}, or an empty
        list if the corpus doesn't exist or nothing clears the confidence
        floor."""
        if not config.RETRIEVAL_ENABLED:
            return []
        from ..retrieval.index import get_corpus

        try:
            # Mirrors router.py's own once-per-process lazy build — this tool
            # never hits an /api/retrieval/* HTTP route, so nothing else would
            # ever trigger the corpora to actually build; without this call
            # get_corpus() always returns None and the tool always abstains.
            from ..retrieval.filesystem_corpora import ensure_filesystem_corpora

            ensure_filesystem_corpora()
            c = get_corpus(corpus)
            if c is None:
                return []
            hits = c.query(query)
        except Exception:
            # A corpus-build failure (e.g. the embeddings provider is
            # unreachable) must abstain, not crash the whole agent turn —
            # same "degrade gracefully, never crash" rule as everywhere else.
            logging.getLogger(__name__).warning(
                "copilot_agent: query_knowledge_base failed for corpus=%r; abstaining.",
                corpus, exc_info=True,
            )
            return []
        return [{"document_id": h.get("document_id"), "text": h.get("text"), "score": h.get("score")} for h in hits]

    @tool
    def get_open_ncrs(document_id: Optional[str] = None) -> list[dict]:
        """Read already-computed compliance NCRs (non-conformance reports) —
        does NOT compute a new verdict, only reports what the deterministic
        Compliance pipeline already decided. Pass a specific document_id to
        scope to one submittal, or omit to read across the whole project's
        Design Basis Report. Returns a compact summary per NCR: {id, item,
        severity, finding, citation}."""
        if document_id:
            try:
                results = [compliance.evaluate(document_id)]
            except Exception:
                return []
        else:
            results = _evaluate_all()
        out = []
        for r in results:
            for n in r.ncrs:
                out.append(
                    {
                        "id": n.id,
                        "item": n.item,
                        "severity": n.severity,
                        "finding": n.finding,
                        "citation": f"{n.citation.standard} {n.citation.clause}" if n.citation else None,
                    }
                )
        return out

    @tool
    def get_schedule_risk() -> list[dict]:
        """Read the already-computed CPM + leading-indicator schedule risk
        list (Pillar 3) — activities at risk of slipping, with drivers and
        mitigation. Does not run a new analysis, just reads the current
        result."""
        return [r.model_dump() for r in schedule_risks()]

    @tool
    def get_supply_chain_status() -> dict:
        """Read the already-computed supply-chain risk list and alert log
        (Pillar 4) — shipments at risk, root causes, and severity-tiered
        alerts. Does not run a new analysis, just reads the current result."""
        return {
            "risks": [r.model_dump() for r in supply_chain_risks()],
            "alerts": [a.model_dump() for a in supply_chain_alerts()],
        }

    return [search_codebook, query_knowledge_base, get_open_ncrs, get_schedule_risk, get_supply_chain_status]


_agent = None
_agent_build_failed = False


def _get_agent():
    """Builds (once, lazily) and caches the compiled LangGraph agent. Returns
    None if the flag is off, no key is present, or construction fails for any
    reason — the caller falls back to the existing single-shot copilot in
    every one of those cases, never raising into a request."""
    global _agent, _agent_build_failed
    if _agent is not None:
        return _agent
    if _agent_build_failed:
        return None
    if not config.COPILOT_AGENT_ENABLED or not config.GEMINI_API_KEY:
        return None

    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langgraph.prebuilt import create_react_agent

        model = ChatGoogleGenerativeAI(model=config.GEMINI_MODEL, google_api_key=config.GEMINI_API_KEY, temperature=0)
        checkpointer = _get_checkpointer()
        _agent = create_react_agent(model, _make_tools(), prompt=_SYSTEM_PROMPT, checkpointer=checkpointer)
        return _agent
    except Exception:
        _agent_build_failed = True
        return None


def _get_checkpointer():
    """MongoDBSaver keyed by thread_id, reusing the SAME Mongo instance as the
    audit ledger (plan §D) — this is the agent's chat memory, replacing any
    hand-rolled history rather than adding a second one. Returns None (agent
    still runs, just stateless per call) if MONGODB_URI is unset or the
    connection fails."""
    if not config.MONGODB_URI:
        return None
    try:
        import pymongo
        from langgraph.checkpoint.mongodb import MongoDBSaver

        client = pymongo.MongoClient(config.MONGODB_URI, serverSelectionTimeoutMS=3000)
        client.admin.command("ping")
        return MongoDBSaver(client, db_name=config.MONGODB_DB, checkpoint_collection_name="copilot_checkpoints")
    except Exception:
        return None


def agent_available() -> bool:
    return _get_agent() is not None


def _text_of(content) -> str:
    """AIMessage.content is typed str | list[str | dict] — Gemini/Anthropic
    can both return multi-block content. Join the text parts; skip non-text
    blocks (e.g. thinking/tool-use blocks) rather than stringifying them."""
    if isinstance(content, str):
        return content
    parts = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and isinstance(block.get("text"), str):
            parts.append(block["text"])
    return "".join(parts)


def run_chat(thread_id: str, message: str) -> dict:
    """Invokes the LangGraph agent for one turn. Returns {"answer": str,
    "sources": list[dict]} shaped like RFIAnswer — sources are best-effort
    extracted from the tool calls made during this turn (LangGraph doesn't
    give a first-class citation list, only the resulting message + the tool
    call/return trail, so we walk it). Caller (copilot.py's /chat route) is
    responsible for falling back to answer() if agent_available() is False;
    this function assumes the agent is already known to exist."""
    agent = _get_agent()
    result = agent.invoke(
        {"messages": [{"role": "user", "content": message}]},
        config={"configurable": {"thread_id": thread_id}},
    )
    messages = result["messages"]
    final_text = _text_of(messages[-1].content) if messages else ""

    sources: list[dict] = []
    for m in messages:
        tool_calls = getattr(m, "tool_calls", None)
        if not tool_calls:
            continue
        for call in tool_calls:
            if call.get("name") not in ("search_codebook", "query_knowledge_base"):
                continue
            # The matching ToolMessage (with the actual return value) is
            # keyed by tool_call_id, not positionally adjacent — find it.
            # A tool's return value comes back as a JSON-encoded STRING in
            # ToolMessage.content (confirmed by direct inspection — LangGraph
            # serializes non-string tool returns, it does not keep the raw
            # Python object), so this must json.loads() it, not assume a list.
            for m2 in messages:
                if getattr(m2, "tool_call_id", None) != call.get("id"):
                    continue
                try:
                    parsed = json.loads(m2.content)
                except (TypeError, ValueError):
                    parsed = None
                if isinstance(parsed, list):
                    sources.extend(c for c in parsed if isinstance(c, dict))
                break

    return {"answer": final_text, "sources": sources}


class ChatRequest(BaseModel):
    message: str
    thread_id: Optional[str] = None


class ChatResponse(RFIAnswer):
    thread_id: str


router = APIRouter(prefix="/api/copilot", tags=["copilot"])


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    """Multi-turn Copilot edge (plan §F2). Falls back to the existing
    single-shot copilot.answer() whenever the LangGraph agent isn't
    available (flag off, no GEMINI_API_KEY, or the agent failed to build) —
    same abstention behavior either way, since search_codebook/
    query_knowledge_base and answer() share the same underlying retrieval
    floor. ALSO falls back on any exception from an actual invoke() attempt
    (e.g. a transient Gemini API error or free-tier RESOURCE_EXHAUSTED quota
    error, confirmed live 2026-07-25) rather than letting it 500 — a live-API
    hiccup should degrade to the deterministic single-shot answerer, same
    resilience pattern as every other optional integration in this project
    (Actian/Mongo/Solana all fail closed to a graceful fallback, never a crash)."""
    thread_id = req.thread_id or str(uuid.uuid4())
    if agent_available():
        try:
            result = run_chat(thread_id, req.message)
            return ChatResponse(answer=result["answer"], sources=result["sources"], thread_id=thread_id)
        except Exception:
            logging.getLogger(__name__).warning("copilot_agent: run_chat failed; falling back.", exc_info=True)

    fallback = single_shot_answer(req.message)
    return ChatResponse(answer=fallback.answer, sources=fallback.sources, seen_before=fallback.seen_before, thread_id=thread_id)
