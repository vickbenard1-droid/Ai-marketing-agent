"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ChevronLeft, ChevronRight, Plus } from "lucide-react";
import {
  ApiError,
  SOCIAL_PLATFORM_LABELS,
  listConnectedAccounts,
  listContent,
  listScheduledPosts,
  type ConnectedAccountPublic,
  type ContentPublic,
  type ScheduledPostPublic,
} from "@/lib/api";
import { useSession } from "@/lib/session";
import { Header } from "@/components/layout/header";
import { Button } from "@/components/ui/button";
import { NewScheduledPostModal } from "@/components/schedule/new-scheduled-post-modal";
import { ScheduledPostDrawer } from "@/components/schedule/scheduled-post-drawer";

const STATUS_DOT: Record<string, string> = {
  draft: "bg-ink-300",
  scheduled: "bg-ink-900",
  publishing: "bg-signal",
  published: "bg-positive",
  failed: "bg-signal",
};

function startOfMonth(d: Date) {
  return new Date(d.getFullYear(), d.getMonth(), 1);
}
function startOfCalendarGrid(d: Date) {
  const first = startOfMonth(d);
  const day = first.getDay();
  const start = new Date(first);
  start.setDate(first.getDate() - day);
  return start;
}
function addDays(d: Date, n: number) {
  const copy = new Date(d);
  copy.setDate(copy.getDate() + n);
  return copy;
}
function sameDay(a: Date, b: Date) {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}
function monthLabel(d: Date) {
  return d.toLocaleDateString(undefined, { month: "long", year: "numeric" });
}

