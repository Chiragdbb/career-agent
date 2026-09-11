"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Menu,
  Search,
  Settings,
  FileText,
  Users,
  BarChart3,
  Compass,
  X,
  LogOut,
  CircleUser,
} from "lucide-react";
import { useEffect, useState } from "react";

import { CommandPalette } from "@/components/CommandPalette";
import { NotificationBell } from "@/components/NotificationBell";
import { TrailMark } from "@/components/ui/Illustrations";
import { apiFetch } from "@/lib/api";
import { cn } from "@/lib/cn";
import { createClient } from "@/lib/supabase/client";

export type NavKey =
  | "dashboard"
  | "discover"
  | "jobs"
  | "applications"
  | "contacts"
  | "documents"
  | "outreach"
  | "automations"
  | "approvals"
  | "analytics"
  | "settings"
  | "profile"
  | "interviews"
  | "tasks"
  | "preferences"
  | "resumes"
  | "activity";

const primaryNav: { key: NavKey; href: string; label: string; badge?: boolean }[] = [
  { key: "dashboard", href: "/dashboard", label: "Today" },
  { key: "jobs", href: "/jobs", label: "Opportunities" },
  { key: "approvals", href: "/approvals", label: "Approvals", badge: true },
  { key: "outreach", href: "/outreach", label: "Conversations" },
  { key: "applications", href: "/applications", label: "Applications" },
  { key: "interviews", href: "/interviews", label: "Interviews" },
];

const secondaryNav = [
  { href: "/preferences", label: "Discover", icon: Compass },
  { href: "/contacts", label: "Contacts", icon: Users },
  { href: "/documents", label: "Documents", icon: FileText },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/settings", label: "Settings", icon: Settings },
  { href: "/settings?tab=profile", label: "Profile", icon: CircleUser },
];

type AppTopNavProps = {
  active?: NavKey;
  approvalCount?: number;
};

function resolveActive(pathname: string, active?: NavKey): NavKey | undefined {
  if (active) return active;
  if (pathname.startsWith("/approvals") || pathname.startsWith("/tasks")) {
    return "approvals";
  }
  if (pathname.startsWith("/dashboard")) return "dashboard";
  if (pathname.startsWith("/jobs")) return "jobs";
  if (pathname.startsWith("/outreach")) return "outreach";
  if (pathname.startsWith("/applications")) return "applications";
  if (pathname.startsWith("/interviews")) return "interviews";
  if (pathname.startsWith("/preferences")) return "discover";
  if (pathname.startsWith("/contacts")) return "contacts";
  if (pathname.startsWith("/documents") || pathname.startsWith("/resumes")) {
    return "documents";
  }
  if (pathname.startsWith("/analytics")) return "analytics";
  if (pathname.startsWith("/settings") || pathname.startsWith("/profile")) {
    return "settings";
  }
  if (pathname.startsWith("/activity")) return "activity";
  return undefined;
}

