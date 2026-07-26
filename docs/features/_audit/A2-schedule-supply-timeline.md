# Agent A2 Audit — Schedule + Supply Chain + Timeline + Cost/Impact

Scope: `backend/app/schedule.py`, `schedule_factors.py`, `supply_chain.py`, `timeline.py`,
`cost_risk.py`, `impact.py`, `evidence_links.py`, `data_loader.py`, `agents/mitigation.py`,
`frontend/app/schedule/page.tsx`, `frontend/app/supply-chain/page.tsx`,
`frontend/app/timeline/page.tsx`.

Method: hit the live backend (`localhost:8000`) with curl, including a real `POST
/api/clock/advance` (+30 days) / `POST /api/clock/reset` round-trip, then confirmed every
observed behaviour against source. Backend and frontend were both live and reachable at
audit time.

## Summary verdict

**This scope is genuinely computed, not canned.** Every route inspected is real Python
arithmetic over loaded fixture data (CSV/JSON committed under `backend/data/project_docs/`),
not asserted output. I found no hardcoded verdicts, no fake "recomputation," and no silent
mock-as-live behavior. The live clock-advance test proved the causal chain end-to-end:
advancing the simulated day by 30 changed `predicted_slip_days`, surfaced three *new*
progress-lag risk items that weren't previously flagged, and pushed `advance_warning_days`
on both supply-chain alerts up by exactly 30 (45→75, 40→70) — then a reset fully restored
baseline output. The one place that looked like a bug on first read — `schedule.risks()`
and friends are `@lru_cache(maxsize=1)`, which would normally make them stale relative to
the clock — turns out to be deliberately handled: `clock.set_offset()` explicitly calls
`.cache_clear()` on every downstream cache (`schedule.py`:239, `clock.py`:44-52). Confirmed
live, not just read in source.

The honesty-labeling discipline claimed in project docs (REPRESENTATIVE synthetic data,
assumption constants named in `basis` strings, dormant-rule self-disclosure) is real in
source and substantially — though not 100% — surfaced in the UI (see "Assumption constants"
and UI sections below for the gap).

## Per-route table

| Route | Method | Verdict | file:line |
|---|---|---|---|
| `/api/schedule/risks` | GET | COMPUTED | `backend/app/schedule.py:239-253` (`risks()`, `_assess()`) |
| `/api/schedule/gantt` | GET | COMPUTED | `backend/app/schedule.py:256-283` |
| `/api/schedule/methodology` | GET | COMPUTED (reads 2 small JSON config files for window dates/constants, self-reports live firing status) | `backend/app/schedule.py:286-340` |
| `/api/supply-chain/shipments` | GET | COMPUTED (over static milestone snapshot; see caveat below) | `backend/app/supply_chain.py:378-380`, `_build()` at 222-246 |
| `/api/supply-chain/risks` | GET | COMPUTED | `backend/app/supply_chain.py:391-393` |
| `/api/supply-chain/alerts` | GET | COMPUTED | `backend/app/supply_chain.py:347-349`, `_build_alert()` at 318-337 |
| `/api/supply-chain/meta` | GET | COMPUTED (metadata/disclosure only) | `backend/app/supply_chain.py:352-375` |
| `/api/supply-chain/equipment-spec-ncrs` | GET | COMPUTED (returned `[]` live — no MISMATCH shipments in bundled data) | `backend/app/supply_chain.py:396-406` |
| `/api/supply-chain/map` | GET | COMPUTED (plain reshaping of `shipments()`, no new logic) | `backend/app/supply_chain.py:409-459` |
| `/api/timeline` | GET | COMPUTED (pure aggregation, zero new judgment — see Q4) | `backend/app/timeline.py:296-303` |
| `/api/cost-risk` | GET | COMPUTED (formula real; dollar constants are labeled assumptions — see below) | `backend/app/cost_risk.py:130-132`, `compute_cost_risk()` at 97-127 |
| `/api/clock`, `/api/clock/advance`, `/api/clock/reset` | GET/POST | COMPUTED (mutates an in-process int; clears dependent caches) | `backend/app/clock.py` |
| `impact.py` pillar impacts (`all_pillar_impacts`, exposed via `/api/overview` per `docs/features.md:18`) | — | COMPUTED (formula real; hours/₹ constants are labeled assumptions — see below) | `backend/app/impact.py:161-167` |

No fixture-only or hardcoded routes found in this scope. One route, `equipment-spec-ncrs`,
returns `[]` on the bundled demo data — genuinely computed, just currently empty (not
disguised as populated).

## Frontend page behaviour

