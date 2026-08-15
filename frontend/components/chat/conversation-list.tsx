"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Plus, MessageSquare } from "lucide-react";
import { listConversations, type ConversationPublic } from "@/lib/api";
import { useSession } from "@/lib/session";
import { cn } from "@/lib/utils";

export function ConversationList() {
  const { accessToken, activeOrganizationId } = useSession();
  const pathname = usePathname();
  const [conversations, setConversations] = useState<ConversationPublic[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!accessToken || !activeOrganizationId) return;
    listConversations(accessToken, activeOrganizationId)
      .then(setConversations)
      .finally(() => setIsLoading(false));
    // Re-fetch whenever the route changes (e.g. after sending a first
    // message creates a new conversation) so the list stays current.
  }, [accessToken, activeOrganizationId, pathname]);

  return (
    <aside className="flex w-64 shrink-0 flex-col border-r border-ink-100 bg-white">
      <div className="p-3">
        <Link
          href="/chat"
          className="flex items-center gap-2 rounded-md border border-ink-200 px-3 py-2 text-sm font-medium text-ink-700 hover:border-ink-400"
        >
          <Plus className="h-4 w-4" />
          New conversation
        </Link>
      </div>
      <div className="flex-1 overflow-y-auto px-2 pb-3">
        {isLoading ? (
          <p className="px-2 py-2 text-sm text-ink-400">Loading…</p>
        ) : conversations.length === 0 ? (
          <p className="px-2 py-2 text-sm text-ink-400">No conversations yet.</p>
        ) : (
          <div className="flex flex-col gap-0.5">
            {conversations.map((c) => {
              const isActive = pathname === `/chat/${c.id}`;
              return (
                <Link
                  key={c.id}
                  href={`/chat/${c.id}`}
                  className={cn(
                    "flex items-center gap-2 rounded-md px-2.5 py-2 text-sm truncate",
                    isActive ? "bg-ink-50 text-ink-900 font-medium" : "text-ink-600 hover:bg-ink-50"
                  )}
                >
                  <MessageSquare className="h-3.5 w-3.5 shrink-0 text-ink-400" />
                  <span className="truncate">{c.title ?? "Untitled"}</span>
                </Link>
              );
            })}
          </div>
        )}
      </div>
    </aside>
  );
}
