# SiteMind — feature inventory (as of 2026-07-25, HexaFalls additions folded in)

Grounded snapshot of every page and feature actually built, for a later critical pass (what's
weak, what's demo theater, what's missing). Not a spec, not a roadmap — a mirror of current code.
Compiled by reading every frontend page and every backend router directly; see file paths inline.

---

## 1. Command Center (`/`, `frontend/app/page.tsx`)
ROI/status dashboard aggregating every pillar. Read-only, no inputs.
- Machine-scale strip: docs read, clauses checked, cross-refs found, conflicts surfaced.
- "Next decisions" — ranked action list merging supply-chain + schedule risks (client-side ranking only).
- "Latest on site" — top-5 most recent Timeline events.
- Cost-at-risk card — total INR + component breakdown, hover tooltips.
- Cumulative impact — issues caught, engineer-hours saved, rework avoided (INR).
- Per-pillar ROI breakdown with links out.
- 3-card row: open NCRs by severity, schedule health, recent submittals/RFIs.
- Backend: `GET /api/overview`, `/api/cost-risk`, `/api/schedule/risks`, `/api/documents`, `/api/timeline`, `/api/supply-chain/risks`.

## 2. Compliance Agent — HERO (`/compliance`, `backend/app/agents/compliance.py`)
Reads a Design Basis doc, extracts params with source spans, checks each against a real cited
IS clause, emits NCRs + a senior ADVISORY.
- Document register with status legend, upload (PDF/DOCX/TXT/MD, click-to-browse).
- Extracted-parameters preview after upload.
- Live SSE-streamed agent reasoning trace (falls back to simulated stream if backend unreachable).
- Results: coverage-by-domain chips, overlapping-requirements panel (multi-clause governance),
  NCR cards, Action Brief cards (finding → linked RFI/schedule activity → owner action),
  conforming-parameter list.
- Backend: `POST /ingest` (real extraction, no mock fallback), `POST /check/stream` (SSE),
  `POST /check` (non-streamed), `GET /action-brief/{document_id}`.
- Decision logic is deterministic Python (`app/agents/checks.py`) against real clauses; LLM only
  writes prose and is handed the clause to cite.

## 3. Spatial Compliance (`/compliance` — "Floor Plan" panel, `backend/app/agents/floor_plan.py`)
A second capability inside the Compliance pillar (spec:
`docs/superpowers/specs/2026-07-25-spatial-compliance-design.md`), not a new page. Reads room
sizes, equipment clearances, exits, and egress facts out of a Design Basis / layout narrative,
computes pass/fail in deterministic Python against real CEA/NBC clauses, and renders a 2D floor
map with NCRs pinned onto the geometry that failed. The existing scalar Compliance path
(`ingest.py` → `checks.py`) is untouched.
- Upload the same file types as `/api/compliance/ingest` (`.pdf .docx .txt .md`). Demo document:
  `backend/data/project_docs/live_upload_samples/DC1-05-DBR-0007-R1_Layout-Design-Basis.md` — a
  synthetic-but-representative Chennai 48 MW Tier-III layout narrative that parses fully via regex,
  no API key, and deterministically produces 2 NCRs, 1 PASS, 2 abstentions, and a server-hall zone
  flagged `not_checked`.
- Frontend: `frontend/components/FloorMap.tsx` (inline SVG, no new npm dependency) + a "Floor Plan"
  panel in `frontend/app/compliance/page.tsx`, rendered only when `has_spatial_data` is true.
- Backend: `POST /api/compliance/floor-plan` — PERCEIVE (`app/spatial/extract.py`, regex-first,
  reuses `ingest.py`'s sentence splitter and `llm_extract.py`'s span-verification gate) → LAYOUT
  (`app/spatial/layout.py`, deterministic shelf packing — same spec in, byte-identical geometry out,
  every time) → DECIDE (`app/agents/checks_spatial.py`, deterministic Python thresholds) → respond.
  Never raises on a document with no spatial content — returns `has_spatial_data: false` with a
  plain-language `reason`.
