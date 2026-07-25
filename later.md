# Later — deferred live verification (not blocking the build)

## Workstream F1 — ElevenLabs + Telegram field bot: BUILT, every component live-verified, full round-trip needs a real phone message (2026-07-24)

New standalone `telegram-bot/` (does not touch the deterministic core — pure
client of the existing, unchanged `/api/copilot/ask`). `bot.py` handles both
text and voice messages: voice → ElevenLabs Scribe STT → Gemini translation
to English (if needed) → `POST /api/copilot/ask` → if the Copilot abstains
(`sources` empty) reply the honest "No confident answer in the project
corpus — raising this as an RFI" (never fabricate) → else translate the
answer back to the user's language via Gemini → ElevenLabs TTS → reply with
voice note + text + citation links.

**Confirmed against the REAL installed packages** (`python-telegram-bot==22.8`,
`elevenlabs==2.59.0`), not guessed:
- Real bot token verified via `getMe` → `@Sitemind_bot` is live.
- **Live TTS call** (`text_to_speech.convert(..., output_format="opus_48000_128")`)
  — inspected the raw bytes: `OggS` magic header, confirmed via `file` as
  "Ogg data, Opus audio" — exactly the container Telegram's `sendVoice`
  requires. This was a genuine unknown (ElevenLabs' output-format docs don't
  say whether `opus_48000_*` is a bare Opus stream or a real Ogg container)
  resolved by direct empirical inspection rather than guessing.
- **Live STT call**: fed that same TTS output back into
  `speech_to_text.convert(model_id="scribe_v1", file=(...))` → got back the
  exact transcript (`"Testing one, two, three."`) + `language_code: "eng"` —
  confirms the full voice round-trip shape end-to-end.
- Confirmed `AsyncClient`-equivalent `File.download_as_bytearray()` is the
  real python-telegram-bot API for pulling a voice note's bytes (not guessed).
- Gemini translation reuses the exact `genai.Client(...).models.generate_content`
  pattern already proven in `backend/app/llm.py` (Workstream A) — a live
  translation call during this session hit the SAME known 20/day free-tier
  quota wall documented above (`gemini-3.6-flash`, 429 RESOURCE_EXHAUSTED).
  This is not a new bug; per the "build, don't over-verify" rule, not retried.
  `translate_to_english`/`translate_from_english` both fail closed (return the
  original text unchanged) on any Gemini error, so the bot still answers in
  whatever language it received without translation once quota resets.
- Bot started for real (`nohup python bot.py &`) and is running in the
  background right now, long-polling Telegram — confirmed in its own log:
  `getMe` 200, `deleteWebhook` 200, `Application started`.

**NOT yet verified: the full live round-trip from a real phone.** Every stage
above was proven individually and live, but no one has actually messaged
`@Sitemind_bot` from a Telegram client yet. **To resume:** message
`@Sitemind_bot` with (a) a plain English text question that's in the seeded
corpus (should get a cited text reply + a synthesized voice note), (b) a
question clearly outside the corpus (should get the honest abstain message,
not a fabrication), and (c) if quota allows, a Hindi voice note (should
transcribe, translate, answer, translate back, and reply with a Hindi voice
clip) — matching the plan's own §F1 "Verify" checklist exactly. Backend
(`cd backend && ./run.sh`) must be running on `:8000` for the bot to answer
anything other than "backend unreachable".


Session policy going forward: build features, verify with unit tests / eval
suite / mocked calls where possible, but don't burn live LLM quota on
exhaustive manual end-to-end re-checks. Come back to this list once quota
allows, or ask before spending more live calls.

## Gemini quota constraint (discovered 2026-07-24)

The configured `GEMINI_API_KEY` is a **free-tier** Google AI Studio key.
`gemini-flash-latest` currently resolves to the underlying model
`gemini-3.6-flash`, which is capped at **20 requests/day** on the free tier
(`GenerateRequestsPerDayPerProjectPerModel-FreeTier`). That quota was
exhausted during this session's testing (429 RESOURCE_EXHAUSTED). Separately,
`gemini-3.5-flash` (the model originally chosen) was also seen returning
503 UNAVAILABLE (transient overload) earlier in the session — a different,
unrelated issue from the 429 quota cap.

Implication: don't script repeated live Gemini calls (health checks are fine;
compliance/copilot calls that hit the LLM are not) until either the daily
quota resets or a higher-quota/billing-enabled key is supplied.

