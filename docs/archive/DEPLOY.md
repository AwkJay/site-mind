# Deploying SiteMind (free tier: Vercel + Render)

Both services below have permanent free tiers (no credit card needed for Render's
free web service, none for Vercel's hobby tier). Total cost: **$0**. This gets you
a real public URL judges can open themselves, instead of only a screen-share.

Do this yourself — it needs your own GitHub/Vercel/Render accounts, and pushing
code to a public or private remote is not something to do without your go-ahead.
This doc is the exact steps; nothing here has been run for you.

## 0. Prerequisites

- A GitHub account, and this repo pushed there. This project has **no git repo
  yet** (confirmed 2026-07-03) — from `research/sitemind/`:
  ```bash
  git init
  git add .
  git commit -m "Initial commit"
  gh repo create sitemind --private --source=. --push   # or create on github.com and add a remote manually
  ```
  Double-check `backend/.env` is NOT staged (`git status` should not list it — the
  `backend/.gitignore` added 2026-07-03 excludes it) before you commit. It holds
  your real Langfuse secret key.
- A Vercel account (vercel.com, free "Hobby" tier) — sign in with GitHub.
- A Render account (render.com, free tier) — sign in with GitHub.

## 1. Backend on Render

1. Render dashboard → **New +** → **Web Service** → connect the GitHub repo.
2. Settings:
   - **Root directory**: `sitemind/backend`
   - **Runtime**: Python 3
   - **Build command**: `pip install -r requirements.txt`
   - **Start command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
     (Render injects `$PORT`; `run.sh`'s hardcoded `--port 8000` is for local dev
     only — don't use it here.)
   - **Instance type**: Free
3. Environment variables (Render → Environment tab) — **all optional**, the app
   runs fully offline with none of these set:
   - `LLM_PROVIDER=offline` (recommended for a stable public demo — see
     `docs/CODEX_SETUP.md` for why `codex` is unsuitable as a standing default:
     ~185s per call, unusable for a public-facing request)
   - `LANGFUSE_SECRET_KEY`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_BASE_URL` — only if
     you want the deployed instance to also emit real Langfuse traces
   - `ALLOWED_ORIGINS=https://<your-vercel-app>.vercel.app` — **required**, set
     this once you know your Vercel URL (step 2), or the frontend will hit CORS
     errors. Can be comma-separated with `http://localhost:3000` if you still
     want local dev to work against the deployed backend.
4. Deploy. Note the resulting URL, e.g. `https://sitemind-backend.onrender.com`.
5. Verify: `curl https://sitemind-backend.onrender.com/api/health` should return
   `{"status":"ok","offline_mode":true,"provider":"offline","langfuse_enabled":false}`
   (or `true`/your provider if you set the optional env vars).

**Free-tier caveat**: Render's free web services spin down after ~15 minutes of
inactivity. The first request after idle takes 30–60s to wake up (subsequent
requests are fast). Hit `/api/health` a minute before a live demo to warm it up.

## 2. Frontend on Vercel

1. Vercel dashboard → **Add New** → **Project** → import the same GitHub repo.
2. Settings:
   - **Root directory**: `sitemind/frontend`
   - **Framework preset**: Next.js (auto-detected)
   - **Build command** / **Output directory**: leave defaults
3. Environment variable:
   - `NEXT_PUBLIC_API_URL=https://sitemind-backend.onrender.com` (your Render URL
     from step 1 — no trailing slash)
4. Deploy. Note the resulting URL, e.g. `https://sitemind.vercel.app`.
5. Go back to Render and set `ALLOWED_ORIGINS` to this exact URL (step 1.3) if
   you hadn't already — then **manually redeploy the backend** (env var changes
   on Render don't auto-restart on some plans; check the dashboard).

## 3. Post-deploy checklist

- [ ] `curl <render-url>/api/health` → `status: ok`
- [ ] Open `<vercel-url>/` — Overview page loads with real stats
- [ ] Open `<vercel-url>/compliance`, select the DBR, run a check → 6 NCRs render
      with citations (proves frontend ↔ backend ↔ clauses.json all connected)
- [ ] Open `<vercel-url>/commissioning`, upload
      `backend/data/project_docs/sample_commissioning_log.csv` → findings render
- [ ] Open browser devtools Network tab, confirm no CORS errors on any page

If the backend is asleep (Render free tier) the frontend's built-in mock
fallback (`lib/mocks.ts`) will render demo data within ~3.5s instead of hanging
— acceptable for browsing, but wake the backend first for a live-data demo.

## 4. What does NOT change between local and deployed

- `OFFLINE_MODE` stays the safe default — no API key is required to deploy a
  fully working public demo.
- `manak`'s clause corpus is cached locally in `clauses.json` and ships with the
  repo — the deployed backend does not need manak running anywhere.
- No database, no vector store, no external service is required for the core
  demo to work end-to-end on the free tiers above.

## 5. Optional: a hosted vector store (only if you outgrow local retrieval)

The Copilot pillar's retrieval currently runs in-process (no external vector DB).
This is fine at the current corpus size. If you want to demonstrate it scaling,
Qdrant Cloud has a free tier (1 GB) — not wired up; out of scope unless you ask
for it specifically, since it's a real architecture change, not a config flip.
