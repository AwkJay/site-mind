# A4 — Retrieval Stack Audit

Scope: `backend/app/retrieval/*`, `backend/app/embeddings.py`, `backend/app/codebook_router.py`,
`backend/app/codebook_client.py`, `backend/app/codebook_rest_client.py`, `standards-service/`,
`frontend/app/knowledge-base/page.tsx`, `frontend/app/codebook/page.tsx`,
`frontend/app/codebook/console/page.tsx`.

Audited live against a running backend (`:8000`) and frontend (`:3000`) on 2026-07-25. All
counts/behaviors below were re-verified by direct `curl`, a live re-run of the Actian parity eval,
and a real Playwright browser session — not read off a cached report or docstring.

**Confirmed environment at audit time** (`backend/.env`, flags only):
`LLM_PROVIDER=gemini`, `SOLANA_ENABLED=1`, `COPILOT_AGENT_ENABLED=1`, `RETRIEVAL_ENABLED=1`.
`CODEBOOK_ENABLED` is **not present** in `.env` → defaults to `0` (off). `HF_TOKEN` **is** present
(non-empty, redacted). `RETRIEVAL_VECTOR_STORE` is not set → defaults to `numpy` (confirmed by
`GET /api/health` → `"vector_store":"numpy"`), even though a real Actian container is running.

---

## Summary verdict

- The Knowledge Base retrieval stack (`backend/app/retrieval/`) is **real and currently
  COMPUTED**, not a fixture: live query against `structural_standard_codes` returned a correct,
  real IS 456 clause (cosine score 0.705) for "minimum cover for footings" — verified by direct
  curl, not asserted.
- The "0 docs · 0 chunks" symptom named in the task **could not be reproduced live**. Right now
  the API reports `structural_standard_codes: 17 docs / 6,206 chunks` and
  `sitemind_existing_standards: 2 docs / 29 chunks`, and the Knowledge Base page renders those
  counts correctly in a real browser. Root cause of the *historical* bug is identified below (§2)
  from source + `docs/gaps.md` — it predates the in-repo migration of the structural corpus and
  has since been fixed.
- The "offline, no API key" claim is **false for semantic search**, true for everything
  deterministic. `app/embeddings.py` hard-`raise`s with no local fallback if `HF_TOKEN` is unset.
  `backend/app/retrieval/embeddings_provider.py` (a separate module for the Knowledge Base/
  Codebook stack) has a nominal `openai -> hf -> local` fallback chain, but the `local` tier
  requires `sentence-transformers`, which is **not installed** in `backend/.venv` — confirmed by a
  failed import. So in this environment, semantic retrieval works ONLY because `HF_TOKEN` happens
  to be set; with it unset, both embedding paths raise/fail.
- Codebook (`standards-service/`) is **currently down** (confirmed: `curl localhost:8010/api/health`
  fails to connect) and `CODEBOOK_ENABLED=0`, so `/api/codebook/*` isn't mounted (`{"detail":"Not
  Found"}`) and the `/codebook` and `/codebook/console` frontend pages both render clean
  "not enabled" states — verified live in a real browser, no crash.
- The Actian VectorAI DB path is real and **currently passes its own parity eval live** (5/5,
  re-run during this audit, not read from the stale JSON report only), but it is **not the active
  vector store** — `RETRIEVAL_VECTOR_STORE=numpy` is the default and nothing in `.env` overrides it,
  so the app is serving all Knowledge Base queries off the numpy path right now, despite the
  Actian container being up.
- `manak_structural` → `structural_standard_codes` rename is **complete in all live code paths**
  (backend and standards-service copies both), including the corpus name returned by the API.
  Two docs files still show the old name as if current: `docs/ARCHITECTURE.md` (diagram + prose,
  not corrected) — see stale-claims section.

---

## Per-route table

