"""Parity eval for the Actian VectorAI DB vector-store backend (plan §C).

This is deliberately NOT blended with `run_cross_corpus_eval.py` or any other
eval in this suite: those assert exact cosine scores / exact chunk ordering
against the numpy path, which an ANN backend can legitimately reorder on
near-ties. This eval instead proves the Actian path is *correct enough to
serve the live app*: for each known-answer query already hand-verified in
`run_cross_corpus_eval.py`, the Actian-backed corpus's top-hit `document_id`
must match the numpy-backed corpus's top-hit `document_id` (not float
equality), and a gibberish query must still abstain via the SAME
`RETRIEVAL_FLOOR` gate.

Requires a real, running Actian VectorAI DB container (`docker compose -f
docker-compose.actian.yml up -d`, gRPC on port 6574 by default) and
`actian-vectorai-client` installed (`uv pip install actian-vectorai-client` —
NOT in requirements.txt by default; see requirements.txt's own comment for
why). If Actian is unreachable, this eval does NOT silently fall back to
numpy-vs-numpy (that would trivially "pass" without proving anything) — it
fails loudly and writes a report saying so, so a missing container is never
mistaken for a working Actian path.

Run: `RETRIEVAL_VECTOR_STORE=actian python -m eval.run_actian_parity_eval`
(from `backend/`, venv active, container running). Writes
`backend/eval/actian_parity_report.json`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _THIS_DIR.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app import config  # noqa: E402
from app.retrieval import vector_store  # noqa: E402
from app.retrieval.filesystem_corpora import build_structural_standard_codes_corpus  # noqa: E402

REPORT_PATH = _THIS_DIR / "actian_parity_report.json"

# Same 2 manak known-answer queries as run_cross_corpus_eval.py's group (b),
# reused here on purpose — parity against an already-verified baseline, not a
# fresh set of assertions about what the "right" answer is.
_QUERIES = [
    (
        "What is the minimum nominal cover for footings under IS 456?",
        "is456_2000",
    ),
    (
        "What is the importance factor I for hospital buildings under IS 1893?",
        "is1893_part1_2016",
    ),
]
_GIBBERISH = "zzqx flibbertigibbet nonsense unrelated blorp banana spaceship"


def _check_actian_reachable() -> tuple[bool, str]:
    try:
        vector_store.actian_store(config.ACTIAN_URL)._connect()
        return True, ""
    except Exception as exc:
        return False, str(exc)


def main() -> None:
    reachable, reason = _check_actian_reachable()
    if not reachable:
        report = {
            "status": "actian_unreachable",
            "reason": reason,
            "note": (
                "Actian VectorAI DB was not reachable at "
                f"{config.ACTIAN_URL!r} — this eval does not fall back to "
                "numpy (that would trivially pass without proving anything). "
                "Start the container (docker compose -f docker-compose.actian.yml "
                "up -d) and ensure actian-vectorai-client is installed, then re-run."
            ),
            "n_cases": 0,
            "n_pass": 0,
            "accuracy": 0.0,
        }
        REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Actian unreachable at {config.ACTIAN_URL}: {reason}")
        print("Wrote actian_parity_report.json with status=actian_unreachable.")
        sys.exit(1)

    # Reference corpus: forced numpy, regardless of the process's own
    # RETRIEVAL_VECTOR_STORE — this is the known-good baseline.
    original_store = config.RETRIEVAL_VECTOR_STORE
    try:
        config.RETRIEVAL_VECTOR_STORE = "numpy"
        numpy_corpus = build_structural_standard_codes_corpus()

        config.RETRIEVAL_VECTOR_STORE = "actian"
        actian_corpus = build_structural_standard_codes_corpus()
    finally:
        config.RETRIEVAL_VECTOR_STORE = original_store

    cases: list[dict] = []
    for query_text, expected_doc_id in _QUERIES:
        numpy_hits = numpy_corpus.query(query_text, k=3)
        actian_hits = actian_corpus.query(query_text, k=3)
        cases.append(
            {
                "name": f"top_hit_doc_id_parity: {query_text[:50]!r}",
                "group": "known_answer_parity",
                "expected": numpy_hits[0]["document_id"] if numpy_hits else None,
                "actual": actian_hits[0]["document_id"] if actian_hits else None,
            }
        )
        cases.append(
            {
                "name": f"top_hit_matches_hand_verified_doc: {query_text[:50]!r}",
                "group": "known_answer_parity",
                "expected": expected_doc_id,
                "actual": actian_hits[0]["document_id"] if actian_hits else None,
            }
        )

    cases.append(
        {
            "name": "actian_gibberish_query_abstains",
            "group": "abstention",
            "expected": True,
            "actual": actian_corpus.query(_GIBBERISH, k=3) == [],
        }
    )

    for c in cases:
        c["pass"] = c["actual"] == c["expected"]

    n_cases = len(cases)
    n_pass = sum(1 for c in cases if c["pass"])
    report = {
        "status": "ran",
        "n_cases": n_cases,
        "n_pass": n_pass,
        "accuracy": round(n_pass / n_cases, 4) if n_cases else 0.0,
        "method": (
            "Actian VectorAI DB parity vs. the numpy reference path over the real "
            "structural_standard_codes corpus. Asserts top-hit document_id PARITY (not float "
            "cosine equality — an ANN backend may legitimately reorder near-ties), "
            "plus the same RETRIEVAL_FLOOR abstention gate on a gibberish query."
        ),
        "actian_url": config.ACTIAN_URL,
        "cases": cases,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"actian parity eval: {n_pass}/{n_cases} passed (accuracy={report['accuracy']})")
    for c in cases:
        status = "PASS" if c["pass"] else "FAIL"
        print(f"  [{status}] ({c['group']}) {c['name']}: expected={c['expected']!r} actual={c['actual']!r}")

    if n_pass != n_cases:
        sys.exit(1)


if __name__ == "__main__":
    main()