- `frontend/app/schedule/page.tsx`: fetches `/api/schedule/gantt`, `/api/schedule/risks`,
  `/api/cost-risk` etc. via `frontend/lib/api.ts`'s `getJSON()` wrapper (line 77-88), which
  on any fetch failure/timeout falls back to hand-authored mock data in `frontend/lib/mocks.ts`
  and flags `live: false`. Confirmed the UI surfaces this: `frontend/app/timeline/page.tsx:161`
  renders `" (Showing bundled mock data — backend unreachable.)"` when `live` is false — this
  is a legitimate offline-safe fallback, not silent fabrication, and it self-discloses.
- `frontend/app/schedule/page.tsx:246` and `:266`/`:337` put the `CostRisk.data_note` and
  each `basis` string into a `title=` tooltip attribute (hover-to-reveal), and
  `MitigationOptionsPanel` (`:487`) renders the full 3-agent mitigation output including
  `viable`/`days_recovered`/`cost_premium_pct`/`summary`.
- `frontend/app/supply-chain/page.tsx` renders `root_cause`, `days_at_risk`,
  `cost_premium_pct` directly in the shipment cards (not hidden in tooltips).
- `frontend/app/timeline/page.tsx:159` states in-page: "Dataset is REPRESENTATIVE synthetic
  data" — an explicit UI disclosure, not just a doc-only caveat.
- No `fetch(` / hardcoded array literal was found directly inside the three page files —
  all three route through the shared `lib/api.ts` client, confirmed by grep.

## The 6 specific questions

**1. Is the CPM computation REAL?**
Yes, confirmed by source and live test. `schedule.py:_cpm()` (lines 62-102) builds a real
`networkx.DiGraph` from `schedule.csv`'s `predecessors` column, does a genuine topological
sort + forward pass (`es`/`ef`) + backward pass (`lf`/`ls`), and derives `float_days` /
`critical` from `ls[n] - es[n]`. `_project_impact()` (113-123) re-runs the *entire* forward
pass with a hypothetical slip added to one activity's duration and diffs the resulting
`project_finish` — this is why `project_impact_days` can legitimately be `0` even when
`predicted_slip_days > 0` (float absorbs it), which I observed live (e.g. `DC1-04-EL-020`:
`predicted_slip_days: 30`, `project_impact_days: 0`, float 197d).

Live proof via clock advance: `POST /api/clock/advance {"days":30}` (day 175→205) changed
`/api/schedule/risks` from 6 flagged activities to 11 — five *new* activities
(`DC1-03-AF-010/020/030`, `DC1-04-EL-010`, `DC1-04-ME-010`) started failing the progress-lag
rule purely because more elapsed time made their 0%-complete status look worse relative to
plan. This cannot happen from a static CSV/JSON lookup; it requires re-running `_expected_pct()`
against the new `clock.current_day()`. `POST /api/clock/reset` correctly restored the
original 6-item list. **Caveat**: `schedule.risks()` etc. are `@lru_cache(maxsize=1)`
(schedule.py:239) — without `clock._clear_downstream_caches()` (clock.py:44-52, called from
`set_offset()`) this would silently serve stale cached numbers after a clock change. I
verified that cache-clear call exists and is wired correctly, and the live test confirms it
actually fires.

**2. Are the 5 leading-indicator rules computed rules or a lookup table? Is Pongal reachable?**
All 5 are computed, not table lookups:
- Rule 1 (vendor slip): `schedule.py:164-172` — `predicted_slip = lead_time * 0.065` (or
  `0.10` for "late"), a formula over the row's `lead_time_days` field, not a static number.
- Rule 2 (progress lag): `schedule.py:174-178` — `behind = (expected - pct)/100 * duration_days`.
- Rule 3 (legacy monsoon proxy, June–Nov): `schedule.py:180-186`, flat `predicted_slip = 5`
  when in-window — this one IS a fixed constant (not a formula), documented as a deliberate
  "legacy, uncited" rule kept only because `eval/run_schedule_eval.py` asserts its exact
  behavior (comment at line 180-182).
- Rule 4 (cited IMD NE-monsoon window): `schedule_factors.py:126-146`, real overlap-day
  arithmetic (`monsoon_overlap_days`) × a documented productivity factor
  (`weather_predicted_slip`, 108-109).
- Rule 5 (Pongal workforce window): `schedule_factors.py:149-170`, same overlap-arithmetic
  shape (`labour_dip_overlap_days` / `labour_dip_slip`).

