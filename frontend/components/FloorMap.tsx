"use client";

// Inline SVG 2D floor map — no charting/mapping npm dependency. Renders the
// backend's deterministic shelf-packed geometry (`FloorPlan`, spec §5.3) and
// pins each spatial finding onto the geometry that failed.
//
// The single most important visual rule (spec §3, the "stated-vs-inferred"
// honesty mechanic): a room whose position or dimensions were never stated in
// the source document is drawn HATCHED + DIMMED, never as if it were a
// surveyed fact. That distinction must be legible before reading a word of
// copy — the legend just confirms what the eye already saw.
//
// Scope note: this is deliberately NOT a CAD-grade drawing (no title block,
// no dimension chains, no north arrow/scale bar) — the brief asked for a
// legible, honest floor map, not a drafting package. What IS here: real wall
// thickness (shared walls between two stated-position rooms read as one
// wall, not two abutting outlines), door openings with a swing arc, and
// legible contrast on every label.

import type {
  ClearanceZone,
  FloorPlan,
  GeometryRef,
  NotCheckedZone,
  PlacedEquipment,
  PlacedExit,
  PlacedRoom,
  SpatialFinding,
  TravelPath,
  Wall,
} from "@/lib/types";
import { equipmentKindLabel, severityMeta, zoneMetaFor } from "@/lib/format";

const PAD_M = 3;
const WALL_M = 0.22; // wall band thickness in map units (metres)

function isRoomInferred(room: PlacedRoom): boolean {
  return room.position_source === "inferred" || room.dimension_source === "inferred";
}

function roomById(rooms: PlacedRoom[], id: string | null | undefined): PlacedRoom | null {
  return rooms.find((r) => r.id === id) ?? null;
}

// Room pins are deliberately NOT placed at the room centre — that's exactly
// where the room-name label sits (RoomShape). Instead they sit inset from the
// room's top-right corner, clamped so small rooms never push the pin past
// their own centreline. Deterministic (pure function of the room's stated
// geometry), never a leader line — the pin stays inside the room it refers to.
function roomPinPosition(room: PlacedRoom): [number, number] {
  const insetX = Math.min(1.1, room.width_m * 0.35);
  const insetY = Math.min(1.1, room.length_m * 0.35);
  return [room.x_m + room.width_m - insetX, room.y_m + insetY];
}

function pinPosition(ref: GeometryRef, plan: FloorPlan): [number, number] | null {
  if (ref.kind === "room") {
    const r = roomById(plan.rooms, ref.id);
    return r ? roomPinPosition(r) : null;
  }
  if (ref.kind === "equipment") {
    const e = plan.equipment.find((eq) => eq.id === ref.id);
    return e ? [e.x_m, e.y_m] : null;
  }
  if (ref.kind === "exit") {
    const ex = plan.exits.find((x) => x.id === ref.id);
    return ex ? [ex.x_m, ex.y_m] : null;
  }
  return null;
}

// A TravelPath (backend/app/spatial/layout.py) carries only a stated distance
// and the room it was measured in — no route geometry is on the wire. We draw
// a schematic line from the room's centre to its own nearest exit (or, if the
// room has none, to the exit closest to the room) purely so the number has
// somewhere to sit; the ONLY asserted fact is the labelled distance itself.
function schematicPathLine(
  path: TravelPath,
  plan: FloorPlan,
): { x1: number; y1: number; x2: number; y2: number } | null {
  const room = roomById(plan.rooms, path.room_id);
  if (!room) return null;
  const cx = room.x_m + room.width_m / 2;
  const cy = room.y_m + room.length_m / 2;
  const candidates = plan.exits.filter((e) => e.room_id === path.room_id);
  const pool = candidates.length > 0 ? candidates : plan.exits;
  if (pool.length === 0) {
    return { x1: cx - room.width_m * 0.3, y1: cy, x2: cx + room.width_m * 0.3, y2: cy };
  }
  let nearest = pool[0];
  let best = Infinity;
  for (const e of pool) {
    const d = (e.x_m - cx) ** 2 + (e.y_m - cy) ** 2;
    if (d < best) {
      best = d;
      nearest = e;
    }
  }
  return { x1: cx, y1: cy, x2: nearest.x_m, y2: nearest.y_m };
}

