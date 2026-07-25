# HexaFalls Revamp Plan — SiteMind → tamper-proof intelligence for hyperscale & public-infra megaprojects

> **Executor note (read first).** This plan is written to be executed by a fresh, cheaper model
> (Sonnet-tier) in a new session. Follow it literally. When a step says "do NOT touch X," that is a
> hard rule, not advice.
>
> **Git (user-confirmed):** the existing `.git` holds **old ET AI hackathon history** and is being
> **intentionally wiped for a fresh HexaFalls history**. On step 0: `rm -rf .git` then `git init`.
> **Before wiping, print the current remote** (`git remote get-url origin`) so the user can re-add it
> later — it is `git@github.com:AwkJay/sitemind.git`. Do **not** re-add the remote or force-push
> yourself; leave that to the user. After init, make **one** initial commit only if the user asks;
> otherwise commit after each workstream **only when the user asks**.

---

## 1. Context — why we are doing this

SiteMind was built for the ET AI Hackathon (Problem #4: data-centre EPC intelligence). That hackathon
is over. We are now entering **HexaFalls** — an open-innovation MLH hackathon with **no fixed track**
and several sponsor prizes. Two things change:

1. **Positioning.** We are no longer bound to "data-centre EPC." We reframe SiteMind as the
   intelligence + **tamper-proof accountability** layer for *any hyperscale / public-infrastructure
   megaproject* — data centres, semiconductor fabs, and by extension government infrastructure
   spending where opacity enables cost/quality fraud.
2. **Sponsor tracks.** We integrate sponsor tech **where it genuinely strengthens the product**, not
   as decoration. Each integration below has an honest justification tied to the thesis.

**What must NOT change: the credibility thesis.** SiteMind wins because *the LLM never computes a
verdict*. Every pass/fail is deterministic Python against a **real, cited** primary-source clause —
either a **pre-vetted rule** (`backend/app/agents/checks.py`, the "certified" tier) or a rule the LLM
**reads out of the real clause text** and `rule_eval.py` then **computes**, shown as a **DRAFT an
engineer confirms** (the "computed-draft" tier, Workstream B2). The LLM extracts and explains; it
never does the arithmetic and never invents a rule. Every metric comes from a real eval run. We are
*adding capabilities around* that core — including scaling it past hand-written rules — never
weakening it.

---

## 2. The new pitch (positioning)

**One-liner:** *"Every compliance decision on a megaproject — cited to the actual law, decided by
auditable code not a black-box model, and notarized on a public blockchain so it can never be quietly
altered. Runs fully offline, on-site."*

**The narrative arc for judges:**
- **Perceive** — Google **Gemini** reads the documents *and now the drawings/photos* (multimodal).
- **Retrieve** — **Actian VectorAI DB** serves the semantic search over 6,206 real Indian-code clause
  chunks, running **fully offline / air-gapped** — matching the security posture of a real
  hyperscale or government site where data cannot leave the premises.
- **Decide** — a **two-tier** engine (Workstream B2): where a **pre-vetted rule** exists,
  deterministic Python decides against the cited clause; for any other clause, **Gemini reads the
  rule out of the real clause text into a structured spec** and **deterministic Python (`rule_eval`)
  computes** the verdict — a **DRAFT an engineer confirms**. The LLM never does the arithmetic and
  never invents a rule. *This is the moat — now scalable past hand-written rules.*
- **Remember** — every finalized decision is written append-only to a **MongoDB Atlas** audit ledger
  (the project memory flat files never had).
- **Prove** — each ledger entry's hash is anchored on **Solana** (devnet), so anyone can
  independently verify the record was never tampered with. *This is the anti-corruption mechanism —
  concrete and demoable, not a slogan.*
- **Reach the field** — a **Telegram** bot with **ElevenLabs** voice lets a site engineer ask
  questions by voice note in Hindi/regional languages and hear a cited answer back.

**Honesty guardrails for the pitch (do not violate):**
- Say "tamper-**evident** / independently verifiable," never "impossible to corrupt / eliminates
  corruption." The mechanism proves a record wasn't *silently* altered; it doesn't police human intent.
- All project data remains **synthetic/representative** (modelled on public tenders). The standards,
  the checking logic, and the crypto/audit mechanisms are **real**. Disclose this.
- Say **"AI-drafted, engineer-confirmed"** for computed-draft findings; never present a draft verdict
  as certified. The two tiers are labeled in the UI — do not blur them in the pitch.
- **No asserted numbers.** Any metric stated must come from an eval run in `backend/eval/`.

---

## 3. Non-negotiables — apply to EVERY workstream

1. **The LLM never computes a verdict.** Every pass/fail is produced by deterministic Python —
   either `backend/app/agents/checks.py` (pre-vetted rules, the "certified" tier) or the new generic
   evaluator `backend/app/agents/rule_eval.py` (the "computed-draft" tier). The LLM only *perceives*
   (extract values, transcribe, and **read a rule out of a real clause into a structured spec**) and
   *explains* (prose). It never does arithmetic, never invents a rule (the rule's `clause_phrase`
   must be a verbatim substring of the retrieved clause), and computed-draft verdicts are labeled
   DRAFT for an engineer to confirm. **Do NOT modify `checks.py` decision logic.**
2. **Preserve the span-verification gate.** `backend/app/llm_extract.py::verify_spans` must still run
   on anything an LLM extracts (including Gemini Vision output). Values whose quote is not a verbatim
   substring of the source text are dropped. Vision-sourced params must be labeled with the correct
   `Citation.source_type` (`primary_scan_ocr`) so provenance is disclosed honestly.
3. **OFFLINE_MODE must always boot with zero keys.** Every integration is *additive* and must degrade
   to a clean no-op with a clear "not configured" state (in UI and API) when its key/service is
   absent. The keyless demo path must never break.
4. **Evals must stay byte-identical.** Do not route the deterministic source-data loaders
   (`backend/app/data_loader.py`) or the numpy retrieval reference through any new backend by default.
   New backends are opt-in via env flags; `python -m eval.run_eval` and all `run_*_eval.py` must
   produce the same reports as before. (Actian gets its **own** parity eval instead.)
5. **No framework in the verdict core; LangGraph only on the Copilot edge.** The compliance verdict
   path — `checks.py`, `rule_eval.py`, and the compliance pipeline — stays plain, auditable Python
   with **NO framework**. **LangGraph is permitted ONLY on the Copilot conversational edge**
   (Workstream F2) for tool-routing + memory, and may **never** make a pass/fail decision or import
   from the verdict core. This scoping is deliberate: framework at the conversational edge (where
   scaling tools + state is the job), deterministic at the decision core (where auditability is the
   job). Do **NOT** add LangChain's legacy `AgentExecutor`/chains, LlamaIndex, or CrewAI anywhere.
   (Actian's SDK is fine — a database client, not an agent framework.)
6. **No secrets in git.** API keys, the Solana keypair, Mongo URIs live in `.env` only. Update
   `.gitignore` to cover any new secret/keyfile paths.
7. **Follow the existing provider-switch pattern.** New backends mirror how `LLM_PROVIDER` /
   `RETRIEVAL_EMBEDDINGS_PROVIDER` already work in `backend/app/config.py`: an env var selects the
   implementation, default = the safe/offline one, unknown/missing → graceful fallback.
8. **Frontend convention:** every new **GET** endpoint must have a bundled mock fallback in
   `frontend/lib/mocks.ts` (see the existing `getJSON`/`postJSON` pattern in `frontend/lib/api.ts`);
   real-action **POST**s throw a typed `*UnavailableError` instead (see `IngestUnavailableError`).

---

## 4. Sponsor-track scorecard (what each workstream is FOR)

| Workstream | Sponsor prize it targets | Honest justification |
|---|---|---|
| C. Actian VectorAI DB | **Accio Relevance — Actian ($1,000, top priority)** | Production, **offline/edge** vector DB for the 6,206 real clause chunks — matches air-gapped megaproject security. |
| A+B. Gemini (prose + vision) | **Best Use of Gemini** | Gemini becomes the reasoning+perception engine; **vision** reads scanned drawings the app rejects today. |
| B2. Tiered verdicts (rule extraction) | **Best Use of Gemini + Technical Excellence** | Gemini reads a rule out of any real clause → deterministic `rule_eval` computes → engineer confirms. Scales compliance past hand-written rules **without** letting the model decide. |
| F2. Copilot agent (LangGraph) | **Technical Excellence + field UX** | Multi-pillar tool-routing + durable Mongo-backed memory on the conversational edge; verdict core stays framework-free. |
| D. MongoDB Atlas | **Best Use of MongoDB Atlas** | The append-only audit ledger — real persistence the flat-file app never had. |
| E. Solana | **Best Use of Solana** | On-chain notarization of every decision = the tamper-evidence / anti-corruption mechanism. |
| F. ElevenLabs + Telegram | **Best Use of ElevenLabs** (+ field UX) | Multilingual voice site-agent; ElevenLabs STT+TTS, Telegram delivery. |
| G. DigitalOcean | **Best Use of DigitalOcean** (deferred) | Deploy guide only for now (`digitalocean.md`); implement if credits arrive. |

---

## 5. Accounts / keys the user must obtain (list these for the user; do not fabricate)

- **Gemini:** API key from Google AI Studio → `GEMINI_API_KEY`.
- **Actian VectorAI DB:** local via Docker (`docker compose up`); Community Edition (5K vectors, free)
  or Starter 30-day trial (1M vectors). Docs: https://docs.vectoraidb.actian.com/ . See §6.C for the
  5K-vs-6,206 constraint.
- **MongoDB Atlas:** free M0 cluster → connection string `MONGODB_URI`.
- **Solana:** no account needed — generate a **devnet** keypair locally and airdrop test SOL (script
  in §6.E). Devnet only, zero real cost.
- **ElevenLabs:** API key → `ELEVENLABS_API_KEY` (+ pick a multilingual voice id).
- **Telegram:** create a bot via @BotFather → `TELEGRAM_BOT_TOKEN`.

---

## 6. Workstreams

Each workstream is independently shippable and independently demoable. Do them in the order in §7.

---

### A. Gemini as the default prose LLM

**Goal:** Gemini writes NCR findings and copilot answers (replacing Claude/OpenAI as the headline
provider), via the existing clean provider-dispatch wrapper. Decisions stay in Python.

**Why it's honest/clean:** `backend/app/llm.py` is already a provider switch (`codex`/`openai`/
`anthropic`). Adding `gemini` is ~30 lines and touches no caller.

**Files to change:**
- `backend/app/config.py`
  - Add `GEMINI_API_KEY = os.getenv("GEMINI_API_KEY","").strip()` and
    `GEMINI_MODEL = os.getenv("GEMINI_MODEL","gemini-2.5-flash").strip()`
    (confirm the exact current model id in Google AI Studio; a `*-flash` model is right for cost).
  - Extend the `LLM_PROVIDER` inference block (lines ~60-68) so a present `GEMINI_API_KEY` infers
    `"gemini"`, and make `gemini` the **preferred** inference if multiple keys exist.
  - Extend `_provider_usable()` (lines ~71-78): `if LLM_PROVIDER == "gemini": return bool(GEMINI_API_KEY)`.
- `backend/app/llm.py`
  - Add `_gemini_complete(system, user, max_tokens) -> str` using the `google-genai` SDK:
    `from google import genai`; `client = genai.Client(api_key=config.GEMINI_API_KEY)`;
    `client.models.generate_content(model=config.GEMINI_MODEL, contents=[...], config=...)` with
    system instruction = `system`, temperature 0; return `resp.text.strip()`.
  - Add `if provider == "gemini": return _gemini_complete(system, user, max_tokens)` inside
    `complete_text()` (lines ~108-118). Keep the `except Exception: return ""` behavior — a Gemini
    hiccup must fall back to offline templates, never crash a request.
- `backend/requirements.txt`: add `google-genai`.
- `.env.example` and `backend/.env.example`: document `LLM_PROVIDER=gemini`, `GEMINI_API_KEY=`,
  `GEMINI_MODEL=gemini-2.5-flash`.

**Fallback:** no key → `OFFLINE_MODE` True → deterministic templates (unchanged path).

**Verify:** set the key + `LLM_PROVIDER=gemini`; `GET /api/health` shows `provider: gemini`; run a
compliance check and a copilot ask — prose should read as model-written, not the offline template.
Unset the key → app still boots and answers from templates. Run `python -m eval.run_eval` → **still
41/41** (prose provider must not change any verdict).

---

### B. Gemini Vision — read scanned drawings / photos (the multimodal win)

**Goal:** The compliance upload can accept an **image** (photo/scan of a shop drawing or spec sheet)
or an image-only PDF. Gemini Vision transcribes it + extracts parameters; the existing
`verify_spans` gate still enforces zero-hallucination; Python still decides.

**Why it's honest:** Today `backend/app/agents/compliance.py` (the ingest handler, ~lines 365-370)
raises **422 "scanned/image-only PDFs are not supported"**. That dead-end is the exact hook. Crucially,
Vision must not bypass the span gate — so Gemini returns **both** a full text transcription **and** the
params-with-quotes, and we run `verify_spans(params, transcription)`. The quote must be a verbatim
substring of Gemini's own transcription; survivors are tagged provenance = OCR/scan so
`Citation.source_type = "primary_scan_ocr"` discloses that the source is an image transcription, not a
native text layer. This keeps the guarantee *and* discloses the weaker provenance honestly.

**Files:**
- New `backend/app/gemini_vision.py`:
  - `is_image_mime(mime) -> bool` (png/jpeg/webp) and a check for "pdf with no extractable text."
  - `extract_from_bytes(content: bytes, mime: str) -> dict` — sends inline bytes to Gemini
    (`genai` supports inline `Part.from_bytes(data=..., mime_type=...)`; Gemini accepts `application/pdf`
    and images directly, so no pdf-to-image rasterization dependency is needed). Prompt asks for JSON:
    `{ "transcription": "<verbatim readable text of the doc>", "params": [ {param_type, value, unit,
    quote, element} ... ] }`. Return that dict. Return `{}` on any failure.
  - Gate the module on `config.GEMINI_VISION_ENABLED` and a present `GEMINI_API_KEY`.
- `backend/app/config.py`: add `GEMINI_VISION_ENABLED = os.getenv("GEMINI_VISION_ENABLED","0")=="1"`.
- `backend/app/agents/compliance.py` ingest handler: where text extraction yields empty text (the
  current 422 branch, ~365-370) **and** vision is enabled **and** the file is image/scanned-PDF →
  call `gemini_vision.extract_from_bytes`, take `transcription` as the document text, run the existing
  `llm_extract.verify_spans(params, transcription)`, feed survivors through the normal
  `ingest.to_param_dicts` → `register_upload` → checks path. Tag the resulting citations'
  `source_type = "primary_scan_ocr"`. If vision disabled or returns nothing → keep the current 422.
- `backend/app/llm_extract.py`: reuse `verify_spans` as-is. If a small helper is needed to accept an
  externally supplied transcription, add it without altering the gate's substring logic.
- Frontend `frontend/app/compliance/page.tsx`: allow image mime types in the upload input; surface the
  `source_type` provenance badge on results (the `NCRCard`/`CitedClauseBox` components already render
  citation fields — extend to show a "read from scan (OCR)" tag when `source_type=primary_scan_ocr`).
- `backend/requirements.txt`: none beyond `google-genai` (already added in A).

**Fallback:** `GEMINI_VISION_ENABLED=0` or no key → unchanged 422 for scanned files (today's behavior).

**Demo:** upload a **photo** of a drawing stating e.g. a clearance/rating value → Gemini reads it →
Python raises the cited NCR. "The old pipeline literally rejected this file; now it reads a photo from
the field." Also upload a blurry/uninformative image → it **abstains** (no fabricated params).

**Verify:** with vision on, POST an image to `/api/compliance/ingest` → params extracted, each with a
quote that is a substring of the transcription, NCRs cited, `source_type=primary_scan_ocr`. With
vision off → 422. `verify_spans` unit tests (`tests/test_llm_extract.py`) still pass.

---

### B2. Tiered compliance verdicts — read-the-rule / code-computes / engineer-confirms (CORE SCALING UPGRADE)

**Goal:** Stop hand-writing a Python rule per clause (it cannot scale to thousands of IS clauses).
For any clause with no pre-vetted rule: an LLM **reads the retrieved, real clause and extracts a
structured rule** (operator/threshold/table/formula) + the verbatim clause phrase; a **generic
evaluator computes** PASS/FAIL; the UI shows value + rule + math + cited clause as a **DRAFT** an
engineer confirms. The existing ~17 hand-vetted `checks.py` rules stay as the "certified" tier,
**untouched** (evals byte-identical). New path is **additive + flag-gated (default off)**.

**Three verdict tiers (all cite a real clause):**

| `verdict_tier` | When | Verdict by | UI badge |
|---|---|---|---|
| `certified` | Param matches a `checks.py` rule | hand-vetted Python (unchanged) | "Certified · pre-vetted" (green) |
| `computed_draft` | No rule → retrieve clause → LLM extracts rule → evaluator computes | `rule_eval.py`; LLM only *read* the rule | "DRAFT · confirm reading" (amber) |
| `unresolved` | Retrieval abstains, or clause-phrase substring gate fails | none — honestly flagged | "No governing clause found" (slate) |

**Two anti-hallucination gates (non-negotiable):** (1) the extracted **value** still passes
`verify_spans` (verbatim quote from the doc); (2) the extracted rule's **`clause_phrase` must be a
verbatim substring of the retrieved clause `raw_text`** — reuse `llm_extract._norm` + substring
logic; fail → `unresolved`. Never fabricate a rule or clause.

**The seam (verified):** in `backend/app/agents/compliance.py`, the per-param loop drops any param
matching no check at **`if not applied: continue` (≈ lines 282-283)** — today a silent blind spot
(not counted, not reported). That is exactly where the computed-draft/unresolved tier attaches.
Precedent to reuse: `ActionBrief.status` already has `"REVIEW_REQUIRED"` (schemas.py ≈281),
`CommissioningFinding.verdict` already has `"NOT_CHECKABLE"` (≈310).

**Build steps (make each a TODO; verify before moving on):**
1. **Generic evaluator (pure Python, build+test FIRST)** — new `backend/app/agents/rule_eval.py`
   + new pydantic `ExtractedRule` in `schemas.py`
   `{ kind: Literal["compare","range","min_of","max_of","table_lookup","formula","none"], operator,
     threshold, unit, inputs: dict={}, table: dict|None, expression: str|None, clause_key,
     clause_phrase }`. `evaluate(rule, param) -> (PASS|FAIL|NOT_CHECKABLE, detail)`, never raises.
   `formula` runs `expression` via a **SAFE AST evaluator** (whitelist numbers, named inputs,
   `+ - * / ** ( )`, `min`/`max` only — **never `eval()`**). These are exactly the shapes the
   `checks.py` lambdas already use by hand — read them as reference. Unit tests
   `backend/tests/test_rule_eval.py` (one per kind + reject an unsafe expression) must be green first.
2. **Schema fields + flag** — on `NCR` (schemas.py ≈38-52) add `verdict_tier: Literal["certified",
   "computed_draft","unresolved"] = "certified"` and `extracted_rule: Optional[ExtractedRule] = None`;
   extend `NCR.status` to include `"REVIEW_REQUIRED"`; add `computed_draft`/`unresolved` counts to
   `CoverageStat`/`ComplianceResult` (≈319-333). `config.py`:
   `COMPLIANCE_RULE_EXTRACTION = os.getenv("COMPLIANCE_RULE_EXTRACTION","0")=="1"`.
3. **Seam rewrite** — gate on `COMPLIANCE_RULE_EXTRACTION and RETRIEVAL_ENABLED` (off → keep the
   `continue`). New `_computed_draft_finding(param, ncr_id)`: build query text from the param →
   in-process `Corpus.query(text, k=1..3)` (`retrieval/index.py` ≈115; use `raw_text`, NOT the HTTP
   API); empty → `unresolved`; else extract rule (step 4) → substring gate → `rule_eval.evaluate`
   → FAIL builds an NCR (`verdict_tier="computed_draft"`, `status="REVIEW_REQUIRED"`,
   `extracted_rule`, citation from chunk `raw_text`+`verify_url`, `source_type` from `provenance_tag`).
   **Prove the flow with a hand-written `ExtractedRule` fixture BEFORE wiring the LLM.**
4. **LLM reads the rule** — `_RULE_EXTRACT_SYSTEM` prompt: "given ONE real clause + ONE param, output
   JSON matching ExtractedRule stating the requirement **as written**; `clause_phrase` copied
   verbatim; do not invent a threshold; if no checkable rule, `kind:'none'`." Call `llm.complete_json`
   (inherits `LLM_PROVIDER`; Gemini once Workstream A lands). No key/empty → `unresolved`.
5. **Extraction allowlist** — `llm_extract.py`: add an `EXTRACTABLE_TYPES` set so interpretive param
   types survive the span gate (still needing a verbatim value quote) and route to
   `_computed_draft_finding`. Widen only the **type allowlist**, not the substring gate.
6. **Frontend two-half panel** — `types.ts`/`format.ts`: add `verdict_tier`, `extracted_rule`,
   `"REVIEW_REQUIRED"`, an `ExtractedRule` type, a `tierMeta` map, and map retrieval provenance tags
   into `sourceTypeMeta`. `NCRCard.tsx`: add a third `<Chip>` (tier) to the header chip row (≈24-31);
   for `computed_draft` render a DRAFT banner (reuse advisory branch ≈102-128) + **Interpretation
   half** ("clause requires: value {op} {threshold} {unit}", highlight `clause_phrase`) beside
   `CitedClauseBox` + **Computation half** ("your value {v} → {v} {op} {threshold} → FAIL/PASS").
7. **One curated demo clause** — wire a `table_lookup` (w/c-ratio-by-exposure) or `formula`
   (`pz >= 0.6·Vz²`) end-to-end.
**If the clock runs short:** ship through steps 3+6 with a hand-written `ExtractedRule` — the
read-rule/code-computes/engineer-confirms story + two-half UI land without LLM extraction (step 4).

**New files:** `backend/app/agents/rule_eval.py`, `backend/tests/test_rule_eval.py`.
**Fallback:** flag off → today's behavior (drop). Flag on but no LLM key → `unresolved` (no fabricated
rule). Certified tier + keyless boot unchanged.
**Verify:** `python -m eval.run_eval` + all `run_*_eval.py` byte-identical (flag off);
`pytest backend/tests/test_rule_eval.py`; with `COMPLIANCE_RULE_EXTRACTION=1 RETRIEVAL_ENABLED=1`,
a rule-less param yields a `computed_draft` NCR with a populated `extracted_rule` + real cited clause
+ the two-half UI; a `clause_phrase` not in the clause → `unresolved`; footing cover 40 mm still
returns `certified` from `checks.py`.

---

### C. Actian VectorAI DB — the offline production vector store ($1,000 track, HIGH PRIORITY)

**Goal:** Back SiteMind's dense semantic retrieval with **Actian VectorAI DB** — a production vector
database running **fully offline** — over the 6,206 real Indian-code clause chunks, without disturbing
the eval-calibrated numpy reference path.

**Why this design (read carefully):** the retrieval evals assert exact cosine scores, calibrated
abstention floors (0.30/0.40/0.35), exact `document_id`/`chunk_id`/`raw_text` round-trip, and exact
chunk counts (17 docs / 6,206 chunks; 2 / 29). An approximate-ANN backend can reorder results and shift
scores, which would break those known-answer assertions. So we do **NOT** replace the numpy path for
evals. Instead we add a **vector-store provider switch** (mirroring `RETRIEVAL_EMBEDDINGS_PROVIDER`):
- `RETRIEVAL_VECTOR_STORE=numpy` (default) → the current in-memory numpy matrix. Evals + offline use
  this, byte-identical.
- `RETRIEVAL_VECTOR_STORE=actian` → the live app + demo use Actian. Proven correct by its **own**
  parity eval (below), not by the numpy-calibrated evals.

This is exactly how the codebase already treats embeddings providers, so it's in-grain and honest: a
real, functioning Actian retrieval path serves the deployed app; numpy remains the reference/fallback.

**Actian API (from docs, mirrors Qdrant):**
```python
from actian_vectorai import VectorAIClient, VectorParams, Distance, PointStruct
with VectorAIClient("localhost:6574") as client:      # gRPC; runs offline in Docker
    client.health_check()
    client.collections.create("c", vectors_config=VectorParams(size=384, distance=Distance.Cosine))
    client.points.upsert("c", points=[PointStruct(id=i, vector=v, payload={...})])
    results = client.points.search("c", vector=q, limit=k)   # result.id, result.score, result.payload
```
Install: `pip install actian-vectorai` (also `numpy grpcio pydantic`; Python ≥3.10). Confirm the exact
package name against the docs (quickstart says `actian-vectorai`; the SDK reference mentions
`actian-vectorai-client`).

**The single seam:** `Corpus` in `backend/app/retrieval/index.py` (and the **identical** file in
`standards-service/app/retrieval/index.py` — apply the same change in both). All dense retrieval flows
through `Corpus._rebuild_indices()` (ingest, ~lines 85-92) and `Corpus.query()` (search + floor + RRF,
~lines 115-139). The FastAPI retrieval router, the Codebook MCP server, and `document_check` all call
`Corpus` and nothing lower. `copilot.py` has a *separate* inline dense store (`_index`/`_retrieve`) —
leave that on numpy for now (out of scope; note as a stretch).

**Files:**
- New `backend/app/retrieval/vector_store.py` (and copy into `standards-service/app/retrieval/`):
  - Abstraction selected by `config.RETRIEVAL_VECTOR_STORE`:
    - `NumpyVectorStore`: wraps the current `self._matrix @ q` behavior (extract from `index.py` so the
      numpy path is unchanged in effect).
    - `ActianVectorStore`: connect to `config.ACTIAN_URL` (default `"localhost:6574"`).
      `ensure_collection(name, dim=384)` (idempotent — swallow "already exists");
      `upsert(name, ids, vectors, payloads)` with `payload={"chunk_index": i}`;
      `search(name, query_vector, limit) -> list[(chunk_index:int, score:float)]`.
  - Both return the **same shape**: a ranked list of `(chunk_index, cosine_score)` so `Corpus.query`
    keeps its floor gate + BM25 + RRF + result assembly untouched.
- `backend/app/retrieval/index.py` (and the standards-service twin):
  - In `_rebuild_indices()`: after `embeddings_provider.embed(...)`, if store is Actian →
    `ensure_collection` + `upsert` vectors keyed by chunk index; if numpy → keep `self._matrix`. BM25
    build stays numpy/rank_bm25 always.
  - In `query()`: replace **only** lines ~124-126 (`q = embed(...); dense_sims = self._matrix @ q;
    dense_order = argsort`) with: embed the query, then `dense = store.search(name, q, ...)` → derive
    `dense_order` + per-index score. **Keep unchanged**: the floor gate
    (`if top_score < RETRIEVAL_FLOOR: return []`), BM25 order, `_rrf_fuse`, and result-chunk assembly
    (so `chunk_id`/`document_id`/`raw_text`/`heading`/`breadcrumb` round-trip identically). Attach
    `chunk["score"] = float(top cosine)` as before.
- `backend/app/config.py`: add `RETRIEVAL_VECTOR_STORE = os.getenv("RETRIEVAL_VECTOR_STORE","numpy")`
  and `ACTIAN_URL = os.getenv("ACTIAN_URL","localhost:6574")`. (Same in `standards-service` config.)
- `backend/requirements.txt` and `standards-service/requirements.txt`: add `actian-vectorai`.
- New `docker-compose.actian.yml` at repo root: runs the Actian VectorAI DB container exposing `6574`.
  Document `docker compose -f docker-compose.actian.yml up -d` in README.
- New eval `backend/eval/run_actian_parity_eval.py` (and/or standards-service):
  - Boots against a running Actian instance, ingests the same known corpus, runs the same known-answer
    queries as `run_cross_corpus_eval.py`, and asserts **top-hit `document_id` parity** with the numpy
    path (not exact float equality — ANN may reorder ties) and that **gibberish still abstains**.
    Writes `actian_parity_report.json`. This is how we *prove* the Actian path with a real number.
- `backend/app/main.py` health endpoint: add `vector_store: config.RETRIEVAL_VECTOR_STORE`. Frontend:
  a small "Vector store: Actian VectorAI (offline)" indicator on the Knowledge Base / Codebook pages.

**The 5K-vector constraint (important):** Community Edition caps at 5,000 vectors; the structural corpus
is **6,206 chunks**. Options in preference order: (1) use the **Starter 30-day free trial** (1M vectors)
for the demo so the full 6,206 chunks load — best headline; (2) if only Community: index the smaller
project/copilot corpus + a ≤5,000 subset of the structural corpus, and state the tier limit. Document
which tier was used; never claim more than what actually loaded.

**Fallback:** `RETRIEVAL_VECTOR_STORE=numpy` (default) or Actian container down → numpy path. The app
must detect an unreachable Actian and fall back to numpy with a logged warning (do not crash retrieval).

**Demo:** show the Codebook/Copilot answering a semantic query, served by Actian VectorAI in a local
Docker container with **no internet** — "the retrieval a government or defense-grade site can run
air-gapped." Show `actian_parity_report.json`.

**Verify:** `docker compose ... up`; set `RETRIEVAL_VECTOR_STORE=actian RETRIEVAL_ENABLED=1`; ingest a
corpus; `POST /api/retrieval/query` returns correct known-answer hits; `run_actian_parity_eval.py`
passes; with the flag back to `numpy`, all existing retrieval evals remain byte-identical.

---

### D. MongoDB Atlas — the append-only audit ledger

**Goal:** Persist every finalized compliance decision (NCR + cited clause + source span + provenance +
timestamp + content hash) to MongoDB as an **append-only** collection — the project memory that
flat-file recomputation never had. This is the substrate the Solana notarization anchors.

**Why it's honest:** today NCRs/alerts/timeline events are recomputed fresh from flat files every
request; nothing records *when a finding first appeared or changed*. Mongo's role is specifically this
new audit history — we do **not** migrate the deterministic source loaders to Mongo (that would risk
the evals for no benefit). `backend/app/trace.py` (per-run JSON) is the existing pattern to generalize.

**Files:**
- New `backend/app/audit.py`:
  - Lazy pymongo client from `config.MONGODB_URI`. DB name `config.MONGODB_DB` (default `sitemind`),
    collection `audit_events`. Wrap writes in `fastapi.concurrency.run_in_threadpool` at the call site
    (writes are tiny) to avoid blocking.
  - `content_hash(payload: dict) -> str`: SHA-256 over **canonical** JSON
    (`json.dumps(payload, sort_keys=True, separators=(",",":"))`). Deterministic → idempotency + it's
    what Solana anchors.
  - `record_event(pillar, kind, ref_id, payload) -> dict`: builds
    `{ _id, seq, created_at, pillar, kind, ref_id, payload, content_hash, solana:{status:"pending"} }`,
    inserts with a **unique index on `content_hash`** so re-recording the same decision is a no-op.
    Returns the stored doc.
  - `get_events(filters)` / `get_event(id)` for the UI.
  - **No update/delete of `payload`/`content_hash` is ever exposed** (append-only). Only the `solana`
    sub-doc is updated later by the notary.
  - **Graceful degradation:** if `MONGODB_URI` unset/unreachable, all functions become safe no-ops that
    instead append to a local JSONL at `backend/data/audit_events.jsonl`. Never raise into a request.
- New `backend/app/audit_api.py` (router): `GET /api/audit` (list, filter), `GET /api/audit/{id}`.
  Mount in `backend/app/main.py` (always on — degrades to JSONL/empty without Mongo).
- New pydantic `AuditEvent` model in `backend/app/schemas.py` (keep the "shapes are stable" discipline).
- Wire the write: in `backend/app/agents/compliance.py`, after `evaluate()` on a **real upload**
  (`/api/compliance/ingest`), call `audit.record_event(...)` once per NCR (idempotent via hash). Do
  **not** record on every read-only `/api/compliance/check` of the preloaded demo — seed instead.
- Seeding: an idempotent `POST /api/audit/seed` (or startup hook) that records the preloaded project's
  current NCRs so `/audit` isn't empty on stage. Idempotent via `content_hash`.
- `backend/requirements.txt`: add `pymongo[srv]` (+ `dnspython`).
- `backend/app/config.py`: add `MONGODB_URI` and `MONGODB_DB` (default `"sitemind"`).
- Frontend: new page `frontend/app/audit/page.tsx` — the **Audit Ledger** ("Chain of Custody"): a table
  of events with timestamp, pillar, severity, cited clause, content hash (short), and per-row Solana
  status/link (filled by E). Add to left nav (`frontend/components/Shell.tsx`). Add `getAudit()` to
  `frontend/lib/api.ts` with a mock fallback in `frontend/lib/mocks.ts`.

**Fallback:** no Mongo → local JSONL ledger + same UI (badge: "local ledger, Atlas not configured").

**Verify:** with `MONGODB_URI` set, ingest → `GET /api/audit` shows event(s) with a stable
`content_hash`; recording twice does not duplicate. Without Mongo → app boots, ledger reads JSONL.
Existing evals unaffected.

---

### E. Solana — on-chain notarization (the anti-corruption proof)

**Goal:** Anchor each audit event's `content_hash` on **Solana devnet** so anyone can independently
verify the record was not altered. Store the tx signature back on the Mongo event. Provide a verify
endpoint that recomputes the hash and confirms it against the chain.

**What gets recorded & why it's useful (put this reasoning in the pitch — the plan must not be vague
about "why a blockchain").** Walk the concrete example end to end:

