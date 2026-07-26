# Phase 1 audit — consolidated findings

> Produced 2026-07-25 by 6 parallel audit agents (A1–A6) against the **live running app**
> (backend `:8000`, frontend `:3000`), not from documentation.
> Individual reports: `A1-compliance-copilot.md`, `A2-schedule-supply-timeline.md`,
> `A3-commissioning-kg-overview.md`, `A4-retrieval.md`, `A5-sponsor-tracks.md`, `A6-evals-data.md`.
>
> **Rule applied throughout: live code and live responses beat any document.**

---

## 1. Headline verdict

**The app is substantially real.** The "it looks hardcoded" worry was wrong about the backend
(7,869 lines, ~50 routes, only 2 fixture files) and right about exactly one page (Copilot).

**The core thesis survived its hardest test.** Agent A5 verified there is **no import path from
`llm.py` into `checks.py`/`rule_eval.py`** — the pass/fail verdict is computed by plain Python at
`compliance.py:299`. LangGraph is confined to `copilot_agent.py`; all 5 of its tools are read-only.
*"The LLM never computes a verdict"* is true and provable on demand.

**The headline metric reproduces exactly.** Live run of `run_eval.py`:
`n=41 · SiteMind acc=1.0 · hallucination=0.0 · naive baseline acc=0.5854`.

**What's actually wrong is not the code — it's that several finished features are switched off,
mislabelled, or silently degraded.** Four of the six demo beats are affected.

---

## 2. Demo blockers, ranked

| # | Blocker | Impact | Fix size |
|---|---|---|---|
| 1 | **Solana `/verify` returns `chain_intact: false` for genuinely-anchored records.** A `ConnectTimeout` in the vendored solana-py HTTP client is swallowed and returned as `False`. Frontend renders a red "chain mismatch" badge on valid data. | **Demo beat 4 (the money shot) proves nothing** — tampering changes nothing visible because it is already red. | Code fix, small |
| 2 | **`computed_draft` verdict tier is dead on this deployment.** `COMPLIANCE_RULE_EXTRACTION` unset → defaults off. All 6 demo NCRs return `verdict_tier:"certified"` with `computed_detail`/`extracted_rule` both `null`. Turning it on needs Gemini, which is **currently quota-exhausted** (observed live: a non-fixture Copilot question returned the literal `_fallback_answer()` template). | **Demo beat 3 (the moat) has nothing to show.** | Env flag + quota |
| 3 | **SSE "reasoning trace" is a hardcoded per-param-type string table** (`_reasoning_trace`), never model output — yet the UI badges it **"● live · backend SSE"**, which only reflects that the fetch succeeded. | Integrity risk. The label implies something untrue on the hero page. | Label change |
| 4 | **Knowledge Graph per-node scoping is observably dead.** The graph is genuinely built from real data, but the live dataset is a **single connected component of 37 nodes** — so every `element_id` (real, near-miss, or garbage) returns the identical whole graph. Page copy says "Click a node to trace its links." | Demo trap if a judge clicks. | Data or copy |
| 5 | **Actian is switched off.** Container running, client installed, **6,206 vectors loaded**, parity eval re-run live **5/5 pass** — but `RETRIEVAL_VECTOR_STORE` defaults to `numpy` and nothing overrides it. | Priority-1 sponsor track sitting unused. | One env var |
| 6 | **Contradictory badges on commissioning NCRs.** `commissioning.py`'s `_to_ncr()` never sets `verdict_tier`, so it silently defaults to `"certified"` (`schemas.py:74`) — rendering a green "Certified · pre-vetted" badge beside a red "Cross-source · unverified" citation badge on the same card. | Says "we vetted this" and "we couldn't verify this" simultaneously. | Code fix, small |
| 7 | **Codebook is down.** `standards-service` not running (`:8010`), `CODEBOOK_ENABLED` absent from `.env` → `/api/codebook/*` 404s. Both pages render clean "not enabled" states. | 2 of 11 nav items show nothing. | Start service |

---

## 3. Claims that must never be made

1. **Gemini Vision.** `GEMINI_VISION_ENABLED` exists as a flag with **zero other references anywhere
   in the codebase**. 100% dead code. Never mention it as built.
2. **"Actian is well under the 5,000-vector Community cap."** `docs/gaps.md` says this; the live
   container holds **6,206**. Directly contradicted. Do not repeat until someone establishes which
   tier is actually running.
3. **"There is a local embedding fallback."** `embeddings.py:34-39` hard-raises without `HF_TOKEN`.
   The `openai→hf→local` chain in `embeddings_provider.py` is **dead code** — `sentence-transformers`
   and `torch` are not installed in `backend/.venv`. Semantic search works right now *only* because
   `HF_TOKEN` is set.
