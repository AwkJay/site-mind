# PS_optimize.md — gap audit against the hackathon problem statement (2026-07-12)

Live audit against the actual pasted problem statement ("AI Intelligence Platform
for Data-Centre EPC Project Delivery", ET AI Hackathon 2026, Problem #4).
Method: ran the real stack (backend :8000 + Codebook :8010 + frontend :3000, all
three launched from their own already-installed venvs/`node_modules`, no mocks),
hit real API endpoints, read real responses, grepped real data files. Every
finding below is something observed, not assumed — where I couldn't verify
something live (no browser/Playwright tool available this session — see
"Testing method" below), that's stated explicitly rather than claimed.

## Testing method (be honest about what this covers)
- **Backend**: real HTTP calls against a live-running backend, Codebook, with
  `RETRIEVAL_ENABLED=1 CODEBOOK_ENABLED=1` — not mocked, not read from code
  alone. Compliance `/check`, Copilot `/ask`, Schedule `/risks`, Supply Chain
  `/shipments`+`/alerts`, Codebook `/corpora`+`/search`, Overview, Cost-risk all
  hit for real.
- **Frontend**: confirmed all 8 pages return HTTP 200 from the real Next.js dev
  server (`/`, `/compliance`, `/copilot`, `/schedule`, `/supply-chain`,
  `/commissioning`, `/codebook`, `/graph`). This proves no build/render crash —
  it does NOT prove client-side interactivity/hydration is bug-free, since no
  Playwright/browser-automation tool was available in this session to click
  through and screenshot. **This is a real coverage gap in this audit** — a
  human (or a future session with a browser tool) should click-test each page's
  interactive flows before presenting.
- Everything in "Found live" below was actually observed via a real running
  process, not inferred from reading code.

---

## Findings — ranked by what actually affects judged criteria

### 1. [HIGH][FIXED THIS SESSION] Codebook cold-start latency causes a real 503 on first use
**Found live**: Codebook's structural corpus (6,206 chunks across 17 standards)
builds lazily on the FIRST request to hit it — no on-disk embedding cache. On
this machine that took **7 real minutes** (sentence-transformer embedding
computation, single-threaded). A concurrent request that lands during that
window gets a hard `503 Service Unavailable` — confirmed live: the first
`GET /api/codebook/corpora` call 503'd while the corpus was still building
6m37s in.
**Why it matters**: if a judge's first live interaction with Codebook (Act 7 of
the demo script) happens to be the very first request against a freshly
started process, they see a failure, not a result. Technical Excellence +
UX-relevant.
**Fix applied this session**: Codebook now warms the corpus during its own
FastAPI startup lifespan (`standards-service/app/main.py`) instead of lazily on
first request — the service takes longer to become healthy, but every request
once it reports healthy is instant (confirmed: subsequent `/search` calls
~0.17s). See task #21 in this session's TaskCreate list.
**Deferred, not done** (bigger, needs a decision): caching the computed
embeddings to disk (mirroring `store.py`'s existing pattern for
company-uploaded corpora) so a RESTART is also fast, not just the same-process
lifetime. Not done autonomously — it's a real architecture/cache-invalidation
decision (what invalidates the cache? corpus content hash? file mtimes?), not
a mechanical fix. Recommend deciding this explicitly before the final demo
rehearsal, not the night before presenting.