- **The stated-vs-inferred rule (the honesty mechanic):** a room's dimensions are only ever
  `"stated"` (an unstated room isn't drawn to scale — a hatched, dimmed nominal 6×6 m placeholder
  instead). A room's position is `"stated"` only when the document gives an explicit room-to-room
  relation the layout engine consumed ("the LV Switchroom sits immediately to the west of Data Hall
  1"); otherwise it's placed by deterministic shelf-packing and marked `"inferred"`. **A check may
  only read a value whose provenance is `"stated"` — never an inferred one.**
- **The 6 checks**, each a Python threshold function anchored to a verbatim-digitised clause
  (`backend/data/standards/spatial_clauses.json` — separate file from `clauses.json` so the existing
  24 clauses and their evals stay byte-identical):
  | check | rule | clause |
  |---|---|---|
  | `SWBD_FRONT_CLEARANCE` | front clearance ≥ 1.0 m | CEA 37(iii)(a) |
  | `SWBD_REAR_CLEARANCE` | rear space < 0.20 m or > 0.75 m | CEA 37(iii)(b) |
  | `SWBD_REAR_PASSAGE` | rear passage ≥ 1.8 m (only when rear space > 0.75 m) | CEA 37(iii)(c) |
  | `EGRESS_DEAD_END` | dead-end corridor ≤ 6 m (educ./inst./assembly) or ≤ 15 m (other) | NBC 2016 4.4.2.2(c) |
  | `EGRESS_TRAVEL_DISTANCE` | travel distance ≤ NBC Table 5 limit for the occupancy | NBC 2016 4.4.2.2(a) |
  | `EGRESS_EXIT_WIDTH` | exit width ≥ occupant load × NBC Table 4 mm/person | NBC 2016 4.4.2.3 |

  Every check abstains (never fails) when a required companion value is missing or its provenance
  isn't `"stated"`. Two checks (`EGRESS_DEAD_END`, `EGRESS_TRAVEL_DISTANCE`) implement a
  determinate-regardless-of-group shortcut: `Room.occupancy_group` has no extraction path in this
  build (the demo doc never states one, and guessing it is forbidden), so when a measured value
  breaches even NBC's most permissive limit for any occupancy the verdict is FAIL regardless of
  group, and when it satisfies even the strictest limit the verdict is PASS regardless — abstention
  is reserved for the genuinely ambiguous band in between.
- **Rule tier:** all 6 rules are "certified" tier (`checks_spatial.py`) — hand-written Python
  thresholds, same as `checks.py`. There is no "computed-draft" spatial tier in this slice.
- **Deliberately NOT checked:** rack/aisle geometry inside the server hall (cold-aisle/hot-aisle
  containment, row spacing) is governed by ASHRAE TC 9.9, which is **not a freely redistributable
  standard** and is not digitised here — the zone is rendered on the floor map for spatial context
  (`not_checked_zones` in the API response, shown as a visible caption, not hidden in a tooltip) but
  never judged, because inventing a threshold against a standard SiteMind can't cite verbatim would
  break the "never invent a clause" rule. See `docs/gaps.md`.
- Eval: `backend/eval/run_spatial_eval.py` — decision accuracy, citation-hallucination rate, and
  abstention correctness across boundary cases for all 6 checks, reported on its own, never blended
  into `run_eval.py`'s or `run_electrical_eval.py`'s numbers.

## 4. Project/RFI Copilot (`/copilot`, `backend/app/agents/copilot.py`)
Cited hybrid-RAG Q&A over project docs/standards, plus "seen-before RFI" detection.
- Chat thread, hoverable `[n]` citation chips, per-answer sources list.
- "Seen before" card when a semantically similar resolved RFI is found.
- Suggestion chips (auto-asks the first on load), "try also" row, explicit abstention disclosure.
- Backend: `POST /ask` — curated fixture match first (keyword + embedding confirm), else hybrid
  BM25+dense retrieval with RRF fusion and an abstention floor; `OFFLINE_MODE` (no LLM key) uses a
  deterministic fallback composer instead of an LLM call for the *prose*.
- Retrieval reality (matters for the "offline" claim): the *dense* half embeds via
  `app/embeddings.py`, which calls `all-MiniLM-L6-v2` on the **Hugging Face Inference API** and
  **requires a free `HF_TOKEN`** — the local torch/sentence-transformers path was removed (512 MB
  free-tier RAM ceiling). So `OFFLINE_MODE` governs only the LLM prose; Copilot/Knowledge Base/
  Codebook *semantic search* (and their eval scripts) still need `HF_TOKEN` + network. The
  deterministic pillars (Compliance, Commissioning, Schedule, Supply Chain, Timeline, Cost) need no
  token at all. Extraction on upload is **regex/heuristic in `ingest.py`, not an LLM**.
- **HexaFalls addition — LangGraph conversational edge** (`backend/app/agents/copilot_agent.py`,
  plan §F2, gated on `COPILOT_AGENT_ENABLED` + a present `GEMINI_API_KEY`): a new
  `POST /api/copilot/chat` endpoint turns this from single-shot Q&A into a multi-turn agent that
  routes across ALL pillars via 5 read-only tools (`search_codebook`, `query_knowledge_base`,
  `get_open_ncrs`, `get_schedule_risk`, `get_supply_chain_status`) and remembers conversation
  context via a LangGraph checkpointer (Mongo-backed if `MONGODB_URI` is set, else stateless
  per-call). This is the ONLY place in the codebase a general agent-orchestration framework is
  allowed to run — it cannot import `checks.py`/`rule_eval.py` and never produces a verdict, only
  routes and phrases already-computed, read-only results. Flag off/no key → falls back to the
  existing single-shot `answer()` untouched; the frontend Copilot page still uses `/ask` by
  default (switching it to `/chat` with a persisted `thread_id` is noted as a future frontend
  enhancement, not yet wired up).

## 5. Schedule & Risk (`/schedule`, `backend/app/schedule.py`)
CPM + leading-indicator rules (not fabricated-data ML), weather/workforce risk factors.
- WBS gantt (baseline vs. predicted-slip overlay, "today" line, hover tooltips) — read-only.
- "Biggest early warning this cycle" hero card.
- Top schedule risks: drivers, downstream activities, project-impact days (re-run CPM),
  3-option Mitigation panel (viable/not-viable + days recovered per option).
- Backend: `GET /gantt`, `/risks` (NetworkX forward/backward CPM pass + 5 leading-indicator rules:
  slipping vendor, progress lag, legacy monsoon proxy, cited IMD monsoon window, cited Pongal
  workforce window), `/methodology` (discloses how each risk input is grounded).

## 6. Project Timeline (`/timeline`, `backend/app/timeline.py`)
Cross-pillar chronological aggregation — explicitly "aggregation only, no new judgment" (banner
shown in-page).
- 5-lane chart (compliance, copilot, schedule, supply_chain, commissioning), day axis, phase
  boundaries, "today" marker, severity-colored dots (jittered on same-day collision).
- Click a dot → SVG connector lines to its linked events (reuses `evidence_links.py`'s real
  shared-key matches) + detail card + "open in {pillar}" link.
- Backend: `GET /api/timeline` — pure aggregation of the other 4 pillars' own outputs.

## 7. Supply Chain Visibility & Risk (`/supply-chain`, `backend/app/supply_chain.py`)
Multi-tier shipment tracking extending schedule's procurement fields. Read-only page.
- As-of-day/date disclosure banner.
- In-app timestamped alerts panel (severity-tiered by days-at-risk/critical-path).
- Leaflet shipment map (site/tier-1/tier-2/at-risk legend, dynamic import, no SSR).
- At-risk shipment cards: root cause (first slipped milestone), linked RFI/schedule activity,
  recommended alternative or an explicit "no viable alternative" message.
- Full tracked-shipments table: item, tier-1 supplier, stage, required-by, projected arrival,
  status, equipment-spec compliance chip (IS 8623-1 LV switchgear voltage check).
- Backend: `GET /shipments`, `/shipments/{id}`, `/risks`, `/alerts`, `/meta`,
  `/equipment-spec-ncrs`, `/map`. Delay propagation, root-cause attribution, and alternative
  viability are all computed, not asserted.

## 8. Commissioning QA Copilot (`/commissioning`, `backend/app/commissioning.py`)
Cooling-only slice (electrical/fire deferred — see project instructions, corpus gap).
- Upload a real CSV cooling test log (click-to-browse).
- Persistent corpus-limitation disclosure (ASHRAE TC9.9 envelope is cross-source compiled, not
  manak-verified — ASHRAE is paywalled).
- Summary counts (record/pass/within-allowable/fail/not-checkable) + link to an HTML quality package.
- Findings-with-NCR list, other-test-records list (each with cited-clause box).
- Backend: `POST /ingest` (per-row deterministic PASS / OUT_OF_RECOMMENDED_BUT_WITHIN_ALLOWABLE→
  NCR MEDIUM / FAIL→NCR HIGH / NOT_CHECKABLE, never crashes on a bad row), `GET
  /quality-package/{run_id}` (JSON), `/quality-package/{run_id}/html` (standalone report).

## 9. Codebook (`/codebook`, `standards-service` via MCP)
SiteMind's backend as an MCP *client* of Codebook (standards-service, port 8010) — browser never
talks to Codebook directly.
- Availability gating (checking/disabled/unreachable, explained in-page).
- Indexed-corpora panel (refresh button).
- Search-standards panel (query + optional corpus filter).
- Clause lookup panel (document_id + chunk_id → verbatim text).
- Document-check panel (upload a file + corpus name → per-sentence CONFORMS/NON_CONFORM/
  NEEDS_REVIEW).
- Backend: `GET /corpora`, `/search`, `/clause/{doc_id}/{chunk_id}`, `POST /check`,
  `/check-upload` — all proxy Codebook's 4 MCP tools (`list_corpora`, `search_standards`,
  `get_clause`, `check_document_against_corpus`), all return prose text blocks by design (MCP has
  no structured_output in the pinned SDK version).

