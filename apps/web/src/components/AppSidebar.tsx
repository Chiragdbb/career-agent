"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  BarChart3,
  Briefcase,
  CalendarClock,
  CircleUser,
  Compass,
  FileText,
  LayoutDashboard,
  LayoutGrid,
  LogOut,
  Send,
  Settings,
  Sparkles,
  Users,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";

import { TrailMark } from "@/components/ui/Illustrations";
import { apiFetch } from "@/lib/api";
import { cn } from "@/lib/cn";

export type NavKey =
  | "dashboard"
  | "discover"
  | "jobs"
  | "applications"
  | "contacts"
  | "documents"
  | "outreach"
  | "automations"
  | "analytics"
  | "settings"
  | "profile"
  | "interviews"
  | "tasks"
  | "preferences"
  | "resumes";

type NavItem = {
  key: NavKey;
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  badgeKey?: "applications" | "automations";
};

const overviewNav: NavItem = {
  key: "dashboard",
  href: "/dashboard",
  label: "Overview",
  icon: LayoutDashboard,
};

const pipelineNav: NavItem[] = [
  { key: "discover", href: "/preferences", label: "Discover", icon: Compass },
  { key: "jobs", href: "/jobs", label: "Jobs", icon: Briefcase },
  {
    key: "applications",
    href: "/applications",
    label: "Applications",
    icon: LayoutGrid,
    badgeKey: "applications",
  },
  { key: "interviews", href: "/interviews", label: "Interviews", icon: CalendarClock },
];

const supportNav: NavItem[] = [
  { key: "contacts", href: "/contacts", label: "Contacts", icon: Users },
  { key: "outreach", href: "/outreach", label: "Outreach", icon: Send },
  { key: "documents", href: "/documents", label: "Documents", icon: FileText },
];

const insightNav: NavItem[] = [
  {
    key: "automations",
    href: "/tasks",
    label: "Automations",
    icon: Sparkles,
    badgeKey: "automations",
  },
  { key: "analytics", href: "/analytics", label: "Analytics", icon: BarChart3 },
];

const bottomNav: NavItem[] = [
  { key: "settings", href: "/settings", label: "Settings", icon: Settings },
  { key: "profile", href: "/settings?tab=profile", label: "Profile", icon: CircleUser },
];

type AppSidebarProps = {
  active?: NavKey;
  mobileOpen?: boolean;
  onClose?: () => void;
};

function NavGroupLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="px-2.5 pb-1.5 pt-4 text-[11.5px] text-[#7C8880] first:pt-0">
      {children}
    </p>
  );
}

function NavLink({
  item,
  active,
  showDot,
  badge,
  onNavigate,
}: {
  item: NavItem;
  active: boolean;
  showDot?: boolean;
  badge?: number;
  onNavigate?: () => void;
}) {
  const Icon = item.icon;
  return (
    <Link
      href={item.href}
      onClick={onNavigate}
      className={cn(
        "relative flex w-full items-center gap-2.5 rounded-[7px] px-2.5 py-2 text-[13.5px] transition-colors",
        active
          ? "bg-[rgba(185,130,46,0.14)] font-semibold text-gold-soft"
          : "text-[#B8C2BB] hover:bg-white/5",
      )}
    >
      {showDot !== undefined ? (
        <span
          className={cn(
            "h-1.5 w-1.5 shrink-0 rounded-full",
            showDot ? "bg-gold" : "bg-[#3B4C42]",
          )}
        />
      ) : null}
      <Icon className={cn("h-[15px] w-[15px] shrink-0", !active && "opacity-80")} />
      <span className="flex-1">{item.label}</span>
      {badge != null && badge > 0 ? (
        <span className="rounded-full bg-brick px-1.5 py-px text-[11px] font-semibold text-[#FBE6DF]">
          {badge}
        </span>
      ) : null}
    </Link>
  );
}