**Pongal is confirmed dormant on the bundled demo data**, and this is honestly self-reported
by the app, not hidden: live `GET /api/schedule/methodology` returned `"Not currently firing
— the only bundled activities whose window overlaps mid-January (early site-mobilisation
work) are already 100% complete"`. This matches the code guard `if pct < 100:` at
`schedule.py:201` before calling `workforce_driver()`. It is real, tested code
(`eval/run_workforce_eval.py`, cited in comments and in `docs/features.md:217`), just not
reachable given the current schedule.csv's `pct_complete` values — a genuine, disclosed gap,
not a fabricated "5th rule" for marketing purposes.

**3. Supply chain: is delay propagation / root-cause / alternative-viability real arithmetic?**
Yes. `_milestones()` (`supply_chain.py:82-106`) scans a shipment's real milestone list for
the first `actual_day > planned_day`, computes `current_delay`, and projects every
not-yet-reached milestone forward by that delay — a real forward-propagation, not an
asserted "days_at_risk" field. `_root_cause()` (109-118) independently re-scans for the
*first* slipped milestone and labels it tier-1 vs tier-2 from the milestone's own `tier`
field — this is why SHP-001's root cause correctly reads "tier2 customs clearance slipped
55d (tier-2 sub-supplier)" even though the flagged risk is on the tier-1-facing procurement
line. `_alternatives()` (125-142) computes `arrival = clock.current_day() + lead_time_days`
and sets `viable = arrival <= required_on_site_by` — plain arithmetic against the CPM-derived
required date (`_required_on_site_by()`, 52-72, which itself walks the real schedule DAG for
a downstream "install" activity rather than using a hand-set date).

Data provenance: shipment/milestone data comes from a static JSON snapshot,
`backend/data/project_docs/supply_chain.json`, loaded via `data_loader.load_supply_chain()`
(`data_loader.py:111-115`). This is explicitly disclosed, not disguised as live tracking:
`GET /api/supply-chain/meta` states verbatim "a point-in-time demo dataset, not a live
carrier-tracking feed... the underlying data is REPRESENTATIVE synthetic input." The
*arithmetic* over that snapshot (propagation/root-cause/viability) is real; the *inputs*
(milestone actual/planned days) are fixture data, honestly labeled as such.

**4. Timeline: pure aggregation with no new judgment? Are evidence_links.py cross-links real?**
Confirmed pure aggregation. `timeline.py`'s `all_events()` (278-289) only concatenates
`_compliance_events()` + `_rfi_events()` + `_schedule_events()` + `_supply_chain_events()` +
`_commissioning_events()`, each of which pulls `day`/`severity`/`detail` straight from
another pillar's already-computed result (`evaluate()`, `schedule_risks()`, `sc_alerts()`,
etc.) with no independent scoring logic. The module docstring's claim "zero new fabricated
events... if a day genuinely can't be derived... the event is skipped" matches the code:
`_date_to_day()` (48-57) returns `None` on unparseable dates and every event-builder function
guards on that (`if day is None: continue/return []`).

