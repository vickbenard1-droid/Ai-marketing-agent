"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ApiError, registerAccount } from "@/lib/api";
import { useSession } from "@/lib/session";
import { Button } from "@/components/ui/button";
import { FieldDark } from "@/components/ui/field-dark";

export default function RegisterPage() {
  const router = useRouter();
  const { setSession } = useSession();
  const [fullName, setFullName] = useState("");
  const [organizationName, setOrganizationName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      const tokens = await registerAccount({
        email,
        password,
        full_name: fullName,
        organization_name: organizationName,
      });
      await setSession(tokens);
      router.push("/onboarding");
    } catch (err) {
      setError(
        err instanceof ApiError ? String(err.detail ?? "Could not create account") : "Could not create account"
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div>
      <h1 className="mb-1 text-lg font-semibold text-white">Create your account</h1>
      <p className="mb-6 text-sm text-ink-400">
        We&apos;ll set up your first organization automatically.
      </p>

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <FieldDark
          label="Full name"
          autoComplete="name"
          required
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
        />
        <FieldDark
          label="Organization name"
          placeholder="e.g. Acme Marketing"
          required
          value={organizationName}
          onChange={(e) => setOrganizationName(e.target.value)}
        />
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
          autoComplete="new-password"
          required
          minLength={8}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />

        {error && (
          <p role="alert" className="text-sm text-signal">
            {error}
          </p>
        )}

        <Button type="submit" disabled={isSubmitting} className="mt-2 w-full justify-center">
          {isSubmitting ? "Creating account…" : "Create account"}
        </Button>
      </form>

      <p className="mt-6 text-center text-sm text-ink-400">
        Already have an account?{" "}
        <Link href="/login" className="font-medium text-ink-100 hover:underline">
          Sign in
        </Link>
      </p>
    </div>
  );
}