// ── Walls ────────────────────────────────────────────────────────────────
// Every room edge becomes a wall segment. Two rooms whose edges coincide
// exactly (a future "stated adjacency" backend change, Part 3) collapse into
// ONE shared wall segment, solid only when BOTH owning rooms are non-inferred
// — never drawn as two abutting outlines.
interface WallSeg {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  orientation: "h" | "v";
  inferred: boolean;
}

function buildWalls(rooms: PlacedRoom[]): WallSeg[] {
  const segMap = new Map<string, WallSeg>();
  function addSeg(x1: number, y1: number, x2: number, y2: number, inferred: boolean) {
    const orientation: "h" | "v" = y1 === y2 ? "h" : "v";
    const key =
      orientation === "h"
        ? `h:${y1.toFixed(3)}:${Math.min(x1, x2).toFixed(3)}:${Math.max(x1, x2).toFixed(3)}`
        : `v:${x1.toFixed(3)}:${Math.min(y1, y2).toFixed(3)}:${Math.max(y1, y2).toFixed(3)}`;
    const existing = segMap.get(key);
    if (existing) {
      // Shared by two rooms — solid only if neither owner is inferred.
      existing.inferred = existing.inferred || inferred;
    } else {
      segMap.set(key, { x1, y1, x2, y2, orientation, inferred });
    }
  }
  for (const r of rooms) {
    const inferred = isRoomInferred(r);
    addSeg(r.x_m, r.y_m, r.x_m + r.width_m, r.y_m, inferred); // top
    addSeg(r.x_m, r.y_m + r.length_m, r.x_m + r.width_m, r.y_m + r.length_m, inferred); // bottom
    addSeg(r.x_m, r.y_m, r.x_m, r.y_m + r.length_m, inferred); // left
    addSeg(r.x_m + r.width_m, r.y_m, r.x_m + r.width_m, r.y_m + r.length_m, inferred); // right
  }
  return Array.from(segMap.values());
}

// ── Doors ────────────────────────────────────────────────────────────────
// Each exit becomes: a gap punched in the wall band, a leaf line, and a
// quarter-circle swing arc into the room — not just a floating label.
interface DoorGeometry {
  gapCx: number;
  gapCy: number;
  gapW: number; // gap rect width (map units)
  gapH: number; // gap rect height
  leaf: { x1: number; y1: number; x2: number; y2: number };
  arcPath: string;
  labelX: number;
  labelY: number;
}

