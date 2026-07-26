# Agent A1 Audit — Compliance + Copilot

Scope: `backend/app/agents/{compliance,checks,rule_eval,copilot,copilot_agent,action_brief,mitigation}.py`,
`backend/app/{ingest,llm_extract,clause_viewer,standards}.py`, `frontend/app/compliance/page.tsx`,
`frontend/app/copilot/page.tsx`. Backend hit live on `localhost:8000`, frontend source read on
`localhost:3000`. Live runtime env at audit time: `backend/.env` has `LLM_PROVIDER=gemini`,
`GEMINI_API_KEY` set, `COPILOT_AGENT_ENABLED=1`, `RETRIEVAL_ENABLED=1`, `SOLANA_ENABLED=1`.
`COMPLIANCE_RULE_EXTRACTION` and `LLM_EXTRACTION_ENABLED` are **not set** in `.env` → both default
`"0"` (off). So this live instance is running **ONLINE mode** (not the offline default), but with
the computed-draft tiered-compliance path and LLM-based extraction both off.

---

## Summary verdict

- **Compliance pass/fail is genuinely computed in Python, not the LLM**, for the "certified" tier
  (17 hand-vetted rules in `checks.py`). Verified live: every NCR from `POST /api/compliance/check`
  on the demo document carries `"engine": "deterministic"` (Action Brief) and a real `Citation`
  resolved from `backend/data/standards/clauses.json`, not model-composed text.
- **`verdict_tier` is real and wired, but the `computed_draft` tier never fires on this live
  instance** — `COMPLIANCE_RULE_EXTRACTION=0` in `.env`, so `agents/compliance.py:444`'s gate
  (`COMPLIANCE_RULE_EXTRACTION and RETRIEVAL_ENABLED`) is false and the code path that would ever
  set `verdict_tier="computed_draft"` / populate `extracted_rule` / `computed_detail` is dead on
  this deployment. All 6 NCRs from the live demo document are `"certified"` with
  `extracted_rule: null, computed_detail: null` — confirmed by direct API response, see §2 below.
- **Two anti-hallucination substring gates both exist and both run** in code (`llm_extract.py
  verify_spans`, `compliance.py:295` `clause_phrase` gate) — confirmed by reading the code path,
  not by live-triggering them (both require flags that are off on this instance; see §3, UNVERIFIED).
- **Document extraction on upload is regex/heuristic (`ingest.py`) by default.** `LLM_EXTRACTION_ENABLED=0`
  is the default and is not overridden in `.env`, so `POST /api/compliance/ingest` on this live
  instance runs pure regex, never the Claude Agent SDK path.
