# Competitive framing — where SiteMind sits

No doc in this repo answered "how is this different from [incumbent]?" before this one. Judges ask it
almost every time; a total void reads worse than an imperfect answer. This is a framing document, not a
market-research report — the "what they do" column is each company's own widely-known public positioning
(their websites/marketing), not a claim of complete or verified knowledge of their internals. Verify before
quoting a specific feature claim about a competitor in a real pitch; the *category* claims below are safe.

## The one differentiator none of them share

Every tool below manages, tracks, or displays construction information. **None of them decide pass/fail
against a real, verbatim, cited construction standard, with a measured hallucination rate on that decision,
and expose that decision engine as a service other agents can call.** That's the specific, narrow claim —
not "we're more AI than them," which is both unverifiable and untrue for several of these (some already use
real ML/AI internally, just not for this).

| Tool | Public positioning | What it doesn't do (as far as publicly documented) |
|---|---|---|
| **Procore** | Construction management platform — documents, RFIs, submittals, budgets, scheduling, all in one system of record. | Doesn't check a submittal's engineering parameters against cited standard text; it routes and tracks documents, it doesn't read and verify their content against a code. |
| **Aconex / Autodesk Construction Cloud** | Document control and BIM collaboration platform, common on large EPC/megaprojects for correspondence and drawing management. | Same category as Procore — workflow and version control over documents, not automated compliance verification against a standard's clause text. |
| **ALICE Technologies** | AI-driven construction scheduling/"optioneering" — generates and compares many buildable sequencing options against constraints. | Focused on schedule/sequence optimization, not spec/compliance checking or citation-grounded document review. |
| **nPlan** | ML-based schedule-risk forecasting, trained on a large historical database of real project schedules to predict delay probability. | Statistical/ML forecasting from historical patterns, not a deterministic clause-by-clause compliance check — a genuinely different (and in some ways more mature, given nPlan has real historical training data SiteMind does not) approach to the schedule problem specifically. |
| **Document Crunch** | LLM-based assistant that answers questions over contracts and specs — "ask your documents anything." | This is the closest category neighbor. The open question or is its citation grounded to source text with a measured, published hallucination rate the way SiteMind's `GET /api/eval/report` is — that's the exact comparison to draw out live if asked, not to assert one way or the other without checking their current claims. |

## The honest version of the pitch

"These tools are good at what they do, and several of them (ALICE, nPlan) are more mature specifically at
scheduling than SiteMind is. What none of them are built to do is the thing SiteMind's whole architecture is
organized around: take a real clause from a real standard, decide against it deterministically, and prove —
per citation, on every run — that the decision wasn't hallucinated. That's a narrow claim, on purpose; it's
also the one none of them are competing on."

## What this is not

Not a claim that SiteMind is more valuable, more mature, or more fundable than any tool listed here — most
of them have real customers, real revenue, and real production deployments SiteMind does not. This document
exists to answer one question precisely ("what's different"), not to win an argument about which product is
better overall.
