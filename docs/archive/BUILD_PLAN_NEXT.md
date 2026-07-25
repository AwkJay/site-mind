# BUILD_PLAN_NEXT.md — the next build phase (handoff for the implementing model)

> Written 2026-07-03 after a senior-SWE gap review + a grill-me scoping pass with the user.
> **This is the authoritative spec for the next phase.** Read it top-to-bottom before touching
> code. It is self-contained: real file paths, real symbols, the guardrails, and pass/fail
> acceptance checks are all here. Pairs with `PLAN.md` (§ "Next build phase") and `PROGRESS.md`
> (tail). Keep `PROGRESS.md` current from your first slice.

---

## 0. Why this phase exists (the gap review, in one paragraph)

SiteMind is engineering-strong but **unevenly built** against ET Hackathon P4, and two of the
brief's *own explicitly-named* asks are currently **missing, not scoped-out**:
1. **Cost risk** — the brief says "schedule **AND cost** risk modelling." Only schedule risk
   exists. No cost model anywhere in the codebase.
2. **Reduction in manual coordination effort, measured in hours** — computed today **only for
   Pillar 1** (`backend/app/overview.py`, `HOURS_PER_ISSUE=20`, `REWORK_INR_PER_ISSUE=1_500_000`,
   counting NCRs). Schedule / Supply-Chain / Commissioning contribute nothing to the ROI number.

A third gap is UX: the RFI↔NCR↔shipment connections that make the demo compelling live only in
`DEMO_STORY.md` narration — they are **not surfaced in the product**. A judge browsing the
repo/video unguided never discovers that `SHP-002` and `RFI-EL-112` are the same issue. Only the
Compliance pillar's `ActionBrief` links evidence in-app.

## 1. Decided scope (grill-me, 2026-07-03)

- **Runway:** full remaining window (build properly, not a rush polish).
- **Delivery format:** **recorded video + repo** → **live deploy is OUT** (a live URL isn't the
  delivery vehicle). `DEPLOY.md` stays ready for later; don't run it.
- **IN scope:** three builds + repo-facing polish (below). **OUT:** deploy, CV, Procore/QMS,
  multi-agent orchestration retrofit, auth, multi-tenant, commissioning power/IT slices (still
  corpus-blocked — keep the honest "cooling slice by design" framing).

## 2. NON-NEGOTIABLE guardrails (the whole credibility thesis — do not violate)

1. **No asserted numbers.** Every new cost/hours figure must be **computed** from real inputs and
   **eval-backed**. A single asserted number reopens the exact "confidently fabricates" critique the
   `source_type`/abstention discipline exists to defeat. → Each new deterministic output gets its
   **own held-out eval, never blended** (we currently report **8** separate eval numbers; this phase
   adds a 9th and 10th → keep them separate).
2. **Decisions in Python, never the LLM.** Same pattern as `backend/app/agents/checks.py`.
3. **Never invent a clause.** No new standards work is required here; if any arises, it must resolve
   to real primary text with a correct `Citation.source_type` (see `schemas.py` docstring).
4. **Protect the tracked baseline.** Compliance DBR `DC1-02-DBR-0001-R2` must stay
   **10 checked / 6 NCRs (3 HIGH / 2 MEDIUM / 1 ADVISORY) / 4 conforming**, and all 8 existing evals
   must stay green. **Verify after every slice, not just at the end.**
5. **Synthetic inputs stay labelled REPRESENTATIVE** (README "What's REAL vs REPRESENTATIVE"). New
   cost base-data is synthetic; the *logic* over it is real. Say so.
6. **OFFLINE_MODE stays the default** and must keep working with no API key.

## 3. Real code anchors (verified 2026-07-03 — reuse these, don't reinvent)

- `backend/app/overview.py` — `GET /api/overview`, `OverviewStats`. Holds the only existing
  hours/₹ formula (`HOURS_PER_ISSUE`, `REWORK_INR_PER_ISSUE`), counts DBR NCRs via `_all_ncrs()`.
- `backend/app/schedule.py` — `risks()` → `RiskItem` with `detected_lead_time_days`,
  `project_impact_days` (real CPM re-run), `on_critical_path`, `predicted_slip_days`. `TODAY_DAY`, `_cpm()`.
