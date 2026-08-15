"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ApiError, login } from "@/lib/api";
import { useSession } from "@/lib/session";
import { Button } from "@/components/ui/button";
import { FieldDark } from "@/components/ui/field-dark";

export default function LoginPage() {
  const router = useRouter();
  const { setSession } = useSession();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      const tokens = await login({ email, password });
      await setSession(tokens);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail ?? "Login failed") : "Login failed");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div>
      <h1 className="mb-1 text-lg font-semibold text-white">Welcome back</h1>
      <p className="mb-6 text-sm text-ink-400">Sign in to your account.</p>

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <FieldDark
          label="Email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <FieldDark
          label="Password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />

        <div className="-mt-2 text-right">
          <Link href="/forgot-password" className="text-sm text-ink-400 hover:text-ink-200 hover:underline">
            Forgot password?
          </Link>
        </div>

        {error && (
          <p role="alert" className="text-sm text-signal">
            {error}
          </p>
        )}

        <Button type="submit" disabled={isSubmitting} className="mt-2 w-full justify-center">
          {isSubmitting ? "Signing in…" : "Sign in"}
        </Button>
      </form>

      <p className="mt-6 text-center text-sm text-ink-400">
        Don&apos;t have an account?{" "}
        <Link href="/register" className="font-medium text-ink-100 hover:underline">
          Create one
        </Link>
      </p>
    </div>
  );
}
