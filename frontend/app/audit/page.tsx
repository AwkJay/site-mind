"use client";

import { useCallback, useEffect, useState } from "react";
import { Database, ExternalLink, HardDrive, Link2, RefreshCw, ShieldCheck, ShieldX } from "lucide-react";
import { anchorAllPending, anchorAuditEvent, getAudit, getHealth, seedAudit, verifyAuditEvent } from "@/lib/api";
import type { AuditEvent } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { Button, Card, Chip, Skeleton } from "@/components/ui/primitives";
import { severityMeta } from "@/lib/format";

function fmtTime(unixSeconds: number): string {
  return new Date(unixSeconds * 1000).toLocaleString("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function severityOf(payload: Record<string, unknown>): string | null {
  const s = payload["severity"];
  return typeof s === "string" ? s : null;
}

function solanaMeta(status: string): { label: string; color: string; bg: string } {
  if (status === "anchored") return { label: "Anchored", color: "var(--pass)", bg: "var(--pass-bg)" };
  if (status === "error") return { label: "Anchor failed", color: "var(--critical)", bg: "var(--critical-bg)" };
  if (status === "disabled") return { label: "Solana disabled", color: "var(--text-lo)", bg: "rgba(159,176,191,0.10)" };
  return { label: "Not anchored", color: "var(--text-lo)", bg: "rgba(159,176,191,0.10)" };
}

type ChainStatus = "not_anchored" | "verified" | "mismatch" | "unreachable";
type VerifyResult = {
  mongo_intact: boolean | null;
  chain_intact: boolean | null;
  chain_status?: ChainStatus;
};

export default function AuditPage() {
  const [events, setEvents] = useState<AuditEvent[] | null>(null);
  const [live, setLive] = useState(false);
  const [backend, setBackend] = useState<string>("local_jsonl");
  const [seeding, setSeeding] = useState(false);
  const [anchoringAll, setAnchoringAll] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [verifyResults, setVerifyResults] = useState<Record<string, VerifyResult>>({});

  const refresh = useCallback(async () => {
    const { data, live: l } = await getAudit();
    setEvents(data);
    setLive(l);
  }, []);

  useEffect(() => {
    refresh();
    getHealth().then(({ data }) => setBackend(data.audit_backend ?? "local_jsonl"));
  }, [refresh]);

  async function handleReseed() {
    setSeeding(true);
    try {
      await seedAudit();
      await refresh();
    } finally {
      setSeeding(false);
    }
  }

  async function handleAnchorAll() {
    setAnchoringAll(true);
    try {
      await anchorAllPending();
      await refresh();
    } finally {
      setAnchoringAll(false);
    }
  }

  async function handleAnchor(id: string) {
    setBusyId(id);
    try {
      await anchorAuditEvent(id);
      await refresh();
    } finally {
      setBusyId(null);
    }
  }

  async function handleVerify(id: string) {
    setBusyId(id);
    try {
      const { data } = await verifyAuditEvent(id);
      setVerifyResults((prev) => ({ ...prev, [id]: data }));
    } finally {
      setBusyId(null);
    }
  }

  const backendMeta =
    backend === "mongodb"
      ? { label: "MongoDB Atlas", icon: Database, color: "var(--accent)", bg: "rgba(190,242,100,0.12)" }
      : { label: "Local ledger — Atlas not configured", icon: HardDrive, color: "var(--warning)", bg: "var(--warning-bg)" };

  return (
    <div>
      <PageHeader
        eyebrow="Chain of custody (plan §D/E)"
        title="Audit Ledger"
        subtitle="Every finalized compliance decision, recorded once and append-only — the project memory flat-file recomputation never had. Idempotent via a content hash; anchoring that hash on Solana proves the record hasn't been altered."
      />

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <Chip color={backendMeta.color} bg={backendMeta.bg}>
          <backendMeta.icon size={12} strokeWidth={2} />
          {backendMeta.label}
        </Chip>
        <div className="flex items-center gap-2">
          {!live && (
            <span className="text-xs text-text-lo">backend unreachable — showing bundled sample data</span>
          )}
          <Button onClick={handleAnchorAll} disabled={anchoringAll}>
            <Link2 size={13} strokeWidth={2} className={anchoringAll ? "animate-pulse" : ""} />
            {anchoringAll ? "Anchoring…" : "Anchor all pending"}
          </Button>
          <Button onClick={handleReseed} disabled={seeding}>
            <RefreshCw size={13} strokeWidth={2} className={seeding ? "animate-spin" : ""} />
            {seeding ? "Re-seeding…" : "Re-seed demo data"}
          </Button>
        </div>
      </div>

      {events === null ? (
        <div className="space-y-3">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      ) : events.length === 0 ? (
        <Card className="px-5 py-8 text-center text-sm text-text-mid">
          No audit events yet. Run a compliance check on an uploaded document, or click
          &ldquo;Re-seed demo data&rdquo; to backfill the preloaded project&rsquo;s current NCRs.
        </Card>
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line text-left text-[0.68rem] uppercase tracking-wide text-text-lo">
                  <th className="px-4 py-2.5 font-medium">#</th>
                  <th className="px-4 py-2.5 font-medium">Recorded</th>
                  <th className="px-4 py-2.5 font-medium">Pillar</th>
                  <th className="px-4 py-2.5 font-medium">Item</th>
                  <th className="px-4 py-2.5 font-medium">Content hash</th>
                  <th className="px-4 py-2.5 font-medium">Solana</th>
                  <th className="px-4 py-2.5 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {events.map((e) => {
                  const sev = severityOf(e.payload);
                  const sm = sev ? severityMeta[sev as keyof typeof severityMeta] : null;
                  const solana = solanaMeta(e.solana?.status ?? "pending");
                  const vr = verifyResults[e.id];
                  const busy = busyId === e.id;
                  return (
                    <tr key={e.id} className="border-b border-line/60 last:border-0">
                      <td className="px-4 py-3 font-mono text-text-lo">{e.seq}</td>
                      <td className="px-4 py-3 font-mono text-[0.72rem] text-text-mid">
                        {fmtTime(e.created_at)}
                      </td>
                      <td className="px-4 py-3">
                        <Chip color="var(--data)" bg="rgba(56,189,248,0.12)">
                          {e.pillar}
                        </Chip>
                      </td>
                      <td className="px-4 py-3">
                        <div className="text-text-hi">
                          {typeof e.payload["item"] === "string" ? (e.payload["item"] as string) : e.ref_id}
                        </div>
                        {sm && (
                          <span className="mt-1 inline-flex items-center gap-1 text-[0.68rem]" style={{ color: sm.color }}>
                            <span aria-hidden>{sm.icon}</span> {sm.label}
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 font-mono text-[0.7rem] text-text-lo" title={e.content_hash}>
                        {e.content_hash.slice(0, 12)}…
                      </td>
                      <td className="px-4 py-3">
                        {e.solana?.tx_sig ? (
                          <a
                            href={`https://explorer.solana.com/tx/${e.solana.tx_sig}?cluster=${e.solana.cluster ?? "devnet"}`}
                            target="_blank"
                            rel="noreferrer"
                            title="View this transaction on Solana Explorer (devnet)"
                            className="inline-flex items-center gap-1.5 underline decoration-dotted underline-offset-4 decoration-1 opacity-90 transition hover:opacity-100"
                          >
                            <Chip color={solana.color} bg={solana.bg}>
                              <ShieldCheck size={11} strokeWidth={2} />
                              {solana.label}
                            </Chip>
                            <ExternalLink size={11} strokeWidth={2} className="text-text-lo" />
                          </a>
                        ) : (
                          <Chip color={solana.color} bg={solana.bg}>
                            {solana.label}
                          </Chip>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-col items-start gap-1.5">
                          <div className="flex gap-1.5">
                            {e.solana?.status !== "anchored" && (
                              <Button onClick={() => handleAnchor(e.id)} disabled={busy}>
                                {busy ? "…" : "Anchor"}
                              </Button>
                            )}
                            <Button onClick={() => handleVerify(e.id)} disabled={busy}>
                              {busy ? "…" : "Verify"}
                            </Button>
                          </div>
                          {vr && (
                            <div className="flex items-center gap-1 text-[0.7rem]">
                              {vr.mongo_intact ? (
                                <span className="inline-flex items-center gap-1 text-pass">
                                  <ShieldCheck size={12} strokeWidth={2} /> record intact
                                </span>
                              ) : (
                                <span className="inline-flex items-center gap-1 text-critical">
                                  <ShieldX size={12} strokeWidth={2} /> record altered
                                </span>
                              )}
                              {/* Render chain_status, never chain_intact alone: a
                                  null used to mean BOTH "not anchored" and "RPC
                                  unreachable", so a devnet timeout painted a red
                                  "mismatch" on a perfectly valid anchor. Only a
                                  genuine, read-from-chain disagreement is red. */}
                              {vr.chain_status === "verified" && (
                                <span className="text-pass">· chain match</span>
                              )}
                              {vr.chain_status === "mismatch" && (
                                <span className="text-critical">· chain mismatch</span>
                              )}
                              {vr.chain_status === "unreachable" && (
                                <span
                                  className="text-warning"
                                  title="Could not reach the Solana RPC to check. This says nothing about the record — retry."
                                >
                                  · chain unverifiable (RPC unreachable)
                                </span>
                              )}
                            </div>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