- `backend/app/supply_chain.py` — `risks()` → `SupplyChainRisk` with `days_at_risk`,
  `detected_lead_time_days`, `recommended_alternative.cost_premium_pct`, `wbs_id`, `on_critical_path`.
  `shipments()` → `Shipment` (has `wbs_id`, `equipment_spec`). Data: `load_supply_chain()`.
- `backend/app/commissioning.py` + `schemas.py` `CommissioningFinding` (`verdict` incl. `FAIL`),
  `QualityPackage` (`fail_count`, `within_allowable_count`, `finding.ncr`).
- `backend/app/schemas.py` — all contracts. Extend here; frontend depends on these shapes.
  Relevant: `OverviewStats`, `RiskItem`, `SupplyChainRisk`, `Shipment`, `ActionBrief`
  (`LinkedRFI`/`AffectedActivity`/`RecommendedAction`/`Confidence` — the linking template to generalize).
- RFI log: `backend/data/project_docs/rfi_log.csv` (has `RFI-EL-112` referencing the same
  `wbs_id: DC1-04-EL-030` as `SHP-002` — the join key for real, computed linking).
- Frontend: `frontend/lib/types.ts`, `frontend/lib/format.ts` (meta maps), `frontend/lib/api.ts`,
  `frontend/lib/mocks.ts`, `components/NCRCard.tsx`, `components/CitedClauseBox.tsx`, the ActionBrief
  render on `app/compliance/page.tsx`; pages `app/supply-chain/page.tsx`, `app/commissioning/page.tsx`,
  `app/page.tsx` (Overview), `app/schedule/page.tsx`. Eval page reads the separate eval report JSONs.
- Evals live in `backend/eval/` (`run_eval.py`, `run_extraction_eval.py`, `run_electrical_eval.py`,
  `run_equipment_spec_eval.py`, `run_supply_chain_eval.py`, `run_schedule_eval.py`, `run_copilot_eval.py`,
  `run_commissioning_eval.py`). Each writes its own `*_report.json`. **Add two more; never blend.**

## 4. Slices (build in this order, smallest-first — one coupled chat, phase by phase)

These three builds share `schemas.py`, the overview/impact layer, and the frontend — **coupled**,
so **no parallel writers**; subagents only for read/review/verify. `/compact` at each slice seam.

