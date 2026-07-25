# SiteMind — Deployment: full state, decisions, and operational history

> **Purpose of this file:** a complete, non-summarized dump of everything known about how SiteMind
> is deployed — so a new chat session (possibly on a new machine) has full context without having
> to re-derive it. This file lives at `docs/deploy.md`. **`docs/` is gitignored (see §11) — this
> file will NOT transfer via `git clone` on a new PC.** Copy it (and the rest of `docs/`) over by
> hand (zip, USB, cloud sync, `rsync`) if you need it on another machine.
>
> Written 2026-07-23 by Claude Code, compiled from: `docs/CHECKPOINT.md`, `docs/PROGRESS.md`,
> `docs/archive/DEPLOY.md` (the original, never-executed deploy guide), `docs/render.yaml`,
> `.github/workflows/keepalive.yml`, `backend/app/config.py`, `backend/app/main.py`,
> `backend/app/codebook_client.py`, `frontend/lib/api.ts`, git log/show output, and this session's
> own live investigation (Render/Vercel CLI calls, log inspection, curl timing tests) carried over
> from the previous chat via its compaction summary. Anything sourced only from that carried-over
> summary (not independently re-verified in this session) is marked **[from prior session, not
> re-verified today]**.

---

## 1. TL;DR — what's live right now

- **Live app (frontend):** https://sitemind.awni.in (custom domain, Vercel)
- **Backend API:** https://sitemind-backend.onrender.com (Render, free tier)
- **Codebook (standards-service) API:** https://sitemind-codebook.onrender.com (Render, free tier)
- **Also reachable (raw Vercel URL, pre-custom-domain):** `https://frontend-tau-indol-ucguhuklc7.vercel.app`
- **GitHub repo that actually deploys:** `git@github.com:AwkJay/sitemind-openai-hackathon.git`
  (mirrored to from `hackathon/sitemind2/`). Development happens in `hackathon/sitemind/` →
  `git@github.com:AwkJay/sitemind.git`, which deploys nothing. **See §3 — this trips people up.**
- **(superseded, kept for the record)** `git@github.com:AwkJay/sitemind.git`,
  branch `main`, tracking `origin/main`, clean working tree as of 2026-07-23.
- **Cost:** $0 — Vercel Hobby (free) + two Render free-tier web services. No database, no paid addons.
- **Both optional feature flags are ON in production**: `RETRIEVAL_ENABLED=1` and `CODEBOOK_ENABLED=1`
  on the Render backend (see §6). `LLM_PROVIDER=offline` in production — the deployed app runs
  fully deterministic/offline, same integrity guarantee as local dev.
- **The single biggest live-ops problem, actively being fought:** Render free-tier cold starts /
  instance recycling causing intermittent "Codebook can't be reached" errors in the UI. Two rounds
  of fixes shipped so far (§8); a further, only-partially-understood phenomenon (short restart
  cycles, not just idle cold starts) was found in Render's logs and is **not yet fully mitigated**
  (§9). This is the live open item.

---

## 2. Deployment topology (3 hosted pieces, 2 platforms)

```
Browser
  │  HTTPS
  ▼
Vercel: sitemind.awni.in  (Next.js 14 frontend, project root = frontend/)
  │  REST (fetch), NEXT_PUBLIC_API_URL
  ▼
Render: sitemind-backend.onrender.com  (FastAPI, rootDir = backend/, free web service)
  │  MCP client (streamable-http), CODEBOOK_MCP_URL
  ▼
Render: sitemind-codebook.onrender.com  (FastMCP, rootDir = standards-service/, free web service)
```

Three independently-hosted, independently-cold-starting processes. The frontend never talks to
Codebook directly — it only ever talks to the backend, which is Codebook's sole MCP client. This
means a browser request to any `/codebook` page can require **two sequential cold starts** (backend,
then backend→Codebook) in the worst case — this is the root of the whole cold-start saga in §8–9.

No database anywhere. No Redis/queue. No CDN beyond what Vercel provides by default. No secrets
manager — env vars are set directly in each platform's dashboard.

---

## 3. GitHub

