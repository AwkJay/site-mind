# Spatial Compliance — floor-plan ingestion, 2D floor map, and cited spatial verdicts

**Date:** 2026-07-25
**Status:** approved, ready for implementation
**Scope:** one new capability inside the existing Compliance pillar. No existing behaviour changes.

---

## 1. Goal

A user uploads a Design Basis Report / layout narrative to the Compliance page. SiteMind:

1. extracts the **spatial** parameters (room sizes, equipment clearances, exits, travel distances),
2. computes pass/fail in deterministic Python against **real, verbatim** CEA/NBC clauses,
3. renders a **2D floor map** and pins each finding onto the geometry that failed.

The existing scalar compliance path (`ingest.py` → `checks.py`) is untouched and keeps working exactly as it does today.

## 2. Non-negotiable constraints (inherited from the project thesis)

| Constraint | How this feature honours it |
|---|---|
| The LLM never computes a verdict | All 6 spatial rules are Python threshold functions in `checks_spatial.py`. |
| Never invent a clause | 6 clauses digitised **verbatim** from PDFs already on disk. No paraphrase. |
| No asserted numbers | `backend/eval/run_spatial_eval.py` produces every reported number. |
| OFFLINE_MODE is the safe default | Extraction is **regex-first**. LLM extraction is flag-gated and optional. The whole feature works with zero API keys. |
| Span gate | Every extracted value's `source_quote` must be a literal substring of the document **and** contain the value, else the value is dropped. |
| Abstain rather than guess | No spatial data → say so. Inferred geometry → never produce a verdict from it. |

## 3. The stated-vs-inferred rule (the core honesty mechanic)

A document states *"Data Hall 1 measures 30 m × 20 m"*. It does **not** state where that room sits.

- Every room carries `dimension_source` and `position_source`, each `"stated"` or `"inferred"`.
- Dimensions are only ever `"stated"` — a room with no stated dimensions is not drawn to scale (see §7.3).
- Positions are `"stated"` only when the document gives an explicit relation the layout engine consumed; otherwise `"inferred"`.
- **A check may only read values whose provenance is `"stated"`.** A rule that would require an inferred position emits an `Abstention`, never a verdict.
- Inferred rooms render hatched + dimmed with a legend entry saying why.

## 4. The clause set

New file `backend/data/standards/spatial_clauses.json` — same object shape as the existing `clauses.json` entries (`key, standard, title, clause, text, verify_url, domain, source_type`). Separate file so the existing 24 clauses and every existing eval report stay byte-identical.

`backend/app/standards.py::_load()` is extended to merge `spatial_clauses.json` into the same lookup dict. `get_clause()` / `all_clauses()` keep their signatures.

| key | standard | rule expressed | provenance |
|---|---|---|---|
| `CEA_2010_37iii_a` | CEA (Measures Relating to Safety and Electric Supply) Regulations, 2010 | clear space in front of a switchboard ≥ 1 m | `backend/data/project_docs/CEA_Safetycons.pdf` p.22 |
| `CEA_2010_37iii_b` | ″ | space behind a switchboard < 20 cm **or** > 75 cm | ″ |
| `CEA_2010_37iii_c` | ″ | rear space > 75 cm ⟹ passage from either end, clear to 1.8 m height | ″ |
| `NBC2016_4.4.2.2a` | National Building Code of India 2016, Part 4 | travel distance shall not exceed Table 5 | `standards/NBC2016-Part-IV.pdf` p.29 |
| `NBC2016_4.4.2.2c` | ″ | dead-end corridor ≤ 6 m (educational/institutional/assembly), else ≤ 15 m | ″ p.29 |
| `NBC2016_4.4.2.3` | ″ | exit capacity — required width from occupant load × Table 4 mm/person | ″ p.30 |

`domain: "spatial"` on all six. `source_type: "primary_native_pdf"`.

Two lookup tables also digitised, as separate JSON alongside:
`backend/data/standards/nbc_tables.json` → `{"table_4": {...}, "table_5": {...}}`, each row keyed by NBC occupancy group, values verbatim, plus a `source_page` field.

**Provenance note:** the NBC PDF is a BIS-licensed copy watermarked to a third party. Short verbatim clause quotations go into `spatial_clauses.json` (same practice as the existing 24 clauses). **The PDF itself must not be committed** — add `standards/*.pdf` to `.gitignore`.

## 5. Backend contract

### 5.1 `backend/app/spatial/schemas.py`

