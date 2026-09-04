"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { AlertTriangle, Ban, ShieldCheck } from "lucide-react";
import {
  ACTION_TYPE_LABELS,
  ApiError,
  AUTONOMY_LEVEL_LABELS,
  addToWhitelist,
  getAutonomySettings,
  getWhitelistStatus,
  removeFromWhitelist,
  scanCampaignForOptimization,
  setAutonomySettings,
  setOptimizationEmergencyStop,
  type AutonomyLevel,
  type AutonomySettingsPublic,
  type OptimizationActionType,
} from "@/lib/api";
import { useSession } from "@/lib/session";
import { Header } from "@/components/layout/header";
import { Button } from "@/components/ui/button";

const ALL_ACTION_TYPES: OptimizationActionType[] = [
  "pause_ad", "reduce_budget", "increase_budget", "change_audience", "create_new_creative",
  "change_headline", "change_cta", "duplicate_winning_variation", "start_retargeting", "change_campaign_structure",
];

const EXECUTABLE_ACTION_TYPES = new Set<OptimizationActionType>(["pause_ad", "reduce_budget", "increase_budget"]);

function centsToDisplay(cents: number | null): string {
  return cents === null ? "" : (cents / 100).toString();
}

export default function CampaignAutonomySettingsPage() {
  const params = useParams<{ metaCampaignId: string }>();
  const { accessToken, activeOrganizationId } = useSession();
  const [settings, setSettings] = useState<AutonomySettingsPublic | null>(null);
  const [isWhitelisted, setIsWhitelisted] = useState<boolean | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isTogglingWhitelist, setIsTogglingWhitelist] = useState(false);
  const [isScanning, setIsScanning] = useState(false);
  const [scanResult, setScanResult] = useState<{ decisions_created: string[]; errors: string[] } | null>(null);

  const [autonomyLevel, setAutonomyLevel] = useState<AutonomyLevel>("manual");
  const [maxDailySpend, setMaxDailySpend] = useState("");
  const [maxIncreasePercent, setMaxIncreasePercent] = useState("");
  const [maxActionsPerDay, setMaxActionsPerDay] = useState("");
  const [autoExecutable, setAutoExecutable] = useState<Set<string>>(new Set());

  async function load() {
    if (!accessToken || !activeOrganizationId) return;
    const [s, whitelistEntry] = await Promise.all([
      getAutonomySettings(accessToken, activeOrganizationId, params.metaCampaignId),
      getWhitelistStatus(accessToken, activeOrganizationId, params.metaCampaignId),
    ]);
    setSettings(s);
    setAutonomyLevel(s.autonomy_level);
    setMaxDailySpend(centsToDisplay(s.max_daily_spend_cents));
    setMaxIncreasePercent(s.max_budget_increase_percent?.toString() ?? "");
    setMaxActionsPerDay(s.max_automated_actions_per_day?.toString() ?? "");
    setAutoExecutable(new Set(s.auto_executable_action_types));
    setIsWhitelisted(whitelistEntry !== null);
  }

  useEffect(() => {
    if (!accessToken || !activeOrganizationId) return;
    setIsLoading(true);
    load()
      .catch((err) => setError(err instanceof ApiError ? String(err.detail ?? "Couldn't load") : "Couldn't load"))
      .finally(() => setIsLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken, activeOrganizationId, params.metaCampaignId]);

  async function handleSave() {
    if (!accessToken || !activeOrganizationId) return;
    setIsSaving(true);
    setError(null);
    try {
      await setAutonomySettings(accessToken, activeOrganizationId, params.metaCampaignId, {
        autonomy_level: autonomyLevel,
        max_daily_spend_cents: maxDailySpend ? Math.round(parseFloat(maxDailySpend) * 100) : null,
        max_budget_increase_percent: maxIncreasePercent ? parseInt(maxIncreasePercent, 10) : null,
        max_automated_actions_per_day: maxActionsPerDay ? parseInt(maxActionsPerDay, 10) : null,
        auto_executable_action_types: Array.from(autoExecutable),
      });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail ?? "Couldn't save settings") : "Couldn't save settings");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleToggleWhitelist(add: boolean) {
    if (!accessToken || !activeOrganizationId) return;
    setIsTogglingWhitelist(true);
    setError(null);
    try {
      if (add) await addToWhitelist(accessToken, activeOrganizationId, params.metaCampaignId);
      else await removeFromWhitelist(accessToken, activeOrganizationId, params.metaCampaignId);
      setIsWhitelisted(add);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail ?? "Couldn't update whitelist") : "Couldn't update whitelist");
    } finally {
      setIsTogglingWhitelist(false);
    }
  }

  async function handleEmergencyStop(stop: boolean) {
    if (!accessToken || !activeOrganizationId) return;
    try {
      const updated = await setOptimizationEmergencyStop(accessToken, activeOrganizationId, params.metaCampaignId, { stopped: stop, reason: stop ? "Stopped from dashboard" : undefined });
      setSettings(updated);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail ?? "Couldn't update emergency stop") : "Couldn't update emergency stop");
    }
  }

  async function handleScan() {
    if (!accessToken || !activeOrganizationId) return;
    setIsScanning(true);
    setError(null);
    setScanResult(null);
    try {
      const result = await scanCampaignForOptimization(accessToken, activeOrganizationId, params.metaCampaignId);
      setScanResult(result);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail ?? "Couldn't scan campaign") : "Couldn't scan campaign");
    } finally {
      setIsScanning(false);
    }
  }

  function toggleActionType(actionType: string) {
    setAutoExecutable((prev) => {
      const next = new Set(prev);
      if (next.has(actionType)) next.delete(actionType);
      else next.add(actionType);
      return next;
    });
  }

  return (
    <>
      <Header title="Campaign autonomy settings" description="Configure how much this campaign's optimization agent may do on its own" />
      <main className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-2xl space-y-4">
          {error && <p className="rounded-md bg-signal-soft px-4 py-3 text-sm text-signal">{error}</p>}

          {isLoading ? (
            <p className="text-sm text-ink-500">Loading…</p>
          ) : (
            <>
              <div className="rounded-lg border border-ink-100 bg-white p-4 shadow-panel">
                <div className="mb-3 flex items-center justify-between">
                  <p className="text-sm font-semibold text-ink-900">Whitelist</p>
                  <ShieldCheck className="h-4 w-4 text-ink-300" />
                </div>
                <p className="mb-3 text-xs text-ink-500">A campaign must be whitelisted before the agent may act on it at all, separate from its autonomy level.</p>
                <div className="flex gap-2">
                  <Button variant={isWhitelisted === true ? "secondary" : "primary"} onClick={() => handleToggleWhitelist(true)} disabled={isTogglingWhitelist || isWhitelisted === true}>
                    Add to whitelist
                  </Button>
                  <Button variant="secondary" onClick={() => handleToggleWhitelist(false)} disabled={isTogglingWhitelist || isWhitelisted === false}>
                    Remove
                  </Button>
                </div>
                {isWhitelisted !== null && (
                  <p className="mt-2 text-xs text-ink-500">
                    {isWhitelisted ? "This campaign is whitelisted." : "This campaign is not whitelisted."}
                  </p>
                )}
              </div>

              <div className="rounded-lg border border-ink-100 bg-white p-4 shadow-panel">
                <p className="mb-3 text-sm font-semibold text-ink-900">Autonomy level</p>
                <div className="mb-4 flex gap-2">
                  {(["manual", "assisted", "autonomous"] as AutonomyLevel[]).map((level) => (
                    <button
                      key={level}
                      onClick={() => setAutonomyLevel(level)}
                      className={`rounded-full px-3.5 py-1.5 text-sm font-medium ${autonomyLevel === level ? "bg-ink-900 text-white" : "border border-ink-200 bg-white text-ink-600"}`}
                    >
                      {AUTONOMY_LEVEL_LABELS[level]}
                    </button>
                  ))}
                </div>

                <div className="mb-3 grid grid-cols-3 gap-3">
                  <div>
                    <label className="mb-1 block text-xs text-ink-500">Max daily spend ($)</label>
                    <input type="number" step="0.01" value={maxDailySpend} onChange={(e) => setMaxDailySpend(e.target.value)} className="w-full rounded-md border border-ink-200 px-2 py-1.5 text-sm" placeholder="Unset = blocked" />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs text-ink-500">Max budget increase (%)</label>
                    <input type="number" value={maxIncreasePercent} onChange={(e) => setMaxIncreasePercent(e.target.value)} className="w-full rounded-md border border-ink-200 px-2 py-1.5 text-sm" placeholder="e.g. 20" />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs text-ink-500">Max actions/day</label>
                    <input type="number" value={maxActionsPerDay} onChange={(e) => setMaxActionsPerDay(e.target.value)} className="w-full rounded-md border border-ink-200 px-2 py-1.5 text-sm" placeholder="e.g. 3" />
                  </div>
                </div>
                <p className="mb-4 text-xs text-ink-400">An unset limit blocks the corresponding autonomous action entirely - it never means &quot;unlimited&quot;.</p>

                {autonomyLevel === "autonomous" && (
                  <div className="mb-4">
                    <p className="mb-2 text-xs font-medium text-ink-700">Auto-executable action types</p>
                    <div className="flex flex-wrap gap-2">
                      {ALL_ACTION_TYPES.map((actionType) => {
                        const executable = EXECUTABLE_ACTION_TYPES.has(actionType);
                        return (
                          <label key={actionType} className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs ${executable ? "border-ink-200" : "border-ink-100 text-ink-300"}`}>
                            <input type="checkbox" disabled={!executable} checked={autoExecutable.has(actionType)} onChange={() => toggleActionType(actionType)} />
                            {ACTION_TYPE_LABELS[actionType]}
                            {!executable && <span title="No execution path exists for this action type yet">†</span>}
                          </label>
                        );
                      })}
                    </div>
                  </div>
                )}

                <Button onClick={handleSave} disabled={isSaving}>
                  {isSaving ? "Saving…" : "Save settings"}
                </Button>
              </div>

              <div className="rounded-lg border border-ink-100 bg-white p-4 shadow-panel">
                <div className="mb-2 flex items-center justify-between">
                  <p className="text-sm font-semibold text-ink-900">Emergency stop</p>
                  <Ban className="h-4 w-4 text-signal" />
                </div>
                {settings?.is_emergency_stopped ? (
                  <div>
                    <p className="mb-2 flex items-center gap-1.5 text-sm text-signal">
                      <AlertTriangle className="h-4 w-4" />
                      Emergency stop is active
                    </p>
                    <Button variant="secondary" onClick={() => handleEmergencyStop(false)}>
                      Re-enable
                    </Button>
                  </div>
                ) : (
                  <Button variant="secondary" onClick={() => handleEmergencyStop(true)} className="border-signal text-signal">
                    Emergency stop
                  </Button>
                )}
              </div>

              <div className="rounded-lg border border-ink-100 bg-white p-4 shadow-panel">
                <p className="mb-2 text-sm font-semibold text-ink-900">Manual scan</p>
                <Button onClick={handleScan} disabled={isScanning}>
                  {isScanning ? "Scanning…" : "Scan this campaign now"}
                </Button>
                {scanResult && (
                  <p className="mt-2 text-xs text-ink-500">
                    {scanResult.decisions_created.length} decision(s) created, {scanResult.errors.length} signal(s) skipped.
                  </p>
                )}
              </div>
            </>
          )}
        </div>
      </main>
    </>
  );
}