function doorGeometry(ex: PlacedExit, room: PlacedRoom | null, wall: Wall, widthM: number): DoorGeometry {
  const half = widthM / 2;
  const bandPad = WALL_M / 2 + 0.06;
  // Fallback anchor if we don't have the parent room (shouldn't normally
  // happen — placement always ties an exit to a room).
  const wallY = wall === "north" ? (room ? room.y_m : ex.y_m) : room ? room.y_m + room.length_m : ex.y_m;
  const wallX = wall === "west" ? (room ? room.x_m : ex.x_m) : room ? room.x_m + room.width_m : ex.x_m;

  if (wall === "south") {
    const hingeX = ex.x_m - half;
    const otherX = ex.x_m + half;
    return {
      gapCx: ex.x_m,
      gapCy: wallY,
      gapW: widthM,
      gapH: WALL_M + 0.12,
      leaf: { x1: hingeX, y1: wallY, x2: hingeX, y2: wallY - widthM },
      arcPath: `M ${otherX} ${wallY} A ${widthM} ${widthM} 0 0 1 ${hingeX} ${wallY - widthM}`,
      labelX: ex.x_m,
      labelY: wallY + bandPad + 0.42,
    };
  }
  if (wall === "north") {
    const hingeX = ex.x_m - half;
    const otherX = ex.x_m + half;
    return {
      gapCx: ex.x_m,
      gapCy: wallY,
      gapW: widthM,
      gapH: WALL_M + 0.12,
      leaf: { x1: hingeX, y1: wallY, x2: hingeX, y2: wallY + widthM },
      arcPath: `M ${otherX} ${wallY} A ${widthM} ${widthM} 0 0 0 ${hingeX} ${wallY + widthM}`,
      labelX: ex.x_m,
      labelY: wallY - bandPad - 0.18,
    };
  }
  if (wall === "east") {
    const hingeY = ex.y_m - half;
    const otherY = ex.y_m + half;
    return {
      gapCx: wallX,
      gapCy: ex.y_m,
      gapW: WALL_M + 0.12,
      gapH: widthM,
      leaf: { x1: wallX, y1: hingeY, x2: wallX - widthM, y2: hingeY },
      arcPath: `M ${wallX} ${otherY} A ${widthM} ${widthM} 0 0 0 ${wallX - widthM} ${hingeY}`,
      labelX: wallX + bandPad + 0.55,
      labelY: ex.y_m,
    };
  }
  // west
  const hingeY = ex.y_m - half;
  const otherY = ex.y_m + half;
  return {
    gapCx: wallX,
    gapCy: ex.y_m,
    gapW: WALL_M + 0.12,
    gapH: widthM,
    leaf: { x1: wallX, y1: hingeY, x2: wallX + widthM, y2: hingeY },
    arcPath: `M ${wallX} ${otherY} A ${widthM} ${widthM} 0 0 1 ${wallX + widthM} ${hingeY}`,
    labelX: wallX - bandPad - 0.55,
    labelY: ex.y_m,
  };
}

// A dark plate behind a text label so it stays legible over a hatched or
// zone-tinted fill — the contrast fix called out from the first screenshot.
function LabelPlate({
  x,
  y,
  text,
  size,
  weight,
  color,
  anchor = "middle",
}: {
  x: number;
  y: number;
  text: string;
  size: number;
  weight?: number;
  color: string;
  anchor?: "start" | "middle" | "end";
}) {
  const w = text.length * size * 0.62 + 0.16;
  const h = size * 1.35;
  const plateX = anchor === "middle" ? x - w / 2 : anchor === "end" ? x - w : x;
  return (
    <g>
      <rect x={plateX} y={y - h * 0.78} width={w} height={h} fill="var(--bg-900)" opacity={0.78} rx={0.04} />
      <text
        x={x}
        y={y}
        textAnchor={anchor}
        fontSize={size}
        fontWeight={weight ?? 500}
        fill={color}
        className="font-mono"
      >
        {text}
      </text>
    </g>
  );
}

function RoomShape({ room }: { room: PlacedRoom }) {
  const inferred = isRoomInferred(room);
  const zm = zoneMetaFor(room.zone);
  return (
    <g>
      <rect
        x={room.x_m}
        y={room.y_m}
        width={room.width_m}
        height={room.length_m}
        fill={zm.color}
        fillOpacity={inferred ? 0.07 : 0.15}
      />
      {inferred && (
        <rect
          x={room.x_m}
          y={room.y_m}
          width={room.width_m}
          height={room.length_m}
          fill="url(#hatch)"
          opacity={0.4}
        />
      )}
      <LabelPlate
        x={room.x_m + room.width_m / 2}
        y={room.y_m + room.length_m / 2 - 0.1}
        text={room.name}
        size={0.56}
        weight={700}
        color="var(--text-hi)"
      />
      <LabelPlate
        x={room.x_m + room.width_m / 2}
        y={room.y_m + room.length_m / 2 + 0.55}
        text={
          room.dimension_source === "stated"
            ? `${room.width_m.toFixed(1)} m × ${room.length_m.toFixed(1)} m stated`
            : "size not stated"
        }
        size={0.36}
        color="var(--text-mid)"
      />
    </g>
  );
}

