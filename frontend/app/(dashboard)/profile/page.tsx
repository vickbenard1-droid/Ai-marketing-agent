"use client";

import { useState, type FormEvent } from "react";
import { ApiError, changeMyPassword, updateMyProfile } from "@/lib/api";
import { useSession } from "@/lib/session";
import { Header } from "@/components/layout/header";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";

const TIMEZONE_OPTIONS = [
  "America/New_York",
  "America/Chicago",
  "America/Denver",
  "America/Los_Angeles",
  "Europe/London",
  "Europe/Paris",
  "Europe/Berlin",
  "Asia/Tokyo",
  "Asia/Shanghai",
  "Asia/Kolkata",
  "Australia/Sydney",
  "UTC",
];

export default function ProfilePage() {
  const { user, accessToken, refreshUser } = useSession();

  const [fullName, setFullName] = useState(user?.full_name ?? "");
  const [phone, setPhone] = useState(user?.phone ?? "");
  const [timezone, setTimezone] = useState(user?.timezone ?? "");
  const [profileError, setProfileError] = useState<string | null>(null);
  const [profileSaved, setProfileSaved] = useState(false);
  const [isSavingProfile, setIsSavingProfile] = useState(false);

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordSaved, setPasswordSaved] = useState(false);
  const [isSavingPassword, setIsSavingPassword] = useState(false);

  if (!user || !accessToken) return null;

  async function handleProfileSubmit(event: FormEvent) {
    event.preventDefault();
    setProfileError(null);
    setProfileSaved(false);
    setIsSavingProfile(true);
    try {
      await updateMyProfile(accessToken!, { full_name: fullName, phone, timezone });
      await refreshUser();
      setProfileSaved(true);
    } catch (err) {
      setProfileError(err instanceof ApiError ? String(err.detail ?? "Couldn't save") : "Couldn't save");
    } finally {
      setIsSavingProfile(false);
    }
  }

  async function handlePasswordSubmit(event: FormEvent) {
    event.preventDefault();
    setPasswordError(null);
    setPasswordSaved(false);
    setIsSavingPassword(true);
    try {
      await changeMyPassword(accessToken!, {
        current_password: currentPassword,
        new_password: newPassword,
      });
      setCurrentPassword("");
      setNewPassword("");
      setPasswordSaved(true);
    } catch (err) {
      setPasswordError(
        err instanceof ApiError ? String(err.detail ?? "Couldn't change password") : "Couldn't change password"
      );
    } finally {
      setIsSavingPassword(false);
    }
  }

  return (
    <>
      <Header title="Profile" description="Your personal account settings" />
      <main className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-xl space-y-6">
          <section className="rounded-lg border border-ink-100 bg-white p-6 shadow-panel">
            <h2 className="mb-4 text-sm font-semibold text-ink-900">Personal details</h2>
            <form onSubmit={handleProfileSubmit} className="flex flex-col gap-4">
              <Field label="Email" value={user.email} disabled readOnly />
              {!user.is_email_verified && (
                <p className="-mt-2 text-xs text-signal">Your email isn&apos;t verified yet.</p>
              )}
              <Field
                label="Full name"
                required
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
              />
              <Field
                label="Phone"
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="+1 555 000 0000"
              />
              <div className="flex flex-col gap-1.5">
                <label htmlFor="timezone" className="text-sm font-medium text-ink-700">
                  Timezone
                </label>
                <select
                  id="timezone"
                  value={timezone}
                  onChange={(e) => setTimezone(e.target.value)}
                  className="rounded-md border border-ink-200 bg-white px-3 py-2 text-sm text-ink-900 focus:border-ink-500"
                >
                  <option value="">Not set</option>
                  {TIMEZONE_OPTIONS.map((tz) => (
                    <option key={tz} value={tz}>
                      {tz}
                    </option>
                  ))}
                </select>
              </div>

              {profileError && (
                <p role="alert" className="text-sm text-signal">
                  {profileError}
                </p>
              )}
              {profileSaved && <p className="text-sm text-positive">Saved.</p>}

              <div>
                <Button type="submit" disabled={isSavingProfile}>
                  {isSavingProfile ? "Saving…" : "Save changes"}
                </Button>
              </div>
            </form>
          </section>

          <section className="rounded-lg border border-ink-100 bg-white p-6 shadow-panel">
            <h2 className="mb-4 text-sm font-semibold text-ink-900">Change password</h2>
            <form onSubmit={handlePasswordSubmit} className="flex flex-col gap-4">
              <Field
                label="Current password"
                type="password"
                autoComplete="current-password"
                required
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
              />
              <Field
                label="New password"
                type="password"
                autoComplete="new-password"
                required
                minLength={8}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
              />

              {passwordError && (
                <p role="alert" className="text-sm text-signal">
                  {passwordError}
                </p>
              )}
              {passwordSaved && <p className="text-sm text-positive">Password changed.</p>}

              <div>
                <Button type="submit" variant="secondary" disabled={isSavingPassword}>
                  {isSavingPassword ? "Updating…" : "Change password"}
                </Button>
              </div>
            </form>
          </section>
        </div>
      </main>
    </>
  );
}
