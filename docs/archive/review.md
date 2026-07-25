# SiteMind — Full Competitive Review (Hackathon Judge Pass)

**Reviewer role:** Senior AI SWE / hackathon judge, scoring against the brief
"AI Intelligence Platform for Data Centre EPC Project Delivery."
**Docs reviewed:** `docs/features.md`, `DEMO_STORY.md`, `docs/BUSINESS_IMPACT.md`,
`docs/DECK_OUTLINE.md` (plus cross-references to `PROGRESS.md`, `docs/ARCHITECTURE.md`,
`docs/PS_optimize.md`, `README.md` as cited within them).
**Rubric:** Innovation 25% · Business Impact 25% · Technical Excellence 20% ·
Scalability 15% · User Experience 15%.
**Purpose of this file:** everything — verdict, direction check, per-doc critique,
gaps vs. the brief, judge questions you WILL get, scoring, and a prioritized fix
backlog you (or an AI agent) can execute item by item.

---

## 0. Executive verdict

**Is this in the right direction? Yes — emphatically.** The core thesis (retrieve
the real clause, decide deterministically, cite verbatim, never guess; LLM writes
prose only) is the *correct* architecture for zero-tolerance infrastructure, and it
is exactly the answer to the brief's opening diagnosis: "the intelligence to
connect them never gets built." The cross-pillar evidence thread
(RFI-EL-112 ↔ SHP-002 ↔ Schedule DC1-04-EL-030 ↔ equipment-spec check) IS the
product, and no generic "GPT wrapper over construction docs" competitor will have
it.

**The risk is not the build — it's the framing.** Three structural exposures:

1. **Innovation under-claimed.** You built a *trust engine* but your docs sell
   *rule-checking*. A judge scoring Innovation 25% may read "deterministic Python
   + LLM prose" as "not really AI." You must invert this: the innovation is that
   **the LLM never decides** — that inversion is what makes AI admissible in
   uptime-SLA infrastructure. Name it, put it on a slide.
2. **The brief's named commissioning standards (TIA-942, BICSI, Uptime Institute)
   are essentially absent.** DC1 is pitched as Tier III, but there is no Tier
   topology/redundancy check anywhere. Your IS-code depth is a defensible
   strategic choice for India — but no doc makes that argument, so it reads as an
   omission instead of a decision.
3. **"Schedule risk prediction lead time versus actual delays"** (the brief's own
   evaluation-focus wording) is un-answerable by design — no real project to
   backtest against. Every doc quietly walks past this. Confront it head-on
   instead, the way you confront everything else.

**Projected score today: ≈7.3/10 weighted. With the fixes in §8: ≈8.2–8.5.**
That's the difference between "strong contender" and "winner" in most fields.

---

## 1. What is genuinely excellent (protect these — do not "improve" them away)

- **The honesty model.** "Real logic over representative data," REAL vs
  REPRESENTATIVE in the README, disclosed synthetic dataset, corpus-limitation
  banners, citation trust tiers (`codebook_verified` / `primary_native_pdf` /
  `primary_scan_ocr` / `cross_source_unverified`), typed `*UnavailableError`
  instead of mock fallbacks on ingest paths. This is a *moat*, not overhead.
- **The eval suite** — 18 distinct harnesses (see §5 on the "21" count), each
  pillar scored separately, never blended, with a self-critical caveats section
  (`docs/features.md` lines 202–223) that names its own weaknesses (gold labels
  derived from implemented thresholds, small self-authored test sets, threshold
  overfitting risk, dormant Pongal rule). I almost never see this at hackathon
  level. Deduction-proofing at its finest.
- **The evidence-linking thread.** `evidence_links.py` computing the
  SHP-002 ↔ RFI-EL-112 join live, rendered as a clickable chip — "this link is
  computed live, not typed into a slide" is a devastating demo line.
- **Act 5 (live upload of never-seen docs) and Act 6 (simulated clock).** These
  preempt the two standard hackathon accusations — canned demo and hardcoded
  numbers — *interactively*. Keep both at all costs.