### Slice 1 — Impact model (hours-saved across ALL 4 pillars)  [cheapest, do first]
- New `backend/app/impact.py`: a per-pillar impact layer with **documented, defensible assumptions**
  (mirror `overview.py`'s existing constant-with-a-comment style). Compose hours + ₹ from *real signals*:
  - Compliance: existing NCR-count formula (unchanged).
  - Schedule: from `schedule.risks()` — e.g. hours saved per early-warning (`detected_lead_time_days`)
    and/or ₹ tied to `project_impact_days` avoided. Document the per-unit assumption.
  - Supply-Chain: from `supply_chain.risks()` — `days_at_risk` mitigated + expedite-premium avoided
    (`recommended_alternative.cost_premium_pct`). Document assumptions.
  - Commissioning: from FAIL count (`QualityPackage.fail_count`) — rework/re-test hours avoided.
- Extend `OverviewStats` (schemas.py) with a **per-pillar breakdown** (list or dict of
  `{pillar, hours, inr, basis}`). Update `overview.py` to compose from `impact.py`.
- Frontend: Overview page shows the per-pillar breakdown, computed live from the API (each row shows
  its `basis` string so the number is defensible on camera).
- **Eval #9:** `backend/eval/run_impact_eval.py` — assert the formula on fixed inputs (guards drift).

### Slice 2 — Cost-risk modeling (the brief-named gap)
- New `backend/app/cost_risk.py` + `CostRisk` schema. **Deterministic** cost-at-risk, transparent formula
  (NOT ML / Monte-Carlo — that would contradict the no-ML, explainable thesis):
  `cost_at_risk = schedule_delay_cost + expedite_premium_cost + rework_exposure`, where
  - `schedule_delay_cost` = critical-path slip days (`RiskItem.project_impact_days`) × a documented daily
    delay/liquidated-damages rate;
  - `expedite_premium_cost` = `cost_premium_pct` × a documented equipment base cost;
  - `rework_exposure` = open-NCR count × `REWORK_INR_PER_ISSUE` (reuse the existing constant).
- New synthetic, **documented, REPRESENTATIVE** cost table:
  `backend/data/project_docs/cost_basis.json` (daily delay rate, per-item base costs). Label it clearly.
- New `GET /api/cost-risk` endpoint; Cost-at-Risk UI panel that **shows the formula inputs** (same
  transparency spirit as `ActionBrief.computed_impact`). **Default placement: Overview page** next to the
  ROI ticker — reconsider Schedule page only if it reads better once wired.
- **Eval #10:** `backend/eval/run_cost_risk_eval.py`.

### Slice 3 — In-UI evidence linking (RFI↔NCR↔shipment↔activity)
- Backend: a resolver that **computes** cross-references from shared keys (join `rfi_log.csv` to shipments
  by `wbs_id`; reuse the `ActionBrief` RFI/activity link logic). Add computed `linked_rfi` /
  `linked_activity` fields to `SupplyChainRisk`/`Shipment`; confirm commissioning `finding.ncr` is
  surfaced. **No hardcoded links** — every link derived from a real shared key.
- Frontend: a shared `LinkedEvidence` chip component (generalize Compliance's ActionBrief link render),
  reused on `/supply-chain` and `/commissioning`, so `SHP-002 ↔ RFI-EL-112 ↔ DC1-04-EL-030` is a
  clickable chip a judge discovers unguided — not narration-only. Update `mocks.ts` to match.

### Slice 4 — Repo-facing polish (docs/pitch; no core logic)
- `docs/ARCHITECTURE.md` — a **Mermaid** architecture diagram (renders on GitHub; repo-native, versioned)
  + a **"Why we are deliberately not fully agentic — a stated position"** section (the brief lists
  Agentic/Multi-Agent first; our deterministic-Python-plus-single-LLM-call design is a *choice* for
  hallucination-safety, not an omission — say it, or a judge reads silence as a gap). Mirror a short
  version into `README.md`.
- Update `README.md`, `PROGRESS.md`, `DEMO_STORY.md`, and root `.claude/CLAUDE.md` with the new metrics
  and the two new eval numbers. Wire eval #9/#10 into the Eval page (now **10** separate numbers, framed
  "never blended").

## 5. Execution model & checkpointing

One driving chat, Slices 1→4 in order, smallest-first. Coupled work (shared `schemas.py` + frontend) →
no parallel writers; use subagents only for read/review/verify fan-out. Suggest `/compact` at each slice
seam. Durable state = this file + `PROGRESS.md` + a `TaskCreate` todo list — if compaction fires, resume
from those, not the transcript.

## 6. Done when (testable acceptance checks)

- [ ] `GET /api/overview` returns hours/₹ contributions from **all 4 pillars** (not just Compliance),
      each traceable to a documented assumption in `impact.py`.
- [ ] Overview page shows a per-pillar hours-saved breakdown, computed live, each row showing its `basis`.
- [ ] `GET /api/cost-risk` returns a deterministic cost-at-risk with **visible formula inputs**; a
      Cost-at-Risk UI panel renders it.
- [ ] `/supply-chain` and `/commissioning` show **clickable** linked-evidence chips
      (e.g. `SHP-002 ↔ RFI-EL-112 ↔ DC1-04-EL-030`) — **derived, not hardcoded**.
- [ ] `run_impact_eval.py` and `run_cost_risk_eval.py` exist and pass; reported as **two NEW separate**
      numbers (now 10 evals), never blended.
- [ ] **All 8 pre-existing evals still pass** and the Compliance baseline is still **10 / 6 / 4**.
- [ ] `docs/ARCHITECTURE.md` has a rendered Mermaid diagram + the "why not fully agentic" position;
      README / PROGRESS / DEMO_STORY reflect the new metrics.
- [ ] Backend (`--port 8001`, since manak MCP may hold 8000) + frontend (`:3000`,
      `NEXT_PUBLIC_API_URL=http://localhost:8001`) run and every new surface is exercised end-to-end.

## 7. How to run / verify (Windows)

- Backend: `cd sitemind/backend && .venv/Scripts/python.exe -m uvicorn app.main:app --port 8001`
- Frontend: `cd sitemind/frontend && npm install && npm run dev` (set `NEXT_PUBLIC_API_URL=http://localhost:8001`)
- Evals: `cd sitemind/backend && .venv/Scripts/python.exe -m eval.run_eval` (repeat per eval module).
- Regression gate before declaring any slice done: re-run all evals + confirm the 10/6/4 baseline.
