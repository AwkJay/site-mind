# Presentation deck — outline

> **⚡ HexaFalls note (2026-07-25):** everything below this line describes `docs/deck/index.html`
> and `docs/deck/pitch.html` — both ET AI Hackathon-era decks, scored against THAT hackathon's
> specific rubric (Innovation/Business Impact/Technical Excellence/Scalability/UX), not HexaFalls's.
> **The current, HexaFalls-era judge-facing deck is `docs/v3.1.html`** (13 slides, updated this
> session — cover, positioning, and a new "HexaFalls additions" slide all reflect the current
> build). **The current narrative/click-path companion is `docs/HEXAFALLS_PITCH.md`** — the
> sponsor-track narrative arc (Perceive/Retrieve/Decide/Remember/Prove/Reach-the-field) and the
> exact click-path per sponsor moment, which supersedes needing a slide-by-slide outline for this
> older content. Kept below as historical reference only — do not present from this file.

This outline describes `docs/deck/index.html` (16 slides), which has since been superseded by the
newer `docs/deck/pitch.html` (7 slides) as the canonical deck for submission — see `docs/pitch.md`
for that deck's notes. TODO: a fresh slide-by-slide outline for `pitch.html` doesn't exist yet.

Draft content only — the user builds/delivers the actual deck. Every slide is tagged with the rubric
criterion it's meant to score (Innovation 25 / Business Impact 25 / Technical Excellence 20 / Scalability
15 / UX 15) so nothing is included without a reason. Numbers here must be re-verified against a live run
before presenting (`sitemind/PROGRESS.md` has the reproduction commands) — this outline is content
structure, not a source of truth for numbers on demo day.

**Rewritten 2026-07-03 (third pass)** — the second pass predated today's UI-review + live-upload-story
build phase entirely: the Settings panel fix, the schedule realism fix, the Supply Chain/Graph disclosure
panels, the simulated demo clock, and the two new live-upload `.docx` documents. Two new slides added
(5 and 10); slide numbers below are final. **Supersedes** the earlier version of this file and `PLAN.md` §6.

**Updated 2026-07-10 (fourth pass, post-Phase-2 polish)** — folds in the judge-eyes UI pass, verified
live before writing this: the reworked Overview hero (machine-scale strip + Next-decisions queue), the
Schedule Gantt's ghost baseline-vs-predicted bars with causal driver labels, the Timeline page's drawn
evidence connector lines, the Copilot pre-rendered exemplar, and the Compliance register A–E legend with
de-rigged submittal titles. Slide numbering is unchanged from the third pass — these are in-slide beats,
not new slides.

## 1. Title + hook (0:00–0:15) — *Business Impact*
"India is building $15B of data-centre capacity by 2027. 67% of these projects overrun schedule by more
than 10% — and the brief names the two leading causes: procurement misalignment and commissioning
failures." One line, the brief's own numbers, no invented ones.

## 2. The information-fragmentation problem (0:15–0:35) — *Business Impact*
Specs, submittals, RFIs, schedules, procurement status, quality records: disconnected systems. SiteMind is
one living intelligence layer over all of it — not a chatbot over documents, a decision layer.

## 3. The credibility thesis, stated up front (0:35–0:55) — *Innovation + Technical Excellence*
"Every citation resolves to real, verbatim digitised Indian standard text. Every pass/fail decision is
plain Python, not an LLM guess. If we can't verify it, we don't claim it." This is the one idea worth
repeating three times in the deck — it's the actual differentiator, not a feature list.