```python
Provenance = Literal["stated", "inferred"]

class Extracted(BaseModel):
    value: float
    unit: str                 # "m" | "mm"
    source_quote: str         # verbatim sentence from the document
    verified: bool            # span gate result; False values are dropped before checks

class Room(BaseModel):
    id: str                   # slug, e.g. "data_hall_1"
    name: str
    zone: Literal["server_hall", "electrical", "cooling", "corridor", "other"]
    width_m: Extracted | None
    length_m: Extracted | None
    occupancy_group: str | None      # NBC group, e.g. "industrial"
    occupant_load: Extracted | None

class Equipment(BaseModel):
    id: str
    room_id: str
    kind: Literal["switchboard", "lv_panel", "transformer", "genset", "crac", "rack_row"]
    count: int | None
    front_clearance_m: Extracted | None
    rear_clearance_m: Extracted | None
    rear_passage_height_m: Extracted | None

class ExitDoor(BaseModel):
    id: str
    room_id: str
    width_mm: Extracted | None
    wall: Literal["north", "south", "east", "west"] | None

class SpatialFact(BaseModel):
    kind: Literal["travel_distance", "dead_end_corridor", "corridor_width"]
    room_id: str | None
    value: Extracted

class Abstention(BaseModel):
    what: str                 # "travel distance for Data Hall 1"
    why: str                  # plain-language reason, shown in the UI

class SpatialSpec(BaseModel):
    document_id: str
    rooms: list[Room]
    equipment: list[Equipment]
    exits: list[ExitDoor]
    facts: list[SpatialFact]
    abstentions: list[Abstention]
```

### 5.2 `backend/app/spatial/extract.py`

