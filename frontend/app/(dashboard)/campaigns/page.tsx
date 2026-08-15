"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Megaphone, Plus } from "lucide-react";
import { listCampaigns, type CampaignPublic, type CampaignStatus } from "@/lib/api";
import { useSession } from "@/lib/session";
import { Header } from "@/components/layout/header";
import { Button } from "@/components/ui/button";

const STATUS_LABELS: Record<CampaignStatus, string> = {
  draft: "Draft",
  generating: "Generating…",
  generated: "Ready for review",
  approved: "Approved",
};

const STATUS_STYLES: Record<CampaignStatus, string> = {
  draft: "bg-ink-100 text-ink-600",
  generating: "bg-signal-soft text-signal",
  generated: "bg-ink-100 text-ink-900",
  approved: "bg-positive-soft text-positive",
};

export default function CampaignsPage() {
  const { accessToken, activeOrganizationId } = useSession();
  const [campaigns, setCampaigns] = useState<CampaignPublic[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!accessToken || !activeOrganizationId) return;
    listCampaigns(accessToken, activeOrganizationId)
      .then(setCampaigns)
      .finally(() => setIsLoading(false));
  }, [accessToken, activeOrganizationId]);

  return (
    <>
      <Header title="Campaigns" description="AI-generated campaign drafts" />
      <main className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-3xl">
          <div className="mb-6 flex justify-end">
            <Link href="/campaigns/new">
              <Button className="gap-1.5">
                <Plus className="h-4 w-4" />
                New campaign
              </Button>
            </Link>
          </div>

          {isLoading ? (
            <p className="text-sm text-ink-500">Loading…</p>
          ) : campaigns.length === 0 ? (
            <div className="rounded-lg border border-dashed border-ink-200 bg-white p-10 text-center">
              <Megaphone className="mx-auto mb-3 h-8 w-8 text-ink-300" />
              <p className="mb-1 text-sm font-medium text-ink-900">No campaigns yet</p>
              <p className="mb-4 text-sm text-ink-500">
                Describe what you want to sell and let AI build a complete campaign strategy.
              </p>
              <Link href="/campaigns/new">
                <Button>Create your first campaign</Button>
              </Link>
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              {campaigns.map((c) => (
                <Link
                  key={c.id}
                  href={`/campaigns/${c.id}`}
                  className="flex items-center justify-between rounded-lg border border-ink-100 bg-white p-4 shadow-panel hover:border-ink-300"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-ink-900">{c.product_name}</p>
                    <p className="text-xs text-ink-500">
                      {c.objective.replace(/_/g, " ")}
                      {c.budget_amount != null && ` · ${c.budget_amount.toLocaleString()} ${c.budget_currency}`}
                      {c.desired_outcome_count != null && ` · ${c.desired_outcome_count} target`}
                    </p>
                  </div>
                  <span
                    className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-medium ${STATUS_STYLES[c.status]}`}
                  >
                    {STATUS_LABELS[c.status]}
                  </span>
                </Link>
              ))}
            </div>
          )}
        </div>
      </main>
    </>
  );
}