1. **The compliance decision.** Take one finalized NCR, e.g. *"Beam B-12 concrete cover = 40 mm; IS 456
   cl. 26.4 requires ≥ 50 mm → FAIL."* The audit event (Workstream D) stores: what was checked, the
   extracted value + its verbatim source span, the governing clause + threshold, the verdict, the
   timestamp, and that Python (not the LLM) decided it.
2. **The fingerprint.** `content_hash` = SHA-256 over the canonical JSON of that event. Deterministic:
   the same record always hashes the same; change one character (40 → 45) and the hash is completely
   different. It's a wax seal that cracks if the envelope is opened.
3. **On-chain stamp.** **Only the hash** goes to Solana (via SPL Memo), **never the project data** —
   so nothing confidential leaves the premises; the public sees a meaningless-looking 64-char string.
   The chain returns a tx signature + a permanent, uneditable timestamp: "this fingerprint existed at
   time T and can never be altered or deleted."
4. **Verify (the payoff).** Anyone recomputes the hash from the current DB record and compares it to
   the one frozen on-chain. Match → **green** (record is exactly as first decided). Mismatch → **red**
   (record was edited after the fact).

**Why a public chain and not just a hash in our own DB (the judge's real question):** a hash in your own
Postgres is only as trustworthy as your DB admin — who is often the party being audited. A public,
permissionless ledger lets a regulator/auditor/citizen verify a record was not silently rewritten
**without trusting SiteMind or its server**, and no single party (including the project owner) can
rewrite that history. That independent, outside-verifiable property is the entire reason to use a chain
here. The genuine problem it addresses: in public-infra megaprojects, inconvenient inspection results
get quietly "adjusted" later — this makes such editing **detectable by an outsider**.

**Threat model — state the limits out loud (honesty guardrail):** this defends against **post-hoc
alteration** of an already-recorded decision. It does **NOT** verify the value was ever *true*
(garbage-in is still garbage: if someone lies at entry, the chain faithfully protects the lie), it does
not police intent, and it can't force anyone to anchor (countermeasure: anchor automatically so a
*missing* anchor is itself a red flag). Say "tamper-**evident**", never "impossible to corrupt / stops
corruption." Its value is insurance/CCTV-like: dormant 99% of the time, decisive in the 1% dispute/audit.

