// API client. EVERY call gracefully falls back to bundled mock data so the UI
// always renders for a demo, even with the backend down. See lib/mocks.ts.

import {
  PROJECT_LABEL,
  mockAuditEvents,
  mockComplianceFor,
  mockCopilotAnswer,
  mockCostRisk,
  mockDocuments,
  mockGantt,
  mockKg,
  mockOverview,
  mockReasoningTrace,
  mockRisks,
  mockSupplyChainAlerts,
  mockSupplyChainMap,
  mockSupplyChainMeta,
  mockSupplyChainRisks,
  mockShipments,
  mockTimeline,
} from "./mocks";
import type {
  ActionBrief,
  AuditEvent,
  CodebookCheckResult,
  CodebookClauseResult,
  CodebookConsoleCorpus,
  CodebookConsoleDocument,
  CodebookConsoleUploadResult,
  CodebookCorporaResult,
  CodebookSearchResult,
  ClauseContext,
  CommissioningIngestResult,
  ComplianceResult,
  Confidence,
  CostRisk,
  DocItem,
  FloorPlanResult,
  GanttBar,
  IngestResult,
  KgGraph,
  NCR,
  OverviewStats,
  RetrievalCorpusSummary,
  RetrievalIngestManifest,
  RetrievalQueryResult,
  RFIAnswer,
  RiskItem,
  Shipment,
  SupplyChainAlert,
  SupplyChainMap,
  SupplyChainMeta,
  SupplyChainRisk,
  TimelineData,
} from "./types";

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://localhost:8000";

// Render's free tier spins services down after ~15 min idle. Measured cold
// starts directly: the backend itself took ~52s, Codebook (standards-service)
// took ~72s to answer a health check from fully asleep. 20s was still far too
// short (that's why "unreachable" kept recurring after the first bump) — 90s
// gives the backend-only path real margin above the observed worst case while
// still failing in reasonable time for a genuinely dead backend.
const TIMEOUT_MS = 90000;

// Codebook calls are a sequential double cold-start: the browser's request
// has to wait for SiteMind's backend to wake up, and only THEN does the
// backend make its own MCP call to Codebook — which may ALSO be cold. That
// stacks to well over 90s in the worst case (both services asleep at once),
// so Codebook-specific calls get a longer budget than plain backend calls.
// Matches the explicit timeout now set on the backend's MCP client itself
// (see codebook_client.py) so neither side gives up before the other.
const CODEBOOK_TIMEOUT_MS = 180000;

async function getJSON<T>(path: string, fallback: T): Promise<{ data: T; live: boolean }> {
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
    const res = await fetch(`${API_URL}${path}`, { signal: ctrl.signal, cache: "no-store" });
    clearTimeout(t);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return { data: (await res.json()) as T, live: true };
  } catch {
    return { data: fallback, live: false };
  }
}

