# SiteMind — Demo Video Script (~4:00)

> **Format:** one screen recording, live voiceover, interleaving the deck (`docs/deck/v3.1.html`,
> which carries the argument) with the live web app (`sitemind.awni.in` or localhost, which proves
> it). Target **3:50–4:15**.
>
> **The spine of this video is ONE dangerous number.** A footing is specified at **30 mm** of cover
> when Indian code requires **50**. We follow that single number the whole way: it's the hook, it's
> the live catch, and on the timeline it's the thing that connects compliance to schedule to
> procurement. Don't tour features — chase the number.
>
> **Two roles emerge on their own, don't narrate them as personas:** the **design/QA engineer** is
> who uploads the submittal and needs the catch + citation (Compliance page); the **project manager**
> is who needs to see where that catch bites (Timeline page). Let the demo show that; don't lecture it.
>
> **How to read this:** `[SLIDE n]` = show that deck slide (numbers match `v3.1.html`).
> `[APP → page]` = cut to the live app. **Bold** = say with emphasis. *(italics)* = action cue, not
> spoken. Every number is real (from `backend/eval/`); never round up on camera.
>
> **Golden rules on camera:** (1) pre-load everything, no spinners; (2) disclose the synthetic
> *project* once, plainly, early; (3) never click a `gaudi.local` citation link — show the clause
> text and its `source_type` tag in-app instead; (4) demo docs are in `docs/demo_files/`;
> (5) **say "it reads and pulls each parameter," not "Claude extracts this"** — the deck/PDF present
> LLM extraction as the target architecture, but the live run is still deterministic; narrate what's
> on screen, not what's on the roadmap.

---

## SEGMENT 1 — HOOK + PROBLEM · deck · ~0:40

**[SLIDE 1 — Cover]**
> "India is about to build thousands of megawatts of data-centre capacity, and every one of those
> buildings has to be *verified* against hundreds of pages of Indian structural and electrical code
> before it can be powered on. Today that's a senior engineer, reading by hand. I'm Awnikant, Team
> HashForge, and we built SiteMind to change that."

**[SLIDE 2 — The Problem]**
> "Here's the whole problem in one number. A submittal on a live project specifies a footing poured
> at **30 millimetres** of cover. Indian code, IS 456, requires a minimum of **50**. Get this wrong
> and the rebar corrodes years early — but the number is buried deep in a multi-page design report,
> and by the time a human catches it, the concrete has set. Sixty-plus percent of projects in our region
> already overrun. This is why."

**[SLIDE 3 — The Gap]**
> "So why not point a generic AI at it? Because generic AI does the one thing you can't allow here:
> it **guesses**. It retrieves a paragraph and lets a language model *decide* if it's compliant, and
> nothing stops it inventing a citation. In compliance, a confident wrong answer is worse than no
> answer at all."

---

## SEGMENT 2 — THE RULE · deck · ~0:30

**[SLIDE 4 — The Idea: "the model never decides"]**
> "SiteMind's entire idea is one rule: **the model never decides.** It reads the document and it
> writes the report — but the actual pass-or-fail call is deterministic Python, checked against a
> real, cited Indian Standard clause. On our benchmark that's **100% decision accuracy** versus
> **58-and-a-half percent** for a naive baseline, with a **measured zero percent** hallucinated-
> citation rate."

**[SLIDE 5 — How It Works: Perceive · Decide · Explain]**
> "Three stages. **Perceive** — read the document and pull each parameter with the exact sentence it
> came from. **Decide** — deterministic Python checks it against the cited clause; *this* middle step
> is the one no model is ever allowed to touch. **Explain** — only then does the model write the
> finding in plain English. Rules decide. The model narrates. Let me show you it catch our 30-mil
> footing live."

---

## SEGMENT 3 — LIVE DEMO · web app · ~2:20
*(This is the proof. Keep chasing the 30 mm number. Slow down; let the screen work.)*

