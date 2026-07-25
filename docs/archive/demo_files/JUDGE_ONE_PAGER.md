# SiteMind — one page, 90 seconds

## The problem
India is building $15B of data-centre capacity by 2027. 67% of APAC data-centre EPC projects overrun
schedule by more than 10% — and the brief itself names the two leading causes: **procurement misalignment**
and **commissioning failures**. The intelligence to connect specs, RFIs, schedule, procurement, and quality
records across a project never gets built; it stays fragmented across disconnected systems.

## The thesis — the one sentence that matters
**The LLM never decides.** Every pass/fail in this system is a deterministic Python threshold evaluated
against a real, cited standard's clause text — the model only writes prose *after* the decision is already
made. That inversion is why a measured, published zero-hallucination-citation rate is even possible: a model
that never gets to decide can't quietly hallucinate a decision.

## Five pillars, one line each
1. **Compliance Agent** — extracts a design parameter with its exact source sentence, checks it against a
   real digitised IS clause, cites it, never guesses.
2. **Project/RFI Copilot** — cited hybrid retrieval Q&A over project documents, plus "this was asked before"
   detection.
3. **Predictive Schedule Risk** — CPM recomputation + leading-indicator rules, generating real mitigation
   options (not just alerts).
4. **Supply Chain Visibility** — multi-tier delay propagation, root-cause attribution, computed alternative-
   supplier viability — the brief's own named "procurement misalignment" cause, directly.
5. **Commissioning QA** — deterministic PASS/allowable/FAIL against a cited thermal envelope, real NCRs, an
   as-commissioned quality package (cooling-only slice; electrical/fire is a disclosed, deliberate gap).

## Three real numbers (all re-runnable, not typed in)
- **0% hallucinated citations**, 100% rule-decision accuracy vs a 58.5% naive baseline, n=41
  (`python -m eval.run_eval`, re-checked live via `GET /api/eval/report`).
- **21 eval scripts** — 18 distinct harnesses + 3 more in the standalone Codebook service — each scored
  separately, never blended into one number.
- **6 non-conformances caught** on the one Design Basis Report currently checked, every one cited to a real
  IS clause a judge can click open and read.

## The honesty model, one sentence
Every citation resolves to real, verbatim digitised standard text — never paraphrased from a model's memory
— and every number above is computed from a real formula over a disclosed, representative synthetic dataset,
never asserted; see `README.md`'s "What's REAL vs REPRESENTATIVE."

## Go deeper
Architecture diagram: `docs/ARCHITECTURE.md`. Full feature inventory: `docs/features.md`. Business case:
`docs/BUSINESS_IMPACT.md`. Competitive framing: `docs/COMPETITIVE.md`. Live demo script: `DEMO_STORY.md`.