async function postJSON<T>(path: string, body: unknown, fallback: T): Promise<{ data: T; live: boolean }> {
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
    const res = await fetch(`${API_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: ctrl.signal,
      cache: "no-store",
    });
    clearTimeout(t);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return { data: (await res.json()) as T, live: true };
  } catch {
    return { data: fallback, live: false };
  }
}

export const getOverview = () =>
  getJSON<OverviewStats>("/api/overview", mockOverview);

export const getCostRisk = () =>
  getJSON<CostRisk>("/api/cost-risk", mockCostRisk);

export const getDocuments = () =>
  getJSON<DocItem[]>("/api/documents", mockDocuments);

export const runCompliance = (documentId: string) =>
  postJSON<ComplianceResult>(
    "/api/compliance/check",
    { document_id: documentId },
    mockComplianceFor(documentId),
  );

export const askCopilot = (question: string) =>
  postJSON<RFIAnswer>(
    "/api/copilot/ask",
    { question },
    mockCopilotAnswer(question),
  );

export const getRisks = () =>
  getJSON<RiskItem[]>("/api/schedule/risks", mockRisks);

export const getGantt = () =>
  getJSON<GanttBar[]>("/api/schedule/gantt", mockGantt);

export const getKg = (elementId = "eq-tx") =>
  getJSON<KgGraph>(`/api/kg/${elementId}`, mockKg);

// Clause viewer popup (CitedClauseBox) — replaces the external verify_url
// link. Falls back to an honest "backend unreachable" note, never a
// fabricated excerpt, if the API call itself fails.
export const getClauseContext = (standard: string, clause: string) =>
  getJSON<ClauseContext>(
    `/api/clause-context?standard=${encodeURIComponent(standard)}&clause=${encodeURIComponent(clause)}`,
    {
      has_context: false,
      standard,
      clause,
      note: "Backend unreachable — showing the cited clause text only.",
    },
  );

// ── Audit Ledger (plan §D/E) — "Chain of Custody" ───────────────────────────

export const getAudit = (pillar?: string) =>
  getJSON<AuditEvent[]>(
    `/api/audit${pillar ? `?pillar=${encodeURIComponent(pillar)}` : ""}`,
    mockAuditEvents,
  );

export const getAuditEvent = (id: string) =>
  getJSON<AuditEvent | null>(`/api/audit/${id}`, mockAuditEvents.find((e) => e.id === id) ?? null);

export const seedAudit = () =>
  postJSON<{ new_records: number }>("/api/audit/seed", {}, { new_records: 0 });

export const anchorAuditEvent = (id: string) =>
  postJSON<AuditEvent>(
    `/api/audit/${id}/anchor`,
    {},
    mockAuditEvents.find((e) => e.id === id) ?? mockAuditEvents[0],
  );

export const anchorAllPending = () =>
  postJSON<{ anchored: number }>("/api/audit/anchor-pending", {}, { anchored: 0 });

export const verifyAuditEvent = (id: string) =>
  postJSON<{ mongo_intact: boolean | null; chain_intact: boolean | null }>(
    `/api/audit/${id}/verify`,
    {},
    { mongo_intact: null, chain_intact: null },
  );

// ── Project Timeline (P0) ───────────────────────────────────────────────────

export const getTimeline = () =>
  getJSON<TimelineData>("/api/timeline", mockTimeline);

// ── Supply Chain Visibility ─────────────────────────────────────────────────

export const getShipments = () =>
  getJSON<Shipment[]>("/api/supply-chain/shipments", mockShipments);

export const getSupplyChainRisks = () =>
  getJSON<SupplyChainRisk[]>("/api/supply-chain/risks", mockSupplyChainRisks);

export const getSupplyChainMap = () =>
  getJSON<SupplyChainMap>("/api/supply-chain/map", mockSupplyChainMap);

export const getSupplyChainAlerts = () =>
  getJSON<SupplyChainAlert[]>("/api/supply-chain/alerts", mockSupplyChainAlerts);

export const getSupplyChainMeta = () =>
  getJSON<SupplyChainMeta>("/api/supply-chain/meta", mockSupplyChainMeta);

// ── Action Brief ───────────────────────────────────────────────────────────
// If the backend is unreachable, we do NOT fabricate RFI/schedule links or a
// fake confidence score. The fallback derives only what's honestly computable
// client-side from the NCRs already on screen (same confidence rule as the
// backend); linked_rfi/affected_activity are omitted rather than guessed.
function fallbackConfidence(ncr: NCR): { confidence: Confidence; status: "NCR" | "REVIEW_REQUIRED" } {
  if (ncr.severity === "ADVISORY") {
    return {
      confidence: {
        level: "medium",
        basis: "cited judgment call — requires EOR confirmation, not a binary deterministic threshold",
      },
      status: "NCR",
    };
  }
  if (ncr.source && ncr.citation) {
    return {
      confidence: {
        level: "high",
        basis: "exact-span extraction + exact clause match + deterministic result",
      },
      status: "NCR",
    };
  }
  return {
    confidence: { level: "low", basis: "missing source span or citation — insufficient evidence" },
    status: "REVIEW_REQUIRED",
  };
}

function fallbackActionBrief(ncrs: NCR[]): ActionBrief[] {
  return ncrs.map((ncr) => {
    const { confidence, status } = fallbackConfidence(ncr);
    const evidence: string[] = [];
    if (ncr.source) evidence.push(ncr.source.location);
    if (ncr.citation) evidence.push(`${ncr.citation.standard} Cl ${ncr.citation.clause}`);
    return {
      finding_id: ncr.id,
      parameter: { name: ncr.item, value: "", source: ncr.source },
      check: {
        clause: ncr.citation,
        requirement: ncr.finding,
        result: ncr.severity === "ADVISORY" ? "ADVISORY" : "FAIL",
        engine: "deterministic",
      },
      status,
      linked_rfi: null,
      affected_activity: null,
      recommended_action:
        status === "REVIEW_REQUIRED"
          ? null
          : {
              owner_role: "Design Manager",
              action: ncr.corrective_action,
              note: "System raises a design clarification; it does not redesign.",
            },
      confidence,
      evidence,
      computed_impact: null,
    };
  });
}

export async function getActionBrief(documentId: string, ncrs: NCR[]): Promise<{ data: ActionBrief[]; live: boolean }> {
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
    const res = await fetch(`${API_URL}/api/compliance/action-brief/${encodeURIComponent(documentId)}`, {
      signal: ctrl.signal,
      cache: "no-store",
    });
    clearTimeout(t);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return { data: (await res.json()) as ActionBrief[], live: true };
  } catch {
    return { data: fallbackActionBrief(ncrs), live: false };
  }
}

export const projectLabel = PROJECT_LABEL;

// ── Health / system status (drives the "Agents online" indicator + Settings panel) ──
export interface HealthState {
  status: string;
  offline_mode: boolean;
  provider: string;
  langfuse_enabled: boolean;
  vector_store?: string; // "numpy" (default) | "actian" — plan §C
  audit_backend?: string; // "mongodb" | "local_jsonl" — plan §D
}

const FALLBACK_HEALTH: HealthState = {
  status: "unknown",
  offline_mode: true,
  provider: "offline",
  langfuse_enabled: false,
  vector_store: "numpy",
  audit_backend: "local_jsonl",
};

export async function getHealth(): Promise<{ data: HealthState; live: boolean }> {
  return getJSON<HealthState>("/api/health", FALLBACK_HEALTH);
}

// ── Simulated demo clock (proves risk/alert numbers are computed live, not
// hardcoded — advancing "today" changes real downstream output). No mock
// fallback: if the backend is unreachable there is nothing to advance. ──
export interface ClockState {
  base_day: number;
  offset_days: number;
  current_day: number;
  max_offset_days: number;
}

export async function getClockState(): Promise<ClockState | null> {
  try {
    const res = await fetch(`${API_URL}/api/clock`, { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return (await res.json()) as ClockState;
  } catch {
    return null;
  }
}

export async function advanceClock(days: number): Promise<ClockState | null> {
  try {
    const res = await fetch(`${API_URL}/api/clock/advance`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ days }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return (await res.json()) as ClockState;
  } catch {
    return null;
  }
}

export async function resetClock(): Promise<ClockState | null> {
  try {
    const res = await fetch(`${API_URL}/api/clock/reset`, { method: "POST" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return (await res.json()) as ClockState;
  } catch {
    return null;
  }
}

// ── Real document upload ──────────────────────────────────────────────────
// Deliberately NO mock fallback: this reads an actual uploaded file. If the
// backend is unreachable we must say so, not fabricate an extraction result —
// that would be exactly the kind of dishonesty the product promises to avoid.
export class IngestUnavailableError extends Error {}

export async function ingestDocument(file: File): Promise<IngestResult> {
  const form = new FormData();
  form.append("file", file);
  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/compliance/ingest`, {
      method: "POST",
      body: form,
    });
  } catch {
    throw new IngestUnavailableError(
      "Backend unreachable — document upload needs the live SiteMind API (it reads " +
        "the actual file), so there is no offline/mock fallback for this action.",
    );
  }
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? `Upload failed (HTTP ${res.status})`);
  }
  return (await res.json()) as IngestResult;
}

