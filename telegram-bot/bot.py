"""SiteMind field bot (plan §F1, upgraded 2026-07-25) — Telegram + ElevenLabs
multilingual voice front end for SiteMind's project copilot. Standalone
service; never touches the deterministic verdict core.

Upgraded 2026-07-25 from the single-shot, RAG-only `/api/copilot/ask` to the
F2 LangGraph conversational edge (`/api/copilot/chat`, `app/agents/
copilot_agent.py`) — the earlier version could only search the standards/RAG
corpus, so it abstained ("no confident answer") on anything about NCRs,
schedule risk, or supply chain, which looked like a broken bot. The agent's
tools (search_codebook, query_knowledge_base, get_open_ncrs,
get_schedule_risk, get_supply_chain_status) give it read access across every
pillar — this is intentionally the guardrail, not a gap: every tool only
*reads* an already-computed result, none can write/mutate/execute anything,
so there is no path for this bot to "mess up" project state even though it
now has full project visibility. Each Telegram chat gets its own stable
`thread_id` (`telegram-<chat_id>`) so the agent's own conversation memory
(MongoDB-backed, see copilot_agent.py) carries across messages in that chat
— a real multi-turn conversation, not a one-shot Q&A.

Division of labor unchanged: ElevenLabs does STT (Scribe) + TTS, Gemini does
translation only (the bot's own call, separate from the backend agent's own
Gemini use), the backend copilot still owns retrieval/abstention/citations —
this bot never fabricates an answer, and falls back gracefully (same
ABSTAIN_MSG wording) whenever the backend itself falls back to the older
single-shot answerer (COPILOT_AGENT_ENABLED off or no GEMINI_API_KEY on the
backend).

A small in-memory reply cache avoids re-spending Gemini/ElevenLabs quota (and
guarantees a consistent answer+voice) when the exact same question is asked
again — keyed on (english question, asker's original message) since the
target language for translation/TTS depends on the latter.

Run: `./run.sh` (long-polling, no public webhook needed for the demo).
"""
from __future__ import annotations

import logging
import os
from collections import OrderedDict

import httpx
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from telegram import Update
from telegram.ext import Application, ApplicationBuilder, ContextTypes, MessageHandler, filters

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("sitemind-bot")

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ELEVENLABS_API_KEY = os.environ["ELEVENLABS_API_KEY"]
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

ABSTAIN_MSG = "No confident answer in the project corpus — raising this as an RFI."

_eleven = ElevenLabs(api_key=ELEVENLABS_API_KEY)

# --------------------------------------------------------------------------- #
# Reply cache — avoids re-spending Gemini/ElevenLabs quota on a repeat
# question and guarantees the same question always gets the same answer+
# voice. Bounded (simple FIFO eviction via OrderedDict) so a long-running
# process can't grow this unboundedly; not persisted across restarts —
# that's fine, it's a quota/consistency nicety, not a source of truth.
# --------------------------------------------------------------------------- #
_CACHE_MAX = 200
_reply_cache: "OrderedDict[tuple[str, str], tuple[str, bytes]]" = OrderedDict()


def _cache_get(question_en: str, original_text: str) -> tuple[str, bytes] | None:
    key = (question_en.strip().lower(), original_text.strip().lower())
    hit = _reply_cache.get(key)
    if hit is not None:
        _reply_cache.move_to_end(key)
    return hit


def _cache_put(question_en: str, original_text: str, reply_local: str, audio: bytes) -> None:
    key = (question_en.strip().lower(), original_text.strip().lower())
    _reply_cache[key] = (reply_local, audio)
    _reply_cache.move_to_end(key)
    while len(_reply_cache) > _CACHE_MAX:
        _reply_cache.popitem(last=False)


# --------------------------------------------------------------------------- #
# Gemini translation (thin — Gemini never touches retrieval or verdicts here)
# --------------------------------------------------------------------------- #
def _gemini_translate(system: str, text: str) -> str:
    """Returns "" on any failure (missing key, quota, network) so callers can
    fall back to the original text — translation is a nicety, never a hard
    dependency for answering the question."""
    if not GEMINI_API_KEY:
        return ""
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=GEMINI_API_KEY)
        resp = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=text,
            config=types.GenerateContentConfig(system_instruction=system, temperature=0, max_output_tokens=400),
        )
        return (resp.text or "").strip()
    except Exception:
        log.exception("Gemini translation failed")
        return ""


def translate_to_english(text: str) -> str:
    out = _gemini_translate(
        "Translate the user's message to English. If it is already in English, return it "
        "unchanged. Reply with ONLY the translation — no explanation, no quotes.",
        text,
    )
    return out or text


