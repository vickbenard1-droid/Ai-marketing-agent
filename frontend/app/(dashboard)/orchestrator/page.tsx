"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ChevronRight, Sparkles } from "lucide-react";
import { ApiError, createOrchestrationRun, listOrchestrationRuns, type OrchestrationRunPublic, type OrchestrationRunStatus } from "@/lib/api";
import { useSession } from "@/lib/session";
import { Header } from "@/components/layout/header";
import { Button } from "@/components/ui/button";

const STATUS_STYLES: Record<OrchestrationRunStatus, string> = {
  planning: "bg-ink-100 text-ink-600",
  running: "bg-signal-soft text-signal",
  paused_for_approval: "bg-signal-soft text-signal font-semibold",
  completed: "bg-positive-soft text-positive",
  failed: "bg-signal-soft text-signal",
  cancelled: "bg-ink-100 text-ink-400",
};

const STATUS_LABELS: Record<OrchestrationRunStatus, string> = {
  planning: "Planning", running: "Running", paused_for_approval: "Needs approval",
  completed: "Completed", failed: "Failed", cancelled: "Cancelled",
};

export default function OrchestratorPage() {
  const { accessToken, activeOrganizationId } = useSession();
  const [runs, setRuns] = useState<OrchestrationRunPublic[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [goal, setGoal] = useState("");
  const [isCreating, setIsCreating] = useState(false);

  async function load() {
    if (!accessToken || !activeOrganizationId) return;
    setRuns(await listOrchestrationRuns(accessToken, activeOrganizationId));
  }

  useEffect(() => {
    if (!accessToken || !activeOrganizationId) return;
    setIsLoading(true);
    load().catch((err) => setError(err instanceof ApiError ? String(err.detail ?? "Couldn't load") : "Couldn't load")).finally(() => setIsLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken, activeOrganizationId]);

  async function handleCreate() {
    if (!accessToken || !activeOrganizationId || !goal.trim()) return;
    setIsCreating(true);
    setError(null);
    try {
      await createOrchestrationRun(accessToken, activeOrganizationId, goal);
      setGoal("");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail ?? "Couldn't create run") : "Couldn't create run");
    } finally {
      setIsCreating(false);
    }
  }

  return (
    <>
      <Header title="Orchestrator" description="Give the marketing system a goal - it plans, and asks before it acts" />
      <main className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-2xl space-y-4">
          <div className="rounded-lg border border-ink-100 bg-white p-4 shadow-panel">
            <p className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-ink-900"><Sparkles className="h-4 w-4" />What do you want to accomplish?</p>
            <div className="flex gap-2">
              <input
                value={goal}
                onChange={(e) => setGoal(e.target.value)}
                placeholder="e.g. Help me get 100 sales for my product"
                className="flex-1 rounded-md border border-ink-200 px-3 py-2 text-sm"
                onKeyDown={(e) => e.key === "Enter" && handleCreate()}
              />
              <Button onClick={handleCreate} disabled={isCreating || !goal.trim()}>{isCreating ? "Planning…" : "Start"}</Button>
            </div>
            <p className="mt-2 text-xs text-ink-400">The system will plan the steps, then pause for your approval before spending money, touching your ad account, or publishing anything.</p>
          </div>

          {error && <p className="rounded-md bg-signal-soft px-4 py-3 text-sm text-signal">{error}</p>}

          {isLoading ? (
            <p className="text-sm text-ink-500">Loading…</p>
          ) : runs.length === 0 ? (
            <p className="text-sm text-ink-500">No runs yet - start one above.</p>
          ) : (
            <div className="flex flex-col gap-2">
              {runs.map((run) => (
                <Link key={run.id} href={`/orchestrator/${run.id}`} className="flex items-center justify-between rounded-lg border border-ink-100 bg-white p-4 shadow-panel hover:border-ink-300">
                  <div>
                    <p className="text-sm font-medium text-ink-900">{run.goal_text}</p>
                    <p className="mt-1 text-xs text-ink-400">Step {run.current_step} of {run.plan_json.length} · {new Date(run.created_at).toLocaleString()}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`rounded-full px-2.5 py-1 text-xs ${STATUS_STYLES[run.status]}`}>{STATUS_LABELS[run.status]}</span>
                    <ChevronRight className="h-4 w-4 text-ink-300" />
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </main>
    </>
  );
}
