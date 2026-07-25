# Gaps — an honest audit, for feedback and improvement

Compiled 2026-07-25 during an autonomous overnight build/audit session (see `../trail.md` for the
full chronological log this is distilled from). Updated later the same day after a second work
session (5 more explicit tasks — rename, clause viewer, Telegram bot fix, `docs/know.md`, plus
finishing the backlog). This is not a bug tracker — it's a "here's everything imperfect, in order
of what actually matters" list, so nothing surprises you or a judge later. Nothing here is a
reason not to demo; every item below has a known, disclosed workaround.

---

## Things worth fixing before a demo/submission, if time allows

1. **Zero git commits exist right now.** `git log`/`git status` show every file in the repo as
   untracked — `.git` was freshly initialized earlier this session (an intentional fresh-history
   pivot for the HexaFalls rename, not an accident) but never followed by an actual first commit.
   Everything built across both sessions is sitting uncommitted on disk. **Not committed
   automatically** — per the standing rule, only commit when explicitly asked.
2. ~~**~13 of 24 clause `verify_url`s point at `gaudi.local`**~~ **FIXED (later session,
   2026-07-25).** Investigation found the LIVE `clauses.json`/`commissioning_clauses.json` had
   actually already been fixed to real `archive.org` links in an earlier, undocumented pass — this
   item was stale. What genuinely still had `gaudi.local` (and is now fixed): `standards.py`'s dev
   fallback, `data/fixtures/copilot_answers.json`, `data/gen_synthetic.py` (the generator script
   itself — was a landmine, since re-running it would have regenerated dead links), and
   `frontend/lib/mocks.ts`. **Also built the actual feature this was standing in for**: citations
   now open a proper in-app clause-viewer popup (`ClauseViewerModal.tsx` + `GET
   /api/clause-context`) showing the real digitised source document's own text read off disk,
   instead of sending the user to an external link at all — verified live in a real browser via
   Playwright, both the exact-heading-match and parent-heading-fallback cases.
3. **The F2 LangGraph agent's actual `agent.invoke()` round trip was confirmed live for the first
   time (later session, 2026-07-25)** — and immediately surfaced two real bugs, both fixed: (a)
   `COPILOT_AGENT_ENABLED` had never actually been set in `backend/.env`, so `/api/copilot/chat`
   was ALWAYS silently falling back to the older single-shot answerer no matter what called it —
   this was the root cause of a separate reported bug (see item 4). (b) once enabled, a real
   `agent.invoke()` call correctly reached Gemini and hit the free-tier's `RESOURCE_EXHAUSTED` 429
   — but `/chat` had no exception handling around that call, so it 500'd instead of gracefully
   falling back. Fixed (try/except -> `single_shot_answer()`); re-verified live, now returns a
   normal 200. Gemini's daily quota is exhausted for now, so the actual multi-tool NCR/schedule
   answer content is still not live-re-verified past construction — see `later.md`.
4. ~~**The Telegram bot has never received a real message... just gives a generic abstain.**~~
   **Root-caused and fixed (later session, 2026-07-25).** Two bugs, not one: the
   `COPILOT_AGENT_ENABLED` flag issue above (so even wiring the bot to the right endpoint wouldn't
   have mattered), PLUS the bot itself was calling the old single-shot, RAG-only
   `/api/copilot/ask` (no access to NCRs/schedule/supply chain at all). Rewired to
   `/api/copilot/chat` with a per-chat `thread_id` for conversation continuity, fixed a related
   `format_reply()` bug that incorrectly treated "no sources" as "abstained" (most successful
   agent answers legitimately have no sources), and added a bounded reply cache so repeat questions
   reuse the same answer+voice instead of re-spending quota. Voice in/out were already both
   implemented from the original build. **Still not tested from an actual phone** — that's the
   one honest gap left here; everything else (endpoint, flags, caching, graceful fallback) is
   verified.
5. **Workstream B (Gemini Vision — reading scanned drawings/photos) was never started.** Explicitly
   skipped per direct instruction ("also leave the gemini vision for now, skip this"). Not a bug,
   just genuinely not built — don't claim it works.
6. **B2's full tiered-verdict live re-verification (task #11) is still pending — genuinely
   blocked, not skipped.** Re-attempted in the later session: probed Gemini with a minimal call
   before trying, still `429 RESOURCE_EXHAUSTED` (free-tier 20/day cap, already exhausted).
   Everything possible without a live LLM call WAS re-confirmed (rule_eval unit tests 20/20, all
   18 deterministic evals still 100%, certified-tier verdicts directly re-confirmed in Python). The
   mechanism itself was proven live in the earlier session (real Gemini calls producing correct
   FAIL/PASS/none computed-draft results) — a fresh end-to-end HTTP re-run just needs the daily
   quota to reset. See `later.md` for the exact resume steps.

## Smaller things, already handled but worth knowing about

7. **`backend/.env.local` contains stray InsForge keys** (`NEXT_PUBLIC_INSFORGE_URL`/
   `NEXT_PUBLIC_INSFORGE_ANON_KEY`) that don't belong to this project's actual stack — InsForge is
   never referenced anywhere else in the codebase or the HexaFalls plan. Harmless: the backend's
   `load_dotenv()` only ever reads the exact filename `.env`, never `.env.local`, so this file is
   completely inert. Already covered by `.gitignore` (both a blanket `.env.local` pattern and an
   explicit `.insforge` directory-name entry). Worth deleting during a cleanup pass; not touched
   tonight since it poses no actual risk.
