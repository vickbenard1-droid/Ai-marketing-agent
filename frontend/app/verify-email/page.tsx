"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { CheckCircle2, XCircle } from "lucide-react";
import { ApiError, verifyEmail } from "@/lib/api";
import { useSession } from "@/lib/session";

function VerifyEmailContent() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token");
  const { accessToken, refreshUser } = useSession();

  const [status, setStatus] = useState<"pending" | "success" | "error">("pending");
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    if (!token) {
      setStatus("error");
      setErrorMessage("This verification link is missing its token.");
      return;
    }

    verifyEmail(token)
      .then(async () => {
        setStatus("success");
        // If the person is signed in on this device, refresh their user
        // record so is_email_verified flips without needing a reload.
        if (accessToken) {
          await refreshUser();
        }
      })
      .catch((err) => {
        setStatus("error");
        setErrorMessage(
          err instanceof ApiError ? String(err.detail ?? "Verification failed") : "Verification failed"
        );
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-ink-50 px-4">
      <div className="w-full max-w-sm rounded-lg border border-ink-100 bg-white p-8 text-center shadow-panel">
        {status === "pending" && <p className="text-sm text-ink-500">Verifying your email…</p>}

        {status === "success" && (
          <>
            <CheckCircle2 className="mx-auto mb-3 h-10 w-10 text-positive" />
            <h1 className="mb-1 text-lg font-semibold text-ink-900">Email verified</h1>
            <p className="mb-6 text-sm text-ink-500">Your email address has been confirmed.</p>
            <Link
              href={accessToken ? "/dashboard" : "/login"}
              className="text-sm font-medium text-ink-900 hover:underline"
            >
              {accessToken ? "Go to dashboard" : "Sign in"}
            </Link>
          </>
        )}

        {status === "error" && (
          <>
            <XCircle className="mx-auto mb-3 h-10 w-10 text-signal" />
            <h1 className="mb-1 text-lg font-semibold text-ink-900">Verification failed</h1>
            <p className="mb-6 text-sm text-ink-500">{errorMessage}</p>
            <Link href="/login" className="text-sm font-medium text-ink-900 hover:underline">
              Back to sign in
            </Link>
          </>
        )}
      </div>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-ink-50">
          <p className="text-sm text-ink-500">Loading…</p>
        </div>
      }
    >
      <VerifyEmailContent />
    </Suspense>
  );
}
