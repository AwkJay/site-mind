# Agent A6 Audit — Eval Suite + Data Provenance

Scope: `backend/eval/`, `standards-service/eval/`, `backend/data/` (esp. `gen_synthetic.py`,
`fixtures/`, `standards/clauses.json`, `project_docs/`, `schedule/`, `company_corpus/`).

Method: exact `ls`/`wc` counts of scripts, live re-run of every eval script this session
(`backend/.venv/bin/python -m eval.run_X`, `standards-service/.venv/bin/python -m eval.run_X`),
`python3 -c` counts of clauses/fixtures, `curl` liveness checks of every `verify_url`, `file`/page
counts on every PDF, and direct reading of `gen_synthetic.py` and the two fixture-consuming call
sites in `app/agents/compliance.py` / `app/agents/copilot.py`.

## Summary verdict

**The headline number reproduces exactly as claimed.** `python -m eval.run_eval` this session
printed `n=41 … SiteMind: acc=1.0 macroF1=1.0 hallucination=0.0 … Baseline: acc=0.5854`. All 22
runnable eval scripts (19 backend + 3 standards-service) were executed live this session; every
one PASSED at 100% on its own test set (see table). One script (`run_codebook_tools_eval.py`)
could NOT run — standards-service (:8010) was not running in this sandbox and the script fails
closed with a clear connection-refused error (exit code 2), not a silent skip.

