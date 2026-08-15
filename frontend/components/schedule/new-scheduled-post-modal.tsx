"use client";

import { useEffect, useState } from "react";
import { X } from "lucide-react";
import {
  ApiError,
  SOCIAL_PLATFORM_LABELS,
  createDraftPost,
  listContent,
  type ConnectedAccountPublic,
  type ContentPublic,
} from "@/lib/api";
import { useSession } from "@/lib/session";
import { Button } from "@/components/ui/button";

interface NewScheduledPostModalProps {
  accounts: ConnectedAccountPublic[];
  onClose: () => void;
  onCreated: () => void;
}

export function NewScheduledPostModal({ accounts, onClose, onCreated }: NewScheduledPostModalProps) {
  const { accessToken, activeOrganizationId } = useSession();
  const [contentItems, setContentItems] = useState<ContentPublic[]>([]);
  const [selectedContentId, setSelectedContentId] = useState("");
  const [selectedAccountId, setSelectedAccountId] = useState(accounts[0]?.id ?? "");
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!accessToken || !activeOrganizationId) return;
    listContent(accessToken, activeOrganizationId, { status: "approved" })
      .then(setContentItems)
      .finally(() => setIsLoading(false));
  }, [accessToken, activeOrganizationId]);

  async function handleCreate() {
    if (!accessToken || !activeOrganizationId || !selectedContentId || !selectedAccountId) return;
    setIsSaving(true);
    setError(null);
    try {
      await createDraftPost(accessToken, activeOrganizationId, {
        content_id: selectedContentId,
        connected_account_id: selectedAccountId,
      });
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail ?? "Couldn't create draft") : "Couldn't create draft");
    } finally {
      setIsSaving(false);
    }
  }

  const connectedAccounts = accounts.filter((a) => a.status === "connected");

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
      <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-base font-semibold text-ink-900">Schedule a post</h2>
          <button onClick={onClose} className="text-ink-400 hover:text-ink-700">
            <X className="h-5 w-5" />
          </button>
        </div>

        {isLoading ? (
          <p className="text-sm text-ink-500">Loading…</p>
        ) : connectedAccounts.length === 0 ? (
          <p className="text-sm text-ink-500">Connect a social account first, on the Integrations page.</p>
        ) : contentItems.length === 0 ? (
          <p className="text-sm text-ink-500">
            No approved content yet — approve a piece of content in the Content Studio first.
          </p>
        ) : (
          <div className="flex flex-col gap-4">
            <div>
              <label className="mb-1.5 block text-sm font-medium text-ink-700">Content</label>
              <select
                value={selectedContentId}
                onChange={(e) => setSelectedContentId(e.target.value)}
                className="w-full rounded-md border border-ink-200 px-3 py-2 text-sm"
              >
                <option value="">Select content…</option>
                {contentItems.map((c) => (
                  <option key={c.id} value={c.id}>
                    {(c.title || c.body).slice(0, 60)}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="mb-1.5 block text-sm font-medium text-ink-700">Account</label>
              <select
                value={selectedAccountId}
                onChange={(e) => setSelectedAccountId(e.target.value)}
                className="w-full rounded-md border border-ink-200 px-3 py-2 text-sm"
              >
                {connectedAccounts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {SOCIAL_PLATFORM_LABELS[a.platform]}
                    {a.external_account_name ? ` — ${a.external_account_name}` : ""}
                  </option>
                ))}
              </select>
            </div>

            {error && <p className="text-sm text-signal">{error}</p>}

            <Button onClick={handleCreate} disabled={!selectedContentId || !selectedAccountId || isSaving}>
              {isSaving ? "Creating…" : "Create draft"}
            </Button>
            <p className="text-xs text-ink-400">
              This creates a draft — you&apos;ll pick a time (or get an AI recommendation) next.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