function WallLine({ seg }: { seg: WallSeg }) {
  return (
    <line
      x1={seg.x1}
      y1={seg.y1}
      x2={seg.x2}
      y2={seg.y2}
      stroke={seg.inferred ? "var(--text-lo)" : "var(--text-mid)"}
      strokeWidth={WALL_M}
      strokeLinecap="square"
      strokeDasharray={seg.inferred ? "0.4 0.28" : undefined}
    />
  );
}

function EquipmentGlyph({ eq }: { eq: PlacedEquipment }) {
  const w = 1.1;
  const h = 0.55;
  const label = equipmentKindLabel[eq.kind] ?? eq.kind;
  const detail = [
    eq.front_clearance_m != null ? `front ${eq.front_clearance_m.toFixed(2)} m` : null,
    eq.rear_clearance_m != null ? `rear ${eq.rear_clearance_m.toFixed(2)} m` : null,
  ]
    .filter(Boolean)
    .join(" · ");
  return (
    <g>
      <rect
        x={eq.x_m - w / 2}
        y={eq.y_m - h / 2}
        width={w}
        height={h}
        fill="var(--bg-800)"
        stroke="var(--data)"
        strokeWidth={0.06}
      />
      <line
        x1={eq.x_m - w / 2 + 0.12}
        y1={eq.y_m}
        x2={eq.x_m + w / 2 - 0.12}
        y2={eq.y_m}
        stroke="var(--data)"
        strokeWidth={0.045}
      />
      <title>
        {label}
        {detail ? ` — ${detail}` : ""}
      </title>
      {/* Label sits to the side, not below — clearance zones (front/rear) are
          typically stacked in a vertical column directly above/below the
          equipment, so a below-centred label collides with them. */}
      <LabelPlate
        x={eq.x_m + w / 2 + 0.6}
        y={eq.y_m + 0.12}
        text={label}
        size={0.32}
        color="var(--data)"
        anchor="start"
      />
    </g>
  );
}

function ExitDoorGlyph({ exit: ex, room }: { exit: PlacedExit; room: PlacedRoom | null }) {
  const widthM = (ex.width_mm ?? 900) / 1000;
  const wall: Wall = ex.wall ?? "south";
  const geo = doorGeometry(ex, room, wall, widthM);
  return (
    <g>
      {/* punch the opening out of the wall band */}
      <rect
        x={geo.gapCx - geo.gapW / 2}
        y={geo.gapCy - geo.gapH / 2}
        width={geo.gapW}
        height={geo.gapH}
        fill="var(--bg-900)"
      />
      {/* door leaf */}
      <line x1={geo.leaf.x1} y1={geo.leaf.y1} x2={geo.leaf.x2} y2={geo.leaf.y2} stroke="var(--accent)" strokeWidth={0.06} />
      {/* swing arc */}
      <path d={geo.arcPath} fill="none" stroke="var(--accent)" strokeWidth={0.035} strokeDasharray="0.12 0.1" opacity={0.85} />
      <LabelPlate
        x={geo.labelX}
        y={geo.labelY}
        text={`${ex.width_mm != null ? ex.width_mm.toFixed(0) : "?"} mm exit`}
        size={0.32}
        color="var(--accent)"
      />
    </g>
  );
}

