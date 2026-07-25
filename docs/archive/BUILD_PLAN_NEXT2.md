# BUILD_PLAN_NEXT2.md — multi-agent mitigation + alerting + hybrid retrieval

> Written 2026-07-03, second build phase this session (after BUILD_PLAN_NEXT.md's
> impact/cost-risk/evidence-linking phase, which is DONE — see PROGRESS.md). Scoped
> with the user via direct Q&A (not a formal grill-me round this time). Self-contained:
> read this before touching code.

## Why this phase exists

The brief's Predictive Schedule Risk Engine bullet is the **only** place "multi-agent
system" is named specifically (not "agentic everywhere") — and it asks for
"generating mitigation options, not just alerts." Today `schedule.py`'s
`_mitigation()` returns exactly ONE templated sentence per risk. That's a real,
narrow, currently-unmet gap — not a stretch to manufacture agentic-ness.

Two more brief-named gaps, lower effort:
- Evaluation Focus: "supply chain visibility depth **and alerting timeliness**" —
  today everything is pull-only (visit the page); nothing is a discrete, timestamped
  alert.
- Suggested tech: "RAG over large technical document corpora" — Copilot has dense
  embedding retrieval only; hybrid (BM25 + dense, fused) is a legitimate, scoped
  upgrade, lowest priority of the three (Copilot already evals "Solid").

## Guardrails (same as always — reused, not re-derived)

Every new number/decision computed + eval-backed, own held-out eval, never blended
(evals go 10 → 13). Compliance baseline stays 10/6/4-. All prior evals stay green,
verified after every slice. `npm run build` clean after every slice.

## The multi-agent pattern — what makes this genuinely agentic, not agentic-washing

