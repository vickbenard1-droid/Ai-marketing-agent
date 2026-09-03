"use client";

import { useEffect, useState } from "react";
import { Copy, RefreshCw } from "lucide-react";
import {
  ApiError,
  getDashboard,
  getTrackingKey,
  listConversionTypes,
  regenerateTrackingKey,
  type ConversionTypePublic,
  type DashboardResponse,
} from "@/lib/api";
import { useSession } from "@/lib/session";
import { Header } from "@/components/layout/header";
import { Button } from "@/components/ui/button";

function formatCents(cents: number | null): string {
  if (cents === null) return "—";
  return `$${(cents / 100).toFixed(2)}`;
}

function formatPercent(value: number | null): string {
  if (value === null) return "—";
  return `${value.toFixed(2)}%`;
}

function formatRatio(value: number | null): string {
  if (value === null) return "—";
  return `${value.toFixed(2)}x`;
}

function defaultDateRange() {
  const stop = new Date();
  const start = new Date();
  start.setDate(start.getDate() - 30);
  return { dateStart: start.toISOString().slice(0, 10), dateStop: stop.toISOString().slice(0, 10) };
}

export default function AnalyticsPage() {
  const { accessToken, activeOrganizationId } = useSession();
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null);
  const [conversionTypes, setConversionTypes] = useState<ConversionTypePublic[]>([]);
  const [trackingKey, setTrackingKey] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [range] = useState(defaultDateRange());

  async function load() {
    if (!accessToken || !activeOrganizationId) return;
    const [dashboardData, types, key] = await Promise.all([
      getDashboard(accessToken, activeOrganizationId, range.dateStart, range.dateStop),
      listConversionTypes(accessToken, activeOrganizationId),
      getTrackingKey(accessToken, activeOrganizationId),
    ]);
    setDashboard(dashboardData);
    setConversionTypes(types);
    setTrackingKey(key.key);
  }

  useEffect(() => {
    if (!accessToken || !activeOrganizationId) return;
    setIsLoading(true);
    load()
      .catch((err) => setError(err instanceof ApiError ? String(err.detail ?? "Couldn't load") : "Couldn't load"))
      .finally(() => setIsLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken, activeOrganizationId]);

  async function handleRegenerateKey() {
    if (!accessToken || !activeOrganizationId) return;
    const key = await regenerateTrackingKey(accessToken, activeOrganizationId);
    setTrackingKey(key.key);
  }

  function handleCopyKey() {
    if (!trackingKey) return;
    navigator.clipboard.writeText(trackingKey);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  const snippet = trackingKey
    ? `<script>\n  fetch("${process.env.NEXT_PUBLIC_API_BASE_URL || ""}/api/v1/track/page-view", {\n    method: "POST",\n    headers: { "Content-Type": "application/json" },\n    body: JSON.stringify({\n      tracking_key: "${trackingKey}",\n      visitor_id: crypto.randomUUID(),\n      page_url: window.location.pathname\n    })\n  });\n</script>`
    : "";

  return (
    <>
      <Header title="Analytics" description="Unified performance across every connected data source" />
      <main className="flex-1 overflow-y-auto p-6">
        {error && <p className="mb-4 rounded-md bg-signal-soft px-4 py-3 text-sm text-signal">{error}</p>}
        {isLoading ? (
          <p className="text-sm text-ink-500">Loading…</p>
        ) : dashboard ? (
          <div className="space-y-6">
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <div className="rounded-lg border border-ink-100 bg-white p-4 shadow-panel">
                <p className="text-xs text-ink-500">Impressions</p>
                <p className="text-xl font-semibold text-ink-900">{dashboard.raw.impressions.toLocaleString()}</p>
              </div>
              <div className="rounded-lg border border-ink-100 bg-white p-4 shadow-panel">
                <p className="text-xs text-ink-500">Clicks</p>
                <p className="text-xl font-semibold text-ink-900">{dashboard.raw.clicks.toLocaleString()}</p>
              </div>
              <div className="rounded-lg border border-ink-100 bg-white p-4 shadow-panel">
                <p className="text-xs text-ink-500">Spend</p>
                <p className="text-xl font-semibold text-ink-900">{formatCents(dashboard.raw.spend_cents)}</p>
              </div>
              <div className="rounded-lg border border-ink-100 bg-white p-4 shadow-panel">
                <p className="text-xs text-ink-500">Revenue</p>
                <p className="text-xl font-semibold text-ink-900">{formatCents(dashboard.raw.revenue_cents)}</p>
              </div>
              <div className="rounded-lg border border-ink-100 bg-white p-4 shadow-panel">
                <p className="text-xs text-ink-500">CTR</p>
                <p className="text-xl font-semibold text-ink-900">{formatPercent(dashboard.derived.ctr)}</p>
              </div>
              <div className="rounded-lg border border-ink-100 bg-white p-4 shadow-panel">
                <p className="text-xs text-ink-500">Cost / Lead</p>
                <p className="text-xl font-semibold text-ink-900">{formatCents(dashboard.derived.cost_per_lead_cents)}</p>
              </div>
              <div className="rounded-lg border border-ink-100 bg-white p-4 shadow-panel">
                <p className="text-xs text-ink-500">CPA</p>
                <p className="text-xl font-semibold text-ink-900">{formatCents(dashboard.derived.cpa_cents)}</p>
              </div>
              <div className="rounded-lg border border-ink-100 bg-white p-4 shadow-panel">
                <p className="text-xs text-ink-500">ROAS</p>
                <p className="text-xl font-semibold text-ink-900">{formatRatio(dashboard.derived.roas)}</p>
              </div>
            </div>
            <p className="text-xs text-ink-400">
              A dash (—) means this metric hasn&apos;t been measured yet, not that it&apos;s zero.
            </p>

            <div className="rounded-lg border border-ink-100 bg-white p-4 shadow-panel">
              <p className="mb-3 text-sm font-semibold text-ink-900">Conversion types</p>
              <div className="flex flex-wrap gap-2">
                {conversionTypes.map((t) => (
                  <span key={t.id} className="rounded-full bg-ink-100 px-3 py-1 text-xs text-ink-700">
                    {t.name}
                    {t.counts_as_revenue && <span className="ml-1 text-positive">$</span>}
                  </span>
                ))}
              </div>
            </div>

            <div className="rounded-lg border border-ink-100 bg-white p-4 shadow-panel">
              <div className="mb-3 flex items-center justify-between">
                <p className="text-sm font-semibold text-ink-900">Website tracking</p>
                <Button variant="secondary" onClick={handleRegenerateKey} className="gap-1.5 text-xs">
                  <RefreshCw className="h-3.5 w-3.5" />
                  Regenerate key
                </Button>
              </div>
              <p className="mb-3 text-xs text-ink-500">
                Add this snippet to your website to start tracking page views and conversions.
              </p>
              <div className="relative">
                <pre className="overflow-x-auto rounded-md bg-ink-900 p-3 text-xs text-white">{snippet}</pre>
                <button
                  onClick={handleCopyKey}
                  className="absolute right-2 top-2 rounded-md bg-white/10 p-1.5 text-white hover:bg-white/20"
                >
                  <Copy className="h-3.5 w-3.5" />
                </button>
              </div>
              {copied && <p className="mt-1 text-xs text-positive">Copied!</p>}
            </div>
          </div>
        ) : null}
      </main>
    </>
  );
}