// ── Clearance zones (Part 3 — defensive: optional field, may not exist yet
// on any given backend response) — the provided band vs the required
// envelope it fails (or meets), drawn as literal geometry so a switchboard
// clearance failure is unmistakable without reading a word of prose.
function ClearanceZoneShape({ zone }: { zone: ClearanceZone }) {
  if (!zone.provided_rect) return null;
  const pr = zone.provided_rect;
  const rr = zone.required_rect;
  const color =
    zone.status === "fail" ? "var(--critical)" : zone.status === "pass" ? "var(--pass)" : "var(--text-lo)";
  const label =
    zone.required_m != null
      ? `${zone.provided_m.toFixed(2)} m provided / ${zone.required_m.toFixed(2)} m required`
      : `${zone.provided_m.toFixed(2)} m provided`;
  // Front and rear clearance bands sit on opposite sides of the equipment, so
  // their labels are anchored on opposite sides too — a "rear" band's label
  // rendered below (toward the equipment/front band) is what collided with
  // the front label and the equipment name in the cramped default demo. Front
  // (and any other kind) keeps the original south-of-rect placement.
  const labelX = pr.x_m + pr.width_m / 2;
  const labelY = zone.kind === "rear" ? pr.y_m - 0.35 : pr.y_m + pr.length_m + 0.55;
  return (
    <g>
      {rr && (
        <rect
          x={rr.x_m}
          y={rr.y_m}
          width={rr.width_m}
          height={rr.length_m}
          fill="none"
          stroke="var(--warning)"
          strokeWidth={0.05}
          strokeDasharray="0.18 0.12"
        />
      )}
      <rect
        x={pr.x_m}
        y={pr.y_m}
        width={pr.width_m}
        height={pr.length_m}
        fill={color}
        fillOpacity={0.3}
        stroke={color}
        strokeWidth={0.05}
      />
      <LabelPlate x={labelX} y={labelY} text={label} size={0.3} color={color} />
    </g>
  );
}

