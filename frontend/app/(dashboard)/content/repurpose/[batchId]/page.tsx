"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { getRepurposeBatch, type ContentPublic, type ContentType } from "@/lib/api";
import { useSession } from "@/lib/session";
import { Header } from "@/components/layout/header";

const GROUP_LABELS: Partial<Record<ContentType, string>> = {
  facebook_post: "Social posts",
  instagram_caption: "Social posts",
  linkedin_post: "Social posts",
  x_post: "Social posts",
  tiktok_caption: "Social posts",
  video_script: "Video scripts",
  blog_post: "Blog article",
  email: "Email",
  hook: "Hooks",
};

const GROUP_ORDER = ["Social posts", "Video scripts", "Blog article", "Email", "Hooks"];

export default function RepurposeBatchPage() {
  const params = useParams<{ batchId: string }>();
  const { accessToken, activeOrganizationId } = useSession();
  const [items, setItems] = useState<ContentPublic[] | null>(null);

  useEffect(() => {
    if (!accessToken || !activeOrganizationId) return;
    getRepurposeBatch(accessToken, activeOrganizationId, params.batchId).then((batch) => setItems(batch.items));
  }, [accessToken, activeOrganizationId, params.batchId]);

  if (!items) {
    return (
      <>
        <Header title="Repurposed content" />
        <main className="flex-1 p-6">
          <p className="text-sm text-ink-500">Loading…</p>
        </main>
      </>
    );
  }

  const grouped = new Map<string, ContentPublic[]>();
  for (const item of items) {
    const group = GROUP_LABELS[item.content_type] ?? "Other";
    grouped.set(group, [...(grouped.get(group) ?? []), item]);
  }

  return (
    <>
      <Header title="Repurposed content" description={`${items.length} items generated`} />
      <main className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-3xl space-y-6">
          {GROUP_ORDER.filter((g) => grouped.has(g)).map((group) => (
            <div key={group} className="rounded-lg border border-ink-100 bg-white p-6 shadow-panel">
              <h2 className="mb-3 text-sm font-semibold text-ink-900">{group}</h2>
              <div className="flex flex-col gap-2">
                {grouped.get(group)!.map((item) => (
                  <Link
                    key={item.id}
                    href={`/content/${item.id}`}
                    className="rounded-md border border-ink-100 p-3 text-sm text-ink-800 hover:border-ink-300"
                  >
                    {item.title && <p className="mb-1 font-medium text-ink-900">{item.title}</p>}
                    <p className="line-clamp-2">{item.body}</p>
                  </Link>
                ))}
              </div>
            </div>
          ))}
        </div>
      </main>
    </>
  );
}
