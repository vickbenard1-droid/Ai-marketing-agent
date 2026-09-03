"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { AlertOctagon, ShieldCheck } from "lucide-react";
import {
  ApiError,
  getSpendLimit,
  setEmergencyStop,
  setSpendLimit,
  type AdAccountSpendLimitPublic,
} from "@/lib/api";
import { useSession } from "@/lib/session";
import { Header } from "@/components/layout/header";
import { Button } from "@/components/ui/button";

export default function AdAccountDetailPage() {
  const params = useParams<{ adAccountId: string }>();
  const { accessToken, activeOrganizationId } = useSession();
  const [limit, setLimit] = useState<AdAccountSpendLimitPublic | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [dailyLimitInput, setDailyLimitInput] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [stopReason, setStopReason] = useState("");

  async function load() {
    if (!accessToken || !activeOrganizationId) return;
    const result = await getSpendLimit(accessToken, activeOrganizationId, params.adAccountId);
    setLimit(result);
    if (result) setDailyLimitInput((result.daily_spend_limit_cents / 100).toFixed(2));
  }

  useEffect(() => {
    if (!accessToken || !activeOrganizationId) return;
    setIsLoading(true);
    load()
      .catch((err) => setError(err instanceof ApiError ? String(err.detail ?? "Couldn't load") : "Couldn't load"))
      .finally(() => setIsLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken, activeOrganizationId, params.adAccountId]);

  async function handleSaveLimit() {
    if (!accessToken || !activeOrganizationId) return;
    const cents = Math.round(parseFloat(dailyLimitInput) * 100);
    if (isNaN(cents) || cents < 0) {
      setError("Enter a valid daily spend limit");
      return;
    }
    setIsSaving(true);
    setError(null);
    try {
      const updated = await setSpendLimit(accessToken, activeOrganizationId, params.adAccountId, cents);
      setLimit(updated);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail ?? "Couldn't save") : "Couldn't save");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleToggleStop(stopped: boolean) {
    if (!accessToken || !activeOrganizationId) return;
    setIsSaving(true);
    setError(null);
    try {
      const updated = await setEmergencyStop(accessToken, activeOrganizationId, params.adAccountId, {
        stopped,
        reason: stopped ? stopReason || undefined : undefined,
      });
      setLimit(updated);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail ?? "Couldn't update") : "Couldn't update");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <>
      <Header title="Ad account" description="Spend limits and emergency stop" />
      <main className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-lg space-y-4">
          {error && <p className="rounded-md bg-signal-soft px-4 py-3 text-sm text-signal">{error}</p>}

          {isLoading ? (
            <p className="text-sm text-ink-500">Loading…</p>
          ) : (
            <>
              <div className="rounded-lg border border-ink-100 bg-white p-4 shadow-panel">
                <div className="mb-3 flex items-center gap-1.5">
                  <ShieldCheck className="h-4 w-4 text-ink-400" />
                  <p className="text-sm font-semibold text-ink-900">Daily spend limit</p>
                </div>
                {!limit && (
                  <p className="mb-3 text-xs text-signal">
                    No spend limit configured — nothing can spend on this ad account until one is set.
                  </p>
                )}
                <div className="flex gap-2">
                  <input
                    type="number"
                    step="0.01"
                    value={dailyLimitInput}
                    onChange={(e) => setDailyLimitInput(e.target.value)}
                    placeholder="Daily limit ($)"
                    className="flex-1 rounded-md border border-ink-200 px-3 py-2 text-sm"
                  />
                  <Button onClick={handleSaveLimit} disabled={isSaving}>
                    {isSaving ? "Saving…" : "Save"}
                  </Button>
                </div>
              </div>

              {limit && (
                <div className="rounded-lg border border-ink-100 bg-white p-4 shadow-panel">
                  <div className="mb-3 flex items-center gap-1.5">
                    <AlertOctagon className="h-4 w-4 text-signal" />
                    <p className="text-sm font-semibold text-ink-900">Emergency stop</p>
                  </div>
                  {limit.is_emergency_stopped ? (
                    <div>
                      <p className="mb-3 text-sm text-signal">
                        Active{limit.emergency_stop_reason ? `: ${limit.emergency_stop_reason}` : ""}
                      </p>
                      <Button variant="secondary" onClick={() => handleToggleStop(false)} disabled={isSaving}>
                        Resume spending
                      </Button>
                    </div>
                  ) : (
                    <div className="flex flex-col gap-2">
                      <input
                        value={stopReason}
                        onChange={(e) => setStopReason(e.target.value)}
                        placeholder="Reason (optional)"
                        className="rounded-md border border-ink-200 px-3 py-2 text-sm"
                      />
                      <Button variant="secondary" onClick={() => handleToggleStop(true)} disabled={isSaving} className="gap-1.5">
                        <AlertOctagon className="h-4 w-4" />
                        Stop all spending now
                      </Button>
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </main>
    </>
  );
}
