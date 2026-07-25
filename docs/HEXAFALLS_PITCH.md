# The HexaFalls pitch — narrative arc + exact click-path per sponsor moment

This is the **HexaFalls-specific** companion to `docs/DEMO_STORY.md`. That doc still owns the core
5-pillar walkthrough (Compliance, Copilot, Schedule, Supply Chain, Commissioning) on the DC1 Chennai
data-centre project — nothing there changed. This doc adds the **new sponsor-track narrative** on
top: what to say, and exactly what to click, for each HexaFalls addition. Say the same up-front
honesty line from `DEMO_STORY.md` once, then don't re-manage it here.

## The one-liner

*"Every compliance decision on a megaproject — cited to the actual law, decided by auditable code
not a black-box model, and notarized on a public blockchain so it can never be quietly altered.
Runs fully offline, on-site."*

## The narrative arc (say this, in this order)

| Step | Sponsor tech | What it does | Why it's not decoration |
|---|---|---|---|
| **Perceive** | Gemini | Reads the uploaded document, extracts values + source spans, writes findings in plain English | Same LLM-never-decides boundary as always — Gemini is a drop-in prose provider, not a new trust boundary |
| **Retrieve** | Actian VectorAI DB | Offline/air-gapped semantic search over the digitised IS/CEA clause corpus | Matches the security posture of a real hyperscale or government site where data can't leave the premises |
| **Decide** | (core, unchanged) | Certified rule OR computed-draft (LLM reads the rule, Python computes) | The actual moat — now scalable past hand-written rules |
| **Remember** | MongoDB Atlas | Every finalized decision written once, append-only, to an audit ledger | The "project memory" flat files never had |
| **Prove** | Solana (devnet) | Each ledger entry's hash anchored on-chain | Anyone can independently verify a record wasn't altered — the anti-corruption mechanism, concrete and demoable |
| **Reach the field** | Telegram + ElevenLabs | A site engineer asks by voice, in Hindi/regional language, gets a cited voice answer back | Intelligence in the field, in the language of the field, still cited to the real code |
| *(edge only)* | LangGraph | Multi-turn Copilot that routes across pillars, remembers context | The only place a general agent framework runs — it routes and phrases, never decides |

## Exact click-path per sponsor moment

### Gemini (Perceive)
1. `/compliance` → upload a submittal (or use the pre-loaded DC1 project).
2. Point out a finding's prose (`why_it_matters`/`recommendation`) — that's Gemini-written, not
   templated. Toggle: `LLM_PROVIDER=gemini` in `backend/.env` (already the HexaFalls default).
3. For the **computed-draft tier**: find/trigger an NCR whose `verdict_tier` badge reads "DRAFT ·
   confirm reading" (amber) instead of "Certified · pre-vetted" (green) — click it open to show the
   `extracted_rule` Gemini read out of the real clause, and the `computed_detail` Python actually
   computed from it.

### Actian VectorAI DB (Retrieve)
1. Ensure the container is running (`docker-compose.actian.yml`) and
   `RETRIEVAL_VECTOR_STORE=actian RETRIEVAL_ENABLED=1` is set for the backend.
2. `/knowledge-base` → point at the "Vector store: Actian VectorAI (offline)" chip (vs. the default
   "numpy (in-memory)" label when the flag's off).
3. Run a query; the result is served by the same offline Actian instance, not a numpy in-process
   matrix — say this out loud, it's not visually different, which is the point (drop-in swap).

### MongoDB Atlas (Remember)
1. `/audit` → the table itself IS the demo: every row is a real, already-recorded compliance
   decision, one row per event, never duplicated (idempotent via `content_hash`).
2. Point out the backend badge: "MongoDB Atlas" (green) if `MONGODB_URI` is set, or "Local ledger —
   Atlas not configured" (amber) otherwise — both work identically from the UI's perspective.
3. Click "Re-seed demo data" to show it's idempotent — the count doesn't change on a re-run.

### Solana (Prove) — the money shot
1. On `/audit`, pick a row, click **Anchor** → a real devnet transaction fires; the Solana chip
   becomes a link to `https://explorer.solana.com/tx/<sig>?cluster=devnet` — click through to prove
   it's a real chain, not a mock.
2. Click **Verify** → green "record intact · chain match".
3. **The reveal**: directly edit that event's `severity` (or any field) in the local ledger
   (`backend/data/audit_events.jsonl` if running without Atlas) to simulate tampering, then click
   **Verify** again → `mongo_intact: false` (the local record no longer matches its own hash) while
   `chain_intact: true` (the ORIGINAL hash really was anchored on Solana) — say explicitly: *"you
   don't have to trust our database to know this was tampered with; the chain proves what the
   original hash really was."* This is the single most concrete anti-corruption demo in the product.
4. Fallback if `SOLANA_ENABLED=0`: the chip reads "Solana disabled" and the ledger still works —
   say so, don't hide it.

### Telegram + ElevenLabs (Reach the field)
1. On a phone, message `@Sitemind_bot` (or whatever bot the deployed `TELEGRAM_BOT_TOKEN` maps to).
2. Send a plain English text question first (safest — no live-transcription risk on stage) — get a
   cited text reply + a synthesized voice note back.
3. If comfortable live: send a Hindi voice note (e.g. "transformer ka clearance kitna chahiye?") →
   bot transcribes (ElevenLabs Scribe), translates (Gemini), answers (existing cited Copilot),
   translates back, and replies with a Hindi voice clip + the English citation.
4. Ask an out-of-scope question too — the honest abstain ("No confident answer in the project
   corpus — raising this as an RFI") is itself worth showing; it proves the bot isn't just agreeing
   with whatever's asked.

### LangGraph (edge only)
1. Set `COPILOT_AGENT_ENABLED=1` + a Gemini key, restart the backend.
2. `POST /api/copilot/chat` with a multi-pillar question ("any open NCRs on the submittal, and is
   the cooling shipment delayed?") — the agent calls `get_open_ncrs` + `get_supply_chain_status` and
   composes one cited answer across two pillars.
3. Follow up with a pronoun-dependent question ("what about the transformer?") using the same
   `thread_id` — it resolves via conversation memory, not a fresh unrelated answer.
4. Say explicitly: *"this is the only place in the codebase a general agent framework runs — it
   routes and phrases; it never touches the verdict pipeline."*

## Honesty guardrails (say once, keep saying)

- "Tamper-**evident** / independently verifiable" — never "impossible to corrupt." The mechanism
  proves a record wasn't *silently* altered; it doesn't police human intent or prevent someone from
  simply not anchoring a record in the first place.
- "AI-drafted, engineer-confirmed" for computed-draft findings — never presented as certified.
- All project data is synthetic/representative, modelled on public tenders — the standards, the
  checking logic, and the crypto/audit mechanisms are real.
- No asserted numbers — every metric quoted comes from a real eval run in `backend/eval/`.
- If a sponsor integration's flag is off (the honest default for most judges' first run), say so
  plainly and show the graceful fallback rather than skip past it — "unconfigured, here's what it
  looks like off" is itself a demonstration of the degrade-gracefully design principle running
  through this whole project.
