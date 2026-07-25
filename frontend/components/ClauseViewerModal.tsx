"use client";

import { useEffect, useRef, useState } from "react";
import { ExternalLink, X } from "lucide-react";
import type { Citation, ClauseContext } from "@/lib/types";
import { getClauseContext } from "@/lib/api";
import { sourceTypeMeta } from "@/lib/format";

// The in-app clause viewer popup (2026-07-25 follow-up): CitedClauseBox used
// to send an engineer straight to an external verify_url. Now it opens this
// modal instead, which shows the real digitised source document's own text
// (read directly off disk by GET /api/clause-context) — the actual clause in
// its actual document, not a generic link to a whole scanned standard.
export function ClauseViewerModal({
  citation,
  onClose,
}: {
  citation: Citation;
  onClose: () => void;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const [ctx, setCtx] = useState<ClauseContext | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getClauseContext(citation.standard, citation.clause).then(({ data }) => {
      if (!cancelled) {
        setCtx(data);
        setLoading(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [citation.standard, citation.clause]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  function onOverlayClick(e: React.MouseEvent) {
    if (panelRef.current && !panelRef.current.contains(e.target as Node)) onClose();
  }

  const st = sourceTypeMeta[citation.source_type ?? "codebook_verified"];

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 p-4"
      onMouseDown={onOverlayClick}
      role="presentation"
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={`Clause viewer — ${citation.standard} Cl. ${citation.clause}`}
        className="flex max-h-[85vh] w-full max-w-2xl flex-col rounded border border-line bg-bg-800 shadow-2xl"
      >
        <div className="flex items-start justify-between gap-3 border-b border-line px-5 py-4">
          <div>
            <span
              className="font-mono inline-flex items-center gap-1.5 rounded-chip px-2 py-0.5 text-[0.68rem] font-bold uppercase tracking-wider"
              style={{ color: st.color, background: st.bg, border: `1px solid ${st.color}40` }}
            >
              ◢ {st.label}
            </span>
            <div className="mt-2 flex flex-wrap items-baseline gap-x-3">
              <span className="clause text-lg font-semibold text-text-hi">{citation.standard}</span>
              <span className="clause text-sm text-text-mid">Cl. {citation.clause}</span>
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="rounded p-1 text-text-lo transition-colors hover:bg-bg-700 hover:text-text-hi"
          >
            <X size={18} />
          </button>
        </div>

        <div className="overflow-y-auto px-5 py-4">
          <div className="mb-4">
            <div className="overline mb-1">Cited clause text</div>
            <p className="font-sans text-[0.95rem] italic leading-relaxed text-text-mid">
              &ldquo;{citation.text}&rdquo;
            </p>
          </div>

          <div>
            <div className="overline mb-1">Source document</div>
            {loading && <p className="text-sm text-text-lo">Loading the real source document…</p>}
            {!loading && ctx?.has_context && (
              <>
                {ctx.heading && (
                  <p className="mb-1.5 font-mono text-xs text-text-lo">§ {ctx.heading}</p>
                )}
                <pre className="max-h-80 overflow-y-auto whitespace-pre-wrap rounded bg-bg-900 p-3 font-mono text-[0.8rem] leading-relaxed text-text-mid">
                  {ctx.context_text}
                </pre>
                {ctx.filename && (
                  <p className="mt-1.5 font-mono text-[0.68rem] text-text-lo">
                    standards-service/data/structural_corpus/{ctx.filename}
                  </p>
                )}
              </>
            )}
            {!loading && ctx && !ctx.has_context && (
              <p className="text-sm text-text-lo">{ctx.note}</p>
            )}
          </div>
        </div>

        <div className="flex items-center justify-between gap-3 border-t border-line px-5 py-3">
          <p className="text-[0.68rem] text-text-lo">
            {ctx?.has_context
              ? "Verbatim excerpt, read directly from the digitised source file on disk."
              : "No in-app source excerpt available for this citation — the link below opens the primary source."}
          </p>
          <a
            href={citation.verify_url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex shrink-0 items-center gap-1.5 text-sm font-medium text-data transition-colors hover:text-[#7cd4fb]"
          >
            Primary source <ExternalLink size={13} strokeWidth={2} />
          </a>
        </div>
      </div>
    </div>
  );
}