## 10. Codebook Console (`/codebook/console`, new 2026-07-12)
Admin/browsing UI on Codebook's plain REST retrieval API (structured JSON, not MCP prose) — built
after establishing Codebook was already a separate service and already renamed (no new service,
no new brand needed; see `docs/codebook_console.md`).
- Corpora list, expandable rows, lazily-loaded per-corpus document list.
- Provenance badges: `codebook_verified`/`sitemind_indexed` → "Internal verified standard"
  (green); `company_uploaded` → "External / uploaded" (amber); unknown → gray. Per-document, not
  just per-corpus, since a corpus can be mixed.
- Add-a-document panel: corpus-name input (datalist suggestions) + drag-and-drop upload.
- Backend: `GET /console/corpora`, `/console/corpora/{name}/documents`, `POST /console/upload` —
  `httpx`-based REST proxy (bypasses MCP entirely) to standards-service's own `/api/retrieval/*`.

## 11. Knowledge Base (`/knowledge-base`, `backend/app/retrieval/` — flag-gated)
Independent standalone retrieval package (`RETRIEVAL_ENABLED`, default off) — predates Codebook,
still live because 2 eval scripts (`run_retrieval_eval.py`, `run_cross_corpus_eval.py`) import it
directly. Upload arbitrary docs into a searchable corpus, ask cited questions.
- Corpus selector (text input + datalist + clickable chips showing doc/chunk counts).
- Drag-and-drop upload panel.
- Ask-a-question panel — citations show source-type badge, score, filename/breadcrumb, verbatim
  quoted text; explicit abstention message when nothing clears the retrieval floor.
