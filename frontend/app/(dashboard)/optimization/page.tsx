"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle, CheckCircle2, ChevronRight, Sparkles } from "lucide-react";
import {
  ACTION_TYPE_LABELS,
  ApiError,
  listMetaCampaigns,
  listOptimizationDecisions,
  reviewOptimizationDecision,
  type DecisionStatus,
  type MetaCampaignPublic,
  type OptimizationDecisionPublic,
} from "@/lib/api";
import { useSession } from "@/lib/session";
import { Header } from "@/components/layout/header";
import { Button } from "@/components/ui/button";

const STATUS_TABS: { value: DecisionStatus | "all"; label: string }[] = [
  { value: "recommended", label: "Needs review" },
  { value: "approved", label: "Approved" },
  { value: "executed", label: "Executed" },
  { value: "rejected", label: "Rejected" },
  { value: "all", label: "All" },
];

const RISK_STYLES: Record<string, string> = {
  low: "bg-positive-soft text-positive",
  medium: "bg-signal-soft text-signal",
  high: "bg-signal-soft text-signal font-semibold",
};

export default function OptimizationPage() {
  const { accessToken, activeOrganizationId } = useSession();
  const [tab, setTab] = useState<DecisionStatus | "all">("recommended");
  const [decisions, setDecisions] = useState<OptimizationDecisionPublic[]>([]);
  const [campaigns, setCampaigns] = useState<MetaCampaignPublic[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [budgetInputs, setBudgetInputs] = useState<Record<string, string>>({});

  async function load() {
    if (!accessToken || !activeOrganizationId) return;
    const [decisionList, campaignList] = await Promise.all([
      listOptimizationDecisions(accessToken, activeOrganizationId, tab === "all" ? undefined : { status: tab }),
      listMetaCampaigns(accessToken, activeOrganizationId),
    ]);
    setDecisions(decisionList);
    setCampaigns(campaignList);
  }

  useEffect(() => {
    if (!accessToken || !activeOrganizationId) return;
    setIsLoading(true);
    load()
      .catch((err) => setError(err instanceof ApiError ? String(err.detail ?? "Couldn't load") : "Couldn't load"))
      .finally(() => setIsLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken, activeOrganizationId, tab]);

  function campaignName(id: string): string {
    return campaigns.find((c) => c.id === id)?.name ?? "Unknown campaign";
  }

  async function handleReview(decision: OptimizationDecisionPublic, approve: boolean) {
    if (!accessToken || !activeOrganizationId) return;
    setBusyId(decision.id);
    setError(null);
    const needsBudget = decision.action_type === "reduce_budget" || decision.action_type === "increase_budget";
    const budgetInput = budgetInputs[decision.id];
    try {
      await reviewOptimizationDecision(accessToken, activeOrganizationId, decision.id, {
        approve,
        new_daily_budget_cents: approve && needsBudget && budgetInput ? Math.round(parseFloat(budgetInput) * 100) : undefined,
      });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail ?? "Couldn't review decision") : "Couldn't review decision");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <>
      <Header title="Optimization" description="AI-recommended actions, decision history, and autonomy controls" />
      <main className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-3xl space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex gap-2">
              {STATUS_TABS.map((t) => (
                <button
                  key={t.value}
                  onClick={() => setTab(t.value)}
                  className={`rounded-full px-3.5 py-1.5 text-sm font-medium ${tab === t.value ? "bg-ink-900 text-white" : "border border-ink-200 bg-white text-ink-600"}`}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>

          {error && <p className="rounded-md bg-signal-soft px-4 py-3 text-sm text-signal">{error}</p>}

          {isLoading ? (
            <p className="text-sm text-ink-500">Loading…</p>
          ) : decisions.length === 0 ? (
            <p className="text-sm text-ink-500">No {tab === "all" ? "" : tab.replace("_", " ")} decisions.</p>
          ) : (
            <div className="flex flex-col gap-3">
              {decisions.map((d) => {
                const needsBudget = d.action_type === "reduce_budget" || d.action_type === "increase_budget";
                return (
                  <div key={d.id} className="rounded-lg border border-ink-100 bg-white p-4 shadow-panel">
                    <div className="mb-2 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Link href={`/optimization/${d.meta_campaign_id}`} className="text-sm font-semibold text-ink-900 hover:underline">
                          {campaignName(d.meta_campaign_id)}
                        </Link>
                        <span className="rounded-sm bg-ink-50 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-ink-500">
                          {ACTION_TYPE_LABELS[d.action_type]}
                        </span>
                        <span className={`rounded-full px-2 py-0.5 text-xs ${RISK_STYLES[d.risk]}`}>{d.risk} risk</span>
                      </div>
                      <span className="text-xs text-ink-400">{new Date(d.created_at).toLocaleDateString()}</span>
                    </div>
                    <div className="mb-2 flex items-start gap-1.5">
                      <Sparkles className="mt-0.5 h-3.5 w-3.5 shrink-0 text-ink-300" />
                      <p className="text-sm text-ink-800">{d.observation}</p>
                    </div>
                    <p className="mb-1 text-sm font-medium text-ink-900">{d.proposed_action}</p>
                    <p className="mb-2 text-xs italic text-ink-500">{d.expected_outcome}</p>
                    <p className="mb-3 text-xs text-ink-400">Confidence: {(d.confidence * 100).toFixed(0)}%</p>

                    {d.status === "recommended" && (
                      <div className="flex flex-col gap-2">
                        {needsBudget && (
                          <input
                            type="number"
                            step="0.01"
                            placeholder="Exact new daily budget ($)"
                            value={budgetInputs[d.id] ?? ""}
                            onChange={(e) => setBudgetInputs((prev) => ({ ...prev, [d.id]: e.target.value }))}
                            className="w-56 rounded-md border border-ink-200 px-3 py-1.5 text-sm"
                          />
                        )}
                        <div className="flex gap-2">
                          <Button onClick={() => handleReview(d, true)} disabled={busyId === d.id || (needsBudget && !budgetInputs[d.id])} className="gap-1.5">
                            <CheckCircle2 className="h-4 w-4" />
                            Approve
                          </Button>
                          <Button variant="secondary" onClick={() => handleReview(d, false)} disabled={busyId === d.id}>
                            Reject
                          </Button>
                        </div>
                      </div>
                    )}

                    {d.status === "execution_failed" && (
                      <p className="flex items-center gap-1.5 text-sm text-signal">
                        <AlertTriangle className="h-4 w-4" />
                        Execution failed
                      </p>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          <div className="pt-2">
            <p className="mb-2 text-sm font-semibold text-ink-900">Campaigns</p>
            <div className="flex flex-col gap-2">
              {campaigns.map((c) => (
                <Link key={c.id} href={`/optimization/${c.id}`} className="flex items-center justify-between rounded-lg border border-ink-100 bg-white p-3 shadow-panel hover:border-ink-300">
                  <p className="text-sm text-ink-800">{c.name}</p>
                  <ChevronRight className="h-4 w-4 text-ink-300" />
                </Link>
              ))}
            </div>
          </div>
        </div>
      </main>
    </>
  );
}