> ⚠️ **CORRECTED 2026-07-23 (second pass).** An earlier version of this section claimed the
> deployed repo is `AwkJay/sitemind`. **That was wrong** — it was derived by running
> `git remote -v` inside `hackathon/sitemind/`, which is *not* the folder the hosted services
> build from. Read the two-repo explanation below before trusting anything about deploys.

### There are TWO repos. Only one of them deploys.

| Local folder | GitHub remote | Deploys? |
|---|---|---|
| `hackathon/sitemind/` | `git@github.com:AwkJay/sitemind.git` | **No.** Current ET AI Hackathon 2026 codebase; source of truth for all development. |
| `hackathon/sitemind2/` | `git@github.com:AwkJay/sitemind-openai-hackathon.git` | **Yes.** Vercel + both Render services build from this repo's `main`. |

**How this happened:** `sitemind/` *was* the OpenAI-hackathon folder, and Vercel/Render were wired
up from it — at which point its remote was `sitemind-openai-hackathon`. Its `.git` was then deleted
and the folder re-initialised as a fresh repo for the ET AI hackathon (`AwkJay/sitemind`, unrelated
history, no common ancestor). `sitemind2/` is a later re-clone of the original OpenAI repo, made
because that `.git` was gone. The hosting platforms never moved — they still watch the original.

**Two leftovers that mislead:**
- `sitemind/frontend/.vercel/project.json` still exists, from the original CLI link. It identifies
  the Vercel *project*; it says nothing about which Git repo Vercel is wired to. Ignore it.
- Both repos contain near-duplicate cold-start commits (§8) — the same fixes were made twice,
  because fixes pushed to `AwkJay/sitemind` never reached the live services. This is very likely
  the real cause of the "Render auto-deploy didn't fire" symptom recorded in §5: the pushes were
  landing on a repo nothing was watching.

**Workflow (as of 2026-07-23):** develop in `sitemind/` only, push to `AwkJay/sitemind`, then run
`sitemind/sync-to-deploy.sh` to mirror the tracked tree into `sitemind2/` and push, which is what
actually triggers a deploy. Never edit `sitemind2/` by hand. The OpenAI submission state is frozen
at tag `openai-hackathon-submission` (`a13ce5a`) on the deploy repo.

- Single branch workflow: everything lands on `main`; both Vercel and Render are wired to auto-deploy
  from `main` **of the deploy repo** (see §4 and §5 for each platform's auto-deploy behavior/caveats).
- `gh` CLI is **not installed** in this sandbox environment (`gh: command not found` when checked
  2026-07-23) — GitHub Actions run history for `keepalive.yml` could not be pulled this session via
  `gh run list`; use the GitHub web UI (Actions tab) or install `gh` if you need that.
- Historical note (**now known to be backwards**): an earlier pass of this file called
  `AwkJay/sitemind-openai-hackathon` "stale" and asserted `AwkJay/sitemind` was the live remote.
  The opposite is true — `sitemind-openai-hackathon` is the repo the hosted services build from.
  Lesson: `git remote -v` only tells you the remote of *the folder you happen to be standing in*.
  To learn what actually deploys, read the connected repository in the Vercel and Render dashboards.

---

## 4. Vercel — frontend

- **Project root directory:** `frontend/` (monorepo subdirectory deploy — Vercel is configured to
  build only that subfolder, framework auto-detected as Next.js).
- **Deployed URL pattern:** `https://frontend-tau-indol-ucguhuklc7.vercel.app` (the raw Vercel-assigned
  URL) with a **custom domain** `sitemind.awni.in` pointed at it (the user owns `awni.in`; exact
  DNS/registrar setup for the subdomain was not part of this session's investigation — check the
  Vercel dashboard's Domains tab on the frontend project if you need to reproduce/modify it).
- **Required env var:** `NEXT_PUBLIC_API_URL=https://sitemind-backend.onrender.com` (no trailing
  slash) — set in Vercel dashboard → Project → Settings → Environment Variables. This is the only
  env var the frontend needs; everything else (feature flags, offline mode) lives server-side on
  the backend and the frontend just reflects whatever the backend reports.
- **Auto-deploy:** confirmed working and fast — pushes to `main` trigger a Vercel deploy that goes
  `Ready` in roughly **~38 seconds** [from prior session, not re-verified today]. This is
  meaningfully faster and more reliable than Render's auto-deploy (see §5's caveat).
- **CLI auth state:** the Vercel CLI (`npx vercel ...`) was authenticated and working via its stored
  token at `~/.local/share/com.vercel.cli/auth.json` **as a CLI session**, but that same token had
  gone **stale for direct REST API calls** (`{"error":{"code":"forbidden","message":"Not
  authorized","invalidToken":true}}`) as of the prior session's check [from prior session, not
  re-verified today]. If you hit this again: fall back to `npx vercel ls` / `npx vercel inspect
  <url>` (interactive CLI, works) instead of hand-rolled `curl` calls against Vercel's API. A fresh
  `vercel login` would also fix it outright.
