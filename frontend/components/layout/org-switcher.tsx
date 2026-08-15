"use client";

import { useState } from "react";
import { ChevronsUpDown, Check, Plus } from "lucide-react";
import { useSession } from "@/lib/session";
import { cn } from "@/lib/utils";

export function OrgSwitcher() {
  const { organizations, activeOrganization, setActiveOrganizationId } = useSession();
  const [isOpen, setIsOpen] = useState(false);

  if (!activeOrganization) return null;

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setIsOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-2 rounded-md border border-ink-700 bg-ink-800 px-3 py-2 text-left text-sm text-white hover:bg-ink-700"
        aria-haspopup="listbox"
        aria-expanded={isOpen}
      >
        <span className="flex min-w-0 items-center gap-2">
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded bg-signal text-xs font-semibold uppercase text-white">
            {activeOrganization.name.charAt(0)}
          </span>
          <span className="truncate font-medium">{activeOrganization.name}</span>
        </span>
        <ChevronsUpDown className="h-4 w-4 shrink-0 text-ink-400" />
      </button>

      {isOpen && (
        <>
          {/* Click-outside layer */}
          <div className="fixed inset-0 z-10" onClick={() => setIsOpen(false)} />
          <div
            role="listbox"
            className="absolute left-0 right-0 z-20 mt-1.5 overflow-hidden rounded-md border border-ink-700 bg-ink-800 py-1 shadow-lg"
          >
            {organizations.map((org) => (
              <button
                key={org.id}
                role="option"
                aria-selected={org.id === activeOrganization.id}
                onClick={() => {
                  setActiveOrganizationId(org.id);
                  setIsOpen(false);
                }}
                className={cn(
                  "flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-white hover:bg-ink-700"
                )}
              >
                <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded bg-ink-600 text-[10px] font-semibold uppercase">
                  {org.name.charAt(0)}
                </span>
                <span className="min-w-0 flex-1 truncate">{org.name}</span>
                {org.id === activeOrganization.id && (
                  <Check className="h-4 w-4 shrink-0 text-signal" />
                )}
              </button>
            ))}
            <div className="my-1 border-t border-ink-700" />
            <button
              type="button"
              disabled
              title="Coming soon"
              className="flex w-full cursor-not-allowed items-center gap-2 px-3 py-2 text-left text-sm text-ink-500"
            >
              <Plus className="h-4 w-4" />
              New organization
            </button>
          </div>
        </>
      )}
    </div>
  );
}
