"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, Loader2, Send, Sparkles, X, XCircle } from "lucide-react";
import {
  ApiError,
  acceptRecommendation,
  cancelScheduledPost,
  deleteScheduledPost,
  getContent,
  getScheduledPost,
  publishNow,
  recommendPosting,
  retryFailedPost,
  schedulePost,
  type ContentPublic,
  type ScheduledPostDetail as ScheduledPostDetailType,
} from "@/lib/api";
import { useSession } from "@/lib/session";
import { Button } from "@/components/ui/button";

interface ScheduledPostDrawerProps {
  postId: string;
  accountLabel: (accountId: string) => string;
  onClose: () => void;
  onChanged: () => void;
}

const STATUS_LABELS: Record<string, string> = {
  draft: "Draft",
  scheduled: "Scheduled",
  publishing: "Publishing…",
  published: "Published",
  failed: "Failed",
};

export function ScheduledPostDrawer({ postId, accountLabel, onClose, onChanged }: ScheduledPostDrawerProps) {
  const { accessToken, activeOrganizationId } = useSession();
  const [post, setPost] = useState<ScheduledPostDetailType | null>(null);
  const [content, setContent] = useState<ContentPublic | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isBusy, setIsBusy] = useState(false);
  const [scheduledForInput, setScheduledForInput] = useState("");

  async function load() {
    if (!accessToken || !activeOrganizationId) return;
    const detail = await getScheduledPost(accessToken, activeOrganizationId, postId);
    setPost(detail);
    const contentDetail = await getContent(accessToken, activeOrganizationId, detail.content_id);
    setContent(contentDetail);
    if (detail.scheduled_for) {
      setScheduledForInput(new Date(detail.scheduled_for).toISOString().slice(0, 16));
    }
  }

  useEffect(() => {
    setIsLoading(true);
    load().finally(() => setIsLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [postId]);

  async function withBusy(fn: () => Promise<void>) {
    setError(null);
    setIsBusy(true);
    try {
      await fn();
      await load();
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail ?? "That didn't work") : "That didn't work");
    } finally {
      setIsBusy(false);
    }
  }

  if (!accessToken || !activeOrganizationId) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/20">
      <div className="h-full w-full max-w-md overflow-y-auto bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-base font-semibold text-ink-900">Scheduled post</h2>
          <button onClick={onClose} className="text-ink-400 hover:text-ink-700">
            <X className="h-5 w-5" />
          </button>
        </div>

        {isLoading || !post ? (
          <p className="text-sm text-ink-500">Loading…</p>
        ) : (
          <div className="flex flex-col gap-5">
            <div className="flex items-center gap-2">
              <StatusBadge status={post.status} />
              <span className="text-sm text-ink-500">{accountLabel(post.connected_account_id)}</span>
            </div>

            {content && (
              <div className="rounded-md bg-ink-50 p-3 text-sm text-ink-800 whitespace-pre-wrap">{content.body}</div>
            )}

            {post.status === "failed" && post.publishing_logs.length > 0 && (
              <p className="rounded-md bg-signal-soft px-3 py-2 text-sm text-signal">
                {post.publishing_logs[post.publishing_logs.length - 1]!.error_message}
              </p>
            )}

            {(post.status === "draft" || post.status === "scheduled") && (
              <div>
                <label className="mb-1.5 block text-sm font-medium text-ink-700">Scheduled time</label>
                <div className="flex gap-2">
                  <input
                    type="datetime-local"
                    value={scheduledForInput}
                    onChange={(e) => setScheduledForInput(e.target.value)}
                    className="flex-1 rounded-md border border-ink-200 px-3 py-2 text-sm"
                  />
                  <Button
                    disabled={!scheduledForInput || isBusy}
                    onClick={() =>
                      withBusy(async () => {
                        await schedulePost(
                          accessToken,
                          activeOrganizationId,
                          post.id,
                          new Date(scheduledForInput).toISOString()
                        );
                      })
                    }
                  >
                    Set
                  </Button>
                </div>
              </div>
            )}

            {post.status === "draft" && !post.ai_recommended_platform && (
              <Button
                variant="secondary"
                disabled={isBusy}
                onClick={() =>
                  withBusy(async () => {
                    await recommendPosting(accessToken, activeOrganizationId, post.id);
                  })
                }
                className="gap-1.5"
              >
                {isBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                Get AI recommendation
              </Button>
            )}

            {post.ai_recommended_platform && (
              <div className="rounded-md border border-ink-100 p-3">
                <div className="mb-1.5 flex items-center gap-1.5">
                  <Sparkles className="h-3.5 w-3.5 text-ink-400" />
                  <p className="text-xs font-semibold uppercase tracking-wide text-ink-500">
                    AI prediction — not a guarantee
                  </p>
                </div>
                <p className="text-sm text-ink-800">{post.ai_recommendation_rationale}</p>
                {post.ai_recommended_hashtags && (
                  <p className="mt-1.5 text-xs text-ink-500">{post.ai_recommended_hashtags.join(" ")}</p>
                )}
                {post.status === "draft" && (
                  <Button
                    variant="secondary"
                    disabled={isBusy}
                    onClick={() =>
                      withBusy(async () => {
                        await acceptRecommendation(accessToken, activeOrganizationId, post.id);
                      })
                    }
                    className="mt-2"
                  >
                    Use this time
                  </Button>
                )}
              </div>
            )}

            {error && <p className="text-sm text-signal">{error}</p>}

            <div className="flex flex-wrap gap-2 border-t border-ink-100 pt-4">
              {(post.status === "draft" || post.status === "scheduled") && (
                <Button
                  disabled={isBusy}
                  onClick={() =>
                    withBusy(async () => {
                      await publishNow(accessToken, activeOrganizationId, post.id);
                    })
                  }
                  className="gap-1.5"
                >
                  <Send className="h-4 w-4" />
                  Publish now
                </Button>
              )}
              {post.status === "failed" && (
                <Button
                  disabled={isBusy}
                  onClick={() =>
                    withBusy(async () => {
                      await retryFailedPost(accessToken, activeOrganizationId, post.id);
                    })
                  }
                  className="gap-1.5"
                >
                  <Send className="h-4 w-4" />
                  Retry
                </Button>
              )}
              {post.status === "scheduled" && (
                <Button
                  variant="secondary"
                  disabled={isBusy}
                  onClick={() =>
                    withBusy(async () => {
                      await cancelScheduledPost(accessToken, activeOrganizationId, post.id);
                    })
                  }
                >
                  Move back to draft
                </Button>
              )}
              {post.status !== "published" && (
                <button
                  disabled={isBusy}
                  onClick={() =>
                    withBusy(async () => {
                      await deleteScheduledPost(accessToken, activeOrganizationId, post.id);
                      onClose();
                    })
                  }
                  className="ml-auto text-sm text-ink-400 hover:text-signal"
                >
                  Delete
                </button>
              )}
            </div>

            {post.external_post_url && (
              <a
                href={post.external_post_url}
                target="_blank"
                rel="noreferrer"
                className="text-sm font-medium text-ink-900 underline"
              >
                View published post
              </a>
            )}

            {post.publishing_logs.length > 0 && (
              <div>
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-400">Publishing log</p>
                <div className="flex flex-col gap-1.5">
                  {post.publishing_logs.map((log) => (
                    <div key={log.id} className="flex items-start gap-2 text-xs">
                      {log.outcome === "success" ? (
                        <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-positive" />
                      ) : (
                        <XCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-signal" />
                      )}
                      <div>
                        <p className="text-ink-700">
                          Attempt {log.attempt_number} — {log.request_summary}
                        </p>
                        {log.error_message && <p className="text-ink-400">{log.error_message}</p>}
                        <p className="text-ink-300">{new Date(log.created_at).toLocaleString()}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    draft: "bg-ink-100 text-ink-600",
    scheduled: "bg-ink-900 text-white",
    publishing: "bg-signal-soft text-signal",
    published: "bg-positive-soft text-positive",
    failed: "bg-signal-soft text-signal",
  };
  return (
    <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${styles[status] ?? ""}`}>
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}
