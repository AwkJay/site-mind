# Demo-day runbook — operational checklist, not narrative

`DEMO_STORY.md` is what to say. This is what to do with the machine beforehand so nothing narrative-worthy
breaks on stage. Run this checklist the night before and again right before doors open — not for the first
time five minutes before you go on.

## 1. Startup order (do this once, well before doors open)

Start each service separately, in its own terminal, in this order:
```bash
# Terminal 1 — Codebook (the standalone standards service)
cd standards-service && ./run.sh          # serves on :8010

# Terminal 2 — backend, with both optional flags on so Codebook + Knowledge Base go live
cd backend && CODEBOOK_ENABLED=1 RETRIEVAL_ENABLED=1 ./run.sh   # serves on :8000

# Terminal 3 — frontend
cd frontend && npm install && npm run dev   # -> http://localhost:3000
```
Confirm each process is actually up before moving on — don't trust that a command returning means all
three processes are healthy:
```bash
curl localhost:8000/api/health     # -> {"status":"ok","offline_mode":true,...}
curl localhost:8010/health         # -> {"status":"ok","service":"codebook"}
```
Then open `http://localhost:3000` and check the top-bar status indicator is green (reached the real
backend, not silently showing mock data).

**Backend port is 8000 by default.** If it's ever run on a different port (8000 already taken), the
frontend needs `NEXT_PUBLIC_API_URL` in `.env.local` pointed at the actual port, and `npm run dev` (inside
`frontend/`, not the repo root) restarted after — Next.js only reads `.env.local` at startup.

## 2. Pre-warm the Codebook corpus — the single biggest live-demo landmine

`standards-service` has no on-disk embeddings cache: **every process restart triggers a ~7 minute blocking
rebuild** of the 6,206-chunk structural corpus (`docs/features.md`). Consequences for demo day:
- Start `standards-service` (`cd standards-service && ./run.sh`) **at least 15 minutes before you need it
  live**, not right before your slot.
- **Never restart `standards-service` once it's warm** — not to "refresh" it, not because something looks
  stale, not between rehearsal and the real run. A restart mid-event means either a 7-minute dead-air wait
  or skipping Codebook entirely.
- If you must restart it, immediately re-run `curl localhost:8010/health` in a loop and do not touch the
  Codebook Console or Act 7 until it returns healthy.
- If time is genuinely short before going on and Codebook won't be warm in time: **use the 5-minute cut**
  (`DEMO_STORY.md`), where Codebook is one sentence at the close, not a live panel — the corpus being cold
  degrades that sentence not at all.

## 3. Know the SSE fallback and never hide it

The Compliance reasoning panel tries a real SSE stream from the backend (`POST
/api/compliance/check/stream`); if that connection fails for any reason, `frontend/lib/api.ts`'s
`streamCompliance()` transparently falls back to `simulateStream()` — a client-side replay of the same
reasoning trace, so the panel still animates instead of breaking. **This is already disclosed in the UI**:
a small badge reads `● live · backend SSE` or `● simulated · mock stream` (`frontend/app/compliance/page.tsx`
line ~331) — and a parallel badge on Action Briefs reads `● live · backend` or `● derived client-side`.
Your job is not to build a disclosure — it's already built — your job is to **actually look at the badge**
before narrating "this is a real live stream," and to say the honest sentence out loud if it ever reads
"simulated": *"That badge means the backend connection dropped for this run — same underlying trace, replayed
client-side. Let me reconnect and show you the live one."* Never narrate over a simulated badge as if it were
live; that's the one thing that would actually violate this project's own honesty model.

## 4. Reset the simulated clock before you go on

`clock.py`'s `_offset_days` is a single server-lifetime mutable value — it does **not** reset when you
restart the frontend, only when you restart the backend or hit `/api/clock/reset`. If you rehearsed the
clock-advance beat earlier, **reset it before the real run**:
```bash
curl -X POST localhost:8000/api/clock/reset
```
Otherwise the "baseline" numbers you narrate in Act 1-3 won't match what a judge sees if they poke around
afterward.

## 5. Browser click-through — do this once, for real, before presenting

`docs/features.md` admits no automated browser test (Playwright or otherwise) exists for this app — every
page's interactive behavior has only ever been eyeballed, not regression-tested. Before presenting, manually
click through every surface you intend to touch live, in an actual browser, in the order you'll narrate them:
- [ ] `/compliance` — run the check, click a citation, confirm the clause modal opens with a provenance badge
- [ ] `/` (Overview) — confirm ROI + Cost-at-Risk panels render real numbers, not a loading skeleton
- [ ] `/supply-chain` — click the SHP-002 evidence chip, confirm it navigates/links correctly
- [ ] `/commissioning` — upload the sample CSV live, confirm Zone C FAIL renders and the quality package link works
- [ ] Live-upload flow — upload both `live_upload_samples/*.docx` files, confirm the NCRs match what's documented in `DEMO_STORY.md` Act 5
- [ ] Clock control — advance +14 days, confirm at-risk counts and `advance_warning_days` visibly change, then reset
- [ ] `/codebook` and `/codebook/console` — if either might come up in Q&A, confirm both load and a `search_standards` call returns real results

## 6. Fallback plan if something breaks anyway

- Backend unreachable entirely → the frontend silently shows bundled mock data with a red status indicator.
  **Say this out loud if it happens** rather than presenting mock numbers as live — "the backend connection
  just dropped, here's what mock fallback looks like, let me restart it" is a recoverable moment; presenting
  mock data as live and getting caught is not.
- Codebook cold and no time to pre-warm → use the 5-minute cut, Codebook becomes one sentence, not a beat.
- Live-upload document fails to parse as expected → this has been hand-verified against the real regex
  extractors (`DEMO_STORY.md` Act 5 note), so a failure here means something changed in `ingest.py` since
  last verified — re-run the click-through above before the same slot, don't discover it live.