export default function SchedulePage() {
  const { accessToken, activeOrganizationId } = useSession();
  const [monthCursor, setMonthCursor] = useState(() => startOfMonth(new Date()));
  const [posts, setPosts] = useState<ScheduledPostPublic[]>([]);
  const [content, setContent] = useState<Record<string, ContentPublic>>({});
  const [accounts, setAccounts] = useState<ConnectedAccountPublic[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isNewPostOpen, setIsNewPostOpen] = useState(false);
  const [selectedPostId, setSelectedPostId] = useState<string | null>(null);

  const gridStart = useMemo(() => startOfCalendarGrid(monthCursor), [monthCursor]);
  const gridDays = useMemo(() => Array.from({ length: 42 }, (_, i) => addDays(gridStart, i)), [gridStart]);

  async function load() {
    if (!accessToken || !activeOrganizationId) return;
    const rangeStart = gridDays[0]!;
    const rangeEnd = gridDays[gridDays.length - 1]!;
    const [postList, accountList] = await Promise.all([
      listScheduledPosts(accessToken, activeOrganizationId, {
        start: rangeStart.toISOString(),
        end: rangeEnd.toISOString(),
      }),
      listConnectedAccounts(accessToken, activeOrganizationId),
    ]);
    setPosts(postList);
    setAccounts(accountList);

    const missingIds = [...new Set(postList.map((p) => p.content_id))].filter((id) => !content[id]);
    if (missingIds.length > 0) {
      const items = await listContent(accessToken, activeOrganizationId);
      const map: Record<string, ContentPublic> = {};
      for (const c of items) map[c.id] = c;
      setContent((prev) => ({ ...prev, ...map }));
    }
  }

  useEffect(() => {
    if (!accessToken || !activeOrganizationId) return;
    setIsLoading(true);
    setError(null);
    load()
      .catch((err) =>
        setError(err instanceof ApiError ? String(err.detail ?? "Couldn't load calendar") : "Couldn't load calendar")
      )
      .finally(() => setIsLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken, activeOrganizationId, monthCursor]);

  const postsByDay = useMemo(() => {
    const map = new Map<string, ScheduledPostPublic[]>();
    for (const post of posts) {
      const dateStr = post.scheduled_for ?? post.created_at;
      const key = new Date(dateStr).toDateString();
      map.set(key, [...(map.get(key) ?? []), post]);
    }
    return map;
  }, [posts]);

  const today = new Date();

  return (
    <>
      <Header title="Content Calendar" description="Scheduled, draft, published, and failed posts" />
      <main className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-5xl">
          <div className="mb-4 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <button
                onClick={() => setMonthCursor((d) => new Date(d.getFullYear(), d.getMonth() - 1, 1))}
                className="rounded-md p-1.5 text-ink-500 hover:bg-ink-100"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <h2 className="w-40 text-center text-sm font-semibold text-ink-900">{monthLabel(monthCursor)}</h2>
              <button
                onClick={() => setMonthCursor((d) => new Date(d.getFullYear(), d.getMonth() + 1, 1))}
                className="rounded-md p-1.5 text-ink-500 hover:bg-ink-100"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
            <div className="flex items-center gap-3">
              <Legend />
              <Button onClick={() => setIsNewPostOpen(true)} className="gap-1.5">
                <Plus className="h-4 w-4" />
                Schedule post
              </Button>
            </div>
          </div>

          {error && <p className="mb-4 text-sm text-signal">{error}</p>}

          {accounts.length === 0 && !isLoading && (
            <div className="mb-4 rounded-md border border-dashed border-ink-200 bg-white p-4 text-sm text-ink-500">
              Connect a social account on the{" "}
              <Link href="/integrations" className="font-medium text-ink-900 underline">
                Integrations
              </Link>{" "}
              page before scheduling posts.
            </div>
          )}

          <div className="grid grid-cols-7 gap-px overflow-hidden rounded-lg border border-ink-100 bg-ink-100">
            {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((d) => (
              <div key={d} className="bg-ink-50 px-2 py-1.5 text-center text-xs font-medium text-ink-500">
                {d}
              </div>
            ))}
            {gridDays.map((day) => {
              const dayPosts = postsByDay.get(day.toDateString()) ?? [];
              const isCurrentMonth = day.getMonth() === monthCursor.getMonth();
              const isToday = sameDay(day, today);
              return (
                <div
                  key={day.toISOString()}
                  className={`min-h-[92px] bg-white p-1.5 ${isCurrentMonth ? "" : "bg-ink-50/50"}`}
                >
                  <p
                    className={`mb-1 text-xs ${
                      isToday
                        ? "inline-flex h-5 w-5 items-center justify-center rounded-full bg-ink-900 font-semibold text-white"
                        : isCurrentMonth
                          ? "text-ink-500"
                          : "text-ink-300"
                    }`}
                  >
                    {day.getDate()}
                  </p>
                  <div className="flex flex-col gap-0.5">
                    {dayPosts.slice(0, 3).map((post) => (
                      <button
                        key={post.id}
                        onClick={() => setSelectedPostId(post.id)}
                        className="flex w-full items-center gap-1 rounded-sm px-1 py-0.5 text-left text-[11px] text-ink-700 hover:bg-ink-50"
                      >
                        <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${STATUS_DOT[post.status]}`} />
                        <span className="truncate">
                          {content[post.content_id]?.title || content[post.content_id]?.body || "…"}
                        </span>
                      </button>
                    ))}
                    {dayPosts.length > 3 && (
                      <p className="px-1 text-[10px] text-ink-400">+{dayPosts.length - 3} more</p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </main>

      {isNewPostOpen && (
        <NewScheduledPostModal
          accounts={accounts}
          onClose={() => setIsNewPostOpen(false)}
          onCreated={() => {
            setIsNewPostOpen(false);
            load();
          }}
        />
      )}

      {selectedPostId && (
        <ScheduledPostDrawer
          postId={selectedPostId}
          accountLabel={(accountId) => {
            const acc = accounts.find((a) => a.id === accountId);
            return acc ? SOCIAL_PLATFORM_LABELS[acc.platform] : "";
          }}
          onClose={() => setSelectedPostId(null)}
          onChanged={load}
        />
      )}
    </>
  );
}

function Legend() {
  return (
    <div className="hidden items-center gap-3 text-xs text-ink-500 sm:flex">
      {Object.entries(STATUS_DOT).map(([status, dot]) => (
        <span key={status} className="flex items-center gap-1">
          <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />
          {status}
        </span>
      ))}
    </div>
  );
}