**Demo must prove the "don't trust us" property:** open the anchored tx on **Solana Explorer in a
separate browser tab, outside the app** — verification that doesn't route through SiteMind is the whole
point. (**Production path, optional to mention:** anchor one **Merkle root** per batch instead of one tx
per NCR, then prove any single record's inclusion — cheaper and it answers "what about 10,000 records?")

**Design (kept simple, no Rust program):** use the **SPL Memo** program — send a tiny transaction whose
memo is the `content_hash`, from a funded devnet keypair. Verify by recomputing the hash and confirming
the memo transaction (by stored signature) contains it. Devnet only, zero real cost. No custom on-chain
program to author/deploy (lower risk than an Anchor program). **No NFT, no token, no custom contract —
this is hash-anchoring / notarization, not minting.**

**Files:**
- New `backend/app/notary.py`:
  - Uses `solana` (solana-py) + `solders`. Load the devnet keypair from `config.SOLANA_SECRET_KEY`
    (base58). RPC from `config.SOLANA_RPC_URL` (default `https://api.devnet.solana.com`).
  - `anchor_hash(hash_hex) -> {status,tx_sig,slot,cluster}`: build a tx with a single **Memo**
    instruction (data = `hash_hex`), sign, send, confirm. On any error return `{status:"error",detail}`.
  - `verify_anchor(hash_hex, tx_sig) -> bool`: fetch the tx, read its memo, return `memo == hash_hex`.
  - Gate on `config.SOLANA_ENABLED`; off → no-op `{status:"disabled"}`.
- New `backend/scripts/solana_setup.py`: generate a devnet keypair, print the base58 secret for `.env`,
  airdrop devnet SOL (`request_airdrop`). Run once.
- Extend `audit_api.py`:
  - `POST /api/audit/{id}/anchor` → `notary.anchor_hash(event.content_hash)`, update the event's
    `solana` sub-doc (only the sub-doc — `payload`/`content_hash` stay immutable).
  - `POST /api/audit/anchor-pending` → anchor all `solana.status=="pending"` events (one-click demo).
  - `POST /api/audit/{id}/verify` → recompute `content_hash(event.payload)`, compare to stored hash
    (Mongo integrity), then `notary.verify_anchor(...)` (chain check). Return both booleans.
  - Anchor **on demand** (button), not on every write, so devnet latency never slows core flows.
- `backend/app/config.py`: add `SOLANA_ENABLED`, `SOLANA_RPC_URL`, `SOLANA_SECRET_KEY`,
  `SOLANA_CLUSTER=devnet`.
- `backend/requirements.txt`: add `solana` and `solders`.
- `.gitignore`: no keypair file committed (secret in `.env`).
- Frontend `frontend/app/audit/page.tsx`: per-row **"Anchor to Solana"** + **"Verify"**; when anchored,
  link the tx sig to `https://explorer.solana.com/tx/{sig}?cluster=devnet`; verify shows green (intact)
  / red (tampered). A top-level "Anchor all pending" button.

**Fallback:** `SOLANA_ENABLED=0` → ledger works, rows show "not anchored."

**Demo (the money shot):** Audit Ledger → "Anchor to Solana" on an NCR → tx on Solana Explorer (devnet)
→ "Verify" → green. Then (optional, powerful) manually edit that event's `payload` in Mongo → "Verify"
→ **red** ("record altered — hash no longer matches the chain"). Anti-corruption, demonstrated.

**Verify:** run `solana_setup.py` (keypair + airdrop). Anchor → tx_sig visible on Explorer. Verify →
true. Tamper with the payload → verify → false. `SOLANA_ENABLED=0` → graceful "disabled."

---

### F1. ElevenLabs + Telegram — the multilingual field bot

**Goal:** A Telegram bot where a site engineer sends **text or a voice note in Hindi/English/regional
language** → transcribe + translate → query the existing Copilot → reply with a **cited answer as
ElevenLabs voice + text + a citation link**.

**Division of labor:** ElevenLabs does **STT (Scribe)** and **TTS** (its prize — voice fully in
ElevenLabs). Gemini does **translation** (Hindi↔English, prose, within Gemini's role). `/api/copilot/ask`
is unchanged and already **abstains** below a similarity floor — the bot must respect that.

**Files (new standalone service — does NOT touch the deterministic core):**
- New `telegram-bot/` directory (Python; `python-telegram-bot` async, long-polling — no public webhook
  needed for the demo):
  - `bot.py` handlers for text + voice:
    - Voice: download the Telegram voice file → **ElevenLabs Scribe STT** → transcript (+ language).
    - Translate → English via Gemini if needed.
    - `POST {BACKEND_URL}/api/copilot/ask` → cited `RFIAnswer`.
    - If Copilot **abstains** → reply "No confident answer in the project corpus — raising this as an
      RFI" (do not fabricate).
    - Translate the answer back → **ElevenLabs TTS** (multilingual voice) → send voice clip **+** text
      **+** citation link.
  - `requirements.txt`: `python-telegram-bot`, `httpx`, `google-genai`, `elevenlabs` (or raw REST).
  - `run.sh`: loads `telegram-bot/.env`, starts long-polling.
  - `.env.example`: `TELEGRAM_BOT_TOKEN`, `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`, `GEMINI_API_KEY`,
    `BACKEND_URL` (default `http://localhost:8000`).
- No backend change required (pure client of `/api/copilot/ask`). Optionally add a stable citation
  deep-link field to the copilot response if absent.

**Fallbacks:** STT fails → ask for text. TTS fails → text only. Backend unreachable → friendly error.
Copilot abstains → honest "no confident answer."

**Demo:** on a phone, send a Hindi voice note ("transformer ka clearance kitna chahiye?") → bot replies
with a Hindi voice clip + the English citation. "Intelligence in the field, in the language of the
field, still cited to the real code."

**Verify:** text question → cited answer; Hindi voice note → Hindi voice + text + citation; out-of-scope
question → graceful abstain.

---

### F2. Copilot conversational edge — LangGraph (framework at the edge ONLY)

**Goal:** Turn the Copilot (and the Telegram bot in F1) from a doc-only search box into a
**project-brain** that routes a question across pillars, remembers the conversation, and answers with
citations — using **LangGraph** on the conversational edge only. It **NEVER** decides a compliance
pass/fail; it routes, calls **read-only** tools, and phrases cited answers. Verdicts still come only
from the deterministic pipeline (B2). Keep this boundary absolute.

**Why LangGraph (not LangChain legacy agents):** LangGraph is an explicit graph/state-machine — you
define nodes/edges, the LLM chooses only *within* a node, so control flow stays inspectable (fits the
auditability thesis). It ships durable state (checkpointers) for chat memory, tool nodes for easy
tool growth, and human-in-the-loop interrupts. **Confirm the current LangGraph API against its docs
at build time** (fast-moving ecosystem — treat API names below as intent, verify before coding, same
discipline as confirming Gemini model ids).

**Files (new — do NOT touch the verdict core):**
- New `backend/app/agents/copilot_agent.py`:
  - A LangGraph agent (prebuilt ReAct-style agent, or a small `StateGraph` = model node + `ToolNode`).
    Model = Gemini via `langchain-google-genai` `ChatGoogleGenerativeAI` (inherits `GEMINI_API_KEY`
    from Workstream A), temperature 0.
  - **Tools = thin READ-ONLY callers of EXISTING functions/routers** (in-process preferred), each
    returning structured data *with citations/sources*, none making a pass/fail decision:
    `search_codebook(query)` (→ `copilot._hybrid_retrieve`), `query_knowledge_base(corpus, query)`
    (→ `Corpus.query`), `get_open_ncrs(document_id?)` (READ already-computed NCRs — NOT a new
    verdict), `get_schedule_risk()`, `get_supply_chain_status()`.
  - **Memory:** a LangGraph **Mongo checkpointer** (`langgraph-checkpoint-mongodb`, confirm name)
    keyed by `thread_id = session/user`, on the same Mongo added for the audit ledger (Workstream D).
    This **replaces** any hand-rolled history — do NOT also build a separate history collection.
  - **Abstention respected:** retrieval below floor → "no confident answer in the project corpus"
    (mirror `copilot._RETRIEVAL_FLOOR = 0.40`); never fabricate.
- API: new `POST /api/copilot/chat` (multi-turn: `thread_id` + `message`) returning the existing
  `RFIAnswer`-shaped payload (`answer`, `sources`, optional `seen_before`) + `thread_id`. Keep the
  existing single-shot `/api/copilot/ask` untouched (current UI + offline fallback).
- Gate on `config.COPILOT_AGENT_ENABLED` (default `0`) **and** a present `GEMINI_API_KEY`.
- `backend/requirements.txt`: add `langgraph`, `langchain-google-genai`,
  `langgraph-checkpoint-mongodb` (confirm exact names/versions at build).
- `backend/app/config.py`: `COPILOT_AGENT_ENABLED = os.getenv("COPILOT_AGENT_ENABLED","0")=="1"`.

**Fallback (HARD RULE — keyless boot must survive):** flag off or no `GEMINI_API_KEY` →
`/api/copilot/chat` and the Telegram bot **bypass LangGraph entirely** and fall back to the existing
cited-RAG `copilot.answer()` (doc-only, single-shot). **Import LangGraph lazily inside the agent
module, guarded by the flag** — a LangGraph import must never crash a keyless startup.

**Frontend:** Copilot page keeps working on `/api/copilot/ask`; optionally switch to
`/api/copilot/chat` with a persisted `thread_id` (localStorage) so it remembers the conversation —
keep the mock-fallback convention (`frontend/lib/api.ts` + `mocks.ts`).

**Verify:** keyless (flag off/no key) → Copilot + Telegram answer via existing RAG, app boots offline;
agent on → "any open NCRs on the submittal, and is the cooling shipment delayed?" calls
`get_open_ncrs` + `get_supply_chain_status` for a cited multi-pillar answer, and a follow-up ("what
about the transformer?") resolves via `thread_id` memory; confirm `copilot_agent.py` imports nothing
from `checks.py`/`rule_eval.py` and no tool returns a verdict; `python -m eval.run_eval` unaffected.

---

### G. DigitalOcean — deploy guide only (deferred)

**Goal:** Write `digitalocean.md` at repo root; do **not** implement/deploy now (credits uncertain).

**Contents:** App Platform spec per service — `backend` (Python buildpack,
`uvicorn app.main:app --host 0.0.0.0 --port $PORT`, health `/api/health`), `standards-service` (same,
health `/health`), `frontend` (Node, `next build`/`next start -p $PORT`), `telegram-bot` (worker, no
port), and **Actian VectorAI DB** container. Managed MongoDB vs Atlas via `MONGODB_URI`. Env checklist
(the §9 table). A Droplet + reverse-proxy alternative. Note the Python 3.12 pin.

---

### H. Narrative & docs

- This file (`hexafalls_plan.md`) at repo root.
- Update `README.md` top section to the new positioning (§2) — keep all integrity caveats; **no
  asserted numbers**; keep "what's real vs representative."
- Create `docs/HEXAFALLS_PITCH.md` (or reuse `docs/DEMO_STORY.md`) with the demo arc (§2) and the exact
  click-path for each sponsor moment. If `docs/` drift is noticed, suggest the `docs-steward` agent
  rather than hand-editing many docs.
- Fix or explicitly caveat the known **`gaudi.local` dead citation links** if touching citations
  (existing landmine — ~13 of 24 `verify_url`s).

---

## 7. Build order & "if time runs short"

0. **Git reset (user-confirmed):** print `git remote get-url origin` (save it — `git@github.com:AwkJay/sitemind.git`), then `rm -rf .git && git init` for a fresh HexaFalls history. Do NOT re-add the remote or push (user does that). Confirm `hexafalls_plan.md` present; create `.env` scaffolding from the examples.
1. **A. Gemini prose** (quick win).
2. **B. Gemini vision** (multimodal wow).
3. **B2. Tiered verdicts** (CORE scaling upgrade). Its step-1 `rule_eval.py` is pure Python — start
   it in parallel any time; the LLM-extraction step needs A. Needs `RETRIEVAL_ENABLED`.
4. **C. Actian VectorAI** ($1,000 track — needs Docker + corpus load + parity eval).
5. **D. MongoDB audit ledger** (narrative backbone).
6. **E. Solana notarization** (depends on D; the money shot).
7. **F1. ElevenLabs + Telegram** (field-demo flash).
8. **F2. Copilot LangGraph edge** (needs A + D/Mongo; multi-pillar project-brain).
9. **G. `digitalocean.md`** (doc only).
10. **H. README + pitch/demo-story**.

**Prize-weighted priority if the clock runs out:** **B2 (core scaling story — the answer to "does it
only handle 17 checks?") → C (Actian $1,000) → A+B (Gemini) → D+E (Mongo+Solana transparency story) →
F1 (ElevenLabs/Telegram)**. F2 (LangGraph copilot), G, and the `copilot.py` Actian stretch are the
first to cut. Note: B2 step 1 (`rule_eval` + tests) is pure Python and cheap — do it even if the LLM
extraction (step 4) gets cut, so the tiered UI still demos with a hand-written rule.

---

## 8. Global verification checklist (before the demo)

- [ ] Keyless boot: unset all new keys → backend + frontend start, compliance + commissioning work,
      `/api/health` shows `offline`, no crashes.
- [ ] `python -m eval.run_eval` and every `backend/eval/run_*_eval.py` produce **unchanged** reports.
      Retrieval evals unchanged with `RETRIEVAL_VECTOR_STORE=numpy`.
- [ ] `run_actian_parity_eval.py` passes against a live Actian instance.
- [ ] Gemini: `/api/health` shows `provider: gemini`; prose is model-written; vision reads an image and
      still passes `verify_spans`.
- [ ] B2 tiered verdicts: `pytest backend/tests/test_rule_eval.py` green; with
      `COMPLIANCE_RULE_EXTRACTION=1 RETRIEVAL_ENABLED=1` a rule-less param yields a `computed_draft`
      NCR (real cited clause + two-half UI); bad `clause_phrase` → `unresolved`; footing cover 40 mm
      still `certified`. Flag off → evals byte-identical.
- [ ] F2 copilot edge: flag off/no key → copilot answers via existing RAG, boots offline; flag on →
      multi-pillar cited answer + `thread_id` memory; `copilot_agent.py` imports nothing from
      `checks.py`/`rule_eval.py`.
- [ ] Mongo: ingest writes an audit event with a stable `content_hash`; no-Mongo falls back to JSONL.
- [ ] Solana: anchor → tx on devnet Explorer; verify green; tamper → verify red.
- [ ] Telegram: Hindi voice note → cited Hindi voice + text reply; out-of-scope → graceful abstain.
- [ ] No secrets committed; `.gitignore` covers `.env`, keypair, local ledger.

---

## 9. Consolidated new env vars

| Var | Where | Default | Purpose |
|---|---|---|---|
| `LLM_PROVIDER` | backend | `offline`→`gemini` when key present | select prose LLM |
| `GEMINI_API_KEY` | backend, telegram-bot | — | Gemini access |
| `GEMINI_MODEL` | backend | `gemini-2.5-flash` (confirm id) | Gemini model |
| `GEMINI_VISION_ENABLED` | backend | `0` | enable scanned-drawing extraction |
| `COMPLIANCE_RULE_EXTRACTION` | backend | `0` | enable the computed-draft verdict tier (B2) |
| `COPILOT_AGENT_ENABLED` | backend | `0` | enable the LangGraph copilot edge (F2) |
| `RETRIEVAL_VECTOR_STORE` | backend, standards-service | `numpy` | `numpy` \| `actian` |
| `ACTIAN_URL` | backend, standards-service | `localhost:6574` | Actian gRPC endpoint |
| `MONGODB_URI` | backend | — | Atlas connection (empty → JSONL fallback) |
| `MONGODB_DB` | backend | `sitemind` | audit DB name |
| `SOLANA_ENABLED` | backend | `0` | enable notarization |
| `SOLANA_RPC_URL` | backend | `https://api.devnet.solana.com` | devnet RPC |
| `SOLANA_SECRET_KEY` | backend | — | base58 devnet keypair |
| `TELEGRAM_BOT_TOKEN` | telegram-bot | — | Telegram bot |
| `ELEVENLABS_API_KEY` | telegram-bot | — | STT + TTS |
| `ELEVENLABS_VOICE_ID` | telegram-bot | — | multilingual voice |
| `BACKEND_URL` | telegram-bot | `http://localhost:8000` | Copilot API base |

## 10. Consolidated new files

- `hexafalls_plan.md` (this plan, repo root)
- `backend/app/gemini_vision.py`
- `backend/app/agents/rule_eval.py`, `backend/tests/test_rule_eval.py` (B2 — tiered verdicts)
- `backend/app/agents/copilot_agent.py` (F2 — LangGraph copilot edge)
- `backend/app/retrieval/vector_store.py` (+ copy in `standards-service/app/retrieval/`)
- `backend/app/audit.py`, `backend/app/audit_api.py`
- `backend/app/notary.py`, `backend/scripts/solana_setup.py`
- `backend/eval/run_actian_parity_eval.py`
- `frontend/app/audit/page.tsx`
- `telegram-bot/` (`bot.py`, `requirements.txt`, `run.sh`, `.env.example`)
- `docker-compose.actian.yml`, `digitalocean.md`, `docs/HEXAFALLS_PITCH.md`

## 11. Hard DO-NOTs (repeat)

- Do NOT add any framework to the **verdict core** (`checks.py`, `rule_eval.py`, compliance
  pipeline). **LangGraph is allowed ONLY on the Copilot edge (F2)** — it must never decide pass/fail
  or import from the verdict core. No LangChain legacy `AgentExecutor`/chains, LlamaIndex, CrewAI.
- Do NOT modify `checks.py` decision logic or let any LLM **compute** a verdict — all math lives in
  `checks.py` or `rule_eval.py`; the LLM only *reads* a rule into a spec and *explains*.
- Do NOT let a computed-draft rule be fabricated: `clause_phrase` must be a verbatim substring of the
  retrieved clause or the finding becomes `unresolved`. Do NOT use `eval()` for formulae (AST-only).
- Do NOT let Gemini Vision bypass `verify_spans`; label vision provenance `primary_scan_ocr`.
- Do NOT route `data_loader.py` or the numpy eval reference through Actian/Mongo by default.
- Do NOT break keyless OFFLINE boot; every integration degrades to a clean no-op.
- Do NOT commit secrets; Solana is **devnet only**.
- Do NOT overclaim ("stops corruption") or assert any number not produced by an eval run.