4. **"The Telegram bot has been field-tested."** Every component is verified; a real phone round-trip
   has never happened.
5. **"Every citation is independently clickable."** Of 24 `verify_url`s: 20 → archive.org (HTTP 200),
   2 → cea.nic.in (HTTP 200), **2 → bis.gov.in (HTTP 302, homepage only)**. Those last two are
   weaker citations and should be described as such.
6. **"Runs fully offline with no API key"** — true only for the deterministic pillars (Compliance,
   Commissioning, Schedule, Supply Chain, Timeline, Cost). Any semantic-retrieval feature needs
   `HF_TOKEN` + network.

---

## 4. Verified real (safe to claim)

- **Compliance verdicts** — 17 hand-vetted deterministic rules in `checks.py`; no LLM path into them.
- **Eval suite** — exact count is **19 in `backend/eval/` + 3 in `standards-service/eval/` = 22**
  (docs say 21 / "18+3", both wrong). **21 passed live at 100%**; 1 (`run_codebook_tools_eval.py`)
  CANNOT-RUN because `:8010` was down — it fails closed cleanly (exit 2), not broken.
- **CPM** — real NetworkX forward/backward pass; proved by advancing the simulated clock 30 days
  (5 new at-risk activities appeared) and resetting cleanly. Cache invalidation genuinely fires
  (`clock.py:44-52`); at-risk count moved 6 → 13 → 6 across advance/reset.
- **Supply chain** — delay propagation, root-cause and alternative-viability are real arithmetic
  over a **disclosed** point-in-time snapshot (`/api/supply-chain/meta` states this).
- **Timeline** — pure aggregation, zero new judgement. `evidence_links.py` cross-links are real
  shared-key matches (wbs_id substring, TF-IDF cosine fallback), not hardcoded pairs.
- **Mitigation** — the "3-agent" claim is legitimate: 3 functions over 3 disjoint data sources,
  coordinated by a 3-line collector with no hidden ranking.
- **Commissioning** — computed per-row; all 6 sample rows hand-verified against
  `commissioning_clauses.json`. ASHRAE caveat disclosed unconditionally in the UI.
- **Overview** — stat tiles, "Next decisions", and ROI are computed, not constants.
- **Retrieval** — `structural_standard_codes` = **17 docs / 6,206 chunks**, counted live via API
  plus 17 `.md` files counted on disk. (The `0 docs · 0 chunks` in the old screenshot is **stale** —
  the corpus built empty before the source files were copied in-repo.)
- **Solana anchoring** — 2 **real devnet transactions** independently confirmed via direct RPC;
  memo bytes match `content_hash` exactly. (Only the read-back verify is broken — see §2.1.)
- **MongoDB ledger idempotency** — proven live: `POST /api/audit/seed` called twice, 0 new records
  both times, count stayed at 13. Currently on the **JSONL fallback** (`MONGODB_URI` unset).
- **ElevenLabs** — bot process running; real Scribe STT + multilingual TTS in correct Ogg/Opus.
- **Data provenance** — every synthetic file carries its own `_note` admitting synthetic status.
  `monsoon_window.json` is **genuinely real IMD data**. All project PDFs verified as real multi-page
  documents. `gen_synthetic.py` only *reads* `clauses.json`, never writes it — re-running it cannot
  reintroduce bad URLs.
- **`gaudi.local` landmine is FIXED.** All 24 `verify_url`s resolve to real hosts. Zero `gaudi.local`
  references anywhere in data/app/frontend.

---

## 5. Stale claims to correct (do not carry forward)

| File | Claim | Reality |
|---|---|---|
| `docs/features.md` | fetch timeout "3.5s" | **90s** (`frontend/lib/api.ts:66`, raised for Render cold-starts) |
| `docs/features.md` | Telegram bot calls `/api/copilot/ask` | calls **`/api/copilot/chat`** |
| `docs/features.md` §14 | "21 scripts (18 + 3)" | **22 (19 + 3)**; `run_actian_parity_eval.py` is undocumented entirely |
| `docs/features.md` §14 | 6 `n_cases` counts | mismatch live output (e.g. electrical claimed 30 → actual **32**; cross-corpus claimed ~20 → actual **26**) |
| `docs/features.md` | "13/24 verify_urls dead (gaudi.local)" | **all 24 resolve**; landmine fixed |
| `docs/features.md` §2 | — | never mentions the tiered-verdict system at all, even as "built but off" |
| `docs/ARCHITECTURE.md` | lines 16 & 111 say `manak_structural` | renamed to **`structural_standard_codes`**; code is clean, docs drifted |
| `.claude/CLAUDE.md` | `gaudi.local` dead-link warning | now stale — the links are fixed |
| `docs/gaps.md` | Actian "well under 5,000 vectors" | live container holds **6,206** |

---

## 6. Eval credibility — the attack a technical judge will make

