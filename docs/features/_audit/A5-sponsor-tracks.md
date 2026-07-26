# A5 — Sponsor-track integration audit

Audited live against the running stack: backend `localhost:8000`, frontend `localhost:3000`,
Docker, and process list, on 2026-07-25. Every claim below is either a direct file:line read or a
live command run in this session (commands and raw output are inlined where they matter). Nothing
here is inferred from documentation without an independent check.

Live state snapshot at time of audit:
```
GET /api/health -> {"status":"ok","offline_mode":false,"provider":"gemini",
  "langfuse_enabled":true,"vector_store":"numpy","audit_backend":"local_jsonl"}
docker ps -> actian_vectorai_db (actian/vectorai:latest) Up 21 hours, ports 6573-6575
ps aux | grep bot.py -> awni  82597  ...  python bot.py   (running, started 01:09)
```

---

## 1. Actian VectorAI DB

**Status: FLAG-GATED-OFF (currently), but a genuine, working, independently-proven integration — not a stub.**

The live backend is answering retrieval queries with `vector_store: numpy` right now
(`/api/health`). `RETRIEVAL_VECTOR_STORE` is **not set** in `backend/.env` (`grep -c
"^RETRIEVAL_VECTOR_STORE=" .env` → `0`), so `config.py:143` defaults it to `"numpy"`. The Actian
path is real and does run when the flag is flipped, but it is off in the configuration actually
running.

**What it actually does** — `backend/app/retrieval/vector_store.py`:
- `NumpyVectorStore.search()` (lines 33-43): the original brute-force `matrix @ query_vector`
  cosine search, extracted unchanged into this module — this is what's live now.
- `ActianVectorStore` (lines 46-93): a real gRPC client (`actian_vectorai` package, `v1.0.2`,
  confirmed installed: `pip show actian-vectorai-client` → `Version: 1.0.2`) against a real running
  container. `_connect()` (56-67) lazily imports and connects; `ensure_collection`/`upsert`/`search`
  (69-93) are genuine collection-create / point-upsert / kNN-search calls, not mocked.
- Caller wiring in `backend/app/retrieval/index.py`: `_rebuild_indices()` (105-125) upserts into
  Actian only if `RETRIEVAL_VECTOR_STORE == "actian"`, wrapped in try/except that falls back to
  numpy with a logged warning on any failure (120-125). `_dense_search()` (127-139) same pattern.
  Numpy is *always* the fallback and the only path a delete of the Actian branch would remove.

**Container state (verified live):**
```
docker ps: actian_vectorai_db, Up 21 hours, ports 6573 (REST) / 6574 (gRPC) / 6575 (LocalUI)
GET localhost:6573/collections -> {"structural_standard_codes","manak_structural"}
GET localhost:6573/collections/structural_standard_codes ->
  points_count: 6206, indexed_vectors_count: 6206, health_status_ext: "HEALTH_GREEN"
GET localhost:6573/collections/manak_structural ->
  points_count: 6206, health_status_ext: "HEALTH_RED" (stale/earlier collection, unused by current code)
```

**Community Edition 5,000-vector cap question — answered, and it contradicts a project doc.**
`docs/gaps.md:88-91` claims the corpus is "well under 5000 vectors" and the cap hasn't been hit.
That is **false as currently loaded**: the live `structural_standard_codes` collection holds
**6,206 points** — over the documented 5,000-vector Community Edition cap — and reports
`HEALTH_GREEN` with `indexed_vectors_count: 6206`. Either the cap is not actually enforced by this
container/version, or the 30-day trial license mentioned in `docs/gaps.md:88-89` was in fact
applied (its LocalUI step was reported as "never pasted in"). This is an unresolved discrepancy
between two directly-observed facts (container state vs. `docs/gaps.md`) — flag it, don't repeat
either claim uncaveated.