export function FloorMap({
  floorPlan,
  findings,
  notCheckedZones,
  onPinClick,
}: {
  floorPlan: FloorPlan;
  findings: SpatialFinding[];
  notCheckedZones: NotCheckedZone[];
  onPinClick?: (findingId: string) => void;
}) {
  const [extentW, extentH] = floorPlan.extent_m;
  const viewW = extentW + PAD_M * 2;
  const viewH = extentH + PAD_M * 2;
  const notCheckedZoneNames = new Set(notCheckedZones.map((z) => z.zone));
  const walls = buildWalls(floorPlan.rooms);
  // Defensive: clearance_zones may not exist on every backend response yet.
  const clearanceZones = floorPlan.clearance_zones ?? [];

  const pins = findings
    .map((f) => {
      const pos = pinPosition(f.geometry_ref, floorPlan);
      return pos ? { finding: f, pos } : null;
    })
    .filter((p): p is { finding: SpatialFinding; pos: [number, number] } => p !== null);

  return (
    <div>
      <div className="overflow-x-auto rounded-card border border-line bg-bg-900" style={{ maxWidth: "100%" }}>
        <svg
          viewBox={`${-PAD_M} ${-PAD_M} ${viewW} ${viewH}`}
          width="100%"
          style={{ minWidth: `${Math.max(560, extentW * 24)}px`, height: "auto", display: "block" }}
          role="img"
          aria-label="2D floor plan with compliance findings pinned onto the geometry"
        >
          <defs>
            <pattern id="hatch" patternUnits="userSpaceOnUse" width="1.1" height="1.1" patternTransform="rotate(45)">
              <line x1="0" y1="0" x2="0" y2="1.1" stroke="var(--text-lo)" strokeWidth={0.09} />
            </pattern>
          </defs>

          {/* rooms (+ not-checked watermark) */}
          {floorPlan.rooms.map((r) => (
            <g key={r.id}>
              <RoomShape room={r} />
              {notCheckedZoneNames.has(r.zone) && (
                <LabelPlate
                  x={r.x_m + r.width_m / 2}
                  y={r.y_m + 0.6}
                  text="NOT CHECKED"
                  size={0.32}
                  weight={700}
                  color="var(--warning)"
                />
              )}
            </g>
          ))}

          {/* walls — real thickness; a shared edge between two stated-position
              rooms draws once, as one wall, not two abutting outlines */}
          {walls.map((seg, i) => (
            <WallLine key={i} seg={seg} />
          ))}

          {/* exits — gap in the wall + swing arc + label */}
          {floorPlan.exits.map((ex) => (
            <ExitDoorGlyph key={ex.id} exit={ex} room={roomById(floorPlan.rooms, ex.room_id)} />
          ))}

          {/* equipment */}
          {floorPlan.equipment.map((eq) => (
            <EquipmentGlyph key={eq.id} eq={eq} />
          ))}

          {/* clearance zones (Part 3, defensive — renders nothing if absent) */}
          {clearanceZones.map((z, i) => (
            <ClearanceZoneShape key={`${z.equipment_id}-${z.kind}-${i}`} zone={z} />
          ))}

          {/* travel paths — red polyline, distance labelled at the midpoint.
              Renders nothing at all when travel_paths is empty (never fake a
              route the document never stated). */}
          {floorPlan.travel_paths.map((tp, i) => {
            const line = schematicPathLine(tp, floorPlan);
            if (!line) return null;
            const mx = (line.x1 + line.x2) / 2;
            const my = (line.y1 + line.y2) / 2;
            return (
              <g key={i}>
                <polyline
                  points={`${line.x1},${line.y1} ${line.x2},${line.y2}`}
                  fill="none"
                  stroke="var(--critical)"
                  strokeWidth={0.08}
                  strokeDasharray="0.4 0.2"
                />
                <LabelPlate x={mx} y={my} text={`${tp.distance_m.toFixed(1)} m travel`} size={0.34} weight={700} color="var(--critical)" />
              </g>
            );
          })}

          {/* numbered NCR pins */}
          {pins.map(({ finding, pos }, i) => {
            const meta = severityMeta[finding.severity];
            return (
              <g
                key={finding.id}
                transform={`translate(${pos[0]}, ${pos[1]})`}
                style={{ cursor: onPinClick ? "pointer" : "default" }}
                onClick={() => onPinClick?.(finding.id)}
              >
                <circle r={0.55} fill={meta.color} stroke="var(--bg-900)" strokeWidth={0.08} />
                <text
                  y={0.19}
                  textAnchor="middle"
                  fontSize={0.55}
                  fontWeight={800}
                  fill="var(--bg-900)"
                  className="font-mono"
                >
                  {i + 1}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      {/* legend — always visible, explains solid vs hatched */}
      <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 rounded-card border border-line bg-bg-800 px-4 py-3 text-[0.72rem] text-text-mid">
        <span className="overline">Legend</span>
        <span className="inline-flex items-center gap-1.5">
          <span
            className="inline-block h-3 w-4 rounded-[2px]"
            style={{ background: "var(--data)", opacity: 0.35, border: "1px solid var(--data)" }}
          />
          Solid = dimensions &amp; position stated in the document
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span
            className="inline-block h-3 w-4 rounded-[2px]"
            style={{
              background: "repeating-linear-gradient(45deg, var(--text-lo) 0 1.5px, transparent 1.5px 6px)",
              opacity: 0.7,
              border: "1px dashed var(--text-lo)",
            }}
          />
          Hatched = position and/or size inferred — never used in a check
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block h-0.5 w-5" style={{ background: "var(--critical)" }} />
          Red line = a stated travel distance
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span
            className="inline-grid h-4 w-4 place-items-center rounded-full font-mono text-[0.6rem] font-bold"
            style={{ background: "var(--critical)", color: "var(--bg-900)" }}
          >
            1
          </span>
          Numbered pin = a finding — click to jump to it
        </span>
        {clearanceZones.length > 0 && (
          <span className="inline-flex items-center gap-1.5">
            <span
              className="inline-block h-3 w-4 rounded-[2px]"
              style={{ background: "var(--critical)", opacity: 0.4, border: "1px dashed var(--warning)" }}
            />
            Filled band = clearance provided; dashed outline = clearance required
          </span>
        )}
        <span className="inline-flex items-center gap-1.5" style={{ color: "var(--warning)" }}>
          NOT CHECKED = rendered for context, deliberately not judged (see caption below map)
        </span>
      </div>
    </div>
  );
}