export function AppTopNav({ active, approvalCount }: AppTopNavProps) {
  const pathname = usePathname();
  const router = useRouter();
  const current = resolveActive(pathname, active);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [cmdOpen, setCmdOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [badgeCount, setBadgeCount] = useState(approvalCount ?? 0);

  useEffect(() => {
    setMobileOpen(false);
    setMenuOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (approvalCount != null) {
      setBadgeCount(approvalCount);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const [outreachRes, tasksRes] = await Promise.all([
          apiFetch("/api/v1/outreach"),
          apiFetch("/api/v1/human-tasks?status=open"),
        ]);
        let count = 0;
        if (outreachRes.ok) {
          const data = (await outreachRes.json()) as { status?: string }[];
          count += (Array.isArray(data) ? data : []).filter((o) => {
            const s = (o.status ?? "").toLowerCase();
            return s.includes("draft") || s === "pending_approval";
          }).length;
        }
        if (tasksRes.ok) {
          const data = (await tasksRes.json()) as unknown[];
          count += Array.isArray(data) ? data.length : 0;
        }
        if (!cancelled) setBadgeCount(count);
      } catch {
        /* ignore */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [approvalCount, pathname]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setCmdOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  async function signOut() {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.replace("/login");
  }

  return (
    <>
      <header className="sticky top-0 z-40 border-b border-line/80 bg-white/90 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-[1280px] items-center gap-3 px-4 sm:px-6 md:h-20 md:px-8">
          <button
            type="button"
            className="rounded-full border border-line p-2 text-ink lg:hidden"
            aria-label="Open menu"
            onClick={() => setMobileOpen(true)}
          >
            <Menu className="h-5 w-5" />
          </button>

          <Link href="/dashboard" className="flex shrink-0 items-center gap-2">
            <TrailMark size={28} />
            <span className="text-[15px] font-bold tracking-tight text-ink">
              Waypoint
            </span>
          </Link>

          <nav className="ml-4 hidden items-center gap-1 lg:flex">
            {primaryNav.map((item) => {
              const isActive = current === item.key;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "relative rounded-full px-3 py-1.5 text-[13px] font-semibold transition-colors",
                    isActive
                      ? "bg-lavender text-lavender-deep"
                      : "text-text-muted hover:bg-paper hover:text-ink",
                  )}
                >
                  {item.label}
                  {item.badge && badgeCount > 0 ? (
                    <span className="ml-1.5 inline-flex items-center rounded-full bg-coral-soft px-1.5 py-0.5 text-[10px] font-bold text-coral-deep">
                      {badgeCount} to check
                    </span>
                  ) : null}
                </Link>
              );
            })}
          </nav>

          <div className="ml-auto flex items-center gap-2 sm:gap-3">
            <button
              type="button"
              onClick={() => setCmdOpen(true)}
              className="hidden items-center gap-2 rounded-full border border-line bg-paper px-3 py-2 text-xs text-text-faint sm:flex md:min-w-[220px]"
            >
              <Search className="h-3.5 w-3.5" />
              <span className="flex-1 text-left">Jump to role, note, or prompt…</span>
              <kbd className="rounded border border-line bg-white px-1.5 py-0.5 text-[10px] font-semibold">
                ⌘K
              </kbd>
            </button>

            <NotificationBell />

            <div className="hidden items-center gap-1.5 text-[11px] font-semibold text-text-muted md:flex">
              <span className="size-1.5 rounded-full bg-coral" />
              Agent at your side
            </div>

            <div className="relative">
              <button
                type="button"
                onClick={() => setMenuOpen((v) => !v)}
                className="flex h-9 w-9 items-center justify-center overflow-hidden rounded-full border border-line bg-lavender text-xs font-bold text-lavender-deep"
                aria-label="Account menu"
              >
                W
              </button>
              {menuOpen ? (
                <div className="absolute right-0 mt-2 w-52 overflow-hidden rounded-2xl border border-line bg-white py-1 shadow-card">
                  {secondaryNav.map((item) => {
                    const Icon = item.icon;
                    return (
                      <Link
                        key={item.href}
                        href={item.href}
                        className="flex items-center gap-2 px-3 py-2.5 text-sm text-ink hover:bg-paper"
                        onClick={() => setMenuOpen(false)}
                      >
                        <Icon className="h-4 w-4 text-text-faint" />
                        {item.label}
                      </Link>
                    );
                  })}
                  <button
                    type="button"
                    onClick={() => void signOut()}
                    className="flex w-full items-center gap-2 border-t border-line px-3 py-2.5 text-sm text-coral-deep hover:bg-coral-bg"
                  >
                    <LogOut className="h-4 w-4" />
                    Sign out
                  </button>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      </header>

      {mobileOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            className="absolute inset-0 bg-ink/40"
            aria-label="Close menu"
            onClick={() => setMobileOpen(false)}
          />
          <aside className="absolute inset-y-0 left-0 flex w-[280px] flex-col bg-white shadow-card">
            <div className="flex items-center justify-between border-b border-line px-4 py-4">
              <div className="flex items-center gap-2">
                <TrailMark size={24} />
                <span className="font-bold text-ink">Waypoint</span>
              </div>
              <button
                type="button"
                onClick={() => setMobileOpen(false)}
                className="rounded-full p-2 hover:bg-paper"
                aria-label="Close"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <nav className="flex flex-col gap-1 p-3">
              {primaryNav.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "rounded-xl px-3 py-2.5 text-sm font-semibold",
                    current === item.key
                      ? "bg-lavender text-lavender-deep"
                      : "text-ink hover:bg-paper",
                  )}
                >
                  {item.label}
                  {item.badge && badgeCount > 0
                    ? ` · ${badgeCount}`
                    : ""}
                </Link>
              ))}
              <div className="my-2 border-t border-line" />
              {secondaryNav.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className="rounded-xl px-3 py-2.5 text-sm text-text-muted hover:bg-paper hover:text-ink"
                >
                  {item.label}
                </Link>
              ))}
            </nav>
          </aside>
        </div>
      ) : null}

      <CommandPalette open={cmdOpen} onClose={() => setCmdOpen(false)} />
    </>
  );
}
