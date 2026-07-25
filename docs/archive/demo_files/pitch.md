# Pitch Deck — Working Context

Exported context for a fresh Claude session picking up pitch-deck work. Covers the two deck
files, the standing hard constraint, the full edit history/rationale for `pitch.html`, the CSS
component system, bugs found + fixed, and the QA workflow used to verify every round of edits.

For a slide-by-slide outline of the older `docs/deck/index.html` deck, see `docs/DECK_OUTLINE.md`
(it documents `index.html`, not the canonical `pitch.html` covered here).

## Files — read this before touching anything

| File | Status |
|---|---|
| `docs/deck/index.html` | **The original 16-slide deck. NEVER overwrite or modify this file again.** |
| `docs/deck/pitch.html` | **The only file in scope for all pitch-deck work.** A separate, denser 8-slide deck. |

### Why the hard constraint on `index.html` exists

Earlier in this project's history, `index.html` was accidentally overwritten and had to be
restored byte-for-byte. That mistake set a standing rule for every session since: **all pitch-deck
edits happen in `pitch.html` only.** Do not read-then-rewrite `index.html`, do not "sync" content
between the two files, do not touch it even to fix something that looks like a bug. If a task ever
seems to require changing `index.html`, stop and ask the user first.

## What `pitch.html` is

A single self-contained HTML file (inline `<style>` + inline `<script>`, no build step) — an
8-slide scroll-snap deck styled as a dark, monospace-accented "engineering console" aesthetic
(lime-green `--accent: #bef264` on near-black `--bg-900: #0b0f14`). Open directly in a browser or
serve via `python3 -m http.server` from the **repo root** (so the `../../ui_images/*.png` relative
paths resolve).

### Stage tags (added in the "simple-first restructure" round)

