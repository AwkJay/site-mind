"use client";

import { useState } from "react";
import { FileSearch } from "lucide-react";
import type { Citation } from "@/lib/types";
import { sourceTypeMeta } from "@/lib/format";
import { ClauseViewerModal } from "./ClauseViewerModal";

// THE signature component. A cited clause rendered as a verified system fact:
// lime left-border, provenance badge, mono clause id + exact text, verify link.
// The badge is NEVER a generic "Verified" — it discloses the real source_type
// (Codebook / primary native PDF / primary OCR scan / cross-source) so a
// non-Codebook citation is never presented as equivalent to a Codebook one.
export function CitedClauseBox({
  citation,
  advisory,
}: {
  citation: Citation;
  advisory?: boolean;
}) {
  const st = sourceTypeMeta[citation.source_type ?? "codebook_verified"];
  const accent = advisory ? "var(--info)" : st.color;
  const badgeBg = advisory ? "var(--info-bg)" : st.bg;
  const [viewerOpen, setViewerOpen] = useState(false);
  return (
    <div
      className="relative rounded bg-bg-700 px-4 py-3"
      style={{
        borderLeft: `3px solid ${accent}`,
        boxShadow: advisory ? undefined : "0 0 0 1px var(--accent-glow)",
      }}
    >
      <div className="flex items-center justify-between gap-2">
        <span
          className="font-mono inline-flex items-center gap-1.5 rounded-chip px-2 py-0.5 text-[0.68rem] font-bold uppercase tracking-wider"
          title={st.caveat}
          style={{ color: accent, background: badgeBg, border: `1px solid ${accent}40` }}
        >
          ◢ {st.label}
        </span>
        <span className="font-mono text-[0.7rem] text-text-lo">
          ground truth · clauses.json
        </span>
      </div>
      {citation.source_type && citation.source_type !== "codebook_verified" && (
        <p className="mt-1.5 text-[0.7rem] leading-snug text-text-lo">{st.caveat}</p>
      )}

      <div className="mt-2 flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="clause text-base font-semibold text-text-hi">
          {citation.standard}
        </span>
        <span className="clause text-sm text-text-mid">
          Cl. {citation.clause}
        </span>
      </div>

      <p className="mt-1.5 font-sans text-[0.95rem] italic leading-relaxed text-text-mid">
        &ldquo;{citation.text}&rdquo;
      </p>

      {/* Retrieval provenance (Compliance pillar only — set by clause_resolver.py).
          "vector_index" = independently confirmed live against the Actian-backed
          corpus, not just a hardcoded lookup. "local_cache" is a visible, honest
          FEATURE — the index didn't surface this clause, so the demo falls back
          to the pre-vetted digitised copy rather than papering over the miss. */}
      {citation.retrieval?.resolved_via === "vector_index" && (
        <div
          className="mt-2.5 rounded bg-bg-700 px-2.5 py-2 font-mono text-[0.68rem] leading-relaxed"
          style={{ border: "1px solid var(--accent-glow)" }}
        >
          <div className="flex flex-wrap items-center justify-between gap-x-2 gap-y-0.5">
            <span
              className="font-bold uppercase tracking-wider"
              style={{ color: "var(--accent)" }}
            >
              ◆ Retrieved from vector index
            </span>
            {typeof citation.retrieval.vectors_searched === "number" && (
              <span className="text-text-lo">
                {citation.retrieval.vectors_searched.toLocaleString()} vectors searched
              </span>
            )}
          </div>
          {citation.retrieval.query && (
            <div className="mt-1 text-text-lo">
              query: &ldquo;{citation.retrieval.query}&rdquo;
            </div>
          )}
          <div className="mt-0.5 text-text-mid">
            {citation.retrieval.rank != null && <>rank {citation.retrieval.rank}</>}
            {citation.retrieval.score != null && <> · score {citation.retrieval.score.toFixed(3)}</>}
            {citation.retrieval.chunk_source && <> · {citation.retrieval.chunk_source}</>}
          </div>
        </div>
      )}
      {citation.retrieval?.resolved_via === "local_cache" && (
        <div
          className="mt-2.5 rounded px-2.5 py-2 font-mono text-[0.68rem] leading-relaxed"
          style={{ border: "1px solid var(--warning)66", background: "var(--warning-bg)" }}
        >
          <span
            className="font-bold uppercase tracking-wider"
            style={{ color: "var(--warning)" }}
          >
            ▲ Vector index fallback
          </span>
          <div className="mt-1 text-text-lo">
            {citation.retrieval.note ??
              "The vector index did not surface a confirmed match for this clause — citing the locally cached digitised copy instead."}
          </div>
        </div>
      )}

      <button
        onClick={() => setViewerOpen(true)}
        className="mt-2.5 inline-flex items-center gap-1.5 text-sm font-medium text-data transition-colors hover:text-[#7cd4fb]"
      >
        <span aria-hidden>↳</span> View standard
        <FileSearch size={13} strokeWidth={2} />
      </button>

      {viewerOpen && (
        <ClauseViewerModal citation={citation} onClose={() => setViewerOpen(false)} />
      )}
    </div>
  );
}
