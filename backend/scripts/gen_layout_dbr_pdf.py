"""Regenerates `DC1-05-DBR-0007-R1_Layout-Design-Basis.pdf` from the `.md`
file of the same name (both in `data/project_docs/live_upload_samples/`).

The original PDF was produced by an ad hoc, uncommitted reportlab call
(`pdfinfo` on the committed file shows `Producer: ReportLab PDF Library`).
This script saves that generation step so the PDF is reproducible rather than
a one-off — spec `docs/superpowers/specs/2026-07-25-spatial-compliance-design.md`
§7.4 requires the `.pdf` to round-trip to the identical extraction result as
the `.md`, which is only checkable if regeneration is repeatable.

Deliberately simple: this is a flat notes document (a title, a metadata
block, a blockquote disclaimer, one `##` heading, and a flat list of
`Note N: ...` paragraphs separated by blank lines) — not a general
Markdown-to-PDF converter. It:
  - strips `#`/`##`/`>` markdown markers, rendering each as its own style,
  - converts `**bold**` spans to reportlab `<b>...</b>` inline markup,
  - joins hard-broken lines within one block (markdown's trailing
    double-space line break, e.g. the Project/Document No/Discipline/Status
    block) with `<br/>` so they extract as separate lines, exactly like the
    committed PDF's `pdfplumber`-extracted text does today,
  - otherwise renders one blank-line-delimited block as one paragraph.

Run from `backend/`: `.venv/bin/python scripts/gen_layout_dbr_pdf.py`
"""
from __future__ import annotations

import re
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

_HERE = Path(__file__).resolve().parent
SRC_MD = (
    _HERE.parent
    / "data"
    / "project_docs"
    / "live_upload_samples"
    / "DC1-05-DBR-0007-R1_Layout-Design-Basis.md"
)
DST_PDF = SRC_MD.with_suffix(".pdf")


def _inline(text: str) -> str:
    """`**bold**` -> `<b>bold</b>`. Nothing else in this document needs
    inline markdown conversion (no italics, links, or code spans)."""
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)


def build_pdf(md_path: Path = SRC_MD, pdf_path: Path = DST_PDF) -> None:
    raw = md_path.read_text(encoding="utf-8")

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("DBRTitle", parent=styles["Title"], fontSize=15, spaceAfter=12)
    heading_style = ParagraphStyle("DBRHeading2", parent=styles["Heading2"], fontSize=12, spaceBefore=10, spaceAfter=6)
    meta_style = ParagraphStyle("DBRMeta", parent=styles["BodyText"], fontSize=10, leading=13, spaceAfter=10)
    quote_style = ParagraphStyle("DBRQuote", parent=styles["BodyText"], fontSize=9, leading=12, textColor="#555555", spaceAfter=10)
    body_style = ParagraphStyle("DBRBody", parent=styles["BodyText"], fontSize=10, leading=14, spaceAfter=8)

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title="DC1-05-DBR-0007-R1 Layout Design Basis",
        author="SiteMind (synthetic demo)",
    )
    story: list = []

    blocks = [b for b in raw.split("\n\n") if b.strip()]
    for block in blocks:
        lines = [ln.rstrip() for ln in block.splitlines() if ln.strip()]
        first = lines[0].strip()

        if first.startswith("# "):
            story.append(Paragraph(_inline(first[2:].strip()), title_style))
        elif first.startswith("## "):
            story.append(Paragraph(_inline(first[3:].strip()), heading_style))
        elif first.startswith("> "):
            merged = " ".join(ln.strip().lstrip(">").strip() for ln in lines)
            story.append(Paragraph(_inline(merged), quote_style))
        elif len(lines) > 1:
            # A markdown hard-line-break block (e.g. Project / Document No /
            # Discipline / Status) — keep each source line on its own visual
            # line via <br/>, not merged into one flowing sentence.
            html = "<br/>".join(_inline(ln.strip()) for ln in lines)
            story.append(Paragraph(html, meta_style))
        else:
            story.append(Paragraph(_inline(first), body_style))

    doc.build(story)


if __name__ == "__main__":
    build_pdf()
    print(f"wrote {DST_PDF}")
