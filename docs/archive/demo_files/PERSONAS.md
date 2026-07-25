# Who actually uses this — one persona per pillar

UX is the rubric's most orphaned criterion (15% weight, no doc addressed it before this one). Most pages in
this app are read-only dashboards; this file exists to answer "read-only *for whom*, doing *what* on a
working Tuesday" — a persona a judge can picture, not a title on a slide.

## Compliance Agent → the QA/QC or structural design-review engineer

Reviews L&T's submittals for DC1 as they land — foundation drawings, rebar schedules, cover details — one
of maybe 40 active submittals in flight this week, each 30-80 pages, cross-checked by hand against IS 456
today. On a Tuesday: a revised shop drawing (`DC1-02-SD-0142-R1`) lands in the register. Instead of
re-reading the whole document to find what changed, they open `/compliance`, run the check, and land
directly on the one line that matters (30mm cover vs 50mm required) with the governing clause already
cited — the six days RFI-CIV-073 took to surface manually, collapsed to the time it takes to click "check."
They don't trust a bare pass/fail; they click through to the cited clause text before signing off, which is
exactly the workflow the citation-first design assumes they'll do.

## Project/RFI Copilot → the site engineer or document controller fielding RFIs

Owns the RFI log for one discipline package and gets asked the same three questions a week by different
subcontractors, plus the genuinely new ones. On a Tuesday: a subcontractor asks a question that sounds
familiar. Instead of grep-ing through six months of RFI PDFs by memory, they ask `/copilot` and get a cited
answer plus a "this was asked before, see RFI-EL-112" flag — the exact failure mode ("did we already answer
this?") that costs a coordination meeting to resolve manually.

## Schedule → the planning engineer running the CPM

Owns the master schedule in P6 or Primavera and re-runs the critical path whenever a vendor status changes,
which is often invisible until it's already a problem. On a Tuesday: a long-lead LV switchgear vendor
reports a slip. Instead of waiting for that to surface as a missed milestone weeks later, `/schedule`
already shows it as an at-risk activity with a real recomputed project-finish impact and — critically — the
three mitigation options the coordinator generated (procurement alternative, float/resequencing, resource
recovery), including the ones that don't work, so they're not starting the mitigation conversation from a
blank page.

## Supply Chain → the procurement or logistics lead

Tracks shipment status across tiers for equipment that's usually invisible until it's late — the classic
"vendor said two weeks, it's been six" problem the brief names as a leading cause of overruns. On a Tuesday:
`/supply-chain` shows SHP-002 flagged at-risk with the actual root cause three tiers deep (a tier-2
battery-cell customs delay, not just "vendor is late"), a computed viable alternative with its real cost
premium, and a clickable link straight to the RFI and schedule activity it affects — turning "is this going
to be a problem" from a phone-call-to-find-out into an on-screen answer.

## Commissioning QA → the MEP/commissioning engineer

Runs functional performance tests during the commissioning phase and has to certify results against a
governing standard, then produce a quality package that survives an owner's-engineer audit. On a Tuesday:
they upload the cooling test log; `/commissioning` returns a deterministic PASS/allowable/FAIL per zone
against the cited thermal envelope, generates the NCR for the failing zone automatically, and compiles an
exportable as-commissioned package — instead of manually cross-referencing each reading against a table and
writing the NCR by hand. They see, and would be expected to disclose to their own client, the
cross-source-compiled caveat on this specific envelope (ASHRAE's book is paywalled) before relying on it for
a real certification decision.

## What this doesn't cover yet

No persona for the Codebook Console (corpus/document browsing) or Knowledge Base — those are closer to
internal/platform-admin surfaces than a named field role's daily workflow, which is honestly why they read
as "architectural debt documented as a feature" in `docs/features.md` rather than a pillar with its own
persona. That's a fair characterization, not an oversight here.
