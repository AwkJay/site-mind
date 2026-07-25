# Business impact — anchored to the brief's own cited figures

This connects SiteMind's real, computed numbers to the two figures the brief itself cites (JLL 2025 India
Data Centre Report; 2024 Turner & Townsend APAC survey) — without inventing a project-level $ projection
neither number supports. Per `.claude/CLAUDE.md`'s integrity rules, nothing below is asserted; every number
either comes from a real computed run (`GET /api/overview`, `backend/eval/*.py`) or is explicitly labeled
an assumption with its value stated.

## The brief's own numbers (context, not ours to claim credit for)

- India DC capacity: ~900 MW (2024) → 2,700+ MW (2027), $15B+ capital deployment.
- 67% of APAC data-centre EPC projects saw schedule overruns exceeding 10% (Turner & Townsend, 2024).
- **Leading causes named in the brief: procurement misalignment and commissioning failures.**

That last line matters more than the headline numbers — it's the brief telling us where the money is lost.
SiteMind's five pillars map directly onto those named causes, not onto a generic "AI dashboard" pitch:

| Brief's named cause | SiteMind pillar | What it actually does about it |
|---|---|---|
| Spec/quality deviations reaching site | Compliance Agent | Catches them before casting/procurement approval, cited to a real IS clause |
| **Procurement misalignment** | Supply Chain Visibility | Multi-tier shipment tracking + root-cause attribution + real alternative-supplier arithmetic — the exact failure mode named in the brief |
| **Commissioning failures** | Commissioning QA Copilot | Deterministic PASS/allowable/FAIL against a cited thermal envelope, generating real NCRs (cooling-only slice built; electrical/fire deferred — see `docs/ARCHITECTURE.md`) |
| Schedule risk generally | Predictive Schedule Risk | CPM + leading-indicator rules, with a measured lead-time-of-warning |
| Fragmented project knowledge | Project/RFI Copilot | Cited RAG + seen-before-RFI detection, closing the "information fragmentation" gap the brief opens with |

## Real, computed numbers from this project (not projections)

As of the current demo state (`GET /api/overview`, reproducible by running it):
- **6 non-conformances caught** on the one Design Basis Report currently checked, all cited to a real IS
  clause, 0 hallucinated citations (`backend/eval/report.json`).
- **6 schedule activities flagged at-risk** (re-verified live, `GET /api/schedule/risks`), with a computed
  advance-warning lead time per activity (`detected_lead_time_days`) — not asserted, derived from
  `lead_time_days × 0.15` for the vendor-slip rule (see `backend/app/schedule.py` for the exact, inspectable
  formula).
- **2 of 6 tracked shipments flagged at-risk** in the Supply Chain pillar (re-verified live, `GET
  /api/supply-chain/risks`), each with a real root-cause attribution (naming the specific supplier tier and
  milestone that slipped) and a genuinely viable alternative supplier at a stated cost premium — or an
  honest "no viable alternative, escalate" when that's what the arithmetic says.
- **21 eval scripts** — **18 distinct harnesses** in `backend/eval/`, plus **3 more** in the standalone
  Codebook service's own `standards-service/eval/` (2 of which repoint near-duplicate logic at the
  relocated corpus rather than testing something new — the third, `run_codebook_tools_eval.py`, is the
  genuinely distinct one, driving the live MCP protocol). All 21 pass, never blended into one score — see
  `sitemind/docs/features.md` for a per-script breakdown and `sitemind/PROGRESS.md` for the exact numbers
  and how to reproduce them.

## Unit economics (labeled assumptions — defend these as estimates, not measurements)

`backend/app/overview.py` computes the ROI ticker from two explicit, documented constants:
- **~20 engineer-hours saved per issue caught early** (manual cross-checking a submittal against the code +
  writing the NCR by hand) — a round, conservative estimate, not a time-motion study result.
- **~₹15 lakh (≈ $18K) average rework/avoidance cost per structural/durability non-conformance caught
  before casting** — again a stated estimate, not a measured figure from a real project.

These are unit economics, not a project-level total: multiplying them out to a full hyperscale project (the
brief's own scale — 15,000–40,000 equipment line items, up to 200 concurrent trade contractors) would
require assuming how many of those line items are structural-compliance-checkable and how many
non-conformances a real project surfaces — SiteMind has no real project's data to base that assumption on,
so this document deliberately stops short of projecting one. The honest claim is: **the per-issue and
per-shipment mechanics are real and computed; the aggregate at project scale is for the audience to reason
about themselves, not for us to assert.**

## Illustrative scenario band (sensitivity, not a forecast)

Refusing to project a number outsources the multiplication to the audience — which is honest, but it also
means the room does no reasoning *with* you. This band still isn't a forecast; it's the same real per-issue
constants above, run against a stated, clearly-labeled assumption instead of left undone:

> **IF** a project at the brief's own stated scale (15,000–40,000 equipment line items, up to 200 concurrent
> trade contractors) surfaces **50–200 catchable non-conformances** [assumption — not measured, not derived
> from any real project's data; picked as a round, defensible-sounding range for illustration only], **THEN**
> the unit economics above imply:
> - **1,000–4,000 engineer-hours** saved (50–200 × ~20h/issue)
> - **₹7.5–30 Cr rework exposure avoided** (50–200 × ~₹15L/issue)

State the assumption out loud every time this band is shown — it is the one input that makes the range move,
and it is the one input nobody in the room, including SiteMind, has real data to pin down yet.

## The lead-time-vs-actual-delays gap, stated head-on

The brief's own evaluation-focus line asks for "schedule risk prediction lead time versus actual delays" —
that is a backtest question, and SiteMind cannot answer it: there is no real historical project with actual
outcomes to compare a prediction against. Here is exactly what we CAN and do prove, and exactly what closes
the gap:
- **Provable today:** the CPM critical-path recomputation is real (`backend/app/schedule.py`), the
  leading-indicator rules are real and eval'd (`run_schedule_eval.py`, `run_weather_eval.py`,
  `run_workforce_eval.py`), and `detected_lead_time_days = lead_time_days × 0.15` is a real, inspectable
  formula for the vendor-slip rule specifically — not a backtested measurement.
- **What a 90-day pilot on one live project would measure:** for every activity SiteMind flags at-risk, log
  the warning date the tool produced and the actual slip date the project later recorded, then compute the
  real lead time (warning date to actual slip date) across enough activities to report a distribution, not
  a point estimate. That is the concrete, fundable next step that turns this from an assumption into data.

Owning this gap in writing, with the pilot design attached, reads as maturity — walking past it silently is
what reads as a hole.

## Who pays

Per-project SaaS license to the EPC contractor or owner's-engineer, priced per active project rather than
per seat — one avoided rework event at the ~₹15L average stated above already covers a meaningful share of
a year's licensing on its own. This is a business-model sentence, not a priced offer; treat it as a starting
point for the conversation, not a number to defend line-by-line.

## What this means for the pitch

Lead with the causal mapping (procurement misalignment → Supply Chain pillar, commissioning failures →
Commissioning QA pillar) — it demonstrates the product was built *against the brief's own diagnosis*, not a
generic feature list. Follow with the real computed numbers above. Do not state a project-level $ or %
improvement figure as a *claim* — the illustrative scenario band above exists so you don't have to leave the
room to do its own unguided multiplication, but present it labeled exactly as what it is (a sensitivity band
on a stated assumption), never as a projection. If pressed further, give the raw unit economics and the
assumption behind the band, and let the questioner substitute their own project's real line-item count.