export function AppSidebar({ active, mobileOpen = false, onClose }: AppSidebarProps) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const router = useRouter();
  const [userName, setUserName] = useState("User");
  const [initials, setInitials] = useState("U");
  const [badges, setBadges] = useState({ applications: 0, automations: 0 });

  useEffect(() => {
    async function loadUser() {
      const { createClient } = await import("@/lib/supabase/client");
      const supabase = createClient();
      const {
        data: { user },
      } = await supabase.auth.getUser();
      if (!user) return;
      const name =
        (user.user_metadata?.full_name as string | undefined) ||
        user.email?.split("@")[0] ||
        "User";
      setUserName(name);
      const parts = name.split(" ").filter(Boolean);
      setInitials(
        parts.length >= 2
          ? `${parts[0][0]}${parts[1][0]}`.toUpperCase()
          : name.slice(0, 2).toUpperCase(),
      );
    }
    void loadUser();
  }, []);

  useEffect(() => {
    async function loadBadges() {
      try {
        const [appsRes, tasksRes, summaryRes] = await Promise.all([
          apiFetch("/api/v1/applications"),
          apiFetch("/api/v1/human-tasks?status=open"),
          apiFetch("/api/v1/dashboard/summary"),
        ]);
        let applicationsBadge = 0;
        let automationsBadge = 0;
        let summary: { open_follow_ups?: number; open_human_tasks?: number } | null =
          null;
        if (summaryRes.ok) {
          summary = (await summaryRes.json()) as {
            open_follow_ups?: number;
            open_human_tasks?: number;
          };
          automationsBadge = summary?.open_human_tasks ?? 0;
        }
        if (tasksRes.ok) {
          const tasks = (await tasksRes.json()) as unknown[];
          automationsBadge = Math.max(automationsBadge, tasks.length);
        }
        if (appsRes.ok) {
          const apps = (await appsRes.json()) as { status: string }[];
          applicationsBadge = apps.filter((a) => {
            const s = a.status.toLowerCase();
            return (
              s.includes("blocked") ||
              s.includes("action") ||
              s.includes("paused") ||
              s.includes("needs")
            );
          }).length;
          applicationsBadge += summary?.open_follow_ups ?? 0;
        }
        setBadges({ applications: applicationsBadge, automations: automationsBadge });
      } catch {
        /* badges are optional */
      }
    }
    void loadBadges();
  }, []);

  function isActive(item: NavItem) {
    if (active) return active === item.key;
    const tab = searchParams.get("tab");
    if (item.key === "profile") {
      return pathname === "/profile" || (pathname === "/settings" && tab === "profile");
    }
    if (item.key === "settings") {
      return pathname === "/settings" && tab !== "profile";
    }
    if (item.key === "discover") {
      return pathname === "/preferences";
    }
    const baseHref = item.href.split("?")[0];
    return pathname === baseHref || pathname.startsWith(`${baseHref}/`);
  }

  async function signOut() {
    const { createClient } = await import("@/lib/supabase/client");
    const supabase = createClient();
    await supabase.auth.signOut();
    onClose?.();
    router.replace("/login");
    router.refresh();
  }

  function badgeFor(item: NavItem) {
    if (!item.badgeKey) return undefined;
    return badges[item.badgeKey];
  }

  return (
    <aside
      className={cn(
        "flex h-full w-[min(100vw-3rem,232px)] shrink-0 flex-col bg-ink px-3.5 py-5 md:h-screen md:w-[232px]",
        "fixed inset-y-0 left-0 z-50 transition-transform duration-200 ease-out md:sticky md:top-0 md:translate-x-0",
        mobileOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0",
      )}
      aria-label="Main navigation"
    >
      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
        <div className="mb-5 flex items-center justify-between gap-2 px-2 py-1">
          <div className="flex items-center gap-2">
            <TrailMark size={26} />
            <span className="font-serif text-[16.5px] font-semibold text-[#F3EFE2]">
              Waypoint
            </span>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-1.5 text-[#7C8880] hover:bg-white/5 md:hidden"
            aria-label="Close menu"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <nav className="flex flex-col gap-0.5">
          <NavLink item={overviewNav} active={isActive(overviewNav)} onNavigate={onClose} />

          <NavGroupLabel>Pipeline</NavGroupLabel>
          <div className="relative flex flex-col gap-0.5">
            <div className="absolute bottom-4 left-[15px] top-4 w-px bg-[#2E3F35]" />
            {pipelineNav.map((item) => (
              <NavLink
                key={item.key}
                item={item}
                active={isActive(item)}
                showDot={isActive(item)}
                badge={badgeFor(item)}
                onNavigate={onClose}
              />
            ))}
          </div>

          <NavGroupLabel>Support</NavGroupLabel>
          {supportNav.map((item) => (
            <NavLink
              key={item.key}
              item={item}
              active={isActive(item)}
              onNavigate={onClose}
            />
          ))}

          <NavGroupLabel>Insight</NavGroupLabel>
          {insightNav.map((item) => (
            <NavLink
              key={item.key}
              item={item}
              active={isActive(item)}
              badge={badgeFor(item)}
              onNavigate={onClose}
            />
          ))}
        </nav>
      </div>

      <div className="mt-2.5 shrink-0">
        <div className="my-2.5 h-px bg-[#263831]" />
        {bottomNav.map((item) => (
          <NavLink
            key={item.key}
            item={item}
            active={isActive(item)}
            onNavigate={onClose}
          />
        ))}
        <div className="mt-2 flex items-center gap-2 px-2 py-1.5">
          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gold-soft font-serif text-xs font-semibold text-[#3B2A08]">
            {initials}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-[12.5px] font-medium text-[#EDE9DB]">{userName}</p>
            <p className="text-[11px] text-[#7C8880]">Settings</p>
          </div>
          <button
            type="button"
            onClick={() => void signOut()}
            className="rounded-md p-1 text-[#7C8880] hover:bg-white/5 hover:text-[#EDE9DB]"
            title="Sign out"
          >
            <LogOut className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </aside>
  );
}
