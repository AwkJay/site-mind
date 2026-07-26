import { FileSearch, ShieldAlert, Wrench, Info, Layers, FlaskConical } from "lucide-react";
import type { ExtractedRule, NCR } from "@/lib/types";
import { domainMeta, severityMeta, tierMeta } from "@/lib/format";
import { CitedClauseBox } from "./CitedClauseBox";
import { Chip } from "./ui/primitives";

// Plain-language statement of what an ExtractedRule requires, derived only
// from the rule's own fields (never the submitted value — that half of the
// story is `computed_detail`, computed and printed verbatim by rule_eval.py).
function describeRule(rule: ExtractedRule): string {
  const unit = rule.unit ? ` ${rule.unit}` : "";
  switch (rule.kind) {
    case "compare":
      return `value ${rule.operator ?? "?"} ${rule.threshold ?? "?"}${unit}`;
    case "range":
      return `value between ${rule.inputs?.min ?? "?"} and ${rule.inputs?.max ?? "?"}${unit}`;
    case "min_of":
      return `value must not exceed the least of the stated limits${unit}`;
    case "max_of":
      return `value must be at least the greatest of the stated limits${unit}`;
    case "table_lookup":
      return `value ${rule.operator ?? ">="} the applicable table threshold${unit}`;
    case "formula":
      return `value ${rule.operator ?? ">="} (${rule.expression ?? "?"})${unit}`;
    default:
      return "no checkable numeric rule stated";
  }
}

// The "computed_draft" tier's signature UI: an LLM only READ the rule
// (Interpretation half); rule_eval.py COMPUTED the verdict (Computation half,
// printed verbatim — never re-derived in the frontend).
function TieredVerdictPanel({ ncr }: { ncr: NCR }) {
  const rule = ncr.extracted_rule;
  if (!rule) return null;
  return (
    <div className="mt-3 grid gap-3 sm:grid-cols-2">
      <div className="rounded border border-warning/30 bg-bg-900/50 px-3 py-2.5">
        <div className="overline mb-1" style={{ color: "var(--warning)" }}>
          Interpretation · what the clause requires
        </div>
        <p className="text-sm leading-relaxed text-text-mid">
          <span className="font-mono text-text-hi">{describeRule(rule)}</span>
        </p>
        <blockquote className="mt-1.5 rounded bg-bg-900/60 px-2.5 py-1.5 text-[0.8rem] italic leading-snug text-text-lo">
          &ldquo;{rule.clause_phrase}&rdquo;
        </blockquote>
      </div>
      <div className="rounded border border-warning/30 bg-bg-900/50 px-3 py-2.5">
        <div className="overline mb-1" style={{ color: "var(--warning)" }}>
          Computation · what your value does
        </div>
        <p className="font-mono text-sm leading-relaxed text-text-hi">
          {ncr.computed_detail ?? "—"}
        </p>
      </div>
    </div>
  );
}

