"use client";

import { useEffect, useRef, useState } from "react";
import {
  FileText,
  Play,
  Terminal,
  CheckCircle2,
  Loader2,
  Upload,
  AlertTriangle,
} from "lucide-react";
import {
  getActionBrief,
  getDocuments,
  ingestDocument,
  ingestRegisteredDocument,
  IngestUnavailableError,
  postFloorPlan,
  streamCompliance,
} from "@/lib/api";
import type { ActionBrief, ComplianceResult, DocItem, FloorPlanResult, IngestResult } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { Card, Overline, Button, Skeleton, cn } from "@/components/ui/primitives";
import { NCRCard } from "@/components/NCRCard";
import { ActionBriefCard } from "@/components/ActionBriefCard";
import { FloorMap } from "@/components/FloorMap";
import { domainMeta, statusMeta } from "@/lib/format";

type Phase = "idle" | "streaming" | "done";

const TYPE_LABEL: Record<string, string> = {
  design_basis: "Design Basis",
  submittal: "Submittal",
  mix_design: "Mix Design",
  rfi: "RFI",
};

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

export default function CompliancePage() {
  const [docs, setDocs] = useState<DocItem[] | null>(null);
  const [selected, setSelected] = useState<DocItem | null>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [trace, setTrace] = useState("");
  const [result, setResult] = useState<ComplianceResult | null>(null);
  const [live, setLive] = useState<boolean | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [ingestResult, setIngestResult] = useState<IngestResult | null>(null);
  // Which selected-doc id the current ingestResult was produced for — NOT the
  // same as ingestResult.document_id, which is the UPLOAD-xxxx id the register
  // row's real file was ingested into. Lets the extraction preview panel key
  // off "the currently selected register row" instead of the opaque upload id.
  const [ingestSourceId, setIngestSourceId] = useState<string | null>(null);
  const [ingestingSelected, setIngestingSelected] = useState(false);
  const [checkError, setCheckError] = useState<string | null>(null);
  const [actionBriefs, setActionBriefs] = useState<ActionBrief[] | null>(null);
  const [briefsLive, setBriefsLive] = useState<boolean | null>(null);
  const [floorPlanResult, setFloorPlanResult] = useState<FloorPlanResult | null>(null);
  const [floorPlanLoading, setFloorPlanLoading] = useState(false);
  const [floorPlanError, setFloorPlanError] = useState<string | null>(null);
  const cancelRef = useRef<(() => void) | null>(null);
  const traceEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    getDocuments().then((r) => {
      setDocs(r.data);
      const def =
        r.data.find((d) => d.type === "design_basis") ?? r.data[0] ?? null;
      setSelected(def);
    });
    return () => cancelRef.current?.();
  }, []);

  useEffect(() => {
    traceEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [trace]);

  async function runCheck() {
    if (!selected) return;
    cancelRef.current?.();
    setCheckError(null);
    setPhase("streaming");
    setTrace("");
    setResult(null);
    setLive(null);
    setActionBriefs(null);
    setBriefsLive(null);

    // Filesystem-backed register rows (has_file: true) carry a manifest id, not
    // an upload id — read the real file off disk and extract from it FIRST, so
    // the check that follows runs against real extracted parameters rather than
    // any pre-structured fixture. Already-uploaded rows (from "Upload DBR")
    // already have an upload id from ingestDocument(), so this step is skipped.
    let checkId = selected.id;
    if (selected.has_file) {
      setIngestingSelected(true);
      setTrace(
        `Reading ${selected.filename ?? selected.title} off disk and extracting checkable parameters…\n`,
      );
      try {
        const r = await ingestRegisteredDocument(selected.id);
        setIngestResult(r);
        setIngestSourceId(selected.id);
        checkId = r.document_id;
        setTrace(
          (t) =>
            t +
            `Extracted ${r.checkable_params} checkable parameter(s), abstained on ${r.abstained.length}.\n`,
        );
      } catch (e) {
        setIngestingSelected(false);
        setPhase("idle");
        setCheckError(
          e instanceof Error ? e.message : "Reading the real document failed.",
        );
        return;
      }
      setIngestingSelected(false);
    }

    cancelRef.current = streamCompliance(checkId, {
      onReasoning: (chunk) => setTrace((t) => t + chunk),
      onResult: (r) => {
        setResult(r);
        setPhase("done");
        if (r.ncrs.length > 0) {
          getActionBrief(checkId, r.ncrs).then(({ data, live: l }) => {
            setActionBriefs(data);
            setBriefsLive(l);
          });
        }
      },
      onSource: (isLive) => setLive(isLive),
    });
  }

  async function handleUpload(file: File) {
    setUploading(true);
    setUploadError(null);
    setIngestResult(null);
    setFloorPlanResult(null);
    setFloorPlanError(null);
    try {
      const r = await ingestDocument(file);
      setIngestResult(r);
      const uploadedDoc: DocItem = {
        id: r.document_id,
        title: `${r.title} (uploaded)`,
        type: "design_basis",
        status: "Pending",
        discipline: "Structural",
      };
      setIngestSourceId(uploadedDoc.id);
      setDocs((prev) => [uploadedDoc, ...(prev ?? [])]);
      setSelected(uploadedDoc);
      setPhase("idle");
      setResult(null);
      setTrace("");
      setCheckError(null);
    } catch (e) {
      setUploadError(
        e instanceof IngestUnavailableError
          ? e.message
          : e instanceof Error
            ? e.message
            : "Upload failed.",
      );
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }

    // Spatial extraction is a separate endpoint with its own honest
    // success/failure path — independent of the scalar ingest above.
    setFloorPlanLoading(true);
    try {
      const fp = await postFloorPlan(file);
      setFloorPlanResult(fp);
    } catch (e) {
      setFloorPlanError(e instanceof Error ? e.message : "Floor-plan check failed.");
    } finally {
      setFloorPlanLoading(false);
    }
  }

  function scrollToFinding(id: string) {
    document.getElementById(`spatial-finding-${id}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  return (
    <div>
      <PageHeader
        eyebrow="Automated Code Compliance"
        title="Compliance Check"
        subtitle="For the QA/QC manager — select a document, run the agent, and watch it cite the exact IS clause for every finding."
      />

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[320px_1fr]">
        {/* Document register */}
        <Card className="h-fit">
          <div className="flex items-center justify-between border-b border-line px-4 py-3">
            <Overline>Document register</Overline>
            <span className="font-mono text-xs text-text-lo">
              {docs?.length ?? "—"} docs
            </span>
          </div>

          {/* Legend for the A–E chip codes below — real AEC submittal-review
              status codes (A=Approved ... E=For Information), previously shown
              as a bare letter with no explanation anywhere on the page. */}
          <div className="flex flex-wrap gap-x-3 gap-y-1 border-b border-line px-4 py-2 font-mono text-[0.6rem] text-text-lo">
            <span><span className="text-pass">A</span> Approved</span>
            <span><span className="text-warning">B</span> Approved as noted</span>
            <span><span className="text-critical">C</span> Revise &amp; resubmit</span>
            <span><span className="text-critical">D</span> Rejected</span>
            <span><span className="text-text-mid">E</span> For information</span>
          </div>

          {/* Real document upload — reads the actual file, no fabricated data */}
          <div className="border-b border-line px-3 py-3">
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.docx,.txt,.md"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) handleUpload(f);
              }}
            />
            <Button
              variant="ghost"
              className="w-full justify-center"
              disabled={uploading}
              onClick={() => fileInputRef.current?.click()}
            >
              {uploading ? (
                <>
                  <Loader2 size={15} className="animate-spin" /> Reading document…
                </>
              ) : (
                <>
                  <Upload size={15} /> Upload DBR (PDF/DOCX/TXT)
                </>
              )}
            </Button>
            <p className="mt-1.5 font-mono text-[0.62rem] leading-snug text-text-lo">
              Reads the real file text; extracts only the checked parameter set and
              abstains on the rest instead of guessing.
            </p>
            {uploadError && (
              <p className="mt-1.5 flex items-start gap-1.5 text-[0.68rem] leading-snug text-critical">
                <AlertTriangle size={12} className="mt-0.5 shrink-0" />
                {uploadError}
              </p>
            )}
          </div>

          <ul className="p-2">
            {docs
              ? docs.map((d) => {
                  const sm = statusMeta(d.status);
                  const active = selected?.id === d.id;
                  return (
                    <li key={d.id}>
                      <button
                        onClick={() => setSelected(d)}
                        className={cn(
                          "w-full rounded px-3 py-2.5 text-left transition-colors duration-150",
                          active
                            ? "bg-bg-700"
                            : "hover:bg-bg-700/60",
                        )}
                        style={
                          active
                            ? { boxShadow: "inset 3px 0 0 var(--accent)" }
                            : undefined
                        }
                      >
                        <div className="flex items-start gap-2">
                          <FileText
                            size={15}
                            strokeWidth={1.5}
                            className="mt-0.5 shrink-0 text-text-lo"
                          />
                          <div className="min-w-0 flex-1">
                            <div className="text-sm leading-snug text-text-hi">
                              {d.title}
                            </div>
                            <div className="mt-1 flex items-center justify-between gap-2">
                              <span className="font-mono text-[0.66rem] text-text-lo">
                                {d.id}
                              </span>
                              <span
                                title={d.status}
                                className="rounded-chip px-1.5 py-0.5 font-mono text-[0.6rem] font-semibold"
                                style={{ color: sm.color, background: sm.bg }}
                              >
                                {d.status.split(" ")[0]}
                              </span>
                            </div>
                            <div className="mt-1 text-[0.66rem] text-text-lo">
                              {TYPE_LABEL[d.type] ?? d.type} · {d.discipline}
                            </div>
                            {/* Real-file proof: filename + size only exist for
                                filesystem-backed register rows (has_file: true) —
                                this is the visible evidence there's a real
                                document behind this row, not a synthetic one. */}
                            {d.has_file && (
                              <div
                                className="mt-1 flex items-center gap-1 truncate font-mono text-[0.62rem] text-text-lo"
                                title={d.filename}
                              >
                                <span className="text-pass">●</span>
                                <span className="truncate">{d.filename}</span>
                                {typeof d.size_bytes === "number" && (
                                  <span className="shrink-0">· {formatBytes(d.size_bytes)}</span>
                                )}
                              </div>
                            )}
                          </div>
                        </div>
                      </button>
                    </li>
                  );
                })
              : [0, 1, 2, 3].map((i) => (
                  <Skeleton key={i} className="m-1 h-16" />
                ))}
          </ul>
        </Card>

        {/* Run + reasoning + results */}
        <div className="space-y-5">
          <Card className="flex items-center justify-between px-5 py-4">
            <div className="min-w-0">
              <Overline>Selected document</Overline>
              <div className="mt-1 truncate text-sm font-medium text-text-hi">
                {selected?.title ?? "—"}
              </div>
              <div className="font-mono text-xs text-text-lo">
                {selected?.id}
              </div>
            </div>
            <Button
              onClick={runCheck}
              disabled={!selected || phase === "streaming"}
            >
              {phase === "streaming" ? (
                <>
                  <Loader2 size={16} className="animate-spin" />{" "}
                  {ingestingSelected ? "Reading document…" : "Checking…"}
                </>
              ) : (
                <>
                  <Play size={16} /> Run compliance check
                </>
              )}
            </Button>
          </Card>

          {checkError && (
            <p className="flex items-start gap-1.5 text-[0.8rem] leading-snug text-critical">
              <AlertTriangle size={13} className="mt-0.5 shrink-0" />
              {checkError}
            </p>
          )}

          {/* Real extraction preview — shown after ingest, before/alongside the check.
              Keyed on ingestSourceId (the register row / upload id that produced this
              ingestResult), not ingestResult.document_id itself — for register rows
              those are two different ids (manifest id vs. the fresh UPLOAD-xxxx id). */}
          {ingestResult && selected?.id === ingestSourceId && (() => {
            // A layout document genuinely has zero rebar/structural figures to
            // extract — that's correct abstention, not a failure. But rendered
            // as ~15 abstention lines directly above the floor-map panel, it
            // reads as one. When the spatial path found real spatial data on
            // this same upload, re-order emphasis: one honest sentence saying
            // why the structural/electrical set doesn't apply, with the full
            // abstention list still reachable in one click, never hidden.
            const isLayoutDocNoScalar =
              floorPlanResult?.has_spatial_data === true && ingestResult.extracted.length === 0;
            return (
              <Card className="px-5 py-4">
                <div className="flex items-center justify-between">
                  <Overline>Extracted from the uploaded document</Overline>
                  <span className="font-mono text-[0.66rem] text-text-lo">
                    {ingestResult.checkable_params} found · {ingestResult.abstained.length} abstained
                  </span>
                </div>
                {ingestResult.extracted.length > 0 ? (
                  <ul className="mt-3 space-y-2">
                    {ingestResult.extracted.map((p, i) => (
                      <li key={i} className="text-sm">
                        <div className="text-text-hi">
                          {p.element} · {p.param.replace(/_/g, " ")} ={" "}
                          <span className="font-mono">{p.value} {p.unit}</span>
                        </div>
                        <p className="mt-0.5 font-mono text-[0.68rem] leading-snug text-text-lo">
                          &ldquo;{p.source_quote}&rdquo;
                        </p>
                      </li>
                    ))}
                  </ul>
                ) : isLayoutDocNoScalar ? (
                  <p className="mt-3 text-sm text-text-mid">
                    This is a layout / design-basis document describing rooms, equipment and egress —
                    it doesn&rsquo;t state structural figures like rebar cover, concrete grade or w/c
                    ratio, so the structural/electrical parameter set genuinely doesn&rsquo;t apply here.
                    See the floor-plan panel below for what this document <em>was</em> checked against.
                  </p>
                ) : (
                  <p className="mt-3 text-sm text-text-mid">
                    No parameters could be confidently extracted from this document — see the abstained
                    list below for why. Running a compliance check on it will find 0 checkable parameters.
                  </p>
                )}
                {ingestResult.abstained.length > 0 &&
                  (isLayoutDocNoScalar ? (
                    <details className="mt-4 border-t border-line pt-3">
                      <summary className="flex cursor-pointer items-center gap-1.5 text-[0.7rem] font-medium text-text-lo">
                        <AlertTriangle size={12} />
                        Why no structural parameters? ({ingestResult.abstained.length} abstained)
                      </summary>
                      <ul className="mt-1.5 space-y-1">
                        {ingestResult.abstained.map((a, i) => (
                          <li key={i} className="text-[0.72rem] leading-snug text-text-lo">
                            <span className="font-mono text-text-mid">{a.param.replace(/_/g, " ")}</span>
                            {" — "}
                            {a.reason}
                          </li>
                        ))}
                      </ul>
                    </details>
                  ) : (
                    <div className="mt-4 border-t border-line pt-3">
                      <div className="flex items-center gap-1.5 text-[0.7rem] font-medium text-text-lo">
                        <AlertTriangle size={12} /> Abstained — not found or not confidently extractable
                      </div>
                      <ul className="mt-1.5 space-y-1">
                        {ingestResult.abstained.map((a, i) => (
                          <li key={i} className="text-[0.72rem] leading-snug text-text-lo">
                            <span className="font-mono text-text-mid">{a.param.replace(/_/g, " ")}</span>
                            {" — "}
                            {a.reason}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
              </Card>
            );
          })()}

          {/* Floor Plan — spatial compliance (docs/superpowers/specs/2026-07-25-spatial-compliance-design.md §6).
              Populated by the same upload; a separate endpoint with its own
              honest success/failure/abstention story. */}
          {(floorPlanLoading || floorPlanResult || floorPlanError) && (
            <Card className="px-5 py-4">
              <div className="flex items-center justify-between">
                <Overline>Floor Plan · spatial compliance</Overline>
                {floorPlanResult && (
                  <span className="font-mono text-[0.66rem] text-text-lo">
                    {floorPlanResult.coverage.params_extracted} extracted ·{" "}
                    {floorPlanResult.coverage.params_checked} checked ·{" "}
                    {floorPlanResult.coverage.abstained} abstained
                  </span>
                )}
              </div>

              {floorPlanLoading && (
                <div className="mt-3 flex items-center gap-2 text-sm text-text-mid">
                  <Loader2 size={15} className="animate-spin" /> Extracting spatial geometry from the
                  document…
                </div>
              )}

              {floorPlanError && !floorPlanLoading && (
                <p className="mt-3 flex items-start gap-1.5 text-[0.8rem] leading-snug text-critical">
                  <AlertTriangle size={13} className="mt-0.5 shrink-0" />
                  {floorPlanError}
                </p>
              )}

              {floorPlanResult && !floorPlanLoading && (
                <>
                  {!floorPlanResult.has_spatial_data ? (
                    <p className="mt-3 text-sm leading-relaxed text-text-mid">
                      {floorPlanResult.reason ?? "No spatial data found in this document."}
                    </p>
                  ) : (
                    <div className="mt-4 space-y-4">
                      {floorPlanResult.floor_plan && (
                        <FloorMap
                          floorPlan={floorPlanResult.floor_plan}
                          findings={floorPlanResult.findings}
                          notCheckedZones={floorPlanResult.not_checked_zones}
                          onPinClick={scrollToFinding}
                        />
                      )}

                      {/* not_checked_zones — a visible caption, not a tooltip */}
                      {floorPlanResult.not_checked_zones.length > 0 && (
                        <div className="rounded border border-line bg-bg-900/50 px-3.5 py-2.5">
                          <div className="overline mb-1" style={{ color: "var(--warning)" }}>
                            Rendered but deliberately not checked
                          </div>
                          <ul className="space-y-1">
                            {floorPlanResult.not_checked_zones.map((z) => (
                              <li key={z.zone} className="text-[0.78rem] leading-snug text-text-mid">
                                <span className="font-mono text-text-hi">{z.zone.replace(/_/g, " ")}</span>
                                {" — "}
                                {z.reason}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {/* spatial findings, id-anchored so map pins can scroll to them,
                          reusing the existing NCRCard (which itself renders
                          CitedClauseBox -> ClauseViewerModal, unchanged). */}
                      {floorPlanResult.findings.length > 0 && (
                        <div className="space-y-3">
                          <Overline>Spatial findings</Overline>
                          {floorPlanResult.findings.map((f, i) => (
                            <div key={f.id} id={`spatial-finding-${f.id}`}>
                              <NCRCard ncr={f} index={i} />
                            </div>
                          ))}
                        </div>
                      )}

                      {/* abstentions — treated as a feature, always visible */}
                      {floorPlanResult.abstentions.length > 0 && (
                        <div className="rounded border border-line bg-bg-900/50 px-3.5 py-2.5">
                          <div className="flex items-center gap-1.5 text-[0.7rem] font-medium text-text-lo">
                            <AlertTriangle size={12} /> Abstained — no verdict rather than a guess
                          </div>
                          <ul className="mt-1.5 space-y-1.5">
                            {floorPlanResult.abstentions.map((a, i) => (
                              <li key={i} className="text-[0.75rem] leading-snug text-text-lo">
                                <span className="font-mono text-text-mid">{a.what}</span>
                                {" — "}
                                {a.why}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  )}
                </>
              )}
            </Card>
          )}

          {/* Reasoning panel — the "alive" moment */}
          {phase !== "idle" && (
            <Card glow={phase === "streaming"} className="overflow-hidden">
              <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
                <div className="flex items-center gap-2">
                  <Terminal size={15} strokeWidth={1.5} className="text-accent" />
                  <Overline>Agent reasoning trace</Overline>
                </div>
                {live !== null && (
                  // "live" here means the SSE stream is genuinely coming from the
                  // backend — NOT that the text is model-generated. The trace is a
                  // deterministic per-parameter-type string table (`_reasoning_trace`
                  // in compliance.py), which is the honest thing for it to be: this
                  // panel narrates steps that are themselves deterministic. Label it
                  // for what it is so nobody reads it as the model thinking aloud.
                  <span
                    className="font-mono text-[0.66rem] text-text-lo"
                    title={
                      live
                        ? "Streamed live from the backend. The trace text is deterministic, not model-generated — it narrates the same Python steps that compute the verdict."
                        : "Backend unreachable — this is a simulated stream of mock data."
                    }
                  >
                    {live ? "● backend SSE · deterministic trace" : "● simulated · mock stream"}
                  </span>
                )}
              </div>
              <div className="relative max-h-56 overflow-y-auto px-4 py-3">
                {phase === "streaming" && (
                  <div className="scanline animate-scan" />
                )}
                <pre className="whitespace-pre-wrap font-mono text-[0.78rem] leading-relaxed text-text-mid">
                  {trace}
                  {phase === "streaming" && (
                    <span className="ml-0.5 inline-block h-3.5 w-2 translate-y-0.5 bg-accent animate-blink" />
                  )}
                </pre>
                <div ref={traceEndRef} />
              </div>
            </Card>
          )}

          {/* Results */}
          {result && phase === "done" && (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center gap-x-6 gap-y-2 rounded-card border border-line bg-bg-800 px-5 py-3.5">
                <div className="flex items-center gap-2">
                  <CheckCircle2 size={16} className="text-pass" />
                  <span className="text-sm text-text-mid">
                    Checked{" "}
                    <span className="font-mono text-text-hi">
                      {result.checked_params}
                    </span>{" "}
                    parameters
                  </span>
                </div>
                <div className="text-sm text-text-mid">
                  <span className="font-mono text-critical">
                    {result.ncrs.length}
                  </span>{" "}
                  finding(s)
                </div>
                <div className="text-sm text-text-mid">
                  <span className="font-mono text-pass">
                    {result.conforming.length}
                  </span>{" "}
                  conforming
                </div>
                {result.coverage && (
                  <div className="ml-auto flex items-center gap-2 text-sm text-text-mid">
                    <span className="font-mono text-text-hi">
                      {result.coverage.clauses_cited}
                    </span>
                    <span>clauses cited across</span>
                    <span className="font-mono text-text-hi">
                      {result.coverage.standards.length}
                    </span>
                    <span>standards</span>
                  </div>
                )}
              </div>

              {/* Coverage meter — honest depth-of-review */}
              {result.coverage && (
                <Card className="px-5 py-3.5">
                  <div className="flex items-center justify-between">
                    <Overline>Coverage this review</Overline>
                    <span className="font-mono text-[0.66rem] text-text-lo">
                      {result.coverage.checks_run} deterministic checks ·{" "}
                      {result.coverage.library_clauses} clauses in library
                    </span>
                  </div>
                  {result.coverage.standards_by_domain &&
                  Object.keys(result.coverage.standards_by_domain).length > 0 ? (
                    <div className="mt-3 space-y-2.5">
                      {Object.entries(result.coverage.standards_by_domain).map(([domain, stds]) => {
                        const dm = domainMeta[domain] ?? domainMeta.structural;
                        return (
                          <div key={domain} className="flex flex-wrap items-center gap-2">
                            <span
                              className="rounded-chip px-2 py-0.5 font-mono text-[0.66rem] font-semibold uppercase tracking-wide"
                              style={{ color: dm.color, background: dm.bg }}
                            >
                              {dm.label}
                            </span>
                            {stds.map((s) => (
                              <span
                                key={s}
                                className="rounded-chip border border-line bg-bg-900/60 px-2.5 py-1 font-mono text-[0.72rem] text-text-mid"
                              >
                                {s}
                              </span>
                            ))}
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {result.coverage.standards.map((s) => (
                        <span
                          key={s}
                          className="rounded-chip border border-line bg-bg-900/60 px-2.5 py-1 font-mono text-[0.72rem] text-text-mid"
                        >
                          {s}
                        </span>
                      ))}
                    </div>
                  )}
                </Card>
              )}

              {/* Overlapping requirements — multi-clause governance */}
              {result.overlaps && result.overlaps.length > 0 && (
                <Card className="px-5 py-4">
                  <Overline>Overlapping requirements · binding clause resolved</Overline>
                  <ul className="mt-3 space-y-3">
                    {result.overlaps.map((o, i) => (
                      <li key={i} className="text-sm">
                        <div className="text-text-hi">
                          {o.item} · {o.param.replace(/_/g, " ")}
                        </div>
                        <p className="mt-1 text-text-mid">{o.note}</p>
                        <div className="mt-1.5 flex flex-wrap items-center gap-1.5 font-mono text-[0.7rem]">
                          {o.clauses.map((c) => (
                            <span
                              key={c}
                              className={cn(
                                "rounded-chip px-2 py-0.5",
                                c === o.governing
                                  ? "bg-accent/15 text-accent"
                                  : "border border-line text-text-lo",
                              )}
                            >
                              {c === o.governing ? "● binding · " : ""}
                              {c}
                            </span>
                          ))}
                        </div>
                      </li>
                    ))}
                  </ul>
                </Card>
              )}

              {result.ncrs.map((ncr, i) => (
                <NCRCard key={ncr.id} ncr={ncr} index={i} />
              ))}

              {actionBriefs && actionBriefs.length > 0 && (
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <Overline>Action Brief · finding → linked evidence → owner action</Overline>
                    {briefsLive !== null && (
                      <span className="font-mono text-[0.66rem] text-text-lo">
                        {briefsLive ? "● live · backend" : "● derived client-side (backend unreachable)"}
                      </span>
                    )}
                  </div>
                  {actionBriefs.map((b, i) => (
                    <ActionBriefCard key={b.finding_id} brief={b} index={i} />
                  ))}
                </div>
              )}

              {result.conforming.length > 0 && (
                <Card className="px-5 py-4">
                  <Overline>Conforming parameters</Overline>
                  <ul className="mt-3 space-y-1.5">
                    {result.conforming.map((c, i) => (
                      <li
                        key={i}
                        className="flex items-start gap-2 text-sm text-text-mid"
                      >
                        <CheckCircle2
                          size={14}
                          className="mt-0.5 shrink-0 text-pass"
                        />
                        {c}
                      </li>
                    ))}
                  </ul>
                </Card>
              )}

              {result.checked_params === 0 && (
                <Card className="px-5 py-4">
                  <p className="text-sm text-text-mid">
                    No checkable parameters were found in this document — nothing to report against the
                    check registry. This can happen on a real upload whose text doesn&rsquo;t confidently
                    match the narrow parameter set SiteMind extracts (see the abstained list above).
                  </p>
                </Card>
              )}
            </div>
          )}

          {/* Empty state */}
          {phase === "idle" && (
            <Card className="grid place-items-center px-5 py-16 text-center">
              <Terminal
                size={28}
                strokeWidth={1.2}
                className="mb-3 text-text-lo"
              />
              <p className="text-sm text-text-mid">
                No checks run yet — select a document and press{" "}
                <span className="font-medium text-text-hi">
                  Run compliance check
                </span>
                .
              </p>
              <p className="mt-1 font-mono text-xs text-text-lo">
                The agent streams its reasoning, then renders cited NCRs.
              </p>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
