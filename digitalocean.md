# Deploying SiteMind on DigitalOcean (guide only — not yet deployed)

> **Status: deferred, per `hexafalls_plan.md` §G.** This is a deploy GUIDE, not a deployed
> environment — DigitalOcean credits for this hackathon weren't confirmed at build time. Nothing
> here has been stood up or tested against a live DigitalOcean account. Treat every command/spec
> below as a starting point to verify, not a proven recipe (unlike `render.yaml`, which IS live —
> see that file for a working reference of the same idea on a different platform).

## 1. Services overview

SiteMind is 5 independently-deployable pieces. Only `backend` + `frontend` are required for the
core demo; the rest are additive.

| Service | What it is | Language/runtime | Port | Health check |
|---|---|---|---|---|
| `backend` | FastAPI app — all 5 pillars, evals, audit ledger | Python 3.12, buildpack | `$PORT` | `/api/health` |
| `standards-service` (Codebook) | Standalone MCP-consumable standards service | Python 3.12, buildpack | `$PORT` | `/health` |
| `frontend` | Next.js 14 Command Center UI | Node, buildpack | `$PORT` | `/` |
| `telegram-bot` | Long-polling field bot (plan §F1) | Python 3.12, buildpack | none (worker) | n/a |
| Actian VectorAI DB | Offline vector store (plan §C) | Docker container | 6573–6575 | — |

Only `backend` and `frontend` are needed for the golden demo path. `standards-service` is needed
only if `CODEBOOK_ENABLED=1`. `telegram-bot` is its own always-on worker process, not a web
service. Actian is needed only if `RETRIEVAL_VECTOR_STORE=actian` — the default `numpy` path needs
no extra service at all.

## 2. App Platform spec — one YAML per service

DigitalOcean App Platform's `doctl apps create --spec <file>.yaml` (or the equivalent App Platform
dashboard flow) takes one spec describing all services in an app, OR you can deploy each as its own
App Platform "app" the way `render.yaml` does per-service. The shape below mirrors `render.yaml`
(already live on Render for this project) translated to App Platform's spec format — cross-check
against DigitalOcean's own App Platform spec reference before using, since the exact YAML schema
(`services:` vs `- name:` nesting, `envs:` vs `envVars:`) differs between providers and this was
NOT validated against a real `doctl` run this session.

```yaml
# .do/app.yaml (illustrative — NOT validated against a real doctl deploy)
name: sitemind
region: nyc
services:
  - name: sitemind-backend
    github:
      repo: <your-fork>/sitemind
      branch: main
      deploy_on_push: true
    source_dir: backend
    build_command: pip install -r requirements.txt
    run_command: uvicorn app.main:app --host 0.0.0.0 --port $PORT
    http_port: 8080
    health_check:
      http_path: /api/health
    envs:
      - key: PYTHON_VERSION
        value: "3.12"
      - key: LLM_PROVIDER
        value: gemini
      - key: GEMINI_API_KEY
        type: SECRET
      - key: RETRIEVAL_ENABLED
        value: "1"
      - key: CODEBOOK_ENABLED
        value: "1"
      - key: CODEBOOK_MCP_URL
        value: ${sitemind-codebook.PUBLIC_URL}/mcp
      - key: MONGODB_URI
        type: SECRET
      - key: SOLANA_ENABLED
        value: "0"
      - key: ALLOWED_ORIGINS
        value: ${sitemind-frontend.PUBLIC_URL}

  - name: sitemind-codebook
    github:
      repo: <your-fork>/sitemind
      branch: main
    source_dir: standards-service
    build_command: pip install -r requirements.txt
    run_command: uvicorn app.main:app --host 0.0.0.0 --port $PORT
    http_port: 8080
    health_check:
      http_path: /health
    envs:
      - key: PYTHON_VERSION
        value: "3.12"

  - name: sitemind-frontend
    github:
      repo: <your-fork>/sitemind
      branch: main
    source_dir: frontend
    build_command: npm install && npm run build
    run_command: npm run start -- -p $PORT
    http_port: 8080
    envs:
      - key: NEXT_PUBLIC_API_BASE
        value: ${sitemind-backend.PUBLIC_URL}

workers:
  - name: sitemind-telegram-bot
    github:
      repo: <your-fork>/sitemind
      branch: main
    source_dir: telegram-bot
    build_command: pip install -r requirements.txt
    run_command: python bot.py
    envs:
      - key: TELEGRAM_BOT_TOKEN
        type: SECRET
      - key: ELEVENLABS_API_KEY
        type: SECRET
      - key: ELEVENLABS_VOICE_ID
        value: JBFqnCBsd6RMkjVDRZzb
      - key: GEMINI_API_KEY
        type: SECRET
      - key: BACKEND_URL
        value: ${sitemind-backend.PUBLIC_URL}
```

