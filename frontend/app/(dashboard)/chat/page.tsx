"use client";

import { useRouter } from "next/navigation";
import { Header } from "@/components/layout/header";
import { ConversationList } from "@/components/chat/conversation-list";
import { ChatThread } from "@/components/chat/chat-thread";

export default function ChatPage() {
  const router = useRouter();

  return (
    <>
      <Header title="AI Assistant" description="Ask about strategy, audience, or campaigns" />
      <div className="flex min-h-0 flex-1">
        <ConversationList />
        <div className="flex-1">
          <ChatThread
            conversationId={null}
            initialMessages={[]}
            onConversationCreated={(id) => router.push(`/chat/${id}`)}
          />
        </div>
      </div>
    </>
  );
}
