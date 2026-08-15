"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Send, Sparkles } from "lucide-react";
import { ApiError, sendChatMessage, type ChatMessagePublic } from "@/lib/api";
import { useSession } from "@/lib/session";
import { Button } from "@/components/ui/button";

const SUGGESTED_PROMPTS = [
  "How should I market my business?",
  "Who is my best customer?",
  "Why might my ads not be converting?",
  "What should I post today?",
];

interface ChatThreadProps {
  conversationId: string | null;
  initialMessages: ChatMessagePublic[];
  onConversationCreated?: (conversationId: string) => void;
}

export function ChatThread({ conversationId, initialMessages, onConversationCreated }: ChatThreadProps) {
  const { accessToken, activeOrganizationId } = useSession();
  const router = useRouter();

  const [messages, setMessages] = useState<ChatMessagePublic[]>(initialMessages);
  const [draft, setDraft] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setMessages(initialMessages);
  }, [initialMessages]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSend(text?: string) {
    const content = (text ?? draft).trim();
    if (!content || !accessToken || !activeOrganizationId) return;

    setError(null);
    setIsSending(true);
    setDraft("");

    // Optimistic append of the user's own message — the server response
    // only returns the assistant's reply, not an echo of what was sent.
    const optimisticUserMessage: ChatMessagePublic = {
      id: `optimistic-${Date.now()}`,
      role: "user",
      content,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, optimisticUserMessage]);

    try {
      const result = await sendChatMessage(accessToken, activeOrganizationId, {
        message: content,
        conversation_id: conversationId,
      });
      setMessages((prev) => [...prev, result.message]);

      if (!conversationId && onConversationCreated) {
        onConversationCreated(result.conversation_id);
      } else if (!conversationId) {
        router.push(`/chat/${result.conversation_id}`);
      }
    } catch (err) {
      setError(
        err instanceof ApiError
          ? String(err.detail ?? "Couldn't send that — try again")
          : "Couldn't send that — try again"
      );
      // Remove the optimistic message on failure so the thread doesn't
      // show a message that was never actually saved.
      setMessages((prev) => prev.filter((m) => m.id !== optimisticUserMessage.id));
    } finally {
      setIsSending(false);
    }
  }

  const isEmpty = messages.length === 0;

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 overflow-y-auto px-6 py-6">
        {isEmpty ? (
          <div className="mx-auto flex h-full max-w-lg flex-col items-center justify-center text-center">
            <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-ink-900">
              <Sparkles className="h-5 w-5 text-white" />
            </div>
            <h2 className="mb-1 text-base font-semibold text-ink-900">AI Marketing Assistant</h2>
            <p className="mb-6 text-sm text-ink-500">
              Ask about strategy, audience, campaigns, or content — grounded in your business.
            </p>
            <div className="flex w-full flex-col gap-2">
              {SUGGESTED_PROMPTS.map((prompt) => (
                <button
                  key={prompt}
                  onClick={() => handleSend(prompt)}
                  className="rounded-md border border-ink-200 bg-white px-4 py-2.5 text-left text-sm text-ink-700 hover:border-ink-400"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="mx-auto flex max-w-2xl flex-col gap-4">
            {messages.map((m) => (
              <div
                key={m.id}
                className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[85%] whitespace-pre-wrap rounded-lg px-4 py-2.5 text-sm ${
                    m.role === "user"
                      ? "bg-ink-900 text-white"
                      : "border border-ink-100 bg-white text-ink-900"
                  }`}
                >
                  {m.content}
                </div>
              </div>
            ))}
            {isSending && (
              <div className="flex justify-start">
                <div className="rounded-lg border border-ink-100 bg-white px-4 py-2.5 text-sm text-ink-400">
                  Thinking…
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      <div className="border-t border-ink-100 bg-white px-6 py-4">
        <div className="mx-auto flex max-w-2xl items-end gap-2">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="Ask about your marketing…"
            rows={1}
            className="flex-1 resize-none rounded-md border border-ink-200 bg-white px-3 py-2 text-sm text-ink-900 focus:border-ink-500"
          />
          <Button onClick={() => handleSend()} disabled={isSending || !draft.trim()} className="shrink-0">
            <Send className="h-4 w-4" />
          </Button>
        </div>
        {error && (
          <p role="alert" className="mx-auto mt-2 max-w-2xl text-sm text-signal">
            {error}
          </p>
        )}
        <p className="mx-auto mt-2 max-w-2xl text-xs text-ink-400">
          The assistant can prepare recommendations, campaigns, and content for your review — it
          can&apos;t spend money, publish, or launch anything on its own.
        </p>
      </div>
    </div>
  );
}