Notes on the spec above:
- `frontend/package.json`'s `start` script hardcodes `-p 3000`; the `run_command` above overrides
  it with App Platform's `$PORT` via `npm run start -- -p $PORT`. Confirm this override actually
  works with a real deploy — not tested.
- `workers:` (no HTTP port, no health check) is the right App Platform primitive for the Telegram
  bot's long-polling process — confirm the exact YAML key name against DigitalOcean's current docs;
  it may be `workers:` or nested under `services:` with `instance_size_slug` differences depending
  on API Platform spec version.
- Cross-service URL interpolation (`${service-name.PUBLIC_URL}`) is a DigitalOcean App Platform
  feature — confirm the exact template syntax before relying on it.

## 3. Actian VectorAI DB on DigitalOcean

Actian ships as a Docker image (`actian/vectorai:latest`), not a buildpack service — App Platform
supports Docker-based services via a `Dockerfile` or an image reference. Options:
1. **App Platform, Docker Hub source**: point a service at `actian/vectorai:latest` directly (if
   App Platform's image-source deploy type supports the ports/volume this container needs — its
   real requirements are `ports: 6573-6575`, `ACTIAN_VECTORAI_ACCEPT_EULA=YES` env var, and a
   writable volume at `/var/lib/actian-vectorai` — confirm App Platform's volume/persistent-disk
   support before relying on this, since Actian's data must survive restarts).
2. **A DigitalOcean Droplet** running the exact `docker run` command already proven locally
   (`docker-compose.actian.yml` at repo root) — simpler and more predictable for a container with
   persistent local storage requirements than a PaaS service.
3. **Skip it entirely** — `RETRIEVAL_VECTOR_STORE` defaults to `numpy` (in-memory), which needs no
   extra service and is what every retrieval eval in this repo is calibrated against. Actian is a
   sponsor-track integration, not required for the core demo.

## 4. MongoDB: Managed vs. Atlas

`MONGODB_URI` (used by both the audit ledger, plan §D, and F2's optional chat checkpointer) accepts
any real MongoDB connection string — this app has zero code dependency on which MongoDB service
provides it. Two options:
- **DigitalOcean Managed MongoDB** — a DO-native database cluster; simplest if staying entirely
  inside DigitalOcean for the "Best Use of DigitalOcean" sponsor track. Get the connection string
  from the DO control panel, set it as a SECRET env var.
- **MongoDB Atlas** (what this project used for local/dev testing) — works identically; use the
  `mongodb+srv://` connection string DigitalOcean is happy to reach over the public internet.

Either way: leave `MONGODB_URI` unset to keep the local-JSONL audit ledger fallback (already proven
live this session) rather than requiring a database at all for a minimal deploy.

## 5. Env var checklist

Same table as `hexafalls_plan.md` §9 — repeated here so this guide is self-contained. `type: SECRET`
in the specs above corresponds to "don't hardcode this in the YAML, set it via the dashboard/`doctl`
secrets flow" for anything sensitive.

| Var | Service(s) | Default | Purpose |
|---|---|---|---|
| `LLM_PROVIDER` | backend | `offline`→`gemini` when key present | select prose LLM |
| `GEMINI_API_KEY` | backend, telegram-bot | — | Gemini access |
| `GEMINI_MODEL` | backend, telegram-bot | `gemini-flash-latest` | Gemini model |
| `COMPLIANCE_RULE_EXTRACTION` | backend | `0` | enable the computed-draft verdict tier (B2) |
| `COPILOT_AGENT_ENABLED` | backend | `0` | enable the LangGraph copilot edge (F2) |
| `RETRIEVAL_ENABLED` | backend | `0` | mount `/api/retrieval/*`, needed for B2's computed-draft tier |
| `CODEBOOK_ENABLED` | backend | `0` | mount `/api/codebook/*` (talks to standards-service) |
| `CODEBOOK_MCP_URL` | backend | — | standards-service's MCP endpoint |
| `RETRIEVAL_VECTOR_STORE` | backend, standards-service | `numpy` | `numpy` \| `actian` |
| `ACTIAN_URL` | backend, standards-service | `localhost:6574` | Actian gRPC endpoint |
| `MONGODB_URI` | backend | — | Mongo connection (empty → local JSONL fallback) |
| `MONGODB_DB` | backend | `sitemind` | audit DB name |
| `SOLANA_ENABLED` | backend | `0` | enable devnet notarization |
| `SOLANA_RPC_URL` | backend | `https://api.devnet.solana.com` | devnet RPC |
| `SOLANA_SECRET_KEY` | backend | — | base58 devnet keypair (SECRET) |
| `SOLANA_CLUSTER` | backend | `devnet` | cluster label |
| `TELEGRAM_BOT_TOKEN` | telegram-bot | — | Telegram bot (SECRET) |
| `ELEVENLABS_API_KEY` | telegram-bot | — | STT + TTS (SECRET) |
| `ELEVENLABS_VOICE_ID` | telegram-bot | `JBFqnCBsd6RMkjVDRZzb` | multilingual voice |
| `BACKEND_URL` | telegram-bot | `http://localhost:8000` | Copilot API base — set to the deployed backend's URL |
| `HF_TOKEN` | backend, standards-service | — | Copilot's HF Inference API embeddings (SECRET) |
| `ALLOWED_ORIGINS` | backend | — | CORS allowlist — set to the deployed frontend's URL |

## 6. Droplet + reverse-proxy alternative

If App Platform's buildpack/spec model turns out to be a poor fit (e.g. Actian's Docker+volume
needs, or wanting one box for everything to save cost), a single Droplet works too:

1. Provision a Droplet (Ubuntu 24.04, at least 2 vCPU / 4GB RAM given numpy/pandas/sentence
   embeddings in the backend).
2. Install Docker + docker-compose, clone the repo.
3. Run `docker-compose.actian.yml` (already proven working locally) for the vector store, if wanted.
4. Run `backend/run.sh` and `standards-service/run.sh` under a process supervisor (systemd unit or
   `pm2`/`supervisor`) rather than backgrounding with `nohup` (fine for local dev, not for a server).
5. `frontend`: `npm run build && npm run start -- -p 3000` under the same supervisor.
6. `telegram-bot/run.sh` as its own systemd unit (long-polling, no port to expose).
7. Put nginx (or Caddy, for automatic TLS) in front, reverse-proxying:
   - `/` → frontend :3000
   - `/api/*` → backend :8000
   - a subdomain (or `/codebook/*` path) → standards-service, if used
8. Point DNS at the Droplet's IP; TLS via Caddy's automatic HTTPS or `certbot` for nginx.

This trades DigitalOcean's managed-platform conveniences (auto-deploy on push, managed health
checks/restarts) for one flat, predictable cost and full control over the Actian container's
persistent volume — likely the simpler path for a hackathon judge to reproduce.

## 7. The Python 3.12 pin

Both `backend/run.sh` and `standards-service/run.sh` prefer Python 3.12 explicitly
(`command -v python3.12 || command -v python3.11 || command -v python3`) — the pinned
numpy/pandas wheels in `requirements.txt` don't yet build on Python 3.14. Whatever DigitalOcean
buildpack/runtime is selected for the Python services, pin it to 3.12 (App Platform's Python
buildpack typically reads a `runtime.txt` or a `PYTHON_VERSION` env var — confirm the exact
mechanism DigitalOcean's current buildpack uses before relying on the `PYTHON_VERSION` env var shown
in the spec above, since that's Render's convention, not confirmed for DigitalOcean).