**[APP → Overview / Command Center]** *(~15s — establish breadth, then move on)*
> "This is the live app, on a real **48-megawatt, Tier-III Chennai build**. Ten connected modules —
> compliance, schedule, supply chain, commissioning, a knowledge graph — one project. One honest
> note: the *project documents* are synthetic, modelled on public Indian tenders. But the
> **standards, the citations, and the checking logic are completely real** — and so is anything I
> upload right now."

**[APP → Compliance]** *(this is the engineer's cockpit — don't say that, show it)*
> "This is where a design engineer lives. I'll upload a Design Basis Report the system has never
> seen."
*(Click Upload → `docs/demo_files/Structural-Design-Basis-Report_DEMO.pdf`.)*
> "First it **perceives** — it reads the report and pulls each engineering parameter, and next to
> every one it shows the *exact source sentence* it came from. If it can't ground a value, it
> abstains instead of guessing. That's the guardrail."
*(Point at the extracted-parameters list and the source spans.)*

*(Click **Run compliance check**.)*
> "Now it **decides** — in Python, against real clauses. And there's our number: **three
> high-severity non-conformances**, top of the list, the **30-millimetre** footing."

**[APP → click the 30 mm cover NCR]** *(~30s — the money shot)*
> "There it is. Footing F-12, specified at **30 millimetres** of cover. SiteMind flags it against
> **IS 456, clause 26.4.2.2**, which requires **50**. And here's the part that matters..."
*(Open the citation provenance; show the `source_type` tag.)*
> "...that clause isn't paraphrased from a model's memory. It resolves to the **real digitised code
> text**, and it tells you its own reliability tier. The verdict was a threshold check in Python; the
> model only wrote the sentence explaining it. Show your work, cite your source."

**[APP → the ADVISORY finding — seismic importance factor]** *(~20s — the "senior engineer" beat)*
> "And my favourite one. The design uses a seismic importance factor of **1.0** — treating a
> mission-critical data centre like an ordinary building. That's not strictly illegal, so SiteMind
> doesn't cry wolf — it raises a senior **advisory**: a reviewer *should* question this. That's
> judgement a checklist can't give you, and a guessing model can't be trusted to give you."

**[APP → Copilot]** *(~20s — the bot, cited)*
> "Same discipline in the project bot. I'll ask it a real question about this project."
*(Type a question, e.g. "What is the concrete grade required for the coastal pile caps?" → send.)*
> "It answers in plain English — but every claim carries a **citation** back to the source document,
> and if the project data can't support an answer, it **abstains** and tells you, instead of making
> something up. It even flags when a question looks like an RFI that's been raised before."

**[APP → Commissioning QA]** *(~20s — proves the rule is platform-wide)*
> "The rule isn't just for documents. Commissioning: I upload a real cooling test log..."
*(Upload `docs/demo_files/Cooling-Commissioning-Log_DEMO.csv`.)*
> "...and every row gets a deterministic verdict against the thermal envelope — **pass**,
> within-allowable, or **fail**. This zone fails at 34 degrees and becomes a non-conformance with the
> clause attached. The one row it can't check, it marks not-checkable. It never invents a result."

**[APP → Project Timeline]** *(~25s — the payoff: where the 30 mm number bites)*
> "Now watch what that 30-mil footing actually does. This is the **project manager's** view. Every
> non-conformance, RFI, schedule risk, and shipment alert lands on **one connected timeline**,
> cross-linked. Our compliance catch doesn't sit in a report nobody reads — it shows up against the
> **schedule task** it threatens and the **procurement** it holds up. One number, caught in seconds,
> traced across the whole project. **That's** the intelligence layer the problem statement asked for."

---

## SEGMENT 4 — IMPACT + SCALE + CLOSE · deck · ~0:35

**[SLIDE 10 — Impact & Scale]**
> "What does it buy you? Value measured in engineer-hours saved per issue — with every assumption
> stated out loud, never hidden as a forecast. And it scales the honest way: you widen coverage by
> **adding a clause, never by retraining a model**. Twenty-one evals pass today; every number on
> screen is re-runnable."

**[SLIDE 11 — Vision]**
> "The direction is simple: the verification layer for every data centre built in India. Same
> deterministic core, more of the code library — and because the standards backbone speaks a standard
> protocol, any tool in an EPC stack can call it."

