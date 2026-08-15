"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "@/lib/session";
import { Sidebar } from "@/components/layout/sidebar";

export default function DashboardGroupLayout({ children }: { children: React.ReactNode }) {
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
    // Redirect effect above will fire; render nothing in the meantime.
    return null;
  }

  return (
    <div className="flex h-screen overflow-hidden bg-ink-50">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">{children}</div>
    </div>
  );
}
