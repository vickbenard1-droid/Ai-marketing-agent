"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { ApiError, forgotPassword } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { FieldDark } from "@/components/ui/field-dark";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await forgotPassword(email);
      // Always show the same success state regardless of whether the
      // email exists — the backend deliberately returns an identical
      // response either way (see auth/service.py::request_password_reset).
      setSubmitted(true);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail ?? "Something went wrong") : "Something went wrong");
    } finally {
      setIsSubmitting(false);
    }
  }

  if (submitted) {
    return (
      <div>
        <h1 className="mb-1 text-lg font-semibold text-white">Check your email</h1>
        <p className="mb-6 text-sm text-ink-400">
          If an account exists for <span className="text-ink-200">{email}</span>, we&apos;ve sent a
          link to reset your password. It expires in 30 minutes.
        </p>
        <Link href="/login" className="text-sm font-medium text-ink-100 hover:underline">
          Back to sign in
        </Link>
      </div>
    );
  }

  return (
    <div>
      <h1 className="mb-1 text-lg font-semibold text-white">Reset your password</h1>
      <p className="mb-6 text-sm text-ink-400">
        Enter your email and we&apos;ll send you a link to reset your password.
      </p>

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <FieldDark
          label="Email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />

        {error && (
          <p role="alert" className="text-sm text-signal">
            {error}
          </p>
        )}

        <Button type="submit" disabled={isSubmitting} className="mt-2 w-full justify-center">
          {isSubmitting ? "Sending…" : "Send reset link"}
        </Button>
      </form>

      <p className="mt-6 text-center text-sm text-ink-400">
        <Link href="/login" className="font-medium text-ink-100 hover:underline">
          Back to sign in
        </Link>
      </p>
    </div>
  );
}