- Backend: `GET /corpora`, `POST /upload`, `POST /query`.

## 12. Knowledge Graph (`/graph`, `backend/app/kg.py`)
Equipment → spec → standard → RFI connections from real structured data (NetworkX, no LLM/embeddings).
- SVG subgraph, 4 columns (Equipment/Spec/Standard/RFI), curved labeled edges.
- Click a node → highlight its neighborhood, dim the rest; inspector side panel; "how this is
  built" explainer panel.
- Backend: `GET /api/kg/{element_id}` — builds an in-memory graph from `applicable_checks()` and
  shared-ID RFI references, returns the requested node's neighborhood (or whole graph on no match).

## 13. Audit Ledger (`/audit`, `backend/app/audit.py` + `audit_api.py` — HexaFalls plan §D/E)
Every finalized compliance decision recorded once, append-only, via a content hash computed over
its non-prose fields (severity/citation/values — AI-written prose is excluded from the hash on
purpose, since it legitimately reword itself between live LLM calls even at temperature 0).
- Table view: recorded time, pillar, item, severity, content-hash prefix, Solana anchor status
  (clickable Explorer link once anchored), per-row Anchor/Verify buttons, "Anchor all pending".
- Backend: `GET /api/audit`, `/api/audit/{id}`, `POST /api/audit/seed` (idempotent — re-running
  never duplicates), `POST /api/audit/{id}/anchor`, `/anchor-pending`, `/{id}/verify`.
