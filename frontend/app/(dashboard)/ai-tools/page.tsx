"use client";

import { useEffect, useState } from "react";
import { Sparkles, Users, Megaphone, Search, Loader2 } from "lucide-react";
import {
  ApiError,
  getAIUsageSummary,
  listAgents,
  runAgent,
  type AgentInfo,
  type AIUsageSummary,
  type RunAgentResponse,
} from "@/lib/api";
import { useSession } from "@/lib/session";
import { Header } from "@/components/layout/header";
import { Button } from "@/components/ui/button";
import { TextareaField } from "@/components/ui/textarea-field";

const AGENT_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  marketing_strategy_agent: Sparkles,
  audience_research_agent: Users,
  ad_copy_agent: Megaphone,
  seo_agent: Search,
};

const AGENT_LABELS: Record<string, string> = {
  marketing_strategy_agent: "Marketing Strategy",
  audience_research_agent: "Audience Research",
  ad_copy_agent: "Ad Copy",
  seo_agent: "SEO",
};

// These two need a specific product/topic to produce anything useful —
// mirrors the backend's own requirement (see app/agents/ad_copy.py and
// seo.py, both of which reject an empty brief server-side too; this is a
// UX nicety, not the actual enforcement).
const REQUIRES_BRIEF = new Set(["ad_copy_agent", "seo_agent"]);

export default function AIToolsPage() {
  const { accessToken, activeOrganizationId } = useSession();
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [usage, setUsage] = useState<AIUsageSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const [brief, setBrief] = useState("");
  const [result, setResult] = useState<RunAgentResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isRunning, setIsRunning] = useState(false);

  useEffect(() => {
    if (!accessToken || !activeOrganizationId) return;
    Promise.all([
      listAgents(accessToken, activeOrganizationId),
      getAIUsageSummary(accessToken, activeOrganizationId),
    ])
      .then(([agentList, usageSummary]) => {
        setAgents(agentList);
        setUsage(usageSummary);
      })
      .finally(() => setIsLoading(false));
  }, [accessToken, activeOrganizationId]);

  async function handleRun() {
    if (!selectedAgent || !accessToken || !activeOrganizationId) return;
    setError(null);
    setResult(null);
    setIsRunning(true);
    try {
      const response = await runAgent(accessToken, activeOrganizationId, selectedAgent, brief || undefined);
      setResult(response);
      const refreshedUsage = await getAIUsageSummary(accessToken, activeOrganizationId);
      setUsage(refreshedUsage);
    } catch (err) {
      setError(
        err instanceof ApiError ? String(err.detail ?? "That didn't work — try again") : "That didn't work — try again"
      );
    } finally {
      setIsRunning(false);
    }
  }

  const briefRequired = selectedAgent ? REQUIRES_BRIEF.has(selectedAgent) : false;
  const canRun = selectedAgent && (!briefRequired || brief.trim().length > 0) && !isRunning;

  return (
    <>
      <Header title="AI Tools" description="Run a marketing agent for recommendations" />
      <main className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-3xl space-y-6">
          {usage && usage.total_calls > 0 && (
            <div className="flex items-center gap-6 rounded-lg border border-ink-100 bg-white px-5 py-3 text-sm">
              <span className="text-ink-500">
                <span className="font-semibold text-ink-900">{usage.total_calls}</span> AI calls
              </span>
              <span className="text-ink-500">
                <span className="font-semibold text-ink-900 tabular">
                  {(usage.total_input_tokens + usage.total_output_tokens).toLocaleString()}
                </span>{" "}
                tokens
              </span>
              {usage.total_estimated_cost_usd != null && (
                <span className="text-ink-500">
                  <span className="font-semibold text-ink-900 tabular">
                    ${usage.total_estimated_cost_usd.toFixed(4)}
                  </span>{" "}
                  estimated cost
                </span>
              )}
            </div>
          )}

          {isLoading ? (
            <p className="text-sm text-ink-500">Loading…</p>
          ) : (
            <>
              <div className="grid gap-3 sm:grid-cols-2">
                {agents.map((agent) => {
                  const Icon = AGENT_ICONS[agent.name] ?? Sparkles;
                  const isSelected = selectedAgent === agent.name;
                  return (
                    <button
                      key={agent.name}
                      onClick={() => {
                        setSelectedAgent(agent.name);
                        setResult(null);
                        setError(null);
                      }}
                      className={`rounded-lg border p-4 text-left transition-colors ${
                        isSelected ? "border-ink-900 bg-ink-50" : "border-ink-100 bg-white hover:border-ink-300"
                      }`}
                    >
                      <div className="mb-2 flex h-8 w-8 items-center justify-center rounded-md bg-ink-900">
                        <Icon className="h-4 w-4 text-white" />
                      </div>
                      <p className="text-sm font-semibold text-ink-900">
                        {AGENT_LABELS[agent.name] ?? agent.name}
                      </p>
                      <p className="mt-1 text-xs text-ink-500">{agent.description}</p>
                    </button>
                  );
                })}
              </div>

              {selectedAgent && (
                <div className="rounded-lg border border-ink-100 bg-white p-6 shadow-panel">
                  <TextareaField
                    label={briefRequired ? "Brief (required)" : "Brief (optional)"}
                    value={brief}
                    onChange={(e) => setBrief(e.target.value)}
                    placeholder={
                      briefRequired
                        ? "Describe the product, offer, or topic…"
                        : "Leave blank to use a general recommendation, or add specifics…"
                    }
                  />
                  <div className="mt-4">
                    <Button onClick={handleRun} disabled={!canRun} className="gap-2">
                      {isRunning && <Loader2 className="h-4 w-4 animate-spin" />}
                      {isRunning ? "Running…" : "Run"}
                    </Button>
                  </div>

                  {error && (
                    <p role="alert" className="mt-4 text-sm text-signal">
                      {error}
                    </p>
                  )}

                  {result && (
                    <div className="mt-6 border-t border-ink-100 pt-6">
                      {result.success ? (
                        <div className="whitespace-pre-wrap rounded-md bg-ink-50 p-4 text-sm text-ink-900">
                          {result.output}
                        </div>
                      ) : (
                        <p className="text-sm text-signal">{result.notes}</p>
                      )}
                      {result.success && result.notes && (
                        <p className="mt-2 text-xs text-ink-400">{result.notes}</p>
                      )}
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
