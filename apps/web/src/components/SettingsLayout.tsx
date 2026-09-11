"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { cn } from "@/lib/cn";

const settingsNav = [
  { id: "profile", label: "Profile", href: "/settings?tab=profile" },
  { id: "preferences", label: "Job preferences", href: "/preferences" },
  { id: "resume", label: "Resume", href: "/documents?tab=resumes" },
  { id: "notifications", label: "Notifications", href: "/settings?tab=notifications" },
  { id: "email", label: "Email (Coming soon)", href: "/settings?tab=email" },
] as const;

type SettingsLayoutProps = {
  children: React.ReactNode;
  title?: string;
};

export function SettingsLayout({ children, title = "Settings" }: SettingsLayoutProps) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const tab = searchParams.get("tab") || "notifications";

  function isActive(item: (typeof settingsNav)[number]) {
    if (item.id === "preferences") return pathname === "/preferences";
    if (item.id === "resume") return pathname === "/documents";
    if (item.id === "profile") return tab === "profile";
    if (item.id === "email") return tab === "email";
    return tab === "notifications" && item.id === "notifications";
  }

  return (
    <AppShell active="settings" wide>
      <div className="flex min-h-0 flex-col gap-6 md:flex-row md:gap-8">
        <nav className="md:w-56 md:shrink-0">
          <h1 className="mb-3 px-1 text-lg font-bold tracking-tight text-ink md:mb-4">
            {title}
          </h1>
          <ul className="-mx-1 flex gap-2 overflow-x-auto pb-1 md:mx-0 md:flex-col md:gap-1 md:overflow-visible md:pb-0">
            {settingsNav.map((item) => (
              <li key={item.id} className="shrink-0 md:shrink">
                <Link
                  href={item.href}
                  className={cn(
                    "block whitespace-nowrap rounded-full px-3 py-2 text-[13px] font-medium transition-colors",
                    isActive(item)
                      ? "bg-lavender font-semibold text-lavender-deep"
                      : "text-text-muted hover:bg-white hover:text-ink",
                  )}
                >
                  {item.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
        <div className="min-w-0 flex-1">{children}</div>
      </div>
    </AppShell>
  );
}
