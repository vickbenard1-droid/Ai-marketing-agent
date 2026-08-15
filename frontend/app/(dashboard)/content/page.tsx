"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { FileText, Plus, Search, Sparkles } from "lucide-react";
import {
  CONTENT_TYPE_OPTIONS,
  listContent,
  type ContentPublic,
  type ContentStatus,
  type ContentType,
} from "@/lib/api";
import { useSession } from "@/lib/session";
import { Header } from "@/components/layout/header";
import { Button } from "@/components/ui/button";

const STATUS_TABS: { value: ContentStatus | "all"; label: string }[] = [
  { value: "all", label: "All" },
  { value: "draft", label: "Drafts" },
  { value: "approved", label: "Approved" },
];

const CONTENT_TYPE_LABELS: Record<ContentType, string> = Object.fromEntries(
  CONTENT_TYPE_OPTIONS.map((o) => [o.value, o.label])
) as Record<ContentType, string>;
CONTENT_TYPE_LABELS.video_script = "Video script";
CONTENT_TYPE_LABELS.hook = "Hook";

export default function ContentLibraryPage() {
  const { accessToken, activeOrganizationId } = useSession();
  const [items, setItems] = useState<ContentPublic[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [statusTab, setStatusTab] = useState<ContentStatus | "all">("all");
  const [typeFilter, setTypeFilter] = useState<ContentType | "">("");
  const [search, setSearch] = useState("");

  useEffect(() => {
    if (!accessToken || !activeOrganizationId) return;
    setIsLoading(true);
    const timeout = setTimeout(() => {
      listContent(accessToken, activeOrganizationId, {
        status: statusTab === "all" ? undefined : statusTab,
        content_type: typeFilter || undefined,
        search: search || undefined,
      })
        .then(setItems)
        .finally(() => setIsLoading(false));
    }, 250); // debounce search-as-you-type
    return () => clearTimeout(timeout);
  }, [accessToken, activeOrganizationId, statusTab, typeFilter, search]);

  return (
    <>
      <Header title="Content Studio" description="Generate, review, and manage marketing content" />
      <main className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-4xl">
          <div className="mb-6 flex items-center justify-between gap-3">
            <div className="flex gap-2">
              {STATUS_TABS.map((tab) => (
                <button
                  key={tab.value}
                  onClick={() => setStatusTab(tab.value)}
                  className={`rounded-full px-3.5 py-1.5 text-sm font-medium ${
                    statusTab === tab.value ? "bg-ink-900 text-white" : "bg-white text-ink-600 border border-ink-200"
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
            <div className="flex gap-2">
              <Link href="/content/repurpose">
                <Button variant="secondary" className="gap-1.5">
                  <Sparkles className="h-4 w-4" />
                  Repurpose
                </Button>
              </Link>
              <Link href="/content/new">
                <Button className="gap-1.5">
                  <Plus className="h-4 w-4" />
                  New content
                </Button>
              </Link>
            </div>
          </div>

          <div className="mb-4 flex gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search content…"
                className="w-full rounded-md border border-ink-200 bg-white py-2 pl-9 pr-3 text-sm text-ink-900 focus:border-ink-500"
              />
            </div>
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value as ContentType | "")}
              className="rounded-md border border-ink-200 bg-white px-3 py-2 text-sm text-ink-700"
            >
              <option value="">All types</option>
              {CONTENT_TYPE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>

          {isLoading ? (
            <p className="text-sm text-ink-500">Loading…</p>
          ) : items.length === 0 ? (
            <div className="rounded-lg border border-dashed border-ink-200 bg-white p-10 text-center">
              <FileText className="mx-auto mb-3 h-8 w-8 text-ink-300" />
              <p className="mb-1 text-sm font-medium text-ink-900">No content yet</p>
              <p className="mb-4 text-sm text-ink-500">
                Generate a single piece of content or repurpose something you already have.
              </p>
              <Link href="/content/new">
                <Button>Generate content</Button>
              </Link>
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              {items.map((item) => (
                <Link
                  key={item.id}
                  href={`/content/${item.id}`}
                  className="flex items-start justify-between gap-3 rounded-lg border border-ink-100 bg-white p-4 shadow-panel hover:border-ink-300"
                >
                  <div className="min-w-0">
                    <div className="mb-1 flex items-center gap-2">
                      <span className="rounded-sm bg-ink-50 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-ink-500">
                        {CONTENT_TYPE_LABELS[item.content_type] ?? item.content_type}
                      </span>
                      {item.status === "approved" && (
                        <span className="rounded-full bg-positive-soft px-2 py-0.5 text-[10px] font-medium text-positive">
                          Approved
                        </span>
                      )}
                    </div>
                    <p className="truncate text-sm text-ink-800">{item.title || item.body}</p>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </main>
    </>
  );
}