**[SLIDE 12 — Thank you / land on the thesis]**
> "So that's SiteMind. It doesn't ask you to trust an AI — it **shows its work, cites its source, and
> lets you check every call it makes.** For infrastructure with zero tolerance for error, that's the
> only kind of AI worth shipping. Thank you."

---

## TIMING SUMMARY
| Segment | Screen | Target |
|---|---|---|
| 1 · Hook + Problem | Deck 1, 2, 3 | 0:40 |
| 2 · The Rule | Deck 4, 5 | 0:30 |
| 3 · Live Demo | App: Overview → Compliance (30 mm NCR + advisory) → Copilot → Commissioning → Timeline | 2:20 |
| 4 · Impact + Close | Deck 10, 11, 12 | 0:35 |
| **Total** | | **~4:05** |

**Trim to 3:15 if needed:** cut the Commissioning beat and shorten the Copilot beat to a single
sentence. The 30 mm thread (Compliance → citation → advisory → Timeline) is the non-negotiable core.

## SHOT LIST / CLICK CUE-SHEET (tape this next to your monitor)
*(Running clock is cumulative. "Say" = the one line that must land in that beat; full wording is in
the segments above. Every number here is verified against the live backend, 2026-07-22.)*

| Clock | Screen / action | Exact click | Say (the beat) |
|---|---|---|---|
| 0:00 | **Deck Slide 1** (cover) | — | "India is about to build thousands of MW… I'm Awnikant, Team HashForge." |
| 0:18 | **Deck Slide 2** | → next | "One number: a footing at **30 mm** cover; code wants **50**." |
| 0:32 | **Deck Slide 3** | → next | "Generic AI **guesses** — invents citations. Can't allow that." |
| 0:40 | **Deck Slide 4** | → next | "One rule: **the model never decides.** 100% vs 58.5%, 0% hallucinated." |
| 0:58 | **Deck Slide 5** | → next | "Perceive · Decide · Explain. Let me show it catch our 30-mil footing." |
| 1:10 | **App → Overview** | click tab | "Live 48 MW Tier-III Chennai build, 10 modules. *Project* data is synthetic; standards + logic are real." |
| 1:25 | **App → Compliance** | click tab | "This is where a design engineer lives. Uploading a DBR it's never seen." |
| 1:32 | Upload dialog | drag **`Structural-Design-Basis-Report_DEMO.pdf`** | *(silent while it extracts)* |
| 1:38 | Extracted params visible | point at **source spans** | "It **perceives** — each param with the exact source sentence. Can't ground it? It abstains." |
| 1:52 | Run check | click **Run compliance check** | "Now it **decides**, in Python. **Three HIGH non-conformances** — top is the 30-mil footing." |
| 2:05 | Open NCR #1 | click **cover 30 mm NCR** | "F-12 at 30 mm vs IS 456 26.4.2.2's 50." |
| 2:15 | Citation provenance | expand citation, point at **`source_type`** | "Real digitised code text, not model memory. Verdict was Python; model only wrote the sentence." |
| 2:35 | Advisory finding | click **seismic I=1.0 ADVISORY** | "I=1.0 for a mission-critical DC. Not illegal → a senior **advisory**, not a false alarm." |
| 2:55 | **App → Copilot** | click tab, type Q, send | "Cited answer; abstains if the data can't support it. Flags seen-before RFIs." *(Q: coastal pile-cap grade)* |
| 3:15 | **App → Commissioning QA** | click tab, upload **`Cooling-Commissioning-Log_DEMO.csv`** | "Every row: **pass / allowable / fail** vs the thermal envelope. One row not-checkable — never invented." |
| 3:35 | **App → Project Timeline** | click tab | "The PM's view. That 30-mil catch lands on the **schedule task** + **procurement** it threatens. One number, traced." |
| 4:00 | **Deck Slide 10** | back to deck | "Value in engineer-hours, assumptions stated. Scale by **adding a clause, not retraining**. 21 evals pass." |
| 4:15 | **Deck Slide 11** | → next | "The verification layer for every data centre in India." |
| 4:25 | **Deck Slide 12** | → next | "It shows its work, cites its source, lets you check every call. Thank you." |