- **The ADVISORY finding (I = 1.0 vs 1.5, IS 1893 Cl. 7.2.3 / 6.4.2).** Judgment
  surfacing, not pass/fail — the single moment that reads "senior reviewer," and
  correctly abstains from forcing a verdict. Right closing beat.
- **Codebook as an MCP-consumable standalone service.** A real (not slideware)
  scalability answer: breadth grows by adding corpora and callers, no retraining.
- **BUSINESS_IMPACT's causal-mapping table** — pillars mapped onto the brief's
  *named* loss causes (procurement misalignment, commissioning failures). "Built
  against the brief's own diagnosis" is how you win Business Impact without
  fabricating ROI.
- **Deck slides tagged to rubric criteria.** Forces coverage of the criteria
  teams usually forfeit (Scalability, UX). Keep the discipline.

---

## 2. Doc-by-doc critique

### 2.1 `docs/features.md` — A− internally, C+ as a judge-facing artifact

**Goods**
- Grounded mirror of code with inline file paths; spot-check-proof.
- Best-in-class caveats section; ranking your own eval scripts by strength
  ("strongest scripts in the suite, for contrast") is senior-grade
  self-awareness.

**Flaws**
- **No thesis, no hierarchy.** 12 flat sections; a skimming judge can't tell the
  hero (Compliance) from the appendix (Knowledge Base — feature §10 is
  architectural debt documented as a feature: "predates Codebook, still live
  because 2 eval scripts import it").
- **Two parallel retrieval stacks** (`backend/app/retrieval/` vs
  `standards-service`) and **near-duplicate eval scripts maintained in two
  places** are the same disease: unconsolidated forks. Honest documentation of
  debt ≠ absence of debt; expect a scalability question on it.
- The **~7-minute blocking embeddings rebuild** of the 6,206-chunk corpus on
  every `standards-service` restart is a live-demo landmine buried at the bottom
  of a features doc. It belongs in a demo-day runbook with a mitigation.
- **13/24 dead citation `verify_url`s** (per `docs/PS_optimize.md`) in a project
  whose entire brand is citation trust. Small task, disproportionate
  embarrassment if a judge clicks one.

**Actions**
- Add a 10-line header: thesis, hero pillar, the one-sentence honesty model, and
  "read DEMO_STORY.md first if you're a judge."
- Create a separate judge-facing one-pager (see §8, fix #7).
- Move operational caveats (rebuild time, live-service eval dependency) into a
  `docs/DEMO_RUNBOOK.md`.

### 2.2 `DEMO_STORY.md` — A. Strongest doc; the real product is this narrative.

**Goods**
- One continuous thread instead of five feature demos — the single best
  presentation decision made in this project.
- Preemptive fabrication disclosure section, correctly scoped (real formulas
  over representative data).
- Contractor-names disclosure (L&T, Tata Projects, Voltas, Sterling & Wilson —
  real companies, illustrative use) handled correctly.

**Flaws**
- **9–10 minutes is too long.** Most hackathon slots are 5–7 min + Q&A. You have
  8 beats and no documented shorter cut. If you run over, judges cut YOU, and
  they'll cut the close (the ADVISORY beat — your best moment).
- **Five separate "say this if asked" conditional disclosures** scattered through
  the acts. Under stage adrenaline you will forget which ones. Consolidate into
  ONE up-front honesty statement (~15s): *"Everything you'll see is real
  computation over a disclosed representative dataset — happy to show exactly
  where that line sits."* Then stop managing disclosures mid-demo.
- **Act 3 is overloaded** (fault-level RFI + lead-time RFI + WBS join + root
  cause + spec chip in 2 min). RFI-EL-110 adds nothing the story needs — cut it.
- **Act 7 (Codebook) is a second product** narratively. Architecturally
  impressive, but it steps OUT of the DC1 story at the moment you should be
  landing it. In the short cut, compress to one sentence inside the close.
- **"Shop drawing" language invites the computer-vision question** you can't
  answer (you parse `.docx` prose, not drawings; the brief explicitly suggests
  CV for drawing review). Prepare the one-liner: "text-borne parameters today;
  the check engine is format-agnostic — CV extraction is a front-end swap, the
  deterministic clause-check behind it doesn't change."

**Actions**
- Write the 5-minute cut into the doc itself:
  1. Compliance + open-RFI match (90s) → 2. ROI/Cost-at-Risk (30s) →
  3. Supply-chain thread + evidence chip (90s) → 4. Live upload, one HIGH NCR
  (60s) → 5. Clock advance (20s) → 6. ADVISORY close + one-line Codebook mention
  (30s). Commissioning becomes a backup beat unless asked.
- Add a "Q&A ammunition" appendix (see §6 — pre-write answers to every question
  listed there).

### 2.3 `docs/BUSINESS_IMPACT.md` — B+

**Goods**
- The causal-mapping table (brief's named causes → pillars). Lead with it.
- Unit economics labeled as estimates with code locations
  (`backend/app/overview.py`, 20h / ₹15L constants). Right epistemics.
- Refusing an unsupported project-level $ projection is defensible and rare.

**Flaws**
- **You disarmed yourself at your highest-weighted criterion (25%).** The doc's
  climax is "the aggregate is for the audience to reason about themselves."
  Honest — but judges reward teams that do the reasoning *with guardrails*.
- **Internal contradiction with features.md:** this doc claims "21 separate
  held-out evals … all independently verified correct"; features.md says
  held-out "mostly means different wording, not independent authorship" and that
  duplicates inflate the count. A judge reading both catches you overselling in
  one doc what you undersold in the other. features.md's version is the true
  one — harmonize to it.
- **The lead-time-vs-actual-delays gap is walked past.** The brief's evaluation
  focus asks for "schedule risk prediction lead time versus actual delays."
  You offer `detected_lead_time_days = lead_time_days × 0.15` — a *derived
  warning window*, not a backtest. Features.md admits no backtest exists (no
  real project). You can't fix the data gap in a weekend; you CAN own it in
  writing.

**Actions**
- Add a clearly-labeled **scenario band** (sensitivity, not forecast): "IF a
  project at the brief's stated scale (15,000–40,000 line items, 200
  contractors) surfaces even 50–200 catchable non-conformances [assumption,
  stated], the unit economics imply 1,000–4,000 engineer-hours and ₹7.5–30 Cr
  rework exposure." Still your honesty model — it just doesn't outsource the
  multiplication.
- Add a head-on paragraph: "No real historical project exists to backtest
  prediction lead time against. Here is the arithmetic we CAN prove (CPM
  recomputation, leading-indicator rules, all eval'd), and here is exactly what
  a 90-day pilot on one live project would measure: warning date vs. actual
  slip date, per activity." Turning the gap into a pilot design reads as
  maturity, not weakness.
- Change "21 separate held-out evals" → "18 distinct eval harnesses (plus 3
  repointed copies)."

### 2.4 `docs/DECK_OUTLINE.md` — B+

**Goods**
- Every slide tagged to a rubric criterion; deck consistent with the demo and
  the docs (rarer than it should be).
- "Every number backed by a rerunnable command" posture carries through.

**Flaws**
- **No explicit Innovation thesis slide.** At 25%, the honesty architecture is
  defended implicitly. Name it: *"Inverted AI: the LLM never decides.
  Deterministic engines decide against verbatim standards; the LLM only
  narrates. That inversion is what makes AI admissible in zero-tolerance
  infrastructure."* This converts your biggest perceived weakness
  (deterministic ≠ sexy) into the differentiator.
- **"Multi-agent" is load-bearing but thin.** The project's one explicit
  multi-agent claim is three mitigation functions (`run_mitigation_eval.py`).
  The brief's suggested tech leads with "Agentic AI / Multi-Agent Systems."
  Either drop the phrase from slides (safer), or be ready to defend precisely
  which agents coordinate, over what protocol, and why that's more than three
  functions in a module.
- Needs backup slides for each **suggested-tech gap**: Computer Vision (absent),
  Geospatial depth (Leaflet map over synthetic shipments; no carrier feeds),
  QMS integration (internal NCR trail exists; no Aconex/SAP/Procore hook).
  "Illustrative only" protects you from *building* them, not from being *asked*.

---

## 3. Gaps against the brief that NO doc currently addresses

1. **TIA-942 / BICSI / Uptime Institute absence + no Tier topology check.**
   DC1 is "Tier III (N+1)" but nothing verifies Tier-relevant redundancy or
   commissioning sequence coverage against the brief's named standards.
   *Fix (cheap):* write the strategic paragraph — "we grounded in the codes
   Indian EPC contracts are legally written against (IS 456/875/1893/732/3043,
   CEA regs, IS 8623); Uptime/BICSI/full TIA-942 are licensed documents — same
   corpus mechanism, one indexing job away, and our trust-tier system already
   distinguishes verified from cross-source content." *Fix (better, if you have
   a day):* index the freely available TIA-942 structural/topology summaries or
   an N+1 redundancy check on the CRAH count in the demo data — even ONE
   Tier-flavored check lets you say the sentence with product behind it.
2. **Scale silence.** Brief: 15k–40k line items, 200 contractors, thousands of
   test procedures. Demo: 10 parameters, 6 shipments, 6 test records. No doc
   addresses ingestion throughput, corpus growth economics (the 7-min rebuild is
   the current answer and it's a bad one), or what 40k line items does to the
   checks engine. Write one honest paragraph: "what breaks first at real scale
   and why the architecture survives it" (stateless checks parallelize;
   embeddings need a persistent store — name pgvector/Qdrant as the planned
   swap; per-document checking is embarrassingly parallel).
3. **UX is the orphaned criterion (15%).** No user personas anywhere. Who is the
   QA engineer / planning engineer / commissioning lead, and what do they DO in
   the tool on a Tuesday? Most pages are read-only dashboards; Codebook
   Console's interactions were never exercised in a real browser (no Playwright
   here — features.md admits it). *Cheapest fix:* one persona paragraph per
   pillar in a short `docs/PERSONAS.md` + manually click through every demo
   surface in a real browser before demo day and record it as done.
