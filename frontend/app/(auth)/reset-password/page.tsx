"use client";

import { Suspense, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ApiError, resetPassword } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { FieldDark } from "@/components/ui/field-dark";

function ResetPasswordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token");

  const [newPassword, setNewPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!token) return;
    setError(null);
    setIsSubmitting(true);
    try {
      await resetPassword(token, newPassword);
      setDone(true);
      setTimeout(() => router.push("/login"), 2000);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? String(err.detail ?? "This link is invalid or has expired")
          : "This link is invalid or has expired"
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  if (!token) {
    return (
      <div>
        <h1 className="mb-1 text-lg font-semibold text-white">Invalid link</h1>
        <p className="mb-6 text-sm text-ink-400">
          This password reset link is missing its token. Request a new one below.
        </p>
        <Link href="/forgot-password" className="text-sm font-medium text-ink-100 hover:underline">
          Request a new link
        </Link>
      </div>
    );
  }

  if (done) {
    return (
      <div>
        <h1 className="mb-1 text-lg font-semibold text-white">Password reset</h1>
        <p className="text-sm text-ink-400">Redirecting you to sign in…</p>
      </div>
    );
  }

  return (
    <div>
      <h1 className="mb-1 text-lg font-semibold text-white">Set a new password</h1>
      <p className="mb-6 text-sm text-ink-400">Choose a new password for your account.</p>

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <FieldDark
          label="New password"
          type="password"
          autoComplete="new-password"
          required
          minLength={8}
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
        />

        {error && (
          <p role="alert" className="text-sm text-signal">
            {error}
          </p>
        )}

        <Button type="submit" disabled={isSubmitting} className="mt-2 w-full justify-center">
          {isSubmitting ? "Resetting…" : "Reset password"}
        </Button>
      </form>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<p className="text-sm text-ink-400">Loading…</p>}>
      <ResetPasswordForm />
    </Suspense>
  );
}