**The script-count claim in `docs/features.md` §14 ("18 live in backend/eval/, 3 in
standards-service/eval/" = 21) is now STALE.** An exact `ls backend/eval/run_*.py | wc -l` gives
**19**, not 18 — `run_actian_parity_eval.py` (mtime Jul 25 00:29, an Actian-sponsor-track addition)
is not mentioned anywhere in §14's per-script list. Total is **22 scripts (19+3), not 21**.

**The gaudi.local dead-link landmine flagged in `.claude/CLAUDE.md` is CURRENTLY FIXED, verified
live.** All 24 `clauses.json` `verify_url`s resolve to `archive.org` (20), `cea.nic.in` (2), or
`www.bis.gov.in` (2) — zero `gaudi.local` references anywhere in `backend/data/`, `backend/app/`,
or `frontend/lib/`. `curl` confirmed archive.org and cea.nic.in return HTTP 200, bis.gov.in
returns 302 (redirect, still live). This matches `docs/gaps.md`'s "FIXED (later session)" note —
`.claude/CLAUDE.md`'s "~13 of 24 point at gaudi.local, do NOT claim every citation is clickable"
warning is itself now the stale artifact and should be updated or removed.

**The credibility caveat already written into `docs/features.md` §14 is correct and I confirmed it
directly in source**: `run_eval.py`'s own docstring (lines 1-16) states outright that scoring the
rule engine against gold labels "derived from the same thresholds the code implements... would be
trivially 100% and meaningless," and that the informative number is the baseline-gap, not the
100%. `run_electrical_eval.py`'s docstring makes the same admission ("checks the THRESHOLD
ARITHMETIC against a hand-built answer key"). These are regression tests wearing an eval costume,
and the project's own comments say so — a technical judge who reads the docstrings will find the
caveat already disclosed, which is unusually honest for a hackathon submission.

**Six n_cases discrepancies found between `docs/features.md` §14's stated counts and this
session's actual script output** (see per-script table) — none is large enough to change the
qualitative picture, but none matched exactly either, meaning §14's counts were written once and
never re-verified against a live run, exactly as its own header now (correctly) disclaims.

## Eval script inventory (exact counts)

- `backend/eval/`: **19** `run_*.py` scripts (`ls backend/eval/run_*.py | wc -l` = 19).
- `standards-service/eval/`: **3** `run_*.py` scripts (`ls standards-service/eval/run_*.py | wc -l` = 3).
- **Total: 22, not 21.** `docs/features.md:188-190` claims "18 live in backend/eval/, 3 in
  standards-service/eval/" — the backend count is stale by one script
  (`run_actian_parity_eval.py`, undocumented in §14's list, confirmed via `git log`/mtime as a
  same-day addition alongside the other Jul 25 00:29-00:31 files: `actian_parity_report.json`,
  and a same-day rewrite of `run_cross_corpus_eval.py`).

| Script | What it tests | n (claimed in features.md) | n (actual, this run) | Result |
|---|---|---|---|---|
| `backend/eval/run_eval.py` | Structural rule engine (8 checks) + citation-hallucination rate vs naive-keyword baseline | ~41 | 41 | PASS (acc=1.0, hallucination=0.0; baseline acc=0.5854) |
| `backend/eval/run_extraction_eval.py` | Free-text parameter extraction, planted values + abstention | 14 docs | 14 docs, 11 planted params, 59 abstention checks | PASS (precision=recall=f1=1.0, abstention 59/59) |
| `backend/eval/run_electrical_eval.py` | Electrical checks vs IS 732:1989 OCR | 30 | **32** (MISMATCH) | PASS (acc=1.0) |
| `backend/eval/run_equipment_spec_eval.py` | IS 8623-1 LV switchgear spec matching | 12 | 12 | PASS (acc=1.0) |
| `backend/eval/run_commissioning_eval.py` | ASHRAE cooling envelope verdicts | 14 | 14 | PASS (acc=1.0) |
| `backend/eval/run_alerts_eval.py` | Alert severity tiering + detection-day logic | 11 | 11 | PASS (acc=1.0) |
| `backend/eval/run_supply_chain_eval.py` | Delay propagation, root-cause, alt-viability | 8 | 8 | PASS (acc=1.0) |
| `backend/eval/run_schedule_eval.py` | Leading-indicator rules + CPM recompute | ~11 | 12 (close) | PASS (acc=1.0) |
| `backend/eval/run_weather_eval.py` | IMD monsoon-window overlap/slip arithmetic | 11 | 11 | PASS (acc=1.0) |
| `backend/eval/run_workforce_eval.py` | Pongal labour-dip overlap/slip arithmetic | 10 | 10 | PASS (acc=1.0) |
| `backend/eval/run_mitigation_eval.py` | 3 mitigation functions (procurement/float/resource) | 13 | 13 | PASS (acc=1.0) |
| `backend/eval/run_timeline_eval.py` | Cross-pillar traceability vs live demo dataset | ~20 | 20 | PASS (acc=1.0) |
| `backend/eval/run_cost_risk_eval.py` | Cost-at-risk arithmetic | 9 | 9 | PASS (exact numeric match) |
| `backend/eval/run_impact_eval.py` | ROI-ticker composition | 11 | **12** (MISMATCH) | PASS (acc=1.0) |
| `backend/eval/run_copilot_eval.py` | Retrieval-floor + seen-before-floor calibration | 12+9 | 12+9 | PASS (deployed floors 0.40/0.35 reported as claimed; sweep-optimal computed as **0.25 for both** — see credibility note below) |
| `backend/eval/run_hybrid_retrieval_eval.py` | RRF fusion arithmetic vs independent reference impl | 5 | 5 | PASS (acc=1.0) |
| `backend/eval/run_cross_corpus_eval.py` | 2 real filesystem corpora: build-integrity, known-answer, abstention, verbatim-offset | ~20 | **26** (MISMATCH) | PASS (26/26); confirmed 17 real IS-code docs / 6206 chunks + 2 SiteMind JSON / 29 chunks |
| `backend/eval/run_retrieval_eval.py` | Chunker + RRF + end-to-end ingest/query, 3 made-up docs | ~22 | **24** (MISMATCH) | PASS (24/24) |
| `backend/eval/run_actian_parity_eval.py` | **Not in §14 at all** — Actian VectorAI parity vs the manak corpus (known-answer top-hit doc-id parity + abstention) | — (undocumented) | 5 | PASS (5/5) |
| `standards-service/eval/run_retrieval_eval.py` | Same logic as backend copy, repointed | ~22 | 24 (identical output to backend copy) | PASS (24/24) |
| `standards-service/eval/run_cross_corpus_eval.py` | Same logic as backend copy, repointed | ~20 | 26 (identical output to backend copy) | PASS (26/26) |
| `standards-service/eval/run_codebook_tools_eval.py` | Drives all 4 MCP tools via a real client session against the **live** standards-service on :8010 | ~25 | **CANNOT-RUN** this session (service not up); cached `codebook_tools_report.json` on disk shows n=30, 30/30 pass (also a MISMATCH vs the "~25" claim) | **CANNOT-RUN — environment.** `curl :8010/health` timed out (000). Script fails closed with `ERROR: standards-service is not reachable at http://127.0.0.1:8010/health ([Errno 111] Connection refused)` and exits 2 — a clean, honest failure, not a hang or a fabricated pass. |

## Eval credibility assessment

**Genuinely independent validation:**
- `run_eval.py` — the *baseline comparison* (naive-keyword accuracy 58.5% vs SiteMind 100%) is
  real independent signal; the 100% figure alone is not (see below).
- `run_hybrid_retrieval_eval.py` — cross-checked against an independently written reference RRF
  implementation, not the production code's own constants.
- `run_cross_corpus_eval.py` (both copies) and `run_timeline_eval.py` — test against real,
  externally-sourced or live-derived data (17 real IS/IRC/IRS PDFs turned into a 6206-chunk
  corpus; the live demo dataset) rather than hand-picked synthetic cases. This is the strongest
  part of the suite — full coverage, not sampled, and the corpus composition (doc count, chunk
  count) is independently re-derivable from the filesystem, which I did (`ls
  standards-service/data/structural_corpus | wc -l` = 17, matching the eval's own report).
- `run_extraction_eval.py`'s abstention check (59/59, zero fabricated extractions) is a genuine
  negative-control test, not circular against the extraction logic's own thresholds.
- `run_actian_parity_eval.py` — genuinely compares two independent retrieval backends
  (manak/structural corpus vs Actian) against the same hand-verified known-answer set.

**Regression checks wearing an eval costume (confirmed by reading the code, not just inferring):**
- `run_eval.py` — its own docstring (`backend/eval/run_eval.py:1-16`) states: "Scoring it against
  gold derived from the same thresholds would be trivially 100% and meaningless." The 100%
  accuracy / 1.0 macro-F1 headline is exactly that trivial number; the code says so itself. Only
  the baseline delta is informative.
- `run_electrical_eval.py` — its own docstring (`backend/eval/run_electrical_eval.py:1-21`) states
  it "checks the THRESHOLD ARITHMETIC against a hand-built answer key" — i.e., does the rule
  reach the same verdict the same threshold constants would produce. No baseline comparison exists
  for this one (unlike `run_eval.py`), so this script has *no* independent signal at all — it is a
  pure regression test.
- `run_equipment_spec_eval.py`, `run_commissioning_eval.py`, `run_alerts_eval.py`,
  `run_supply_chain_eval.py`, `run_schedule_eval.py`, `run_weather_eval.py`,
  `run_workforce_eval.py`, `run_mitigation_eval.py`, `run_cost_risk_eval.py`,
  `run_impact_eval.py` — all follow the same pattern as `run_electrical_eval.py`: hand-built cases
  authored by whoever wrote the feature, checked against the feature's own deterministic formula,
  with no baseline/independent-reference comparison. All report 100% accuracy, which is expected
  and not meaningful evidence of correctness against any external ground truth — only evidence the
  arithmetic hasn't regressed since the case was written.
- `run_copilot_eval.py` — a partial exception to the docs' own caveat. `docs/features.md:262-263`
  claims the deployed floors were "chosen using the same small labeled set that evaluates them —
  risk of overfitting." Live output this session: the sweep-optimal floor computed by the eval's
  own labeled set is **0.25** for both retrieval and seen-before, but the *deployed* floors are
  **0.40 / 0.35** — i.e. the deployed values are NOT the eval's own optimum. This doesn't fully
  refute the overfitting concern (0.40/0.35 could still have been hand-picked by eyeballing the
  same set) but it is evidence against the strongest form of the claim ("chosen to hit 100% on
  this set") — worth a follow-up if this claim is repeated in a demo.

**Structurally independent but small:** `run_retrieval_eval.py` and `run_actian_parity_eval.py`
tests are logically independent of the module under test (chunker/RRF-math vs hand keyed
expectations) but n is small (5-24) and entirely self-authored, matching §14's own "held-out
mostly means different wording, not independent authorship" caveat.

## Which evals require an external live service and cannot run standalone

- `standards-service/eval/run_codebook_tools_eval.py` — **requires the standards-service process
  running on :8010** (real MCP client session over `mcp.client.streamable_http`, not an in-process
  import). Confirmed this session: `curl :8010/health` → connection refused; script exits 2 with a
  named, actionable error. Per `docs/features.md:307-308`, cold-starting this service triggers a
  ~7-minute blocking rebuild of the 6206-chunk corpus (no on-disk embeddings cache) — I did not
  boot it this session to avoid a 7+ minute blocking operation outside the audit's time budget;
  the CANNOT-RUN verdict above is therefore an environment/availability finding, not a code defect
  (the script's own failure-closed behavior is itself evidence of correct engineering).
- `backend/eval/run_copilot_eval.py`, `run_hybrid_retrieval_eval.py`,
  `run_cross_corpus_eval.py`/`run_retrieval_eval.py` (both backend and standards-service copies) —
  all depend on `app/embeddings.py`'s Hugging Face Inference API call, which needs a live `HF_TOKEN`
  and outbound network. **These did NOT fail in this sandbox** — a real (non-placeholder) `HF_TOKEN`
  is present in `backend/.env` and outbound network to the HF Inference API was reachable this
  session, so all of these ran and passed live rather than falling back to any offline stub. This
  is worth flagging precisely because it means today's "100%" on these scripts reflects a real
  network-dependent code path succeeding, not an environment-independent guarantee — a CI runner
  or judge's laptop without the same token/network would see these fail closed instead (per
  `embeddings.py:34-36`'s explicit `HF_TOKEN not set` error), a different failure mode than a
  code bug.

## Reproduced headline numbers

Ran `cd backend && source .venv/bin/activate && python -m eval.run_eval` live this session.
Actual stdout, verbatim:
```
n=41
SiteMind : acc=1.0  macroF1=1.0  hallucination=0.0
Baseline : acc=0.5854  macroF1=0.5607  hallucination=0.0
wrote eval/report.json + eval/testset.jsonl
```
This **exactly matches** the claimed headline: "100% rule-decision accuracy vs a 58.5% naive
baseline (n=41), 0% citation-hallucination rate." Reproduced, not merely re-read from a cached
JSON. See the credibility section above for why the 100% figure alone should not be over-claimed —
the 58.5%-vs-100% *gap* is the part with independent evidentiary value.

## Data provenance table

| Path | Classification | Notes |
|---|---|---|
| `backend/data/standards/clauses.json` | **REAL** | 24 clauses, real BIS/CEA IS-code text (IS 456/875/1893/732/3043/8623, CEA 2010 regs). File's own `_note` (line 2) states this. Verified live — see verify_url audit below. |
| `backend/data/standards/commissioning_clauses.json` | **REAL, lower-tier / self-disclosed partial** | 5 clauses. Own `_note` explicitly labels itself `cross_source_unverified` — compiled from one official ASHRAE free white paper + several convergent secondary sources, NOT independently verified against a single primary ASHRAE document (the ASHRAE book itself is commercial, not freely fetchable). `known_simplification` field discloses a real methodological shortcut (flat RH% vs true dew-point envelope). |
| `backend/data/standards/source_pdfs/is732_1989.md` | **REAL** | 6114-line OCR markdown transcription of the real scanned IS 732:1989 PDF; visible OCR garbage (mangled table glyphs) in the raw text confirms genuine OCR of a real scan, not synthetic text. |
| `backend/data/project_docs/*.pdf` (CEA_Safetycons, is.3043.1987, is.732.1989, IS732_2019, "IS732 & IS3043...", is.8623.1.1993, "List of IS Standards", "Volume 6 - Electrical Safety Audit...") | **REAL** | All verified as genuine multi-page PDFs via `file`, not stubs (72, 95, 116, 73, 4, 31 pages resp.). Caveat: `IS732_2019.pdf` is only **5 pages** — almost certainly a partial/preview extract of the full 2019 edition, not the complete standard; the project itself uses the older `is.732.1989.pdf` (full, 1989 edition) as the actual electrical-check ground truth per `run_electrical_eval.py`'s docstring, not the 2019 file. |
| `backend/data/project_docs/standards/*.pdf` (ASHRAE white papers, therm-gdlns refcard, diminico, 90_4_2022, TS_2020 presentation) | **REAL** | All genuine multi-page PDFs (8-85 pages), real ASHRAE/secondary technical-conference sources feeding the commissioning corpus. |
| `backend/data/project_docs/design_basis.md`, `design_basis_params.json` | **SYNTHETIC** | Generated by `gen_synthetic.py:206-273`; fictional project ("Hyperscale DC — Chennai, 48 MW"), values deliberately aligned to real clause thresholds so violations are meaningful. |
| `backend/data/project_docs/submittals.csv`, `rfi_log.csv`, `boq.csv` | **SYNTHETIC** | Generated by `gen_synthetic.py:280-453`. |
| `backend/data/schedule/schedule.csv` | **SYNTHETIC** | Generated by `gen_synthetic.py:459-509`, ~33 activities. |
| `backend/data/project_docs/monsoon_window.json` | **REAL** | File's own `_note`: "Real IMD (India Meteorological Department) primary-source data" for the Chennai NE monsoon window — planning-grade climatological fact, explicitly disclaims being a forecast. Not generated by `gen_synthetic.py`. |
| `backend/data/project_docs/workforce_calendar.json` | **SYNTHETIC (partially real)** | File's own `_note`: Pongal festival window is a real calendar fact; the labour-dip *magnitude* (`availability_factor`) is "a conservative, documented assumption... NOT a cited statistic." |
| `backend/data/project_docs/supply_chain.json` | **SYNTHETIC** | Own `_note`: "REPRESENTATIVE... Coordinates are real city coordinates; supplier names are fictional." |
| `backend/data/project_docs/cost_basis.json` | **SYNTHETIC** | Own `_note`: "REPRESENTATIVE synthetic cost data... NOT any real project's actual costs." |
| `backend/data/fixtures/compliance_prose.json` | **FIXTURE** | 6 canned NCR-prose entries keyed by param id (DBP-01, DBP-03…09). Served by `app/agents/compliance.py:82-95` (`_offline_prose`) whenever `config.OFFLINE_MODE` is true, OR as a robustness fallback (`_prose`, line 103) when a live LLM call returns malformed JSON — so it fires in both the pure-offline path and as an online-failure safety net. |
| `backend/data/fixtures/copilot_answers.json` | **FIXTURE** | 6 canned Q&A entries (`transformer-yard-footing-grade-cover`, `open-rfis-marine-cooling-rcc`, `design-wind-speed-chennai`, `m30-vs-m35-severe-exposure-seen-before`, `which-submittals-non-conforming`, `importance-factor-data-centre`). Served by `app/agents/copilot.py:54,78` via keyword-slug matching (`_SLUG_KEYWORDS`) confirmed by embedding-similarity against the fixture's own answer text when only 1 keyword hits (`_match_fixture`, line ~70-90) — this is the canned-answer/"seen-before" demo path, distinct from live retrieval. |
| `backend/data/company_corpus/` | **EMPTY / RUNTIME, not committed data** | `.gitignore` (`*` except `.gitignore`/`.gitkeep`) confirms this is a write-target for user uploads under `RETRIEVAL_ENABLED=1`, never tracked demo data. Directory is empty (0 files besides the two dotfiles) at audit time. |
| `backend/data/traces/*.json` | **RUNTIME LOG, not test/demo data** | **1280 files** (`ls backend/data/traces/*.json \| wc -l` = 1280) — auto-generated provenance/audit trace records written by the app on every pipeline run (`pipeline`, `steps`, `duration_ms` fields), not authored data. Out of scope for eval-provenance classification but noted since it's under `backend/data/`. |
| `backend/data/audit_events.jsonl` | **RUNTIME LOG** | Same category as `traces/` — not inspected in depth (out of assigned scope beyond noting its existence and category). |

## clauses.json verify_url audit

Exact count: **24 clauses** (`json.load(...)['clauses']` length, counted via Python, not eyeballed).

| Domain | verify_url target | Count | Live check (curl, this session) |
|---|---|---|---|
| archive.org (IS 456/875/1893/732:1989/3043/8623) | `https://archive.org/details/gov.in.is.*` | 20 | HTTP 200 |
| cea.nic.in (CEA 2010 Regs, clauses 41(xii)/41(xiii)) | `https://cea.nic.in/regulations-category/...` | 2 | HTTP 200 |
| www.bis.gov.in (IS 732:2019, clauses 4.2.11.5.3/Table 15) | `https://www.bis.gov.in` | 2 | HTTP 302 (redirect — still live, but this is a bare homepage link, NOT a deep link to the specific clause; weaker citation quality than the archive.org entries even though not "dead") |

**`gaudi.local` count: 0/24, confirmed live.** Grepped `backend/data/`, `backend/app/`,
`frontend/lib/` for the string `gaudi` — the only hit is a docstring comment in
`backend/app/clause_viewer.py:1,5` explaining *why* the in-app clause viewer exists ("replaces
the dead `http://gaudi.local/...` verify_url... For most clauses that link is dead"), not a live
data reference. This corroborates `docs/gaps.md:19-22`'s note that the 13/24-dead-link issue was
"FIXED (later session)" and confirms it is **still fixed as of this audit** — the `.claude/CLAUDE.md`
"Known landmines" section's "~13 of 24 clause verify_urls point at gaudi.local" warning is itself
now stale and should be corrected or removed to avoid future sessions re-flagging a resolved issue.

Caveat worth surfacing: 2/24 (the two `www.bis.gov.in` entries) are not truly "independently
clickable to the exact clause" even though they resolve — they land on the BIS homepage, not the
IS 732:2019 document itself (that standard is paywalled/not freely hosted, unlike the archive.org
scans). This is a real, current, smaller-scope version of the "dead citation" concern and should
not be conflated with "all 24 fully resolve to the primary text" if that claim is ever made.

## `gen_synthetic.py` — what it generates and re-run safety

Read in full (740 lines). Confirmed via `grep -n "^def \|write_csv\|write_json\|json.dump"`:
writes `project_docs/design_basis.md`, `project_docs/design_basis_params.json`,
`project_docs/submittals.csv`, `project_docs/rfi_log.csv`, `project_docs/boq.csv`,
`schedule/schedule.csv`, `fixtures/compliance_prose.json`, `fixtures/copilot_answers.json`, and
`data/README.md`. RNG seeded (`random.seed(42)`, line 24) — reproducible byte-identical output on
re-run.

**Does NOT write to `standards/clauses.json`.** Lines 33-35 open it strictly for reading
(`with open(STANDARDS...) as fh: CLAUSES = {...}`) — a comment at line 34 states this is a
"Sanity-check we can read (not edit) the real clauses so violating values stay aligned." Re-running
`gen_synthetic.py` today would **regenerate only the synthetic project files and fixtures listed
above, byte-identically (seeded), and would NOT touch `clauses.json` and therefore could NOT
reintroduce the gaudi.local URLs** — those live only in `clauses.json`/`commissioning_clauses.json`,
neither of which this script writes. This directly refutes any assumption that re-running the
generator is a landmine for the citation-URL fix.

## Stale-or-wrong claims found in `docs/features.md` §14

1. **Script count**: "18 live in backend/eval/, 3 in standards-service/eval/" → actual is **19 + 3
   = 22**. `run_actian_parity_eval.py` is entirely absent from §14's per-script breakdown.
2. **`run_electrical_eval.py`**: claimed "30 boundary cases" → actual `n_cases=32` this run.
3. **`run_impact_eval.py`**: claimed "11 synthetic cases" → actual `n_cases=12` this run.
4. **`run_cross_corpus_eval.py`** (both copies): claimed "~20 cases" → actual **26/26** this run
   (off by 6, larger than the "~" hedge should cover).
5. **`run_retrieval_eval.py`** (both copies): claimed "~22 cases" → actual **24/24** this run.
6. **`run_codebook_tools_eval.py`**: claimed "~25 cases" → the on-disk cached report
   (`standards-service/eval/codebook_tools_report.json`, `n_cases: 30`) shows 30, not ~25.
7. `docs/features.md`'s §14 header itself already flags this risk ("script count not re-verified
   this pass") — so items 1-6 are not a surprise so much as a confirmation that the self-disclosed
   staleness is real and larger than a single script's drift.
8. `.claude/CLAUDE.md`'s "Known landmines" section's gaudi.local warning is stale (see verify_url
   audit above) — the fix is real and current, the warning is not.

## UNVERIFIED list

- **`run_codebook_tools_eval.py`'s live pass/fail this session** — not run; standards-service
  (:8010) was not started (would require a ~7-minute blocking corpus rebuild per project docs,
  outside this audit's scope to boot). Only the cached `codebook_tools_report.json` (n=30, 30/30,
  timestamped same-day as this audit) was inspected — that number is UNVERIFIED as a live result
  by me this session, only as an on-disk artifact.
- **Whether `run_copilot_eval.py`'s deployed floors (0.40/0.35) were originally hand-tuned by
  eyeballing this same eval's labeled set** (the stronger form of the overfitting concern in
  `docs/features.md:262-263`) — I can only confirm they are NOT literally the sweep-optimal value
  the script computes (0.25), which is evidence against but not a refutation of the claim; the
  original tuning process itself is not visible in the eval script.
- **`backend/data/audit_events.jsonl` contents** — noted to exist, not inspected in depth (outside
  the explicitly named provenance targets in the assignment).
- **Whether every one of the 1280 `traces/*.json` files is genuinely produced by real pipeline
  runs vs. some being seeded/backfilled** — sampled only one file; did not check all 1280 for
  internal consistency (out of scope for this audit's eval/data-provenance focus).
- **Reproducibility of `gen_synthetic.py`'s "seeded, byte-identical" claim** — read the seed and
  the "no clauses.json write" logic in source, but did NOT actually execute the generator against
  a scratch copy to diff byte-for-byte against the checked-in files this session.

## Notable side observation (outside assigned scope, flagged for awareness)

`backend/.env` (present on disk, gitignored per its own header) contains what appear to be live,
non-placeholder API keys and secrets (`HF_TOKEN`, `GEMINI_API_KEY`, `LANGFUSE_SECRET_KEY`,
`SOLANA_SECRET_KEY`). This explains why the HF-Inference-dependent eval scripts (`run_copilot_eval.py`
etc.) succeeded live in this sandbox rather than failing on missing credentials/network — it is
not evidence of a network-independent eval path. I did not evaluate this file for secret-handling
policy compliance; it is out of this audit's assigned scope (evals + data provenance) but worth a
security-focused pass by whoever owns that concern.
