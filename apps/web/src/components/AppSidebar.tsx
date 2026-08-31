"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  BarChart3,
  Briefcase,
  Calendar,
  CircleUser,
  Columns3,
  Compass,
  FileText,
  LayoutDashboard,
  LogOut,
  Search,
  Send,
  Settings,
  Users,
  X,
  Zap,
} from "lucide-react";
import { useEffect, useState } from "react";

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
};

const workspaceNav: NavItem[] = [
  { key: "dashboard", href: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { key: "discover", href: "/preferences", label: "Discover", icon: Compass },
  { key: "jobs", href: "/jobs", label: "Jobs", icon: Briefcase },
  { key: "applications", href: "/applications", label: "Applications", icon: Columns3 },
  { key: "interviews", href: "/interviews", label: "Interviews", icon: Calendar },
  { key: "contacts", href: "/contacts", label: "Contacts", icon: Users },
  { key: "documents", href: "/documents", label: "Documents", icon: FileText },
  { key: "outreach", href: "/outreach", label: "Outreach", icon: Send },
];

const automationNav: NavItem[] = [
  { key: "automations", href: "/tasks", label: "Automations", icon: Zap },
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

function NavLink({
  item,
  active,
  onNavigate,
}: {
  item: NavItem;
  active: boolean;
  onNavigate?: () => void;
}) {
  const Icon = item.icon;
  return (
    <Link
      href={item.href}
      onClick={onNavigate}
      className={cn(
        "flex items-center gap-2.5 rounded-md px-2.5 py-2.5 text-[13px] transition-colors md:py-2",
        active
          ? "bg-sidebar-accent text-sidebar-foreground font-medium"
          : "text-sidebar-muted hover:bg-sidebar-accent/60 hover:text-sidebar-foreground",
      )}
    >
      <Icon className="h-4 w-4 shrink-0" />
      {item.label}
    </Link>
  );
}

function NavGroupLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="px-2 pb-1 pt-2 text-[10px] font-semibold tracking-wider text-sidebar-muted">
      {children}
    </p>
  );
}

export function AppSidebar({ active, mobileOpen = false, onClose }: AppSidebarProps) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const router = useRouter();
  const [userName, setUserName] = useState("User");
  const [userEmail, setUserEmail] = useState("");
  const [initials, setInitials] = useState("U");

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
      setUserEmail(user.email || "");
      const parts = name.split(" ").filter(Boolean);
      setInitials(
        parts.length >= 2
          ? `${parts[0][0]}${parts[1][0]}`.toUpperCase()
          : name.slice(0, 2).toUpperCase(),
      );
    }
    void loadUser();
  }, []);

  function isActive(item: NavItem) {
    if (active) return active === item.key;
    const tab = searchParams.get("tab");
    if (item.key === "profile") {
      return pathname === "/profile" || (pathname === "/settings" && tab === "profile");
    }
    if (item.key === "settings") {
      return (
        (pathname === "/settings" && tab !== "profile") ||
        pathname === "/preferences"
      );
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

  return (
    <aside
      className={cn(
        "flex h-full w-[min(100vw-3rem,17.5rem)] shrink-0 flex-col justify-between border-r border-sidebar-border bg-sidebar px-3 py-4 md:h-screen md:w-60",
        "fixed inset-y-0 left-0 z-50 transition-transform duration-200 ease-out md:static md:translate-x-0",
        mobileOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0",
      )}
      aria-label="Main navigation"
    >
      <div className="flex flex-col gap-4 overflow-y-auto">
        <div className="flex items-center justify-between gap-2.5 px-2 py-1">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
              <span className="font-serif text-base text-primary-foreground">C</span>
            </div>
            <div>
              <p className="text-sm font-semibold text-sidebar-foreground">
                Career Agent
              </p>
              <p className="text-[10px] text-sidebar-muted">Pro workspace</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-1.5 text-sidebar-muted hover:bg-sidebar-accent hover:text-sidebar-foreground md:hidden"
            aria-label="Close menu"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="hidden items-center justify-between rounded-md border border-sidebar-border bg-sidebar-accent px-2.5 py-2 md:flex">
          <div className="flex items-center gap-2">
            <Search className="h-3.5 w-3.5 text-sidebar-muted" />
            <span className="text-xs text-sidebar-muted">Search...</span>
          </div>
          <kbd className="rounded border border-sidebar-border bg-[#18181B] px-1.5 py-0.5 text-[10px] text-sidebar-muted">
            ⌘K
          </kbd>
        </div>

        <nav className="flex flex-col gap-0.5">
          <NavGroupLabel>WORKSPACE</NavGroupLabel>
          {workspaceNav.map((item) => (
            <NavLink
              key={item.key}
              item={item}
              active={isActive(item)}
              onNavigate={onClose}
            />
          ))}
          <NavGroupLabel>AUTOMATION</NavGroupLabel>
          {automationNav.map((item) => (
            <NavLink
              key={item.key}
              item={item}
              active={isActive(item)}
              onNavigate={onClose}
            />
          ))}
        </nav>
      </div>

      <div className="mt-4 flex shrink-0 flex-col gap-2">
        <div className="h-px bg-sidebar-border" />
        {bottomNav.map((item) => (
          <NavLink
            key={item.key}
            item={item}
            active={isActive(item)}
            onNavigate={onClose}
          />
        ))}
        <div className="flex items-center gap-2.5 rounded-md bg-sidebar-accent p-2.5">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary">
            <span className="text-[11px] font-semibold text-primary-foreground">
              {initials}
            </span>
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-xs font-medium text-sidebar-foreground">
              {userName}
            </p>
            <p className="truncate text-[10px] text-sidebar-muted">{userEmail}</p>
          </div>
          <button
            type="button"
            onClick={() => void signOut()}
            className="rounded-md p-1 text-sidebar-muted hover:bg-sidebar hover:text-sidebar-foreground"
            title="Sign out"
          >
            <LogOut className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </aside>
  );
}
