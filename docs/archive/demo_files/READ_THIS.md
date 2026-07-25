# READ THIS FIRST — SiteMind docs map

This folder accumulated many overlapping files; this index is the front door so you don't have to guess.
For code-repo orientation see `../.claude/CLAUDE.md`; for live build state see `PROGRESS.md`.

## 🚀 Run & demo it

| File | What it's for |
| --- | --- |
| DEMO_STORY.md | The connected demo narration — one project, five pillars, one continuous thread, every number real. |
| DEMO_RUNBOOK.md | Operational demo-day checklist: startup order and what to do with the machine so nothing breaks on stage. |
| TELEPROMPTER.md | Word-for-word `DO`/`SAY` script to read while recording the demo video. |
| JUDGE_ONE_PAGER.md | The 90-second, one-page pitch: problem, solution, impact. |
| SETUP.md | Detailed OS-specific setup/troubleshooting — read this if `README.md`'s quick start doesn't cover your situation. |
| deck/pitch.html | **Canonical deck** (7 slides) — the one to use for submission/recording. Engineering/edit notes: `pitch.md`. |
| deck/index.html | Prior deck (16 slides), superseded by `pitch.html` above — kept for reference only. Slide outline: `DECK_OUTLINE.md`. |

## 📊 Pitch & impact

| File | What it's for |
| --- | --- |
| DECK_OUTLINE.md | Slide-by-slide outline for `deck/index.html` — the **superseded** deck, not the canonical `pitch.html`. Each slide tagged with the rubric criterion it scores. |
| pitch.md | Engineering/edit notes for `deck/pitch.html` — the canonical deck: layout engine, CSS component system, content-revision history, QA workflow. |
| BUSINESS_IMPACT.md | Real computed numbers anchored to the brief's own cited JLL / Turner & Townsend figures. |
| COMPETITIVE.md | Framing of how SiteMind differs from incumbents — the "how is this different?" answer judges ask. |
| PERSONAS.md | One user persona per pillar: read-only *for whom*, doing *what* on a working Tuesday. |

## 🧠 Understand the system

| File | What it's for |
| --- | --- |
| ARCHITECTURE.md | Source-of-truth architecture diagram-as-code (Mermaid) for all five pillars. |
| architecture.mmd | Same Mermaid flowchart, extracted verbatim from ARCHITECTURE.md purely for standalone rendering convenience — not separately authored or maintained; edit ARCHITECTURE.md and re-extract, don't edit this file directly. |
| features.md | Grounded inventory of every page and feature actually built, with inline file paths — also the current endpoint source of truth (superseded the archived `CONTRACT.md`). |
| PROJECT_OVERVIEW.html | Standalone rendered overview of the whole project. |
| codes.txt | Which Indian standards are still needed for the Commissioning QA pillar and why it's deferred. |

## 📈 Live state & known issues

| File | What it's for |
| --- | --- |
| `PROGRESS.md` | **The sole source of truth for build state and verified numbers.** The living checkpoint — cite its most recent (bottom-most) section when numbers matter. |
| PS_optimize.md | Known issues: gap audit against the problem statement — documents the dead citation-link landmine. |

## 🗄️ Archived

See `archive/` for historical / superseded build logs, including the ones moved out of this folder:
BUILD_PLAN_CODEBOOK.md, codebook_changes.md, codebook_console.md, IMPROVEMENTS.md, review.md, rag1.txt
(alongside earlier BUILD_PLAN_NEXT*.md, CODEX_SETUP.md, DEPLOY.md, and README.md).

---

⚠️ ../AGENTS.md is partly stale — see the banner at its top.
