"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Banknote,
  Megaphone,
  FileText,
  Plug,
  Target,
  TrendingUp,
  Users,
} from "lucide-react";
import { getDashboardSummary, type DashboardSummary } from "@/lib/api";
import { useSession } from "@/lib/session";
import { Header } from "@/components/layout/header";
import { Button } from "@/components/ui/button";

const GOAL_LABELS: Record<string, string> = {
  sales: "Sales",
  leads: "Leads",
  website_traffic: "Website traffic",
  brand_awareness: "Brand awareness",
};

export default function DashboardPage() {
  const { user, accessToken, activeOrganization, activeOrganizationId } = useSession();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const firstName = user?.full_name?.split(" ")[0];

  useEffect(() => {
    if (!accessToken || !activeOrganizationId) return;
    getDashboardSummary(accessToken, activeOrganizationId)
      .then(setSummary)
      .finally(() => setIsLoading(false));
  }, [accessToken, activeOrganizationId]);

  return (
    <>
      <Header title="Dashboard" description={activeOrganization ? activeOrganization.name : undefined} />

      <main className="flex-1 overflow-y-auto p-6">
        <div className="mb-6">
          <h2 className="text-xl font-semibold text-ink-900">
            {firstName ? `Welcome back, ${firstName}` : "Welcome"}
          </h2>
        </div>

        {!isLoading && summary && !summary.onboarding_completed && (
          <div className="mb-6 flex items-center justify-between rounded-lg border border-ink-200 bg-ink-50 p-4">
            <div>
              <p className="text-sm font-medium text-ink-900">Finish setting up your business</p>
              <p className="text-sm text-ink-500">
                A few quick questions help us tailor everything to your business.
              </p>
            </div>
            <Link href="/onboarding">
              <Button>Continue setup</Button>
            </Link>
          </div>
        )}

        {isLoading ? (
          <p className="text-sm text-ink-500">Loading…</p>
        ) : summary ? (
          <>
            {/* Business snapshot — real onboarding data, no fabricated numbers */}
            <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <SnapshotCard
                icon={Target}
                label="Marketing goal"
                value={
                  summary.marketing_goal ? GOAL_LABELS[summary.marketing_goal] ?? summary.marketing_goal : "Not set"
                }
              />
              <SnapshotCard
                icon={Banknote}
                label="Monthly budget"
                value={
                  summary.monthly_ad_budget != null
                    ? `${summary.monthly_ad_budget.toLocaleString()} ${summary.budget_currency}`
                    : "Not set"
                }
              />
              <SnapshotCard
                icon={Plug}
                label="Connected platforms"
                value={String(summary.connected_platforms_count)}
              />
              <SnapshotCard icon={Users} label="Business" value={summary.business_name} />
            </div>

            {/* Performance — genuine empty states. No backing data exists
                yet (campaigns/content/leads/sales aren't built until a
                later week), so these are honestly zero, not placeholders
                dressed up as numbers. */}
            <h3 className="mb-3 text-sm font-semibold text-ink-900">Performance</h3>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <EmptyMetricCard
                icon={Megaphone}
                label="Campaigns"
                count={summary.campaign_count}
                emptyBody="No campaigns yet. Campaign creation is coming in a future release."
              />
              <EmptyMetricCard
                icon={FileText}
                label="Content"
                count={summary.content_count}
                emptyBody="No content yet. Content generation is coming in a future release."
              />
              <EmptyMetricCard icon={Users} label="Leads" count={summary.leads_count} emptyBody="No leads tracked yet." />
              <EmptyMetricCard
                icon={TrendingUp}
                label="Sales"
                count={summary.sales_count}
                emptyBody="No sales tracked yet."
              />
              <EmptyMetricCard
                icon={Banknote}
                label="Total spend"
                count={summary.total_spend}
                formatAsCurrency
                currency={summary.spend_currency}
                emptyBody="No ad spend recorded yet."
              />
            </div>
          </>
        ) : (
          <p className="text-sm text-ink-500">Couldn&apos;t load your dashboard.</p>
        )}
      </main>
    </>
  );
}

function SnapshotCard({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-lg border border-ink-100 bg-white p-5 shadow-panel">
      <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-md bg-ink-50">
        <Icon className="h-4.5 w-4.5 text-ink-600" />
      </div>
      <p className="text-xs font-medium uppercase tracking-wide text-ink-400">{label}</p>
      <p className="mt-1 truncate text-base font-semibold text-ink-900">{value}</p>
    </div>
  );
}

function EmptyMetricCard({
  icon: Icon,
  label,
  count,
  emptyBody,
  formatAsCurrency,
  currency,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  count: number;
  emptyBody: string;
  formatAsCurrency?: boolean;
  currency?: string;
}) {
  const isEmpty = count === 0;
  const displayValue = formatAsCurrency
    ? `${count.toLocaleString()} ${currency ?? ""}`.trim()
    : count.toLocaleString();

  return (
    <div className="rounded-lg border border-ink-100 bg-white p-5 shadow-panel">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex h-9 w-9 items-center justify-center rounded-md bg-ink-50">
          <Icon className="h-4.5 w-4.5 text-ink-600" />
        </div>
        <span className="text-2xl font-semibold tabular text-ink-900">{displayValue}</span>
      </div>
      <p className="text-sm font-medium text-ink-900">{label}</p>
      {isEmpty && <p className="mt-1 text-xs text-ink-400">{emptyBody}</p>}
    </div>
  );
}