**Deterministic-result cheat-card (so you never misspeak on camera):**
- Compliance = **3 HIGH + 1 ADVISORY + 1 PASS**. Order on screen: cover → M25 grade → w/c → advisory.
  Clauses: 26.4.2.2 · 8.2.8 · 8.2.4.1 · (IS 1893) 7.2.3 · (PASS) 26.5.3.1. All `codebook_verified`.
- Commissioning = **5 pass · 2 within-allowable · 2 fail · 1 not-checkable** (10 rows).
- Never say "**Claude** extracts this" — say "**it reads and pulls** each parameter."

## PRE-FLIGHT CHECKLIST (before recording)
- [ ] Backend + frontend up; top-bar status pill is **green** (real backend, not mock).
- [ ] `docs/demo_files/` open in a file picker, ready to drag.
- [ ] Compliance page pre-scrolled; deck open in a second tab at Slide 1.
- [ ] Copilot: pre-decide the exact question and confirm it returns a **cited** answer (needs
      `HF_TOKEN` for retrieval — set it, or skip Copilot and keep the 3:15 cut).
- [ ] Silent dry-run upload of the DBR to warm any cold-start, then reset.
- [ ] Never open a `gaudi.local` link on camera; show clause text + `source_type` tag instead.

## FALLBACKS
- Slow upload on camera: findings are deterministic, so a pre-warmed run looks identical — do the
  silent dry-run first.
- Live site cold (Render free tier): record against localhost.
- If the compliance PDF ever misbehaves in extraction: use `Structural-Design-Basis-Report_DEMO.txt`
  (same 5 findings, guaranteed).
- Copilot returns no citation / HF_TOKEN unset: skip it, go straight from the advisory to
  Commissioning (or to Timeline for the 3:15 cut).

---

# ADD-ON SEGMENT — shoot separately, splice into the middle
*(These three surfaces — **Knowledge Graph, Codebook, Knowledge Base** — aren't in the first take.
Record them as three self-contained beats and drop each in at the splice point noted. Each stands
alone: no beat depends on the one before it, so you can use one, two, or all three, in any order that
fits your cut. Keep the same voice and the same honesty rules from the top of this script.)*

> **⚠️ Deck renumber (because of these features):** the deck (`v3.1.html`) now has a **new Slide 10,
> "The standards backbone,"** added right after the Knowledge-Graph slide. So in the **current** deck:
> Slide 9 = *"Traced, not guessed"* (graph), Slide 10 = *"The standards backbone"* (Codebook + KB),
> and the close shifts down: **Impact = Slide 11, Vision = Slide 12, Thanks = Slide 13.** Your first
> take used the old 12-slide deck where those were 10/11/12 — if you re-cut the close against the new
> deck, use 11/12/13. The add-on beats below reference the new slides by **name**, so you can't misfire.

> **Extra pre-flight for these beats (they need more than the base demo):**
> - **Knowledge Graph** — works with the base stack, **no extra flags**. Safe offline.
> - **Codebook** — needs the standards service running (`cd standards-service && ./run.sh`, port
>   **8010**) and the backend started with **`CODEBOOK_ENABLED=1`**. Without it the page shows a
>   "Codebook is off" state — don't film that.
> - **Knowledge Base** — needs **`RETRIEVAL_ENABLED=1`** and a **`HF_TOKEN`** in `backend/.env`
>   (hybrid retrieval uses HF embeddings). Do a silent warm-up query first; the first embed call is slow.

---

### BEAT A — Knowledge Graph  ·  ~25s  ·  **splice: right after the Project Timeline beat**
*(This is the visual punchline to "traced across the whole project." The Timeline lists the links;
the graph shows them. Same 30-mil footing — now as a node. Real, clickable, safe to film live.)*

