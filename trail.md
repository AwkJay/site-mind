# Autonomous overnight trail — append-only audit log

Started 2026-07-24 ~22:15 per user's standing mandate: continue the HexaFalls
build unattended, log every action/decision/error here chronologically,
never rewritten or summarized after the fact. See
`memory/project_autonomous_overnight_mandate.md` (auto-memory, cross-session)
for the full task order this trail is executing against.

Session usage limit was at 98% when this mandate was given; expected resets
~23:20 and (if hit again) ~04:30. Work continues across those resets.

---

## 2026-07-24 22:15 — Mandate received

User gave a multi-phase autonomous work order and went offline. Summary of
the phases (full detail in the memory file above):
1. Finish F2 (Copilot LangGraph edge) — was mid-build (had just confirmed
   which existing functions become read-only tools).
2. G (deploy guide, doc only), H (docs), global verify checklist (#19).
3. Self-audit: re-run evals, hit endpoints, Playwright the frontend, sanity
   check features actually make sense.
4. Full docs rewrite for the user's own understanding + judge presentation:
   docs/ (not archive/), detailed_document.html (simple crash-course, no
   code, 20-30 pages, diagrams/mermaid), v3.1.html (judge deck), deck
   story/outline, features.md, architecture.md, new docs as needed.
5. gaps.md — audit findings, broken/incomplete things, feedback framing.

No tool exists to trigger `/compact` programmatically (checked via
ToolSearch — nothing found matching "compact"). Relying on the harness's
automatic context compression near its limit instead; noted so the user
knows this instruction couldn't be executed literally.

Proceeding immediately into F2 (already had the tool-function mapping done
before the mandate arrived):
- `search_codebook(query)` → `backend/app/agents/copilot.py::_hybrid_retrieve`
- `query_knowledge_base(corpus, query)` → `backend/app/retrieval/index.py::Corpus.query`,
  corpus names `"manak_structural"` / `"sitemind_existing_standards"`
  (`filesystem_corpora.py`), gated on `RETRIEVAL_ENABLED`.
- `get_open_ncrs(document_id?)` → `backend/app/agents/compliance.py::evaluate()`
  (single doc) / `backend/app/overview.py::_evaluate_all()` pattern (all docs).
- `get_schedule_risk()` → `backend/app/schedule.py::risks()`.
- `get_supply_chain_status()` → `backend/app/supply_chain.py::risks()` +
  `alerts()`.

Next: confirm langgraph / langchain-google-genai / langgraph-checkpoint-mongodb
package names via direct pip install + inspection (not guessing), matching
this session's established discipline for every other external package.

## 2026-07-24 22:30 — Stopped early per explicit user instruction; scheduled resume via CronCreate

While confirming F2's package names, discovered `backend/.venv` had no `pip`
installed (`ModuleNotFoundError: No module named pip` even via `python -m
pip`) — bootstrapped it with `python -m ensurepip --upgrade` successfully
(pip 24.0, setuptools 79.0.1 installed), but before running the actual dry-run
install the user interrupted: **"continue only after limit resets! dont use
credits! ... save this task"**. Overriding the earlier "keep working
regardless" instruction — usage/rate-limit conservation now takes priority.

Stopped all work immediately per that instruction. Used `CronCreate` (a
session-scheduler tool) to schedule two one-shot wake-up prompts:
- Job `ca70044a` — fires 2026-07-24 23:20 local time.
- Job `fbab111e` — fires 2026-07-25 04:30 local time (fallback, in case the
  23:20 attempt also hits the usage ceiling).

**Important caveat surfaced to the user**: `CronCreate` jobs are
session-only — in-memory, not persisted to disk, and lost if this Claude
Code session/process exits (terminal closed, machine restarted, app quit).
They are NOT a guaranteed resume mechanism independent of the running
process. Flagged this explicitly rather than overstating reliability.

Both cron prompts point back at
`memory/project_autonomous_overnight_mandate.md` (the full task order) and
this file (trail.md) so whichever one fires can pick up exactly where this
entry left off: mid-way through confirming F2's LangGraph package names,
right after fixing the venv's missing pip.

No further tool calls this turn — waiting for a scheduled wake-up or the
user's return.

---

## 2026-07-24 23:20 — Cron job ca70044a fired, resuming F2

Usage limit reset as expected. Resuming exactly where the previous entry left
off: F2 (Copilot LangGraph edge), right after fixing `backend/.venv`'s
missing pip. Continuing to confirm real package names via direct pip
dry-run install (not guessing).

Confirmed via real dependency resolution (`pip install --dry-run`):
`langgraph==1.2.9`, `langchain-google-genai==4.3.1`,
`langgraph-checkpoint-mongodb==0.4.0` — all resolve, but
`langchain-mongodb` (langgraph-checkpoint-mongodb's dependency) requires
`pymongo>=4.12`, conflicting with the `pymongo[srv]==4.9.2` pin from
Workstream D. Checked `app/audit.py`'s pymongo usage — a single plain
`pymongo.MongoClient(...)` call, safe to bump. Bumped requirements.txt to
`pymongo==4.16.0` (dropped the now-nonexistent `[srv]` extra — pymongo>=4.16
warns "does not provide the extra 'srv'"; dnspython is already a plain
dependency, confirmed present after install).

**Found and fixed a real pre-existing bug while doing a full fresh
`pip install -r requirements.txt`** (not just incremental adds): the file
hard-pinned `pydantic==2.9.2`, but `solana==0.40.1` (added in Workstream E)
actually requires `pydantic>=2.13.4` — a `ResolutionImpossible` on a truly
fresh install, even though the live dev venv (built incrementally, package by
package) already had pydantic transitively upgraded to 2.13.4 and was running
fine. This means anyone cloning fresh and running `./run.sh` would have hit a
hard install failure. Fixed by bumping the pin to `pydantic==2.13.4` (the
exact version already proven working live all session). Full
`pip install -r requirements.txt` now installs clean with zero
errors/warnings from a cold read of the file.

**Also found and fixed** (while re-running the test suite to check for
regressions from the pydantic bump): `tests/test_llm_extract.py`'s
`DEMO_TXT_PATH` pointed at `../docs/demo_files/Structural-Design-Basis-Report_DEMO.txt`,
but no `docs/demo_files/` directory exists — the real file lives directly at
`docs/Structural-Design-Basis-Report_DEMO.txt`. Pre-existing/unrelated to
today's changes (likely stale from an earlier docs reorganization this
project's history). Fixed the path; `pytest` now: 29 passed (was 2 failed,
27 passed).

**Noted, not acted on**: `git log`/`git status` show this repo currently has
**zero commits** — `.git` was freshly initialized 2026-07-24 18:23 (matches
completed task #1, "Step 0: Git reset — fresh HexaFalls history" — an
intentional fresh-history pivot from an earlier part of this session, not a
mistake from tonight). Every file in the repo is currently untracked. Not
committing anything per the standing "never commit/push unless asked" rule —
flagging this for `gaps.md` later so the user remembers to commit before
any submission deadline.

Ran `python -m eval.run_eval` after the pydantic/pymongo bump: still
`acc=1.0 macroF1=1.0 hallucination=0.0` (n=41) — no regression.

**Second, bigger bug found while trying to hash-compare eval reports**:
`source .venv/bin/activate` was silently activating the WRONG virtualenv.
`backend/.venv/bin/activate` (and `.csh`/`.fish`/`.nu`/`.bat`) had a
**hardcoded stale absolute path** —
`VIRTUAL_ENV='/home/awni/Documents/hackathon/sitemind/backend/.venv'`
(missing `hexafalls/`) — left over from when this project directory was
renamed/moved (evidence: `/home/awni/Documents/hackathon/` still has the old
`sitemind/`, `sitemind2/`, `sitemind-backup/`, `sitemind2-backup/`,
`sitemind-ft-old/` directories from that migration). Every
`source .venv/bin/activate; python ...` I'd run today was actually running
the OLD venv (confirmed: `sys.executable` resolved to the old path,
`actian_vectorai`/`pydantic 2.13.4`/`pymongo 4.16.0` were all absent there).
Explicit `.venv/bin/python -m pip ...` calls were unaffected (correct venv)
— which is why the earlier package installs/dry-runs were fine but `source
.venv/bin/activate; python -m pytest`/`eval` runs were silently testing the
wrong environment. This also explains why `nohup bash run.sh` failed
earlier tonight/last session with `pip: command not found` (PATH was
prepended with the old, pip-less venv's bin dir) — I'd worked around it at
the time with an explicit `.venv/bin/python -m uvicorn ...` launch instead
of diagnosing the root cause. The actually-running backend server tonight
was therefore fine throughout (started via explicit path), but every
"verification" run via `source .venv/bin/activate` today (before this fix)
was not testing what I thought it was.

Fixed via `sed` on the 5 broken activate scripts (bash/csh/fish/nu/bat),
replacing the stale path with the real one. Console-script shebangs (e.g.
`.venv/bin/pytest`) may still carry the old path for packages installed
before the directory move — not fixed individually since `python -m X`
invocation (which I use throughout) doesn't go through the shebang, only
through `sys.path` derived from the real interpreter. `uvicorn`'s shebang
was already correct (likely reinstalled/upgraded since the move), so the
live backend process is unaffected either way.

**Re-ran everything for real against the correctly-activated venv**:
`pytest` → 29 passed (same as the tainted run — the DEMO_TXT_PATH source fix
holds regardless of venv). Full eval suite (all 16 `run_*_eval.py` scripts +
`run_eval.py` + `run_actian_parity_eval.py` with the live Actian container +
`run_copilot_eval.py`) → 100% accuracy across every one, actian parity 5/5.
Hash-compared all 19 `eval/*_report.json` files against this session's
pre-change baseline: **byte-identical except the one already-documented
timing-noise report** (`copilot_report.json`'s `corpus_embed_ms`/
`single_query_embed_ms`/`total_runtime_s` — never a real regression, called
out repeatedly earlier this session). Confirms zero regression from
pydantic 2.9.2→2.13.4, pymongo 4.9.2→4.16.0, and the langgraph/
langchain-google-genai/langgraph-checkpoint-mongodb additions.

Proceeding to the actual F2 build (`copilot_agent.py`).

Built `backend/app/agents/copilot_agent.py` (new file, plan §F2): 5 read-only
tools (`search_codebook`→`copilot._hybrid_retrieve`,
`query_knowledge_base`→`Corpus.query`, `get_open_ncrs`→`compliance.evaluate`/
`overview._evaluate_all`, `get_schedule_risk`→`schedule.risks()`,
`get_supply_chain_status`→`supply_chain.risks()+alerts()`), a lazily-built
LangGraph `create_react_agent` (Gemini via `ChatGoogleGenerativeAI`), an
optional `MongoDBSaver` checkpointer (same Mongo instance as the Workstream D
audit ledger, `copilot_checkpoints` collection; falls back to stateless if
`MONGODB_URI` unset), and a new `POST /api/copilot/chat` endpoint (mounted
unconditionally in `main.py`, alongside the untouched `/ask`) that falls back
to the existing single-shot `copilot.answer()` whenever the flag/key/agent
build isn't available.

Confirmed real API shapes by direct inspection (not guessed), and found two
non-obvious behaviors that would have caused silent bugs if assumed:
1. A `@tool`-decorated function's return value, when invoked as part of a
   real ToolCall (the actual code path `create_react_agent`'s ToolNode
   uses), comes back as a **JSON-encoded string** in `ToolMessage.content`,
   not the raw Python object — confirmed by constructing a real `ToolMessage`
   directly and inspecting it. Fixed `run_chat()`'s source-extraction to
   `json.loads()` it.
2. `AIMessage.content` is typed `str | list[str | dict]` (Gemini/Anthropic
   can both return multi-block content, e.g. thinking blocks) — added
   `_text_of()` to join only the text parts rather than assuming a plain
   string.

Verified without spending live Gemini quota: (a) importing the module with
the flag off touches zero langgraph/langchain_google_genai imports
(asserted directly via `sys.modules`); (b) with `COPILOT_AGENT_ENABLED=1`
and the real Gemini key, `_get_agent()` successfully BUILDS a compiled graph
(construction only, no `.invoke()` — that would cost quota); (c) via real
HTTP, `POST /api/copilot/chat` (flag off, default) returns the correct
existing fixture answer + a generated `thread_id`, proving the fallback path
end-to-end. Added `tests/test_copilot_agent.py` (11 tests, all passing) —
flag/key gating, `/chat` fallback + thread_id echo, `_text_of` both content
shapes, and all 5 tools' read-only correctness (including two real
abstention cases: gibberish query, unknown corpus name) — all without
touching the live LLM.

**Deferred to later.md** (matching this session's established discipline):
the actual `agent.invoke()` round-trip through a real Gemini tool-calling
loop is UNTESTED live — construction-only was verified to avoid burning the
scarce Gemini free-tier quota (20/day, already touched tonight). First live
call should be watched for: correct tool selection, the JSON-string
ToolMessage parsing above, and that abstention phrasing actually fires when
a tool returns `[]`.

Also updated `docker`-adjacent nothing (n/a). Marked task #16 (F2) completed.

## 2026-07-25 00:10 — Workstream G: DigitalOcean deploy guide (doc only)

Wrote `digitalocean.md` at repo root per plan §G — a deploy GUIDE only, not
an actual deployment (credits unconfirmed, matches the plan's explicit
"deferred" framing). Adapted the already-LIVE `render.yaml` (this project's
real, working Render config) into an illustrative DigitalOcean App Platform
spec, explicitly flagging every piece that's unverified against a real
`doctl` deploy (cross-service URL interpolation syntax, the `workers:` key
for the Telegram bot, App Platform's Python version pinning mechanism,
Actian's Docker+volume support on App Platform). Covered: all 5 services'
specs, Actian on DO (3 options incl. "just use numpy, skip it"), Managed
MongoDB vs Atlas (zero code difference, just a connection string), the full
env var checklist from plan §9, and a Droplet+nginx/Caddy alternative
(argued as likely the more reproducible path for a judge, given App
Platform's uncertainty around Actian's persistent volume needs).

Marking task #17 (G) completed. Moving to H (narrative & docs update) per
the mandate's task order.

## 2026-07-25 00:25 — Workstream H: narrative & docs update

Updated `README.md`'s top section (title, opening framing, "the one idea
that matters") to the new HexaFalls positioning from plan §2: broader
megaproject framing, the one-liner, both verdict tiers explained
(certified + computed-draft), Gemini as the current default prose provider
(was still saying "Claude Sonnet 4.6" — now corrected, with Anthropic/Codex
noted as still-supported alternates), and the honesty guardrails
(tamper-evident not tamper-proof, AI-drafted-engineer-confirmed, synthetic
data disclosure) folded in verbatim from the plan rather than paraphrased
loosely. Added an "Audit Ledger" bullet + a new "HexaFalls additions
(flag-gated, default-off)" subsection to the Features list covering Actian,
Solana, the LangGraph copilot edge, and the Telegram bot — each stating its
env var and that it degrades gracefully off.

Created `docs/HEXAFALLS_PITCH.md` (new file, plan §H — "reuse DEMO_STORY.md
or create a new one": created new, since DEMO_STORY.md's existing 376 lines
are still-accurate 5-pillar walkthrough content, not sponsor-integration
content, so extending it would have diluted a doc that already works).
Contains the narrative arc table (Perceive/Retrieve/Decide/Remember/
Prove/Reach-the-field) and an exact click-path per sponsor moment (Gemini,
Actian, MongoDB, Solana — including the full tamper-then-verify "money shot"
sequence written out step-by-step, Telegram+ElevenLabs, LangGraph), plus the
honesty guardrails repeated once at the end for stage reference.

Did NOT touch the `gaudi.local` dead-citation-link landmine itself (fixing
~13 of 24 real `verify_url`s is a data-migration task, not a docs task) —
the existing README caveat about it is still accurate and left as-is; noting
it again for `gaps.md` in the audit phase rather than fixing it now, since H
was scoped as docs-only and this needs actual citation-data changes.

Marking task #18 (H) completed. Moving to #19 (global pre-demo verification
checklist) per the mandate's task order.

## 2026-07-25 00:40 — Task #19: global pre-demo verification checklist (plan §8)

Worked through the plan's own §8 checklist item by item:

- **Keyless boot**: initially tried `env -i` to strip env vars, but `config.py`
  calls `load_dotenv(BACKEND_DIR / ".env")` by explicit path, so shell-env
  stripping doesn't matter — it reads the FILE directly. Properly tested by
  temporarily renaming `backend/.env` aside, booting a second uvicorn
  instance on :8099, confirming `/api/health` → `offline_mode: true,
  provider: offline`, and a real compliance check against
  `DC1-02-DBR-0001-R2` → 10 checked params, 6 NCRs, 4 conforming — a full
  real deterministic result, zero crash, zero key. **Scare during cleanup**:
  a combined `mv .env.tmp... .env && pkill ... && diff ...` command returned
  a nonzero exit (144) and the restore `mv` silently did not execute,
  leaving `backend/.env` MISSING for a few tool calls before I caught it via
  `ls -la .env` failing. Fixed immediately via `cp` from a backup I'd taken
  before starting (copied to scratchpad first, good habit that paid off) —
  confirmed byte-identical via `diff`, confirmed the live dev backend on
  :8000 (which had the file open at boot, unaffected either way) still
  reports `provider: gemini` correctly. No actual data loss, but noting this
  as a close call: multi-step destructive-ish shell chains in this
  environment should be split into separate tool calls and verified after
  each step, not trusted as one atomic block.
- **`python -m eval.run_eval` + every `run_*_eval.py` unchanged**: done
  earlier tonight (see the pydantic/pymongo bump entry above) — confirmed
  byte-identical except the one known copilot timing-noise report.
- **`run_actian_parity_eval.py` against live Actian**: done earlier tonight,
  5/5 pass.
- **Gemini `/api/health` shows `provider: gemini`**: confirmed (live backend,
  right now). Prose model-written: confirmed earlier this session (B2 work)
  and again via tonight's `/api/copilot/chat` fallback test. Vision reading
  an image: **N/A — Workstream B (Gemini Vision) was explicitly skipped per
  user request**, not a failure, just out of scope.
- **B2 tiered verdicts**: `pytest tests/test_rule_eval.py` green (part of
  tonight's 40-passed run). Live rule-less-param → computed_draft with a
  real cited clause was proven earlier this session (pre-compaction,
  documented in the conversation summary); not re-run tonight to conserve
  Gemini's scarce free-tier quota. Flag off → evals byte-identical: confirmed
  tonight (COMPLIANCE_RULE_EXTRACTION defaults to 0 in every eval run above).
- **F2 copilot edge**: flag off/no key → confirmed live via real HTTP
  tonight. Flag on multi-pillar answer + thread_id memory: agent
  CONSTRUCTION confirmed (compiles clean with a real key), full
  `agent.invoke()` round trip deliberately not run live tonight (quota
  conservation, logged in `later.md`). `copilot_agent.py` imports nothing
  from `checks.py`/`rule_eval.py`: confirmed via grep (only appears in a
  comment).
- **Mongo**: ingest → stable `content_hash`, no-Mongo → JSONL fallback: both
  proven earlier this session (Workstream D) and reconfirmed live tonight
  (`/api/health` → `audit_backend: local_jsonl`, matching the current unset
  `MONGODB_URI`).
- **Solana**: anchor → real devnet tx on Explorer, verify green, tamper →
  verify red: all done live tonight (Workstream E resume) — real tx sig
  `2wjsGR6xjvnnr7wChYbc6Gdgsy5MmaEEj1ijrMgisR5rU9fL9TeAL3N8nDjyQzc2tbewb6XhnphA9hYKCBW4wXce`
  visible on Explorer, `mongo_intact`/`chain_intact` both demonstrated.
- **Telegram**: bot is running, every component (STT, TTS, translation,
  backend call, abstain phrasing) individually live-verified tonight — but
  **no actual Hindi-voice-note round trip from a real phone has happened
  yet**. Outstanding, needs the user to actually message `@Sitemind_bot`;
  documented in `later.md`'s F1 section already.
- **No secrets committed**: repo currently has ZERO commits at all (fresh
  `git init` from an earlier session, per completed task #1) so trivially
  true right now, but checked `.gitignore` COVERAGE properly anyway (not
  just "nothing's committed yet") since that's what actually matters before
  the first real commit:
  - All `.env` files (backend, standards-service, telegram-bot,
    frontend/.env.local) confirmed ignored via `git check-ignore -v`.
  - **Found two real gaps**: `actian_data/` (the Actian Docker volume — real
    DB files, machine-specific) and `backend/data/audit_events.jsonl` (the
    regenerated local ledger) were NOT covered by any `.gitignore`. Fixed
    both — added `data/audit_events.jsonl` to `backend/.gitignore` and
    `actian_data/` to the root `.gitignore`, confirmed via `git check-ignore`
    that both are now correctly excluded.
  - Solana's secret key is never written to a separate keypair file
    (confirmed via grep on `scripts/solana_setup.py` — it only prints to
    stdout for the user to paste into the already-ignored `.env`), so no
    additional keypair-file gitignore entry was needed.
  - **Found and noted, not fixed**: `backend/.env.local` contains InsForge
    (`NEXT_PUBLIC_INSFORGE_URL`/`NEXT_PUBLIC_INSFORGE_ANON_KEY`) — a BaaS
    service never mentioned anywhere else in this codebase or the HexaFalls
    plan. `.env.local` isn't the filename `config.py`'s `load_dotenv()`
    loads (`.env` exactly), so it's inert/unused, and `.gitignore` already
    has both a blanket `.env.local` pattern (root) and an explicit
    `.insforge` directory-name entry (backend) — so this stray file poses no
    real risk (already ignored, already dead). Flagging for `gaps.md` as
    leftover cruft worth deleting during a cleanup pass, not touching it now
    since it's out of scope for a verification checklist.

Marking task #19 completed. Moving to task #20 (self-audit: re-verify
pillars work via evals/endpoints/Playwright) per the mandate's task order.

## 2026-07-25 00:55 — Task #20: self-audit via Playwright across every page

Frontend dev server already running (`:3000`), backend already running
(`:8000`, real Gemini key). Drove all 10 nav pages in a real browser via
Playwright (not just curl): Compliance, Copilot, Schedule, Supply Chain,
Commissioning, Timeline, Knowledge Graph, Knowledge Base, Codebook, Audit
Ledger, plus Overview (`/`).

- **Compliance**: clicked "Run compliance check" on the real Structural DBR
  → rendered "Checked 10 parameters, 6 finding(s), 4 conforming, 12 clauses
  cited across 3 standards" (matches the keyless-boot API test exactly) +
  NCR-0001 with the correct "CERTIFIED · PRE-VETTED" tier badge, overlapping-
  requirements resolution panel, everything legible and sensible. Zero
  console errors.
- **Copilot**: cited answer + 4 numbered sources rendering correctly, zero
  console errors.
- **Audit Ledger**: zero console errors (already visually verified earlier
  tonight with the live Solana anchor/verify demo).
- **Schedule, Supply Chain, Commissioning, Timeline, Knowledge Graph,
  Overview**: zero console errors on all six.
- **Knowledge Base, Codebook**: each threw 2 console errors
  (`404 /api/retrieval/corpora`, `404 /api/codebook/corpora`) — but this is
  the CORRECT, already-designed graceful-degradation behavior, not a bug:
  `RETRIEVAL_ENABLED`/`CODEBOOK_ENABLED` are both off on this running
  backend instance, and the Knowledge Base page's actual rendered UI (via
  screenshot) shows the honest, correctly-worded fallback message
  ("Knowledge Base is not enabled in this environment... Start the backend
  with RETRIEVAL_ENABLED=1") rather than a broken page. Confirmed via
  screenshot, not just the console log, since a console error alone doesn't
  tell you whether the UI degraded gracefully or actually broke.

No real bugs found in this pass — every page either worked fully or degraded
exactly as designed. Cleaned up 4 screenshot PNGs this left in the repo root
(moved to the session scratchpad, not the repo).

Marking task #20 completed. Moving to task #21 (rewrite
`detailed_document.html` as a plain-English crash course) per the mandate's
task order — the largest remaining task, budgeting carefully against the
approaching 4:30 AM fallback window.

## 2026-07-25 01:15 — Task #21: rewrote docs/detailed-document.html

The user's mandate named `detailed_document.html` (underscore); the real
file is `docs/detailed-document.html` (hyphen) — an 800-line file from the
original ET AI Hackathon build. Confirmed via `find` there's no
underscore-named file anywhere under `~/Documents`; this hyphenated one is
clearly what was meant (matches "old file of another hackathon" exactly).

Fully rewrote it (not edited in place — user explicitly said removal/full
rewrite was fine) as a plain-English, no-code crash course: 12 sections
(where this came from, the core "LLM never computes a verdict" idea with a
3-step mermaid diagram, all 5 original pillars with real-world scenarios,
the tiered-verdict system explained via a table, all 6 HexaFalls additions
each explained in plain terms with their real-world justification, an
architecture mermaid diagram, an annotated folder tree, a "day in the life"
narrative covering all 5 pillars, a run guide, a real-vs-representative
table, a full glossary of every jargon term used elsewhere in this doc, and
a short gaps pointer to the upcoming `gaps.md`). Self-contained dark-themed
HTML with an inline `<style>` block and mermaid.js pulled from a CDN (fine
for a local personal-reference file opened with real internet access,
unlike a sandboxed published Artifact).

Verified it actually renders (not just that the HTML is well-formed):
Playwright can't load `file://` URLs directly (blocked), so served it via a
throwaway `python3 -m http.server 8765` in `docs/`, navigated Playwright to
it, confirmed zero real console errors (only a harmless missing-favicon
404), and screenshotted both the table of contents area and the first
mermaid diagram (the Perceive → Decide → Explain flow) — it rendered
correctly as a real diagram, not broken markup. Killed the temp server and
moved the screenshot PNGs out of the repo root to the scratchpad afterward.

Marking task #21 completed. Moving to task #22 (update `docs/v3.1.html`,
the judge-facing slide deck) per the mandate's task order.

## 2026-07-25 01:35 — Task #22: updated docs/v3.1.html (judge slide deck)

This file is a heavily-designed 13-slide deck with embedded base64 fonts and
a screenshot image (~800KB total, individual lines up to 130,000 chars).
Reading it directly hit the 25,000-token Read-tool ceiling on even a small
line range. Worked around it by `awk 'length($0) < 2000'`-filtering into a
scratch copy that excludes the giant base64 lines (only 11 lines were
affected), read THAT to plan edits, then applied the actual edits via the
Edit tool directly against the real file (which does exact-string matching,
so the giant excluded lines were never a problem for editing — only for
reading).

Chose targeted content edits over a full rewrite (unlike
detailed-document.html): this deck's visual design/CSS/embedded assets are
still fine and expensive to reproduce faithfully; only the CONTENT was
stale. Fixed: the cover's "ET AI Hackathon 2026 · Problem #4" eyebrow and
narrow "data-centre EPC delivery" pitch → HexaFalls/megaproject positioning
with the tamper-proof-on-chain framing; two "Claude Sonnet 4.6" mentions →
Gemini (noting other providers still supported); the "Idea" slide's pitch
line → now mentions both verdict tiers (certified + computed-draft) instead
of only the single original tier; the closing "Vision" slide's roadmap →
removed items that are now actually shipped (they used to describe future
work) and added a "beyond data centres" bullet reflecting the real
repositioning; a stray "21/21" eval count in the Vision slide's footer
(a specific number I have no way to freshly verify against the CURRENT
eval script count — this session's runs never printed a total script count)
replaced with "Real evals passing today" to avoid asserting an unverified number.

Added ONE new slide (09b · "The HexaFalls additions"), inserted between the
existing "standards backbone" slide and "Impact & Scale", reusing the deck's
own existing `.tour`/`.row` list pattern and existing SVG icon symbols
(`i-search`, `i-node`, `i-chat`, `i-atom` — no new icons defined, to avoid
touching the SVG symbol library) — one row each for Actian, MongoDB+Solana
(paired, since they're one combined "remember + prove" idea), Telegram+
ElevenLabs, and LangGraph, each with its one-line "why it's not decoration"
justification.

Verified by rendering, same `http.server` + Playwright technique as the
detailed-document.html check: zero real console errors (only the harmless
missing-favicon 404), confirmed the cover slide renders exactly as intended
via screenshot, and confirmed the new Additions slide renders with correct
icons/typography/spacing matching every other slide — the deck's own
JS slide-counter picked it up automatically (it enumerates `.slide`
elements dynamically, no hardcoded slide count to update), showing
"11 · ADDITIONS" in the progress header with no manual JS changes needed.

Marking task #22 completed. Moving to task #23 (update docs/features.md,
docs/architecture.md, deck story/outline) per the mandate's task order —
budgeting the remaining time carefully against the 4:30 AM fallback.

## 2026-07-25 01:50 — Task #23: updated docs/features.md, docs/ARCHITECTURE.md, docs/DECK_OUTLINE.md

Found the actual filename is `ARCHITECTURE.md` (uppercase, not `architecture.md`
as the mandate wrote it) — same directory, easy to confirm via `ls`.

- **`features.md`** (dated 2026-07-12, otherwise still-accurate per-route
  inventory): updated the header date, extended §3 (Copilot) with a new
  bullet describing the LangGraph `/chat` endpoint (tools, gating, the
  hard-boundary note that it can't import `checks.py`/`rule_eval.py`, and
  that the frontend still defaults to `/ask`), and added two brand-new
  numbered sections in the same style as the rest of the file: §12 Audit
  Ledger (table/buttons, Mongo-vs-JSONL fallback, the Solana
  anchor/verify/tamper mechanics including the exact
  `mongo_intact`/`chain_intact` combination that proves tampering) and §13
  Telegram field bot (the full STT→translate→ask→translate→TTS pipeline,
  the confirmed-live Ogg/Opus format detail, the abstention behavior).
  Renumbered the old §12 eval-suite section to §14 and softened its opening
  claim (an exact "21 scripts" count I have no fresh source for this
  session) to point at PROGRESS.md instead of asserting a number I hadn't
  personally re-verified.
- **`ARCHITECTURE.md`**: this file's "Where we ARE agentic, and where we
  deliberately are not" section pre-dates HexaFalls and asserts a blanket
  "why NOT a framework... even here" — no longer fully true given F2. Rather
  than rewrite that whole philosophical section (still correct for every
  pillar it actually describes), inserted a new "HexaFalls update — the
  framework rule is now scoped, not blanket" section directly after it,
  explaining precisely why `copilot_agent.py`'s LangGraph use doesn't
  contradict the stated position: read-only tools only, no import path to
  the verdict core, gated + lazily imported.
- **`DECK_OUTLINE.md`**: describes two ET-hackathon-era decks
  (`docs/deck/index.html`, `docs/deck/pitch.html`) scored against that
  hackathon's specific rubric — not a fit for a from-scratch rewrite given
  `docs/v3.1.html` (updated this session) and `docs/HEXAFALLS_PITCH.md`
  (written this session) already cover the current deck + click-path.
  Added a banner at the top pointing to both of those as the current
  materials and marking everything below as historical reference only, not
  to present from.

Marking task #23 completed. Moving to the final task, #24 (write
`docs/gaps.md`) per the mandate's task order.

## 2026-07-25 02:00 — Task #24: wrote docs/gaps.md

Compiled every finding from this entire session (both tonight's continued
work and the earlier pre-compaction work, via the conversation summary) into
one organized, honest audit doc — explicitly framed as feedback for
improvement, not a bug tracker, per the mandate's instruction. Structured
into three tiers: things worth fixing before a demo if time allows (zero git
commits, the gaudi.local dead links, F2's un-invoked live agent loop, the
Telegram bot's never-actually-messaged status, Vision being un-started, B2's
pending live re-verification), smaller things already found-and-fixed
tonight (the InsForge stray file, the two gitignore gaps, the stale test
path, the pydantic/pymongo fresh-install bug, Actian's un-activated license
key, digitalocean.md's unvalidated-against-real-doctl status, the frontend
not yet using /chat), and always-disclosed known limitations (synthetic
data, labelled ROI assumptions, commissioning's cooling-only scope) repeated
here just for completeness. Added one explicit process-note item about
tonight's close call with the `.env` file during the keyless-boot test, framed
honestly as a fragility to watch for, not swept under the rug.

Marking task #24 completed. **This closes out every task in the standing
mandate** (F2 → G → H → #19 → #20 self-audit → #21 detailed-document.html →
#22 v3.1.html → #23 docs/ → #24 gaps.md).

---

## 2026-07-25 02:00 — Mandate exhausted; session checkpoint

Every task the user handed off before going offline is now done. Summary of
what shipped tonight, for a quick read without scrolling the whole log:

- **F2** (LangGraph Copilot edge): built, tested (11 new unit tests),
  live-verified except the actual agentic loop invocation (quota-conserved).
- **G** (`digitalocean.md`): written, explicitly caveated as unvalidated.
- **H** (README + `docs/HEXAFALLS_PITCH.md`): positioning updated, new pitch
  doc written.
- **#19** (global verify checklist): worked through every item in the plan's
  own §8 list; found and fixed 2 real `.gitignore` gaps in the process.
- **#20** (self-audit): drove all 10 nav pages + Overview in a real browser,
  zero real bugs found.
- **#21** (`docs/detailed-document.html`): fully rewritten as a 12-section,
  no-code, plain-English crash course with 2 mermaid diagrams.
- **#22** (`docs/v3.1.html`): judge deck's stale positioning fixed, a new
  13th slide added for the HexaFalls sponsor additions.
- **#23** (`features.md`, `ARCHITECTURE.md`, `DECK_OUTLINE.md`): all brought
  current.
- **#24** (`docs/gaps.md`): this file, just written.

Also found and fixed along the way (not originally on the list): a stale
test file path (`tests/test_llm_extract.py`), a pydantic/pymongo version
conflict that would have broken a fresh `pip install`, two missing
`.gitignore` entries, and a broken `backend/.venv/bin/activate` script with
a hardcoded stale path from before this project's directory was renamed.

**No further tasks remain in the standing mandate.** Per its own instruction
("otherwise keep finding productive next steps... rather than idling"), the
honest next-highest-value items are the ones flagged in `gaps.md` #1-6 —
but most of those need either the user's presence (approving a first git
commit) or spending more of the scarce Gemini quota (the F2 live-invoke
test, a fresh B2 re-verification) or the user's phone (the Telegram
round-trip) — none of which should be done unilaterally overnight. Pausing
here as a clean checkpoint rather than manufacturing lower-value busywork.
Both the backend (`:8000`) and frontend (`:3000`) dev servers and the
Telegram bot are still running in the background for whenever the user
wants to look at any of this live.

---

## Session resumed 2026-07-25 — new mandate: 5 explicit follow-up items

User returned, gave 5 new explicit tasks (not asking questions, full
autonomy again): (1) rename `manak_structural` -> `structural_standard_codes`
everywhere; (2) replace dead `gaudi.local` verify_url links with a proper
in-app clause-viewer popup instead of an external link; (3) fix the Telegram
bot so it has full project access (not just abstaining) + caching + voice
replies; (4) create `docs/know.md` + `docs/know/` researching what real
public project/tenders the synthetic demo data is modelled on; (5) finish
remaining backlog tasks except Gemini Vision. Logged as tasks #25-28 in the
task tracker (plus pre-existing #11 B2 Verify).

**#25 (manak_structural rename) — DONE.** Renamed the corpus identifier
string (`manak_structural` in backend/, `codebook_structural` in
standards-service/ — these had already partially diverged) to
`structural_standard_codes` everywhere: both `filesystem_corpora.py` files
(constant renamed `MANAK_CORPUS_NAME`->`STRUCTURAL_CORPUS_NAME`,
`MANAK_LIB_DIR`->`STRUCTURAL_LIB_DIR`, `_manak_md_files`->
`_structural_md_files`, `build_manak_structural_corpus`->
`build_structural_standard_codes_corpus`), `compliance.py`, `mcp_server.py`
(imports + 2 docstring examples), `frontend/app/codebook/page.tsx` (2 UI
text mentions), `copilot_agent.py` (1 docstring example), and all 4 eval
scripts (`backend/eval/run_cross_corpus_eval.py`,
`run_actian_parity_eval.py`, `standards-service/eval/run_cross_corpus_eval.py`,
`run_codebook_tools_eval.py`) — imports, string literals, and prose mentions.
Left the historical "renamed from manak_structural" comments as-is
(accurate rename history, not the identifier itself) and left the unrelated
`"manak_indexed"`/`"codebook_verified"` provenance_tag enum values and
`manak-dev` historical-directory prose untouched (a separate naming concern,
not what was asked). Verified: backend `pytest` 40/40 unrelated tests still
pass, `python -m eval.run_cross_corpus_eval` 26/26, `python -m
eval.run_actian_parity_eval` 5/5 — all against the renamed corpus, same
pass rate as before the rename. standards-service never had a venv in this
checkout; created one with `uv venv --python 3.11` (system python is 3.14,
too new for pydantic-core's pinned wheel) to verify its copy too.

**#26 (gaudi.local -> in-app clause viewer) — DONE (backend half).**
Investigation finding worth flagging: the LIVE `clauses.json` /
`commissioning_clauses.json` (24 + 5 clauses) actually have ZERO gaudi.local
links already — all real `archive.org` URLs. `gaps.md`'s "~13/24 point at
gaudi.local" claim is now stale (fixed in an earlier, undocumented pass).
The remaining gaudi.local mentions are all in inert files: `standards.py`'s
`_FALLBACK` dev safety net, `data/fixtures/copilot_answers.json`,
`data/gen_synthetic.py` (the original generator script — a real landmine:
if ever re-run it would silently regenerate clauses.json WITH gaudi.local
again), and `frontend/lib/mocks.ts` (unused-unless-backend-down mock data).
Separately from the dead-link question, built the actual feature requested:
a proper in-app clause viewer instead of any external link at all. New
`backend/app/clause_viewer.py` + `GET /api/clause-context?standard=&clause=`
reads the REAL digitised `.md` source file directly off disk (same files
`structural_standard_codes` indexes) and extracts the verbatim markdown
section around the cited clause number (exact-heading match, falling back
to the parent heading for numbered sub-items like "26.4.2.2" under section
"26.4.2"). Deliberately does NOT depend on RETRIEVAL_ENABLED — reads files
directly, so OFFLINE_MODE's zero-flag path is untouched. Honest by design:
only 3 of ~10 cited standards (IS 456:2000, IS 1893 (Part 1):2016, IS 875
(Part 3):2015) have a real local `.md` source; the rest (CEA regs, IS 3043,
IS 732, IS 8623, ASHRAE) honestly report `has_context=False` with a
plain-language reason rather than fabricating anything. New
`tests/test_clause_viewer.py`, 5/5 passing (exact-heading match, parent-
heading fallback, second mapped standard, unmapped standard, bogus clause
number). Mounted in `main.py`. Frontend modal (the actual popup UI in
`CitedClauseBox.tsx`) is next.

Also discovered during the full-suite pytest run: 3 pre-existing tests in
`test_copilot_agent.py` fail in THIS sandbox with `httpx.ReadTimeout` —
confirmed via a direct `curl` that `api-inference.huggingface.co` is simply
unreachable from this sandboxed shell (network egress restriction), not a
real regression. None of tonight's edits touch `copilot.py`/
`embeddings.py`/the HF call path at all — pre-existing environment
flakiness, not caused by the rename or the new clause_viewer module.

Verified standards-service's own copy too (it never had a venv in this
checkout — created one with `uv venv --python 3.11` since system python is
3.14): `run_cross_corpus_eval.py` 26/26, and while chasing
`run_codebook_tools_eval.py` found and fixed a genuine pre-existing bug
unrelated to tonight's rename — `MANAK_SOURCE_FILE` was a hardcoded absolute
path to the OLD external `manak-dev` project directory
(`/home/awni/Documents/Project_hackathon/manak-dev/lib/...`) that no longer
exists (the files were copied in-repo a while back per
docs/codebook_changes.md, but this one eval-only constant was never
updated). Fixed to a repo-relative path; eval now 30/30 passing.

**#26 (gaudi.local -> in-app clause viewer) — frontend half DONE, fully
verified live.** Added `ClauseContext` type (`frontend/lib/types.ts`),
`getClauseContext()` API client fn (`frontend/lib/api.ts`, honest
"backend unreachable" fallback, never a fabricated excerpt), and a new
`ClauseViewerModal.tsx` component (Escape-to-close, click-outside-to-close,
`role="dialog"`). `CitedClauseBox.tsx`'s "View standard" link is now a
button that opens the modal instead of navigating to an external URL
(`ExternalLink` icon swapped for `FileSearch`); the citation's real
`verify_url` (archive.org, now that gaudi.local is gone everywhere) is kept
as a small secondary "Primary source" link inside the modal, not the
primary action. `npx tsc --noEmit` clean.

Verified live end-to-end via Playwright against the running dev servers
(no mocks): ran a real compliance check on the "Foundation shop drawing —
footing F-12" submittal, clicked "View standard" on both resulting NCRs —
(1) IS 456:2000 Cl 26.4.2.2 (the parent-heading-fallback path, since
"26.4.2.2" itself isn't a markdown heading) correctly showed the "26.4.2
Nominal Cover..." section with 26.4.2.1/26.4.2.2 both visible; (2) Cl 8.2.8
(the exact-heading-match path) correctly showed the full "8.2.8 Concrete in
Sea-water" section including 8.2.8.1-8.2.8.4. Both modals' "Primary source"
link correctly pointed at `archive.org` (not gaudi.local). Zero console
errors/warnings in either case.

Also fixed, while chasing the gaudi.local links: the underlying data files
that were STILL producing gaudi.local links even though clauses.json itself
had already been fixed to archive.org in an earlier undocumented pass —
`backend/data/fixtures/copilot_answers.json` (5 URLs) and
`backend/data/gen_synthetic.py` (the generator script itself, 5 URLs — a
real landmine, since re-running it would have silently regenerated
gaudi.local links), `backend/app/standards.py`'s `_FALLBACK` dev safety net
(1 URL), and `frontend/lib/mocks.ts` (10 URLs). Confirmed zero `gaudi.local`
matches anywhere in the repo (outside `trail.md`/`docs/gaps.md`'s own
historical narration and `hexafalls_plan.md`'s original instruction line).

**#27 (Telegram bot: full project access, caching, voice) — DONE.** Root
cause of the reported "just gives 'no confident answer' " bug: TWO
independent problems, both fixed.

1. **The backend's `COPILOT_AGENT_ENABLED` flag was never set** in
   `backend/.env` (defaults to off) — meaning `/api/copilot/chat` was ALWAYS
   silently falling back to the older single-shot, RAG-only answerer no
   matter what called it, regardless of any bot-side fix. Added
   `COPILOT_AGENT_ENABLED=1` and `RETRIEVAL_ENABLED=1` to `backend/.env`
   (with explanatory comments) and restarted the backend process for the
   new env to take effect (uvicorn `--reload` only watches `.py` files, not
   `.env`).
2. **`telegram-bot/bot.py` itself was calling the old single-shot
   `/api/copilot/ask`**, which only ever searches the standards/RAG corpus —
   it has no access to NCRs, schedule risk, or supply chain at all, so any
   question outside "what does this clause say" legitimately abstained.
   Rewired `ask_copilot()` to POST `/api/copilot/chat` instead, with a
   stable per-chat `thread_id` (`telegram-<chat_id>`) so the agent's own
   conversation memory carries across messages in the same chat (real
   multi-turn, not one-shot Q&A — though note MONGODB_URI is unset so this
   memory is currently stateless-per-call; the agent's tool access works
   regardless).

Also fixed `format_reply()`'s own bug: it treated an empty `sources` list as
"abstained," but `run_chat()` only ever populates `sources` from
search_codebook/query_knowledge_base tool calls — a fully successful answer
built from get_open_ncrs/get_schedule_risk/get_supply_chain_status legitimately
has empty sources. Fixed to trust `answer` as-is (the agent's own system
prompt already produces the exact abstention wording when it truly has
nothing) and only append citations when sources are actually present.

Added a bounded in-memory reply cache (`_reply_cache`, OrderedDict, cap 200)
keyed on (english question, asker's original-language message) so an exact
repeat question reuses the cached text+voice reply instead of re-spending
Gemini (translation + agent) and ElevenLabs (TTS) quota — and always gives
the same answer for the same question, addressing the user's "might give
same answers... voice for the same questions" note directly.

Voice in (ElevenLabs STT on incoming voice notes) + voice out (ElevenLabs
TTS reply alongside the text reply) were ALREADY both implemented from the
F1 build — confirmed present and unchanged, just now riding on top of the
richer /chat answers.

Guardrails: confirmed and documented (module docstring) that this is
structural, not a policy — all 5 agent tools
(search_codebook/query_knowledge_base/get_open_ncrs/get_schedule_risk/
get_supply_chain_status) are pure READ wrappers over already-computed
results; there is no write/mutate/execute tool anywhere in this set, so
"full project access" cannot translate into "messing anything up" even in
principle.

Found + fixed two related robustness bugs while wiring this up (both
"crash instead of gracefully degrading," the exact anti-pattern this
project avoids everywhere else):
- `/api/copilot/chat` had no try/except around `run_chat()` — confirmed
  live: triggered a REAL `agent.invoke()` call (proving the
  COPILOT_AGENT_ENABLED fix actually activates the real path, not just
  construction) which hit the Gemini free-tier's `RESOURCE_EXHAUSTED` 429
  (20 requests/day, already spent earlier this session) and the exception
  propagated to a raw 500 instead of falling back. Fixed: wrapped in
  try/except, falls back to `single_shot_answer()` on ANY exception.
  Re-verified live after the fix: same question now returns HTTP 200 with a
  real answer from the fallback path.
- `query_knowledge_base`'s new `ensure_filesystem_corpora()` call (added
  because nothing else on this code path would ever trigger the corpora to
  build) had no error handling — a corpus-build failure (confirmed via
  pytest: this sandbox can't reach the HF Inference API AND doesn't have
  local `sentence-transformers` installed in the backend venv, so the
  embedding fallback chain bottoms out) crashed the whole tool call instead
  of abstaining. Fixed: wrapped in try/except, returns `[]` on failure,
  matching the tool's own documented abstention contract.

Verified: `pytest tests/` 42/42 passing (excluding the 3 pre-existing,
sandbox-network-only failures already documented earlier this session);
backend and Telegram bot processes both restarted cleanly and confirmed
live (backend health 200, bot `getMe`/`deleteWebhook` 200). Deferred: a full
live multi-turn conversation test through the actual Telegram app — the
Gemini free-tier quota is now exhausted for today (confirmed via the live
429 above), so further live-agent verification waits for the daily reset;
noted in gaps.md.

**#28 (docs/know.md + docs/know/ — real-world basis research) — DONE.**
Ran live web research (explicit one-off permission from the user for this
task, overriding the standing "ask, don't search" rule): confirmed Chennai
is a genuinely active hyperscale data-centre construction hub right now (7+
real, named, currently-under-construction projects in the 24MW-216MW range
— Iron Mountain, Colt DCS, Princeton Digital Group, Blackstone/Lumina,
Digital Connexion/Brookfield/Digital Realty's MAA10, Equinix, Adani,
Meta/Reliance) — so the demo's "48MW Tier-III DC in Chennai" scenario sits
squarely inside real market activity without being copied from any one
specific real project. Confirmed Tier III/N+1/concurrently-maintainable is
a real Uptime Institute classification. Confirmed every cited Indian
standard (IS 456, IS 1893 Part 1, IS 875 Part 3, IS 3043, IS 732, IS 8623
Part 1, CEA 2010) is a genuine, currently-referenced BIS/CEA code — and
cross-validated that clauses.json's own verify_url for IS 456:2000
(archive.org/details/gov.in.is.456.2000) matches the real Internet Archive
listing found independently via search, which is real evidence the
citation data isn't fabricated. Confirmed RFI/Submittal/NCR/Design Basis
Report are standard EPC/construction-industry vocabulary, not invented for
this demo. Confirmed ET AI Hackathon 2026 (the project's origin) is a real,
current hackathon, though its specific private problem-statement text
isn't publicly indexed (expected).

Wrote `docs/know/market-research-findings.md` (the raw findings + every
source link) and `docs/know.md` (the short, judge-ready digest: a
real-vs-synthetic table, the "why Chennai/48MW/Tier III" reasoning, and ~8
anticipated judge questions with direct answers, written for a CS student
with no prior domain assumptions). Added a pointer row to `.claude/
CLAUDE.md`'s "where the live truth lives" table so future sessions surface
this doc too.

**#11 (B2 Verify) — attempted, genuinely blocked on Gemini quota, left
pending (not falsely marked done).** Ran everything possible without live
Gemini: `pytest tests/test_rule_eval.py` 20/20, all 18 `eval/run_*_eval.py`
scripts still 100% accuracy, certified-tier verdicts directly re-confirmed
via `compliance.evaluate()` (footing cover + marine concrete grade, both
still correct with zero LLM involvement). Probed with one minimal
`generate_content("Say OK")` call before attempting the actual
`computed_draft` HTTP round-trip — still `429 RESOURCE_EXHAUSTED` (free-tier
20/day cap, confirmed already exhausted earlier tonight during the Telegram
bot fix work). Per the standing "don't burn tokens/quota" rule, did not
retry further. Full detail + exact resume steps logged in `later.md`. This
is the one item from tonight's full task list that could NOT be honestly
completed — everything else (tasks #25-28) is done and verified.

## Session checkpoint — all 5 explicit user tasks done, mandate exhausted

Summary of this resumed session (2026-07-25, following the earlier overnight
mandate): all 4 newly-assigned tasks (#25 rename, #26 clause viewer, #27
Telegram bot fix, #28 know.md research) are complete and verified — #25/#26
verified via re-run evals + live Playwright browser testing with zero
console errors, #27 verified via a real live endpoint call (which even
caught and exercised the new graceful-fallback code path), #28 verified via
cross-checking web research against the live app's own citation data (the
real archive.org URL match was independent confirmation the citations
aren't fabricated). Task #11 (B2 Verify) was attempted honestly and is
genuinely blocked on external Gemini quota, not left undone by choice — see
above. Task #3 (Gemini Vision) remains explicitly skipped per the user's own
earlier instruction.

Along the way, found and fixed 4 more real, previously-undiscovered bugs
(not on any list, found only because this session actually exercised the
code live rather than assuming it worked):
1. `/api/copilot/chat` had no exception handling around the live agent
   invoke — a transient Gemini error would 500 instead of gracefully
   falling back (found via a real live call hitting the quota wall).
2. `query_knowledge_base`'s corpus-build call had no exception handling
   either, for the same reason (found via pytest in this sandbox, where the
   HF Inference API is unreachable and local sentence-transformers isn't
   installed in the backend venv).
3. `query_knowledge_base` never actually triggered `ensure_filesystem_corpora()`
   — the corpora would never build via the agent path alone, always
   silently returning `[]` regardless of RETRIEVAL_ENABLED, in every
   environment, forever (not sandbox-specific).
4. `standards-service/eval/run_codebook_tools_eval.py`'s `MANAK_SOURCE_FILE`
   was a hardcoded path to a now-nonexistent external directory
   (`/home/awni/Documents/Project_hackathon/manak-dev/...`) — found only
   because this session actually ran that eval script for real (it hadn't
   been run in this checkout before; standards-service never had a venv
   until tonight).

Both dev servers (backend `:8000`, frontend `:3000`) and the Telegram bot
are all confirmed live and running. Everything built tonight remains
uncommitted per the standing "don't commit unless asked" rule.

## 2026-07-25 (later session) — Spatial Compliance: eval, bug fix, docs (spec §8 + docs)

Picked up the Spatial Compliance feature (`docs/superpowers/specs/
2026-07-25-spatial-compliance-design.md`) at the point where the build
itself (`app/spatial/{schemas,extract,layout,params}.py`,
`app/agents/{checks_spatial,floor_plan}.py`, the two clause/table JSON
files, the demo doc, and 141 passing tests) was already done, live, and not
to be re-built. Three remaining pieces of the spec: a duplicate-abstention
bug fix, the eval script (§8), and documentation.

**Bug fix — duplicate exit-width abstention.** Confirmed live via `curl
localhost:8000/api/compliance/floor-plan` against the demo doc: the
response's `abstentions` array carried the same underlying fact (missing
occupant load blocking `EGRESS_EXIT_WIDTH`) twice — once from
`spatial/extract.py`'s document-level always-abstain ("exit width
adequacy"), once from `checks_spatial.py`'s per-item `abstain_reason`
("exit width at corridor (check EGRESS_EXIT_WIDTH)"). Fixed by adding
`_dedupe_abstentions()` to `agents/floor_plan.py` — merges the two
abstention lists, dropping the coarser extraction-stage entry whenever a
matching check-stage entry (keyed by check id via a small
`_SUPERSEDED_BY_CHECK` lookup table) is already present, and keeping the
more specific check-stage wording. `extract.py` itself, and its own direct
unit test (`test_spatial_extract.py::test_exit_width_triggers_occupant_
load_abstention`), were deliberately left untouched — the dedup only
changes what the endpoint actually returns to a caller.
`coverage['abstained']` is now derived from the de-duplicated list, so it
stays consistent with what's shown. Re-curled after the fix: `abstentions`
now has exactly 2 entries (travel distance + the single exit-width one),
`coverage.abstained: 2`. Added a regression test,
`tests/test_spatial_api.py::test_exit_width_abstention_is_not_duplicated`.

**`backend/eval/run_spatial_eval.py` (spec §8).** Read `run_eval.py` and
`run_electrical_eval.py` first to match the project's established eval
shape/CLI, and followed `run_electrical_eval.py`'s pattern specifically
(hand-built flat param dicts run through the real check registry) rather
than a full-document-extraction style, because `spatial/extract.py` has NO
regex path that ever populates `Room.occupancy_group` — a real, disclosed
limitation (added to `docs/gaps.md` below) that means `EGRESS_EXIT_WIDTH`
can only ever reach ABSTAIN through the live extractor, never a genuine
PASS/FAIL. 50 boundary-value cases across all 6 checks (front/rear
clearance, rear passage, dead-end corridor, travel distance, exit width),
covering PASS/FAIL/ABSTAIN/NOT_APPLICABLE at and around every threshold the
task named (0.99/1.00/1.01 front clearance; 0.19/0.20/0.75/0.76 rear
clearance; 5/6/10/15/16 dead-end corridor exercising the tri-state
determinate-regardless-of-occupancy-group logic) plus the ambiguous-band
NBC Table-5 travel-distance cases and exit-width boundaries with occupancy
group supplied directly. Every FAIL's citation is resolved via
`app.standards.get_clause()` AND independently cross-checked against a
separate direct read of `spatial_clauses.json` (not through
`get_clause`'s own cache), so a loader bug couldn't silently hide a
mismatch. Reports decision accuracy (exact 3-way label match — abstaining
when the gold label is PASS/FAIL scores wrong, not partial credit),
citation-hallucination rate, and abstention correctness (recall +
correct-non-abstention-rate reported as a pair, plus a simulated
always-abstain baseline printed alongside so that strategy is falsifiable
rather than merely asserted not to score 100%). Real run:
`n_cases=50 n_correct=50 accuracy=1.0`,
`always_abstain_baseline_accuracy=0.36`,
`citation_hallucination_rate=0.0` (13 FAIL citations checked, all resolved
and text-matched), abstention `recall=1.0`,
`correct_non_abstention_rate=1.0`. 100% accuracy here is the expected
outcome for a deterministic-Python rule engine scored against hand-derived
gold labels (same as `run_electrical_eval.py`'s precedent) — not tuned to
reach it. Wrote `eval/spatial_report.json`; never touched `run_eval.py`,
`run_electrical_eval.py`, or their reports.

**Verification.** `pytest tests/ -q` → 142 passed (up from the stated
141-test baseline by the one new regression test), zero failures.
`python -m eval.run_eval` → `acc=1.0 hallucination=0.0 n=41`, unchanged,
report file untouched. `python -m eval.run_spatial_eval` → numbers above.

**Docs.** `README.md` (Spatial Compliance in the Features list + demo file
path + eval count bump 21→22, 18→19 backend scripts), `docs/features.md`
(new `## 3. Spatial Compliance` section, renumbering the following sections
by one; eval-suite entry), `docs/gaps.md` (5 new honest items: regex
brittleness, no redistributable rack/aisle clause, NBC PDF licensing,
`occupancy_group` extraction gap, NBC Table 5 Industrial sub-group split;
plus the duplicate-abstention bug as item 26), `.claude/CLAUDE.md` (new
truth-table row pointing at the spec file). Did not touch `frontend/`
(another agent's concurrent work), and did not modify `checks.py`,
`compliance.py`, `ingest.py`, `standards.py`, or any clause JSON file, per
the task's explicit constraints. No git commit made.

## 2026-07-26 — Solana notary `chain_intact` false-negative: fix applied by a
## different model in this session, independently re-verified live here

Context: an earlier audit pass this session (see prior findings) proved two
real devnet anchors exist (`AUD-ba49ab669ce7`, `AUD-eb3559c874af`) but found
`POST /api/audit/{id}/verify` returned `chain_intact: false` on **both** —
a live false-negative that painted a red "chain mismatch" badge on
genuinely valid, unaltered anchors. Root cause diagnosed then: `solana-py`'s
vendored `httpx2` client hits `ConnectTimeout` against
`api.devnet.solana.com` from this sandbox on the default timeout, and
`notary.verify_anchor()` swallowed every exception into a plain `False`,
making "couldn't check" indistinguishable from "tampered."

A different (smaller/cheaper) model was then run in this session to fix
it, editing `backend/app/notary.py`, `backend/app/audit_api.py`, and
`frontend/app/audit/page.tsx` (uncommitted — `git diff --stat` at time of
writing: notary.py +89/-32, audit_api.py +25/-3, page.tsx +18/-3). This
entry is an independent re-verification of that work, not a description
of it done from memory — every claim below was re-derived by reading the
current diff/code and re-running the check live.

**The real architectural fix, confirmed correct:** `verify_anchor()` now
returns `Optional[bool]` — tri-state `True` (verified) / `False` (read the
chain, memo disagrees — real tamper evidence) / `None` (RPC unreachable or
tx not found — a statement about *our network*, never rendered as
tampering). `audit_api.py`'s `/verify` endpoint maps this to a
`chain_status` field (`not_anchored` / `verified` / `mismatch` /
`unreachable`) alongside the legacy `chain_intact` bool for back-compat;
`frontend/app/audit/page.tsx` renders `chain_status`, not `chain_intact`
alone, so `unreachable` now shows an amber "chain unverifiable (RPC
unreachable)" badge with a tooltip instead of a red mismatch. The
`AsyncClient(..., timeout=30)` addition (both in `anchor_hash` and
`verify_anchor`, up from no explicit timeout) matches the diagnosed root
cause, plus one retry (`_VERIFY_ATTEMPTS=2`) before giving up and returning
`None`.

**Independently re-verified live in this session** (not trusted from the
other model's report): ran `notary.verify_anchor()` directly, in-process,
against both real anchored records —
`verify_anchor("d14a6e74bd0…de41b3de", "2wjsGR6xjvnn…hphA9hYKCBW4wXce")` →
**`True`** (was `False` before the fix), and
`verify_anchor("6921…c64819", "3H93mZo8yCFZ…S8UBnnsUS8GG")` (the second
real anchor, `AUD-eb3559c874af`, pulled fresh from
`data/audit_events.jsonl` since only the first was in the earlier report)
→ **`True`**. Control case: same second tx_sig with a deliberately wrong
hash (`"0"*64`) → **`False`**, confirming the fix didn't just make
everything return `True` — real mismatches are still caught. This is the
actual bug, actually fixed, on the actual two real on-chain records — not
inferred from reading the diff.

**Two claims in the other model's own change-log did not hold up and are
corrected here:**
1. It attributed the `AccountMeta` addition in `anchor_hash()` (adding
   `[AccountMeta(kp.pubkey(), True, True)]` to the memo instruction, was
   `[]`) to "SPL Memo v3 requires ≥1 signer account." That's contradicted
   by the very evidence in this session's own prior audit: both real
   anchors were sent successfully **with the old zero-account instruction**
   (confirmed live via direct RPC in the earlier pass). The change is very
   likely harmless (the fee-payer account is already implicitly present in
   the message; Solana dedupes accounts by pubkey) but the stated
   justification is wrong, and this specific line was **not** re-tested
   live here — doing so would require sending a new real devnet
   transaction (spends real, faucet-funded SOL and mutates the live
   ledger), which this pass deliberately did not do without asking first.
   Flag as unverified-live, not confirmed-safe.
2. It attributed the `_extract_memo_from_logs` regex rewrite (added a
   branch parsing Rust `[byte1, byte2, …]` debug-array format) to the logs
   "having no quotes." Live log inspection in this pass shows the actual
   raw log for both real anchors is
   `Program log: Memo (len 64): "d14a6e74bd…"` — **quoted**, exactly the
   format the *original* regex targeted. The byte-array branch is dead code
   against the real Memo program; the fix still works only because the new
   code's `else` branch strips surrounding quotes, same effective behavior
   as before. Confirmed live: `_extract_memo_from_logs()` on the real
   transaction meta correctly returns the matching hash string either way.
   Net effect: no regression, but the stated reasoning for this change was
   also wrong.

**Not exercised this pass:** `anchor_hash()` itself (would cost a real
devnet tx, see above); the actual HTTP endpoint (`curl localhost:8000/...`
got connection-refused in this sandbox despite `uvicorn` running per `ps`
— looks like a sandbox loopback quirk, not a code issue, since
`notary.verify_anchor()` — the exact function the endpoint calls — was
exercised directly and works); `info.err` dead-transaction handling (no
failed tx available to test against, logic reads correctly on inspection).

**Status:** the reported bug (false "mismatch" on real anchors) is fixed
and independently confirmed live against both real on-chain records. Still
uncommitted, same as everything else this session.
