"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle, ChevronRight, ShieldAlert } from "lucide-react";
import {
  ApiError,
  listMetaAdAccounts,
  listMetaCampaigns,
  type MetaAdAccountPublic,
  type MetaCampaignPublic,
} from "@/lib/api";
import { useSession } from "@/lib/session";
import { Header } from "@/components/layout/header";

const STATUS_STYLES: Record<string, string> = {
  ACTIVE: "bg-positive-soft text-positive",
  PAUSED: "bg-ink-100 text-ink-600",
  DELETED: "bg-signal-soft text-signal",
  ARCHIVED: "bg-ink-100 text-ink-400",
};

function formatCents(cents: number | null): string {
  if (cents === null) return "—";
  return `$${(cents / 100).toFixed(2)}`;
}

export default function MetaAdsPage() {
  const { accessToken, activeOrganizationId } = useSession();
  const [adAccounts, setAdAccounts] = useState<MetaAdAccountPublic[]>([]);
  const [campaigns, setCampaigns] = useState<MetaCampaignPublic[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!accessToken || !activeOrganizationId) return;
    setIsLoading(true);
    Promise.all([
      listMetaAdAccounts(accessToken, activeOrganizationId),
      listMetaCampaigns(accessToken, activeOrganizationId),
    ])
      .then(([accounts, campaignList]) => {
        setAdAccounts(accounts);
        setCampaigns(campaignList);
      })
      .catch((err) => setError(err instanceof ApiError ? String(err.detail ?? "Couldn't load") : "Couldn't load"))
      .finally(() => setIsLoading(false));
  }, [accessToken, activeOrganizationId]);

  return (
    <>
      <Header title="Meta Ads" description="Manage real ad accounts, campaigns, and spend" />
      <main className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-3xl space-y-6">
          <div className="flex items-center justify-between">
            <p className="text-sm text-ink-500">
              Connect an ad account from{" "}
              <Link href="/integrations" className="underline">
                Integrations
              </Link>{" "}
              first, then configure a spend limit here before anything can launch.
            </p>
            <Link href="/meta-ads/approval-requests" className="flex items-center gap-1 text-sm font-medium text-ink-700 underline">
              Approval requests
              <ChevronRight className="h-4 w-4" />
            </Link>
          </div>

          {error && (
            <p className="flex items-center gap-1.5 rounded-md bg-signal-soft px-4 py-3 text-sm text-signal">
              <AlertTriangle className="h-4 w-4" />
              {error}
            </p>
          )}

          {isLoading ? (
            <p className="text-sm text-ink-500">Loading…</p>
          ) : (
            <>
              <div>
                <p className="mb-2 text-sm font-semibold text-ink-900">Ad accounts</p>
                {adAccounts.length === 0 ? (
                  <p className="text-sm text-ink-400">No ad accounts connected yet.</p>
                ) : (
                  <div className="flex flex-col gap-2">
                    {adAccounts.map((account) => (
                      <Link
                        key={account.id}
                        href={`/meta-ads/${account.id}`}
                        className="flex items-center justify-between rounded-lg border border-ink-100 bg-white p-4 shadow-panel hover:border-ink-300"
                      >
                        <div className="flex items-center gap-2">
                          <ShieldAlert className="h-4 w-4 text-ink-300" />
                          <div>
                            <p className="text-sm font-medium text-ink-900">{account.name}</p>
                            <p className="text-xs text-ink-400">{account.external_ad_account_id} · {account.currency}</p>
                          </div>
                        </div>
                        <ChevronRight className="h-4 w-4 text-ink-300" />
                      </Link>
                    ))}
                  </div>
                )}
              </div>

              <div>
                <p className="mb-2 text-sm font-semibold text-ink-900">Campaigns</p>
                {campaigns.length === 0 ? (
                  <p className="text-sm text-ink-400">No campaigns yet.</p>
                ) : (
                  <div className="flex flex-col gap-2">
                    {campaigns.map((campaign) => (
                      <div key={campaign.id} className="rounded-lg border border-ink-100 bg-white p-4 shadow-panel">
                        <div className="mb-1 flex items-center justify-between">
                          <p className="text-sm font-medium text-ink-900">{campaign.name}</p>
                          <span className={`rounded-full px-2 py-0.5 text-xs ${STATUS_STYLES[campaign.status]}`}>
                            {campaign.status}
                          </span>
                        </div>
                        <div className="flex gap-4 text-xs text-ink-500">
                          <span>{campaign.objective}</span>
                          <span>Daily budget: {formatCents(campaign.daily_budget_cents)}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </main>
    </>
  );
}
