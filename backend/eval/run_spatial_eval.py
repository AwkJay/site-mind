"""SiteMind SPATIAL COMPLIANCE rule-decision evaluation — reported SEPARATELY
from every other eval in this project (structural `run_eval.py`, electrical
`run_electrical_eval.py`, etc.), never blended into any of their numbers. Same
discipline as `run_electrical_eval.py`: this isolates `app/agents/
checks_spatial.py`'s deterministic threshold arithmetic + citation grounding,
built from labelled cases at and around each of the 6 checks' boundaries (spec
§8, `docs/superpowers/specs/2026-07-25-spatial-compliance-design.md`).

Why cases are hand-built flat param dicts (not full-document regex
extraction), mirroring `run_electrical_eval.py`'s pattern exactly rather than
`test_spatial_api.py`'s end-to-end style:
  * The values, units and structure are IDENTICAL to what `spatial/params.py::
    to_params()` actually emits — this is the real input shape
    `checks_spatial.py` consumes in production, not a simplification.
  * `Room.occupancy_group` has NO regex extraction path anywhere in
    `spatial/extract.py` today (the demo document never states one — see its
    Note 10, and `docs/gaps.md`). EGRESS_EXIT_WIDTH genuinely cannot reach a
    PASS/FAIL verdict through the live extractor; testing its boundary
    arithmetic at all requires supplying `occupancy_group`/`occupant_load`
    directly, exactly as `tests/test_checks_spatial.py` already does. This is
    disclosed here, not hidden.
  * The full-document, real-extractor path (demo doc -> regex extraction ->
    layout -> checks) is already covered by `tests/test_spatial_api.py`'s
    end-to-end test and is not re-measured here — this eval is the
    "boundary arithmetic + citation grounding" layer, same scope as
    `run_electrical_eval.py`.

Three-way decision space per case: PASS / FAIL / ABSTAIN / NOT_APPLICABLE.
  * NOT_APPLICABLE: the check's `applies_when` does not even match this
    param (e.g. front-clearance check offered a `crac` instead of a
    switchboard/lv_panel).
  * ABSTAIN: `applies_when` matched but `rule()` returned `None` — a required
    companion value is missing, or its provenance isn't "stated", or (for the
    two occupancy-aware checks) the value falls in the genuinely ambiguous
    band between NBC's strictest and most permissive limits.
  * PASS / FAIL: `rule()` returned a concrete bool.
Decision accuracy is an EXACT match against the gold label — abstaining when
the gold label is PASS or FAIL is scored WRONG, not partial credit. A
strategy that abstains on every case is simulated below and reported
alongside the real score specifically so that property is falsifiable, not
asserted.

Citation-hallucination rate: for every case whose gold-consistent verdict is
FAIL (the only verdict that actually emits an NCR citation in production —
see `agents/floor_plan.py::_run_spatial_checks`), the check's `clause_key` is
resolved via `app.standards.get_clause()` (must not be None) AND its
`.text` is cross-checked against an INDEPENDENT re-read of
`spatial_clauses.json` (not `get_clause`'s own cache) for the same key, so a
bug in the loader itself could not silently hide a mismatch.

Run:  python -m eval.run_spatial_eval   (from backend/, venv active)
      -> writes eval/spatial_report.json

Reported on its own. NEVER blended into run_eval.py's or run_electrical_eval.
py's accuracy/hallucination numbers.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/ on path

from app.agents.checks_spatial import CHECKS_SPATIAL, applicable_checks_spatial  # noqa: E402
from app.standards import get_clause  # noqa: E402
from app.config import DATA_DIR  # noqa: E402

HERE = Path(__file__).resolve().parent
_SPATIAL_CLAUSES_PATH = DATA_DIR / "standards" / "spatial_clauses.json"


def _param(**kw) -> dict:
    """Same flat shape `spatial/params.py::to_params()` emits. Any field a
    case doesn't need simply isn't set (checks read with `.get()`, exactly
    like `checks_spatial.py` itself assumes)."""
    base = {
        "provenance": "stated",
        "room_id": "room_1",
        "room_zone": "electrical",
        "equipment_kind": None,
        "occupancy_group": None,
        "occupant_load": None,
        "occupant_load_provenance": None,
        "unit": "m",
        "source_quote": "synthetic eval case — not drawn from any real document sentence.",
    }
    base.update(kw)
    return base


# --------------------------------------------------------------------------- #
# Cases: (case_id, param_dict, gold_label) — gold_label in
# {"PASS", "FAIL", "ABSTAIN", "NOT_APPLICABLE"}.
# --------------------------------------------------------------------------- #
CASES: list[tuple[str, dict, str]] = []


def add(case_id: str, param: dict, gold: str) -> None:
    CASES.append((case_id, param, gold))


# --- SWBD_FRONT_CLEARANCE (>= 1.0 m, CEA 37(iii)(a)) ------------------------ #
add("front-fail-0.99", _param(param="front_clearance", value=0.99, equipment_kind="lv_panel"), "FAIL")
add("front-pass-1.00-boundary", _param(param="front_clearance", value=1.00, equipment_kind="lv_panel"), "PASS")
add("front-pass-1.01", _param(param="front_clearance", value=1.01, equipment_kind="switchboard"), "PASS")
add("front-pass-well-over", _param(param="front_clearance", value=1.50, equipment_kind="lv_panel"), "PASS")
add("front-fail-well-under", _param(param="front_clearance", value=0.40, equipment_kind="lv_panel"), "FAIL")
add(
    "front-abstain-inferred-provenance",
    _param(param="front_clearance", value=0.5, equipment_kind="lv_panel", provenance="inferred"),
    "ABSTAIN",
)
add(
    "front-not-applicable-wrong-equipment",
    _param(param="front_clearance", value=0.2, equipment_kind="crac"),
    "NOT_APPLICABLE",
)

# --- SWBD_REAR_CLEARANCE (< 0.20 m or > 0.75 m, CEA 37(iii)(b)) ------------- #
add("rear-pass-0.19", _param(param="rear_clearance", value=0.19, equipment_kind="lv_panel"), "PASS")
add("rear-fail-0.20-boundary", _param(param="rear_clearance", value=0.20, equipment_kind="lv_panel"), "FAIL")
add("rear-fail-0.75-boundary", _param(param="rear_clearance", value=0.75, equipment_kind="lv_panel"), "FAIL")
add("rear-pass-0.76", _param(param="rear_clearance", value=0.76, equipment_kind="switchboard"), "PASS")
add("rear-fail-midband-0.45", _param(param="rear_clearance", value=0.45, equipment_kind="lv_panel"), "FAIL")
add(
    "rear-abstain-inferred-provenance",
    _param(param="rear_clearance", value=0.9, equipment_kind="lv_panel", provenance="inferred"),
    "ABSTAIN",
)
add(
    "rear-not-applicable-wrong-equipment",
    _param(param="rear_clearance", value=0.5, equipment_kind="genset"),
    "NOT_APPLICABLE",
)

# --- SWBD_REAR_PASSAGE (>= 1.8 m, only when rear_clearance > 0.75 m, CEA
# 37(iii)(c)) — `_rear_clearance_m` is the cross-referenced companion value
# `agents/floor_plan.py::annotate_rear_clearance` stamps onto each row in
# production; supplied directly here for the same reason `occupancy_group`
# is above. ------------------------------------------------------------------ #
add(
    "passage-fail-1.79",
    _param(param="rear_passage_height", value=1.79, equipment_kind="lv_panel", _rear_clearance_m=0.9),
    "FAIL",
)
add(
    "passage-pass-1.80-boundary",
    _param(param="rear_passage_height", value=1.80, equipment_kind="lv_panel", _rear_clearance_m=0.9),
    "PASS",
)
add(
    "passage-pass-1.81",
    _param(param="rear_passage_height", value=1.81, equipment_kind="switchboard", _rear_clearance_m=2.0),
    "PASS",
)
add(
    "passage-abstain-rear-clearance-unknown",
    _param(param="rear_passage_height", value=2.1, equipment_kind="lv_panel", _rear_clearance_m=None),
    "ABSTAIN",
)
add(
    "passage-abstain-inferred-provenance",
    _param(
        param="rear_passage_height",
        value=2.1,
        equipment_kind="lv_panel",
        _rear_clearance_m=0.9,
        provenance="inferred",
    ),
    "ABSTAIN",
)
add(
    "passage-not-applicable-rear-clearance-under-threshold",
    # A KNOWN rear space <= 75 cm means 37(iii)(c) genuinely does not govern
    # this equipment at all (see checks_spatial.py's applies_when docstring).
    _param(param="rear_passage_height", value=1.0, equipment_kind="lv_panel", _rear_clearance_m=0.5),
    "NOT_APPLICABLE",
)

# --- EGRESS_DEAD_END (<= 6 m strict groups / <= 15 m others, NBC 4.4.2.2(c))
# `Room.occupancy_group` has no extraction path in this build (see module
# docstring), so an unstated group exercises the tri-state
# determinate-regardless-of-group logic; a stated group is also covered. ---- #
add("deadend-pass-well-under-5", _param(param="dead_end_corridor", value=5.0), "PASS")
add("deadend-pass-strict-boundary-6.0", _param(param="dead_end_corridor", value=6.0), "PASS")
add("deadend-abstain-just-over-strict-6.01", _param(param="dead_end_corridor", value=6.01), "ABSTAIN")
add("deadend-abstain-ambiguous-10", _param(param="dead_end_corridor", value=10.0), "ABSTAIN")
add("deadend-abstain-loose-boundary-15.0", _param(param="dead_end_corridor", value=15.0), "ABSTAIN")
add("deadend-fail-just-over-loose-15.01", _param(param="dead_end_corridor", value=15.01), "FAIL")
add("deadend-fail-well-over-16", _param(param="dead_end_corridor", value=16.0), "FAIL")
add(
    "deadend-pass-with-stated-group-institutional",
    _param(param="dead_end_corridor", value=5.0, occupancy_group="institutional"),
    "PASS",
)
add(
    "deadend-fail-with-stated-group-institutional",
    _param(param="dead_end_corridor", value=10.0, occupancy_group="institutional"),
    "FAIL",
)
add(
    "deadend-pass-with-stated-group-industrial",
    _param(param="dead_end_corridor", value=10.0, occupancy_group="industrial"),
    "PASS",
)
add(
    "deadend-abstain-inferred-provenance",
    _param(param="dead_end_corridor", value=5.0, provenance="inferred"),
    "ABSTAIN",
)

# --- EGRESS_TRAVEL_DISTANCE (<= Table 5 limit, NBC 4.4.2.2(a)) — same
# determinate-regardless-of-group logic against Table 5's overall bounds
# (lo=22.5 m, hi=45.0 m, computed from nbc_tables.json — see
# `checks_spatial.py::_table5_numeric_values`). --------------------------- #
add("travel-pass-well-under-20", _param(param="travel_distance", value=20.0), "PASS")
add("travel-pass-strict-boundary-22.5", _param(param="travel_distance", value=22.5), "PASS")
add("travel-abstain-just-over-strict-22.51", _param(param="travel_distance", value=22.51), "ABSTAIN")
add("travel-abstain-ambiguous-30", _param(param="travel_distance", value=30.0), "ABSTAIN")
add("travel-abstain-loose-boundary-45.0", _param(param="travel_distance", value=45.0), "ABSTAIN")
add("travel-fail-just-over-loose-45.01", _param(param="travel_distance", value=45.01), "FAIL")
add("travel-fail-well-over-50", _param(param="travel_distance", value=50.0), "FAIL")
add(
    "travel-pass-with-stated-group-residential",
    _param(param="travel_distance", value=29.0, occupancy_group="residential"),
    "PASS",
)
add(
    "travel-fail-with-stated-group-residential",
    _param(param="travel_distance", value=31.0, occupancy_group="residential"),
    "FAIL",
)
add(
    "travel-abstain-unresolvable-group-industrial",
    # "industrial" splits into g1_g2 / g3 sub-groups in Table 5 — no single
    # figure exists for the bare group name, so this abstains even though a
    # group IS stated (see _travel_distance_limit_m's docstring).
    _param(param="travel_distance", value=30.0, occupancy_group="industrial"),
    "ABSTAIN",
)
add(
    "travel-abstain-inferred-provenance",
    _param(param="travel_distance", value=20.0, provenance="inferred"),
    "ABSTAIN",
)

# --- EGRESS_EXIT_WIDTH (>= occupant_load x Table 4 mm/person, NBC 4.4.2.3)
# institutional's level_components_and_ramps factor = 13 mm/person
# (nbc_tables.json table_4.institutional). occupant_load=100 -> required =
# 1300 mm. --------------------------------------------------------------- #
add(
    "exitwidth-fail-1299",
    _param(
        param="exit_width", unit="mm", value=1299,
        occupancy_group="institutional", occupant_load=100, occupant_load_provenance="stated",
    ),
    "FAIL",
)
add(
    "exitwidth-pass-1300-boundary",
    _param(
        param="exit_width", unit="mm", value=1300,
        occupancy_group="institutional", occupant_load=100, occupant_load_provenance="stated",
    ),
    "PASS",
)
add(
    "exitwidth-pass-1301",
    _param(
        param="exit_width", unit="mm", value=1301,
        occupancy_group="institutional", occupant_load=100, occupant_load_provenance="stated",
    ),
    "PASS",
)
add(
    "exitwidth-abstain-occupant-load-missing",
    _param(param="exit_width", unit="mm", value=1200, occupancy_group="institutional"),
    "ABSTAIN",
)
add(
    "exitwidth-abstain-occupant-load-not-stated",
    _param(
        param="exit_width", unit="mm", value=1200, occupancy_group="institutional",
        occupant_load=100, occupant_load_provenance="inferred",
    ),
    "ABSTAIN",
)
add(
    "exitwidth-abstain-group-missing",
    _param(param="exit_width", unit="mm", value=1200, occupant_load=100, occupant_load_provenance="stated"),
    "ABSTAIN",
)
add(
    "exitwidth-abstain-group-unresolvable",
    _param(
        param="exit_width", unit="mm", value=1200, occupancy_group="not_a_real_nbc_group",
        occupant_load=100, occupant_load_provenance="stated",
    ),
    "ABSTAIN",
)
add(
    "exitwidth-abstain-inferred-provenance",
    _param(
        param="exit_width", unit="mm", value=1200, occupancy_group="institutional",
        occupant_load=100, occupant_load_provenance="stated", provenance="inferred",
    ),
    "ABSTAIN",
)

LABELS = ("PASS", "FAIL", "ABSTAIN", "NOT_APPLICABLE")


# --------------------------------------------------------------------------- #
# Predict via the REAL check registry — same call `agents/floor_plan.py::
# _run_spatial_checks` makes (`applicable_checks_spatial` then `rule(p)`).
# --------------------------------------------------------------------------- #
def predict(param: dict) -> tuple[str, str | None]:
    """(gold-comparable label, clause_key emitted for a FAIL verdict or None)."""
    applied = applicable_checks_spatial(param)
    if not applied:
        return "NOT_APPLICABLE", None
    # Every case above is constructed to match exactly one check's
    # applies_when; assert that stays true rather than silently picking [0].
    assert len(applied) == 1, f"case matched {len(applied)} checks, expected exactly 1: {[c['id'] for c in applied]}"
    check = applied[0]
    verdict = check["rule"](param)
    if verdict is None:
        return "ABSTAIN", None
    if verdict is True:
        return "PASS", None
    return "FAIL", check["clause_key"]


def _load_spatial_clauses_independently() -> dict[str, dict]:
    """A SEPARATE read of spatial_clauses.json (not through app.standards'
    cached `_load()`), so the hallucination check is a true independent
    cross-check rather than comparing the loader against itself."""
    raw = json.loads(_SPATIAL_CLAUSES_PATH.read_text(encoding="utf-8"))
    return {c["key"]: c for c in raw.get("clauses", [])}


def main() -> None:
    independent_clauses = _load_spatial_clauses_independently()

    results = []
    n_correct = 0
    n_always_abstain_correct = 0  # sanity baseline — see module docstring

    citations_checked = 0
    citations_hallucinated: list[dict] = []

    should_abstain_hits = should_abstain_total = 0
    should_not_abstain_hits = should_not_abstain_total = 0

    for case_id, param, gold in CASES:
        got, clause_key = predict(param)
        ok = got == gold
        n_correct += int(ok)
        n_always_abstain_correct += int(gold == "ABSTAIN")  # what a blanket-abstain strategy would score

        if gold == "ABSTAIN":
            should_abstain_total += 1
            should_abstain_hits += int(got == "ABSTAIN")
        else:
            should_not_abstain_total += 1
            should_not_abstain_hits += int(got != "ABSTAIN")

        if got == "FAIL":
            citations_checked += 1
            citation = get_clause(clause_key)
            independent = independent_clauses.get(clause_key)
            resolves = citation is not None
            text_matches = resolves and independent is not None and citation.text == independent["text"]
            if not (resolves and text_matches):
                citations_hallucinated.append(
                    {"case": case_id, "clause_key": clause_key, "resolves": resolves, "text_matches": text_matches}
                )

        results.append({"case": case_id, "gold": gold, "got": got, "pass": ok, "clause_key": clause_key})

    n = len(CASES)
    accuracy = round(n_correct / n, 4)
    always_abstain_accuracy = round(n_always_abstain_correct / n, 4)
    hallucination_rate = (
        round(len(citations_hallucinated) / citations_checked, 4) if citations_checked else 0.0
    )
    abstention_recall = (
        round(should_abstain_hits / should_abstain_total, 4) if should_abstain_total else None
    )
    abstention_precision_complement = (  # rate of NOT wrongly abstaining when it should not
        round(should_not_abstain_hits / should_not_abstain_total, 4) if should_not_abstain_total else None
    )

    report = {
        "n_cases": n,
        "label_space": list(LABELS),
        "n_correct": n_correct,
        "accuracy": accuracy,
        "always_abstain_baseline_accuracy": always_abstain_accuracy,
        "citation_hallucination_rate": hallucination_rate,
        "citations_checked": citations_checked,
        "citations_hallucinated": citations_hallucinated,
        "abstention_correctness": {
            "should_abstain_total": should_abstain_total,
            "should_abstain_and_did": should_abstain_hits,
            "recall": abstention_recall,
            "should_not_abstain_total": should_not_abstain_total,
            "should_not_abstain_and_didnt": should_not_abstain_hits,
            "correct_non_abstention_rate": abstention_precision_complement,
            "note": "recall = of cases that SHOULD abstain, fraction that DID abstain. "
            "correct_non_abstention_rate = of cases that should NOT abstain (a real PASS or "
            "FAIL), fraction where the system reached that verdict instead of abstaining. "
            "Both must be reported together — abstaining on everything scores recall=1.0 but "
            "correct_non_abstention_rate=0.0, which is why decision `accuracy` above (exact "
            "3-way label match) is the headline, not this pair alone.",
        },
        "results": results,
        "method": "Boundary-value cases against the REAL check registry (app/agents/"
        "checks_spatial.py), built as flat param dicts in the exact shape `spatial/params.py"
        "::to_params()` emits in production (same pattern as run_electrical_eval.py). Decision "
        "is deterministic Python; every FAIL's citation is resolved via app.standards.get_clause "
        "AND independently cross-checked against a separate read of spatial_clauses.json.",
        "limitation": "EGRESS_EXIT_WIDTH's PASS/FAIL cases supply occupancy_group/occupant_load "
        "directly because spatial/extract.py has no regex path that ever populates "
        "Room.occupancy_group (see docs/gaps.md) — the live regex extractor can only ever reach "
        "ABSTAIN for this check today, never PASS/FAIL. The full real-extractor end-to-end path "
        "(demo doc -> regex -> layout -> checks) is covered separately by "
        "tests/test_spatial_api.py::test_demo_doc_end_to_end, not re-measured here.",
        "headline": f"{hallucination_rate:.2f} citation-hallucination rate over {citations_checked} "
        f"emitted FAIL citations; {accuracy:.2%} 3-way decision accuracy over {n} boundary cases "
        f"(a blanket-abstain strategy would score {always_abstain_accuracy:.2%} on this same set, "
        "not 100%).",
    }

    out = HERE / "spatial_report.json"
    out.write_text(json.dumps(report, indent=2))

    print(f"n_cases={n}  n_correct={n_correct}  accuracy={accuracy}")
    print(f"always_abstain_baseline_accuracy={always_abstain_accuracy}")
    print(f"citation_hallucination_rate={hallucination_rate}  (checked={citations_checked})")
    print(
        f"abstention: recall={abstention_recall} (should-abstain caught) "
        f"correct_non_abstention_rate={abstention_precision_complement} (should-not-abstain not abstained)"
    )
    print(f"wrote {out}")

    if n_correct != n:
        print("\nFAILING CASES:")
        for r in results:
            if not r["pass"]:
                print(f"  {r['case']}: gold={r['gold']} got={r['got']}")

    # Sanity: every check id in the registry was exercised by at least one case.
    exercised_ids = {c["clause_key"] for c in [applicable_checks_spatial(p)[0] for _, p, _ in CASES if applicable_checks_spatial(p)]}
    all_ids = {c["clause_key"] for c in CHECKS_SPATIAL}
    missing = all_ids - exercised_ids
    if missing:
        print(f"\nWARNING: clause_keys never exercised by any case: {missing}")


if __name__ == "__main__":
    main()
