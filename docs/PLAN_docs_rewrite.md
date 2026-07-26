# PLAN — Feature documentation + pitch rewrite

> **Written 2026-07-25. Executor: a fresh Claude Code session (claude-sonnet-5 for subagents).**
> This plan is self-contained. You do not need the conversation that produced it.
> Read §0 and §8 before touching anything.

---

## §0 — Locked decisions (do NOT re-derive or re-litigate these)

### 0.1 The positioning spine
Every document produced by this plan derives from this. It was debated and approved. Use it verbatim.

- **0.1.1 Category** — SiteMind is an **assurance layer**, not an "AI platform".
  It sits *beside* the system of record (Procore / Aconex / Autodesk Construction Cloud),
  it does not compete with it.
- **0.1.2 UVP (one line)** —
  > SiteMind turns an engineering judgment into evidence: every pass/fail carries the clause it was
  > decided under, the sentence it was read from, the arithmetic that produced it, and a hash anyone
  > can check. No AI verdicts, ever.
- **0.1.3 The three words** — **Cited. Computed. Notarized.**
- **0.1.4 Buyer** — whoever carries *liability*, not whoever builds. In rank order:
  owner's engineer → PMC → third-party quality auditor → lender's technical advisor.
  These people pay humans per-document to do exactly this today.
- **0.1.5 Why now** — LLMs made document review cheap and simultaneously made it *inadmissible*.
  Every competitor ships "AI flagged this." Nobody ships a decision you can defend to a regulator.
  That gap is the product.
