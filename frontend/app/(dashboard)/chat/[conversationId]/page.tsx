"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { getConversation, type ChatMessagePublic } from "@/lib/api";
import { useSession } from "@/lib/session";
import { Header } from "@/components/layout/header";
import { ConversationList } from "@/components/chat/conversation-list";
import { ChatThread } from "@/components/chat/chat-thread";

export default function ConversationPage() {
  const params = useParams<{ conversationId: string }>();
  const { accessToken, activeOrganizationId } = useSession();
  const [messages, setMessages] = useState<ChatMessagePublic[] | null>(null);
  const [title, setTitle] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    if (!accessToken || !activeOrganizationId || !params.conversationId) return;
    setMessages(null);
    setNotFound(false);
    getConversation(accessToken, activeOrganizationId, params.conversationId)
      .then((detail) => {
        setMessages(detail.messages);
        setTitle(detail.title);
      })
      .catch(() => setNotFound(true));
  }, [accessToken, activeOrganizationId, params.conversationId]);

  return (
    <>
      <Header title="AI Assistant" description={title ?? undefined} />
      <div className="flex min-h-0 flex-1">
        <ConversationList />
        <div className="flex-1">
          {notFound ? (
            <div className="flex h-full items-center justify-center">
              <p className="text-sm text-ink-500">Conversation not found.</p>
            </div>
          ) : messages === null ? (
            <div className="flex h-full items-center justify-center">
              <p className="text-sm text-ink-500">Loading…</p>
            </div>
          ) : (
            <ChatThread conversationId={params.conversationId} initialMessages={messages} />
          )}
        </div>
      </div>
    </>
  );
}