| Route | Method | Verdict | File:line |
|---|---|---|---|
| `/api/retrieval/corpora` | GET | COMPUTED (live in-memory corpus registry, lazily built) | `backend/app/retrieval/router.py:66-78` |
| `/api/retrieval/corpora/{name}/documents` | GET | COMPUTED (derived from live chunk list) | `backend/app/retrieval/router.py:81-101` |
| `/api/retrieval/upload` | POST | COMPUTED (real chunking + embedding + BM25 index build, persisted to disk) | `backend/app/retrieval/router.py:47-63`, `backend/app/retrieval/ingest.py:65` |
| `/api/retrieval/query` | POST | COMPUTED (hybrid BM25+dense RRF fusion, real cosine scores) | `backend/app/retrieval/router.py:104-141`, `backend/app/retrieval/index.py:162-191` |
| `/api/codebook/corpora` | GET | COMPUTED when reachable — proxies a real MCP tool call; **503 when standards-service is down** (confirmed: currently down) | `backend/app/codebook_router.py:65-68`, `backend/app/codebook_client.py:87-91` |
| `/api/codebook/search` | GET | COMPUTED when reachable, MCP proxy | `backend/app/codebook_router.py:71-75` |
| `/api/codebook/clause/{doc_id}/{chunk_id}` | GET | COMPUTED when reachable, MCP proxy | `backend/app/codebook_router.py:78-81` |
| `/api/codebook/check`, `/check-upload` | POST | COMPUTED when reachable, MCP proxy | `backend/app/codebook_router.py:84-114` |
| `/api/codebook/console/corpora`, `/console/corpora/{name}/documents`, `/console/upload` | GET/GET/POST | COMPUTED when reachable — plain REST proxy (not MCP) to standards-service's own `/api/retrieval/*` | `backend/app/codebook_router.py:117-155`, `backend/app/codebook_rest_client.py` |
| `standards-service` `/api/retrieval/*` (its own copy) | GET/POST | COMPUTED, independent duplicate stack — currently unreachable (service down) | `standards-service/app/retrieval/router.py` (not directly read this pass; same shape as backend's copy per diff) |
| `standards-service` `/mcp` 4 tools | MCP | COMPUTED when service is up; not tested live this pass (service down) | `standards-service/app/mcp_server.py:248,296,316,357` |

No HARDCODED or pure-FIXTURE routes were found anywhere in this scope — every route either computes
a real result or fails cleanly (503 / 404-not-mounted / disabled UI state).

---

## The offline-claim truth table

| Feature | Needs `HF_TOKEN`? | Needs network? | Needs LLM key? |
|---|---|---|---|
| Compliance HERO (checks.py verdicts) | No | No | No (prose only, optional) |
| Commissioning / Schedule / Supply Chain / Timeline / Cost | No | No | No |
| Copilot dense retrieval (`app/embeddings.py`) | **Yes — hard requirement, no local fallback** (raises `RuntimeError` if unset, `backend/app/embeddings.py:34-39`) | Yes (HF Inference API over HTTPS) | No (prose composer has an offline fallback; retrieval itself does not) |
| Knowledge Base retrieval (`app/retrieval/embeddings_provider.py`) | Yes, in this actual install — the `local` sentence-transformers fallback exists in code (`embeddings_provider.py:59-62,71-74`) but the package **is not installed** in `backend/.venv` (confirmed: `import sentence_transformers`/`torch` fails), so the fallback chain dead-ends and would raise inside `_local_model()` | Yes (for the `hf` tier; `openai` tier if selected) | No |
| Codebook search (standards-service, same embeddings pattern) | Same as above (`standards-service/app/retrieval/embeddings_provider.py` mirrors the backend copy) | Yes | No |
| LLM prose (Compliance advisory, Copilot answers, Codebook check prose) | No | Only if a provider key is set | Governed by `OFFLINE_MODE`; `LLM_PROVIDER=gemini` + `GEMINI_API_KEY` set in this env, so prose is live, not the offline fallback |

**Bottom line:** "runs fully offline, no API key" is true for the five deterministic verdict
pillars and false for every semantic-search feature in this scope. `docs/features.md` already
states this correctly and explicitly (see "Stale-or-wrong claims" — this is a case where the docs
are accurate, not stale).

---

## Frontend page behaviour

### `frontend/app/knowledge-base/page.tsx`
- Availability states: `checking` → skeleton, `disabled`/`unreachable` → `NotEnabledState` card
  (`page.tsx:80-107`), `available` → full UI.
- Live-tested in a real browser (`RETRIEVAL_ENABLED=1`, backend up): correctly rendered
  `structural_standard_codes · 17 docs · 6206 chunks` and `sitemind_existing_standards · 2 docs ·
  29 chunks` as clickable corpus chips, plus a `Vector store: numpy (in-memory)` badge
  (`page.tsx:188-197`) reflecting `GET /api/health`'s `vector_store` field.
- One reproducible UI quirk (not the reported bug): on first paint, the global nav "Mode" indicator
  briefly reads "Mock fallback (backend unreachable)" before the health poll resolves a moment
  later to "Backend live" — a client-side race, not a backend problem. Confirmed by taking two
  snapshots ~1s apart on the same load.

### `frontend/app/codebook/page.tsx` and `frontend/app/codebook/console/page.tsx`
- Both live-tested with `CODEBOOK_ENABLED=0` (the actual current state): both correctly render the
  "Codebook is not enabled on this backend... Start the backend with `CODEBOOK_ENABLED=1`..." message
  (`codebook/page.tsx:96-104`, `codebook/console/page.tsx:68-76`) — no crash, no stale data shown.
- Both pages also have a distinct `unreachable` message (service down but flag on) vs `disabled`
  (flag off) — the copy correctly tells the operator which of the two states they're in.

---

## The 7 questions, answered

**1. The `HF_TOKEN` question — does anything work with zero API keys?**
No semantic-search feature works with zero keys. `backend/app/embeddings.py:34-39` raises
`RuntimeError` immediately if `HF_TOKEN` is unset — there is no local fallback in that module at
all (its own docstring, lines 9-14, explains torch/sentence-transformers were deliberately removed
for a 512MB free-tier RAM ceiling). The separate `backend/app/retrieval/embeddings_provider.py`
*does* have a 3-tier fallback (`openai -> hf -> local`, lines 105-136) and the `local` tier's code
exists (`_local_model()`, lines 58-62, lazy-imports `sentence_transformers`) — but
`sentence-transformers`/`torch` are **not installed** in `backend/.venv`
(`python -c "import sentence_transformers"` fails; not in `requirements.txt`, confirmed by grep).
So the documented fallback chain is real code but a dead end in this actual install: with `HF_TOKEN`
unset and no OpenAI key, `embed()` would raise inside `_embed_local()`'s import. Right now
`HF_TOKEN` **is** set in `backend/.env`, so semantic retrieval is genuinely live (verified: real
IS 456 clause returned for a real query). The deterministic pillars (Compliance, Commissioning,
Schedule, Supply Chain, Timeline, Cost, Knowledge Graph) need no token and were not affected either
way.

**2. Why does the Knowledge Base page show `0 docs · 0 chunks`?**
**Not reproducible right now** — live counts are 17/6,206 and 2/29, confirmed via both `curl` and a
real Playwright browser session. Root cause of the historical bug, reconstructed from source +
`docs/gaps.md`:
- `backend/app/retrieval/filesystem_corpora.py:66-78` (`_structural_md_files()`): if
  `STRUCTURAL_LIB_DIR` doesn't exist on disk, it logs a warning and returns `[]`, and
  `build_structural_standard_codes_corpus()` (line 89-106) then builds a corpus with zero chunks —
  this is silent, not an error the UI would surface distinctly from "genuinely empty corpus".
  The module's own comments (lines 7-17, 49-56) explain that `STRUCTURAL_LIB_DIR` used to point at
  a **separate sibling project directory outside this repo** (`manak-dev`) before the 17 `.md`
  files were copied in-repo to `standards-service/data/structural_corpus/` — if that external path
  had ever been unavailable in an environment, or before the copy-in happened, the corpus would
  have silently built empty, producing exactly a `0 docs · 0 chunks` tile (not a "disabled" state,
  since `RETRIEVAL_ENABLED` being on is a separate condition from the directory existing).
- `docs/gaps.md` item 16 documents an adjacent, now-fixed bug in the same family:
  `copilot_agent.py`'s `query_knowledge_base` tool called `get_corpus()` directly without first
  calling `ensure_filesystem_corpora()`, so it silently returned `[]` regardless of flags — fixed by
  adding the `ensure_filesystem_corpora()` call.
- Currently `STRUCTURAL_LIB_DIR` (`backend/app/retrieval/filesystem_corpora.py:56`) resolves to
  `standards-service/data/structural_corpus/`, which exists and contains 17 `.md` files (confirmed:
  `find ... -name "*.md" | wc -l` → 17) — so this failure mode is closed for the current repo
  layout. UNVERIFIED: whether the *literal* `0 docs · 0 chunks` UI state was ever screen-captured
  from this exact bug vs. a different transient (e.g. `RETRIEVAL_ENABLED=0` giving the "not
  enabled" card, which is visually different, not a 0/0 tile) — I could not find a source or log
  artifact pinning the exact prior observation, only the code path that would produce it.

**3. The `manak_structural` → `structural_standard_codes` rename — any stale references?**
Confirmed clean in all live code. `grep -rn "manak_structural"` across `backend/`, `frontend/`,
`standards-service/` (`.py`/`.tsx`/`.ts`) returns only **historical-narration comments** inside
`filesystem_corpora.py` (both the backend and standards-service copies) and
`run_codebook_tools_eval.py`, all explicitly framed as "renamed from X" — never used as a live
identifier. The API itself returns `"corpus_name":"structural_standard_codes"` (confirmed live).
Two **docs** files still present the old name as current, not historical — see stale-claims below;
that's a documentation gap, not a code gap.

**4. Two parallel retrieval stacks — how do they differ, why both exist, what depends on each?**
`backend/app/retrieval/` and `standards-service/app/retrieval/` are structurally identical forks
(same filenames: `chunker.py`, `embeddings_provider.py`, `filesystem_corpora.py`, `index.py`,
`ingest.py`, `models.py`, `router.py`, `store.py`, `vector_store.py`) but have **diverged** in
content:
- `backend/app/retrieval/` powers the `/knowledge-base` page directly (`RETRIEVAL_ENABLED`), and is
  also imported directly by two eval scripts (`run_retrieval_eval.py`, `run_cross_corpus_eval.py`)
  — `docs/features.md` explains this is *why* it's still live: "predates Codebook, still live
  because 2 eval scripts... import it directly" (`docs/features.md:132-133`, confirmed accurate).
  Its `filesystem_corpora.py` docstring/comments are up to date post-rename (`manak_indexed`
  provenance tag, `STRUCTURAL_LIB_DIR` pointing in-repo to `standards-service/data/structural_corpus/`).
- `standards-service/app/retrieval/` is Codebook's **own internal copy**, used to build its own
  in-process corpora, served only over MCP (+ a REST facade for the Console). Its own
  `filesystem_corpora.py` uses a different provenance tag string (`codebook_verified` vs. the
  backend copy's `manak_indexed`) and its comments narrate an *extra* rename hop
  (`manak_structural -> codebook_structural -> structural_standard_codes`) that the backend copy's
  comments don't mention — i.e., the two copies really did fork and evolve independently, not just
  cosmetically. Functionally though, both now resolve `STRUCTURAL_LIB_DIR` to the physically same
  17-file directory (`standards-service/data/structural_corpus/`, backend via
  `config.BACKEND_DIR.parent / "standards-service" / "data" / "structural_corpus"`,
  standards-service via its own relative-to-self path) — so despite the divergent prose, they'd
  build the same corpus from the same files if standards-service were running (UNVERIFIED live,
  since standards-service is down this session — not exercised).
- **Why both exist**: the retrieval package was built first as backend-embedded (`Phase 3`), then
  Codebook (`standards-service/`) was built later as a "relocated" standalone MCP-serving process
  (`docs/ARCHITECTURE.md:14-15`: "relocates the retrieval package built in the fourth-and-earlier
  passes' Phase 3/3b") — but the backend copy was never deleted because live evals still depend on
  it and the Knowledge Base page was never migrated to call Codebook instead.
- **What depends on each**: Knowledge Base page + `run_retrieval_eval.py`/`run_cross_corpus_eval.py`
  → backend copy only. Codebook page/Console + `run_codebook_tools_eval.py`/
  `run_cross_corpus_eval.py` (standards-service's own copy, per its eval dir) → standards-service
  copy only. The two are not wired together at runtime; `backend/app/codebook_client.py`/
  `codebook_rest_client.py` talk to standards-service **over the network** (MCP/REST), never by
  importing its retrieval code.

**5. `vector_store.py` — does the actian path work? Is a container running? What does the eval prove?**
- A real Actian VectorAI DB Docker container **is running** (confirmed:
  `docker ps` → `actian/vectorai:latest`, container `actian_vectorai_db`, up 21 hours, ports
  6573-6575 mapped).
- The `actian-vectorai-client` Python package **is installed** in `backend/.venv` (confirmed:
  `import actian_vectorai` succeeds, resolves to `.venv/lib/python3.11/site-packages/actian_vectorai/`).
- `RETRIEVAL_VECTOR_STORE` is **not set** in `backend/.env` → defaults to `"numpy"`
  (`backend/app/config.py:143`), confirmed live via `GET /api/health` → `"vector_store":"numpy"`.
  So right now the running app is NOT using Actian for any query, despite the container being up.
- Setting `RETRIEVAL_VECTOR_STORE=actian` changes `Corpus._rebuild_indices()`
  (`backend/app/retrieval/index.py:114-125`) to also upsert every chunk's embedding into an Actian
  collection named after the corpus, and `Corpus._dense_search()` (lines 127-139) to query Actian
  instead of the numpy brute-force matrix — with an automatic fallback to numpy (logged warning) if
  Actian is unreachable at either step (`vector_store.py`'s docstring, lines 14-22, and the
  try/except in both `index.py` methods).
- **`backend/eval/run_actian_parity_eval.py`** proves the Actian-backed corpus's top-hit
  `document_id` matches the numpy-backed corpus's top-hit for 2 hand-verified known-answer queries,
  plus that a gibberish query still abstains via the same `RETRIEVAL_FLOOR` gate — explicitly NOT
  asserting float-identical cosine scores (an ANN backend can legitimately reorder near-ties; see
  the eval's own docstring, lines 3-11). **It currently passes**: I re-ran it live during this audit
  (`RETRIEVAL_VECTOR_STORE=actian python -m eval.run_actian_parity_eval`) and got `5/5 passed
  (accuracy=1.0)` — not just read from the pre-existing `actian_parity_report.json` (which also
  showed 5/5, and matches the fresh run byte-for-byte).

**6. Codebook (MCP client of standards-service) — is the service running, and page behavior?**
`standards-service` is **currently down** — `curl localhost:8010/api/health` fails to connect
(confirmed both via the audit's own curl and by checking no process listens on 8010). Confirmed the
4 MCP tools in `standards-service/app/mcp_server.py`: `list_corpora` (line 248-249),
`search_standards` (line 295-296), `get_clause` (line 315-316),
`check_document_against_corpus` (line 356-357) — matching `codebook_client.py`'s own 4 wrapper
functions exactly. `CODEBOOK_ENABLED` is absent from `.env` → defaults to `0`
(`backend/app/config.py:122`), confirmed live: `GET /api/codebook/corpora` → `{"detail":"Not
Found"}` (the router genuinely isn't mounted — `backend/app/main.py:100-103` only imports
`codebook_router` when the flag is true, so this is a plain FastAPI 404, not a custom "disabled"
response). Both `/codebook` and `/codebook/console` frontend pages, live-tested in a real browser,
correctly render a clean "Codebook is not enabled on this backend..." message rather than
erroring or showing stale/fake data.

**7. Corpus sizes — verify the real chunk count of the structural corpus (~6,206 documented).**
Confirmed live, not repeated from memory: `GET /api/retrieval/corpora` right now returns
`{"corpus_name":"structural_standard_codes","document_count":17,"chunk_count":6206,...}`. The
17-file count was independently cross-checked by counting `.md` files on disk
(`find standards-service/data/structural_corpus -name "*.md" | wc -l` → 17). The 6,206 chunk count
was NOT independently recomputed from scratch by this audit (that would mean re-running the
chunker) — it is the live API's own count from the actually-built in-memory corpus, which is a
stronger source than a doc claim but still short of an independent chunk-by-chunk recount.

---

## Stale-or-wrong claims found in `docs/features.md` (and one in `docs/ARCHITECTURE.md`)

- `docs/features.md`'s HF_TOKEN/offline disclosure (lines 42-46, 310-315) is **accurate**, not
  stale — matches what this audit independently confirmed. Flagging this explicitly since the task
  asked to check for drift and this section could easily have been wrong; it isn't.
- `docs/features.md` line 132: "Independent standalone retrieval package (`RETRIEVAL_ENABLED`,
  default off)" — accurate as a statement of the *default*; just noting the live audited
  environment has it turned on (`RETRIEVAL_ENABLED=1` in `backend/.env`), consistent with what the
  task brief already flagged before I started.
- `docs/features.md`'s Codebook Console note ("never exercised in an actual browser (no Playwright
  in this environment)") is **now stale** — Playwright *is* available in this environment (used
  throughout this audit) and both Codebook pages were exercised live in a real browser during this
  session, in their disabled state. Not re-verified in their *available* (service-up) state, since
  standards-service is down this session.
- `docs/ARCHITECTURE.md` lines 16 and 111 still name the corpus **`manak_structural`** — both in
  prose ("indexes three corpora (`manak_structural`, `sitemind_existing_standards`,
  `company_uploaded`)") and in the architecture diagram itself
  (`CB_STRUCT[("manak_structural\n17 docs / 6,206 chunks")]`). The live corpus name (confirmed via
  API and via every current `.py` source file) is `structural_standard_codes`. This is presented as
  current architecture, not narrated history, so it's a real doc/code drift — not covered by the
  task's "screenshots are known-stale, ignore those" carve-out, since this is prose/diagram text,
  not a screenshot.

---

## UNVERIFIED

- Whether `standards-service`'s own retrieval stack, if started, actually builds successfully and
  matches the backend copy's live counts — not tested this session because starting a new backend
  process was outside the "don't modify running state beyond investigation" spirit of a read-only
  audit, and the task's useful-commands list didn't include starting it. `standards-service/app/`
  itself was read but not executed.
- The exact historical UI artifact ("0 docs · 0 chunks") — I identified the code path that would
  produce it and a documented adjacent bug (`docs/gaps.md` item 16), but found no log/screenshot in
  this repo pinning that it was ever this exact corpus (`structural_standard_codes`) in this exact
  state, as opposed to a different corpus or a `my-documents`-style empty-corpus-by-design case.
- Full byte-for-byte re-chunking of the 6,206-chunk structural corpus to independently verify the
  count rather than trust the live API's own in-memory count.
- `standards-service`'s own eval reports (`retrieval_report.json`, `cross_corpus_report.json`,
  `codebook_tools_report.json` under `standards-service/eval/`) were located but not opened/verified
  this pass — out of the specific 7 questions asked, and the service being down means they can't be
  freshly re-run without starting it.
- Whether Actian's Community Edition 5,000-vector cap (noted in `docs/gaps.md` item 11) is a live
  constraint on the current 6,206-chunk structural corpus when `RETRIEVAL_VECTOR_STORE=actian` is
  active — the parity eval passed, but it only checks 2 known-answer queries + 1 gibberish query,
  not full-corpus upsert completeness under the cap.
