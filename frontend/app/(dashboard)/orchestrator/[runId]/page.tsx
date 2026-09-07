"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { AlertTriangle, Bot, CheckCircle2, Database, Lightbulb, ListChecks } from "lucide-react";
import {
  ApiError, approveOrchestrationStep, getOrchestrationRun, getRunActivity,
  type AgentActivityLogPublic, type OrchestrationRunPublic,
} from "@/lib/api";
import { useSession } from "@/lib/session";
import { Header } from "@/components/layout/header";
import { Button } from "@/components/ui/button";

const STATUS_LABELS: Record<string, string> = {
  planning: "Planning", running: "Running", paused_for_approval: "Needs your approval",
  completed: "Completed", failed: "Failed", cancelled: "Cancelled",
};

function agentLabel(name: string): string {
  return name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function OrchestrationRunDetailPage() {
  const params = useParams<{ runId: string }>();
  const { accessToken, activeOrganizationId } = useSession();
  const [run, setRun] = useState<OrchestrationRunPublic | null>(null);
  const [activity, setActivity] = useState<AgentActivityLogPublic[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isActing, setIsActing] = useState(false);

  async function load() {
    if (!accessToken || !activeOrganizationId) return;
    const [r, a] = await Promise.all([
      getOrchestrationRun(accessToken, activeOrganizationId, params.runId),
      getRunActivity(accessToken, activeOrganizationId, params.runId),
    ]);
    setRun(r); setActivity(a);
  }

  useEffect(() => {
    if (!accessToken || !activeOrganizationId) return;
    setIsLoading(true);
    load().catch((err) => setError(err instanceof ApiError ? String(err.detail ?? "Couldn't load") : "Couldn't load")).finally(() => setIsLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken, activeOrganizationId, params.runId]);

  async function handleApproval(approve: boolean) {
    if (!accessToken || !activeOrganizationId) return;
    setIsActing(true);
    setError(null);
    try {
      await approveOrchestrationStep(accessToken, activeOrganizationId, params.runId, { approve });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail ?? "Couldn't record your decision") : "Couldn't record your decision");
    } finally {
      setIsActing(false);
    }
  }

  return (
    <>
      <Header title={run?.goal_text || "Orchestration run"} description={run ? STATUS_LABELS[run.status] : undefined} />
      <main className="flex-1 overflow-y-auto p-6">
        {error && <p className="mb-4 rounded-md bg-signal-soft px-4 py-3 text-sm text-signal">{error}</p>}
        {isLoading || !run ? (
          <p className="text-sm text-ink-500">Loading…</p>
        ) : (
          <div className="mx-auto max-w-2xl space-y-4">
            <div className="rounded-lg border border-ink-100 bg-white p-4 shadow-panel">
              <p className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-ink-900"><ListChecks className="h-4 w-4" />Plan</p>
              {run.final_summary && <p className="mb-3 text-sm italic text-ink-600">{run.final_summary}</p>}
              <div className="flex flex-col gap-1.5">
                {run.plan_json.map((step, i) => (
                  <div key={i} className={`flex items-center gap-2 rounded-md p-2 text-sm ${i === run.current_step ? "bg-ink-50 font-medium" : i < run.current_step ? "text-ink-400 line-through" : "text-ink-500"}`}>
                    <span className="w-5 text-xs text-ink-300">{i + 1}</span>
                    <Bot className="h-3.5 w-3.5 shrink-0" />
                    <span className="flex-1">{step.action_description}</span>
                    <span className="text-[10px] uppercase text-ink-300">{agentLabel(step.agent_name)}</span>
                    {step.requires_approval && <span className="rounded-full bg-signal-soft px-1.5 py-0.5 text-[10px] text-signal">approval</span>}
                  </div>
                ))}
              </div>
            </div>

            {run.status === "paused_for_approval" && (
              <div className="rounded-lg border border-signal bg-signal-soft/40 p-4 shadow-panel">
                <p className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-signal"><AlertTriangle className="h-4 w-4" />This step needs your approval before it happens</p>
                <p className="mb-3 text-sm text-ink-700">{run.plan_json[run.current_step]?.action_description}</p>
                <div className="flex gap-2">
                  <Button onClick={() => handleApproval(true)} disabled={isActing} className="gap-1.5"><CheckCircle2 className="h-4 w-4" />Approve</Button>
                  <Button variant="secondary" onClick={() => handleApproval(false)} disabled={isActing}>Reject</Button>
                </div>
              </div>
            )}

            <div className="rounded-lg border border-ink-100 bg-white p-4 shadow-panel">
              <p className="mb-3 text-sm font-semibold text-ink-900">Activity timeline</p>
              <div className="flex flex-col gap-3">
                {activity.map((a) => (
                  <div key={a.id} className="border-l-2 border-ink-100 pl-3">
                    <div className="mb-1 flex items-center gap-2">
                      <span className="text-xs font-semibold uppercase text-ink-500">{agentLabel(a.agent_name)}</span>
                      <span className={`text-xs ${a.status === "completed" ? "text-positive" : a.status === "failed" || a.status === "rejected" ? "text-signal" : "text-ink-400"}`}>{a.status.replace("_", " ")}</span>
                    </div>
                    <p className="text-sm text-ink-800">{a.action_description}</p>
                    {a.reasoning && (
                      <p className="mt-1 flex items-start gap-1 text-xs text-ink-500"><Lightbulb className="mt-0.5 h-3 w-3 shrink-0" />{a.reasoning}</p>
                    )}
                    {Object.keys(a.data_used_json).length > 0 && (
                      <p className="mt-1 flex items-start gap-1 text-xs text-ink-400"><Database className="mt-0.5 h-3 w-3 shrink-0" />Used real data: {Object.keys(a.data_used_json).join(", ")}</p>
                    )}
                    {a.recommendation && <p className="mt-1 text-xs italic text-ink-600">{a.recommendation}</p>}
                  </div>
                ))}
                {activity.length === 0 && <p className="text-xs text-ink-300">No activity yet.</p>}
              </div>
            </div>
          </div>
        )}
      </main>
    </>
  );
}
