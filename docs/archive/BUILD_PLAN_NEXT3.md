# SiteMind — build plan 3: "this looks hardcoded" fix + live-upload demo story

## Context

A hands-on UI review (2026-07-03, third pass) surfaced 5 concrete issues, all verified against
the running app, not guessed:

1. **Settings gear button did nothing** (`Shell.tsx` — no `onClick` at all). **FIXED already**:
   wired to a real popover (`SettingsPanel`) showing live `/api/health` state (provider,
   offline_mode, langfuse_enabled) + the "Agents online"/"Mode" indicators now reflect actual
   backend reachability instead of being hardcoded strings.
2. **Mojibake in the Compliance document register** ("Foundation shop drawing â€" footing...").
   **FIXED already**: root cause was `Path.read_text()` / `Path.write_text()` calls in
   `data_loader.py`, `standards.py`, `trace.py`, `eval.py`, `commissioning_standards.py` with no
   explicit `encoding="utf-8"` — on Windows, `Path.read_text()` defaults to the system codepage
   (cp1252), which mangles the UTF-8 em-dashes already correctly stored in `submittals.csv`. All
   6 call sites now pass `encoding="utf-8"` explicitly. Verified via a direct `/api/documents`
   call post-restart: real em dashes render correctly.
3. **Schedule Gantt shows almost everything red/critical**: verified with real numbers — 19/33
   activities (58%) on critical path, 13/33 (39%) at-risk, only 7/33 nominal. Traced to
   `schedule.csv`'s `pct_complete` values not tracking elapsed time realistically outside the 2-3
   deliberately-planted narrative rows (e.g. `DC1-02-CS-050`: window closed 35 days ago, still
   shows 20% complete) — the leading-indicator rule logic itself is correct and eval-verified
   (`run_schedule_eval.py` uses fully synthetic held-out rows/DAGs, independent of the real CSV —
   confirmed by reading it, so this fix carries zero eval-regression risk).
4. **Supply Chain data provenance is undisclosed**: confirmed `supply_chain.py` reads one static
   JSON fixture once (`lru_cache`), derives "status" by diffing that frozen milestone snapshot
   against a fixed `TODAY_DAY=175` constant — genuinely computed, but not live-tracked, and the
   page never says so.
5. **Knowledge Graph has zero in-product methodology explanation**: confirmed `kg.py` builds a
   real NetworkX graph from structured data (same `applicable_checks()` used by Compliance, no
   LLM/embeddings involved) but the page doesn't say this.

The user chose the largest of three offered remediation tiers: **disclosure + realism fixes,
PLUS a simulated day-advance control, PLUS a small set of realistic-looking documents for live
upload during the demo** — i.e. everything below.

## Scope (5 slices, smallest/safest first)

**Slice 1 — Disclosure panels (near-zero regression risk).**
- Supply Chain page: an "as of Day N (~date) — static demo snapshot, not live carrier tracking"
  banner, sourced from a real backend field (not a hardcoded frontend string).
- Knowledge Graph page: a short "how this was built" panel — NetworkX, same structured data +
  same `applicable_checks()` rule engine as Compliance, zero LLM/embeddings involved.

**Slice 2 — Schedule realism fix.**
Rewrite `backend/data/schedule/schedule.csv`'s `pct_complete` column only (same 33 rows, same
DAG, same durations/predecessors — do not touch structure) so completion tracks elapsed time
realistically for activities NOT part of the deliberate narrative (LV switchgear procurement,
DRUPS, the one planted weather-sensitive catch), while keeping those specific rows genuinely
behind. Target: critical path share drops to a defensible ~25-35% (real projects have float),
at-risk count driven by genuine leading indicators, not universal progress-lag saturation.
Re-verify: `run_schedule_eval.py` (independent, should be untouched), the Compliance DBR baseline
(independent pillar, unaffected), and re-run `run_impact_eval.py`/`run_cost_risk_eval.py` (pure
formula evals, safe by construction) — but manually sanity-check the LIVE `/api/overview` and
`/api/cost-risk` numbers still look sane with the new schedule shape (they will change in value,
which is correct and expected, not a regression).

**Slice 3 — Simulated day-advance control (the "prove it's not hardcoded" beat).**
New `backend/app/clock.py`: a single mutable `_offset_days` (default 0), `current_day()` returns
`schedule.TODAY_DAY + _offset_days`, `advance(days)` / `reset()` mutate it and clear every cache
downstream of "today" (`schedule._cpm`, `schedule.risks`, `supply_chain.shipments`,
`supply_chain.risks`, `supply_chain.alerts`, plus impact/cost-risk since they compose those).
`schedule.py` (2 call sites) and `supply_chain.py` (4 call sites) switch from the bare
`TODAY_DAY` constant to `clock.current_day()` at the point of use. New
`POST /api/clock/advance {days}` and `POST /api/clock/reset`. Frontend: a small control (likely
on Overview or Schedule) — "Advance N days" — that re-fetches and visibly changes at-risk counts/
alerts/mitigation options, so a judge watches the system react instead of taking "derived, not
hardcoded" on faith. Highest-risk slice (cross-module cache invalidation) — verify with a live
before/after API diff, not just "it didn't crash."

**Slice 4 — Synthetic documents for live upload.**
Author 2 new realistic-looking documents, one connected narrative, both parseable by the REAL
regex extractors in `ingest.py` (not decorative text — sentences must match the existing
extraction patterns so a live upload produces genuine NCRs):
- A `.docx` "Design Basis Report" excerpt for a second discipline/element not already in the
  bundled demo DBR (so it's visibly a *different* live upload, not a re-upload of the existing
  fixture) — e.g. a column/footing pair with a cover value that trips the real IS 456 check.
- A `.docx` "Method statement" or shop-drawing-style doc continuing the same narrative (same
  project, same element family) so the two documents tell one story across two live uploads.
Verify via an actual `POST /api/compliance/ingest` call on the built file, not just eyeballing
the prose — confirm real extracted params + a real NCR against a real cited clause.

**Slice 5 — Regression + docs.**
Full 13-eval sweep + DBR baseline check. Update `PROGRESS.md`, `DEMO_STORY.md` (add the new
upload beat + the day-advance beat), `README.md` Golden Demo Path.

## Non-negotiables (carried from `.claude/CLAUDE.md`, apply throughout)
- Never invent a clause; every new document's extractable claims must resolve to a real cited IS
  clause via the existing deterministic check pipeline, not a new hand-asserted verdict.
- No ML, no LLM-based extraction for the new documents — same regex/heuristic pipeline as today.
- Compliance DBR baseline (`10 checked / 6 NCRs / 4 conforming`) must not regress — Slice 2-4
  touch schedule/supply-chain/new-uploads only, never the tracked DBR fixture itself.
- Every existing eval must still pass; report the real re-run numbers, never assert them.
