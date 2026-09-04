"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Mail, Send } from "lucide-react";
import {
  ApiError, evaluateLeadQualification, generateFollowUp, getLead, getLeadTransitions, listFollowUps, sendFollowUp,
  LEAD_STAGE_LABELS, LEAD_STAGE_ORDER, transitionLeadStage, updateLeadNotes,
  type FollowUpChannel, type LeadFollowUpPublic, type LeadPublic, type LeadStage, type LeadStageTransitionPublic,
} from "@/lib/api";
import { useSession } from "@/lib/session";
import { Header } from "@/components/layout/header";
import { Button } from "@/components/ui/button";

export default function LeadDetailPage() {
  const params = useParams<{ leadId: string }>();
  const { accessToken, activeOrganizationId } = useSession();
  const [lead, setLead] = useState<LeadPublic | null>(null);
  const [transitions, setTransitions] = useState<LeadStageTransitionPublic[]>([]);
  const [followUps, setFollowUps] = useState<LeadFollowUpPublic[]>([]);
  const [qualification, setQualification] = useState<{ qualifies: boolean; reasons: string[] } | null>(null);
  const [notes, setNotes] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);

  async function load() {
    if (!accessToken || !activeOrganizationId) return;
    const [l, t, f, q] = await Promise.all([
      getLead(accessToken, activeOrganizationId, params.leadId),
      getLeadTransitions(accessToken, activeOrganizationId, params.leadId),
      listFollowUps(accessToken, activeOrganizationId, params.leadId),
      evaluateLeadQualification(accessToken, activeOrganizationId, params.leadId),
    ]);
    setLead(l); setTransitions(t); setFollowUps(f); setQualification(q); setNotes(l.notes ?? "");
  }

  useEffect(() => {
    if (!accessToken || !activeOrganizationId) return;
    setIsLoading(true);
    load().catch((err) => setError(err instanceof ApiError ? String(err.detail ?? "Couldn't load") : "Couldn't load")).finally(() => setIsLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken, activeOrganizationId, params.leadId]);

  async function handleStageChange(stage: LeadStage) {
    if (!accessToken || !activeOrganizationId) return;
    try {
      await transitionLeadStage(accessToken, activeOrganizationId, params.leadId, { to_stage: stage });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail ?? "Couldn't update stage") : "Couldn't update stage");
    }
  }

  async function handleSaveNotes() {
    if (!accessToken || !activeOrganizationId) return;
    try {
      await updateLeadNotes(accessToken, activeOrganizationId, params.leadId, notes);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail ?? "Couldn't save notes") : "Couldn't save notes");
    }
  }

  async function handleGenerateFollowUp(channel: FollowUpChannel) {
    if (!accessToken || !activeOrganizationId) return;
    setIsGenerating(true);
    setError(null);
    try {
      await generateFollowUp(accessToken, activeOrganizationId, params.leadId, { channel });
      const f = await listFollowUps(accessToken, activeOrganizationId, params.leadId);
      setFollowUps(f);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail ?? "Couldn't generate follow-up") : "Couldn't generate follow-up");
    } finally {
      setIsGenerating(false);
    }
  }

  async function handleSendFollowUp(followUpId: string) {
    if (!accessToken || !activeOrganizationId) return;
    try {
      await sendFollowUp(accessToken, activeOrganizationId, followUpId);
      const f = await listFollowUps(accessToken, activeOrganizationId, params.leadId);
      setFollowUps(f);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail ?? "Couldn't send follow-up") : "Couldn't send follow-up");
    }
  }

  return (
    <>
      <Header title={lead?.full_name || lead?.email || "Lead"} description={lead ? LEAD_STAGE_LABELS[lead.stage] : undefined} />
      <main className="flex-1 overflow-y-auto p-6">
        {error && <p className="mb-4 rounded-md bg-signal-soft px-4 py-3 text-sm text-signal">{error}</p>}
        {isLoading || !lead ? (
          <p className="text-sm text-ink-500">Loading…</p>
        ) : (
          <div className="mx-auto max-w-2xl space-y-4">
            <div className="rounded-lg border border-ink-100 bg-white p-4 shadow-panel">
              <div className="mb-3 flex items-center justify-between">
                <p className="text-sm font-semibold text-ink-900">Details</p>
                {lead.score !== null && <span className="rounded-full bg-ink-100 px-2.5 py-1 text-sm font-semibold text-ink-800">Score: {lead.score}</span>}
              </div>
              <p className="text-sm text-ink-600">{lead.email || "No email"} · {lead.phone || "No phone"}</p>
              {lead.product_interest && <p className="mt-1 text-sm text-ink-600">Interested in: {lead.product_interest}</p>}
              {lead.disclosed_budget_cents !== null && <p className="mt-1 text-sm text-ink-600">Budget: ${(lead.disclosed_budget_cents / 100).toFixed(2)}</p>}

              {lead.score_factors_json && (
                <div className="mt-3 border-t border-ink-100 pt-3">
                  <p className="mb-2 text-xs font-medium text-ink-700">Score factors</p>
                  <div className="flex flex-col gap-1">
                    {lead.score_factors_json.factors.map((f, i) => (
                      <div key={i} className="flex items-center justify-between text-xs text-ink-500">
                        <span>{f.reason}</span>
                        <span className={f.points >= 0 ? "text-positive" : "text-signal"}>{f.points >= 0 ? "+" : ""}{f.points}</span>
                      </div>
                    ))}
                  </div>
                  <p className="mt-2 text-[11px] italic text-ink-300">{lead.score_factors_json.excluded_factors_note}</p>
                </div>
              )}

              {qualification && (
                <div className="mt-3 border-t border-ink-100 pt-3">
                  <p className={`text-xs font-medium ${qualification.qualifies ? "text-positive" : "text-ink-500"}`}>
                    {qualification.qualifies ? "Meets qualification criteria" : "Does not yet meet qualification criteria"}
                  </p>
                </div>
              )}
            </div>

            <div className="rounded-lg border border-ink-100 bg-white p-4 shadow-panel">
              <p className="mb-2 text-sm font-semibold text-ink-900">Stage</p>
              <div className="flex flex-wrap gap-2">
                {LEAD_STAGE_ORDER.map((stage) => (
                  <button key={stage} onClick={() => handleStageChange(stage)} className={`rounded-full px-3 py-1.5 text-sm font-medium ${lead.stage === stage ? "bg-ink-900 text-white" : "border border-ink-200 bg-white text-ink-600"}`}>
                    {LEAD_STAGE_LABELS[stage]}
                  </button>
                ))}
              </div>
            </div>

            <div className="rounded-lg border border-ink-100 bg-white p-4 shadow-panel">
              <p className="mb-2 text-sm font-semibold text-ink-900">Notes</p>
              <textarea value={notes} onChange={(e) => setNotes(e.target.value)} onBlur={handleSaveNotes} rows={3} className="w-full rounded-md border border-ink-200 px-3 py-2 text-sm" placeholder="Add notes…" />
            </div>

            <div className="rounded-lg border border-ink-100 bg-white p-4 shadow-panel">
              <p className="mb-2 text-sm font-semibold text-ink-900">Follow-ups</p>
              <div className="mb-3 flex gap-2">
                <Button onClick={() => handleGenerateFollowUp("email")} disabled={isGenerating} className="gap-1.5 text-xs">
                  <Mail className="h-3.5 w-3.5" />
                  {isGenerating ? "Generating…" : "Draft email"}
                </Button>
              </div>
              <div className="flex flex-col gap-2">
                {followUps.map((f) => (
                  <div key={f.id} className="rounded-md border border-ink-100 p-3">
                    <div className="mb-1 flex items-center justify-between">
                      <span className="text-xs font-medium uppercase text-ink-500">{f.channel}</span>
                      <span className={`text-xs ${f.status === "sent" ? "text-positive" : f.status === "failed" || f.status === "not_sendable" ? "text-signal" : "text-ink-400"}`}>{f.status}</span>
                    </div>
                    {f.subject && <p className="text-sm font-medium text-ink-800">{f.subject}</p>}
                    <p className="mt-1 whitespace-pre-wrap text-sm text-ink-600">{f.body}</p>
                    {f.status === "drafted" && (
                      <Button variant="secondary" onClick={() => handleSendFollowUp(f.id)} className="mt-2 gap-1.5 text-xs">
                        <Send className="h-3.5 w-3.5" />
                        Send
                      </Button>
                    )}
                    {f.send_error && <p className="mt-1 text-xs text-signal">{f.send_error}</p>}
                  </div>
                ))}
                {followUps.length === 0 && <p className="text-xs text-ink-300">No follow-ups yet.</p>}
              </div>
            </div>

            <div className="rounded-lg border border-ink-100 bg-white p-4 shadow-panel">
              <p className="mb-2 text-sm font-semibold text-ink-900">History</p>
              <div className="flex flex-col gap-1.5">
                {transitions.map((t) => (
                  <p key={t.id} className="text-xs text-ink-500">
                    {t.from_stage ? `${LEAD_STAGE_LABELS[t.from_stage]} → ` : "Created at "}
                    {LEAD_STAGE_LABELS[t.to_stage]} <span className="text-ink-300">· {new Date(t.changed_at).toLocaleString()}</span>
                    {t.note && <span className="italic"> — {t.note}</span>}
                  </p>
                ))}
              </div>
            </div>
          </div>
        )}
      </main>
    </>
  );
}
