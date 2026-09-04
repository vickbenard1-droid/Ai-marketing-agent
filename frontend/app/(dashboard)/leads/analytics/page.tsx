"use client";

import { useEffect, useState } from "react";
import { Sparkles } from "lucide-react";
import { ApiError, askSalesAgent, getSalesAnalytics, type SalesAnalytics } from "@/lib/api";
import { useSession } from "@/lib/session";
import { Header } from "@/components/layout/header";
import { Button } from "@/components/ui/button";

function formatCents(cents: number | null): string {
  return cents === null ? "—" : `$${(cents / 100).toFixed(2)}`;
}
function formatPercent(v: number | null): string {
  return v === null ? "—" : `${v.toFixed(1)}%`;
}
function formatRatio(v: number | null): string {
  return v === null ? "—" : `${v.toFixed(2)}x`;
}

function defaultRange() {
  const stop = new Date();
  const start = new Date();
  start.setDate(start.getDate() - 30);
  return { dateStart: start.toISOString().slice(0, 10), dateStop: stop.toISOString().slice(0, 10) };
}

export default function SalesAnalyticsPage() {
  const { accessToken, activeOrganizationId } = useSession();
  const [analytics, setAnalytics] = useState<SalesAnalytics | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [range] = useState(defaultRange());
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<string | null>(null);
  const [isAsking, setIsAsking] = useState(false);

  useEffect(() => {
    if (!accessToken || !activeOrganizationId) return;
    setIsLoading(true);
    getSalesAnalytics(accessToken, activeOrganizationId, range.dateStart, range.dateStop)
      .then(setAnalytics)
      .catch((err) => setError(err instanceof ApiError ? String(err.detail ?? "Couldn't load") : "Couldn't load"))
      .finally(() => setIsLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken, activeOrganizationId]);

  async function handleAsk() {
    if (!accessToken || !activeOrganizationId || !question.trim()) return;
    setIsAsking(true);
    setError(null);
    setAnswer(null);
    try {
      const result = await askSalesAgent(accessToken, activeOrganizationId, { question, date_start: range.dateStart, date_stop: range.dateStop });
      setAnswer(result.answer_text);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail ?? "Couldn't get an answer") : "Couldn't get an answer");
    } finally {
      setIsAsking(false);
    }
  }

  return (
    <>
      <Header title="Sales analytics" description="Lead-to-sale performance and the AI sales agent" />
      <main className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-2xl space-y-4">
          {error && <p className="rounded-md bg-signal-soft px-4 py-3 text-sm text-signal">{error}</p>}
          {isLoading ? (
            <p className="text-sm text-ink-500">Loading…</p>
          ) : analytics ? (
            <>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <div className="rounded-lg border border-ink-100 bg-white p-4 shadow-panel"><p className="text-xs text-ink-500">Leads</p><p className="text-xl font-semibold text-ink-900">{analytics.leads}</p></div>
                <div className="rounded-lg border border-ink-100 bg-white p-4 shadow-panel"><p className="text-xs text-ink-500">Qualified</p><p className="text-xl font-semibold text-ink-900">{analytics.qualified_leads}</p></div>
                <div className="rounded-lg border border-ink-100 bg-white p-4 shadow-panel"><p className="text-xs text-ink-500">Sales</p><p className="text-xl font-semibold text-ink-900">{analytics.sales}</p></div>
                <div className="rounded-lg border border-ink-100 bg-white p-4 shadow-panel"><p className="text-xs text-ink-500">Conversion rate</p><p className="text-xl font-semibold text-ink-900">{formatPercent(analytics.conversion_rate)}</p></div>
                <div className="rounded-lg border border-ink-100 bg-white p-4 shadow-panel"><p className="text-xs text-ink-500">Revenue</p><p className="text-xl font-semibold text-ink-900">{formatCents(analytics.revenue_cents)}</p></div>
                <div className="rounded-lg border border-ink-100 bg-white p-4 shadow-panel"><p className="text-xs text-ink-500">Cost / sale</p><p className="text-xl font-semibold text-ink-900">{formatCents(analytics.cost_per_sale_cents)}</p></div>
                <div className="rounded-lg border border-ink-100 bg-white p-4 shadow-panel"><p className="text-xs text-ink-500">ROAS</p><p className="text-xl font-semibold text-ink-900">{formatRatio(analytics.roas)}</p></div>
                <div className="rounded-lg border border-ink-100 bg-white p-4 shadow-panel"><p className="text-xs text-ink-500">CAC</p><p className="text-xl font-semibold text-ink-900">{formatCents(analytics.customer_acquisition_cost_cents)}</p></div>
              </div>
              <p className="text-xs italic text-ink-400">{analytics.note}</p>

              <div className="rounded-lg border border-ink-100 bg-white p-4 shadow-panel">
                <p className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-ink-900"><Sparkles className="h-4 w-4" />Ask the sales agent</p>
                <div className="flex gap-2">
                  <input value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="Why aren't leads converting?" className="flex-1 rounded-md border border-ink-200 px-3 py-2 text-sm" onKeyDown={(e) => e.key === "Enter" && handleAsk()} />
                  <Button onClick={handleAsk} disabled={isAsking || !question.trim()}>{isAsking ? "Asking…" : "Ask"}</Button>
                </div>
                {answer && <p className="mt-3 whitespace-pre-wrap rounded-md bg-ink-50 p-3 text-sm text-ink-800">{answer}</p>}
              </div>
            </>
          ) : null}
        </div>
      </main>
    </>
  );
}