4. **Commissioning is cooling-only** (electrical/fire deferred, NBC 2016 / DG-set
   corpus gap). Disclosed, but the brief's commissioning ask is broad
   ("thousands of individual test procedures across power, cooling, and IT").
   The live-upload generator-earthing addendum partially covers electrical —
   point at it explicitly when the question comes.
5. **No prioritized "if we had 3 more months" roadmap.** Judges ask this in
   every Q&A. Write it once: (a) CV submittal/drawing extraction feeding the
   same check engine, (b) Uptime/TIA corpus licensing + Tier topology checks,
   (c) live carrier/EDI feeds for supply chain, (d) QMS (Aconex/Procore)
   bidirectional NCR sync, (e) pilot backtest protocol for schedule
   predictions. Note that ALL five plug into existing seams — that's the
   architecture compliment you want the roadmap to pay you.

---

## 4. Judge-mind: hard questions you WILL get (pre-write every answer)

1. "Where's the AI? This looks like rules + retrieval." → The inversion thesis
   (§2.4). LLM for extraction prose + narration; retrieval + deterministic
   checks for decisions; that's WHY zero hallucinated citations is provable.
2. "The brief says multi-agent. Where are the agents?" → Honest answer or drop
   the phrase. Have one.
3. "Can it read an actual drawing?" → The CV one-liner (§2.2).
4. "What's your accuracy on real project data?" → "No team in this room has real
   hyperscale EPC data. We prove internal correctness with 18 eval harnesses and
   disclose exactly which numbers are synthetic-grounded; here's the pilot
   protocol that closes the loop."