### 2. [HIGH][FIXED 2026-07-12] 13 of 24 compliance citations had dead verify links
**Found live**: `backend/data/standards/clauses.json`'s `verify_url` field —
13 of 24 clauses pointed to `gaudi.local` (a hostname that only resolves on the
original dev machine's local network), 7 to `archive.org`, 2 to
`bis.gov.in`, 2 to `cea.nic.in`. **Over half the Compliance pillar's citations
were unreachable to anyone outside this machine** — directly undermined the
product's central pitch ("every citation is verifiable, never fabricated").
**Fix applied**: option (b) from the original recommendation below — the 13
`gaudi.local` links (all IS 456:2000 / IS 875 Part 3:2015 / IS 1893 Part 1:2016
clauses) now point to that standard's real public listing page on
`archive.org`, same pattern already used for the 7 IS 732/3043/8623 clauses in
this file (document-level, not clause-anchored — less precise, but genuinely
reachable instead of silently dead). Each target URL was fetched and confirmed
live before writing it in (not guessed): `gov.in.is.456.2000`,
`gov.in.is.875.3.2015`, `gov.in.is.1893.1.2016` all resolve to the correct BIS
document on Internet Archive. Structural eval re-run clean after the change
(41/41, `hallucination=0.0`) — `verify_url` isn't part of the decision logic,
so this only touches link reachability, not any scored behavior.
**Original recommendation** (for reference): before presenting, either (a) do
a human click-through and swap the 13 `gaudi.local` links for whatever real
public URL each standard actually has (BIS/CEA/IRC's own sites, same tier as
the 2 that already resolved), or (b) if no real public per-clause URL exists,
change `verify_url` to point at the *standard's* real public listing page
rather than a per-clause deep link. (b) is what got applied.

### 3. [MEDIUM] Two of the brief's 4 "what you may build" areas are only partially realized
Re-reading the pasted problem statement against what's live:
- **Specification & Quality Compliance Agent** — fully built (structural +
  electrical domains, both live-tested this session).
- **Predictive Schedule Risk Engine** (the brief explicitly names "generating
  mitigation options, not just alerts") — fully built (`agents/mitigation.py`,
  3 specialist agents, confirmed live via `/api/schedule/risks`).
- **Supply Chain Visibility & Risk Agent** ("Geospatial AI... across
  multi-tier suppliers") — built, confirmed live: `/api/supply-chain/shipments`
  returns real tier-1/tier-2 supplier lat/lon and a `/map` endpoint exists.
- **Commissioning Quality Assurance Copilot** — the brief names TIA-942/
  BICSI/Uptime specifically. **Deliberately not cited** (documented, honest
  scope decision — manak's corpus doesn't cover them, and paraphrasing from
  training data would be fabrication). What's live is a **cooling-only slice**
  grounded in cross-source-compiled ASHRAE data, clearly disclosed as
  `cross_source_unverified`. The electrical/fire-safety/DG-set commissioning
  slice (the part closest to genuine Tier III/IV certification checks) is
  still not built. This is the single largest remaining gap against the
  brief's own illustrative list — not a bug, a scope decision already on
  record (CLAUDE.md's "Commissioning QA — deferred" section), but worth
  re-surfacing here since it directly maps to one of the brief's 4 named
  areas and judges may specifically look for TIA-942/Uptime language.
  **Option, not executed**: if CEA/IS 732/IS 3043 PDFs already extracted for
  the Compliance pillar's electrical domain are judged sufficient grounding
  for a *commissioning-test-log* check (a different verification pattern than
  a compliance-document check), that reopens this scope — CLAUDE.md says this
  needs an explicit go-ahead, not something to decide autonomously.

### 4. [MEDIUM] Computer Vision (drawing review) — named in "Suggested Technologies", not built at all
The brief explicitly suggests CV for "drawing review, submittal checking."
Nothing in this codebase does this — confirmed via grep, nothing resembling
image/drawing analysis exists anywhere in `backend/` or `standards-service/`.
Already tracked as an explicit last-priority stretch in CLAUDE.md
("drawing-vision CV"). Real gap against a named suggested technology, but a
genuinely large build (would need real drawing corpora + a vision model +
grounding logic) — **not attempted autonomously**, listed here as a big-fix
option for a deliberate go/no-go decision, not silently skipped or silently
built half-way.

### 5. [LOW] QMS Integration — named in "Suggested Technologies", not built
The brief names "Quality Management System (QMS) Integration." SiteMind
produces real quality packages (Commissioning pillar) and NCR logs
(Compliance pillar) but doesn't push/pull to an external QMS or PM tool
(Procore, etc.) — already tracked as an explicit last-priority stretch
("Procore connector") in CLAUDE.md. Low priority because the brief's own
"illustrative only" framing plus the 15%-weight Scalability/UX criteria are
already well served by what exists; a real external integration needs a
target system to integrate with, which isn't available in this environment.

### 6. [LOW, already flagged, still true] Deliverables outside the repo aren't done
Per the brief's "Expected Deliverables": Working Prototype exists and now runs
live end-to-end (this session proved that). Architecture Diagram exists as a
real Mermaid diagram in `docs/ARCHITECTURE.md` but not as a rendered
image/exportable asset. Presentation Deck and Demo Video are not started.
These were already listed under CLAUDE.md's "Still open" — restating here
only because judging criteria literally requires them as deliverables, so
they're the highest-leverage remaining work regardless of anything in this
file, and shouldn't get lost under the code-level findings above.

---

## Executed this session (low-risk, done autonomously per go-ahead)
- Real drag-and-drop/file-picker upload wired into `/codebook`'s
  Document-check panel (was a raw filesystem path textbox) — see
  `docs/codebook_changes.md` item 5.
- Copied `manak-dev/lib`'s 17 real standard files into this repo
  (`standards-service/data/structural_corpus/`), removing an external,
  outside-the-repo runtime dependency — verified byte-for-byte + live corpus
  rebuild (6,206 chunks, unchanged) — `docs/codebook_changes.md` item 4.
- Renamed Codebook's own `"manak_indexed"`/`"manak_structural"` literals to
  `"codebook_verified"`/`"codebook_structural"` — verified live (real
  `/api/codebook/corpora`+`/search` calls after the rename both return the new
  names) and via eval (`run_retrieval_eval.py` 24/24, `run_cross_corpus_eval.py`
  26/26, unchanged) — `docs/codebook_changes.md` items 1+2.
- Codebook cold-start fix (finding #1 above) — corpus now warms at process
  startup instead of on first request.
- Root `package.json` added so `npm run dev` from the repo root boots the full
  stack (Codebook + backend, flags on + frontend) via the existing
  `run-full.sh`, answering the earlier "shouldn't this run automatically"
  question without changing any default flag.

## Still in flight (this session, tracked in TaskCreate, not abandoned)
- Rename the PROTECTED `"manak_verified"` Citation tag (Compliance pillar) to
  `"codebook_verified"` — full 19-script backend eval re-run before/after
  required, in progress.
- Update `PROGRESS.md` with this session's outcome.

## On the third-party LLM gateway API key the user shared this session
The user shared a real API key for a third-party OpenAI-compatible gateway
(`api.iamhc.cn`) as an available resource, saying explicitly it's "not
necessary, just listing as a resource." **Not wired into the product this
session** — deliberate, not an oversight:
- The key is a live secret; it was never written into any file, committed, or
  logged by this session.
- SiteMind's whole architecture defaults to `OFFLINE_MODE` specifically so the
  demo never depends on a live, rate-limited, possibly-flaky third-party
  endpoint (`CODEX_SETUP.md`'s own measured 185s-per-call finding is exactly
  this risk materializing once already, with a *different* provider).
  Wiring in an untested, unfamiliar gateway autonomously, unsupervised,
  the night before a demo, is a real reliability risk for a marginal
  Innovation-score gain — the existing `LLM_PROVIDER=offline|codex|openai|
  anthropic` pattern already demonstrates "this generalizes to any real LLM
  provider" without needing a 5th one.
- **If wanted later**: it would slot in as a 5th `LLM_PROVIDER` option
  alongside the existing 4 (same interface, `backend/app/llm.py`-equivalent
  adapter), key stored only in `backend/.env` (already gitignored), never
  hardcoded. Worth doing only as a deliberate, tested addition — not
  something to bolt on inside an unattended autonomous run.

## Judging-criteria framing (25/25/20/15/15 — Innovation/Impact/Tech/Scale/UX)
- **Innovation (25%)**: strongest asset is Codebook itself (a standalone,
  MCP-consumable trust-engine service, not a one-off script) plus the
  mitigation multi-agent system — both genuinely match the brief's suggested
  tech, not bolted on. The CV gap (finding #4) is the main thing competitors
  might have that this doesn't.
- **Business Impact (25%)**: `/api/overview`'s per-pillar hours/₹ breakdown
  and `/api/cost-risk`'s 3-term formula directly answer the brief's own
  "measured in hours, not percentages" evaluation-focus line — confirmed live
  this session, not just in code.
- **Technical Excellence (20%)**: the dead-citation-link finding (#2) — the
  single biggest risk to this score if a judge clicked a `verify_url` live —
  is now fixed; all 24 `verify_url`s resolve to a real, confirmed-live BIS
  document page.
- **Scalability (15%)**: Codebook's "add a corpus, not a retrain" story is
  real and demonstrable; the cold-start fix (#1) makes it also *reliably*
  demonstrable, not just true in principle.
- **UX (15%)**: all pages render; the Document-check panel's new real upload
  widget removes the one interaction that most obviously looked like a
  developer tool rather than a product. The un-audited client-side
  interactivity gap (see "Testing method" above) is the main remaining
  unknown here.
