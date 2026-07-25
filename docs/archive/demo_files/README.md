# SiteMind — demo files (for the video)

Drop-in files to upload live during the demo. Each is synthetic but **verified to fire real findings**
through the actual backend pipeline. All findings are decided by deterministic Python against real IS
clauses (the model never decides).

| File | Upload into | What it demonstrates | Expected result (verified) |
|---|---|---|---|
| `Structural-Design-Basis-Report_DEMO.pdf` (or `.txt`) | **Compliance** → Upload DBR | Reads a submittal, extracts params with source spans, checks each against a cited IS clause | **3 HIGH NCRs + 1 ADVISORY + conforming params** |
| `Cooling-Commissioning-Log_DEMO.csv` | **Commissioning QA** → upload log | Deterministic PASS / within-allowable / FAIL vs the thermal envelope | **PASS + MEDIUM (allowable) + HIGH (fail)** rows |

## Compliance DBR — the exact findings it produces
*(clause refs and on-screen order below are verified against the live backend, 2026-07-22 —
`3 HIGH + 1 ADVISORY`, in this order, plus 1 conforming PASS. 6 params extracted, 5 checks run.)*
1. **HIGH** — Raft footing F-12: nominal cover **30 mm** vs **50 mm** minimum (IS 456:2000, Cl. 26.4.2.2).
2. **HIGH** — Coastal pile caps: **M25** concrete vs **M30** minimum for marine RCC (IS 456:2000, Cl. 8.2.8).
3. **HIGH** — Severe-exposure raft: water-cement ratio **0.50** vs **0.45** max (IS 456:2000, Cl. 8.2.4.1).
4. **ADVISORY** — Seismic importance factor **I = 1.0** for a mission-critical facility (IS 1893 Part 1, Cl. 7.2.3). *The memorable "senior engineer would question this" beat.*
5. **Conforming** — Column C-08 longitudinal steel **1.8%** (within range) → PASS (IS 456:2000, Cl. 26.5.3.1), proving it doesn't just flag everything.

The **M35 superstructure grade** also passes silently (not marine), so the run shows real
selectivity, not a blanket flag. The `.pdf` looks like a real submittal on camera; the `.txt` is a
guaranteed-clean fallback. Both extract to the identical 4 NCRs + 1 conforming.

## Commissioning CSV — the spread it produces
- **PASS:** supply-air 22.5 / 24.8 °C, return-air 26.2 °C, room 19.4 °C, RH 45% (inside recommended 18–27 °C / 20–60% RH).
- **MEDIUM (within allowable):** supply-air 30.5 °C and RH 72% (outside recommended, inside A1 allowable) → NCR MEDIUM.
- **HIGH (fail):** supply-air 34.0 °C and RH 88% (outside the A1 allowable envelope) → NCR HIGH.
- **NOT_CHECKABLE:** the `airflow_rate` row (no thermal-envelope clause) → honestly skipped, not guessed.

> Note: uploads need the backend running. Compliance + Commissioning run fully offline (no key).
> If you also demo Copilot / Knowledge Base search, the backend needs a free `HF_TOKEN` set.