## 4. Live demo — Compliance Agent (the hero) (0:55–1:55) — *Innovation + Technical Excellence + UX*
Upload a real DBR (or use the pre-loaded one) → real extraction with source spans → NCRs cited to real IS
456/875/1893 clauses (plus a second **electrical domain**: IS 732/3043/CEA/8623, held out from the demo
baseline but eval-proven, 32/32) → the IS 1893 I=1.5 judgment-catch ADVISORY ("a Tier-III/IV DC is arguably
a lifeline facility... confirm with EOR," now cited to *both* governing clauses) → click a citation, the
real clause opens, with a **source-type provenance badge** showing exactly how verified it is (manak-
verified / primary native PDF / primary OCR scan / cross-source compiled — never presented as equivalent) →
Action Brief (confidence enum, never a fabricated %, real RFI/schedule links or an honest "none found").
The document register now carries a compact **A–E status-code legend** (real AEC submittal-review codes),
and register titles no longer state the checked parameter values — a rigged-looking artifact removed with
zero effect on the 10-checked / 6-findings / 4-conforming baseline.

## 5. Live demo — a document SiteMind has never seen before (1:55–2:20) — *Innovation + Technical Excellence*
The pre-loaded DBR could look memorised. Upload one of the two new real `.docx` files instead
(`backend/data/project_docs/live_upload_samples/`) — a generator-earthing addendum that produces 3 real
HIGH NCRs (under-earthed frame, under-earthed neutral, high earth-grid resistance, each cited to a real CEA/
IS 3043 clause) plus 1 conforming reading, or a generator-plinth shop drawing whose 35mm footing cover
trips the *same* overlap-resolution logic as the F-12 finding on slide 4. Both documents continue the same
generator/DRUPS story already on screen elsewhere — not a disconnected new example.

## 6. Live demo — Schedule Risk + Multi-Agent Mitigation (2:20–3:05) — *Innovation + Technical Excellence + Business Impact*
CPM + leading-indicator rules, a real re-computed project-finish impact (not asserted — float correctly
absorbs slips on non-critical activities). **This is the literal answer to the brief's own words**: its
Predictive Schedule Risk Engine bullet is the only place the brief names multi-agent specifically —
"generating mitigation options, not just alerts." Click a flagged risk and show **three specialist agents**
firing in parallel: a procurement-alternative check (reuses Supply Chain's real viability arithmetic), a
resequencing/float check (reads real CPM float), and a resource/overtime-recovery check (real productivity-
rate math) — a plain coordinator collects every result, including the ones that come back non-viable,
transparently. State plainly: this is a bounded multi-agent system, not a planning-loop framework — each
agent is one real tool-call over data already in-process, not LLM reasoning. **If pressed on why three
deterministic functions count as "agents":** name the pattern precisely — specialist/coordinator, each
specialist owns one domain's decision logic (procurement viability, CPM float, resource-recovery math),
all three always invoked together and the coordinator returns every result including non-viable ones.
That's "multi-agent" in the software-engineering sense (bounded, composable, coordinator-orchestrated),
not the autonomous-planning-loop sense — say the distinction rather than let the word do the work alone.
On the Gantt itself, every
at-risk activity now shows a **ghost baseline bar beneath its predicted bar** with a `+Nd` slip label and
a short causal driver phrase — the slip is *visible*, not just listed in a side panel.

## 7. Live demo — Supply Chain Visibility, Alerts & Evidence Linking (3:05–3:50) — *Innovation + Business Impact*
This directly answers the brief's "procurement misalignment" cause. An **Alerts panel** (in-app, severity-
tiered, `advance_warning_days` computed from real milestone data — answers the brief's "alerting
timeliness" metric) sits above the map: a DRUPS shipment flagged at-risk, root cause traced to a *tier-2*
battery-cell customs delay in Shanghai — not just "vendor is late," but *why*, three tiers deep. Then the
computed alternative: a viable bridge-rental supplier, real lead time, real cost premium. Point at the
**clickable evidence chip** on SHP-002 linking straight to RFI-EL-112 and its schedule activity — computed
live from a real shared key, not typed into a slide. Also show the **equipment-spec compliance** chip (IS
8623-1:1993 MATCH), and the page's own **as-of-day disclosure banner** — say plainly this is a computed
snapshot, not a live carrier feed, matching the credibility thesis from slide 3. The same SHP-002↔RFI-EL-112
link is also *drawn as a literal connector line* on the **Timeline page** (build lifecycle, groundbreaking →
handover, now-line at the current simulated day) — worth a 5-second cutaway if time allows.

## 8. Live demo — Commissioning QA (3:50–4:25) — *Innovation + Technical Excellence*
Upload the sample cooling test-log CSV live → deterministic PASS/within-allowable/FAIL against the ASHRAE
TC9.9 thermal envelope → a real NCR for the Zone C failure → an exportable as-commissioned quality package.
State the corpus-limitation banner out loud: cross-source compiled (ASHRAE's book is paywalled), disclosed
on every finding, never presented as manak-grade. Say plainly this is the cooling slice only — electrical/
fire commissioning is a disclosed, deliberate gap (see slide 14).

## 9. Live demo — Copilot with hybrid retrieval (4:25–4:45) — *Technical Excellence + UX*
Cross-document Q&A, cited answers, "this RFI was resolved before." New: retrieval now fuses BM25 keyword
search with dense embeddings via Reciprocal Rank Fusion — better recall on exact-ID queries ("RFI-EL-112")
without touching the eval-calibrated abstention floor. Show it correctly abstaining on an off-topic
question, not guessing — that floor is byte-identical before and after hybrid retrieval was added. The page
now opens with a **pre-rendered exemplar** — a real `askCopilot()` call fired on page load, same API path
and citation pipeline as a typed question — plus "Try also" chips and a one-line abstention disclosure, so
the beat never starts from a cold, empty composer.

## 10. Live demo — the simulated clock (4:45–5:05) — *Technical Excellence + UX*
Click the **Day N** control in the top bar, advance +14 or +20 days. Watch real numbers change live: the
schedule at-risk count grows, an alert's `advance_warning_days` grows by exactly the days advanced, an
alternative supplier that was viable can stop being viable as its arrival date gets pushed out. Reset
restores the exact baseline. This is the single best "prove it, don't just assert it" beat in the whole
demo — nothing in the underlying data changes, only time passing does, and the system reacts correctly.

## 11. ROI + Cost-at-Risk (5:05–5:35) — *Business Impact*
The Overview hero now leads with a **machine-scale strip** (documents read / clauses checked /
cross-references found / conflicts surfaced — each verified equal to API ground truth in the Phase-2
consistency sweep, not typed) and a **Next decisions** queue whose items deep-link to the pillar pages —
point at both before the ROI panel. Then the ROI story: a platform-wide hours/₹-saved total with a **per-pillar breakdown** (Compliance NCRs,
Schedule flags + CPM impact, Supply-Chain at-risk days, Commissioning FAILs — each traceable to a
documented, conservative assumption) directly answers the brief's "reduction in manual coordination effort
measured in hours." Next to it, a **Cost-at-Risk** panel: deterministic `schedule_delay_cost +
expedite_premium_cost + rework_exposure`, every term's formula and real inputs shown — the brief's other
explicit ask, "schedule AND cost risk modelling," both now answered.

## 12. Proof — twenty-one separate evals, never blended (5:35–6:00) — *Technical Excellence*
State plainly: rule-decision, extraction, electrical, equipment-spec, supply-chain, schedule, copilot,
commissioning, impact-model, cost-risk, mitigation, alerting, hybrid-retrieval-fusion, weather, workforce,
timeline-aggregation-consistency, and two retrieval/corpus-integrity checks are EIGHTEEN different metrics
in `backend/eval/` measuring eighteen different things — plus THREE more in the standalone Codebook
service's own `standards-service/eval/` (protocol-level MCP tests, real-corpus integrity) — twenty-one
total, reported separately on purpose, because blending them into one number was an earlier mistake this
project caught and corrected, and stayed corrected as the pillar count grew from 3 to 5. Show the real
numbers from the latest run.

## 13. Architecture + where we are (and aren't) agentic (6:00–6:20) — *Technical Excellence + Scalability*
`sitemind/docs/ARCHITECTURE.md` diagram. Emphasize: the LLM only ever writes prose (every arrow into it
labeled "prose only"); manak is a build-time dependency, not a live one. State the agentic position
explicitly, since it's now backed by real code: agentic where a task is naturally multi-option and every
option is a grounded computation (schedule mitigation) — never agentic where a task is a single verifiable
yes/no against a cited standard (compliance, commissioning, cost-risk). That line is the honest answer to
"why not a fully agentic platform," not a dodge.

## 14. Scalability story — from prototype to product (6:20–6:35) — *Scalability*
"Breadth scales by adding clauses, not by retraining anything — zero ML training anywhere in this system."
Roadmap: IS 875 all parts, IS 13920, IS 800, IS 1893 Pt4, NBC 2016 — say it, don't oversell it as built.
Then the bigger framing, stated once, plainly: **"SiteMind is the real product's kernel with the
enterprise shell deliberately absent."** The shell — P6/Aconex/SAP connectors, NCR workflow states,
role-based push delivery — is commodity engineering that can be hired; the kernel — grounded,
deterministic, citable verification, proven here on 5 pillars with 21 separate eval scripts (18
distinct harnesses + 3 more in the standalone Codebook service) — is the part that can't be bought,
so that's what got built. Six-stage roadmap (`docs/ARCHITECTURE.md`'s "From prototype to
product"): trust kernel (built) → overlay systems of record, don't replace them → equipment-tag ontology
as the join key for the brief's 15,000–40,000-line-item scale (today's SHP-002↔RFI-EL-112 evidence link,
now on the Timeline, is a working miniature) → findings become workflows → commissioning at real L1–L5
scale → cross-project memory as the compounding moat. Say the honest limit too: no live deploy in this
delivery (video + repo, by choice, not by gap), single project instance, no second-project proof yet.

## 15. Business impact — mapped to the brief's own diagnosis (6:35–6:55) — *Business Impact*
`sitemind/docs/BUSINESS_IMPACT.md`: the pillar-to-root-cause table, then real computed per-issue/per-shipment
unit economics — explicitly NOT a project-level $ projection, since SiteMind has no real project to base one
on. This restraint is itself a credibility signal worth saying out loud.

## 16. Honest close (6:55–7:15) — *all criteria*
What's real vs representative (`sitemind/README.md`'s framing). What's still deliberately out: Commissioning
QA's electrical/fire slice (grounded in real Indian codes when built, not the paywalled TIA-942/BICSI/Uptime
standards named in the brief — explain WHY that's the more defensible choice), live deployment, a second
tenant project. One sentence on what's next.

## Slides NOT to include
- Any slide asserting a project-level dollar figure derived from the brief's $15B market number — nothing
  in the codebase supports that multiplication (see `BUSINESS_IMPACT.md`).
- A slide claiming full autonomous multi-agent orchestration across the whole platform — the *schedule
  mitigation engine specifically* is genuinely multi-agent (three specialists + a coordinator, real code,
  eval-backed) and should be claimed plainly on slide 6. Compliance/Commissioning/Cost-risk stay
  deterministic Python by design — say that distinction out loud rather than blurring it either direction.
- Do NOT claim commissioning coverage beyond cooling — the electrical/fire slice is not built.
- Do NOT present the live-upload demo (slide 5) as if it were the pre-loaded fixture, or vice versa — the
  distinction ("this document has never been seen by the pipeline before") is the entire point of the beat.