- `extract_spatial(text: str, document_id: str) -> SpatialSpec`
- **Regex-first.** Anticipated phrasings for each field (see §8 for the demo doc's exact wording, which must parse without an LLM).
- Every match records the full containing sentence as `source_quote`, reusing `ingest.py`'s existing sentence splitter — do not write a second one.
- Every extracted value passes the existing span gate from `app/llm_extract.py::verify_spans` (or an equivalent call into it). Values failing the gate are dropped and recorded as an `Abstention`.
- LLM enhancement is gated on a new `SPATIAL_LLM_EXTRACTION_ENABLED` config flag, default `0`. When off, zero LLM imports execute — assert this in a test, mirroring `copilot_agent.py`'s existing flag-off import test.

### 5.3 `backend/app/spatial/layout.py`

- `place(spec: SpatialSpec) -> FloorPlan`
- Deterministic **shelf packing**: rooms sorted by (area desc, id asc), packed left-to-right into rows bounded by the widest room, 2 m gap. No randomness, no seeding — the same spec must always produce byte-identical geometry (asserted in a test).
- Rooms with no stated dimensions are given a nominal 6×6 m box, `dimension_source="inferred"`, and are excluded from every check.
- Equipment and exits are placed as glyphs relative to their parent room; their positions are always `"inferred"` unless the document states a wall.

```python
class PlacedRoom(BaseModel):
    id: str; name: str; zone: str
    x_m: float; y_m: float; width_m: float; length_m: float
    dimension_source: Provenance
    position_source: Provenance

class FloorPlan(BaseModel):
    rooms: list[PlacedRoom]
    equipment: list[PlacedEquipment]
    exits: list[PlacedExit]
    travel_paths: list[TravelPath]     # only for STATED travel distances
    extent_m: tuple[float, float]
    notes: list[str]                   # e.g. "Positions are inferred; see legend."
```

### 5.4 `backend/app/spatial/params.py`

`to_params(spec: SpatialSpec) -> list[dict]` — flattens the spec into the **same flat param-dict shape** `checks.py` already consumes, so `checks_spatial.py` is structurally identical to `checks.py`. Each param dict carries at minimum:
`{param, value, unit, source_quote, provenance, room_id, room_zone, equipment_kind, occupancy_group}`.

### 5.5 `backend/app/agents/checks_spatial.py`

Same `Check` TypedDict imported from `checks.py`. Six entries:

| id | `applies_when` | `rule` | clause_key | severity |
|---|---|---|---|---|
| `SWBD_FRONT_CLEARANCE` | `param == "front_clearance"` and equipment is switchboard/lv_panel | `value >= 1.0` | `CEA_2010_37iii_a` | HIGH |
| `SWBD_REAR_CLEARANCE` | `param == "rear_clearance"` ″ | `value < 0.20 or value > 0.75` | `CEA_2010_37iii_b` | MEDIUM |
| `SWBD_REAR_PASSAGE` | `param == "rear_passage_height"` and rear_clearance > 0.75 | `value >= 1.8` | `CEA_2010_37iii_c` | MEDIUM |
| `EGRESS_DEAD_END` | `param == "dead_end_corridor"` | `value <= limit_for(occupancy_group)` (6 or 15 m) | `NBC2016_4.4.2.2c` | HIGH |
| `EGRESS_TRAVEL_DISTANCE` | `param == "travel_distance"` and occupancy_group known | `value <= table_5[occupancy_group]` | `NBC2016_4.4.2.2a` | HIGH |
| `EGRESS_EXIT_WIDTH` | `param == "exit_width"` and occupant_load known | `value >= occupant_load * table_4[group]` | `NBC2016_4.4.2.3` | HIGH |

Every check must abstain (not fail) when a required companion value is missing or `provenance != "stated"`.

### 5.6 Endpoint

`POST /api/compliance/floor-plan` — multipart upload, same accepted types as `/api/compliance/ingest` (`.pdf .docx .txt .md`).

```jsonc
{
  "document_id": "…",
  "has_spatial_data": true,
  "reason": null,                    // populated when has_spatial_data is false
  "floor_plan": { /* FloorPlan */ },
  "findings": [ /* existing Finding shape, with a `geometry_ref` field added */ ],
  "abstentions": [ {"what": "…", "why": "…"} ],
  "not_checked_zones": [
    {"zone": "server_hall",
     "reason": "Rack and aisle geometry is governed by ASHRAE TC 9.9, which is not a freely redistributable standard and is not digitised here. Rendered for context; deliberately not judged."}
  ],
  "coverage": {"params_extracted": 0, "params_checked": 0, "abstained": 0}
}
```

`geometry_ref` on a finding is `{"kind": "room"|"equipment"|"exit"|"path", "id": "…"}` so the UI can pin it.

Mounted in `main.py` unconditionally. Never raises on a document with no spatial content — returns `has_spatial_data: false` with a plain-language `reason`.

## 6. Frontend contract

- `frontend/components/FloorMap.tsx` — **inline SVG, no new npm dependency.**
  - rooms: `<rect>`; inferred position ⟹ `fill` uses an SVG `<pattern>` hatch + reduced opacity
  - equipment glyphs, exit doors as gaps in the wall stroke, dimension lines with arrowheads
  - `travel_paths` drawn as a red polyline with the measured distance labelled at its midpoint
  - NCR pins: numbered circles at `geometry_ref`; click ⟹ scrolls to / opens the finding
  - a legend that always explains solid vs hatched
  - viewBox derived from `extent_m`; responsive width, `overflow-x: auto`
- `frontend/app/compliance/page.tsx` — new "Floor Plan" panel below the existing findings list. Renders only when `has_spatial_data`; otherwise shows the `reason` string verbatim.
- Findings reuse the existing `CitedClauseBox` → `ClauseViewerModal` path. The clause viewer must resolve the new CEA/NBC clauses; where no local `.md` source exists it already reports `has_context=false` honestly — that is acceptable and must not be faked.
- `not_checked_zones` render as a visible caption on the map, not hidden in a tooltip.

## 7. Demo document

`backend/data/project_docs/live_upload_samples/DC1-05-DBR-0007-R1_Layout-Design-Basis.md` plus a generated `.pdf` of the same content.

Requirements:

1. **Synthetic but representative** — modelled on public Indian data-centre tenders, consistent with the existing Chennai 48 MW Tier-III scenario in `docs/know.md`. Header must state it is representative.
2. Parses **fully via regex, with no API key**.
3. Produces deterministically:
   - a complete map: server hall, electrical room, cooling plant, corridor
   - **NCR-1** — LV panel front clearance stated at **0.8 m** vs CEA's 1.0 m ⟹ FAIL
   - **NCR-2** — dead-end corridor stated at **18 m** vs NBC's 15 m ⟹ FAIL
   - at least one **PASS** (e.g. rear clearance stated at 0.9 m)
   - at least one **visible abstention** (e.g. travel distance never stated, or occupancy group omitted so exit width can't be computed)
   - the server hall rendered but carrying the `not_checked_zones` caption
4. The `.pdf` must round-trip: uploading it yields the identical result to uploading the `.md`. Verified, not assumed.

## 8. Tests and eval

- `backend/tests/test_spatial_extract.py` — each regex phrasing; span-gate rejection of a fabricated quote; abstention recorded on drop.
- `backend/tests/test_spatial_layout.py` — determinism (same spec twice ⟹ identical geometry), no room overlap, inferred marking.
- `backend/tests/test_checks_spatial.py` — all 6 rules at boundary values (0.99/1.0/1.01 m; 0.19/0.20/0.75/0.76 m; 14.9/15.0/15.1 m), and abstention when provenance is inferred.
- `backend/tests/test_spatial_api.py` — the demo doc end-to-end; a doc with no spatial content ⟹ `has_spatial_data: false`; flag-off ⟹ zero LLM imports.
- `backend/eval/run_spatial_eval.py` — labelled cases over the demo doc + variants, reporting decision accuracy and citation-hallucination rate in the same report shape as the other eval scripts. **Reported on its own, never blended into an existing score.**

## 9. Out of scope

- Image / scanned-drawing input (Workstream B, Gemini Vision) — remains skipped.
- DXF/DWG ingestion — `ezdxf` is pure-Python and can be added later behind a flag; no judge will supply a CAD file.
- Floor-plan *generation* from an adjacency program (GPLAN-style) — that is design synthesis, not compliance.
- Any check on rack/aisle geometry until a freely redistributable governing clause exists.

## 10. Risks

| Risk | Mitigation |
|---|---|
| Inferred layout mistaken for a real survey | Persistent hatch + legend + `notes[]`; no verdict from inferred geometry. |
| NBC PDF redistribution | Short quotations only; PDF gitignored. |
| Regex brittleness on unseen phrasing | Documented as a limitation in `docs/gaps.md`; the optional LLM path is the answer, not silent guessing. |
| New clauses disturbing existing evals | Separate JSON file; existing eval reports must stay byte-identical — verified after the change. |