**[APP → Knowledge Graph]**  *(optionally cut from **Deck Slide 9 — "Traced, not guessed"** first)*
> "And this is what 'connected' actually looks like. Not a vector database guessing at similarity —
> a **deterministic graph**. Let me click the node for that same footing."
*(Click the **Footing F-12** node. The Inspector panel opens on the right.)*
> "There it is. One click, and it traces to every place it lives: the **Design Basis Report** it was
> specified in, the **foundation shop drawing**, the **IS 456 clause** that governs it, and the **RFI**
> that's chasing it. This is permanent, clickable memory — so an issue is never stranded in a document
> nobody reopens. Every link here is a fact you can follow, not a similarity it hoped was right."

*Cheat: nodes are equipment ↔ spec ↔ standard ↔ RFI. Footing F-12 → Structural Design Basis Report,
foundation shop drawing, IS 456:2000 Cl. 26.4.2.2, RFI. Say "**traces**," never "predicts."*

---

### BEAT B — Codebook (the MCP standards service)  ·  ~30s  ·  **splice: right after the Compliance citation beat** (when you've just shown a real clause), *or* group with Beat C before the close
*(Answers the judge's unspoken question: "where does that 'real clause text' actually come from?"
It comes from Codebook — and Codebook is a standalone service any agent can call over MCP.)*

**[APP → Codebook]**  *(optionally cut from **Deck Slide 10 — "The standards backbone"** first)*
> "When the compliance check cited IS 456 a moment ago, it didn't pull that from a model's memory. It
> pulled it from **Codebook** — and Codebook is its own standalone service. SiteMind's backend is just
> one **client** of it, over **MCP**, the open tool protocol — so any other agent in an EPC stack could
> query the exact same verified standards."
*(Show the live corpus list, then run a search — e.g. `search_standards` for "nominal cover" — or open
the **Console** via the button.)*
> "Here are the real corpora it's indexed, and here's it returning verbatim clause text with a
> **reliability tier** on every result — `codebook_verified` for the digitised ones. Six-thousand-plus
> verbatim-checked chunks across seventeen Indian codes. This is the backbone, and it's **shareable, not
> locked inside one app.**"

*Cheat: Codebook = separate process (`standards-service`, :8010), MCP tools `list_corpora` /
`search_standards` / `get_clause`. Corpora include `manak_structural`. Say "**MCP client**," and only
claim "any agent can query it" — don't stage a fake external client unless you actually run one.*

---

### BEAT C — Knowledge Base (bring-your-own-documents retrieval)  ·  ~25s  ·  **splice: right after the Copilot beat** (same retrieval discipline, now on *your* corpus), or group with Beat B
*(Codebook holds the public codes; the Knowledge Base is where a company's **own** standards/QA docs go —
the guardrailed-retrieval story, made tangible.)*

**[APP → Knowledge Base]**
> "Codebook holds the public codes. But every operator has its **own** standards and QA documents. This
> is the **Knowledge Base** — I drop a company document into a private corpus..."
*(Upload a document into a named corpus — you can reuse `docs/demo_files/Structural-Design-Basis-Report_DEMO.pdf`
or any standards PDF.)*
> "...and now I can ask it a question, answered with **cited, verbatim chunks** — the same **hybrid
> BM25-plus-dense retrieval** the copilot uses, with the same rule: if the corpus can't support an
> answer, it **abstains** rather than fabricate one. Guardrailed retrieval, on your data. Not naive RAG."
*(Type a question the uploaded doc can answer; show the cited chunk.)*

*Cheat: KB page = upload → query, hybrid BM25+dense, cited verbatim chunks, abstains below the floor.
Say "**guardrailed retrieval, not naive RAG**." Needs `RETRIEVAL_ENABLED=1` + `HF_TOKEN`.*

---

**If you splice all three in:** the natural order in the live-demo section is
… Compliance citation → **[Beat B · Codebook]** → advisory → Copilot → **[Beat C · Knowledge Base]** →
Commissioning → Timeline → **[Beat A · Knowledge Graph]** → close. That adds roughly **80 seconds**, so
either let the video run to ~5:20 or trim the Commissioning beat to keep it near 4:30.