// ── Filesystem-backed register documents ────────────────────────────────────
// Reads the REAL file behind a document-register row (backend/data/project_docs/
// demo_docs/) and runs it through the identical ingest pipeline as ingestDocument
// above. Same honesty rule: no mock fallback — a register row with has_file:true
// promises a real file, so a check must run against real extracted bytes or
// fail loudly, never fall back to a synthetic result.
export async function ingestRegisteredDocument(docId: string): Promise<IngestResult> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/documents/${encodeURIComponent(docId)}/ingest`, {
      method: "POST",
    });
  } catch {
    throw new IngestUnavailableError(
      "Backend unreachable — running the real pipeline needs the live SiteMind API " +
        "(it reads the actual file on disk), so there is no offline/mock fallback for this action.",
    );
  }
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? `Ingest failed (HTTP ${res.status})`);
  }
  return (await res.json()) as IngestResult;
}

// ── Spatial Compliance (floor plan) ─────────────────────────────────────────
// Deliberately NO mock fallback — same honesty rule as ingestDocument/
// ingestCommissioningLog: this reads the actual uploaded file's real geometry
// and real findings. If the backend is unreachable there is nothing honest to
// fabricate, so callers must surface the failure rather than render a fake map.
export class FloorPlanUnavailableError extends Error {}

export async function postFloorPlan(file: File): Promise<FloorPlanResult> {
  const form = new FormData();
  form.append("file", file);
  let res: Response;
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
    res = await fetch(`${API_URL}/api/compliance/floor-plan`, {
      method: "POST",
      body: form,
      signal: ctrl.signal,
    });
    clearTimeout(t);
  } catch {
    throw new FloorPlanUnavailableError(
      "Backend unreachable — floor-plan extraction needs the live SiteMind API (it reads " +
        "the actual file), so there is no offline/mock fallback for this action.",
    );
  }
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? `Floor-plan check failed (HTTP ${res.status})`);
  }
  return (await res.json()) as FloorPlanResult;
}

// ── Commissioning QA (Pillar 5, cooling-only slice) ─────────────────────────
// Deliberately NO mock fallback: this reads an actual uploaded CSV test log.
// Same honesty rule as ingestDocument — if the backend is unreachable we must
// say so, not fabricate a quality package.
export class CommissioningUnavailableError extends Error {}

export async function ingestCommissioningLog(file: File): Promise<CommissioningIngestResult> {
  const form = new FormData();
  form.append("file", file);
  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/commissioning/ingest`, {
      method: "POST",
      body: form,
    });
  } catch {
    throw new CommissioningUnavailableError(
      "Backend unreachable — commissioning log ingest needs the live SiteMind API (it parses " +
        "the actual CSV test log), so there is no offline/mock fallback for this action.",
    );
  }
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    const msg = detail?.detail?.message ?? detail?.detail ?? `Upload failed (HTTP ${res.status})`;
    const errors: string[] = detail?.detail?.errors ?? [];
    throw new Error(errors.length ? `${msg} — ${errors.join("; ")}` : msg);
  }
  return (await res.json()) as CommissioningIngestResult;
}