def translate_from_english(english_text: str, reference_text: str) -> str:
    out = _gemini_translate(
        "Translate the given English text into the SAME language as this reference message: "
        f"{reference_text!r}. If that reference is already in English, return the English text "
        "unchanged. Reply with ONLY the translation — no explanation, no quotes.",
        english_text,
    )
    return out or english_text


# --------------------------------------------------------------------------- #
# ElevenLabs STT / TTS
# --------------------------------------------------------------------------- #
def transcribe_voice(ogg_bytes: bytes) -> str:
    resp = _eleven.speech_to_text.convert(
        model_id="scribe_v1",
        file=("voice.ogg", ogg_bytes, "audio/ogg"),
    )
    return getattr(resp, "text", "") or ""


def synthesize_voice(text: str) -> bytes:
    """Returns b"" on any TTS failure — caller falls back to text-only reply."""
    try:
        audio = _eleven.text_to_speech.convert(
            text=text,
            voice_id=ELEVENLABS_VOICE_ID,
            model_id="eleven_multilingual_v2",
            output_format="opus_48000_128",  # real OGG/Opus container — verified against
            # Telegram's sendVoice requirement live this session.
        )
        return b"".join(audio)
    except Exception:
        log.exception("ElevenLabs TTS failed")
        return b""


# --------------------------------------------------------------------------- #
# Copilot backend
# --------------------------------------------------------------------------- #
def ask_copilot(question_en: str, thread_id: str) -> dict:
    """POSTs to the F2 conversational edge, /api/copilot/chat — full
    read-only project access (NCRs, schedule risk, supply chain, standards/
    KB search) via the LangGraph agent, with per-chat conversation memory.
    Falls back server-side to the older single-shot answerer whenever the
    agent isn't available on the backend (COPILOT_AGENT_ENABLED off, or no
    GEMINI_API_KEY there) — same response shape either way. Raises httpx
    errors up to the caller, which replies with a friendly "backend
    unreachable"."""
    resp = httpx.post(
        f"{BACKEND_URL}/api/copilot/chat",
        json={"message": question_en, "thread_id": thread_id},
        timeout=60.0,
    )
    resp.raise_for_status()
    return resp.json()


def format_reply(payload: dict) -> str:
    """The agent's own system prompt (copilot_agent.py) already produces the
    exact abstention wording when no tool result clears its confidence floor
    — trust `answer` as-is rather than inferring abstention from an empty
    `sources` list, since most tool calls here (NCRs/schedule/supply chain)
    never populate `sources` at all even on a fully successful answer (see
    run_chat()'s docstring: sources are only extracted from search_codebook/
    query_knowledge_base calls). Citations are appended only when present."""
    answer = payload.get("answer") or ABSTAIN_MSG
    sources = payload.get("sources") or []
    if not sources:
        return answer
    lines = [answer, ""]
    for s in sources[:3]:
        label = s.get("label", "Source")
        url = s.get("verify_url")
        lines.append(f"— {label}" + (f" ({url})" if url else ""))
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Handlers
# --------------------------------------------------------------------------- #
async def _respond(update: Update, original_text: str, question_en: str) -> None:
    cached = _cache_get(question_en, original_text)
    if cached is not None:
        reply_local, audio = cached
        await update.message.reply_text(reply_local)
        if audio:
            await update.message.reply_voice(voice=audio)
        return

    thread_id = f"telegram-{update.effective_chat.id}"
    try:
        payload = ask_copilot(question_en, thread_id)
    except Exception:
        log.exception("Backend unreachable")
        await update.message.reply_text("SiteMind backend is unreachable right now — please try again shortly.")
        return

    reply_en = format_reply(payload)
    reply_local = translate_from_english(reply_en, original_text)

    await update.message.reply_text(reply_local)

    audio = synthesize_voice(reply_local)
    if audio:
        await update.message.reply_voice(voice=audio)

    _cache_put(question_en, original_text, reply_local, audio)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text or ""
    question_en = translate_to_english(text)
    await _respond(update, text, question_en)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_file = await update.message.voice.get_file()
    ogg_bytes = bytes(await tg_file.download_as_bytearray())

    try:
        transcript = transcribe_voice(ogg_bytes)
    except Exception:
        log.exception("ElevenLabs STT failed")
        await update.message.reply_text("Sorry, I couldn't understand that voice note — could you send it as text?")
        return

    if not transcript.strip():
        await update.message.reply_text("Sorry, I couldn't understand that voice note — could you send it as text?")
        return

    question_en = translate_to_english(transcript)
    await _respond(update, transcript, question_en)


def build_app() -> Application:
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    return app


if __name__ == "__main__":
    log.info("Starting SiteMind field bot (long-polling)...")
    build_app().run_polling()
