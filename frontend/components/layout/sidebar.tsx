"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Sparkles,
  Bot,
  Megaphone,
  FileText,
  CalendarClock,
  BarChart3,
  Plug,
  Settings,
  Users,
  CircleDollarSign,
  Gauge,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { OrgSwitcher } from "./org-switcher";

// Every item below except Dashboard, AI Assistant, AI Tools, Campaigns,
// Content, Schedule, Meta Ads, Team, and Settings is a placeholder route
// for functionality that arrives in a later week (see project scope doc).
// They're shown disabled rather than omitted so the information
// architecture of the full product is visible from day one.
const NAV_ITEMS = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard, enabled: true },
  { label: "AI Assistant", href: "/chat", icon: Sparkles, enabled: true },
  { label: "AI Tools", href: "/ai-tools", icon: Bot, enabled: true },
  { label: "Campaigns", href: "/campaigns", icon: Megaphone, enabled: true },
  { label: "Content", href: "/content", icon: FileText, enabled: true },
  { label: "Schedule", href: "/schedule", icon: CalendarClock, enabled: true },
  { label: "Meta Ads", href: "/meta-ads", icon: CircleDollarSign, enabled: true },
  { label: "Analytics", href: "/analytics", icon: BarChart3, enabled: true },
  { label: "Optimization", href: "/optimization", icon: Gauge, enabled: true },
  { label: "Integrations", href: "/integrations", icon: Plug, enabled: true },
  { label: "Team", href: "/team", icon: Users, enabled: true },
] as const;

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex h-screen w-64 shrink-0 flex-col border-r border-ink-800 bg-ink-900">
      <div className="flex items-center gap-2.5 px-4 py-4">
        <div className="flex h-7 w-7 items-center justify-center rounded-md bg-signal font-mono text-xs font-semibold text-white">
          A
        </div>
        <span className="text-sm font-medium tracking-wide text-white">
          AI MARKETING AGENT
        </span>
      </div>

      <div className="px-3 pb-3">
        <OrgSwitcher />
      </div>

      <nav className="flex-1 space-y-0.5 px-3">
        {NAV_ITEMS.map((item) => {
          const isActive = pathname === item.href || pathname.startsWith(`${item.href}/`);
          const Icon = item.icon;

          if (!item.enabled) {
            return (
              <div
                key={item.label}
                title="Coming in a later release"
                className="flex cursor-not-allowed items-center gap-2.5 rounded-md px-3 py-2 text-sm text-ink-500"
              >
                <Icon className="h-4 w-4" />
                {item.label}
                <span className="ml-auto rounded-sm bg-ink-800 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-ink-500">
                  Soon
                </span>
              </div>
            );
          }

          return (
            <Link
              key={item.label}
              href={item.href}
              className={cn(
                "flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-ink-800 text-white"
                  : "text-ink-300 hover:bg-ink-800 hover:text-white"
              )}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-ink-800 px-3 py-3">
        <Link
          href="/business-profile"
          className="flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium text-ink-300 hover:bg-ink-800 hover:text-white"
        >
          <Settings className="h-4 w-4" />
          Business profile
        </Link>
      </div>
    </aside>
  );
}
