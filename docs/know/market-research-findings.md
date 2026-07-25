# Market research findings — backing notes for `docs/know.md`

Compiled 2026-07-25 via live web search (explicitly requested by the user for this
specific task — the project's normal rule is "ask, don't search"). This file is the
raw findings; `docs/know.md` is the digested, judge-ready version. Read that one first.

## 1. Is Chennai a real hub for hyperscale data centres right now?

Yes — genuinely, heavily. As of the 2024-2026 window, real announced/under-construction
projects in Chennai (mostly the Ambattur corridor) include:

| Operator | Project | Scale | Status |
|---|---|---|---|
| Iron Mountain | CHN-1 / CHN-2, Ambattur | 42 MW across 2 buildings | Phased completion targeting 2026/2028 |
| Colt DCS | Ambattur campus | up to 72 MW across 2 buildings | Under development |
| Princeton Digital Group | CH1 | 72 MW | Dual 230kV power, PUE < 1.4 |
| Blackstone (Lumina CloudInfra) | Ambattur campus | 216 MW initial IT load | Under development |
| Digital Connexion / Brookfield / Digital Realty | MAA10 | 100 MW | Launched Jan 2024 |
| Equinix | CN1 | 3.24 MW -> 24MW+ scaling | Launched Q3 2024 |
| Adani Group | (announced) | hyperscale, unspecified MW | Announced |
| Meta / Reliance | Chennai campus | Meta's first India DC | Announced |

Sources: [datacentermap.com/india/chennai](https://www.datacentermap.com/india/chennai/),
[Iron Mountain via baxtel.com](https://baxtel.com/data-centers/iron-mountain),
[Colt DCS](https://www.coltdatacentres.net/en-GB/our-locations/data-centre-locations-asia/chennai),
[Princeton Digital Group newsroom](https://princetondg.com/newsroom/princeton-digital-group-unveils-major-india-expansion-taking-total-capacity-to-230-mw-in-mumbai-and-chennai/),
[ConstructionWorld — Adani](https://www.constructionworld.in/latest-construction-technology/Adani-Group-to-set-up-hyperscale-data-centre-in-Chennai-/25092),
[BlackRidge Research — Meta/Reliance](https://www.blackridgeresearch.com/news-releases/meta-to-build-its-first-indian-data-center-in-reliance-chennai-campus-india).

**Conclusion:** SiteMind's demo project — a 48 MW Tier-III data centre in Chennai — sits
squarely inside the real range of these announced projects (between Equinix's ~24MW and
Iron Mountain's 42MW and Colt's 72MW). It is not copied from any single one of them; it's
a plausible, representative composite, sized to be believable without claiming to BE any
specific real company's project.

## 2. Is "Tier III / concurrently maintainable / N+1" a real classification?

Yes — this is the Uptime Institute's actual published tier standard, not invented
terminology. Tier III means every component in the critical power/cooling path has a
redundant path and can be maintained without shutting down IT operations (N+1 redundancy,
99.982% published availability target).

Source: [Uptime Institute — Tier Classification System](https://uptimeinstitute.com/tiers).

## 3. Are the cited Indian standards (IS 456, IS 1893, IS 875, IS 3043, IS 732, IS 8623) real?

Yes, all of them are genuine, currently-referenced Bureau of Indian Standards (BIS) codes:

- **IS 456:2000** — Plain and Reinforced Concrete, Code of Practice. The exact standard
  SiteMind cites for cover/durability/marine-exposure clauses.
- **IS 1893 (Part 1):2016** — Criteria for Earthquake Resistant Design of Structures.
- **IS 875 (Part 3):2015** — Design Loads (wind loads) for Buildings and Structures.
- **IS 3043:1987** — Code of Practice for Earthing.
- **IS 732** — Code of Practice for Electrical Wiring Installations.
- **IS 8623 (Part 1):1993** — Low-voltage switchgear and controlgear assemblies (identical
  to IEC 439-1:1985).
- **CEA (Measures Relating to Safety and Electric Supply) Regulations, 2010** — a real
  Indian central government electrical-safety regulation, not a BIS code.

Confirmed independently via the Bureau of Indian Standards' own site (bis.gov.in) and
the Internet Archive's digitised copy of IS 456:2000
(`https://archive.org/details/gov.in.is.456.2000` — this is the EXACT verify_url already
used in `backend/data/standards/clauses.json`, so the citation data in the live app
resolves to a real, independently-checkable government standard, not a fabricated link).

Sources: [BIS — IS 8623 Part 3](https://www.services.bis.gov.in/php/BIS_2.0/bisconnect/standard_review/Standard_review/Isdetails?ID=MTU4MDI%3D),
[Internet Archive — IS 456:2000](https://archive.org/details/gov.in.is.456.2000),
[InfraLens IS code index](https://infralens.in/is-codes).

## 4. Are "Design Basis Report", "RFI", "Submittal", "NCR" real construction-industry terms?

Yes — standard Engineering, Procurement & Construction (EPC) / construction-administration
vocabulary, used on virtually any large infrastructure project (not data-centre-specific):

- **RFI (Request for Information)** — a formal question raised during construction when
  a spec/drawing is ambiguous or needs clarification.
- **Submittal** — a contractor's formal submission of a shop drawing, product data sheet,
  or method statement for the engineer/owner to review and approve/reject/annotate.
- **NCR (Non-Conformance Report)** — a formal record that some executed or submitted work
  deviates from the specified requirement/standard; often resolved via an RFI.
- **Design Basis Report** — the document that states a project's foundational design
  parameters/assumptions (loads, exposure class, seismic zone, etc.) that everything else
  gets checked against.

Sources: [QIC Management — RFI in Construction](https://qualityinconstruction.com/rfi-construction/),
[QIC Management — NCR in Construction](https://qualityinconstruction.com/ncr-in-a-construction-project/),
[Eric Ocampo — Project QAQC controls (RFI/CAR/NCR)](https://ericocampo.com/project-qaqc-controls-management-rfi-car-ncr/).

## 5. Where did the original problem statement come from?

SiteMind was originally built for the **ET AI Hackathon 2026, Problem #4 — "AI
Intelligence Platform for Data-Centre EPC Project Delivery."** ET AI Hackathon 2026 is a
real, currently-running hackathon (Economic Times-affiliated; confirmed via
[groupify.ai's coverage of its prototype stage](https://www.groupify.ai/blog/et-ai-hackathon-enters-prototype-stage)).
The specific problem-statement text itself is not publicly indexed (expected — hackathon
problem statements are typically distributed privately to registered teams, not published
as a public web page), so its exact original wording can't be independently verified via
search; what's confirmed is that the event itself, and the general "AI for data-centre EPC
delivery" problem space, are real and current. The project was later repositioned for the
**HexaFalls** open-innovation hackathon (see `hexafalls_plan.md` for that pivot's reasoning).

## What this does NOT establish

This research shows the *scenario* (Chennai, hyperscale, Tier III, 48MW, the specific
Indian standards, the EPC document workflow) is realistic and grounded in things that
genuinely exist. It does **not** mean:
- SiteMind's specific demo project (document IDs like `DC1-02-DBR-0001-R2`, the specific
  RFIs/NCRs/schedule/supply-chain data) belongs to any real, named company or site — that
  data is synthetic, generated by `backend/data/gen_synthetic.py` for this demo.
- Any of the 6 HexaFalls sponsor-tech additions (Actian, MongoDB, Solana, Telegram,
  ElevenLabs, LangGraph) are things a real Chennai DC project actually uses today — those
  are this project's own build choices for the hackathon, not claims about industry practice.