- **0.1.6 Demo hierarchy** (4 beats, in order):
  1. Compliance run → NCR with clause + source span *(the hook)*
  2. Click the clause → in-app verbatim source text *(proof it isn't invented)*
  3. Verdict tier: `certified` vs `computed_draft` *(proof of the moat)*
  4. Audit ledger → anchor → tamper → Verify goes red *(the money shot)*
- **0.1.7 Everything else** (schedule, supply chain, commissioning, KG, KB, Codebook, Telegram)
  gets **one slide** as "what the same evidence spine extends to." Cut from the *pitch*, **not**
  from the app.

### 0.2 Sponsor tracks — fixed priority order
1. **Actian VectorAI DB**
2. **Gemini API**
3. **Solana**
4. **MongoDB**
5. **ElevenLabs**

This order drives section order, slide order, and how much space each gets.
(Revised 2026-07-25 by the user — supersedes an earlier ordering that had ElevenLabs 2nd.
File names under `docs/features/tracks/` must match this order: `1-actian`, `2-gemini`,
`3-solana`, `4-mongodb`, `5-elevenlabs`.)

**Presentation constraint:** each track must be explainable to a non-technical judge in
**≤2 sentences** — what it does and why it had to be there. Simple over complete.

### 0.3 Non-goals — DO NOT DO THESE
- **0.3.1** Do **not** change `backend/app/agents/copilot.py`. The fixture-first path at
  `copilot.py:280-290` is known and deliberate for now. Document it honestly; do not fix it.
- **0.3.2** Do **not** change the compliance page or `compliance.py`.
- **0.3.3** Do **not** build the "Evidence Record" view. Deferred.
- **0.3.4** Do **not** pre-seed demo data / change empty states.
- **0.3.5** Do **not** redesign the UI. It is good. Leave it alone.
- **0.3.6** Do **not** commit or push unless explicitly asked.
- **0.3.7** This plan produces **documentation only**, with ONE approved exception — see 0.4.

### 0.4 Approved code changes (2026-07-25, after the Phase 1 audit)
The audit found 7 demo blockers (`docs/features/_audit/00-CONSOLIDATED.md` §2). The user approved
fixing **only these four**; everything else stays documentation-only.
1. Flip `RETRIEVAL_VECTOR_STORE=actian` — priority-1 sponsor track was idle despite a healthy
   container and a passing 5/5 parity eval.
2. Fix the SSE reasoning-trace badge label — it reads "● live · backend SSE" over a hardcoded
   string table. Change the label, keep the feature.
3. Fix `commissioning.py::_to_ncr()` silently defaulting `verdict_tier` to `"certified"`, which
   renders a green "Certified · pre-vetted" badge beside a red "Cross-source · unverified" one.
4. Fix `/api/audit/{id}/verify` returning `chain_intact: false` for genuinely-anchored records
   (a `ConnectTimeout` swallowed to `False` in the Solana RPC client).

**Not approved / still blocked:** turning on `COMPLIANCE_RULE_EXTRACTION` (needs live Gemini, quota
exhausted), the Knowledge Graph single-component issue, and starting `standards-service`.
Document all three as known gaps.

---

## §1 — Deliverables (exact file tree)

```
docs/
├── features.md                          # REWRITTEN: short index only, ~80 lines
├── features/
│   ├── 00-architecture-map.md           # NEW: all mermaid diagrams + routing map
│   ├── 01-compliance.md                 # NEW  (HERO)
│   ├── 02-copilot.md                    # NEW
│   ├── 03-schedule.md                   # NEW
│   ├── 04-supply-chain.md               # NEW
│   ├── 05-commissioning.md              # NEW
│   ├── 06-timeline.md                   # NEW
│   ├── 07-knowledge-graph.md            # NEW
│   ├── 08-knowledge-base.md             # NEW
│   ├── 09-codebook.md                   # NEW (page + console together)
│   ├── 10-audit-ledger.md               # NEW
│   ├── 11-overview.md                   # NEW
│   ├── 90-evals.md                      # NEW: migrated from current features.md §14
│   ├── 91-real-vs-hardcoded.md          # NEW: the honesty ledger (see §3.4)
│   └── tracks/
│       ├── 1-actian.md                  # NEW
│       ├── 2-elevenlabs.md              # NEW
│       ├── 3-solana.md                  # NEW
│       ├── 4-gemini.md                  # NEW
│       └── 5-mongodb.md                 # NEW
├── HEXAFALLS_PITCH.md                   # REWRITTEN: timed spoken script
├── DECK_OUTLINE.md                      # REWRITTEN: outline of the real current deck
├── detailed-document.html               # REWRITTEN: lead with positioning
└── v3.1.html                            # INSPECT FIRST, then fix (see §4.4)
```

The existing `docs/features.md` (316 lines) is **source material, not truth**. It contains at least
one confirmed-stale claim (see §8.3). Verify everything before carrying it forward.

---

## §2 — PHASE 1: The audit (do this FIRST, ~3h)

**Nothing gets written until this phase produces its report.** The whole point of this rewrite is
that the app was vibe-coded and nobody currently knows what is real. Guessing here poisons every
downstream document.

### 2.1 Rules
- **2.1.1** Every claim must be traced to a **file:line** or a **live HTTP response**.
- **2.1.2** If a claim cannot be verified, it is written as "UNVERIFIED" — never softened, never dropped.
- **2.1.3** Prefer hitting the live backend over reading code, then confirm with code.
- **2.1.4** Dispatch subagents with `model: "sonnet"` and `subagent_type: "general-purpose"` for
  token savings. (`Explore` is read-only and cannot write its own report file — do not use it here.)
- **2.1.5** Write each subagent's findings to `docs/features/_audit/<name>.md` so nothing is lost to
  context compaction. Delete `_audit/` at the end only if the user asks.

### 2.2 Environment prep
```bash
# backend should already be running on :8000 — confirm, don't assume
curl -s localhost:8000/api/health
# expected shape: {"status":"ok","offline_mode":...,"provider":...,"vector_store":...,"audit_backend":...}

cd /home/awni/Documents/hackathon/hexafalls/sitemind/frontend && npm run dev   # :3000 if not up
```
If the backend is down, start it: `cd backend && ./run.sh`.
Note the flags in `backend/.env` — `COPILOT_AGENT_ENABLED` and `RETRIEVAL_ENABLED` were set to `1`
in a previous session, which changes behaviour vs the documented defaults.

### 2.3 Subagent dispatch (6 agents, run in parallel)

Each agent gets this preamble:

> You are auditing a vibe-coded FastAPI + Next.js app at
> `/home/awni/Documents/hackathon/hexafalls/sitemind`. The backend runs on `localhost:8000`,
> frontend on `localhost:3000`. For every feature you examine, report: (a) the exact frontend
> file + backend route, (b) whether the output is COMPUTED from data, READ from a fixture/JSON
> file, or HARDCODED in source, (c) the file:line proving it, (d) what happens when its feature
> flag is off / its API key is missing. Do not summarize charitably — if something is a canned
> fixture, say so plainly. Report UNVERIFIED for anything you could not confirm.

| # | Agent | Scope |
|---|---|---|
| A1 | Compliance + Copilot | `app/agents/*.py`, `app/ingest.py`, `app/llm_extract.py`, `app/clause_viewer.py`, frontend `compliance/`, `copilot/`. **Must** report on the `copilot.py:283` fixture-first path and on `verdict_tier`/`computed_detail` (`schemas.py:55-79`). |
| A2 | Schedule + Supply Chain + Timeline | `app/schedule.py`, `schedule_factors.py`, `supply_chain.py`, `timeline.py`, `cost_risk.py`, `impact.py`, `evidence_links.py` + their pages. Is the CPM real? Is delay propagation computed? |
| A3 | Commissioning + KG + Overview | `app/commissioning.py`, `kg.py`, `overview.py`, `documents.py`, `clock.py` + their pages. |
| A4 | Retrieval stack | `app/retrieval/*` (incl. `vector_store.py`, `embeddings_provider.py`, `filesystem_corpora.py`), `app/embeddings.py`, `standards-service/`, `codebook_router.py`, `codebook_client.py`. **Must** resolve: does anything work without `HF_TOKEN`? Why does the Knowledge Base page show `0 docs · 0 chunks`? |
| A5 | Sponsor tracks | `app/audit.py`, `audit_api.py`, `notary.py`, `llm.py`, `scripts/solana_setup.py`, `telegram-bot/bot.py`, `docker-compose.actian.yml`, `app/retrieval/vector_store.py`. For each of the 5 tracks: what actually runs, what's flag-gated off, what was never built. |
| A6 | Evals + data provenance | `backend/eval/*`, `standards-service/eval/*`, `backend/data/` (esp. `gen_synthetic.py`, `fixtures/`, `standards/clauses.json`). Which evals currently pass? Which need a live service? Which data is synthetic? |

### 2.4 Phase 1 exit criteria
- [ ] All 6 audit files exist under `docs/features/_audit/`
- [ ] Every one of the 12 frontend pages appears in exactly one audit file
- [ ] Every one of the ~50 backend routes is accounted for
- [ ] Each of the 5 sponsor tracks has a verdict: **LIVE / FLAG-GATED-OFF / NEVER BUILT**
- [ ] A consolidated list of every stale claim found in the current `docs/features.md`

---

## §3 — PHASE 2: Write `docs/features/` (~5h)

### 3.1 The per-feature template — use this EXACT structure for files 01–11

```markdown
# <N>. <Feature name>  ·  `<route>`

**One line:** <what it does, in plain English, no jargon>

## Why this exists
<The real-world problem. Who has it. What they do today without this.
 2-4 sentences. A judge with zero construction knowledge must understand it.>

## How it works
<Plain-English walkthrough. Then a mermaid diagram of the data flow.>

```mermaid
<flowchart — see §5 for style rules>
```

## What's real, what isn't
| Element | Status | Proof |
|---|---|---|
| <e.g. IS 456 clause text> | REAL | `backend/data/standards/clauses.json` + archive.org URL |
| <e.g. project documents> | SYNTHETIC | generated by `backend/data/gen_synthetic.py` |
| <e.g. copilot demo answers> | HARDCODED FIXTURE | `copilot.py:283` |

## Benefits
- <benefit stated as an outcome for the buyer in §0.1.4, not a feature>

## Code map
| Layer | File | Key symbols |
|---|---|---|
| Page | `frontend/app/<x>/page.tsx` | |
| Route | `backend/app/<x>.py` | `GET /api/...` |
| Logic | | |

## Flags & degradation
| Flag | Default | When off |
|---|---|---|

## If a judge asks…
**Q: <hardest question about this feature>**
A: <honest answer, ≤3 sentences>
*(minimum 3 Q&A pairs; at least one must be a question you would rather not be asked)*
```

### 3.2 Per-file notes
- **3.2.1** `01-compliance.md` is the **hero** — longest, most detailed. Must fully explain the
  two verdict tiers (`certified` vs `computed_draft`) and the two anti-hallucination gates
  (span verification + clause-phrase substring gate).
- **3.2.2** `02-copilot.md` must state plainly that the 6 demo questions return curated fixtures in
  every mode (`copilot.py:280-290`), and that `/api/copilot/chat` (LangGraph) is a separate,
  flag-gated path the frontend does not use by default.
- **3.2.3** `08-knowledge-base.md` must explain the `HF_TOKEN` dependency and the empty-corpus state.
- **3.2.4** `11-overview.md` must flag that ROI figures are labelled assumptions, not measurements.

### 3.3 `00-architecture-map.md`
See §5 for the required diagrams. This file is the one the user reads to finally understand
their own app — write it for someone who has never seen the codebase.

### 3.4 `91-real-vs-hardcoded.md` — the honesty ledger
One table, whole app, sorted worst-first:

| Feature | Claim a judge might infer | Reality | File:line |
|---|---|---|---|

This file is **for the user's eyes and for pre-empting judges**, not a public artifact.
It is also the single source that `docs/gaps.md` should agree with — if they conflict, fix `gaps.md`.

### 3.5 `features.md` (the new index)
- Table of the 11 features: name · route · one-line · REAL/PARTIAL/DEMO status · link
- Table of the 5 sponsor tracks in priority order · verdict · link
- Link to `00-architecture-map.md` and `91-real-vs-hardcoded.md`
- Nothing else. Keep it under ~80 lines.

---

## §4 — PHASE 3: Sponsor tracks + pitch rewrites (~6h)

### 4.1 The sponsor-track template — files `tracks/1-actian.md` … `tracks/5-mongodb.md`

```markdown
# <Track name>  ·  priority <N> of 5

## 1. What it does here
<Plain English. Then: exact files, exact env flags, exact behaviour when off.>

| Env var | Default | Effect |
|---|---|---|

## 2. Why THIS tech and not the obvious alternative
<Name the alternative a judge will name. Answer it. Be specific, not defensive.>

## 3. The "not decoration" defense
<Why the integration is load-bearing. Then the killer test:
 what breaks / what capability is lost if you delete it? If nothing breaks, SAY SO.>

## 4. Live demo click-path
1. <exact step>
2. <exact step>
   - **Judge sees:** <…>
   - **You say:** "<…>"
<Include the failure mode: what to do if it doesn't work on stage.>

## 5. Honest status
LIVE / FLAG-GATED-OFF / NEVER BUILT — plus what remains unproven.
```

### 4.2 Known starting points per track (verify all of these in Phase 1)
| # | Track | Files | Flags |
|---|---|---|---|
| 1 | Actian | `backend/app/retrieval/vector_store.py`, `docker-compose.actian.yml`, `backend/eval/run_actian_parity_eval.py` | `RETRIEVAL_VECTOR_STORE=numpy\|actian`, `ACTIAN_URL` |
| 2 | ElevenLabs | `telegram-bot/bot.py` | `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`, `TELEGRAM_BOT_TOKEN` |
| 3 | Solana | `backend/app/notary.py`, `backend/scripts/solana_setup.py`, `backend/app/audit_api.py` | `SOLANA_ENABLED`, `SOLANA_RPC_URL`, `SOLANA_SECRET_KEY`, `SOLANA_CLUSTER` |
| 4 | Gemini | `backend/app/llm.py`, `backend/app/agents/copilot_agent.py` | `GEMINI_API_KEY`, `GEMINI_MODEL`, `GEMINI_VISION_ENABLED`, `LLM_PROVIDER`, `COPILOT_AGENT_ENABLED` |
| 5 | MongoDB | `backend/app/audit.py`, LangGraph checkpointer in `copilot_agent.py` | `MONGODB_URI` (empty → JSONL fallback), `MONGODB_DB` |

**Landmine:** `GEMINI_VISION_ENABLED` exists as a flag but Gemini Vision was **explicitly never
built** (skipped by user decision). `tracks/4-gemini.md` must say so. Do not let the flag's
existence imply a shipped feature.

**Landmine:** Actian Community Edition caps at 5,000 vectors; the structural corpus is ~6,206
chunks. Verify what actually loaded before claiming corpus size anywhere.

### 4.3 `HEXAFALLS_PITCH.md` — rewrite as a timed spoken script
Format is **presented, not clicked** (user presents, judges watch). Structure:
- **Total runtime: 5 minutes** (confirmed by the user 2026-07-25).
- **Tone constraint:** impactful and simple. A judge with no construction and no ML background must
  follow every feature and every sponsor track. No jargon without an immediate plain-English gloss.
- Beat-by-beat table: `time · what's on screen · what you say · what could go wrong`
- The 4 beats from §0.1.6 are the spine
- One "everything else" beat covering the other 7 pages in ~15 seconds
- Sponsor tracks woven into the beats in priority order, not bolted on at the end
- A "if the demo breaks" fallback path (static screenshots live in `docs/ui_images/`)

### 4.4 `v3.1.html` — INSPECT BEFORE EDITING
The user called this "broken slides" but the failure is **not yet diagnosed**.
1. Serve and render it — `cd docs && python3 -m http.server 8765`, then drive it with Playwright
   (Playwright cannot open `file://` URLs in this environment).
2. Report to the user what "broken" actually means before changing anything.
3. Known handling constraint: this file has embedded base64 fonts + an image; individual lines
   reach ~130,000 chars and the Read tool will fail. Work around it with
   `awk 'length($0) < 2000' v3.1.html > /tmp/v3.1-readable.html`, read that to plan, then apply
   changes with Edit against the real file (exact-string matching is unaffected by the long lines).

### 4.5 `detailed-document.html` — re-cut
Currently a 12-section plain-English crash course, ordered as history-first.
- New section 1 = the positioning spine (§0.1)
- Demote ET-hackathon history to an appendix
- Keep the no-code, plain-English constraint — this is the doc the user reads to understand the app
- Keep the existing dark theme and mermaid CDN usage; do not redesign

### 4.6 `DECK_OUTLINE.md` — replace
Currently a historical banner over ET-hackathon-era content. Replace with the actual slide-by-slide
outline of `v3.1.html` as it exists after §4.4, mapped to the §0.1.6 demo beats.

---

## §5 — Required diagrams (all mermaid)

Put all of these in `docs/features/00-architecture-map.md`. Repeat individual ones inside the
per-feature files where useful.

- **5.1 System map** — browser → Next.js → FastAPI → (Codebook MCP · retrieval · KG · Mongo ·
  Solana · Gemini · Actian). Show which edges are flag-gated with dashed lines.
- **5.2 The verdict pipeline** — READ (LLM) → JUDGE (Python) → WRITE (LLM), with the two
  anti-hallucination gates drawn as explicit checkpoints. **This is the money diagram.**
- **5.3 Verdict tiers** — a decision tree: param → has `checks.py` rule? → certified /
  → retrieval finds clause? → computed_draft / → unresolved.
- **5.4 Routing map** — the 12 frontend pages, each with the backend routes it calls.
  A table is acceptable here if a diagram gets unreadable.
- **5.5 Request lifecycle** — one compliance check end to end, from click to rendered NCR,
  as a sequence diagram.
- **5.6 The audit chain** — NCR → content hash → ledger row → Solana anchor → verify,
  showing where tampering is detected (`mongo_intact` false + `chain_intact` true).
- **5.7 Data provenance** — which data is real (IS/CEA clauses), which is synthetic
  (project docs, schedule, shipments), which is fixture (copilot answers, compliance prose).

**Style rules:** every diagram ≤ 15 nodes; label edges with verbs; no colour-only meaning;
must render in GitHub-flavoured markdown.

---

## §6 — Execution order & budget

| Phase | Work | Est. |
|---|---|---|
| 1 | Audit — 6 parallel sonnet subagents + consolidation | 3h |
| 2 | `docs/features/` — 11 feature files + index + architecture map + honesty ledger + evals | 5h |
| 3a | 5 sponsor-track files | 2h |
| 3b | `HEXAFALLS_PITCH.md` rewrite | 1.5h |
| 3c | `v3.1.html` inspect → report → fix | 1.5h |
| 3d | `detailed-document.html` + `DECK_OUTLINE.md` | 1h |
| — | **Total** | **~14h** |

**Checkpoint with the user after Phase 1.** The audit will surface things the user does not know
about their own app. They should see that before 10 hours of writing is built on top of it.

---

## §7 — Acceptance criteria

- [ ] Every claim in every produced file traces to a file:line or a live response
- [ ] All 12 frontend pages documented; all ~50 backend routes accounted for
- [ ] All 5 sponsor tracks have all 4 required sections (§4.1) and an honest status verdict
- [ ] All 7 diagrams present and rendering
- [ ] `91-real-vs-hardcoded.md` exists and does not contradict `docs/gaps.md`
- [ ] Zero application code changed (`git status` shows only `docs/` modifications)
- [ ] The user can read `00-architecture-map.md` alone and explain their own app
- [ ] Every "If a judge asks…" section contains at least one question the user would rather avoid

---

## §8 — Ground rules and known landmines

- **8.1 Honesty over polish.** This project's entire thesis is "the LLM never computes a verdict."
  A single overstated claim in these docs damages that more than any missing feature. If something
  is a fixture, write "fixture."
- **8.2 Never assert a number you did not just verify.** Not eval counts, not chunk counts, not
  clause counts. Read it from the source or omit it.
- **8.3 Confirmed-stale claims in the current `docs/features.md`** — do not carry these forward:
  - Line ~309: "13/24 citation `verify_url`s flagged as dead" — **no longer true**, the live
    `clauses.json` has zero `gaudi.local` URLs.
  - The corpus name `manak_structural` was renamed to `structural_standard_codes`.
    Screenshots in `docs/ui_images/` still show the old name; they are stale.
  - The eval-script count ("21 scripts") has not been re-verified.
- **8.4 The screenshots in `docs/ui_images/` predate the Audit Ledger page.** `/audit` **is** in the
  nav (`frontend/components/Shell.tsx:51-62`). Re-screenshot before using any image in a deck.
- **8.5 Gemini free tier is 20 requests/day** and has been exhausted in past sessions. Do not burn
  it on verification. Prefer reading code and hitting deterministic endpoints.
- **8.6 Split destructive shell commands** into separate tool calls. A previous session nearly lost
  `backend/.env` to a chained `mv && pkill && diff`.
- **8.7 `docs/` scatters easily** — there is a `docs/archive/` full of prior casualties. Every file
  this plan creates is listed in §1. Do not create files outside that list without asking.
- **8.8 Read before writing.** `docs/PROGRESS.md` (build log), `docs/gaps.md` (honest gap list),
  `docs/know.md` (real-vs-synthetic + judge Q&A), `.claude/CLAUDE.md` (project front door),
  `hexafalls_plan.md` (canonical build spec). Where they conflict with a live-code observation,
  **the live code wins** and the doc gets flagged.
