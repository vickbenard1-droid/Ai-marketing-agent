"use client";

import { useState } from "react";
import { LogOut, Settings, User as UserIcon, Users } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useSession } from "@/lib/session";

export function UserMenu() {
  const { user, logout } = useSession();
  const router = useRouter();
  const [isOpen, setIsOpen] = useState(false);
  const [isSigningOut, setIsSigningOut] = useState(false);

  if (!user) return null;

  const initials = (user.full_name ?? user.email)
    .split(" ")
    .map((part) => part.charAt(0))
    .slice(0, 2)
    .join("")
    .toUpperCase();

  async function handleSignOut() {
    setIsSigningOut(true);
    try {
      await logout();
    } finally {
      router.push("/login");
    }
  }

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setIsOpen((v) => !v)}
        className="flex items-center gap-2 rounded-full"
        aria-haspopup="menu"
        aria-expanded={isOpen}
      >
        <span className="flex h-8 w-8 items-center justify-center rounded-full bg-ink-800 text-xs font-semibold text-white">
          {initials}
        </span>
      </button>

      {isOpen && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setIsOpen(false)} />
          <div
            role="menu"
            className="absolute right-0 z-20 mt-2 w-56 overflow-hidden rounded-md border border-ink-200 bg-white py-1 shadow-lg"
          >
            <div className="border-b border-ink-100 px-3 py-2">
              <p className="truncate text-sm font-medium text-ink-900">
                {user.full_name ?? "Unnamed user"}
              </p>
              <p className="truncate text-xs text-ink-500">{user.email}</p>
            </div>
            <Link
              href="/profile"
              role="menuitem"
              onClick={() => setIsOpen(false)}
              className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-ink-700 hover:bg-ink-50"
            >
              <UserIcon className="h-4 w-4" />
              Profile
            </Link>
            <Link
              href="/team"
              role="menuitem"
              onClick={() => setIsOpen(false)}
              className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-ink-700 hover:bg-ink-50"
            >
              <Users className="h-4 w-4" />
              Team
            </Link>
            <Link
              href="/business-profile"
              role="menuitem"
              onClick={() => setIsOpen(false)}
              className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-ink-700 hover:bg-ink-50"
            >
              <Settings className="h-4 w-4" />
              Business profile
            </Link>
            <div className="my-1 border-t border-ink-100" />
            <button
              role="menuitem"
              disabled={isSigningOut}
              onClick={handleSignOut}
              className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-ink-700 hover:bg-ink-50 disabled:opacity-50"
            >
              <LogOut className="h-4 w-4" />
              {isSigningOut ? "Signing out…" : "Sign out"}
            </button>
          </div>
        </>
      )}
    </div>
  );
}
