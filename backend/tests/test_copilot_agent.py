"""Tests for app.agents.copilot_agent (plan §F2, LangGraph copilot edge).

No live LLM calls here (Gemini's free-tier quota is scarce this session) —
these test the parts that don't require an actual model call: the flag/key
gating, the read-only tool functions (pure wrappers over already-tested
deterministic pillar code), the ToolMessage-content parsing helper, and the
/chat endpoint's fallback path (which reuses the already-tested single-shot
copilot.answer()). The live agent.invoke() round trip is deferred to
later.md pending Gemini quota, same discipline as the rest of this project's
Gemini-backed paths.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app import config
from app.agents import copilot_agent
from app.main import app

client = TestClient(app)


def test_agent_unavailable_when_flag_off(monkeypatch):
    monkeypatch.setattr(config, "COPILOT_AGENT_ENABLED", False)
    monkeypatch.setattr(copilot_agent, "_agent", None)
    monkeypatch.setattr(copilot_agent, "_agent_build_failed", False)
    assert copilot_agent.agent_available() is False


def test_agent_unavailable_when_no_key(monkeypatch):
    monkeypatch.setattr(config, "COPILOT_AGENT_ENABLED", True)
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    monkeypatch.setattr(copilot_agent, "_agent", None)
    monkeypatch.setattr(copilot_agent, "_agent_build_failed", False)
    assert copilot_agent.agent_available() is False


def test_chat_endpoint_falls_back_when_agent_unavailable(monkeypatch):
    monkeypatch.setattr(copilot_agent, "_get_agent", lambda: None)
    resp = client.post("/api/copilot/chat", json={"message": "What is the seismic importance factor?"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["answer"]
    assert isinstance(data["sources"], list)
    assert data["thread_id"]  # generated when none was passed


def test_chat_endpoint_echoes_provided_thread_id(monkeypatch):
    monkeypatch.setattr(copilot_agent, "_get_agent", lambda: None)
    resp = client.post(
        "/api/copilot/chat",
        json={"message": "What is the seismic importance factor?", "thread_id": "thread-abc-123"},
    )
    assert resp.status_code == 200
    assert resp.json()["thread_id"] == "thread-abc-123"


def test_text_of_handles_plain_string():
    assert copilot_agent._text_of("hello") == "hello"


def test_text_of_handles_multi_block_content():
    blocks = [{"type": "text", "text": "hello "}, {"type": "thinking", "thinking": "..."}, "world"]
    assert copilot_agent._text_of(blocks) == "hello world"


def test_get_open_ncrs_tool_returns_compact_summaries():
    tools = copilot_agent._make_tools()
    get_open_ncrs = next(t for t in tools if t.name == "get_open_ncrs")
    result = get_open_ncrs.invoke({})
    assert isinstance(result, list)
    for entry in result:
        assert set(entry.keys()) == {"id", "item", "severity", "finding", "citation"}


def test_get_schedule_risk_tool_returns_serialized_risk_items():
    tools = copilot_agent._make_tools()
    get_schedule_risk = next(t for t in tools if t.name == "get_schedule_risk")
    result = get_schedule_risk.invoke({})
    assert isinstance(result, list)
    for entry in result:
        assert "activity" in entry and "predicted_slip_days" in entry


def test_get_supply_chain_status_tool_returns_risks_and_alerts():
    tools = copilot_agent._make_tools()
    get_supply_chain_status = next(t for t in tools if t.name == "get_supply_chain_status")
    result = get_supply_chain_status.invoke({})
    assert set(result.keys()) == {"risks", "alerts"}
    assert isinstance(result["risks"], list)
    assert isinstance(result["alerts"], list)


def test_search_codebook_tool_abstains_on_gibberish():
    tools = copilot_agent._make_tools()
    search_codebook = next(t for t in tools if t.name == "search_codebook")
    result = search_codebook.invoke({"query": "asdkjqwe zzxxcc nonsense gibberish query 12345"})
    assert result == []


def test_query_knowledge_base_tool_empty_for_unknown_corpus():
    tools = copilot_agent._make_tools()
    query_knowledge_base = next(t for t in tools if t.name == "query_knowledge_base")
    result = query_knowledge_base.invoke({"corpus": "does_not_exist_corpus", "query": "anything"})
    assert result == []