- **No `vercel.json` exists in the repo** (checked this session — `find` for it returns nothing).
  All Vercel config (root directory, env vars, domain) lives in the Vercel dashboard, not in-repo.

---

## 5. Render — backend (`sitemind-backend`)

- **Service type:** `web`, **runtime:** `python`, **region:** `oregon`, **plan:** `free`.
- **Root directory:** `backend/`
- **Build command:** `pip install -r requirements.txt`
- **Start command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Health check path:** `/api/health`
- **Env vars (from `docs/render.yaml` — see §7 for why this file is reference-only, not a live Blueprint):**
  | Key | Value | Notes |
  |---|---|---|
  | `PYTHON_VERSION` | `3.12.4` | pinned — numpy/pandas wheels don't build on 3.13+/3.14 |
  | `LLM_PROVIDER` | `offline` | production runs fully deterministic, no API key needed |
  | `RETRIEVAL_ENABLED` | `"1"` | Knowledge Base package is live in production |
  | `CODEBOOK_ENABLED` | `"1"` | backend acts as an MCP client of Codebook in production |
  | `CODEBOOK_MCP_URL` | `https://sitemind-codebook.onrender.com/mcp` | points at the *other* Render service, not localhost |
  | `ALLOWED_ORIGINS` | `https://frontend-tau-indol-ucguhuklc7.vercel.app,https://sitemind.awni.in,http://localhost:3000` | CORS allowlist — comma-separated, parsed in `backend/app/config.py:77-79` |
  | `HF_TOKEN` | *(set via Dashboard, `sync: false`)* | free Hugging Face Inference API token (read scope + "Make calls to Inference Providers"), powers MiniLM embeddings for Copilot/Knowledge Base retrieval |