export function NCRCard({ ncr, index }: { ncr: NCR; index: number }) {
  const meta = severityMeta[ncr.severity];
  const advisory = ncr.severity === "ADVISORY";
  const dm = domainMeta[ncr.domain ?? "structural"];
  const tier = tierMeta[ncr.verdict_tier ?? "certified"];
  const draft = ncr.verdict_tier === "computed_draft";
  // The tier chip describes how the VERDICT was computed; the citation badge
  // describes how trustworthy the SOURCE is. They're independent axes, and on a
  // cross-source-unverified clause (e.g. Commissioning's compiled ASHRAE
  // envelope) showing a green "Certified · pre-vetted" chip beside a red
  // "Cross-source · unverified" one reads as self-contradictory. Suppress the
  // tier chip in exactly that case — never suppress a DRAFT chip, which is a
  // warning the reader must always see.
  const showTier = draft || ncr.citation?.source_type !== "cross_source_unverified";
  return (
    <article
      className="animate-fadeUp rounded-card border border-line bg-bg-800"
      style={{ borderLeft: `3px solid ${meta.border}`, animationDelay: `${index * 90}ms` }}
    >
      <header className="flex items-start justify-between gap-3 border-b border-line px-5 py-3.5">
        <div className="flex items-center gap-3">
          <span className="font-mono text-sm font-semibold text-text-hi">
            {ncr.id}
          </span>
          <span className="text-text-lo">·</span>
          <span className="text-sm text-text-mid">{ncr.item}</span>
        </div>
        <div className="flex items-center gap-2">
          <Chip color={dm.color} bg={dm.bg}>
            {dm.label}
          </Chip>
          <Chip color={meta.color} bg={meta.bg}>
            <span aria-hidden>{meta.icon}</span> {meta.label}
          </Chip>
          {showTier && (
            <Chip color={tier.color} bg={tier.bg}>
              {tier.label}
            </Chip>
          )}
        </div>
      </header>

      <div className="space-y-4 px-5 py-4">
        {/* Finding */}
        <div className="flex gap-3">
          <ShieldAlert
            size={18}
            strokeWidth={1.5}
            className="mt-0.5 shrink-0"
            style={{ color: meta.color }}
          />
          <div>
            <div className="overline mb-1">Finding</div>
            <p className="text-[0.95rem] leading-relaxed text-text-hi">
              {ncr.finding}
            </p>
          </div>
        </div>

        {/* Source span — proves it came from the document */}
        {ncr.source && (
          <div className="flex gap-3">
            <FileSearch
              size={18}
              strokeWidth={1.5}
              className="mt-0.5 shrink-0 text-text-lo"
            />
            <div className="min-w-0">
              <div className="overline mb-1">Source in document</div>
              <blockquote className="rounded bg-bg-900/60 px-3 py-2 text-sm text-text-mid">
                <span className="italic">&ldquo;{ncr.source.quote}&rdquo;</span>
                <span className="mt-1 block font-mono text-[0.72rem] text-text-lo">
                  {ncr.source.location}
                </span>
              </blockquote>
            </div>
          </div>
        )}

        {/* The cited clause box — the hero */}
        {ncr.citation && (
          <CitedClauseBox citation={ncr.citation} advisory={advisory} />
        )}

        {/* computed_draft tier: the LLM only read the rule, rule_eval.py computed
            it — an engineer must confirm before this counts as a non-conformance. */}
        {draft && (
          <div
            className="rounded px-4 py-3"
            style={{ background: "var(--warning-bg)", border: "1px solid #f59e0b33" }}
          >
            <div className="flex items-center gap-2">
              <FlaskConical size={15} strokeWidth={1.8} style={{ color: "var(--warning)" }} />
              <span
                className="overline"
                style={{ color: "var(--warning)", letterSpacing: "0.08em" }}
              >
                DRAFT · engineer must confirm the reading
              </span>
            </div>
            <p className="mt-1.5 text-sm leading-relaxed text-text-hi">
              No pre-vetted check covers this parameter. An LLM read the rule below out of the
              cited clause — it never decided pass/fail — and the evaluator computed the verdict.
            </p>
            <TieredVerdictPanel ncr={ncr} />
          </div>
        )}

        {/* Multi-clause governance — names the binding requirement */}
        {ncr.governing_note && (
          <div className="flex gap-3">
            <Layers
              size={18}
              strokeWidth={1.5}
              className="mt-0.5 shrink-0 text-accent"
            />
            <div>
              <div className="overline mb-1">Governing requirement</div>
              <p className="rounded border-l-2 border-accent/40 bg-bg-900/50 px-3 py-2 text-sm leading-relaxed text-text-mid">
                {ncr.governing_note}
              </p>
            </div>
          </div>
        )}

        {/* Why it matters */}
        <div>
          <div className="overline mb-1">Why it matters</div>
          <p className="text-sm leading-relaxed text-text-mid">
            {ncr.why_it_matters}
          </p>
        </div>

        {/* Corrective action OR advisory recommendation */}
        {advisory ? (
          <div
            className="rounded px-4 py-3"
            style={{ background: "var(--info-bg)", border: "1px solid #38bdf833" }}
          >
            <div className="flex items-center gap-2">
              <Info size={15} strokeWidth={1.8} style={{ color: "var(--info)" }} />
              <span
                className="overline"
                style={{ color: "var(--info)", letterSpacing: "0.08em" }}
              >
                Advisory · Judgment call
              </span>
            </div>
            <p className="mt-1.5 text-sm leading-relaxed text-text-hi">
              {ncr.recommendation}
            </p>
            {ncr.confirm_with && (
              <p className="mt-2 text-xs text-text-mid">
                <span className="font-mono">↳</span> Confirm with{" "}
                <span className="font-semibold text-text-hi">
                  {ncr.confirm_with}
                </span>{" "}
                before incorporation.
              </p>
            )}
          </div>
        ) : (
          <div className="flex gap-3">
            <Wrench
              size={18}
              strokeWidth={1.5}
              className="mt-0.5 shrink-0 text-accent"
            />
            <div>
              <div className="overline mb-1">Corrective action</div>
              <p className="rounded border-l-2 border-accent/40 bg-bg-900/50 px-3 py-2 text-sm leading-relaxed text-text-hi">
                {ncr.corrective_action}
              </p>
            </div>
          </div>
        )}
      </div>
    </article>
  );
}