5. "How is this different from Procore/Aconex/ALICE/nPlan/Document Crunch?" →
   Currently answered NOWHERE in your docs. Write a 5-row competitive table:
   they manage documents/schedules; none decide against verbatim Indian
   standards with cited, hallucination-audited clauses; none expose the checker
   as an MCP service other agents can consume. This absence is a real gap —
   Business Impact judges love a competitive frame.
6. "What happens at 40,000 line items?" → §3.2 paragraph.
7. "Who pays, and how much?" → Also answered nowhere. Even one sentence
   ("per-project SaaS to EPC contractors; a single avoided rework event at
   ₹15L covers a year of seats") beats silence. Add to BUSINESS_IMPACT.md.
8. "Is IS 456 actually the right standard for a DC?" → Yes for structural works
   in India — but be ready to say why the *portfolio* of codes was chosen and
   that the corpus mechanism is standard-agnostic.
9. "Why should I trust the 0-hallucination claim?" → `GET /api/eval/report`
   re-checks every NCR citation against the real clause cache, live. Show it.
10. "This 2.5Ω vs 1.0Ω earth-grid check — did an engineer validate these
    thresholds?" → Your citations are the answer; know the two or three
    headline clauses cold (IS 456 Cl. 26.4.2.2 50mm cover; IS 3043 1.0Ω; IS
    1893 I-factor) so you never read them off the screen.

---

## 5. Internal consistency issues to fix (docs contradicting docs)

- **"21 evals" vs "18 distinct + 3 repointed copies"** — BUSINESS_IMPACT.md
  oversells what features.md correctly caveats. Standardize on 18-distinct
  phrasing everywhere.
- **"held-out"** — features.md correctly narrows this to "different wording, not
  independent authorship"; BUSINESS_IMPACT.md uses "held-out" unqualified, and
  DEMO_STORY Act 7 says "Held-out eval: 30/30." Either qualify once, globally,
  or get one truly independent set: **have a teammate (or another AI, blind to
  the thresholds) author 10–15 test cases from the standards text alone.** This
  is maybe 2 hours of work and upgrades your single most repeated caveat into a
  strength. Highest-leverage technical improvement available to you.
- **Pongal rule is dormant on demo data** (features.md) — so don't gesture at
  workforce risk in the live demo unless you've added a fixture that exercises
  it, or a judge who reads the docs catches the mismatch.
- **`run_codebook_tools_eval.py` requires the live service** — if you quote "all
  evals pass," make sure it actually ran in the state you're quoting.

---

## 6. Things to ADD (ranked by points-per-hour)

1. **Innovation thesis slide + paragraph** ("the LLM never decides"). ~1h.
   Directly targets the 25% criterion where you're most under-priced.
2. **Scenario-band + pilot-protocol sections in BUSINESS_IMPACT.md.** ~1h.
   Directly targets the other 25% criterion.
3. **Independent eval authorship** (blind-authored 10–15 cases, §5). ~2h.
   Converts your most-repeated caveat into a headline.
4. **Competitive one-pager** (vs Procore/Aconex/nPlan/ALICE/Document Crunch).
   ~1–2h. Fills a total void; judges ask this every single time.
5. **5-minute demo cut written into DEMO_STORY.md** + Q&A appendix from §4. ~1h.
6. **"Why IS codes, not TIA-942" strategic paragraph** (and, if time, one
   Tier/N+1-flavored check on the demo data). ~30min / ~1 day respectively.
7. **`docs/JUDGE_ONE_PAGER.md`** — problem → thesis → 5 pillars in one line each
   → 3 real numbers → honesty model in one sentence → stack diagram pointer.
   Judges give you 90 seconds of reading; features.md is not that artifact. ~1h.
8. **`docs/DEMO_RUNBOOK.md`** — pre-warm standards-service (7-min rebuild!),
   never restart live, `run-full.sh` / `npm run dev` startup order, fallback
   plan if SSE stream fails (the simulated-stream fallback exists — know when
   it's on and DISCLOSE it if it triggers, or it violates your own honesty
   model), browser click-through checklist for Codebook Console. ~1h.
9. **Personas paragraph per pillar** (`docs/PERSONAS.md`). ~1h. Cheapest UX
   points available.
10. **Business model sentence** (who pays). ~10min.
11. **Fix or strip the 13/24 dead `verify_url`s.** ~1–2h. Brand-critical.
12. **Pre-recorded demo video** (an expected deliverable!) following the
    5-minute cut — also your insurance against the 7-min-rebuild landmine and
    venue Wi-Fi. Confirm all four expected deliverables exist: prototype ✓,
    architecture diagram (verify `docs/ARCHITECTURE.md` has an actual diagram,
    not just prose), deck (outline exists — build it), video (no evidence it
    exists yet).

## 7. Things to REMOVE / DEMOTE / STOP

- **Demote Act 7 (Codebook) in the live demo** to one closing sentence; keep the
  page as Q&A ammunition for scalability.
- **Cut RFI-EL-110 from Act 3.** Redundant with RFI-EL-112.
- **Stop using "multi-agent" on slides** unless you can defend it (§2.4).
- **Demote Knowledge Base (feature §10)** — don't show it; it's debt. If a
  refactor hour appears, consolidate the two retrieval stacks or at least add a
  README note that Codebook is the canonical one.
- **Remove the five scattered "say if asked" disclosures** in favor of the one
  up-front honesty statement.
- **Don't lead with eval caveats verbally.** The caveats live in writing (great
  for diligence); the stage version is "every number you saw is reproducible by
  a script in this repo — and the repo also documents what those scripts can't
  prove."