`evidence_links.py` cross-links are real shared-key matches, not hardcoded pairs:
`link_rfi(wbs_id=...)` (48-81) does a literal substring match of the `wbs_id` against each
RFI's `Ref`/`Subject`/`Question` text (`"curated"` match), falling back to TF-IDF cosine
similarity (`"retrieved"` match, threshold `_SIM_THRESHOLD = 0.15`) only if no literal match
exists. `link_activity()` (84-96) does an exact `wbs_id` lookup against `load_schedule()`
rows plus the real CPM `critical` set. Live-verified: `SHP-002`'s `linked_rfi` correctly
resolved to `RFI-EL-112` with `"match": "curated"` — the RFI's own `Ref` text literally cites
"Schedule DC1-04-EL-030" (SHP-002's wbs_id), so this is a genuine text match, not an asserted
pairing. `timeline.py:258-275`'s `_link_pairs()` reuses these same `Shipment.linked_rfi` /
`.linked_activity` objects to wire Timeline's `linked_event_ids` — confirmed no second,
independent linking logic exists for Timeline.

**5. Cost-at-risk / ROI — which constants are ASSUMPTIONS, and are they labeled?**
See the Assumption constants table below. The formula and its live inputs
(`project_impact_days`, `cost_premium_pct`, open-NCR count) are real computed values (see Q1
and Q3); the ₹-per-unit and hours-per-unit multipliers are documented, hardcoded assumption
constants. They ARE labeled as assumptions in both source comments and API output
(`CostRiskComponent.basis` strings, `CostRisk.data_note`, `cost_basis.json`'s own `_note`
field), and partially surfaced in the UI via hover tooltips (`schedule/page.tsx:246,266,337`)
— but this labeling is tooltip-only, not always-visible text, so a judge skimming the
dashboard without hovering would see only the ₹ totals, not the "REPRESENTATIVE" caveat.

**6. Mitigation agents — genuinely 3 independent strategies, or one function with branches?**
Genuinely 3 separate functions with materially different logic and data sources, coordinated
by one dumb collector — not a single branching function dressed up as "3 agents":
- `_procurement_alternative_agent` (`mitigation.py:37-98`) — pulls from **Supply Chain's**
  shipment/alternative data (a cross-module dependency, lazily imported to avoid a circular
  import per the comment at lines 44-45), evaluates viable alternative suppliers by arrival
  date.
- `_resequencing_float_agent` (101-125) — reads the **CPM float** (`cpm["float"][wbs_id]`,
  i.e. `schedule.py`'s real `ls[n]-es[n]`), zero shared logic with the procurement agent.
- `_resource_recovery_agent` (128-176) — pure duration/remaining-time arithmetic
  (`overtime_pct_needed = predicted_slip_days / remaining * 100`) against a documented
  threshold constant (`_OVERTIME_RECOVERABLE_THRESHOLD_PCT = 30.0`, line 27), no shared logic
  with either of the other two.

`generate_mitigation_options()` (179-188) just calls all three and returns the list — "no
hidden ranking beyond each option's own numbers," confirmed by reading it (it's a 3-line
function). Live-verified on `DC1-04-EL-020`: the three options returned genuinely different
verdicts from genuinely different reasoning (procurement: viable, 5d via alt supplier @ +45%
cost; resequencing: viable, 30d via 197d of CPM float; resource_recovery: not viable, window
elapsed) — these numbers could not come from one branching function since they draw on three
disjoint data sources (supply_chain shipments, CPM float dict, schedule row duration/start).

## Assumption constants table

| Constant | Value | file:line | Labeled as assumption in UI? |
|---|---|---|---|
| `COMPLIANCE_HOURS_PER_ISSUE` | 20 h/issue | `impact.py:31` | Tooltip only (`basis` string, not always-visible) |
| `COMPLIANCE_REWORK_INR_PER_ISSUE` | ₹15,00,000/issue | `impact.py:32` | Tooltip only; also reused by `cost_risk.py` rework component |
| `SCHEDULE_HOURS_PER_FLAG` | 4 h/flag | `impact.py:41` | Tooltip only |
| `SCHEDULE_INR_PER_CRITICAL_DAY_AVOIDED` | ₹50,000/day | `impact.py:42` | Tooltip only |
| `SUPPLY_CHAIN_HOURS_PER_AT_RISK_SHIPMENT` | 6 h/shipment | `impact.py:49` | Tooltip only |
| `SUPPLY_CHAIN_INR_PER_DAY_AT_RISK_MITIGATED` | ₹75,000/day | `impact.py:50` | Tooltip only |
| `COMMISSIONING_HOURS_PER_FAIL` | 8 h/fail | `impact.py:56` | Tooltip only |
| `COMMISSIONING_INR_PER_FAIL` | ₹3,00,000/fail | `impact.py:57` | Tooltip only |
| `COMMISSIONING_HOURS_PER_WITHIN_ALLOWABLE` | 2 h | `impact.py:58` | Tooltip only |
| `COMMISSIONING_INR_PER_WITHIN_ALLOWABLE` | ₹0 | `impact.py:59` | Tooltip only |
| `daily_delay_rate_inr` | ₹3,50,000/day | `backend/data/project_docs/cost_basis.json` (loaded `cost_risk.py:99`) | Tooltip (`CostRiskComponent.basis`) + file's own `_note` field |
| `equipment_base_cost_inr` (per item, e.g. DRUPS ₹18cr, LV switchgear ₹4.5cr) | see JSON | same file | Tooltip only |
| `default_equipment_base_cost_inr` | ₹2,00,00,000 | same file | Tooltip only |
| `MONSOON_PRODUCTIVITY_FACTOR` | 0.75 (75% output retained) | `schedule_factors.py:40` | Surfaced via `/api/schedule/methodology`, driver text says "a planning-grade climatological window, not a forecast" — factor itself not spelled out in driver text |
| `_DEFAULT_WORKFORCE_AVAILABILITY_FACTOR` / `availability_factor` | 0.6 (60% availability during Pongal) | `schedule_factors.py:41`, `workforce_calendar.json` | Yes — driver text explicitly says "(REPRESENTATIVE assumption)" (`schedule_factors.py:168`) and methodology endpoint repeats it |
| `_OVERTIME_RECOVERABLE_THRESHOLD_PCT` | 30.0% (max realistic sustained overtime) | `mitigation.py:27` | Surfaced in mitigation option `detail` text on `/schedule` page (not tooltip-hidden — rendered inline) |
| Rule-1 vendor-slip factors | 0.065 ("slipping") / 0.10 ("late") of lead time | `schedule.py:168` | Not labeled as an assumption anywhere I found — no "documented/representative" language attached to these two specific numbers in driver text or docs |
| Rule-1 lead-time-advantage factor | 0.15 of lead time | `schedule.py:172` | Not labeled as an assumption in driver text |
| Rule-3 legacy monsoon flat slip | 5 days (flat, not a formula) | `schedule.py:186` | Not labeled as REPRESENTATIVE in driver text (comment calls it "legacy, uncited" in source only) |

Every dollar figure ultimately traces to a hand-set constant somewhere in this table — this
matches the project's own stated rule that ROI/cost figures are labeled assumptions, not
measurements. The labeling is real and present in source + API `basis`/`data_note`/`_note`
fields everywhere I checked. The gap is UI prominence: most of it is hover-tooltip-only on
the dashboard (`page.tsx`), so it is discoverable but not front-and-center; two of the
`schedule.py` Rule-1 constants (0.065/0.10/0.15) have no "assumption" language attached to
them anywhere, unlike the monsoon/workforce/overtime constants which are explicitly flagged.

## Stale-or-wrong claims found in `docs/features.md`

None found for this scope. Checked `docs/features.md` lines 62-86 and 206-227 (Schedule,
Timeline, Supply Chain sections + eval descriptions) against live behavior and source:
- "5 leading-indicator rules: slipping vendor, progress lag, legacy monsoon proxy, cited IMD
  monsoon window, cited Pongal ... window" (line 68-69) — matches code exactly (schedule.py
  Rules 1-5).