**Parity eval — what it actually proves.** `backend/eval/run_actian_parity_eval.py` explicitly does
**NOT** assert float/cosine equality (lines 6-11, 142-145 in the report's own `method` field):
it asserts (a) Actian's top-hit `document_id` matches numpy's top-hit `document_id` for 2
known-answer queries, and (b) the same `RETRIEVAL_FLOOR` abstention gate rejects a gibberish query.
Report at `backend/eval/actian_parity_report.json` (dated Jul 25 00:31, re-read live this session):
`"status": "ran", "n_cases": 5, "n_pass": 5, "accuracy": 1.0"` — genuinely passed, not stale/fake
(the script fails loudly with `status: actian_unreachable` and exit 1 if the container isn't up —
confirmed by reading the eval's own fail-closed branch, lines 67-87).

**What breaks if you delete it:** nothing in production right now — the live server runs on numpy
by default and the Actian branches are wrapped in try/except with a numpy fallback. Deleting
`ActianVectorStore` and the `"actian"` branches in `index.py` would lose: the parity eval itself,
the `docker-compose.actian.yml` capability, and the sponsor-track story — but zero live-app
behavior, since nothing depends on the Actian path being available.

**Env flags:**
| Flag | Default | Currently set to |
|---|---|---|
| `RETRIEVAL_VECTOR_STORE` | `numpy` (`config.py:143`) | unset → `numpy` (confirmed live) |
| `ACTIAN_URL` | `localhost:6574` (`config.py:144`) | unset → default |

**UNVERIFIED:** whether the 6,206-vector load genuinely exceeds a real enforced cap, or whether
Community Edition's cap claim in `docs/gaps.md` is itself stale/wrong — I could not find an
authoritative Actian doc in-repo confirming the cap is enforced at write time vs. just a licensing
term. Also unverified: whether `RETRIEVAL_VECTOR_STORE=actian` has ever been the *live* app
config (as opposed to only the eval script temporarily setting it in-process) — no evidence either
way was found in logs.

---

## 2. ElevenLabs (Telegram field bot)

**Status: LIVE (process running), component-level verified, but end-to-end phone round-trip is UNVERIFIED — the project's own docs say so.**

Bot process confirmed running: `ps aux` → `awni 82597 ... python bot.py` (started 01:09, still up).

**APIs used** — `telegram-bot/bot.py`:
- STT: `_eleven.speech_to_text.convert(model_id="scribe_v1", file=("voice.ogg", ogg_bytes,
  "audio/ogg"))` (lines 137-142) — ElevenLabs Scribe.
- TTS: `_eleven.text_to_speech.convert(text=text, voice_id=ELEVENLABS_VOICE_ID,
  model_id="eleven_multilingual_v2", output_format="opus_48000_128")` (lines 145-158). The inline
  comment (152-154) claims this was "verified against Telegram's sendVoice requirement live this
  session" — `opus_48000_128` is genuinely an Ogg/Opus container at 48kHz/128kbps, which is what
  Telegram's `sendVoice` requires (Opus-encoded OGG). This audit did not re-send a real voice note
  to re-confirm the claim; it is architecturally correct on inspection but not independently
  re-verified end-to-end here (see below).
- Translation is Gemini, not ElevenLabs (`_gemini_translate`, lines 93-112) — a separate call from
  the backend's own Gemini use, correctly scoped as translation-only, not verdict logic.

**Backend endpoint called:** `POST /api/copilot/chat` (line 174, `ask_copilot()`) — **not**
`/api/copilot/ask`. This matters because `docs/features.md:171` still says the bot is "a pure
client of `POST /api/copilot/ask`" — **that line is stale/wrong**; the code and `docs/gaps.md:40-51`
both confirm it was rewired to `/chat` on 2026-07-25 specifically because `/ask` had no access to
NCRs/schedule/supply-chain tools. Flag this contradiction if the pitch deck pulls from
`features.md`.

**Reply cache:** yes, in-process only — `OrderedDict`, FIFO-evicted at 200 entries (lines 70-88),
keyed on `(question_en, original_text)`. Not persisted to disk or DB; reset on every bot restart.
Purpose is stated as quota/consistency, not source-of-truth (docstring, lines 63-69).

**Has a real end-to-end voice round trip ever been verified, or only component-level?**
Per the project's own `docs/gaps.md:49-51` (item 4): *"Still not tested from an actual phone —
that's the one honest gap left here; everything else (endpoint, flags, caching, graceful fallback)
is verified."* This audit did not attempt a live phone test either (would require sending a real
Telegram voice message and consuming ElevenLabs/Gemini quota, out of scope per instructions). So:
**component-level and code-level verified; genuine phone-to-phone round trip is UNVERIFIED, and the
project's own docs already say so — do not claim it was demoed end-to-end.**

**Env flags:**
| Flag | Required/optional | Notes |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | required (`bot.py:52`, hard `os.environ[...]`, crashes on missing) | |
| `ELEVENLABS_API_KEY` | required (`bot.py:53`, same) | |
| `ELEVENLABS_VOICE_ID` | optional, defaults to a fixed voice id (`bot.py:54`) | |

**What breaks if you delete it:** the entire Telegram field-bot capability — it's a standalone
process with no other code depending on it (confirmed: `grep` for `telegram` outside
`telegram-bot/` and docs turned up nothing in `backend/app/`). The backend's `/api/copilot/chat`
endpoint is unaffected either way.

**UNVERIFIED:** genuine phone-to-phone voice round trip (see above, openly gapped in the repo's own
`docs/gaps.md`). Whether the currently-running bot process (PID 82597) has received and correctly
answered any real Telegram message this session — process liveness was confirmed, message handling
was not (would require sending a live message; not done here per scope).

---

## 3. Solana

**Status: LIVE — SOLANA_ENABLED=1, and this audit independently confirmed two REAL devnet transactions exist on-chain. But the app's own on-chain verify check is currently returning a false negative for both of them — a live, reproducible bug, not a hypothetical one.**

`SOLANA_ENABLED=1` is set in `backend/.env` (confirmed by grep of the flags-only view; comment
in `.env` notes it was "funded via https://faucet.solana.com on 2026-07-24").

**Trace of `/api/audit/{id}/anchor`** (`backend/app/audit_api.py:82-93`): looks up the event,
calls `notary.anchor_hash(doc["content_hash"])`, writes the result into the event's `solana`
sub-doc only (`audit.update_solana`) — `payload`/`content_hash` are never touched, confirmed by
reading `audit.py:210-233`.

**Trace of `notary.anchor_hash`** (`backend/app/notary.py:31-76`): builds a single SPL Memo
instruction (program id `MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr`, the real, already-deployed
Solana Memo program) whose data IS the raw content_hash bytes, signs with `config.SOLANA_SECRET_KEY`,
sends via `AsyncClient(config.SOLANA_RPC_URL)`, confirms, and returns `{status: "anchored", tx_sig,
slot, cluster}`. Not simulated — no mock/stub in this path.

**Independently verified live, this session** (direct RPC call to Solana's own public devnet
cluster, bypassing the SiteMind backend entirely):
```
curl -s https://api.devnet.solana.com -X POST -d '{"method":"getTransaction",
  "params":["2wjsGR6xjvnnr7wChYbc6Gdgsy5MmaEEj1ijrMgisR5rU9fL9TeAL3N8nDjyQzc2tbewb6XhnphA9hYKCBW4wXce", ...]}'
-> logMessages: 'Program MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr invoke [1]'
             'Program log: Memo (len 64): "d14a6e74bd05f0786610ab429e8df9f4c5aff8f17f6d665aad9e5268de41b3de"'
             '... success'
-> slot: 478588513 (matches the value stored in SiteMind's own audit event)
```
`GET /api/audit/AUD-ba49ab669ce7` → `content_hash: "d14a6e74bd05f0786610ab429e8df9f4c5aff8f17f6d665aad9e5268de41b3de"`
— **exact byte-for-byte match** with the on-chain memo. This is a genuinely real, independently
verifiable devnet anchor. Two such anchored events exist in the ledger (`AUD-ba49ab669ce7`,
`AUD-eb3559c874af`); the other 11 events in the ledger show `solana.status: "disabled"` (anchored
was attempted while the flag was off at some earlier point, or never anchored).

**Bug found live:** `POST /api/audit/{id}/verify` on **both** genuinely-anchored events returned
`{"mongo_intact": true, "chain_intact": false}` — i.e., the app's own on-chain check says the
anchor does *not* match, despite the independent RPC check above proving it does. Root-caused live
in this session: the `solana` Python package's vendored HTTP client (an internally-renamed
`httpx2`/`httpcore2` fork) hits a `ConnectTimeout` against `api.devnet.solana.com` from this
environment on 3/3 attempts, while plain `httpx` and `curl` both succeed (curl instantly; plain
httpx in ~5s) — `notary.verify_anchor()` (`notary.py:132-162`) swallows **all** exceptions into
`return False` (line 161-162), so a network timeout is indistinguishable from a genuine tamper at
the API layer. The frontend (`frontend/app/audit/page.tsx:224-225`) renders this as a red **"chain
mismatch"** badge — visually identical to real tampering. **This is a live, demo-visible landmine
right now**: clicking "Verify" on either of the two real anchored records currently shows a false
"mismatch." Whether this reproduces on the actual demo machine/network (vs. being specific to this
audit's sandboxed egress) is unconfirmed — but it is reproducible on the exact host serving
`localhost:8000` right now, since the `curl -X POST localhost:8000/api/audit/.../verify` calls
(not the isolated Python repro) also returned `chain_intact: false`.

**`mongo_intact` / `chain_intact` semantics** (`audit_api.py:110-124`, `audit.py:164-177`):
- `mongo_intact`: recomputes `content_hash` over the stored `hashed_fields` and compares to the
  stored `content_hash` — detects direct DB/JSONL tampering (someone editing the record out of
  band). Deliberately does **not** cover LLM prose fields (`finding`/`why_it_matters` etc.) which
  are excluded from `hashed_fields` on purpose (`audit.py:170-173`) since those are
  non-deterministic wording, not the decision itself.
- `chain_intact`: `None` until anchored; once anchored, fetches the tx by signature and checks the
  on-chain memo bytes equal `content_hash` — detects tampering with the *stored* hash after the
  fact (the chain is the independent witness). Currently returning false negatives, see bug above.

**Idempotency of the ledger — proven live, not asserted:**
```
POST /api/audit/seed (1st call) -> {"new_records": 0}
POST /api/audit/seed (2nd call) -> {"new_records": 0}
GET /api/audit?limit=1000 count before and after: 13, 13 — no duplicates.
```
(Ledger was already seeded from an earlier session; re-running twice in this audit produced zero
duplicates either time, confirming `content_hash`-keyed idempotency genuinely works, not just as
claimed in the docstring.)

**Audit Ledger page when Solana is off:** `frontend/app/audit/page.tsx:26` — a dedicated status
badge `"Solana disabled"` (grey), confirmed by direct code read; `docs/features.md:166-167`
corroborates: `SOLANA_ENABLED=0 (the default) → rows show "Solana disabled," ledger still works
fully without it.` Not independently re-tested with the flag flipped off this session (it's
currently on) — treat that specific UI state as UNVERIFIED-by-this-audit, code-confirmed only.

**Env flags:**
| Flag | Default | Currently |
|---|---|---|
| `SOLANA_ENABLED` | `0` (`config.py:157`) | `1` (confirmed in `.env`) |
| `SOLANA_RPC_URL` | `https://api.devnet.solana.com` (`config.py:158`) | devnet (confirmed) |
| `SOLANA_SECRET_KEY` | `""` | set (not printed) |
| `SOLANA_CLUSTER` | `devnet` (`config.py:160`) | `devnet` |

**What breaks if you delete it:** the audit ledger keeps working exactly as-is (JSONL/Mongo,
idempotent, hash-verified) — `notary.py` is fully additive per its own docstring (lines 12-14,
every function no-ops `{"status": "disabled"}` when off). Deleting it loses only the on-chain
notarization claim and the two real anchored transactions' provenance.

**UNVERIFIED:** whether the `chain_intact: false` bug reproduces on a non-sandboxed network (it may
be an artifact of this audit environment's egress, not the actual demo host) — flagged as a
concrete thing to re-test on the real demo machine before presenting, not dismissed as environment
noise, since it also reproduced through the actual running backend (`localhost:8000`), not just
the isolated repro script.

---

## 4. Gemini API

**Status: LIVE for prose (multiple real call sites, confirmed no verdict path). GEMINI_VISION_ENABLED flag exists but is CONFIRMED dead/unused — never built. LangGraph agent (F2) confirmed read-only, 5 tools.**

`/api/health` confirms `"provider": "gemini"` live right now, `LLM_PROVIDER=gemini` in `.env`.

**Every Gemini call site, found by grepping all callers of `llm.complete_text`/`complete_json` plus
direct `genai`/`ChatGoogleGenerativeAI` usage:**
1. `backend/app/llm.py:107-121` (`_gemini_complete`) — the single shared wrapper for the
   `LLM_PROVIDER=gemini` case (also serves `openai`/`anthropic`/`codex`/offline via sibling
   functions). Called by:
   - `backend/app/agents/copilot.py:261` — single-shot Copilot answer prose (`/api/copilot/ask`).
   - `backend/app/agents/compliance.py:105` — NCR "senior advisory" explanatory prose.
   - `backend/app/agents/compliance.py:220` (`_extract_rule`) — **the B2 tiered-compliance path**:
     LLM reads a real clause and returns a structured `ExtractedRule` (JSON: kind/operator/
     threshold/unit/clause_phrase, system prompt at lines 190-203 explicitly instructs "You never
     decide pass/fail — you only perceive what the clause says").
2. `backend/app/agents/copilot_agent.py` — a **separate** direct call path via
   `ChatGoogleGenerativeAI` (`langchain_google_genai`, line ~190) inside `_get_agent()` — this is
   the F2 LangGraph conversational edge behind `COPILOT_AGENT_ENABLED`, distinct from `llm.py`'s
   wrapper (it needs LangChain's tool-calling model interface, not the plain-text wrapper).
3. `telegram-bot/bot.py:93-112,100-108` — a **third**, independent Gemini call (translation only,
   the bot's own `google.genai` client, not routed through the backend at all).

**Proof there is no import path from the LLM layer into the verdict core:**
```
grep -n "^import\|^from" app/agents/checks.py app/agents/rule_eval.py
-> checks.py: only stdlib (typing)
-> rule_eval.py: __future__, ast, operator, ..schemas.ExtractedRule
grep -rn "from .llm\|from ..llm\|import llm" app/agents/*.py -> zero matches
```
Neither `checks.py` (the "certified"-tier pre-vetted rules) nor `rule_eval.py` (the "computed-draft"
tier that consumes the LLM's `ExtractedRule`) imports `llm.py`, `google.genai`, or anything
LLM-related, directly or transitively. The actual verdict computation is confirmed at
`compliance.py:299`: `verdict, detail = rule_eval.evaluate(rule, param)` — a plain Python function
(`ast`/`operator`-based expression evaluation) computes the verdict from the structured rule; the
LLM's job stops at producing that structured, verbatim-anchored rule. **This is a real, verifiable
separation, not just a docstring claim.**

**GEMINI_VISION_ENABLED — confirmed dead, never built:**
```
grep -n "GEMINI_VISION" app/config.py -> only the flag definition, config.py:46
grep -rn "GEMINI_VISION" . --include="*.py" (whole backend) -> that single line, nothing else
```
The flag is defined (`config.py:46`, defaults `"0"`) and **read nowhere else in the codebase** —
no code branches on it, no vision call exists anywhere. This matches (and independently confirms)
`docs/gaps.md:52-54`'s own admission: *"Workstream B (Gemini Vision...) was never started...
Explicitly skipped per direct instruction... Not a bug, just genuinely not built — don't claim it
works."* **Confirmed: this must not appear in the pitch as a working capability.**

**LangGraph agent tools — all 5, confirmed read-only** (`copilot_agent.py:68-166`):
| Tool | What it reads | Mutates? |
|---|---|---|
| `search_codebook` (74-82) | hybrid BM25+dense retrieval over the standards corpus | No |
| `query_knowledge_base` (84-117) | a named RETRIEVAL_ENABLED corpus | No |
| `get_open_ncrs` (119-146) | already-computed `compliance.evaluate()` results | No — docstring explicitly: "does NOT compute a new verdict" |
| `get_schedule_risk` (148-154) | already-computed `schedule_risks()` | No |
| `get_supply_chain_status` (156-164) | already-computed risks/alerts | No |

No tool in this list calls anything with write/insert/update semantics; each is a thin read wrapper
around an already-computed pillar result. `_get_checkpointer()` (199-215) uses `MongoDBSaver` for
cross-message memory only if `MONGODB_URI` is set (it is not, live — see §5); otherwise the agent
runs but stateless per call (confirmed by the `.env` comment on `COPILOT_AGENT_ENABLED`).
Confirmed LangGraph/LangChain imports are isolated to exactly `copilot_agent.py` and `config.py`
(the flag definitions) — nowhere else in `backend/app/`, matching the plan's "LangGraph ONLY on the
Copilot edge" rule.

**Env flags:**
| Flag | Default | Currently |
|---|---|---|
| `GEMINI_API_KEY` | `""` (`config.py:44`) | set (not printed) |
| `GEMINI_MODEL` | `gemini-flash-latest` (`config.py:45`) | default |
| `GEMINI_VISION_ENABLED` | `0` (`config.py:46`) | unset → off, and unused regardless |
| `LLM_PROVIDER` | auto-detects from keys (`config.py:67-79`) | `gemini` (explicit in `.env`) |
| `COPILOT_AGENT_ENABLED` | `0` (`config.py:172`) | `1` (confirmed in `.env`) |

**What breaks if you delete it:** all NCR prose, the single-shot Copilot answer prose, and the B2
computed-draft tier's rule extraction fall back to their offline/deterministic paths (`llm.py`
returns `""`/`None` on any failure by design, callers already handle that) — no crash, just loss of
prose quality and loss of the computed-draft tier (falls back to "unresolved" NCRs, per
`compliance.py:240-250`'s `_unresolved_ncr`). The LangGraph agent and Telegram bot's translation
would stop working entirely (they have no non-Gemini fallback for their own calls).

**UNVERIFIED:** live, fresh Gemini responses were not re-triggered in this audit (explicitly
out of scope — quota is documented elsewhere as likely exhausted, `docs/gaps.md:56-62`). All
findings above are from static code/import analysis, not a live model call.

---

## 5. MongoDB

**Status: FLAG-GATED-OFF / running on the JSONL fallback right now — confirmed live, not inferred.**

`/api/health` → `"audit_backend": "local_jsonl"`. Confirmed independently: `grep -c
"^MONGODB_URI=" backend/.env` → `0` — the variable is not set at all (not just empty), so
`audit.py`'s `_mongo_collection()` (`audit.py:57-77`) short-circuits at line 64
(`if not config.MONGODB_URI: return None`) before ever attempting a connection. Same is true for
the LangGraph checkpointer (`copilot_agent.py:199-215`, `_get_checkpointer()` returns `None` at the
same guard) — confirmed both audit ledger and agent chat memory are on their no-Mongo fallback
paths simultaneously right now.

**Content hash — computed over exactly what, and what's excluded:**
`audit.py:49-54` (`content_hash`): `hashlib.sha256` over `json.dumps(payload, sort_keys=True,
separators=(",", ":"))` — canonical JSON, deterministic. Critically, it's computed over
`hashed_fields`, not the full `payload` (`audit.py:117-146`, `record_event`): `hashed_fields =
dedup_key if dedup_key is not None else payload`. For NCR events specifically, the dedup key
deliberately **excludes LLM-generated prose** (`finding`, `why_it_matters` — confirmed by the
docstring at `audit.py:170-173` and the general `record_event` rationale at 123-129): *"payload may
legitimately contain non-deterministic prose... callers whose payload mixes deterministic decision
fields with LLM prose should pass a dedup_key containing only the deterministic fields."* This is a
real, load-bearing design choice, not incidental — it's what makes `seed_preloaded()`'s
already-recorded-vs-new distinction (and the whole append-only/idempotent guarantee) survive the
LLM rephrasing the same finding differently across two runs.

**Append-only + idempotent — proven live in this session, not just asserted:**
```
POST /api/audit/seed -> {"new_records": 0}
POST /api/audit/seed -> {"new_records": 0}   (called again, immediately after)
GET /api/audit?limit=1000 -> 13 events both before and after both calls
```
No duplicates were created by calling `/seed` twice. `_jsonl_record()` (`audit.py:86-99`) is the
mechanism: under a `threading.Lock`, it linear-scans existing lines for a matching `content_hash`
before appending — genuinely idempotent, confirmed by direct behavior, not just by reading the
code.

**Env flags:**
| Flag | Default | Currently |
|---|---|---|
| `MONGODB_URI` | `""` (`config.py:149`) | unset (confirmed: 0 matches in `.env`) |
| `MONGODB_DB` | `sitemind` (`config.py:150`) | default (irrelevant while URI is unset) |

**What breaks if you delete Mongo support entirely:** nothing in the currently-running app — it's
already on the JSONL fallback. You'd lose: multi-process/multi-instance consistency (JSONL is a
single local file with an in-process lock, not safe across multiple backend replicas), and the
LangGraph agent's cross-message conversation memory would be permanently stateless-per-call instead
of conditionally so.

**UNVERIFIED:** this audit did not spin up a real MongoDB instance to confirm the Mongo-connected
code path (`pymongo.MongoClient`, unique index on `content_hash`, `MongoDBSaver` checkpointer)
actually works end-to-end — only the JSONL fallback was live-exercised. The Mongo branch is
plausible on code inspection (standard pymongo usage) but not independently run in this audit.

---

## Summary table

| # | Track | Status | Live right now? | Real capability or thin wrapper? | Biggest risk if overclaimed |
|---|---|---|---|---|---|
| 1 | Actian VectorAI DB | FLAG-GATED-OFF (numpy is live default) | Container up, parity eval passed 5/5 live-verified | Real: genuine gRPC client, real 6,206-vector collection, proven parity eval | Corpus (6,206 chunks) actually exceeds the documented 5,000-vector Community Edition cap — `docs/gaps.md` claim of "well under 5000" is contradicted by the live container |
| 2 | ElevenLabs (Telegram bot) | LIVE (process running) | Yes, PID confirmed running | Real: genuine Scribe STT + multilingual TTS calls, correct Ogg/Opus format for Telegram | Never tested from an actual phone — project's own docs already admit this; do not claim a demoed voice round-trip |
| 3 | Solana | LIVE (SOLANA_ENABLED=1) | Yes — 2 real, independently-verified devnet transactions found on-chain | Real: genuine SPL Memo anchoring, hash matches on-chain exactly | The app's own "Verify" button currently shows a false "chain mismatch" for both real anchored records — a live, reproducible, demo-visible bug |
| 4 | Gemini API | LIVE (prose only, multiple call sites) | Yes, `provider: gemini` confirmed | Real: 3 independent call sites, proven no import path into the verdict core | `GEMINI_VISION_ENABLED` flag exists but is 100% dead code — zero other references anywhere; must not be presented as a working feature |
| 5 | MongoDB | FLAG-GATED-OFF (JSONL fallback live) | No — `MONGODB_URI` unset, confirmed | Real fallback design (not a stub): idempotency proven live via double-seed test, hash-exclusion of LLM prose is a genuine architectural choice | None currently claimed live — just don't say "MongoDB-backed" without the "when configured" caveat |
