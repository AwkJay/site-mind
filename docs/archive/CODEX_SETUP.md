# Using OpenAI Codex as SiteMind's LLM backend (ChatGPT login, no API key)

SiteMind runs **fully offline by default** — compliance pass/fail + clause citations are deterministic, and
prose/answers come from cached fixtures. That's the safest path for a scripted stage demo (no network, no
latency, no failures). Enable Codex only when you want **live prose** or the copilot to answer **unseen**
questions / **newly uploaded** documents.

## What Codex is (and the honest trade-off)
The **Codex SDK** (`openai-codex`) drives a local **Codex coding agent** authenticated via your **ChatGPT
login** — so it needs no API key or separate billing. But it is a *coding agent*, not an inference API, so it
is **much slower** than a normal LLM call in the request path — **measured live 2026-07-03: ~185 seconds for
one trivial completion** (a fresh app-server thread per call is the likely cost, not model latency). SiteMind
constrains it to a `read_only` sandbox (it cannot edit files or run commands) and uses it purely for text
generation. If a call is slow or fails, SiteMind **automatically falls back** to the deterministic offline
output — nothing can crash a request, but nothing times it out early either, so a slow call just blocks.

**Do not set `LLM_PROVIDER=codex` as the standing default.** `compliance.py`'s `_violation_ncr()` calls the
LLM once per NCR, synchronously, in the same request. The bundled demo DBR (`DC1-02-DBR-0001-R2`) raises 6
NCRs — at ~185s each that's 18+ minutes for one compliance check, which will hang the SSE stream and the
frontend well past any reasonable demo pause. Keep `LLM_PROVIDER=offline` in `backend/.env` at all times
except the one scripted moment described below.

## One-time setup
1. **Install the Codex CLI** and sign in with your ChatGPT account:
   ```bash
   # install the Codex CLI per OpenAI's instructions, then:
   codex login          # opens ChatGPT login in the browser
   ```
2. **Install the Python SDK** into the backend venv:
   ```bash
   cd backend && source .venv/bin/activate
   pip install -r requirements-codex.txt      # installs openai-codex
   ```
3. **Point SiteMind at Codex** — in `backend/.env`:
   ```ini
   LLM_PROVIDER=codex
   CODEX_MODEL=gpt-5.4        # or whichever model your Codex account exposes
   ```
4. **Restart** the backend (`./run.sh`). Check it picked up the provider:
   ```bash
   curl -s localhost:8000/api/health
   # -> {"status":"ok","offline_mode":false,"provider":"codex"}
   ```

## How it's wired (for reference)
- `app/config.py` — `LLM_PROVIDER` selects the backend; `OFFLINE_MODE` is derived from it.
- `app/llm.py` — `_codex_complete()` reuses one Codex app-server, starts a `Sandbox.read_only` thread per
  call, and returns `result.final_response`. Any exception → returns `""` → caller uses the offline path.
- Callers (`agents/compliance.py` `_prose`, `agents/copilot.py`) prefer curated fixtures for the known demo
  inputs and only call the live model for unseen ones — so the scripted demo stays deterministic even with a
  provider configured.

## Recommendation for the hackathon
- **On stage:** keep `LLM_PROVIDER=offline` (or rely on the fixture-first behaviour). It's bulletproof.
- **For the "it generalises" moment:** switch to `codex` and ask the copilot ONE question that's *not* in the
  fixtures (the copilot only calls the LLM once per question, unlike the compliance check's per-NCR loop) —
  then **wait ~3 minutes** for the real response, or pre-record it once and play the clip live rather than
  wait on stage. Do not demo a live compliance check under `codex` — see the per-NCR cost above.
- Swapping to `openai` (API key) or `anthropic` is a one-line `LLM_PROVIDER` change if you prefer — both are
  real inference APIs and should return in a couple of seconds, not minutes.
