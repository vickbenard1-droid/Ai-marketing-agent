"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { CheckCircle2, Link2, RefreshCw, Unlink, XCircle } from "lucide-react";
import {
  ApiError,
  SOCIAL_PLATFORM_LABELS,
  createProject,
  disconnectAccount,
  listConnectedAccounts,
  listProjects,
  listSupportedPlatforms,
  reauthorizeAccount,
  startConnectFlow,
  type ConnectedAccountPublic,
  type SocialPlatform,
  type SupportedPlatform,
} from "@/lib/api";
import { useSession } from "@/lib/session";
import { Header } from "@/components/layout/header";
import { Button } from "@/components/ui/button";

const STATUS_STYLES: Record<string, string> = {
  connected: "bg-positive-soft text-positive",
  expired: "bg-signal-soft text-signal",
  error: "bg-signal-soft text-signal",
  disconnected: "bg-ink-100 text-ink-500",
};

function IntegrationsContent() {
  const { accessToken, activeOrganizationId } = useSession();
  const router = useRouter();
  const searchParams = useSearchParams();

  const [platforms, setPlatforms] = useState<SupportedPlatform[]>([]);
  const [accounts, setAccounts] = useState<ConnectedAccountPublic[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [connectingPlatform, setConnectingPlatform] = useState<SocialPlatform | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [banner, setBanner] = useState<string | null>(null);

  async function load() {
    if (!accessToken || !activeOrganizationId) return;
    const [platformList, accountList] = await Promise.all([
      listSupportedPlatforms(accessToken, activeOrganizationId),
      listConnectedAccounts(accessToken, activeOrganizationId),
    ]);
    setPlatforms(platformList);
    setAccounts(accountList);
  }

  useEffect(() => {
    if (!accessToken || !activeOrganizationId) return;
    load().finally(() => setIsLoading(false));

    const connected = searchParams.get("connected");
    const oauthError = searchParams.get("error");
    if (connected) {
      setBanner(`${SOCIAL_PLATFORM_LABELS[connected as SocialPlatform] ?? connected} connected successfully.`);
      router.replace("/integrations");
    } else if (oauthError) {
      setError(oauthError);
      router.replace("/integrations");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken, activeOrganizationId]);

  async function handleConnect(platform: SocialPlatform) {
    if (!accessToken || !activeOrganizationId) return;
    setError(null);
    setConnectingPlatform(platform);
    try {
      const projects = await listProjects(accessToken, activeOrganizationId);
      const project =
        projects[0] ?? (await createProject(accessToken, activeOrganizationId, { name: "Default" }));

      const { authorize_url } = await startConnectFlow(accessToken, activeOrganizationId, platform, project.id);
      window.location.href = authorize_url;
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail ?? "Couldn't start connection") : "Couldn't start connection");
      setConnectingPlatform(null);
    }
  }

  async function handleDisconnect(accountId: string) {
    if (!accessToken || !activeOrganizationId) return;
    await disconnectAccount(accessToken, activeOrganizationId, accountId);
    await load();
  }

  async function handleReauthorize(accountId: string) {
    if (!accessToken || !activeOrganizationId) return;
    try {
      const { authorize_url } = await reauthorizeAccount(accessToken, activeOrganizationId, accountId);
      window.location.href = authorize_url;
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail ?? "Couldn't reauthorize") : "Couldn't reauthorize");
    }
  }

  const accountsByPlatform = new Map(accounts.map((a) => [a.platform, a]));

  return (
    <>
      <Header title="Integrations" description="Connect your social accounts to schedule and publish content" />
      <main className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-2xl space-y-4">
          {banner && (
            <p className="flex items-center gap-2 rounded-md bg-positive-soft px-4 py-3 text-sm text-positive">
              <CheckCircle2 className="h-4 w-4 shrink-0" />
              {banner}
            </p>
          )}
          {error && (
            <p className="flex items-center gap-2 rounded-md bg-signal-soft px-4 py-3 text-sm text-signal">
              <XCircle className="h-4 w-4 shrink-0" />
              {error}
            </p>
          )}

          {isLoading ? (
            <p className="text-sm text-ink-500">Loading…</p>
          ) : (
            <div className="flex flex-col gap-2">
              {platforms.map((p) => {
                const account = accountsByPlatform.get(p.platform);
                return (
                  <div
                    key={p.platform}
                    className="flex items-center justify-between rounded-lg border border-ink-100 bg-white p-4 shadow-panel"
                  >
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-semibold text-ink-900">{p.display_name}</p>
                        {account && (
                          <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[account.status]}`}>
                            {account.status}
                          </span>
                        )}
                      </div>
                      {account?.external_account_name && (
                        <p className="text-xs text-ink-500">{account.external_account_name}</p>
                      )}
                      {account?.last_error && <p className="text-xs text-signal">{account.last_error}</p>}
                      {!p.configured && !account && (
                        <p className="text-xs text-ink-400">Not available on this deployment yet</p>
                      )}
                    </div>

                    <div className="flex shrink-0 gap-2">
                      {account && account.status !== "disconnected" ? (
                        <>
                          {(account.status === "expired" || account.status === "error") && (
                            <Button
                              variant="secondary"
                              onClick={() => handleReauthorize(account.id)}
                              className="gap-1.5"
                            >
                              <RefreshCw className="h-4 w-4" />
                              Reauthorize
                            </Button>
                          )}
                          <button
                            onClick={() => handleDisconnect(account.id)}
                            className="flex items-center gap-1.5 rounded-md px-3 py-2 text-sm text-ink-500 hover:bg-ink-50"
                          >
                            <Unlink className="h-4 w-4" />
                            Disconnect
                          </button>
                        </>
                      ) : (
                        <Button
                          variant="secondary"
                          disabled={!p.configured || connectingPlatform === p.platform}
                          onClick={() => handleConnect(p.platform)}
                          className="gap-1.5"
                        >
                          <Link2 className="h-4 w-4" />
                          {connectingPlatform === p.platform ? "Connecting…" : "Connect"}
                        </Button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </main>
    </>
  );
}

export default function IntegrationsPage() {
  return (
    <Suspense fallback={<Header title="Integrations" />}>
      <IntegrationsContent />
    </Suspense>
  );
}