- Mongo Atlas if `MONGODB_URI` is set, else a local JSONL ledger — same idempotency either way,
  never raises into a request. `GET /api/health`'s `audit_backend` field shows which is active.
- **HexaFalls addition — Solana devnet notarization** (`backend/app/notary.py`, plan §E, gated on
  `SOLANA_ENABLED`): anchors a ledger record's content hash via the SPL Memo program (a real
  devnet transaction, zero real-money cost). `/verify` returns both `mongo_intact` (does the local
  record still match its own hash?) and `chain_intact` (does the anchored on-chain hash match the
  record's stored hash field?) — tampering the local record after anchoring shows the striking
  combination `mongo_intact: false` + `chain_intact: true`: proof the record was altered locally,
  while the chain independently proves what the original hash really was, without needing to trust
  SiteMind's own database. `SOLANA_ENABLED=0` (the default) → rows show "Solana disabled," ledger
  still works fully without it.

## 14. Telegram field bot (`telegram-bot/`, standalone service — HexaFalls plan §F1)
A multilingual voice front end for the existing Copilot, reachable from a phone. Not a new backend
route — a pure client of `POST /api/copilot/ask`.
- Text or voice-note input, any of Hindi/English/regional language.
- Voice pipeline: Telegram voice file → ElevenLabs Scribe (STT) → Gemini translation to English (if
  needed) → existing Copilot `/ask` → Gemini translation back → ElevenLabs TTS (`opus_48000_128` —
  confirmed via direct inspection to be a real Ogg/Opus container, exactly what Telegram's
  `sendVoice` requires) → reply as a voice note + text + citation links.
- Same abstention discipline as the desktop Copilot: below the retrieval floor → "No confident
  answer in the project corpus — raising this as an RFI," never a fabricated answer.
- Needs `TELEGRAM_BOT_TOKEN` + `ELEVENLABS_API_KEY` (+ `GEMINI_API_KEY` for translation, optional —
  fails closed to untranslated text/voice if absent or over quota). Run with `cd telegram-bot &&
  ./run.sh`.

---

## 15. Automated eval suite (script count not re-verified this pass — see PROGRESS.md)
Every pillar's correctness claim is a *computed* number from a re-runnable script, not an assertion
(project rule — see `PROGRESS.md` for current pass counts). Run via `python -m eval.run_X_eval`;
each writes a JSON report (`n_cases`, `n_pass`, `accuracy`/precision-recall-F1, `cases`). 19 live in
`backend/eval/` (18 counted at last audit + `run_spatial_eval.py`, 2026-07-25), 3 in
`standards-service/eval/` (2 of which are near-duplicates of a backend script, repointed — see
caveats). None are blended into one score; each pillar reports separately.

**Compliance / extraction**
- `run_eval.py` — structural rule engine (8 checks) + citation-hallucination rate. ~41 hand-built
  boundary cases + naive-keyword baseline comparison, macro-F1/accuracy/confusion matrix.
- `run_extraction_eval.py` — free-text parameter extraction (planted values, correct abstention,
  no fabrication). 14 held-out-phrasing mini-docs incl. 2 adversarial decoys; precision/recall/F1.
- `run_electrical_eval.py` — electrical checks vs. IS 732 (OCR, superseded edition). 30 boundary
  cases; exact-match accuracy.
- `run_equipment_spec_eval.py` — IS 8623-1 LV switchgear spec matching. 12 cases incl. 4
  NOT_APPLICABLE (categories the standard doesn't cover); exact-match accuracy.
- `run_spatial_eval.py` — Spatial Compliance's 6 checks (CEA switchboard clearances, NBC egress),
  boundary-value cases built as flat param dicts (same shape `spatial/params.py::to_params()`
  emits), reporting 3-way decision accuracy (PASS/FAIL/ABSTAIN/NOT_APPLICABLE), citation-
  hallucination rate, and abstention correctness (a blanket-abstain baseline is reported alongside
  so abstention isn't free credit). Reported on its own, never blended into `run_eval.py`'s or
  `run_electrical_eval.py`'s numbers — see `eval/spatial_report.json` for the real numbers.

**Commissioning**
- `run_commissioning_eval.py` — ASHRAE-derived cooling envelope verdicts. 14 boundary cases
  (temp/RH, A1/A2 classes, 2 out-of-scope); exact-match accuracy.

**Supply chain**
- `run_alerts_eval.py` — alert severity tiering + detection-day logic. 11 synthetic cases;
  exact-match accuracy.
- `run_supply_chain_eval.py` — delay propagation, root-cause attribution, alternative viability.
  8 synthetic milestone scenarios; multi-field pass/fail.

**Schedule**
- `run_schedule_eval.py` — leading-indicator rules + CPM re-computation. ~11 cases (7 rule + 4
  synthetic dependency-graph); exact-match accuracy, uses live module constants (not fully mocked).
- `run_weather_eval.py` — IMD monsoon-window overlap/slip arithmetic. 11 synthetic cases;
  exact-match accuracy.
- `run_workforce_eval.py` — Pongal labour-dip overlap/slip arithmetic. 10 synthetic cases;
  exact-match accuracy.
- `run_mitigation_eval.py` — 3 mitigation functions (procurement-alternative, resequencing-float,
  resource-recovery) — the project's one explicit multi-agent claim. 13 synthetic cases; exact
  match on verdict + days-recovered.
- `run_timeline_eval.py` — cross-pillar aggregation traceability (every event id resolves to a
  real source record, phase bands match real `schedule.csv`, links are symmetric). ~20 checks
  against the **live demo dataset**, not synthetic fixtures.

**Cost / impact**
- `run_cost_risk_eval.py` — cost-at-risk arithmetic (delay/expedite/rework components). 9 synthetic
  cases; exact numeric match.
- `run_impact_eval.py` — ROI-ticker composition (hours/₹ saved per pillar). 11 synthetic cases;
  exact match + non-empty basis-string check.

**Copilot / retrieval (backend)**
- `run_copilot_eval.py` — retrieval-floor and seen-before-floor calibration (embeddings). 12 +
  9 hand-labeled queries; threshold-sweep accuracy, reports the deployed floors (0.40/0.35).
- `run_hybrid_retrieval_eval.py` — RRF fusion arithmetic only, cross-checked against an
  independently written reference implementation. 5 synthetic cases; accuracy.
- `run_cross_corpus_eval.py` (backend) — builds/tests 2 real filesystem corpora (17 real IS-code
  files, ~6,200 chunks + SiteMind's own clause JSON). ~20 cases: build-integrity, known-answer
  queries, gibberish abstention, byte-for-byte verbatim-offset integrity over **every** chunk,
  read-only-source proof.
- `run_retrieval_eval.py` (backend) — chunker + RRF + end-to-end ingest/query. ~22 cases across
  3 tiny made-up documents (earthing/fire/canteen — never real standards).

**Codebook / standards-service**
- `run_codebook_tools_eval.py` — drives all 4 MCP tools through a real client session against the
  **live running service** (port 8010) — the only script testing the actual MCP protocol surface,
  not just in-process logic. ~25 cases, every expected value independently pre-verified (REST call,
  grep, or direct function call) before being hardcoded; deliberately covers error paths (bogus
  chunk id/corpus/path), not just happy paths.
- `run_cross_corpus_eval.py` (standards-service) — same logic as the backend script above,
  repointed at the relocated `codebook_structural` corpus.
- `run_retrieval_eval.py` (standards-service) — same logic as the backend script above, repointed
  at the relocated package.

**Eval-suite caveats worth a critical look**
- Several rule-engine evals (`run_eval.py`, `run_electrical_eval.py`) grade the code against gold
  labels derived from the same thresholds the code implements — closer to a regression check than
  independent validation. The informative part of `run_eval.py` is its baseline comparison, not
  the headline accuracy number alone.
- Most test sets are small (n=5–14) and entirely self-authored by whoever wrote the feature —
  "held-out" mostly means different wording, not independent authorship.
- `run_copilot_eval.py`'s deployed retrieval floors are chosen using the same small labeled set
  that evaluates them — risk of overfitting the threshold to the eval's own paraphrase style.
- `run_workforce_eval.py` self-reports the Pongal rule is "dormant" on the real bundled demo data
  (formula proven correct in isolation, never exercised end-to-end against real project data).
- The backend and standards-service copies of `run_cross_corpus_eval.py` and `run_retrieval_eval.py`
  are near-duplicate test code maintained in two places — a fix in one isn't guaranteed to land in
  the other, and inflates the "21 scripts" count somewhat.
- `run_codebook_tools_eval.py` requires a separately running live service and can't run standalone
  in CI — easy for it to silently go stale if that process isn't up when the rest of the suite runs.
- No script backtests a prediction against real historical outcomes (no real project to backtest
  against) — schedule/supply-chain/cost evals all explicitly disclaim this and only prove internal
  arithmetic consistency, not real-world predictive accuracy.
- Strongest scripts in the suite, for contrast: `run_timeline_eval.py` and both
  `run_cross_corpus_eval.py` copies test against real derived/external data rather than hand-picked
  synthetic cases, with full (not sampled) coverage.

---

## Cross-cutting backend-only endpoints (no dedicated page)
- `GET /api/eval/report` — live-verified hallucination rate (every NCR citation re-checked
  against the real clause cache) + precomputed macro-F1/accuracy/confusion matrix from
  `backend/eval/run_eval.py`. Auto-runs the eval script if `report.json` is missing.
- `GET /api/trace`, `/api/trace/{run_id}` — provenance/trace record log.
- `GET /api/clock`, `POST /api/clock/advance`, `/api/clock/reset` — simulated "today" (offset
  clamped 0–60d), clears every downstream `lru_cache` on advance so schedule/supply-chain/
  timeline numbers recompute live. No mock fallback anywhere in this router.

## Cross-cutting frontend conventions
- `lib/api.ts`'s `getJSON`/`postJSON` helpers: 3.5s timeout, silent fallback to bundled mock data
  (`lib/mocks.ts`) on failure, surfaced to callers via a `live: boolean`.
- Upload/ingest/retrieval/codebook endpoints deliberately have **no** mock fallback — they throw a
  typed `*UnavailableError` instead, per the project's "never fabricate a real-file result" rule.
- Citation trust tiers, used consistently across Compliance and Codebook: `codebook_verified` /
  `primary_native_pdf` / `primary_scan_ocr` / `cross_source_unverified` — never silently presented
  as equivalent.

## Known caveats worth a critical look
- Two parallel retrieval stacks exist: the flag-gated `backend/app/retrieval/` (Knowledge Base
  page) and `standards-service` (Codebook + Codebook Console). Not consolidated — kept apart
  because 2 eval scripts still depend on the former directly.
- Codebook Console's frontend interactions (drag-and-drop, expand/collapse) have been code-reviewed
  and endpoint-verified live, but never exercised in an actual browser (no Playwright in this
  environment).
- Commissioning QA is cooling-only; electrical/fire slice is explicitly deferred pending a corpus
  gap (NBC 2016, DG-set testing standard not yet confirmed in Codebook).
- `standards-service` has no on-disk embeddings cache — every process restart triggers a ~7 minute
  blocking rebuild of the 6,206-chunk structural corpus.
- 13/24 citation `verify_url`s flagged as dead in `docs/PS_optimize.md`, not yet replaced.
- "Runs offline, no API key" is true **only for the deterministic pillars** (the Compliance HERO,
  Commissioning, Schedule, Supply Chain, Timeline, Cost). Any *semantic-retrieval* feature (Copilot,
  Knowledge Base, Codebook search) needs a **free `HF_TOKEN`** for MiniLM embeddings via the HF
  Inference API — a free, not paid, key, but a real external dependency. Don't claim the *whole* app
  or *every* eval runs with zero keys. (`copilot.py`'s docstring was corrected 2026-07-22; it had
  still claimed retrieval was "fully offline, no API key".)