Every slide now carries a small solid-fill `.stage-tag` pill (e.g. `PROBLEM`, `SOLUTION`, `WHY WE'RE
DIFFERENT`) directly above the existing technical `.eyebrow` line. This is a classic pitch-deck stage
label, distinct from the eyebrow (topic name, e.g. "03 · Introducing SiteMind") and distinct from the
rubric-tag chips (Innovation/Business Impact/etc, top-right of `.slide-meta`) — three separate label
systems now coexist per slide, each answering a different question ("what stage of the pitch is
this," "what's this slide about," "which rubric criteria does it serve").

### Layout engine (do not change without a specific reason — this is infrastructure, not content)

- `.deck { scroll-snap-type: y mandatory }` + `.slide { scroll-snap-align: start }` — one slide per
  viewport, snap-scroll.
- `.slide { min-height: 100vh; display: flex; flex-direction: column; justify-content: center }` —
  **important footgun, see "Known bug class" below.**
- `.slide-meta` — absolutely positioned top bar per slide (brand + rubric-tag chips).
- `.rail` — right-edge dot navigation, built and kept in sync by the `<script>` block via
  `IntersectionObserver` (threshold 0.55) watching which `.slide` is in view.
- `.hint` — fixed-position bottom-left "↓ scroll ... slide N / 7" footer.
- Keyboard nav: `ArrowDown`/`j`/`PageDown` and `ArrowUp`/`k`/`PageUp` scroll to next/prev slide
  (driven by the same script, reading which rail dot is `.active`).
- `@media print` block: landscape, one slide per page, colors preserved, rail/hint hidden. Never
  edited in this project's history — leave it alone unless explicitly asked.

**None of the above (CSS vars, scroll-snap, rail/dot script, print rules, keyboard nav) has been
touched across any round of content edits.** Every edit round changed slide *content* and
slide-specific presentational components only.

## Reusable CSS component system

These are the Bento-grid-style building blocks introduced/used across slides. When writing new
slide content, prefer reusing one of these over inventing a new component:

| Component | Used on | Purpose |
|---|---|---|
| `.stat-row` / `.stat-card` | 1, 6 | Horizontal strip of big-number stat cards (`.num` + `.lbl`). |
| `.split` | 2 | 2-column grid (text + screenshot), collapses to 1 col under 980px. |
| `.shot` / `.bar` | 2, 4 | Fake-browser-chrome screenshot frame (traffic-light dots + caption). |
| `.pipeline` / `.p-step` / `.p-arrow` / `.p-decide` | 3 | Horizontal numbered pipeline steps; `.p-decide` highlights the "decision" step with an accent border. |
| `.pillar-grid` / `.pillar-card` / `.dot` | 4 | 5-up (2-up on mobile) card grid for the five product pillars. |
| `.shot-grid` | 4 | 4-up grid of small `.shot` screenshots. |
| `.graph-frame` | 5 | **Purpose-built for the Knowledge Graph screenshot** — see below, do not reuse `.shot` for it. |
| `.chain-box` / `.chain-label` / `.chain` | 5 | Dashed-border monospace callout showing a live cross-link chain (e.g. Submittal ↔ RFI ↔ WBS task). |
| `.graph-callouts` / `.callout` | 5 | Two side-by-side annotation blurbs under the graph. |
| `.corpus-chip` | 6 | Small pill-shaped tag for standard names (IS 875, IS 13920, etc.). |
| `.two-col` / `.box` | 6 | 2-column boxed layout for economics/scale content. |
| `.close-grid` / `.fact-list` / `.fact-item` | *(unused as of the restructure below)* | 2-column "what's shipped vs. what's disclosed" fact lists — kept defined in CSS but no longer used on slide 8; the closing slide now uses a single `.footnote` proof-strip instead, to end on ambition rather than a recap. |
| `.tagline` / `.cta` | *(`.cta` used on 8; `.tagline` unused)* | Closing statement + call-to-action line. |
| `.stage-tag` | all 8 | Small solid-accent pill above the eyebrow — the classic pitch-stage label ("Problem", "Solution", etc), added in the simple-first restructure. |
| `.quote` | 1 | Accent-bordered callout, used for the single concrete 30mm/50mm example on the new Problem slide. |
| `.icon` / `.icon-sm` / `.icon-lg` | 3, 4, 5 | Generic monochrome line-icon system (see below), referencing `<symbol>`s in the hidden sprite `<svg>` right after `<body>`. |
| `.tech-stack` / `.tech-stack-label` / `.stack-diagram` / `.stack-tier` / `.stack-arrow` / `.tech-chip` | 4 | 3-tier flowchart (Frontend → Backend API → Rules + Retrieval) for the real project stack, each tier a bordered box of icon+label `.tech-chip`s connected by `→` arrows matching the pipeline's own arrow style. Replaced an earlier flat single-row chip list after user feedback that it "looked bad" and should be "a flowchart or professional diagram." |

### Icon sprite system (added when the deck got "too little visual/no diagrams" feedback)

A hidden `<svg><defs>...</defs></svg>` sprite sits right after the opening `<body>` tag (`position:absolute;width:0;height:0;overflow:hidden`), containing one `<symbol>` per icon (`i-search`, `i-book`, `i-check-circle`, `i-message`, `i-shield`, `i-chat`, `i-clock`, `i-box`, `i-gauge`, `i-flask`, `i-bolt`, `i-graph-node`, `i-code`, `i-window`, `i-chart`, `i-brush`, `i-atom`, `i-cluster`). Every icon use is `<svg class="icon"><use href="#i-name"></use></svg>`.

**Two generations of the tech-stack visual, both driven by direct user feedback:**

1. First pass (superseded): 9 tech-stack chips using generic representational icons (an atom/orbit shape for Python, a lightning bolt for FastAPI, a flask for scikit-learn, etc.) in a single flat wrapped row — a deliberate choice at the time to avoid recreating trademarked logos from memory.
2. **Current:** the user pushed back twice — "proper tech stack favicons" (wanted the *real* logos, not generic stand-ins) and "the tech stack representation is too bad, use some flowchart" (wanted an actual architecture diagram, not a flat chip list). Both addressed by:
   - Fetching the **real brand SVGs** for Python, FastAPI, Next.js, TypeScript, Tailwind CSS, scikit-learn from [Simple Icons](https://simpleicons.org) (CC0-licensed icon artwork; brand names/marks remain their owners' trademarks — this is the same usage pattern as a GitHub README tech-stack badge) via `curl` directly to raw `.svg` files (not WebFetch, which runs content through a summarizing model and would risk corrupting exact path data). sentence-transformers has no icon of its own, so it uses the **Hugging Face** mark (`logo-huggingface`) since sentence-transformers is a Hugging Face-ecosystem library — labeled "sentence-transformers" on the chip, logo represents the ecosystem it ships through, not a claim that HF and sentence-transformers are the same tool.
   - NetworkX and Recharts have **no official Simple Icons entry** (both 404'd) — these two still use the earlier generic icons (`i-graph-node`, `i-chart`), which is a defensible fallback since a 3-connected-node glyph for a *graph* library and a bar-chart glyph for a *charting* library are honest representations, not arbitrary substitutes.
   - Rebuilt the layout as a **3-tier flowchart** (`.stack-diagram`/`.stack-tier`/`.stack-arrow`): Frontend (Next.js 14, TypeScript, Tailwind, Recharts) → Backend API (FastAPI, Python) → Rules + Retrieval (scikit-learn, sentence-transformers, NetworkX), connected by the same `→` arrow glyph the 4-step pipeline above it uses, so the two diagrams on this slide read as one consistent visual language. The "Rules + Retrieval" tier gets the accent-glow border (`.stack-tier.accent`) since that's the innovation-thesis layer (deterministic checks).
   - The 6 generic icons that became fully orphaned by the real-logo swap (`i-flask`, `i-bolt`, `i-code`, `i-window`, `i-brush`, `i-cluster`) were deleted from the sprite rather than left as dead defs.

Where used: stat-card icons (slide 3: checkmark-circle, shield, atom), pipeline-step icons (slide 4: search/book/checkmark-circle/message, one per Extract/Retrieve/Decide/Narrate step), the tech-stack flowchart (slide 4, real logos via `.brand-icon` + two generic fallbacks via `.icon`), pillar-card icons (slide 5: shield/chat/clock/box/gauge, one per pillar, replacing the old plain `.dot` span — `.dot` itself is still defined in CSS but no longer used anywhere in the live deck).

Two icon classes now coexist: `.icon` (stroke-based line icons, `stroke: var(--accent)` by default, overridden to `var(--text-mid)` inside `.tech-chip`) for the custom/generic glyphs, and `.brand-icon` (filled, `fill: var(--text-mid)`) for real logo `<path>` marks pulled from Simple Icons — don't mix them up, a stroke-style rule applied to a filled logo path (or vice versa) will render wrong or invisible.

If you add a new custom (non-brand) icon: define one `<symbol>` in the sprite (viewBox `0 0 24 24`, simple primitives — circles/rects/lines/polylines/short paths, not complex bezier curves, since there's no visual preview while authoring; always screenshot-verify via the QA workflow below), then reference it with `<use>` and the `.icon` class. If you add a new real brand logo: fetch the raw SVG via `curl` from `https://cdn.jsdelivr.net/npm/simple-icons@latest/icons/<slug>.svg` (check simpleicons.org for the exact slug), extract just the `<path d="...">` into a `<symbol viewBox="0 0 24 24">`, and reference it with the `.brand-icon` class, not `.icon`.

### `.graph-frame` — why it's not just another `.shot`

Slide 5's Knowledge Graph screenshot originally used the standard `.shot` component (fake browser
chrome + `object-fit: cover; object-position: top`). `cover` cropped the bottom of the screenshot,
cutting off the inspector panel's "3 CONNECTION(S)" detail — the user caught this via a pasted
screenshot. Fix: a new `.graph-frame` component with **no chrome bar** and
`object-fit: contain` (not `cover`), centered in a flex container, so the *entire* screenshot
renders letterboxed on a dark background that blends with the screenshot's own dark theme. If you
add more graph/UI screenshots that must show every pixel (not just look like an app window), reuse
`.graph-frame`, not `.shot`.

## Known bug class — read before adding content to any slide

`.slide` uses `justify-content: center` with only `min-height: 100vh` (not a fixed height). If a
slide's total content height grows past 100vh, the flexbox centers the *taller* box within itself,
which shifts where the content visually starts. Symptom pattern to watch for:
- The `eyebrow`/`h1` visually crowds or overlaps the absolutely-positioned `.slide-meta` bar at the
  top (`top: 3.2vh`), **and simultaneously**
- The fixed-position `.hint` footer overlaps the last piece of slide content at the bottom.

Both symptoms appearing together means the slide overflowed 100vh — the fix is to **trim vertical
space** (shrink a component's height, tighten a margin), not to add more room. This exact bug hit
the graph slide (then slide 5, now slide 6) twice across two separate edit rounds:
- First time: after adding a new lede paragraph — fixed by shrinking `.graph-frame` from `46vh` →
  `36vh` and adding `margin-bottom: 0.6em` to the lede.
- Second time (simple-first restructure round): the h1 was rewritten to a 4-line headline
  ("Cross-Discipline Proof, Traced Through a Graph, Not Guessed by an Embedding.") — fixed not by
  shrinking `.graph-frame` further, but by **shortening the headline itself** to 2 lines ("Traced
  Through a Graph, Not Guessed by an Embedding."). Worth remembering: a long h1 is just as likely a
  cause of this overflow as an oversized image/component — check headline length first, it's the
  cheaper fix and also punchier copy.

`.graph-frame` is still tightly budgeted at 36vh — if you add more text to this slide, re-check for
this overflow, don't just assume there's headroom.

## Content evolution (three successive full rewrites, each replacing the last)

The narrative went through three complete rewrites of all 7 slides' copy, each driven by a
detailed user blueprint, each fully replacing the previous round's text (not additive):

1. **Bento-grid density pass** — the deck previously had text-wall paragraphs. Rewrote every slide
   into card/grid layouts with a hard budget (max ~20 words of body text per slide), while keeping
   the layout engine untouched.
2. **Domain-anchor rewrite #1** — flagged that leading with "The AI engineer" framing would read,
   to judges unfamiliar with EPC/data-center construction, as "this is a tool for writing code" —
   the wrong association entirely. Reframed around "The Automated Compliance Moat for Complex
   Infrastructure," eliminating "AI engineer" language throughout.
3. **Domain-anchor rewrite #2** — went further: anchor *every* slide explicitly on
   **hyperscale data-center construction physics** (structural + electrical engineering
   compliance), eliminating any remaining abstract/generic phrasing in favor of concrete,
   domain-specific detail (e.g. "30mm footing cover violation against the 50mm legal code minimum,"
   "Shanghai battery cell customs," "ASHRAE cooling envelope").
4. **Simple-first restructure (current, final)** — the deck previously opened directly into dense
   proof (100% vs 58.5% accuracy stat cards) with no plain-language problem statement first, and had
   no classic pitch-stage labels (only technical eyebrows + rubric chips). Went from 7 to 8 slides:
   added a brand-new plain-language Problem slide (1) and a "Why Existing Tools Fail" slide (2)
   before the stat-heavy hero (now slide 3, reframed as "Introducing SiteMind"); added a `.stage-tag`
   pill to every slide; moved the "Deep Tech & The Magic" slide to right before Impact and reframed
   it as "Why We're Different" (the deliberate "hammer" slide); added an explicit "labeled
   assumption" disclosure next to the ROI stat cards (previously implicit); and rewrote the closing
   slide to end on ambition ("The Verification Layer for Every Data Center Built in India") rather
   than a shipped-features recap. This is the version currently live in the file (see full
   slide-by-slide content below).

Two deliberate judgment calls made during rewrite #2, worth knowing if the wording looks slightly
off from a blueprint you're handed:
- Slide 4's Schedule Risk card: the source blueprint text read "...against active weather and
  labor **dines**" — clearly a typo. Corrected to "labor **constraints**" as the sensible reading.
- Slide 4's Supply Chain card: blueprint's general idea was "customs delay visibility" — used the
  blueprint's own concrete example ("Shanghai battery cell customs") instead of a generic phrase,
  consistent with rewrite #2's whole point (concrete over abstract).
- Slide 3: the old `.p-branch`/`.p-llm` dashed callout box ("the LLM never votes") was removed
  entirely — the new lede sentence already states this, so the box would have been redundant.

## Current full content (verbatim, as of the last edit — verify against the live file if it's been
a while; this doc is a snapshot, not a live mirror)

**Slide 1 — Problem** · stage-tag `Problem` · rubric: Business Impact
- Eyebrow: `01 · The Problem`
- H1: `One Missed Number on a Drawing Can Stop a $15B Data Center.`
- Plain-language lede (no stats): a senior engineer checks compliance by hand; one overlooked clause means months of rework or an unsafe facility.
- `.quote` callout: the 30mm poured vs. 50mm legal minimum footing-cover example (IS 456:2000 Cl. 26.4.2.2) — the *only* concrete detail on this slide, deliberately no accuracy stats yet.

**Slide 2 — Why Existing Tools Fail** · stage-tag `Why Existing Tools Fail` · rubric: Business Impact, Innovation
- Eyebrow: `02 · The Gaps We Found`
- H1: `Manual Review Is Too Slow. Generic AI Tools Guess.`
- Three critiques (`ul.points`): manual review, generic RAG/chatbot tools (no hallucination guardrail), spreadsheets/checklists (don't scale, no cross-linking).
- `.footnote`: the 67% APAC schedule-overrun stat, explicitly attributed to the hackathon's own problem brief (Townsend survey) — never implied to be a SiteMind-measured number.

**Slide 3 — Introducing SiteMind** (was the old slide 1 hero) · stage-tag `Solution` · rubric: Innovation, Business Impact
- Eyebrow: `03 · Introducing SiteMind`
- H1: `Deterministic Compliance Verification, Not a Guess.`
- Lede: extracts parameters with source sentence, checks against a real cited IS/CEA clause, in seconds.
- Stats: `100%` SiteMind vs 58.5% naive-LLM accuracy (41-case benchmark, `backend/eval/report.json`) · `0.0%` hallucinated-citation rate · `5` offline-capable AI pillars, each verified by a real eval run. Each stat card now has an icon (`i-check-circle`, `i-shield`, `i-atom`).

**Slide 4 — How It Works** (was slide 3, content unchanged) · stage-tag `How It Works` · rubric: Innovation, Technical Excellence
- Eyebrow: `04 · System Architecture`
- H1: `Inverting the Stack: Rules Decide, Models Narrate`
- 4-step pipeline: `01 Extract` (`i-search`) → `02 Retrieve` (`i-book`) → `03 Decide` (`i-check-circle`, accent-highlighted) → `04 Narrate` (`i-message`) — one icon per step now, in a `.p-step-head` row next to the step number.
- New: a `.tech-stack` **3-tier flowchart** below the pipeline — "Real Stack, Three Layers" — Frontend (Next.js 14, TypeScript, Tailwind, Recharts) → Backend API (FastAPI, Python) → Rules + Retrieval (scikit-learn, sentence-transformers, NetworkX, accent-highlighted tier), using real brand logos (`.brand-icon`) for 6 of the 9 items and generic fallback icons for the 2 without an official mark (NetworkX, Recharts), plus a footnote stating "no model training anywhere, no agent-orchestration framework, optional LLM writes prose only." Added in two rounds: first the tech stack was missing entirely, then a flat chip-list first draft was replaced with this flowchart after feedback that a plain row of chips wasn't a "professional diagram."

**Slide 5 — Product Tour** (was slide 4, content unchanged) · stage-tag `Product Tour` · rubric: Business Impact, Innovation
- Eyebrow: `05 · One Shared Graph, Five Disciplines`
- H1: `One Shared Graph Over Five Disconnected Disciplines`
- 5-card pillar grid + 4-up screenshot grid (supply-chain, schedule, commissioning QA, overview). The deliberate multi-visual exception to the one-visual-per-slide rule. Each pillar card now has a distinct icon (Compliance=`i-shield`, Copilot=`i-chat`, Schedule=`i-clock`, Supply Chain=`i-box`, Commissioning=`i-gauge`) replacing the old plain `.dot` marker.

**Slide 6 — Why We're Different** (was slide 5 "Deep Tech & The Magic", reframed as the "hammer") · stage-tag `Why We're Different` · rubric: Innovation, Technical Excellence
- Eyebrow: `06 · No Vector Database Needed`
- H1: `Traced Through a Graph, Not Guessed by an Embedding.` (shortened from an original 4-line draft — see "Known bug class" above for why)
- `.graph-frame` Knowledge Graph screenshot (36vh, `object-fit: contain`) + `.chain-box` cross-link example + two callouts ("clickable system memory," "fully offline"). Placed immediately before Impact — the slide judges should remember.

**Slide 7 — Impact & Scale** (was slide 6 "Market & Business Impact") · stage-tag `Impact & Scale` · rubric: Business Impact, Scalability
- Eyebrow: `07 · Transparent Economics, Real Validation`
- Left box now has **three** stat cards: `~20 hrs`, `₹15L`, and `21/21` (real eval scripts passing, full suite — moved here from the old hero slide since it's validation evidence, not a hook stat).
- New `.footnote` directly under the stat-row: explicit "labeled cost assumptions, not measured outcomes" disclosure for the ROI figures — previously implicit.
- Right box unchanged: "zero fine-tuning" scale story + corpus chips.

**Slide 8 — Vision** (was slide 7 "The Ask & Operational Reality", restructured to end on ambition) · stage-tag `Vision` · rubric: all five chips
- Eyebrow: `08 · What's Next`
- H1: `The Verification Layer for Every Data Center Built in India.` (ambition, not a recap)
- Lede: today = one project type; tomorrow = every clause/discipline/contractor, same deterministic core, no retraining.
- The old two-column "What Is Shipped Today" / "Disclosed Project Scope" fact-lists were demoted to a single compact `.footnote` proof-strip below the lede (21/21 evals, genuine codes/logic, representative project data, 90-day pilot next) — the ambition headline now carries the emotional close, not a shipped-features recap.
- CTA unchanged: `Launch Verification Console: sitemind.awni.in`

All rubric-tag chips (Innovation / Business Impact / Technical Excellence / Scalability / UX) are
assigned per-slide in `.slide-meta` and were preserved/re-assigned appropriately across rewrites —
check the live file if you need the exact current per-slide tag assignment. Each slide now also
carries a `.stage-tag` (see "Stage tags" section above) — three independent label systems coexist:
stage tag, technical eyebrow, and rubric chips.

## QA workflow used after every edit round (repeat this for future edits)

1. Serve the repo from its **root** (not `docs/deck/`) so `../../ui_images/*.png` resolves:
   ```bash
   python3 -m http.server 8791 --bind 127.0.0.1 &
   ```
2. Use Playwright MCP tools to drive a real Chrome instance:
   - `browser_navigate` → `http://127.0.0.1:8791/docs/deck/pitch.html`
   - `browser_press_key` with `ArrowDown` to advance one slide at a time (exercises the deck's own
     keyboard-nav script, not just a raw scroll).
   - `browser_take_screenshot` after each slide, then `Read` the PNG to visually inspect.
   - `browser_console_messages` if anything looks broken, to check for JS errors.
3. Grep-verify structural integrity after any content edit:
   ```bash
   grep -c '<section class="slide"' docs/deck/pitch.html   # should equal 7 (the hero slide has class="slide hero", an extra word after "slide" breaks the exact-quote match)
   grep -c '<section' docs/deck/pitch.html                   # should equal 8 (total slide count)
   grep -c '</section>' docs/deck/pitch.html                 # must equal 8, matching the total above
   grep -n "—" docs/deck/pitch.html                          # should be empty — no em dashes per house style
   ```
4. Clean up: delete all screenshot PNGs written to the repo root, and kill the http.server
   (`pkill -f "http.server 8791"` — note this reliably returns an ambiguous exit code ~144 in this
   environment because the compound command kills itself; verify actual cleanup with
   `ps aux | grep "[h]ttp.server 8791"` returning empty, not by trusting the exit code).

### A real bug this workflow caught

The slide-5 overflow bug (see "Known bug class" above) was only caught because this workflow
takes an actual screenshot of every slide after every edit, rather than just eyeballing the raw
HTML diff. Do not skip the visual pass even for what looks like a small content tweak — a single
added sentence was enough to trigger a real, non-obvious layout collision.

## If you're picking this up fresh

- Read `docs/deck/pitch.html` in full before editing anything — this doc is a snapshot/summary, the
  file is the source of truth.
- Never touch `docs/deck/index.html`.
- Reuse the component table above before inventing new CSS.
- Run the full QA workflow (screenshot every slide) after any content change, not just a lint/grep
  pass — the overflow bug class described above is real and non-obvious from source alone.