Confirmed from the scripts' own docstrings: `run_eval.py` and `run_electrical_eval.py` **admit**
their 100% score is "trivially… meaningless" when graded against thresholds the code itself
implements. Most of the other 9 rule-arithmetic scripts have **no baseline comparison at all**.

**The defensible framing:** the informative signal in `run_eval.py` is the **baseline gap
(58.5% → 100%)**, not the headline accuracy. The strongest scripts in the suite are
`run_timeline_eval.py` and both `run_cross_corpus_eval.py` copies, which test against real derived
data with full (not sampled) coverage. Say this before a judge says it for you.

---

## 7. Coverage confirmation (§2.4 exit criteria)

- [x] All 6 audit files written
- [x] All 12 frontend pages covered exactly once across A1–A4
- [x] All ~50 backend routes accounted for
- [x] All 5 sponsor tracks have a status verdict (§2 table + §3)
- [x] Consolidated stale-claim list (§5)

---

## 7a. Fixes applied 2026-07-25 (user-approved, post-audit)

All four verified live after the change, not just written.

| # | Fix | Verification |
|---|---|---|
| 1 | `RETRIEVAL_VECTOR_STORE=actian` added to `backend/.env` | `/api/health` → `vector_store:"actian"`; a real query returned the correct IS 456 Cl 26.4.2.2 chunk (score 0.70) from 6,206 vectors |
| 2 | SSE badge relabelled `● backend SSE · deterministic trace` (+ explanatory `title`) in `frontend/app/compliance/page.tsx` | Confirmed rendered in a real browser run |
| 3 | `commissioning.py::_to_ncr()` now sets `verdict_tier` explicitly; `NCRCard.tsx` suppresses the tier chip when `source_type == "cross_source_unverified"` (never for a DRAFT chip) | Live ingest → 3 NCRs `tier=certified, src=cross_source_unverified`; compliance page still shows "Certified · pre-vetted" on all 6 NCRs (no regression) |
| 4 | `notary.verify_anchor()` now tri-state (`True`/`False`/`None`) with a 30s timeout and one retry; `/verify` returns a new `chain_status`; audit page renders amber "chain unverifiable" instead of red | **Both anchored records now return `chain_status:"verified"` — they returned `false` before.** The money shot works. |

**Root cause of #4, for the record:** the RPC call simply needed longer than the default timeout.
The old code swallowed the resulting `ConnectTimeout` to `False`, which the UI painted as tamper
evidence. A verification mechanism that cries tamper on network latency is worse than none, because
it trains people to ignore the red badge.

## 7b. ⚠️ Feature found AFTER the audit: Spatial Compliance

Not covered by agents A1–A6 (they were scoped to files that existed in the documented inventory).
Discovered via `git status` while reviewing the fix diff.

- **Spec:** `docs/superpowers/specs/2026-07-25-spatial-compliance-design.md` — dated today, marked
  "approved, ready for implementation".
- **Code present, uncommitted:** `backend/app/spatial/` (extract, layout, params, schemas),
  `backend/app/agents/checks_spatial.py`, `backend/app/agents/floor_plan.py`,
  `frontend/components/FloorMap.tsx`, `backend/data/standards/spatial_clauses.json` +
  `nbc_tables.json`, a sample layout DBR (`.md` + `.pdf`), and 4 test files.
- **Status: built but NOT LIVE.** `grep spatial backend/app/main.py` returns nothing — the router is
  not mounted. `backend/eval/run_spatial_eval.py` does **not exist**, despite the spec requiring it.
- **Tests: 76 passed** across the 4 spatial test files.
- **What it does:** extracts spatial params (room sizes, clearances, exits, travel distances) from a
  layout DBR, computes 6 deterministic Python rules against 6 verbatim CEA/NBC clauses, and pins
  each finding onto a rendered 2D floor map.

**Why this matters for the pitch:** it is the most visually demonstrable thing in the repo (a floor
plan with failures pinned on it), it extends the same "cited + computed" spine, and it closes the
NBC 2016 fire/egress gap the README lists under Roadmap. It is also the only feature whose own spec
demands an eval that was never written — do not claim a number for it.

**Decision required from the user** before it enters any document or the demo.

## 8. Housekeeping flagged, not acted on

- `backend/.env` contains **live, non-placeholder API keys** (HF, Gemini, Langfuse, Solana). This is
  why network-dependent evals passed live. `.gitignore` coverage was verified in a prior session,
  but the repo still has **zero commits** — confirm ignore rules hold before the first one.
- The two retrieval stacks (`backend/app/retrieval/` and `standards-service/app/retrieval/`) are
  structurally identical forks that have genuinely diverged (different provenance-tag strings), yet
  now resolve to the same physical corpus directory. Technical debt; document, don't fix now.