8. **Two real `.gitignore` gaps were found and fixed tonight**: `actian_data/` (the Actian Docker
   volume — real DB files) and `backend/data/audit_events.jsonl` (the regenerated local audit
   ledger) were NOT excluded before. Both fixed and confirmed via `git check-ignore`. Would have
   been a real problem on the first commit if not caught.
9. **A stale test-file path bug was found and fixed**: `tests/test_llm_extract.py` referenced
   `docs/demo_files/Structural-Design-Basis-Report_DEMO.txt`, but no `demo_files/` subdirectory
   exists — the real file lives directly at `docs/Structural-Design-Basis-Report_DEMO.txt`. Fixed;
   full suite is 40/40 passing now (was 27 passing / 2 failing before the fix).
10. **A real fresh-install bug was found and fixed**: `backend/requirements.txt` pinned
    `pydantic==2.9.2`, but `solana==0.40.1` (added earlier this session) actually needs
    `pydantic>=2.13.4` — a true `ResolutionImpossible` on a genuinely fresh `pip install -r
    requirements.txt`, even though the incrementally-built local dev venv had already drifted past
    the stale pin and was running fine. Fixed by bumping the pin to match what was actually already
    running (2.13.4); confirmed a full fresh install now succeeds with zero conflicts, and that all
    ~20 eval scripts + `pytest` still produce byte-identical results after the bump.
11. **The Actian VectorAI DB container is running Community Edition** (5000-vector cap) — a real
    30-day trial license key was provided but never pasted into its LocalUI
    (`http://localhost:6575`), a browser-only step. Fine for everything tested so far (well under
    5000 vectors); would need doing before scaling the corpus meaningfully past that.
12. **`digitalocean.md` is a deploy GUIDE, not a deployment** — explicitly caveated inside the
    document itself. Every YAML spec in it is illustrative, adapted from the real, live
    `render.yaml`, but never validated against an actual `doctl` deploy (DigitalOcean credits
    weren't confirmed at build time). Several specific mechanisms (cross-service URL
    interpolation syntax, the exact `workers:` key, Python version pinning) are flagged inline as
    unconfirmed.
13. **The Copilot frontend page still uses the original single-shot `/api/copilot/ask`**, not the
    new multi-turn `/api/copilot/chat` — this was explicitly optional in the plan ("optionally
    switch to `/api/copilot/chat` with a persisted thread_id") and wasn't done, to prioritize
    getting the backend + tests solid first. (The Telegram bot DOES now use `/chat` — see item 4.)
    The new endpoint is fully live-testable via curl/Postman today; it's just not wired into the
    main web UI yet.
14. **The `manak_structural` corpus identifier was renamed to `structural_standard_codes`**
    (later session, 2026-07-25) across both `filesystem_corpora.py` copies (backend/ and
    standards-service/ — these had already partially diverged, one using `manak_structural`, the
    other `codebook_structural`), `compliance.py`, `mcp_server.py`, the frontend Codebook page, and
    all 4 related eval scripts. Re-verified byte-identical eval behavior after the rename (26/26,
    5/5, 30/30 across the 3 corpus-related eval suites). Internal prose/comments describing the
    rename's own history (e.g. "renamed from manak_structural") were deliberately left as accurate
    historical narration, not scrubbed.
15. **`standards-service/eval/run_codebook_tools_eval.py` had a hardcoded, now-broken absolute
    path** (`MANAK_SOURCE_FILE` pointed at `/home/awni/Documents/Project_hackathon/manak-dev/...`,
    a directory that no longer exists since those files were copied in-repo a while back) — found
    only because this session actually ran that eval for real (standards-service never had a venv
    in this checkout before tonight). Fixed to a repo-relative path; eval now 30/30 passing.
16. **`copilot_agent.py`'s `query_knowledge_base` tool never actually built its corpora** — it
    called `get_corpus()` directly without ever calling `ensure_filesystem_corpora()` first (the
    one thing that actually populates the registry), so it silently returned `[]` forever
    regardless of `RETRIEVAL_ENABLED`, in every environment, not just this sandbox. Fixed to call
    `ensure_filesystem_corpora()` first, wrapped in a try/except so a corpus-build failure (e.g. an
    unreachable embeddings provider) still abstains gracefully instead of crashing the tool call.

## Things that were always known/disclosed (not new findings, just repeated here for completeness)

17. **All project data is synthetic/representative** — a 48MW Chennai data-centre modelled on
    real market conditions (see `docs/know.md` for the research backing that), not a real client's
    project. The standards, the checking logic, and the crypto/audit mechanisms are real; the demo
    project itself is not.
18. **ROI figures (~20 engineer-hours, ~₹15L per issue) are labelled assumptions**, not measured
    outcomes — always disclosed as such, never presented as a forecast.
19. **Commissioning QA covers only the cooling/HVAC slice.** Electrical and fire commissioning are
    deferred — the project's own instructions note a real corpus gap (no good enough real
    test-log data existed to build them credibly), not a shortcut.

## A process note, not a product gap

20. During the keyless-boot verification test tonight, a combined shell command
    (`mv ... && pkill ... && diff ...`) silently failed partway through and left `backend/.env`
    genuinely missing from disk for a few tool calls before it was caught (via a follow-up `ls`
    check) and restored from a backup copy taken before the test started. No actual data was lost —
    the fix worked because a backup had been made proactively — but this surfaced a real fragility:
    multi-step, chained shell commands touching real files in this environment occasionally
    returned misleading exit codes and should be split into separate, individually-verified steps
    rather than trusted as one atomic block, especially for anything destructive-ish. Applied for
    the rest of this session; worth keeping in mind for future sessions too.
