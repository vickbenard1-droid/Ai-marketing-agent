"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "@/lib/session";

export default function OnboardingLayout({ children }: { children: React.ReactNode }) {
  const { accessToken, isLoading } = useSession();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !accessToken) {
      router.replace("/login");
    }
  }, [accessToken, isLoading, router]);

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-ink-50">
        <p className="text-sm text-ink-400">Loading…</p>
      </div>
    );
  }

  if (!accessToken) {
    return null;
  }

  return (
    <div className="min-h-screen bg-ink-50">
      <header className="border-b border-ink-100 bg-white px-6 py-4">
        <div className="mx-auto flex max-w-2xl items-center gap-2.5">
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-signal font-mono text-xs font-semibold text-white">
            A
          </div>
          <span className="text-sm font-medium tracking-wide text-ink-900">AI MARKETING AGENT</span>
        </div>
      </header>
      <main className="mx-auto max-w-2xl px-6 py-10">{children}</main>
    </div>
  );
}
