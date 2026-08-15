"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "@/lib/session";

export default function RootPage() {
  const { accessToken, isLoading } = useSession();
  const router = useRouter();

  useEffect(() => {
    if (isLoading) return;
    router.replace(accessToken ? "/dashboard" : "/login");
  }, [accessToken, isLoading, router]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-ink-50">
      <p className="text-sm text-ink-400">Loading…</p>
    </div>
  );
}