export function qualityPackageHtmlUrl(runId: string): string {
  return `${API_URL}/api/commissioning/quality-package/${encodeURIComponent(runId)}/html`;
}

// ── Streaming compliance check ────────────────────────────────────────────────
// Tries the SSE endpoint; if unreachable, simulates a token stream over the mock
// reasoning trace so the "AI is reasoning" panel always animates for the demo.

export interface StreamHandlers {
  onReasoning: (chunk: string) => void;
  onResult: (result: ComplianceResult) => void;
  onSource?: (live: boolean) => void;
}

export function streamCompliance(
  documentId: string,
  handlers: StreamHandlers,
): () => void {
  let cancelled = false;
  const ctrl = new AbortController();

  (async () => {
    try {
      const res = await fetch(`${API_URL}/api/compliance/check/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        body: JSON.stringify({ document_id: documentId }),
        signal: ctrl.signal,
        cache: "no-store",
      });
      if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);
      handlers.onSource?.(true);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (!cancelled) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const frames = buffer.split("\n\n");
        buffer = frames.pop() ?? "";
        for (const frame of frames) {
          const line = frame
            .split("\n")
            .find((l) => l.startsWith("data:"));
          if (!line) continue;
          try {
            const evt = JSON.parse(line.slice(5).trim());
            if (evt.type === "reasoning") handlers.onReasoning(evt.text + " ");
            else if (evt.type === "result") handlers.onResult(evt.data);
          } catch {
            /* ignore malformed frame */
          }
        }
      }
    } catch {
      // Fallback: simulate streaming over the mock trace.
      if (cancelled) return;
      handlers.onSource?.(false);
      await simulateStream(documentId, handlers, () => cancelled);
    }
  })();

  return () => {
    cancelled = true;
    ctrl.abort();
  };
}

function delay(ms: number) {
  return new Promise<void>((r) => setTimeout(r, ms));
}

async function simulateStream(
  documentId: string,
  handlers: StreamHandlers,
  isCancelled: () => boolean,
) {
  const lines = mockReasoningTrace(documentId);
  for (const line of lines) {
    const words = line.split(" ");
    for (const w of words) {
      if (isCancelled()) return;
      handlers.onReasoning(w + " ");
      await delay(18 + Math.random() * 26);
    }
    handlers.onReasoning("\n");
    await delay(160);
  }
  if (isCancelled()) return;
  await delay(220);
  handlers.onResult(mockComplianceFor(documentId));
}

// ── Knowledge Base (Phase 3 standalone retrieval package,
// backend/app/retrieval/, mounted only when RETRIEVAL_ENABLED=1) ───────────
// No mock fallback anywhere here: this reads a real uploaded document / a
// real query index. If the backend doesn't have the routes mounted at all
// (RETRIEVAL_ENABLED=0 → every route 404s) or is unreachable, callers must
// see a clear "not enabled" / "unreachable" state — never a silent fake
// result, per this project's integrity rules.
export type RetrievalAvailability = "checking" | "available" | "disabled" | "unreachable";

export class RetrievalUnavailableError extends Error {}

export async function getRetrievalCorpora(): Promise<{
  corpora: RetrievalCorpusSummary[];
  availability: RetrievalAvailability;
}> {
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
    const res = await fetch(`${API_URL}/api/retrieval/corpora`, {
      signal: ctrl.signal,
      cache: "no-store",
    });
    clearTimeout(t);
    if (res.status === 404) return { corpora: [], availability: "disabled" };
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = (await res.json()) as RetrievalCorpusSummary[];
    return { corpora: data, availability: "available" };
  } catch {
    return { corpora: [], availability: "unreachable" };
  }
}

export async function uploadKnowledgeBaseDocument(
  corpusName: string,
  file: File,
): Promise<RetrievalIngestManifest> {
  const form = new FormData();
  form.append("corpus_name", corpusName);
  form.append("file", file);
  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/retrieval/upload`, { method: "POST", body: form });
  } catch {
    throw new RetrievalUnavailableError(
      "Backend unreachable — Knowledge Base upload needs the live SiteMind API, so there is no offline fallback for this action.",
    );
  }
  if (res.status === 404) {
    throw new RetrievalUnavailableError(
      "Knowledge Base is not enabled on this backend (RETRIEVAL_ENABLED is off).",
    );
  }
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? `Upload failed (HTTP ${res.status})`);
  }
  return (await res.json()) as RetrievalIngestManifest;
}

