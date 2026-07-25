"""SiteMind context-aware answerer — sends the user's question to the LLM
with the live project context injected as a system prompt.

Uses llm_client.py's fallback chain (MiniMax-M3 → Qwen3.6 → Gemini)
instead of calling Gemini directly.  Falls back to the backend copilot
endpoint for deep standards/retrieval questions the flat context can't
cover.

The module never fabricates data: every answer traces to the structured
context fetched from the backend REST APIs, and the system prompt
explicitly instructs abstention when the context doesn't cover the question.
"""
from __future__ import annotations

import logging
import os

import httpx
from dotenv import load_dotenv

from llm_client import generate

load_dotenv()

log = logging.getLogger("sitemind-bot.answerer")

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

ABSTAIN_MSG = "I don't have that information in the current project data — please check with the project team or the SiteMind dashboard."

_SYSTEM_PROMPT_TEMPLATE = """\
You are SiteMind, an AI-powered project intelligence assistant for **DC1** — \
a 48 MW Tier III (N+1) hyperscale data centre under construction in Chennai, India.

You help site engineers, project managers, and stakeholders understand:
- Project status, ROI, and cost-at-risk exposure
- Supply chain shipment tracking, delays, and alternatives
- Schedule risks, critical-path activities, and mitigation options
- Timeline of cross-pillar events (compliance NCRs, RFIs, alerts)
- Commissioning QA status

The project is being built by four EPC contractors:
- **L&T Construction** — Structural (foundation, rebar)
- **Tata Projects** — Architecture / Fire (raised floor, cladding)
- **Voltas Ltd** — Mechanical (CRAH units, N+1 cooling)
- **Sterling & Wilson** — Electrical (DRUPS, LV switchgear, busway)

CURRENT LIVE PROJECT DATA:
{context}

RULES:
1. Answer ONLY from the project data above. Never invent shipment IDs, dates, \
costs, or status that aren't in the data.
2. If the user is just saying hello, greeting you, or saying thanks, respond with a friendly, brief greeting and offer to help.
3. For any other questions, if it isn't answerable from the data above, say exactly: \
"{abstain_msg}"
4. Cite specific IDs (SHP-001, DC1-04-EL-030, etc.), dates, and numbers from \
the data.
5. Keep answers concise and actionable — this is a mobile field bot used on-site.
6. Use bullet points for multi-item answers.
7. For deep compliance/standards questions (e.g. "what does IS 456 say about \
cover?"), suggest the user ask on the SiteMind Copilot dashboard for cited \
clause lookup.
8. Never make a compliance pass/fail judgment — SiteMind's deterministic engine \
handles that, not you.
9. When mentioning costs, use ₹ (Indian Rupees) and use Indian numbering \
(lakhs/crores).
10. Format all responses using Telegram MarkdownV2 syntax.
    Syntax Rules:
    - Bold: *text*
    - Italic: _text_
    - Strikethrough: ~text~
    - Spoiler: ||text||
    - Inline Code: `code`
    - Code Block: ```python\ncode\n```
    - Inline Link: [Link Text](url)
    - Blockquote: >text
    CRITICAL ESCAPING RULE: Any character from this exact list outside code blocks MUST be preceded by a backslash (\\): _ * [ ] ( ) ~ ` > # + - = | {{ }} . !
    Layout Rules: Do NOT escape characters inside inline code or multi-line code blocks. Do NOT output HTML tags. Separate paragraphs with double line breaks.
"""


def _build_system_prompt(context: str) -> str:
    return _SYSTEM_PROMPT_TEMPLATE.format(
        context=context if context else "(Backend unreachable — no live data available)",
        abstain_msg=ABSTAIN_MSG,
    )


def answer_with_context(question_en: str, context: str) -> str:
    """Generate an answer using the LLM fallback chain with injected project context.

    Returns a plain-text answer string.  On any failure, returns ""
    so the caller can fall back to the copilot endpoint.
    """
    if not context.strip():
        log.warning("Empty context — falling back")
        return ""

    system_prompt = _build_system_prompt(context)
    answer = generate(system_prompt, question_en, temperature=0.1, max_tokens=1000)

    if not answer:
        log.warning("LLM chain returned empty answer")
        return ""

    return answer


def answer_via_copilot(question_en: str, thread_id: str, backend_url: str | None = None) -> str:
    """Fall back to the backend's copilot/chat endpoint.

    This is the existing path — kept as a fallback for deep standards/
    retrieval questions that benefit from the agent's search tools.
    Returns "" on failure so the caller can show a generic error.
    """
    url = backend_url or BACKEND_URL
    try:
        resp = httpx.post(
            f"{url}/api/copilot/chat",
            json={"message": question_en, "thread_id": thread_id},
            timeout=60.0,
        )
        resp.raise_for_status()
        payload = resp.json()
        answer = payload.get("answer") or ""
        sources = payload.get("sources") or []
        if not answer:
            return ""
        # Append citation sources if present
        if sources:
            lines = [answer, ""]
            for s in sources[:3]:
                label = s.get("label", "Source")
                url_s = s.get("verify_url")
                lines.append(f"— {label}" + (f" ({url_s})" if url_s else ""))
            return "\n".join(lines)
        return answer
    except Exception:
        log.exception("Copilot fallback failed")
        return ""