**Specialized agents + a coordinator**, each with ONE bounded real-data tool-call —
not an open-ended reasoning loop, not a framework dependency (LangGraph etc. would
add state/replanning machinery this bounded, parallel-checks task doesn't need).
This is different from the compliance/commissioning pass/fail decisions (which stay
plain deterministic Python, no agents) — mitigation-option generation is naturally
multiple-valid-answers, which is what makes it a legitimate fit for multiple
specialized checks + a coordinator, without reopening the hallucination risk (each
agent's output is a real computation, never free-form LLM reasoning). Update
`docs/ARCHITECTURE.md`'s "why not fully agentic" section to add this nuance: we ARE
agentic where the task is naturally multi-option and each option is grounded; we are
NOT agentic where the task is a verifiable yes/no against a cited standard.

## Slice 1 — Multi-agent mitigation options (Schedule pillar)

New `backend/app/agents/mitigation.py`. Three agents, run per flagged risk:

1. **`_procurement_alternative_agent(row, predicted_slip_days)`** — looks up
   whether this risk's `wbs_id` matches a Supply-Chain shipment
   (`supply_chain.shipments()`, **lazy-imported inside the function** to avoid a
   circular import with `schedule.py`) with a viable alternative. If yes: real
   supplier/lead-time/cost-premium numbers, `days_recovered` = how much of the slip
   the alternative's earlier arrival addresses. If no shipment or no viable
   alternative: `viable=False`, says so plainly (same honesty as Supply Chain's own
   "no viable alternative" case).
2. **`_resequencing_float_agent(wbs_id, predicted_slip_days, cpm)`** — reads the
   activity's OWN CPM float (`ls[wbs_id] - es[wbs_id]`, real numbers already
   computed by `_cpm()`). If float covers some/all of the predicted slip, reports
   exactly how many days are absorbed for free. Framed honestly as "existing
   schedule float," not an invented resequencing plan — deeper resequencing would
   need resource-loading data this project doesn't have.
3. **`_resource_recovery_agent(row, predicted_slip_days)`** — real arithmetic:
   `required_rate = (100 - pct_complete) / remaining_duration`,
   `baseline_rate = 100 / duration_days`,
   `overtime_pct_needed = (required_rate / baseline_rate - 1) * 100`. Viable only if
   `overtime_pct_needed` is under a documented threshold (30%); above that, reports
   the number and says it's not realistically recoverable via resourcing alone —
   never silently rounds down to "viable."

**Coordinator**: `generate_mitigation_options(row, predicted_slip_days, cpm) ->
list[MitigationOption]` just collects all three (including non-viable ones,
transparently) — no LLM synthesis, no hidden ranking logic beyond what's stated.

**Schema** (`schemas.py`): new `MitigationOption` (`agent`, `viable`,
`days_recovered`, `cost_premium_pct: Optional[float]`, `summary`, `detail`).
`RiskItem` gains `mitigation_options: list[MitigationOption] = []` — the EXISTING
`mitigation: str` field stays untouched (zero regression risk to the evaluated
`_mitigation()` logic or the frontend's current `r.mitigation` render).

**Frontend**: `/schedule` page renders `mitigation_options` as a small card row
under the existing mitigation line — one line per agent, viable ones highlighted,
non-viable ones shown greyed with their real reason.

**Eval #11**: `eval/run_mitigation_eval.py` — pure-function cases against each
agent with fixed synthetic inputs (viable/non-viable procurement, float-covers-all/
float-covers-partial/float-covers-none, overtime-under-threshold/over-threshold).

## Slice 2 — Supply-chain alerting

New `SupplyChainAlert` schema (`id`, `shipment_id`, `procurement_item`, `severity:
Literal["INFO","WARNING","CRITICAL"]`, `message`, `detected_at_day`, `days_at_risk`,
`on_critical_path`). Severity tiers: a documented, deterministic rule on
`days_at_risk`/`on_critical_path` (e.g. CRITICAL if on-critical-path OR
days_at_risk > 14; WARNING if 4-14; INFO if 1-3). `detected_at_day` = the real
milestone day the slip first became visible in the data (reuse `_root_cause`'s
first-slipped-milestone loop) — this is what "alerting timeliness" actually means
here: how early the system COULD have raised this, computed from real data, not a
push-notification claim. **Be explicit in code/docs this is an in-app alert log, not
an email/SMS/webhook channel** — no fake "notification sent" claim.

New `GET /api/supply-chain/alerts`. Frontend: an Alerts panel on `/supply-chain`
(chip-per-severity, sorted CRITICAL-first), reusing existing `Chip`/`Card`
primitives.

**Eval #12**: `eval/run_alerts_eval.py` — pure-function severity-tiering + 
detected_at_day cases against fixed synthetic milestone histories.

## Slice 3 — Hybrid retrieval for Copilot (lowest priority of the three)

Add `rank_bm25` to `requirements.txt`. New `_bm25_index()` in `agents/copilot.py`
(tokenize `_build_corpus()`'s texts, `BM25Okapi`). New `_hybrid_retrieve(question,
k)`: computes BM25 ranks + existing dense-embedding ranks over the SAME corpus,
fuses via Reciprocal Rank Fusion (`1/(60+rank+1)`, standard k=60), returns top-k by
fused score. **Critically: the existing abstention floor (`_RETRIEVAL_FLOOR = 0.40`,
eval-calibrated in `run_copilot_eval.py`) stays keyed to the DENSE top-1 similarity,
unchanged** — hybrid fusion only changes which chunks are SELECTED once the query
already cleared the existing, evaluated go/no-go gate. Never touch the floor itself
here; that eval must keep passing byte-for-byte.

**Eval #13**: `eval/run_hybrid_retrieval_eval.py` — pure RRF-fusion arithmetic on
synthetic rank lists (not the live corpus) — verifies the fusion formula, not
retrieval quality (retrieval QUALITY is already covered by the existing
`run_copilot_eval.py`, untouched).

## Execution

One driving chat, Slices 1→3, smallest-first (mitigation is the highest-value/most
build effort, do it first; alerting is cheap/medium value, second; hybrid retrieval
is lowest priority, third — could be dropped under time pressure without losing
anything already shipped). Verify full regression (all evals + 10/6/4 baseline)
after every slice. `/compact` at each slice seam if context runs long.

## Done when

- [ ] `RiskItem.mitigation_options` has 3 real agent outputs per flagged risk,
      `mitigation` (old field) unchanged/still populated.
- [ ] `eval/run_mitigation_eval.py` passes.
- [ ] `GET /api/supply-chain/alerts` returns real, severity-tiered, timestamped
      alerts; `/supply-chain` shows them.
- [ ] `eval/run_alerts_eval.py` passes.
- [ ] Copilot's retrieval uses BM25+dense RRF fusion for chunk selection; the
      EXISTING `run_copilot_eval.py` still passes with the SAME numbers (floor
      untouched).
- [ ] `eval/run_hybrid_retrieval_eval.py` passes.
- [ ] All 10 prior evals still pass; Compliance baseline still 10/6/4.
- [ ] `docs/ARCHITECTURE.md`'s agentic-position section updated with the nuance
      (agentic where naturally multi-option + grounded; not agentic for pass/fail).
- [ ] `npm run build` clean.