- **The Copilot fixture-first path (`copilot.py:280-297`) wins for both of the two demo questions
  tested live.** A judge asking either question verbatim from the demo's own suggestion chips, or
  any of the 6 curated topics, gets one of exactly **6 canned Q&A pairs** from
  `backend/data/fixtures/copilot_answers.json` — not a live LLM answer, regardless of whether
  `OFFLINE_MODE` is on or off. This is by explicit design (comment: "Prefer the curated fixture for
  KNOWN questions in any mode — it's accurate and reliable on stage").
- **Live evidence of Gemini quota exhaustion / failure was captured mid-audit.** A non-fixture
  Copilot question ("required slump for the raft pour") returned the literal `_fallback_answer()`
  template string (`"Based on the retrieved sources [1] [2] [3] [4]: ..."`), which only fires when
  `llm.complete_text()` returns `""` — i.e. the live Gemini call failed even though `OFFLINE_MODE`
  is False. Separately, `POST /api/copilot/chat` (the LangGraph edge, which should route through
  Gemini tool-calling) returned text **byte-identical** to the `copilot_answers.json` fixture for a
  fixture-matching question, which only happens if the LangGraph agent invocation raised and the
  route fell back to `single_shot_answer()` (`copilot_agent.py:311-314`). The code even has a
  comment dated today acknowledging this: `"a transient Gemini API error or free-tier
  RESOURCE_EXHAUSTED quota error, confirmed live 2026-07-25"`. Per the task's instruction, this
  429/fallback is recorded as a finding, not chased further (no more Gemini calls were made).
- **The SSE streaming endpoint's "reasoning trace" is not live model reasoning — it's a canned,
  templated list of strings** keyed off which param types are present in the document
  (`compliance.py:594-625`, `_reasoning_trace`). It is real Python code executing over real data
  (so the *text* legitimately reflects what's about to be checked), but it is not tokens streamed
  from an LLM's thought process — there is no LLM call anywhere in `_sse_stream`. The frontend
  itself labels this distinction faithfully: `frontend/app/compliance/page.tsx:329-333` shows
  `"● live · backend SSE"` vs `"● simulated · mock stream"` depending on whether the fetch to
  `/check/stream` succeeded, but even the "live" case is a scripted trace, not model output.
- **`clause_viewer.py` is honest about its limited coverage**: only 3 of the ~10 cited standards
  (IS 456:2000, IS 1893 (Part 1):2016, IS 875 (Part 3):2015) have a real local `.md` source file;
  everything else returns `has_context:false` with an explicit note — confirmed live for both a
  real clause (has_context) and a fake standard (no context).

---

## Per-route table

| Route | Method | Nature | file:line |
|---|---|---|---|
| `/api/compliance/check` | POST | **COMPUTED** — pass/fail always deterministic Python against `clauses.json`; prose LLM-assisted online / fixture-or-template offline/on-failure | `backend/app/agents/compliance.py:392-548` (`evaluate_with_params`, `_violation_ncr`, `_prose`) |
| `/api/compliance/check/stream` | POST | **COMPUTED result, HARDCODED/templated reasoning trace** — same `evaluate()` call, but the streamed "reasoning" lines are a fixed per-param-type string table, not model output | `backend/app/agents/compliance.py:594-651` (`_reasoning_trace`, `_sse_stream`) |
| `/api/compliance/ingest` | POST | **COMPUTED** (regex extraction by default; LLM+span-gate only if `LLM_EXTRACTION_ENABLED=1`, off here) | `backend/app/agents/compliance.py:551-591`, `backend/app/ingest.py:393-416`, `backend/app/llm_extract.py:311-333` |
| `/api/compliance/action-brief/{document_id}` | GET | **COMPUTED** — RFI/activity links via TF-IDF cosine + real CPM critical-path flag, `confidence` is a rule-driven enum, `computed_impact` always `null` (honestly, per its own docstring — no formula exists yet) | `backend/app/agents/action_brief.py:1-80+` |
| `/api/copilot/ask` | POST | **FIXTURE-FIRST, then COMPUTED retrieval, then LLM or template prose** — see §"the fixture-first path" below | `backend/app/agents/copilot.py:272-303` |
| `/api/copilot/chat` | POST | **LangGraph agent (Gemini) when available, else falls back to the same fixture-first `/ask` logic** — live-observed falling back on this instance | `backend/app/agents/copilot_agent.py:293-316` |
| `/api/clause-context` | GET | **READ from disk** — verbatim `.md` excerpt for 3 standards, honest `has_context:false` otherwise | `backend/app/clause_viewer.py:83-147` |

---

## Frontend page behaviour

**`frontend/app/compliance/page.tsx`**
- Document register, upload button (real file read via `POST /ingest`, no mock fallback — the
  code comment at `lib/api.ts:357` explicitly says this endpoint has **no** offline/mock fallback
  because it reads an actual uploaded file).
- "Agent reasoning trace" panel explicitly labels itself `● live · backend SSE` vs
  `● simulated · mock stream` (`compliance/page.tsx:329-333`) depending on whether the SSE fetch
  succeeded — this is an honest UI disclosure, but as noted above, even the "live" label only means
  the *fetch* succeeded, not that the reasoning text came from a model.
- Action Brief cards similarly self-label `● live · backend` vs `● derived client-side (backend
  unreachable)` (`compliance/page.tsx:481-485`), backed by `getActionBrief`'s try/catch fallback to
  `fallbackActionBrief(ncrs)` in `lib/api.ts:271-285`.
- Coverage meter, overlap panel, conforming list are all rendered directly from the
  `ComplianceResult` JSON — no client-side re-derivation of numbers.

**`frontend/app/copilot/page.tsx`**
- On mount, auto-asks `SUGGESTIONS[0]` ("What cover does IS 456 require for footings?") via a real
  `askCopilot()` call (comment at line 135-140 explicitly says this is "a genuine askCopilot() call
  ... not fake data") — but per the fixture-match logic, this genuine call still resolves to the
  canned fixture answer.
- `[n]` citation chips are rendered from `answer.sources`, hoverable, with `verify_url` links when
  present (dead-link caveat from the project's own landmine list applies here for non-`archive.org`
  citations — not independently re-verified in this audit pass).
- "Try also" row nudges toward the other 2 suggestion questions; abstention is disclosed in a
  caption ("Abstains when the source doesn't answer — no guessed clauses").
- `askCopilot()` in `lib/api.ts` (grep-confirmed) falls back to `mockCopilotAnswer(question)` if the
  backend is unreachable — this mock path was not live-triggered in this audit (backend was up).

---

## Flags & degradation table

| Flag / key | Default | Effect when off / missing | Verified how |
|---|---|---|---|
| `OFFLINE_MODE` (derived, no direct env var) | `True` unless a usable provider key is set | Compliance/Copilot prose uses fixtures/templates instead of an LLM call; pass/fail and citations unaffected either way | `config.py:82-96`; live instance has `GEMINI_API_KEY` set so `OFFLINE_MODE=False` here |
| `LLM_EXTRACTION_ENABLED` | `"0"` (off) | `/api/compliance/ingest` uses pure regex (`ingest.py`) only; LLM+span-verify path (`llm_extract.py`) never runs | `config.py:33`; not set in `.env` |
| `COMPLIANCE_RULE_EXTRACTION` | `"0"` (off) | `_computed_draft_finding` never runs; any param with no `checks.py` rule is silently skipped (`continue` at `compliance.py:451`) rather than emitting an `unresolved`/`computed_draft` NCR | `config.py:135`; not set in `.env`; confirmed live — 0 `computed_draft`/`unresolved` NCRs in `coverage.computed_draft_count`/`unresolved_count` on the live check |
| `RETRIEVAL_ENABLED` | `"0"` (off) | Both `_computed_draft_finding` (needs it jointly with `COMPLIANCE_RULE_EXTRACTION`) and `copilot_agent.py`'s `query_knowledge_base` tool return empty/abstain | `config.py:112`; **live instance has it `=1`** in `.env`, so only `COMPLIANCE_RULE_EXTRACTION=0` is blocking the computed-draft tier |
| `COPILOT_AGENT_ENABLED` + `GEMINI_API_KEY` | off / unset | `POST /api/copilot/chat` falls back to `single_shot_answer()` (the `/ask` fixture-first logic) | `copilot_agent.py:183-196`, `293-316`; live instance has both set, but a live call still fell back — see Summary |
| `HF_TOKEN` | required for dense embeddings | Without it, `embeddings.py` calls (Copilot dense retrieval, seen-before RFI matching) fail — this degrades semantic search, independent of `OFFLINE_MODE` | Not independently re-tested (`.env` has `HF_TOKEN` set); documented accurately in `docs/features.md:42-48` |

---

## The 6 specific questions, answered

**1. `copilot.py:272-300` fixture-first path — when does `_match_fixture` win, in which modes, how many pairs, do the 6 demo questions get canned answers?**

- `answer()` (line 272) calls `_match_fixture(question)` **before** any retrieval, in **every mode**
  (online or offline) — this is explicit in the code comment: *"Prefer the curated fixture for
  KNOWN questions in any mode — it's accurate and reliable on stage. Live LLM (when configured)
  handles UNSEEN questions."* If `_match_fixture` returns non-`None`, the function returns
  immediately (line 284-290) without ever calling `_hybrid_retrieve` or an LLM.
- Match logic (`_match_fixture`, lines 77-101): keyword-hit scoring against `_SLUG_KEYWORDS`
  (line 40-47). ≥2 keyword hits → fixture wins outright, no further check. Exactly 1 hit → confirmed
  against a cosine-similarity floor (`_FIXTURE_MATCH_FLOOR = 0.40`) against the fixture's own
  answer-text embedding before trusting it.
- `backend/data/fixtures/copilot_answers.json` contains **exactly 6 canned Q&A pairs**, keyed by
  slug: `transformer-yard-footing-grade-cover`, `open-rfis-marine-cooling-rcc`,
  `design-wind-speed-chennai`, `m30-vs-m35-severe-exposure-seen-before`,
  `which-submittals-non-conforming`, `importance-factor-data-centre`.
- **Confirmed live**: `curl -X POST /api/copilot/ask -d '{"question":"What cover does IS 456
  require for footings?"}'` returned the `transformer-yard-footing-grade-cover` fixture verbatim
  (2 keyword hits: "footing", "cover"). **Yes — a judge asking that question, or any close paraphrase
  hitting ≥2 keywords of any of the 6 slugs, gets a canned answer, not a live-computed one.**
  The frontend's own 3 suggestion chips include this exact question as the auto-asked first turn.

**2. `schemas.py` `NCR.verdict_tier`/`extracted_rule`/`computed_detail` — is `computed_detail` populated for `certified` or only `computed_draft`?**

- **Only `computed_draft`.** Proven two ways:
  - By reading the code: `computed_detail` is set in exactly one place in the codebase,
    `agents/compliance.py:332`, inside `_computed_draft_finding`, which always sets
    `verdict_tier="computed_draft"` two lines above (line 330). `_violation_ncr` (the certified-tier
    constructor, line 163-176) never sets `computed_detail` or `extracted_rule` at all — they stay
    at the Pydantic defaults (`None`).
  - By live proof: `POST /api/compliance/check {"document_id":"DC1-02-DBR-0001-R2"}` returned 6
    NCRs, **all** `"verdict_tier":"certified"`, and **all** `"extracted_rule":null,
    "computed_detail":null"`. `coverage.computed_draft_count` = 0, `coverage.unresolved_count` = 0
    in the same response — consistent with `COMPLIANCE_RULE_EXTRACTION=0` meaning that tier's code
    path is never reached on this document.
  - Could not live-trigger an actual `computed_draft` NCR (would require flipping
    `COMPLIANCE_RULE_EXTRACTION=1` and restarting the server, which this audit did not do per the
    "do not modify" / minimal-footprint instruction) — the *shape* is confirmed correct by code
    reading only. See UNVERIFIED.

**3. The two anti-hallucination substring gates — do both actually run?**

- **Gate 1 — `llm_extract.py verify_spans` (source-span verbatim gate)**: runs unconditionally
  inside `extract_params()` (line 311-333) whenever `llm_enabled()` is true and the Claude Agent SDK
  call succeeds (line 326: `verify_spans(raw_items, text)`). On this live instance
  `LLM_EXTRACTION_ENABLED=0`, so `llm_enabled()` is false and this code path is **not exercised** —
  confirmed by config only, not a live call (would need `LLM_EXTRACTION_ENABLED=1` + a Claude Code
  OAuth token). Gate logic itself (lines 130-195: verbatim-substring check at 165, value-in-span
  check at 169) is present and unconditional whenever the function runs.
- **Gate 2 — `compliance.py:295` `clause_phrase` verbatim gate** (rule-extraction/computed-draft
  path): `if llm_extract._norm(rule.clause_phrase).lower() not in llm_extract._norm(clause_text).lower():`
  — this line runs unconditionally inside `_computed_draft_finding`'s per-candidate loop, but that
  function itself is only reached when `COMPLIANCE_RULE_EXTRACTION and RETRIEVAL_ENABLED` (line 444)
  — the first of which is off here. **Not live-triggered this audit.**
- **Verdict: both gates exist in code and would run whenever their parent code path executes; neither
  was observed actually gating a real value on this live instance**, because both parent flags
  (`LLM_EXTRACTION_ENABLED`, `COMPLIANCE_RULE_EXTRACTION`) are off in `.env`. Reported as
  code-confirmed, **runtime-UNVERIFIED**.

**4. Document extraction on upload — regex/heuristic or LLM-based? What does `LLM_EXTRACTION_ENABLED` change?**

- Default (and live-instance) behavior is **pure regex/heuristic**, in `backend/app/ingest.py`
  (9 narrow per-parameter regexes, e.g. `_COVER_RE`, `_GRADE_RE`, `_WC_RE`, lines 105-364), each
  requiring an element-type keyword match (e.g. "footing"/"column") before accepting a hit — no
  guessing, explicit `Abstention` objects for everything not confidently matched (`_ALWAYS_ABSTAIN`,
  lines 371-378, covers wind speed/pressure/tie spacing/insulation resistance/RCD touch-voltage —
  deliberately never attempted by regex because they need multi-number context).
- `LLM_EXTRACTION_ENABLED=1` (not the default) would additionally call the Claude Agent SDK
  (`llm_extract.py:228-261`, via `claude_agent_sdk`, using Claude Code subscription OAuth, **not**
  an API key) to propose extra candidate parameters, each still required to pass `verify_spans`
  before being unioned with the regex "floor" set (`_dedup_union`, lines 284-297) — regex results are
  never removed, only ever added to. Not live-tested (flag off; would also need a working
  `CLAUDE_CODE_OAUTH_TOKEN`, not confirmed present).

**5. `clause_viewer.py` — which standards have real local `.md` source text, which honestly report no context?**

- Exactly 3, hardcoded in `_STANDARD_TO_FILE` (`clause_viewer.py:47-51`): **IS 456:2000**,
  **IS 1893 (Part 1):2016**, **IS 875 (Part 3):2015**. Confirmed live:
  `GET /api/clause-context?standard=IS 456:2000&clause=26.4.2.2` → `has_context:true` with a real
  multi-paragraph verbatim excerpt read off disk (`standards-service/data/structural_corpus/is456_2000/is.456.2000.md`).
  `GET /api/clause-context?standard=NEC 2017&clause=1.1` (an unmapped standard) → `has_context:false`
  with note *"No locally digitised source document is mapped for this standard in this
  environment — showing the cited clause text only."* — an honest disclosure, not a fabricated
  fallback.
- The module's own docstring (lines 19-26) states the rest of the ~10 standards cited across
  `clauses.json`/`commissioning_clauses.json` (CEA regs, IS 3043, IS 732, IS 8623, the
  ASHRAE-derived commissioning envelope) have no local source and will always report
  `has_context=False`.

**6. `POST /api/compliance/check/stream` — real or simulated streamed reasoning? Frontend fallback?**

- **Not real model reasoning under any condition.** `_reasoning_trace()` (`compliance.py:594-625`)
  is a static lookup: it iterates the document's real params and appends one of ~8 hardcoded
  template strings per param type (e.g. `"Checking {element_type} cover against IS 456…"`). There is
  no LLM call in `_sse_stream` (line 628-644) at all — it emits these canned lines, then calls the
  same deterministic `evaluate()` used by the non-streaming endpoint, then emits the real result.
  The only "streaming" is real (Python `yield`s over real data), but the *reasoning text* itself is
  scripted, not generated.
  - Confirmed live via `curl -X POST /api/compliance/check`: `document`/`ncrs`/`coverage` came back
    correctly; the equivalent `/check/stream` route was not separately curled (SSE needs a streaming
    client) but the code path is unambiguous from source — `_reasoning_trace` contains no `llm.py`
    or `llm_extract.py` import/call anywhere.
- **Frontend fallback** (`frontend/lib/api.ts:428-482`, `streamCompliance`): tries the real SSE fetch
  first; on any failure (network error, non-OK status, no body) it calls `handlers.onSource?.(false)`
  and `simulateStream(...)` — a client-side mock trace generator. The UI's `● live · backend SSE` vs
  `● simulated · mock stream` badge (`compliance/page.tsx:329-333`) reflects **only whether the
  fetch succeeded**, not whether the underlying content was ever model-generated — in both the "live"
  and "simulated" cases the reasoning text a judge sees is scripted/templated, just from two
  different template sources (backend's `_reasoning_trace` vs frontend's `simulateStream`/mock data).

---

## Stale-or-wrong claims found in `docs/features.md`

`docs/features.md` §2 (Compliance Agent) and §3 (Copilot) are, on the whole, **accurate and
current** as of this audit — they correctly describe the fixture-first Copilot path, the
regex-not-LLM default extraction, the SSE-with-simulated-fallback behavior, and the LangGraph edge
being flag-gated with the frontend not yet wired to `/chat`. No factually wrong claim was found in
these two sections.

One **gap, not an error**: `docs/features.md` §2 never mentions the tiered-verdict system
(`verdict_tier` certified/computed_draft/unresolved, `ExtractedRule`, `rule_eval.py`,
`COMPLIANCE_RULE_EXTRACTION`) at all — a reader of that section alone would not know this
subsystem exists in the codebase, or that it is currently inert on the live/default deployment
(`COMPLIANCE_RULE_EXTRACTION` unset in `.env` → always `"0"`). Given the project's own CLAUDE.md
calls this tiered system out as the *current* thesis wording ("the LLM never computes a verdict"),
this seems worth a line in `features.md` §2 flagging it as built-but-currently-off, similar to how
§3 already flags the LangGraph edge as built-but-not-wired-to-the-frontend.

---

## UNVERIFIED

- **`computed_draft` tier end-to-end behavior** (an actual computed-draft NCR being produced,
  `extracted_rule` populated, `computed_detail` showing real `rule_eval.evaluate()` output) — code
  reading only; not live-triggered because it requires `COMPLIANCE_RULE_EXTRACTION=1`, which is not
  set in the running instance's `.env`, and this audit did not modify config/restart the server.
- **`LLM_EXTRACTION_ENABLED=1` upload path** (Claude Agent SDK extraction + `verify_spans` gate
  actually firing on a live upload) — not live-tested; flag is off, and would additionally need a
  working `CLAUDE_CODE_OAUTH_TOKEN` whose presence/validity was not checked.
- **Whether `CLAUDE_CODE_OAUTH_TOKEN` is even present/valid** in this environment — not checked
  (out of scope of `.env` grep, which only showed Gemini/HF/Langfuse/Solana keys; no
  Anthropic/Claude key line was present in `backend/.env` at all).
- **Exact cause of the observed Gemini failures** (quota `RESOURCE_EXHAUSTED` vs. some other
  transient error) — inferred from (a) the code's own fallback behavior firing, and (b) a code
  comment dated 2026-07-25 explicitly citing a confirmed live `RESOURCE_EXHAUSTED` quota error, but
  not independently confirmed via a raw Gemini API response/error code in this audit (deliberately
  avoided per instruction not to burn more quota).
- **Dead `verify_url` citation links** (the project's own documented landmine — ~13 of 24 clause
  `verify_url`s point at `gaudi.local`) — not re-verified in this pass; out of the specifically
  assigned scope, flagged here only because it's directly adjacent to the Copilot/Compliance
  citation surfaces this audit did examine.
- **`mockCopilotAnswer` / `mockComplianceFor` client-side mock fallback content** (`frontend/lib/mocks.ts`)
  — referenced in `lib/api.ts` but the mock file itself was not read in this pass; not live-triggered
  since the backend was reachable throughout.
- **`agents/mitigation.py`** — read only by name/grep, not opened in full; out of the specific 6
  questions but nominally in scope per the file list. Not substantively audited this pass.
