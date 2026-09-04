"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Plus, User } from "lucide-react";
import {
  ApiError, createManualLead, LEAD_SOURCE_LABELS, LEAD_STAGE_LABELS, LEAD_STAGE_ORDER, listLeads, transitionLeadStage,
  type LeadPublic, type LeadStage,
} from "@/lib/api";
import { useSession } from "@/lib/session";
import { Header } from "@/components/layout/header";
import { Button } from "@/components/ui/button";

const STAGE_COLUMN_STYLES: Record<LeadStage, string> = {
  new_lead: "border-t-ink-300", contacted: "border-t-ink-400", qualified: "border-t-signal",
  interested: "border-t-signal", negotiation: "border-t-signal", won: "border-t-positive", lost: "border-t-ink-200",
};

function scoreColor(score: number | null): string {
  if (score === null) return "text-ink-400";
  if (score >= 60) return "text-positive";
  if (score >= 30) return "text-signal";
  return "text-ink-500";
}

export default function LeadsPipelinePage() {
  const { accessToken, activeOrganizationId } = useSession();
  const [leads, setLeads] = useState<LeadPublic[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [draggedLeadId, setDraggedLeadId] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [productInterest, setProductInterest] = useState("");
  const [budget, setBudget] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  async function load() {
    if (!accessToken || !activeOrganizationId) return;
    setLeads(await listLeads(accessToken, activeOrganizationId));
  }

  useEffect(() => {
    if (!accessToken || !activeOrganizationId) return;
    setIsLoading(true);
    load().catch((err) => setError(err instanceof ApiError ? String(err.detail ?? "Couldn't load") : "Couldn't load")).finally(() => setIsLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken, activeOrganizationId]);

  async function handleCreate() {
    if (!accessToken || !activeOrganizationId) return;
    setIsSaving(true);
    setError(null);
    try {
      await createManualLead(accessToken, activeOrganizationId, {
        full_name: fullName.trim() || undefined, email: email.trim() || undefined, phone: phone.trim() || undefined,
        product_interest: productInterest.trim() || undefined, disclosed_budget_cents: budget ? Math.round(parseFloat(budget) * 100) : undefined,
      });
      setFullName(""); setEmail(""); setPhone(""); setProductInterest(""); setBudget(""); setShowForm(false);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail ?? "Couldn't create lead") : "Couldn't create lead");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleDrop(stage: LeadStage) {
    if (!accessToken || !activeOrganizationId || !draggedLeadId) return;
    const lead = leads.find((l) => l.id === draggedLeadId);
    setDraggedLeadId(null);
    if (!lead || lead.stage === stage) return;
    try {
      await transitionLeadStage(accessToken, activeOrganizationId, lead.id, { to_stage: stage });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail ?? "Couldn't move lead") : "Couldn't move lead");
    }
  }

  return (
    <>
      <Header title="Leads" description="Pipeline from first click to closed sale" />
      <main className="flex-1 overflow-y-auto p-6">
        <div className="mb-4 flex items-center justify-between">
          <Link href="/leads/analytics" className="text-sm font-medium text-ink-600 underline">Sales analytics</Link>
          <Button onClick={() => setShowForm((v) => !v)} className="gap-1.5"><Plus className="h-4 w-4" />Add lead</Button>
        </div>
        {error && <p className="mb-4 rounded-md bg-signal-soft px-4 py-3 text-sm text-signal">{error}</p>}
        {showForm && (
          <div className="mb-4 rounded-lg border border-ink-100 bg-white p-4 shadow-panel">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              <input value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="Full name" className="rounded-md border border-ink-200 px-3 py-2 text-sm" />
              <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email" className="rounded-md border border-ink-200 px-3 py-2 text-sm" />
              <input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="Phone" className="rounded-md border border-ink-200 px-3 py-2 text-sm" />
              <input value={productInterest} onChange={(e) => setProductInterest(e.target.value)} placeholder="Product interest" className="rounded-md border border-ink-200 px-3 py-2 text-sm sm:col-span-2" />
              <input type="number" step="0.01" value={budget} onChange={(e) => setBudget(e.target.value)} placeholder="Disclosed budget ($)" className="rounded-md border border-ink-200 px-3 py-2 text-sm" />
            </div>
            <div className="mt-3 flex gap-2">
              <Button onClick={handleCreate} disabled={isSaving || (!fullName && !email && !phone)}>{isSaving ? "Saving…" : "Create lead"}</Button>
              <Button variant="secondary" onClick={() => setShowForm(false)}>Cancel</Button>
            </div>
          </div>
        )}
        {isLoading ? (
          <p className="text-sm text-ink-500">Loading…</p>
        ) : (
          <div className="flex gap-3 overflow-x-auto pb-4">
            {LEAD_STAGE_ORDER.map((stage) => {
              const stageLeads = leads.filter((l) => l.stage === stage);
              return (
                <div key={stage} onDragOver={(e) => e.preventDefault()} onDrop={() => handleDrop(stage)} className={`w-64 shrink-0 rounded-lg border-t-4 bg-ink-50/50 p-2 ${STAGE_COLUMN_STYLES[stage]}`}>
                  <div className="mb-2 flex items-center justify-between px-1">
                    <p className="text-xs font-semibold uppercase tracking-wide text-ink-600">{LEAD_STAGE_LABELS[stage]}</p>
                    <span className="text-xs text-ink-400">{stageLeads.length}</span>
                  </div>
                  <div className="flex flex-col gap-2">
                    {stageLeads.map((lead) => (
                      <Link key={lead.id} href={`/leads/${lead.id}`} draggable onDragStart={() => setDraggedLeadId(lead.id)} className="block cursor-grab rounded-md border border-ink-100 bg-white p-3 shadow-sm hover:border-ink-300">
                        <div className="mb-1 flex items-center gap-1.5">
                          <User className="h-3.5 w-3.5 text-ink-300" />
                          <p className="truncate text-sm font-medium text-ink-900">{lead.full_name || lead.email || lead.phone || "Unnamed lead"}</p>
                        </div>
                        {lead.product_interest && <p className="mb-1 truncate text-xs text-ink-500">{lead.product_interest}</p>}
                        <div className="flex items-center justify-between">
                          <span className="text-[10px] text-ink-400">{LEAD_SOURCE_LABELS[lead.source]}</span>
                          {lead.score !== null && <span className={`text-xs font-semibold ${scoreColor(lead.score)}`}>{lead.score}</span>}
                        </div>
                      </Link>
                    ))}
                    {stageLeads.length === 0 && <p className="px-1 py-2 text-xs text-ink-300">No leads</p>}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </main>
    </>
  );
}
