"use client";

import { useEffect, useState } from "react";
import { Check, TrendingUp } from "lucide-react";
import {
  ApiError, changePlan, getCurrentPlanAndUsage, listSubscriptionPlans,
  type CurrentPlanAndUsagePublic, type SubscriptionPlanPublic,
} from "@/lib/api";
import { useSession } from "@/lib/session";
import { Header } from "@/components/layout/header";
import { Button } from "@/components/ui/button";

const CATEGORY_LABELS: Record<string, string> = {
  ai_tokens: "AI tokens (this month)",
  campaigns: "Campaigns",
  connected_accounts: "Connected accounts",
  content_generations: "Content generated (this month)",
  automated_actions: "Automated actions (this month)",
};

function formatPrice(cents: number): string {
  return cents === 0 ? "Free" : `$${(cents / 100).toFixed(0)}/mo`;
}

function formatLimit(limit: number | null): string {
  if (limit === null) return "Unlimited";
  return limit.toLocaleString();
}

function usageBarColor(current: number, limit: number | null): string {
  if (limit === null) return "bg-positive";
  const ratio = limit === 0 ? (current > 0 ? 1 : 0) : current / limit;
  if (ratio >= 1) return "bg-signal";
  if (ratio >= 0.8) return "bg-signal-soft";
  return "bg-positive";
}

export default function BillingPage() {
  const { accessToken, activeOrganizationId } = useSession();
  const [current, setCurrent] = useState<CurrentPlanAndUsagePublic | null>(null);
  const [plans, setPlans] = useState<SubscriptionPlanPublic[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isChanging, setIsChanging] = useState<string | null>(null);

  async function load() {
    if (!accessToken || !activeOrganizationId) return;
    const [currentResp, plansResp] = await Promise.all([
      getCurrentPlanAndUsage(accessToken, activeOrganizationId),
      listSubscriptionPlans(accessToken),
    ]);
    setCurrent(currentResp);
    setPlans(plansResp);
  }

  useEffect(() => {
    if (!accessToken || !activeOrganizationId) return;
    setIsLoading(true);
    load().catch((err) => setError(err instanceof ApiError ? String(err.detail ?? "Couldn't load") : "Couldn't load")).finally(() => setIsLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken, activeOrganizationId]);

  async function handleChangePlan(planName: string) {
    if (!accessToken || !activeOrganizationId) return;
    setIsChanging(planName);
    setError(null);
    try {
      await changePlan(accessToken, activeOrganizationId, planName);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail ?? "Couldn't change plan - you may need owner permission") : "Couldn't change plan - you may need owner permission");
    } finally {
      setIsChanging(null);
    }
  }

  return (
    <>
      <Header title="Billing" description="Your plan, usage, and available upgrades" />
      <main className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-3xl space-y-6">
          {error && <p className="rounded-md bg-signal-soft px-4 py-3 text-sm text-signal">{error}</p>}

          {isLoading || !current ? (
            <p className="text-sm text-ink-500">Loading…</p>
          ) : (
            <>
              <div className="rounded-lg border border-ink-100 bg-white p-4 shadow-panel">
                <div className="mb-3 flex items-center justify-between">
                  <p className="text-sm font-semibold text-ink-900">Current plan: {current.plan.display_name}</p>
                  <span className="text-sm text-ink-500">{formatPrice(current.plan.monthly_price_cents)}</span>
                </div>
                <div className="flex flex-col gap-3">
                  {current.usage.map((u) => {
                    const ratio = u.limit === null ? 0 : u.limit === 0 ? (u.current > 0 ? 100 : 0) : Math.min(100, (u.current / u.limit) * 100);
                    return (
                      <div key={u.category}>
                        <div className="mb-1 flex items-center justify-between text-xs text-ink-600">
                          <span>{CATEGORY_LABELS[u.category] ?? u.category}</span>
                          <span>{u.current.toLocaleString()} / {formatLimit(u.limit)}</span>
                        </div>
                        <div className="h-1.5 w-full overflow-hidden rounded-full bg-ink-100">
                          <div className={`h-full rounded-full ${usageBarColor(u.current, u.limit)}`} style={{ width: `${u.limit === null ? 8 : ratio}%` }} />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              <div>
                <p className="mb-3 flex items-center gap-1.5 text-sm font-semibold text-ink-900"><TrendingUp className="h-4 w-4" />Available plans</p>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  {plans.map((plan) => {
                    const isCurrent = plan.name === current.plan.name;
                    return (
                      <div key={plan.id} className={`rounded-lg border p-4 shadow-panel ${isCurrent ? "border-ink-900 bg-ink-50" : "border-ink-100 bg-white"}`}>
                        <p className="text-sm font-semibold text-ink-900">{plan.display_name}</p>
                        <p className="mt-1 text-lg font-semibold text-ink-900">{formatPrice(plan.monthly_price_cents)}</p>
                        <ul className="mt-3 flex flex-col gap-1.5 text-xs text-ink-600">
                          <li>{formatLimit(plan.max_campaigns)} campaigns</li>
                          <li>{formatLimit(plan.max_connected_accounts)} connected accounts</li>
                          <li>{formatLimit(plan.max_content_generations_per_month)} content/mo</li>
                          <li>{formatLimit(plan.max_automated_actions_per_month)} automated actions/mo</li>
                          <li>{formatLimit(plan.max_ai_tokens_per_month)} AI tokens/mo</li>
                        </ul>
                        {isCurrent ? (
                          <div className="mt-4 flex items-center gap-1.5 text-xs font-medium text-ink-500"><Check className="h-3.5 w-3.5" />Current plan</div>
                        ) : (
                          <Button variant="secondary" onClick={() => handleChangePlan(plan.name)} disabled={isChanging === plan.name} className="mt-4 w-full text-xs">
                            {isChanging === plan.name ? "Switching…" : "Switch to this plan"}
                          </Button>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            </>
          )}
        </div>
      </main>
    </>
  );
}
