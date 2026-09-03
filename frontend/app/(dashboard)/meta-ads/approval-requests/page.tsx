"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, PlayCircle, XCircle } from "lucide-react";
import {
  ApiError,
  executeApprovalRequest,
  listApprovalRequests,
  reviewApprovalRequest,
  type ApprovalRequestPublic,
  type ApprovalStatus,
} from "@/lib/api";
import { useSession } from "@/lib/session";
import { Header } from "@/components/layout/header";
import { Button } from "@/components/ui/button";

const TABS: { value: ApprovalStatus | "all"; label: string }[] = [
  { value: "pending", label: "Pending" },
  { value: "approved", label: "Approved" },
  { value: "executed", label: "Executed" },
  { value: "rejected", label: "Rejected" },
  { value: "all", label: "All" },
];

function describeAction(request: ApprovalRequestPublic): string {
  if (request.action_type === "campaign_budget_change") {
    return `Change daily budget to $${((request.action_payload.new_daily_budget_cents as number) / 100).toFixed(2)}`;
  }
  if (request.action_type === "campaign_pause" || request.action_type === "campaign_launch") {
    return `Change status to ${request.action_payload.new_status}`;
  }
  return request.action_type;
}

export default function ApprovalRequestsPage() {
  const { accessToken, activeOrganizationId } = useSession();
  const [tab, setTab] = useState<ApprovalStatus | "all">("pending");
  const [requests, setRequests] = useState<ApprovalRequestPublic[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  async function load() {
    if (!accessToken || !activeOrganizationId) return;
    const list = await listApprovalRequests(accessToken, activeOrganizationId, tab === "all" ? undefined : tab);
    setRequests(list);
  }

  useEffect(() => {
    if (!accessToken || !activeOrganizationId) return;
    setIsLoading(true);
    load()
      .catch((err) => setError(err instanceof ApiError ? String(err.detail ?? "Couldn't load") : "Couldn't load"))
      .finally(() => setIsLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken, activeOrganizationId, tab]);

  async function handleReview(id: string, approve: boolean) {
    if (!accessToken || !activeOrganizationId) return;
    setBusyId(id);
    setError(null);
    try {
      await reviewApprovalRequest(accessToken, activeOrganizationId, id, { approve });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail ?? "Couldn't review") : "Couldn't review");
    } finally {
      setBusyId(null);
    }
  }

  async function handleExecute(id: string) {
    if (!accessToken || !activeOrganizationId) return;
    setBusyId(id);
    setError(null);
    try {
      await executeApprovalRequest(accessToken, activeOrganizationId, id);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail ?? "Couldn't execute") : "Couldn't execute");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <>
      <Header title="Approval requests" description="Review and execute proposed Meta Ads changes" />
      <main className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-2xl space-y-4">
          <div className="flex gap-2">
            {TABS.map((t) => (
              <button
                key={t.value}
                onClick={() => setTab(t.value)}
                className={`rounded-full px-3.5 py-1.5 text-sm font-medium ${
                  tab === t.value ? "bg-ink-900 text-white" : "border border-ink-200 bg-white text-ink-600"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>

          {error && <p className="rounded-md bg-signal-soft px-4 py-3 text-sm text-signal">{error}</p>}

          {isLoading ? (
            <p className="text-sm text-ink-500">Loading…</p>
          ) : requests.length === 0 ? (
            <p className="text-sm text-ink-500">No {tab === "all" ? "" : tab} requests.</p>
          ) : (
            <div className="flex flex-col gap-3">
              {requests.map((r) => (
                <div key={r.id} className="rounded-lg border border-ink-100 bg-white p-4 shadow-panel">
                  <div className="mb-2 flex items-center justify-between">
                    <p className="text-sm font-medium text-ink-900">{describeAction(r)}</p>
                    <span className="text-xs text-ink-400">{new Date(r.created_at).toLocaleDateString()}</span>
                  </div>
                  <p className="mb-3 text-xs text-ink-400">Status: {r.status}</p>

                  {r.status === "pending" && (
                    <div className="flex gap-2">
                      <Button onClick={() => handleReview(r.id, true)} disabled={busyId === r.id} className="gap-1.5">
                        <CheckCircle2 className="h-4 w-4" />
                        Approve
                      </Button>
                      <Button variant="secondary" onClick={() => handleReview(r.id, false)} disabled={busyId === r.id} className="gap-1.5">
                        <XCircle className="h-4 w-4" />
                        Reject
                      </Button>
                    </div>
                  )}

                  {r.status === "approved" && (
                    <Button onClick={() => handleExecute(r.id)} disabled={busyId === r.id} className="gap-1.5">
                      <PlayCircle className="h-4 w-4" />
                      Execute
                    </Button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </>
  );
}