- "`GET /api/timeline` — pure aggregation of the other 4 pillars' own outputs" (line 79) —
  confirmed accurate (Q4 above); it's actually 5 event sources (compliance, copilot/RFI,
  schedule, supply_chain, commissioning) but "4 pillars" plausibly excludes Timeline counting
  itself — not a material discrepancy.
- Eval descriptions (lines 209-227) for `run_supply_chain_eval.py`, `run_schedule_eval.py`,
  `run_weather_eval.py`, `run_workforce_eval.py`, `run_mitigation_eval.py`,
  `run_timeline_eval.py`, `run_cost_risk_eval.py` all match what the corresponding source
  modules actually implement — I did not re-run the eval scripts themselves (out of scope for
  this pass; flagging as UNVERIFIED below) but the *claims about what each module computes*
  check out against source.
- Clock-advance description (line 286-287: "clears every downstream `lru_cache` on advance so
  schedule/supply-chain/timeline numbers recompute live") — confirmed true and reproduced
  live in this audit.

## UNVERIFIED

- Did not re-execute `eval/run_schedule_eval.py`, `run_weather_eval.py`,
  `run_workforce_eval.py`, `run_mitigation_eval.py`, `run_timeline_eval.py`,
  `run_cost_risk_eval.py`, `run_supply_chain_eval.py`, or `run_impact_eval.py` — I read their
  target modules and confirmed the claimed behavior exists in source, but did not confirm the
  eval scripts currently pass or that their pass-count claims elsewhere in `docs/` (e.g.
  README) are current.
- Did not check whether `/api/overview` (which is what actually exposes `impact.py`'s
  `all_pillar_impacts()` output per `docs/features.md:18`) is wired correctly — that route
  lives in `overview.py`, outside this agent's explicit file scope; I traced the import
  (`cost_risk.py:38` imports `from .overview import _evaluate_all`) but did not fully audit
  `overview.py`.
- Did not check `frontend/app/page.tsx`'s exact rendering of the ROI/impact ticker (only
  grepped for `data_note`/`basis`/`CostRisk`) — confirmed those fields are referenced there
  but did not visually inspect the rendered dashboard.
- Did not test extreme/edge clock values (e.g. `days: -1000` or the documented 60-day cap
  behavior) beyond the standard `+30` used to prove recomputation; `set_offset()`'s clamp
  (`max(0, min(MAX_OFFSET_DAYS, days))`, `clock.py:44`) was read but not live-tested at the
  boundary.
- Equipment-spec compliance (`_equipment_spec_check`, IS 8623-1 subset) returns `[]` live
  because no bundled shipment currently has a `declared_spec` mismatch — I did not construct
  a synthetic MISMATCH case to prove the check fires; I verified the logic by reading
  `supply_chain.py:160-201` only.
