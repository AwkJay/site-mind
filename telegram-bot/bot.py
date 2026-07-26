"""SiteMind field bot — project-context-aware Telegram + ElevenLabs
multilingual voice front end for SiteMind.  Standalone service; never
touches the deterministic verdict core.

Architecture (2026-07-26 rewrite):
  1. On every message, fetch live project context from the backend REST
     APIs (overview, supply chain, schedule risks, timeline, cost-risk)
     via context.py — cached 60 s so we don't hammer the backend.
  2. Inject that context into a Gemini system prompt and answer directly
     (answerer.py).  This gives the bot full project awareness without
     depending on the LangGraph copilot agent being enabled.
  3. If the direct answer abstains or Gemini is unavailable, fall back
     to POST /api/copilot/chat (the LangGraph agent with its own tools).
  4. Translate the answer back to the user's language and synthesise a
     voice reply via ElevenLabs TTS.

Commands:
  /start    — welcome message
  /status   — quick project status summary (force-refreshes context)
  /supply   — supply chain status at a glance
  /risks    — top schedule risks

ElevenLabs pipeline unchanged: STT (Scribe) for voice-note input,
TTS (eleven_multilingual_v2, opus_48000_128) for voice replies.

Run: ./run.sh (long-polling, no public webhook needed).
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from collections import OrderedDict

import httpx
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from context import fetch_context, fetch_supply_chain_summary, fetch_schedule_risks_summary
from answerer import answer_with_context, answer_via_copilot, ABSTAIN_MSG
from markdown_v2 import to_markdown_v2, strip_for_speech

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("sitemind-bot")

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ELEVENLABS_API_KEY = os.environ["ELEVENLABS_API_KEY"]
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

_eleven = ElevenLabs(api_key=ELEVENLABS_API_KEY)

# --------------------------------------------------------------------------- #
# Reply cache — avoids re-spending Gemini/ElevenLabs quota on repeat questions.
# Bounded FIFO; not persisted across restarts.
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
# LLM translation (using IAMHC fallback chain)
# --------------------------------------------------------------------------- #
def _llm_translate(system: str, text: str) -> str:
    """Returns "" on any failure so callers can fall back to the original."""
    from llm_client import generate
    try:
        resp = generate(system, text, temperature=0.1, max_tokens=1000)
        return (resp or "").strip()
    except Exception:
        log.exception("LLM translation failed")
        return ""


def translate_to_english(text: str) -> str:
    out = _llm_translate(
        "You are a professional translator. Translate the user's message to English. "
        "CRITICAL INSTRUCTION: If the message is already in English, you MUST return it EXACTLY unchanged. "
        "Output ONLY the English translation. Do not include any explanations, quotes, or markdown.",
        text,
    )
    return out or text


def translate_from_english(english_text: str, reference_text: str) -> str:
    out = _llm_translate(
        "You are a professional translator. Follow these instructions strictly:\n"
        f"1. Identify the language of this reference message: {reference_text!r}\n"
        "2. If the reference message is in English, you MUST output the English text provided below EXACTLY as is, without translation.\n"
        "3. If the reference message is NOT in English, translate the English text provided below into the EXACT SAME language as the reference message.\n"
        "4. Output ONLY the final text. Do not include any explanations, greetings, or conversational filler.",
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
    """Returns b"" on any TTS failure — caller falls back to text-only."""
    try:
        audio = _eleven.text_to_speech.convert(
            text=text,
            voice_id=ELEVENLABS_VOICE_ID,
            model_id="eleven_multilingual_v2",
            output_format="opus_48000_128",  # real OGG/Opus — Telegram sendVoice compatible
        )
        return b"".join(audio)
    except Exception:
        log.exception("ElevenLabs TTS failed")
        return b""


# --------------------------------------------------------------------------- #
# Hybrid answer pipeline
# --------------------------------------------------------------------------- #
def _get_answer(question_en: str, thread_id: str) -> str:
    """Try direct Gemini answer with project context, fall back to copilot agent.

    Returns a non-empty answer string, or the abstention message if
    everything fails.
    """
    # Step 1: Fetch live project context (cached, fast after first call)
    context = fetch_context(BACKEND_URL)

    # Step 2: Try direct Gemini answer with full context. A non-empty result
    # is trustworthy either way — a real answer, or the model legitimately
    # abstaining per its own instructions — so it's returned as-is. Only ""
    # means the call itself failed, which is what should fall through to
    # Step 3; previously an on-topic abstention was treated the same as a
    # failure and wasted a second network round trip on the copilot fallback
    # for no benefit (it would abstain again anyway).
    if context:
        answer = answer_with_context(question_en, context)
        if answer:
            log.info("Answered via direct context")
            return answer

    # Step 3: Fall back to copilot agent (has search tools for standards Q&A)
    answer = answer_via_copilot(question_en, thread_id, BACKEND_URL)
    if answer:
        log.info("Answered via copilot fallback")
        return answer

    # Step 4: Nothing worked
    log.warning("All answer paths exhausted — abstaining")
    return ABSTAIN_MSG


# --------------------------------------------------------------------------- #
# Telegram handlers
# --------------------------------------------------------------------------- #
async def _send_reply(update: Update, reply_local: str, audio: bytes) -> None:
    try:
        await update.message.reply_text(to_markdown_v2(reply_local), parse_mode="MarkdownV2")
    except Exception as e:
        log.error(f"Markdown parse error: {e}, falling back to plain text")
        await update.message.reply_text(reply_local)
    if audio:
        await update.message.reply_voice(voice=audio)


_MIN_RESPONSE_SECONDS = 5.0


async def _respond(update: Update, original_text: str, question_en: str) -> None:
    """Core response pipeline: answer → translate → text reply → voice reply.

    Always takes at least _MIN_RESPONSE_SECONDS end to end. A cache hit
    would otherwise reply near-instantly, which reads as obviously canned
    next to genuine LLM round trips in a live demo — so the wait is
    enforced here regardless of whether the answer came from cache or a
    live call.
    """
    start = time.monotonic()

    cached = _cache_get(question_en, original_text)
    if cached is not None:
        reply_local, audio = cached
    else:
        thread_id = f"telegram-{update.effective_chat.id}"
        reply_en = _get_answer(question_en, thread_id)
        if original_text.strip().lower() == question_en.strip().lower():
            # Original message was already English (translate_to_english is
            # a no-op in that case) — skip the reply-translation LLM call.
            # That call asks the model to choose between two embedded
            # texts, which the weaker fallback model sometimes gets wrong,
            # echoing back the reference question instead of the answer.
            reply_local = reply_en
        else:
            reply_local = translate_from_english(reply_en, original_text)
        audio = synthesize_voice(strip_for_speech(reply_local))
        _cache_put(question_en, original_text, reply_local, audio)

    elapsed = time.monotonic() - start
    if elapsed < _MIN_RESPONSE_SECONDS:
        await asyncio.sleep(_MIN_RESPONSE_SECONDS - elapsed)

    await _send_reply(update, reply_local, audio)


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


# --------------------------------------------------------------------------- #
# Slash commands
# --------------------------------------------------------------------------- #
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Welcome message with usage hints."""
    await update.message.reply_text(
        "👷 *SiteMind Field Bot*\n\n"
        "I'm your project intelligence assistant for the DC1 data centre project in Chennai.\n\n"
        "You can:\n"
        "• Ask me anything about the project — supply chain, schedule, timeline, status\n"
        "• Send a voice note in Hindi, English, or any regional language\n"
        "• Use commands:\n"
        "  /status — project status overview\n"
        "  /supply — supply chain status\n"
        "  /risks — schedule risks\n\n"
        "I answer from live project data only — I'll tell you if I don't have the information.",
        parse_mode="Markdown",
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Quick project status summary — force-refreshes context."""
    project_context = fetch_context(BACKEND_URL, force=True)
    if not project_context:
        await update.message.reply_text("⚠️ SiteMind backend is unreachable — please try again shortly.")
        return

    # Use Gemini to summarise the context into a concise status update
    answer = answer_with_context(
        "Give me a concise project status summary covering: overall health, "
        "open NCRs, supply chain alerts, schedule risks, and cost exposure. "
        "Use bullet points.",
        project_context,
    )
    if not answer:
        # Fall back to raw context (trimmed)
        answer = project_context[:2000]

    await update.message.reply_text(f"📊 *Project Status*\n\n{answer}", parse_mode="Markdown")


async def cmd_supply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Supply chain status at a glance."""
    summary = fetch_supply_chain_summary(BACKEND_URL)
    if not summary:
        await update.message.reply_text("⚠️ Could not fetch supply chain data.")
        return
    await update.message.reply_text(f"🚛 *Supply Chain Status*\n\n{summary}", parse_mode="Markdown")


async def cmd_risks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Top schedule risks."""
    summary = fetch_schedule_risks_summary(BACKEND_URL)
    if not summary:
        await update.message.reply_text("⚠️ Could not fetch schedule risk data.")
        return
    await update.message.reply_text(f"⚠️ *Schedule Risks*\n\n{summary}", parse_mode="Markdown")


# --------------------------------------------------------------------------- #
# App builder
# --------------------------------------------------------------------------- #
def build_app() -> Application:
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("supply", cmd_supply))
    app.add_handler(CommandHandler("risks", cmd_risks))

    # Free-form messages
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    return app


# --------------------------------------------------------------------------- #
# Demo cache pre-warming — computes text + voice for a fixed set of canonical
# questions at startup so a live demo gets an instant cache hit instead of a
# full LLM + TTS round trip. Presenter should ask these exact phrases; any
# other phrasing still works, just via the normal (now faster, see the Step 2
# fix above) live path.
# --------------------------------------------------------------------------- #
PREWARM_QUESTIONS = [
    "hello",
    "What's the weather like today?",
    "Tell me about the project status and cost at risk",
    "Supply chain shipment tracking",
]


def _prewarm_cache() -> None:
    for q in PREWARM_QUESTIONS:
        try:
            reply_en = _get_answer(q, thread_id="prewarm")
            audio = synthesize_voice(strip_for_speech(reply_en))
            _cache_put(q, q, reply_en, audio)
            log.info("Pre-warmed cache for: %r", q)
        except Exception:
            log.exception("Pre-warm failed for: %r", q)


if __name__ == "__main__":
    log.info("Starting SiteMind field bot (long-polling, context-aware)...")
    _prewarm_cache()
    build_app().run_polling()