## 2026-07-25 re-check: Gemini free-tier quota still exhausted

Re-probed with a single minimal `generate_content(model="gemini-flash-latest",
contents="Say OK")` call before attempting today's requested B2 live
re-verification — still `429 RESOURCE_EXHAUSTED` (same free-tier 20/day cap
as 2026-07-24). Per the standing "don't burn tokens/quota" rule, did NOT
retry further or attempt the full computed_draft round-trip below. Also
confirmed live during today's Telegram-bot fix work (see trail.md #27): a
real `/api/copilot/chat` call reached `agent.invoke()` and hit the same 429,
now caught gracefully (previously would have 500'd — fixed).

What WAS re-confirmed today, all Gemini-free:
- `pytest tests/test_rule_eval.py` — 20/20 still passing.
- All 18 `eval/run_*_eval.py` scripts — still 100% accuracy across the board
  (alerts, commissioning, cost_risk, electrical, equipment_spec, run_eval,
  extraction, impact, mitigation, schedule, supply_chain, timeline, weather,
  workforce), plus cross_corpus (26/26) and actian_parity (5/5) re-run
  separately for the manak_structural rename (trail.md #25).
- Certified-tier verdicts (the non-LLM, pre-vetted `checks.py` path) directly
  confirmed via `compliance.evaluate("DC1-02-SD-0142-R1")` — footing cover
  (Cl 26.4.2.2) and marine concrete grade (Cl 8.2.8) both still resolve
  correctly with `verdict_tier="certified"`.

**Still blocked, still needs a live Gemini call once quota resets**: the
`computed_draft` tier's full HTTP round-trip (item 1 below) — the one part
of B2 that genuinely requires the LLM to read a rule out of a real clause.
Task #11 in the tracker is left `pending`, not marked done, because this
genuinely hasn't been re-confirmed live today — only its already-proven
2026-07-24 mechanism (rule_eval unit tests, a real but earlier Gemini call)
still stands.

## Deferred verification items

1. **B2.7 — curated demo clause, full HTTP round-trip.** The mechanism is
   already proven correct:
   - `rule_eval.py`: 20/20 unit tests green (all kinds + unsafe-expression
     rejection + never-raises behavior).
   - `_computed_draft_finding()`: proven end-to-end via a mocked corpus hit
     (`is1893_part3_2014` clause B-1.1, "Minimum grade of concrete should be
     M25") with a REAL (unmocked) Gemini call — correctly extracted
     `kind=compare, operator=">=", threshold=25.0`, correctly gated the
     verbatim `clause_phrase`, and `rule_eval.evaluate()` correctly computed
     both FAIL (value=20) and PASS (value=30).
   - The "none" path (clause states no checkable rule) was also proven via a
     real Gemini call against a real retrieved clause (IS 456 9.1.2
     "Information Required" — correctly returned `kind=none`).
   - Added demo param `DBP-11` to
     `backend/data/project_docs/design_basis_params.json`
     (`min_grade_of_concrete = 20 MPa`, element_type
     "seismically-strengthened member") specifically because its retrieval
     query surfaces `is1893_part3_2014:B-1.1` within the top-3 hits (rank 3,
     score ~0.616) — the multi-candidate loop in `_computed_draft_finding`
     tries hits in order and should land on it.
   - **Not yet confirmed**: a live `POST /api/compliance/check` call for
     `DC1-02-DBR-0001-R2` with `COMPLIANCE_RULE_EXTRACTION=1
     RETRIEVAL_ENABLED=1` produced `verdict_tier=unresolved` instead of
     `computed_draft` on 3 consecutive attempts — but all 3 failed on the
     FIRST candidate hit (`irs_cbc_1997 14.6 Shear`, an irrelevant clause)
     with a 429 quota error, not a real "no rule" answer, so the loop never
     got to try candidate #2/#3 (which include the real B-1.1 clause) with a
     working LLM call. **Once quota resets, just re-run:**
     ```
     COMPLIANCE_RULE_EXTRACTION=1 RETRIEVAL_ENABLED=1 <run backend>
     curl -s -X POST http://localhost:8000/api/compliance/check \
       -H 'Content-Type: application/json' \
       -d '{"document_id":"DC1-02-DBR-0001-R2"}' | python3 -m json.tool
     ```
     and check the NCR for `element: "Seismic retrofit column jacket
     (typical)"` — expect `verdict_tier: "computed_draft"`, a populated
     `extracted_rule`, and `computed_detail` showing `20.0 >= 25.0 -> FAIL`.
     If it's still `unresolved`, read the `why_it_matters` reason string to
     see which gate actually failed before assuming the mechanism is broken.

2. **B2 full Verify checklist** (plan's own verify block) — re-run once (1)
   above is confirmed:
   - `python -m eval.run_eval` + all `run_*_eval.py` still byte-identical
     with the flag off (last confirmed after B2.5 — should still hold, no
     eval-touching code changed since, but worth one more pass before
     declaring B2 done).
   - `pytest backend/tests/test_rule_eval.py` green (already confirmed,
     20/20).
   - Footing cover 40mm still returns `certified` (already directly
     confirmed via a Python-level check, not re-verified via live HTTP).

3. **Workstream B — Gemini Vision** (reading scanned drawings/photos): **explicitly
   skipped for this session per user request** (2026-07-24), not started. Will
   also need live Gemini calls to verify once picked back up — check remaining
   daily quota before starting, or ask the user for a fresh/paid key first
   rather than discovering the same 429 mid-workstream.

4. Frontend two-half panel (B2.6) has been typechecked (`tsc --noEmit` clean)
   but **not yet visually verified in a running browser** — no dev server
   was started this session. Before calling B2.6 fully done, run
   `npm run dev`, open `/compliance`, and look at an actual `computed_draft`
   NCR card once (1) above produces one.

## Workstream C — Actian VectorAI DB: RESOLVED, fully verified live (2026-07-24)

Initial blocker (community-mirror image `williamimoh/actian-vectorai-db` had
an expired beta license) was resolved when the user obtained a real Actian
Community Edition + 30-day trial license and the OFFICIAL image
(`actian/vectorai:latest`). Switched `docker-compose.actian.yml` to that image
(ports `6573-6575`, volume `./actian_data:/var/lib/actian-vectorai`, env
`ACTIAN_VECTORAI_ACCEPT_EULA=YES`). Hit and fixed one more real bug along the
way: Docker auto-created the bind-mount host directory as root, but the
container runs as uid 999 — fixed via a throwaway `alpine` container doing
`chown -R 999:999` on the host path (couldn't `chown` directly as a non-root
host user).

**Confirmed live, real, licensed:** `docker logs actian_vectorai_db` shows a
clean boot — Community Edition active, `allowed=5000` vector cap, gRPC
listening on `6574`, REST on `6573`, LocalUI on `6575`. Our
`ActianVectorStore` connects successfully
(`client.health_check()` → `{'title': 'Actian VectorAI DB', 'version':
'Actian VectorAI DB 1.0.2 / VDE 1.0.2'}`).
`RETRIEVAL_VECTOR_STORE=actian RETRIEVAL_ENABLED=1 python -m
eval.run_actian_parity_eval` → **5/5 PASS** against the real container: both
known-answer queries' top-hit `document_id` matches the numpy reference
exactly (`is456_2000`, `is1893_part1_2016`), and the gibberish-query
abstention gate holds. `ACTIAN_URL` default is `localhost:6574` in both
`config.py` files.

**Still open (low priority, not blocking):**
- The 30-day trial (1M vectors) needs the license key
  (`X3RMY-36YV3-C43P6-PPVBC-BR8D3-JJ677`) pasted into the LocalUI at
  `http://localhost:6575` — a browser step only the user can do. Right now
  the container is running in Community Edition mode (5000-vector cap),
  which the parity eval doesn't need (it only ingests the corpora already
  built) but the full 6,206-chunk structural corpus would need the trial's
  1M cap if ingested wholesale — see the plan's own "5K-vector constraint"
  section for the fallback options.
- `docker-compose.actian.yml`'s `version: '3.8'` key is flagged obsolete by
  Docker Compose (cosmetic warning only, left as-is since it was the user's
  exact provided config).

## Workstream D — MongoDB Atlas audit ledger: DONE, fully verified (2026-07-24)

Built `app/audit.py` (content_hash + record_event/get_events/get_event/
update_solana, Mongo-with-JSONL-fallback), `app/audit_api.py` (GET /api/audit,
GET /api/audit/{id}, POST /api/audit/seed), `AuditEvent`/`SolanaAnchor`
schemas, wired real-upload NCRs into the ledger in `compliance.py`
(`check()` + `check_stream()`), a startup seed hook in `main.py`, and the
`/audit` frontend page + nav entry + `getAudit()`/`seedAudit()` API calls.

**Real bug found and fixed during verification:** the original design hashed
the ENTIRE NCR payload for idempotency, including LLM-generated prose
(finding/why_it_matters/corrective_action) — but Gemini doesn't produce
byte-identical text across calls even at temperature 0, so re-evaluating the
exact same decision kept minting "new" audit rows forever (caught this
because running `pytest` twice against a live Gemini-backed server grew the
ledger 6→13 lines instead of staying flat). Fixed by adding an optional
`dedup_key` parameter to `record_event`/`event_exists`: the full NCR is still
stored as `payload`, but the content_hash used for dedup is computed over
`ncr_dedup_key()` — the NCR minus its four prose fields. Re-verified: running
the full pytest suite twice in a row now correctly produces a stable ledger
count (idempotent), confirmed via the live `/audit` page in a real browser
(Playwright) too — clicking "Re-seed demo data" doesn't duplicate rows.

MONGODB_URI was never provided this session, so everything was verified
against the JSONL fallback path only (by design — that path IS the graceful
degradation the plan requires). If/when a real MongoDB Atlas URI is supplied,
re-run the same checks (`GET /api/health` → `audit_backend: "mongodb"`, the
`/audit` page, double-seed idempotency) against it — the code path is
identical, only `audit._mongo_collection()` needs a reachable cluster to
exercise it for real.

## Workstream E — Solana devnet notarization: RESOLVED, fully verified live (2026-07-24)

**Update:** user funded the generated devnet keypair (5 SOL via
https://faucet.solana.com). Full chain-side round trip now verified live —
see below. The original build note is kept underneath for context.

**Live verification, end to end:**
- Set `SOLANA_ENABLED=1` + the funded keypair's secret in `backend/.env`,
  restarted the backend.
- `POST /api/audit/AUD-ba49ab669ce7/anchor` → real devnet transaction
  `2wjsGR6xjvnnr7wChYbc6Gdgsy5MmaEEj1ijrMgisR5rU9fL9TeAL3N8nDjyQzc2tbewb6XhnphA9hYKCBW4wXce`,
  slot 478588513. Fetched it back directly via `AsyncClient.get_transaction`
  and confirmed the program log literally contains the event's
  `content_hash` (`d14a6e74bd05f0786610ab429e8df9f4c5aff8f17f6d665aad9e5268de41b3de`).
- **Found and fixed the exact bug flagged as the likely failure point below**:
  `POST .../verify` initially returned `chain_intact: false` despite the
  visibly-correct on-chain data. Root cause: `AsyncClient.get_transaction(...,
  encoding="base64")` in `solana==0.40.1`/`solders==0.28.0` does NOT return a
  base64 string/tuple — it returns an already-parsed `VersionedTransaction`
  object. `_extract_memo_bytes_base64` was only handling the string/tuple
  shapes it guessed at build time, so it silently extracted nothing. Fixed by
  handling the `VersionedTransaction` case directly in `notary.py`. Also fixed
  `_extract_memo_from_logs`: the real log format is `Program log: Memo (len
  64): "<hash>"`, not the bare hash — added a regex to unwrap it. After the
  fix, `POST .../verify` → `{"mongo_intact": true, "chain_intact": true}`.
- Re-ran the full tamper demo with a real anchor in place: edited the same
  event's `severity` in the JSONL ledger → re-verified →
  `{"mongo_intact": false, "chain_intact": true}`. This is the strongest
  possible demo result: the local record is provably altered
  (`mongo_intact: false`), while Solana independently proves what the
  *original* hash really was (`chain_intact: true` — the stored
  `content_hash` field itself, untouched, still matches on-chain) — i.e. you
  don't have to trust SiteMind's own database to prove tampering happened.
  Restored the ledger to its correct state afterward.
- Confirmed in the browser too (Playwright): the `/audit` page's row for this
  event shows a clickable Solana Explorer link and, after clicking Verify,
  renders "record intact · chain match" in green.

`notary.py` is now considered live-verified, not just built-against-real-APIs.

---

### Original build note (superseded by the live verification above)

Workstream E — Solana devnet notarization: BUILT, Mongo-side proven live, chain-side blocked on funding (2026-07-24)

Built `app/notary.py` (`anchor_hash`/`verify_anchor`, SPL Memo program, gated
on `SOLANA_ENABLED`), `scripts/solana_setup.py`, `SOLANA_*` config vars, and
extended `audit.py`/`audit_api.py`/`AuditEvent` with `hashed_fields` (the
exact dict `content_hash` was computed over, stored separately from `payload`
so `verify_integrity()` can recompute a REAL match) plus 3 new endpoints
(`POST .../anchor`, `POST .../anchor-pending`, `POST .../verify`) and the
frontend Anchor/Verify buttons + "Anchor all pending".

**Confirmed against the REAL installed packages** (`solana==0.40.1`,
`solders==0.28.0` — resolved with zero conflicts against every existing pin):
- This version only ships `solana.rpc.async_api.AsyncClient` — no sync
  client — so `notary.py` is async throughout (fine: anchoring is only ever
  called on-demand from a button click, never a hot path).
- The exact sign/send pattern (`Instruction(program_id, data, accounts)` →
  `Message.new_with_blockhash(...)` → `VersionedTransaction(message,
  [keypair])` → `client.send_transaction(tx)`) came straight from
  `Message.new_with_blockhash`'s own doctest example, not a guess.
- `Keypair()` generates a random devnet keypair; `str(kp)` is the base58
  secret; `Keypair.from_base58_string(...)` reloads it.

**Mongo-side integrity — fully proven live, including the actual demo
scenario**: reseeded a fresh ledger, ran `POST /api/audit/{id}/verify` →
`mongo_intact: true`; then directly edited that SAME event's `severity` field
in the JSONL ledger (simulating the plan's "someone edited the record"
scenario) → re-ran verify → `mongo_intact: false`. This is the anti-corruption
demo working exactly as the plan describes, confirmed end-to-end including
in the browser (Playwright: clicked Anchor/Verify buttons, saw the green
"record intact" badge render correctly).

**Chain-side (actual Solana anchoring) — NOT live-verified.** The public
devnet airdrop faucet (`api.devnet.solana.com`'s own `requestAirdrop` RPC)
returned a hard 429 on every attempt this session:
```
{"error":{"code":429,"message":"You've either reached your airdrop limit
today or the airdrop faucet has run dry. Please visit
https://faucet.solana.com for alternate sources of test SOL"}}
```
Ran `scripts/solana_setup.py` anyway — it generated a real devnet keypair and
printed everything needed:
```
Pubkey:        3rjsQ56bavbAVpVZLvd9QxLxC426y8caatHHvQvXqhHc
Base58 secret: 61NLGZpvnKx8s5uqXUetCGuFz2APRQJhRyayyBYJE83tHGntCNq3ZNQBQTGCxx2im7PCR1A99zF2REAh6ZwuNCu8
```
**To resume:** fund this pubkey via the web faucet
(https://faucet.solana.com, paste the pubkey above) or send it devnet SOL any
other way, then set in `backend/.env`:
```
SOLANA_ENABLED=1
SOLANA_SECRET_KEY=61NLGZpvnKx8s5uqXUetCGuFz2APRQJhRyayyBYJE83tHGntCNq3ZNQBQTGCxx2im7PCR1A99zF2REAh6ZwuNCu8
SOLANA_RPC_URL=https://api.devnet.solana.com
SOLANA_CLUSTER=devnet
```
restart the backend, click "Anchor" on any audit event, and confirm the tx on
`https://explorer.solana.com/tx/<sig>?cluster=devnet`. **`verify_anchor()`'s
on-chain memo-matching logic is UNTESTED against a real transaction** — it
tries decoding the base64-encoded transaction bytes first (the robust path)
and falls back to string-matching the human-readable program log (see
`_extract_memo_bytes_base64`/`_extract_memo_from_logs` in `notary.py`) since
I could not confirm the exact response shape without a funded keypair to
anchor with. First live anchor+verify should be watched closely — if
`chain_intact` comes back `false` for a transaction that visibly succeeded on
Explorer, the bug is almost certainly in one of those two extraction
functions, not in `anchor_hash` itself (which has no such ambiguity — it just
sends bytes).