export async function queryKnowledgeBase(
  corpusName: string,
  question: string,
  k = 4,
): Promise<RetrievalQueryResult> {
  let res: Response;
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
    res = await fetch(`${API_URL}/api/retrieval/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ corpus_name: corpusName, question, k }),
      signal: ctrl.signal,
      cache: "no-store",
    });
    clearTimeout(t);
  } catch {
    throw new RetrievalUnavailableError(
      "Backend unreachable — Knowledge Base query needs the live SiteMind API, so there is no offline fallback for this action.",
    );
  }
  if (res.status === 404) {
    throw new RetrievalUnavailableError(
      "Knowledge Base is not enabled on this backend (RETRIEVAL_ENABLED is off).",
    );
  }
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? `Query failed (HTTP ${res.status})`);
  }
  return (await res.json()) as RetrievalQueryResult;
}

// ── Codebook (standards-service REST facade, backend/app/codebook_router.py,
// mounted only when CODEBOOK_ENABLED=1) ─────────────────────────────────────
// SiteMind's backend is an MCP *client* of Codebook here — every route below
// proxies exactly one Codebook MCP tool call and returns its raw text block.
// Two distinct "off" states, both surfaced honestly rather than crashing:
//   - CODEBOOK_ENABLED=0 on this backend → the whole router isn't mounted →
//     every route 404s (same as RETRIEVAL_ENABLED's pattern).
//   - CODEBOOK_ENABLED=1 but Codebook's own process (standards-service,
//     port 8010) is unreachable → codebook_router.py's `_call` translates
//     that into a clean HTTP 503 (see codebook_client.CodebookUnavailable).
// A network failure reaching SiteMind's own backend at all collapses into
// the same "unreachable" bucket as a 503 — from the browser's point of view
// there is nothing actionable to distinguish "your API is down" from
// "Codebook is down"; both mean the same features are unusable right now.
export type CodebookAvailability = "checking" | "available" | "disabled" | "unreachable";

export class CodebookUnavailableError extends Error {}

export async function getCodebookCorpora(): Promise<{
  result: CodebookCorporaResult | null;
  availability: CodebookAvailability;
}> {
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), CODEBOOK_TIMEOUT_MS);
    const res = await fetch(`${API_URL}/api/codebook/corpora`, {
      signal: ctrl.signal,
      cache: "no-store",
    });
    clearTimeout(t);
    if (res.status === 404) return { result: null, availability: "disabled" };
    if (res.status === 503) return { result: null, availability: "unreachable" };
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = (await res.json()) as CodebookCorporaResult;
    return { result: data, availability: "available" };
  } catch {
    return { result: null, availability: "unreachable" };
  }
}

export async function searchCodebook(
  query: string,
  corpus?: string,
  k = 5,
): Promise<CodebookSearchResult> {
  const params = new URLSearchParams({ q: query, k: String(k) });
  if (corpus?.trim()) params.set("corpus", corpus.trim());
  let res: Response;
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), CODEBOOK_TIMEOUT_MS);
    res = await fetch(`${API_URL}/api/codebook/search?${params.toString()}`, {
      signal: ctrl.signal,
      cache: "no-store",
    });
    clearTimeout(t);
  } catch {
    throw new CodebookUnavailableError(
      "Backend unreachable — Codebook search needs the live SiteMind API, so there is no offline fallback for this action.",
    );
  }
  if (res.status === 404) {
    throw new CodebookUnavailableError(
      "Codebook is not enabled on this backend (CODEBOOK_ENABLED is off).",
    );
  }
  if (res.status === 503) {
    const detail = await res.json().catch(() => null);
    throw new CodebookUnavailableError(
      detail?.detail ?? "Codebook's own service (standards-service) is unreachable.",
    );
  }
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? `Search failed (HTTP ${res.status})`);
  }
  return (await res.json()) as CodebookSearchResult;
}

export async function getCodebookClause(
  docId: string,
  chunkId: string,
): Promise<CodebookClauseResult> {
  let res: Response;
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), CODEBOOK_TIMEOUT_MS);
    res = await fetch(
      `${API_URL}/api/codebook/clause/${encodeURIComponent(docId)}/${encodeURIComponent(chunkId)}`,
      { signal: ctrl.signal, cache: "no-store" },
    );
    clearTimeout(t);
  } catch {
    throw new CodebookUnavailableError(
      "Backend unreachable — fetching a clause needs the live SiteMind API, so there is no offline fallback for this action.",
    );
  }
  if (res.status === 404) {
    throw new CodebookUnavailableError(
      "Codebook is not enabled on this backend (CODEBOOK_ENABLED is off).",
    );
  }
  if (res.status === 503) {
    const detail = await res.json().catch(() => null);
    throw new CodebookUnavailableError(
      detail?.detail ?? "Codebook's own service (standards-service) is unreachable.",
    );
  }
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? `Clause lookup failed (HTTP ${res.status})`);
  }
  return (await res.json()) as CodebookClauseResult;
}

export async function checkDocumentAgainstCodebook(
  documentPath: string,
  corpusName: string,
  k = 3,
): Promise<CodebookCheckResult> {
  let res: Response;
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), CODEBOOK_TIMEOUT_MS);
    res = await fetch(`${API_URL}/api/codebook/check`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ document_path: documentPath, corpus_name: corpusName, k }),
      signal: ctrl.signal,
      cache: "no-store",
    });
    clearTimeout(t);
  } catch {
    throw new CodebookUnavailableError(
      "Backend unreachable — checking a document needs the live SiteMind API, so there is no offline fallback for this action.",
    );
  }
  if (res.status === 404) {
    throw new CodebookUnavailableError(
      "Codebook is not enabled on this backend (CODEBOOK_ENABLED is off).",
    );
  }
  if (res.status === 503) {
    const detail = await res.json().catch(() => null);
    throw new CodebookUnavailableError(
      detail?.detail ?? "Codebook's own service (standards-service) is unreachable.",
    );
  }
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? `Check failed (HTTP ${res.status})`);
  }
  return (await res.json()) as CodebookCheckResult;
}

export async function checkDocumentAgainstCodebookUpload(
  file: File,
  corpusName: string,
  k = 3,
): Promise<CodebookCheckResult> {
  const form = new FormData();
  form.append("file", file);
  form.append("corpus_name", corpusName);
  form.append("k", String(k));
  let res: Response;
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), CODEBOOK_TIMEOUT_MS);
    res = await fetch(`${API_URL}/api/codebook/check-upload`, {
      method: "POST",
      body: form,
      signal: ctrl.signal,
      cache: "no-store",
    });
    clearTimeout(t);
  } catch {
    throw new CodebookUnavailableError(
      "Backend unreachable — checking a document needs the live SiteMind API, so there is no offline fallback for this action.",
    );
  }
  if (res.status === 404) {
    throw new CodebookUnavailableError(
      "Codebook is not enabled on this backend (CODEBOOK_ENABLED is off).",
    );
  }
  if (res.status === 503) {
    const detail = await res.json().catch(() => null);
    throw new CodebookUnavailableError(
      detail?.detail ?? "Codebook's own service (standards-service) is unreachable.",
    );
  }
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? `Check failed (HTTP ${res.status})`);
  }
  return (await res.json()) as CodebookCheckResult;
}

// ── Codebook Console (docs/codebook_console.md, backend/app/codebook_router.py
// "/console/..." routes, backed by codebook_rest_client.py's httpx client
// against standards-service's own REST retrieval API — NOT MCP) ───────────
// Same two-distinct-"off"-states honesty as the Codebook functions above:
// CODEBOOK_ENABLED=0 on this backend -> every route 404s ("disabled");
// CODEBOOK_ENABLED=1 but standards-service itself is unreachable -> 503
// ("unreachable"). Reuses CodebookUnavailableError/CodebookAvailability —
// this is the same underlying service, just a different transport.

export async function getCodebookConsoleCorpora(): Promise<{
  corpora: CodebookConsoleCorpus[];
  availability: CodebookAvailability;
}> {
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), CODEBOOK_TIMEOUT_MS);
    const res = await fetch(`${API_URL}/api/codebook/console/corpora`, {
      signal: ctrl.signal,
      cache: "no-store",
    });
    clearTimeout(t);
    if (res.status === 404) return { corpora: [], availability: "disabled" };
    if (res.status === 503) return { corpora: [], availability: "unreachable" };
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = (await res.json()) as CodebookConsoleCorpus[];
    return { corpora: data, availability: "available" };
  } catch {
    return { corpora: [], availability: "unreachable" };
  }
}

export async function getCodebookConsoleDocuments(
  corpusName: string,
): Promise<CodebookConsoleDocument[]> {
  let res: Response;
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), CODEBOOK_TIMEOUT_MS);
    res = await fetch(
      `${API_URL}/api/codebook/console/corpora/${encodeURIComponent(corpusName)}/documents`,
      { signal: ctrl.signal, cache: "no-store" },
    );
    clearTimeout(t);
  } catch {
    throw new CodebookUnavailableError(
      "Backend unreachable — listing documents needs the live SiteMind API, so there is no offline fallback for this action.",
    );
  }
  if (res.status === 404) {
    throw new CodebookUnavailableError(
      "Codebook is not enabled on this backend (CODEBOOK_ENABLED is off).",
    );
  }
  if (res.status === 503) {
    const detail = await res.json().catch(() => null);
    throw new CodebookUnavailableError(
      detail?.detail ?? "Codebook's own service (standards-service) is unreachable.",
    );
  }
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? `Listing documents failed (HTTP ${res.status})`);
  }
  return (await res.json()) as CodebookConsoleDocument[];
}

export async function uploadToCodebookConsole(
  file: File,
  corpusName: string,
): Promise<CodebookConsoleUploadResult> {
  const form = new FormData();
  form.append("file", file);
  form.append("corpus_name", corpusName);
  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/codebook/console/upload`, {
      method: "POST",
      body: form,
    });
  } catch {
    throw new CodebookUnavailableError(
      "Backend unreachable — Codebook Console upload needs the live SiteMind API, so there is no offline fallback for this action.",
    );
  }
  if (res.status === 404) {
    throw new CodebookUnavailableError(
      "Codebook is not enabled on this backend (CODEBOOK_ENABLED is off).",
    );
  }
  if (res.status === 503) {
    const detail = await res.json().catch(() => null);
    throw new CodebookUnavailableError(
      detail?.detail ?? "Codebook's own service (standards-service) is unreachable.",
    );
  }
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? `Upload failed (HTTP ${res.status})`);
  }
  return (await res.json()) as CodebookConsoleUploadResult;
}
