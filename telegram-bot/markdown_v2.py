"""Deterministic Telegram MarkdownV2 formatting.

The LLM is unreliable at hand-escaping MarkdownV2 (a single missed `.` or `!`
makes Telegram reject the whole message) — same reason this project never
lets an LLM compute a verdict, it shouldn't have to correctly implement a
strict escaping grammar either. The system prompt only ever asks for
*bold* spans and literal bullet points; this module escapes everything else
and re-emits real (unescaped) delimiters around the bold spans.
"""
from __future__ import annotations

import re

_RESERVED_RE = re.compile(r"([_*\[\]()~`>#+\-=|{}.!])")
_BOLD_RE = re.compile(r"\*([^*\n]+?)\*")


def _escape(segment: str) -> str:
    segment = segment.replace("\\", "\\\\")
    return _RESERVED_RE.sub(r"\\\1", segment)


def to_markdown_v2(text: str) -> str:
    """Escape *text* for Telegram MarkdownV2, preserving *bold* spans as real bold."""
    out: list[str] = []
    pos = 0
    for m in _BOLD_RE.finditer(text):
        out.append(_escape(text[pos:m.start()]))
        out.append("*" + _escape(m.group(1)) + "*")
        pos = m.end()
    out.append(_escape(text[pos:]))
    return "".join(out)


def strip_for_speech(text: str) -> str:
    """Remove markdown markup so TTS doesn't read out asterisks/backslashes."""
    text = _BOLD_RE.sub(r"\1", text)
    text = text.replace("•", ". ").replace("`", "")
    return text
