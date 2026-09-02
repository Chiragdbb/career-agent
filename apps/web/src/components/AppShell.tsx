"use client";

import { Menu } from "lucide-react";
import { usePathname } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { AppSidebar, type NavKey } from "@/components/AppSidebar";
import { NotificationBell } from "@/components/NotificationBell";
import { ActivityBar } from "@/components/ActivityBar";
import { TrailMark } from "@/components/ui/Illustrations";
import { cn } from "@/lib/cn";

type AppShellProps = {
  children: React.ReactNode;
  active?: NavKey;
  className?: string;
  wide?: boolean;
  /** Hide global ActivityBar (e.g. dashboard renders its own inline) */
  hideActivityBar?: boolean;
};

function SidebarFallback() {
  return <aside className="hidden h-screen w-[232px] shrink-0 bg-ink md:block" />;
}

function MobileHeader({ onOpenMenu }: { onOpenMenu: () => void }) {
  return (
    <header className="sticky top-0 z-30 flex items-center gap-3 border-b border-line bg-paper/95 px-4 py-3 backdrop-blur supports-[backdrop-filter]:bg-paper/80 md:hidden">
      <button
        type="button"
        onClick={onOpenMenu}
        className="rounded-md border border-line p-2 text-foreground hover:bg-paper-raised"
        aria-label="Open menu"
      >
        <Menu className="h-5 w-5" />
      </button>
      <div className="flex items-center gap-2">
        <TrailMark size={22} />
        <span className="font-serif text-sm font-semibold text-ink">Waypoint</span>
      </div>
    </header>
  );
}

function AppShellInner({
  children,
  active,
  className,
  wide,
  hideActivityBar,
}: AppShellProps) {
  const pathname = usePathname();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  useEffect(() => {
    setMobileNavOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!mobileNavOpen) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [mobileNavOpen]);

  return (
    <div className="flex h-screen overflow-hidden bg-paper">
      {mobileNavOpen ? (
        <button
          type="button"
          className="fixed inset-0 z-40 bg-black/50 md:hidden"
          aria-label="Close menu"
          onClick={() => setMobileNavOpen(false)}
        />
      ) : null}

      <AppSidebar
        active={active}
        mobileOpen={mobileNavOpen}
        onClose={() => setMobileNavOpen(false)}
      />

      <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <MobileHeader onOpenMenu={() => setMobileNavOpen(true)} />
        <main
          className={cn(
            "flex-1 overflow-y-auto overflow-x-hidden px-4 py-5 sm:px-6 md:px-8 md:py-7",
            !wide && "md:max-w-[1200px]",
            className,
          )}
        >
          <div className="mb-4 flex items-center justify-end gap-3">
            <NotificationBell />
            {!hideActivityBar ? <ActivityBar className="mb-0" /> : null}
          </div>
          {children}
        </main>
      </div>
    </div>
  );
}

export function AppShell(props: AppShellProps) {
  return (
    <Suspense fallback={<SidebarFallback />}>
      <AppShellInner {...props} />
    </Suspense>
  );
}
