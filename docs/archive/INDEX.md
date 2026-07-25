# Archive Index

Log of files moved into `docs/archive/` — never deleted, just superseded/stale.

- `CONTRACT.md` — archived 2026-07-21: Stale API contract (dated 2026-07-09, missing 5+ routers added since: Codebook, Codebook Console, Timeline, Clock, Supply Chain alerts/meta/equipment-spec-ncrs, Retrieval). Superseded by docs/features.md, which is verified current against the live nav and backend routers.
- `package.json` — archived 2026-07-21: Misplaced/broken root-level launcher config — its own content says it belongs at the repo root, but it never worked from docs/. The real workflow (per CHECKPOINT.md) is starting backend and frontend separately, per README.
- `run-full.sh` — archived 2026-07-21: Paired with docs/package.json — same broken-launcher issue. cd/path logic assumes standards-service/backend/frontend are siblings of its own location, but they're actually siblings of the repo root, not of docs/.