---

## 8. Scoring — as I'd mark it today vs. after fixes

| Criterion | Weight | Today | After fixes | Why |
|---|---|---|---|---|
| Innovation | 25% | 7.0 | 8.5 | Trust inversion + evidence-linking + MCP standards engine are real differentiation, currently unclaimed. Thesis slide + competitive frame close the gap. |
| Business Impact | 25% | 7.5 | 8.5 | Causal mapping is best-in-class; scenario band + pilot protocol + who-pays sentence stop the self-disarmament. |
| Technical Excellence | 20% | 9.0 | 9.5 | Already the strongest axis. Independent eval authorship + consistency fixes make it airtight. |
| Scalability | 15% | 6.5 | 7.5 | Codebook-as-service is real; needs the scale paragraph, embedding-store answer, and (ideally) stack consolidation note. |
| User Experience | 15% | 6.0 | 7.0 | Coherent judge-UX; needs personas, browser-verified surfaces, tight 5-min demo. |
| **Weighted** | | **≈7.3** | **≈8.3** | |

---

## 9. Priority execution order (if you only do N things)

1. 5-minute demo cut + one consolidated honesty statement (DEMO_STORY.md).
2. Innovation thesis ("the LLM never decides") — slide + one paragraph reused
   everywhere.
3. BUSINESS_IMPACT.md: scenario band + lead-time-vs-actuals pilot paragraph +
   who-pays sentence + "18 distinct" harmonization.
4. Q&A appendix answering every §4 question.
5. Demo runbook + pre-recorded video + deliverables audit (diagram/deck/video).
6. Independent (blind) eval set, 10–15 cases.
7. Competitive one-pager.
8. "Why IS codes" paragraph (+ one Tier/N+1 check if a day exists).
9. Dead verify_urls; personas; judge one-pager.
10. (Stretch) consolidate retrieval stacks; persist embeddings cache to disk to
    kill the 7-minute rebuild — this one is both a demo-risk fix AND a
    scalability talking point ("we added a persistent vector store").

---

## 10. Final judgment

The direction is right and the engineering discipline is exceptional — the risk
profile of this project is entirely in **narrative and coverage-vs-brief, not in
correctness**. Your discipline is your moat, but discipline documented as
caveats reads as weakness, while discipline documented as *architecture* reads
as innovation. Nearly every fix above is a reframing of something already
built, not a new build. Reframe hard, close the three named exposures
(innovation thesis, standards-choice argument, lead-time honesty), tighten the
demo to five minutes — and this is a winning entry.