- **CORS wiring:** `backend/app/main.py:27-28` — `CORSMiddleware(allow_origins=config.ALLOWED_ORIGINS)`.
  If you add a new frontend origin (e.g. a new Vercel preview URL you want to test against prod
  backend), it must be added to `ALLOWED_ORIGINS` on Render and the backend **manually redeployed**
  (see auto-deploy caveat below — env var changes don't reliably trigger a redeploy on their own).
- **Free-tier cold-start behavior — measured directly this session/prior session:**
  - Fully-idle → first response: **~51.5–57.4s** (backend alone, health check).
  - Render spins free web services down after **~15 minutes** of inactivity.
- **Auto-deploy caveat (important, cost real time this session):** Render's auto-deploy from a
  `main` push **did not fire reliably** — after pushing a fix commit, `render deploys list` still
  showed the old commit as the live deploy even ~50–80s later. Contrast with Vercel's ~38s.
  **Workaround used:** manually trigger a deploy via the Render CLI:
  ```bash
  render deploys create <service-id> --wait --confirm -o json
  ```
  **RESOLVED 2026-07-23 (second pass) — verified via `render services -o json`:**
  ```
  sitemind-backend   srv-d9eefh5aeets73b1gg1g  repo=AwkJay/sitemind-openai-hackathon
                     branch=main  autoDeploy=yes  autoDeployTrigger=commit  rootDir=backend
  sitemind-codebook  srv-d9egrb5aeets73b68u70  repo=AwkJay/sitemind-openai-hackathon
                     branch=main  autoDeploy=yes  autoDeployTrigger=commit  rootDir=standards-service
  ```
  So **auto-deploy is switched ON and correctly configured** — the setting was never the problem.
  Two separate things were being conflated:
  1. **Most of the "auto-deploy didn't fire" history was the wrong-repo problem (§3).** Pushes were
     going to `AwkJay/sitemind`, which no Render service watches. Nothing was ever going to fire.
  2. **Even a correct push to the deploy repo did not reliably trigger a build.** Observed directly
     today: commit `445ebcd` (touches `backend/`, i.e. inside `rootDir`) was pushed to
     `sitemind-openai-hackathon@main` and after ~80s of polling the live deploy was still the older
     `0df5209`. A manual `render deploys create` then built and went live in ~1m50s
     (`build_in_progress` → `update_in_progress` → `live`).
  Note that a *legitimate* skip also exists: Render ignores pushes that change nothing under
  `rootDir`. That is why `a13ce5a` (frontend-only) never produced a backend deploy — correct behaviour,
  not a fault. But `445ebcd` was not that case, so the flakiness is real and still unexplained
  (webhook delivery on that repo is the prime suspect — check GitHub → repo → Settings → Webhooks).
  **Operational rule: after `./sync-to-deploy.sh`, always trigger Render manually and confirm:**
  ```bash
  render deploys create srv-d9eefh5aeets73b1gg1g --confirm -o json   # backend
  render deploys list   srv-d9eefh5aeets73b1gg1g --confirm -o json   # poll until status=live
  ```
  Only redeploy `sitemind-codebook` when something under `standards-service/` actually changed.
- **Service ID captured this session (may rotate if the service is ever recreated — re-derive via
  `render services -o json` if a command using it fails):** `srv-d9eefh5aeets73b1gg1g`
  [from prior session, not re-verified today — treat as a starting point, confirm before relying on it].

---

## 6. Render — Codebook / standards-service (`sitemind-codebook`)

- **Service type:** `web`, **runtime:** `python`, **region:** `oregon`, **plan:** `free`.
- **Root directory:** `standards-service/`
- **Build command:** `pip install -r requirements.txt`
- **Start command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Health check path:** `/health` (note: different from the backend's `/api/health` — no `/api` prefix here)
- **Env vars:**
  | Key | Value |
  |---|---|
  | `PYTHON_VERSION` | `3.12.4` |
  | `HF_TOKEN` | same free HF token as the backend, reused for this service's own retrieval embeddings (`app/retrieval/embeddings_provider.py`) |
- **What it is:** a standalone MCP server (`app/mcp_server.py`, mounted at `/mcp`) exposing 4 tools:
  `list_corpora`, `search_standards`, `get_clause`, `check_document_against_corpus`. Locally it runs
  on port `8010` (`standards-service/run.sh`); in production Render assigns its own `$PORT`, and the
  backend reaches it over the **public internet** at `https://sitemind-codebook.onrender.com/mcp`
  (not a private/internal Render network link — both services are plain public `web` services).
- **MCP SDK pin:** `mcp==1.9.4` in both `backend/requirements.txt` and
  `standards-service/requirements.txt` — deliberately identical versions, and deliberately *not*
  the latest (1.28.1 at time of writing), because newer `mcp` forces `starlette>=1.0`, which breaks
  `fastapi==0.115.0`. Do not bump this without re-checking that constraint.
- **Free-tier cold-start behavior — measured directly:** fully-idle → first response ranged
  **~43.2s to ~72s** across different measurements this session and the prior one. This variability
  itself is one of the open mysteries (§9) — it's not a fixed number.

---

## 7. `docs/render.yaml` — what it actually is (and isn't)

- `docs/render.yaml` (read in full in §5/§6 above) is a **reference copy** of what was originally a
  root-level `render.yaml` Blueprint. Git history shows it was added at repo root in commit
  `7c36996` ("Add Render deploy config") and later **removed from repo root** in commit `111b0d2`
  ("Simplify copilot logic and clean up ignores", 45 lines deleted) — it now survives only as this
  documentation copy under `docs/`.
- **This means: the two live Render services were NOT (or are no longer) instantiated from this
  Blueprint file via Render's "New Blueprint" flow.** They exist as directly-created/dashboard-
  configured services. If you ever need to recreate them from scratch, this YAML is the source of
  truth for *what the settings should be*, but you'd apply it either by hand in the Dashboard or by
  re-adding a `render.yaml` at repo root and using Render's Blueprint deploy flow (New → Blueprint →
  connect repo → Apply) — see `docs/archive/DEPLOY.md` §1 for the original manual-Dashboard steps
  (written before Codebook existed as a second service, so it only covers the single-backend case;
  cross-reference with §5/§6 above for the second service and the env vars that were added since).
- Render CLI (`render blueprints validate`) was used earlier in this project's history to validate
  the Blueprint syntax before it existed as live services — that CLI subcommand only *validates*,
  it does not have a `create`/`launch` subcommand, which is part of why the actual services ended up
  dashboard-created rather than Blueprint-applied.

---

## 8. The cold-start "Codebook unreachable" saga — root causes found and fixed

This was the dominant deployment problem this project has fought, across multiple sessions. Full
blow-by-blow:

### 8.1 Symptom
Frontend `/codebook` page shows: *"Codebook can't be reached right now. Either the SiteMind backend
itself is unreachable, or the backend is up with `CODEBOOK_ENABLED=1` but Codebook's own process
(standards-service, port 8010) isn't running..."* — even though both services were in fact up, just
cold.

### 8.2 Root cause #1 — frontend timeout too short (fixed, commit `8b139eb`, 2026-07-21)
`frontend/lib/api.ts` had a single `TIMEOUT_MS = 20000` (20s) applied to every fetch, including the
7 Codebook-specific call sites. Measured real cold-start latency (52–72s) was **far longer** than
20s, so the frontend gave up and reported "unreachable" while the backend/Codebook were still
legitimately waking up.

**Fix (current, live code — `frontend/lib/api.ts`):**
```javascript
// Render's free tier spins services down after ~15 min idle. Measured cold
// starts directly: the backend itself took ~52s, Codebook (standards-service)
// took ~72s to answer a health check from fully asleep. 20s was still far too
// short (that's why "unreachable" kept recurring after the first bump) — 90s
// gives the backend-only path real margin above the observed worst case while
// still failing in reasonable time for a genuinely dead backend.
const TIMEOUT_MS = 90000;

// Codebook calls are a sequential double cold-start: the browser's request
// has to wait for SiteMind's backend to wake up, and only THEN does the
// backend make its own MCP call to Codebook — which may ALSO be cold. That
// stacks to well over 90s in the worst case (both services asleep at once),
// so Codebook-specific calls get a longer budget than plain backend calls.
// Matches the explicit timeout now set on the backend's MCP client itself
// (see codebook_client.py) so neither side gives up before the other.
const CODEBOOK_TIMEOUT_MS = 180000;
```
Applied to all 7 Codebook-specific fetch call sites: `getCodebookCorpora`, `searchCodebook`,
`getCodebookClause`, `checkDocumentAgainstCodebook`, `checkDocumentAgainstCodebookUpload`,
`getCodebookConsoleCorpora`, `getCodebookConsoleDocuments`. Two Knowledge-Base/retrieval fetch call
sites deliberately stayed on the plain `TIMEOUT_MS` (they don't hop through Codebook). Note:
`uploadToCodebookConsole` has **no** AbortController/timeout at all — this was left alone, not part
of this fix, and is a latent gap if it's ever hit during a cold start.

### 8.3 Root cause #2 — backend's own MCP client silently using the SDK's 30s default (fixed, same commit)
Independent of the frontend, `backend/app/codebook_client.py`'s call to
`streamablehttp_client(config.CODEBOOK_MCP_URL)` used the `mcp==1.9.4` SDK's **default timeout of
30 seconds** (confirmed by reading the pinned-version source directly on GitHub — the SDK's
`streamable_http.py` signature is `timeout: float | timedelta = 30`). Codebook's own cold start
(~60–90s) was longer than this, so **even a patient frontend** would get a `CodebookUnavailable`
error from the backend, because the backend's outbound call to Codebook timed out first.

**Fix (current, live code — `backend/app/codebook_client.py`):**
```python
# Explicit 100s timeout, not the SDK's 30s default: on Render's free
# tier Codebook (standards-service) can take 60-90s to answer from a
# cold start, and this backend only calls it on demand — the SDK
# default gave up on Codebook well before it finished waking.
async with streamablehttp_client(config.CODEBOOK_MCP_URL, timeout=100) as (
    read,
    write,
    _get_session_id,
):
```
No shorter timeout wrapper exists between `codebook_router.py` and `codebook_client.py` (checked by
grep this session) — this 100s MCP-transport timeout is the effective end-to-end bound on the
backend side.

### 8.4 Verification performed (both this session and carried over)
- Confirmed via live production JS bundle inspection (`https://sitemind.awni.in/_next/static/chunks/...`)
  that the new constants are genuinely deployed: Terser minifies large integers to scientific
  notation, so `90000` → `9e4` and `180000` → `18e4` — both literals were found live in
  `setTimeout(() => x.abort(), ...)` contexts in the shipped bundle, confirming this isn't just
  committed but actually serving. [from prior session, not re-verified today, but high confidence]
- `python3 -m py_compile backend/app/codebook_client.py` → syntax OK (no local `.venv`/`mcp` package
  available in this sandbox to do a real import check — see §12).
- Live curl this session: `https://sitemind-backend.onrender.com/api/codebook/corpora` →
  `HTTP 200`, `time=0.947573s` — fast and healthy at time of check (2026-07-21, ~17:48 UTC).

---

## 9. Open/unresolved — the Render "restart cycle" phenomenon

**This is the one thing that is NOT yet confirmed fixed. Read this before assuming the cold-start
fix in §8 is the end of the story.**

While investigating a user report that Codebook was *still* intermittently "unreachable" despite
the §8 fix being live, direct inspection of Codebook's Render logs turned up something new and
distinct from idle-cold-start:

- Codebook underwent a **clean shutdown-then-restart cycle** (`Shutting down` → `Application
  shutdown complete` → later `Uvicorn running on http://0.0.0.0:10000`) with only a **~2min10s gap**
  (17:43:15 → 17:45:25 UTC, 2026-07-21) — **despite continuous internal Render health-check traffic
  every 5 seconds throughout that window.** No crash/error/OOM signature in the logs around it.
- This does **not** match the "idle for 15 minutes" cold-start pattern the §8 fix targets — the
  service was clearly being actively health-checked the whole time, yet still cycled.
- **Working hypothesis (unconfirmed):** routine Render free-tier instance recycling — Render may
  periodically restart free-tier instances for platform-maintenance reasons independent of traffic/
  idleness. This is speculation, not confirmed via Render's own docs/support in this investigation.
- **Evidence it may be relatively benign:** a real external client (IP `223.181.52.68`, inferred to
  be the user's own browser from the request pattern — `GET /api/health` immediately followed by
  `GET /api/codebook/corpora`) completed both calls successfully (`200 OK`) at 17:44:48 and 17:45:32
  UTC respectively — i.e., right around/just after the restart completed. So the window where a
  request could actually fail outright (not just be slow) appears short — on the order of the
  ~2min10s restart gap itself, not the full cold-start duration.
- **Why this matters for the fix in §8:** the §8 timeout increases (90s/180s/100s) are sized for
  *slow-but-eventually-successful* responses (a cold start that takes 52–72s to answer). They do
  **nothing** for a window where the service is briefly **not accepting connections at all**
  (connection-refused, not slow) during an active restart — a longer client-side timeout can't fix
  a server that flatly isn't listening yet. If this restart-cycle theory is right, the residual
  "unreachable" reports the user sees are a **different failure mode** than the one §8 fixed, and
  would need a different mitigation (e.g., client-side retry-with-backoff instead of a single long
  timeout, or investigating with Render support/docs whether this recycling can be disabled/predicted
  on the free tier).

**Concrete next steps if this resurfaces (hand this to whoever picks it up next):**
1. Ask the user for the **exact time** (to the minute) they see the error, and cross-reference
   against Render's logs for both services at that timestamp (`render logs -r <service-id>` around
   that window) — confirm/deny whether it lines up with another restart-cycle gap.
2. Check whether this recycling is periodic (e.g., every N hours) by pulling a longer log window —
   not yet done as of this writing.
3. If confirmed to be Render-side recycling unrelated to idle time, consider a client-side
   retry-with-backoff (e.g., 2–3 retries with a few seconds between) on the Codebook fetch calls in
   `frontend/lib/api.ts`, rather than relying solely on a long single timeout — this is a real code
   change, not yet implemented, and would need the user's go-ahead per this project's "confirm before
   production-affecting changes" norm.
4. Consider whether upgrading either Render service off the free tier would eliminate this class of
   problem entirely — not evaluated/costed in this investigation; the project's cost constraint so
   far has been $0 (see §1), so this would be a deliberate tradeoff to raise with the user, not a
   silent default.

---

## 10. The "keep it warm" mitigation — `.github/workflows/keepalive.yml`

To reduce how often either Render service goes fully idle-cold (separate from the §9 restart-cycle
issue), a GitHub Actions workflow pings both health endpoints every 10 minutes:

```yaml
name: Keep Render backend warm

on:
  schedule:
    - cron: "*/10 * * * *"
  workflow_dispatch:

jobs:
  ping:
    runs-on: ubuntu-latest
    steps:
      - name: Ping backend health endpoint
        run: curl -sf --max-time 90 --retry 3 --retry-delay 10 --retry-all-errors https://sitemind-backend.onrender.com/api/health
      - name: Ping codebook health endpoint
        run: curl -sf --max-time 90 --retry 3 --retry-delay 10 --retry-all-errors https://sitemind-codebook.onrender.com/health
```

- Both curl calls already have retry/backoff hardening (`--max-time 90 --retry 3 --retry-delay 10
  --retry-all-errors`) — this was itself a prior fix (raw `curl -sf` with no retry logic was too
  brittle against a service that's mid-cold-start when the ping fires).
- History added by commits: `cba05c8` ("Add cron job to keep backend warm") → `4a8f99c` ("Add
  Codebook as second Render service", which is when the second `curl` line for Codebook was added)
  → `b51f2f1` ("Keep Codebook warm too") → `16dd4a0` ("Fix false backend unreachable warning").
- **Known reliability gap:** GitHub Actions' `schedule:` cron is documented as best-effort, not
  exact — this workflow is configured for every 10 minutes but was observed firing irregularly
  (gaps of 1–5 hours between runs) with a mix of `success`/`failure` outcomes across the last ~15
  runs checked [from prior session, not re-verified today — `gh` CLI isn't available in this sandbox
  to re-check now; use the GitHub web UI's Actions tab, or install `gh`, to get current run history].
  **Do not assume this workflow reliably prevents idle cold starts** — it reduces the frequency but
  is not a guarantee, and GitHub's own scheduler is the reason why, not anything in this repo.

---

## 11. `docs/` is gitignored — critical for any "new machine" transfer

Confirmed this session (`.gitignore` lines 74–90): `docs/`, `.claude/`, `.playwright-mcp/`,
`graphify-out/`, `chat-history/`, `current_project/`, plus several root-level files (`CHECKPOINT.md`,
`Improvement_plan.md`, `PROGRESS.md`, `DEMO_STORY.md`, etc.) are **all gitignored** — deliberately
kept out of the public/shared repo as private/local-only working material.

**Practical consequence:** if you `git clone` this repo onto a new machine, you will get the code
(`backend/`, `frontend/`, `standards-service/`) and the tracked docs (`README.md`, this repo's
top-level files), but **you will NOT get this file, `docs/CHECKPOINT.md`, `docs/PROGRESS.md`, or
anything else under `docs/`**. If the intent of writing this file was to carry context to a fresh
clone on a new PC, **you must copy the `docs/` folder (and `.claude/` if you want the agent
definitions/skills too) over some other channel** — zip + transfer, a private cloud sync folder, a
second private git remote, etc. A plain `git clone` alone will silently leave all of this behind.

Also note: `backend/.env` and `frontend/.env.local` (the actual local secrets, if any are set) are
gitignored too, as expected — those were never meant to transfer via git either; re-create them from
`.env.example` (repo root) on the new machine.

---

## 12. Local tooling / CLI state (environment facts, not project facts — won't transfer to a new PC)

These are true of *this specific development machine*, not the project — re-establish them fresh
on a new PC:

- **Render CLI:** installed at `~/.local/bin/render`, authenticated this session as `Awnikant`
  (`kant4472@gmail.com`) via `render whoami`. Useful commands used this session:
  `render services -o json`, `render deploys list <service-id> -o json`,
  `render deploys create <service-id> --wait --confirm -o json`,
  `render logs --resources <service-id> --limit N` (plain text output — `-o json` **failed to
  parse** for the `logs` subcommand specifically, `parse error Extra data...`; use default text
  output for logs, JSON is fine for other subcommands).
- **Vercel CLI:** working via `npx vercel ...` (not globally installed), authenticated, but its
  stored token had gone stale for *direct REST API* calls specifically (see §4) — the CLI itself
  still worked fine via `npx vercel ls` / `npx vercel inspect`.
- **`gh` (GitHub CLI):** **not installed** in this sandbox as of 2026-07-23.
- **Python tooling in this sandbox:** no `backend/.venv` exists here, and `pip`/`pip3` are not even
  installed at the system level (`No module named pip`, `pip3 not found`) — this sandbox cannot run
  the backend or its evals directly; it's used for code editing / git / CLI ops only. If you need to
  actually run the backend or evals, do it on a machine with Python 3.12 + pip properly set up (see
  `README.md` / `docs/SETUP.md` — the normal `./run.sh` path handles venv creation there).
- **The harness this session runs in blocks chained `sleep N && <command>`** as a way to poll for
  async state (e.g. "wait for Render's deploy to finish") — it errors out and directs you to use a
  proper wait/monitor primitive instead of a sleep-loop workaround. If you're scripting a "wait for
  deploy" step yourself outside this harness, plain `sleep`/poll loops are fine there — this is a
  constraint of the Claude Code sandbox, not of Render/Vercel.

---

## 13. Quick operational runbook

**Health-check both services by hand:**
```bash
curl https://sitemind-backend.onrender.com/api/health
curl https://sitemind-codebook.onrender.com/health
curl https://sitemind-backend.onrender.com/api/codebook/corpora   # exercises the full MCP round-trip
```
Expect `{"status":"ok",...}` shapes; a slow-but-eventually-200 response from a cold service is
normal and expected (up to the timeouts in §8), not a bug.

**Force-redeploy the backend after a push** (needed because Render auto-deploy is unreliable — §5):
```bash
render deploys create <sitemind-backend-service-id> --wait --confirm -o json
```
(Same pattern for `sitemind-codebook`'s service id if that service needs a manual kick too.)

**If a user reports "Codebook unreachable" again:**
1. Get the exact time they saw it.
2. `render logs --resources <codebook-service-id> --limit 200` (plain text, not `-o json`) around
   that timestamp — look for a `Shutting down` / `Uvicorn running` pair close together (the §9
   restart-cycle pattern) vs. a long gap with no logs at all before the request (the §8 idle-cold-
   start pattern these timeouts already cover).
3. Confirm current health with the curl commands above.
4. Don't re-fix §8's timeouts again without new evidence they're insufficient — the current values
   (90s / 180s / 100s) were sized directly off measured worst-case cold-start latency. If it's
   recurring, it's more likely to be the §9 phenomenon — follow that section's next steps instead.

**Adding a new frontend origin (e.g. testing a Vercel preview URL against the prod backend):**
1. Render dashboard → `sitemind-backend` → Environment → edit `ALLOWED_ORIGINS`, add the new origin
   (comma-separated, no spaces needed but harmless if present — parsed via `.split(",")` +
   `.strip()` in `backend/app/config.py:78`).
2. Manually trigger a redeploy (§5 caveat — don't assume the env var change alone restarts it).

---

## 14. Related docs (for anything not deployment-specific)

- `README.md` — how to run locally, feature list, golden demo path.
- `docs/SETUP.md` — OS-specific local setup/troubleshooting (not deployment — this is the "getting
  it running on your laptop" doc; complements this file rather than duplicating it).
- `docs/PROGRESS.md` — the sole chronological build log; search it for "Render"/"Vercel"/"deploy" if
  you want the narrative context around *why* a given feature/decision happened, not just *what*
  the current deploy state is (this file is state + ops history; PROGRESS.md is the build narrative).
- `docs/CHECKPOINT.md` — session working-memory for the *demo/pitch* track of work (deck, video,
  narrative) — largely orthogonal to deployment, included here only because it's the other
  "resume a session" document and you should know it exists and what it's for.
- `docs/archive/DEPLOY.md` — the **original** deploy guide, written before Codebook existed as a
  second Render service, never fully executed as written (superseded by this file, kept for
  historical reference only — don't follow its steps directly, they're incomplete vs. current state).
