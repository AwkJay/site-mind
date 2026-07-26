"""Pre-demo cache-warming script — run this manually before rehearsing/pitching.

Runs the demo path end-to-end EXACTLY as a live audience would trigger it, so
every prompt the on-stage demo will hit gets a real response cached in
`backend/data/.llm_cache/` (see app/llm_cache.py) ahead of time. After a
successful warm run, the actual demo run should be almost entirely cache
HITs — zero network round-trips, immune to conference wifi, and not spending
any of the ~20-request/day Gemini free tier per repeated rehearsal.

This script makes REAL LLM calls (it is the one place in this repo that is
SUPPOSED to). It does NOT run automatically — nothing in main.py, run.sh, or
any startup hook imports or calls it. It is a deliberate, manually-invoked
pre-demo step:

    cd backend && source .venv/bin/activate && python scripts/warm_llm_cache.py

Safe to re-run any time (idempotent): prompts already cached are reported as
"already cached" and cost zero additional requests; only genuinely new
prompts (a changed clause, a new NCR, a new demo document) make a live call.

What it warms:
  1. Compliance — the pre-loaded Design Basis Report (the hero document),
     run through the exact same `agents.compliance.evaluate_with_params()`
     the real /api/compliance/check endpoint calls. This exercises every
     `_prose()` call (NCR finding/why/corrective_action) and, when
     COMPLIANCE_RULE_EXTRACTION is on, every `_extract_rule()` call too.
  2. Copilot — a representative set of questions that are NOT already
     answered by the deterministic fixture match (`_match_fixture`), so they
     fall through to a live `_online_answer()` call. Questions that DO match
     a fixture are skipped on purpose: the real demo serves those from the
     fixture and never touches the LLM for them (see agents/copilot.py).

Refuses to run (prints why, exits 1, makes zero calls) when OFFLINE_MODE is
True — there is nothing to warm without a configured provider, and this
script must never be the thing that flips OFFLINE_MODE's "no network calls"
guarantee.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/ on sys.path

from app import config, llm  # noqa: E402
from app.agents import compliance  # noqa: E402
from app.agents.copilot import answer as copilot_answer  # noqa: E402
from app.agents.copilot import _match_fixture  # noqa: E402
from app.data_loader import load_submittals  # noqa: E402


# Questions chosen to plausibly miss every _SLUG_KEYWORDS entry in
# agents/copilot.py, so they exercise a genuine live `_online_answer()` call
# instead of being served by the fixture (which the real demo would use too,
# so warming those would be pointless — see module docstring).
_COPILOT_WARM_QUESTIONS = [
    "What is the current status of the electrical commissioning package?",
    "Summarize the outstanding items on the supply chain for the chiller plant.",
    "What schedule risk is the project currently carrying?",
]


def _dbr_document_id() -> str | None:
    """Same DBR-detection rule as data_loader.load_submittal_params — the
    hero document is whichever pre-loaded submittal is the Design Basis
    Report, not a hardcoded id, so this script keeps working if the demo
    dataset is regenerated."""
    for s in load_submittals():
        sid = (s.get("Submittal No") or "").lower()
        title = (s.get("Title") or "").lower()
        if "dbr" in sid or "design basis" in title:
            return s.get("Submittal No")
    return None


def _warm_compliance(before: dict) -> None:
    doc_id = _dbr_document_id()
    if not doc_id:
        print("  [compliance] SKIPPED — no Design Basis Report found in the pre-loaded submittals.")
        return
    print(f"  [compliance] Running evaluate_with_params({doc_id!r}) …")
    try:
        result, _ = compliance.evaluate_with_params(doc_id)
    except Exception as e:  # pragma: no cover - warming must never crash on a bad doc
        print(f"  [compliance] FAILED — {e!r}")
        return
    after = llm.get_stats()
    print(
        f"  [compliance] {len(result.ncrs)} NCR(s) evaluated for {doc_id}. "
        f"live calls so far: {after['live_calls'] - before['live_calls']}, "
        f"cache hits so far: {after['cache_hits'] - before['cache_hits']}"
    )


def _warm_copilot() -> tuple[int, int, int]:
    """Returns (warmed, already_cached, failed) — counted per question by
    diffing app.llm's live/cache-hit/error counters around each call."""
    warmed = already_cached = failed = 0
    for q in _COPILOT_WARM_QUESTIONS:
        if _match_fixture(q) is not None:
            print(f"  [copilot] SKIPPED (answered by fixture, not the LLM, in the real demo): {q!r}")
            continue
        before = llm.get_stats()
        try:
            copilot_answer(q)
        except Exception as e:  # pragma: no cover
            print(f"  [copilot] FAILED — {q!r} — {e!r}")
            failed += 1
            continue
        after = llm.get_stats()
        if after["live_calls"] > before["live_calls"]:
            warmed += 1
            print(f"  [copilot] warmed (live call made, now cached): {q!r}")
        elif after["cache_hits"] > before["cache_hits"]:
            already_cached += 1
            print(f"  [copilot] already cached: {q!r}")
        elif after["errors"] > before["errors"] or after["cache_fallbacks_after_error"] > before["cache_fallbacks_after_error"]:
            failed += 1
            print(f"  [copilot] LIVE CALL FAILED: {q!r}")
        else:
            print(f"  [copilot] no LLM call made (empty retrieval / abstained): {q!r}")
    return warmed, already_cached, failed


def main() -> int:
    print("=" * 72)
    print("SiteMind — LLM cache warm-up")
    print("=" * 72)
    print(f"provider={config.LLM_PROVIDER}  offline_mode={config.OFFLINE_MODE}")

    if config.OFFLINE_MODE:
        print(
            "\nOFFLINE_MODE is True (no usable LLM provider configured) — nothing to warm.\n"
            "Set LLM_PROVIDER=gemini and GEMINI_API_KEY in backend/.env, then re-run."
        )
        return 1

    print(
        "\nThis will make REAL calls to the configured LLM provider for every prompt "
        "not already cached. Re-running later is safe and cheap (already-cached "
        "prompts cost nothing).\n"
    )

    start = llm.get_stats()

    print("\n[1/2] Compliance — hero document")
    _warm_compliance(start)

    print("\n[2/2] Copilot — representative unseen questions")
    cp_warmed, cp_cached, cp_failed = _warm_copilot()

    end = llm.get_stats()
    live_total = end["live_calls"] - start["live_calls"]
    hits_total = end["cache_hits"] - start["cache_hits"]
    fallback_total = end["cache_fallbacks_after_error"] - start["cache_fallbacks_after_error"]
    error_total = end["errors"] - start["errors"]

    print("\n" + "=" * 72)
    print("Warm-up summary")
    print("=" * 72)
    print(f"  New prompts warmed (live call, now cached): {live_total}")
    print(f"  Prompts already cached (no call made):      {hits_total}")
    print(f"  Failed live calls with no cache fallback:   {error_total}")
    print(f"  Failed live calls served from an OLD cache: {fallback_total}")
    print(f"  (copilot breakdown — warmed={cp_warmed} cached={cp_cached} failed={cp_failed})")
    print(f"\nCache directory: {config.DATA_DIR / '.llm_cache'}")

    if error_total > 0:
        print("\nWARNING: one or more prompts failed with no cache fallback available — "
              "check provider auth / quota before the demo.")
        return 1

    print("\nDone. The demo path should now be served from cache.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
