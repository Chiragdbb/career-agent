"use client";

import { Menu } from "lucide-react";
import { usePathname } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { AppSidebar, type NavKey } from "@/components/AppSidebar";
import { cn } from "@/lib/cn";

type AppShellProps = {
  children: React.ReactNode;
  active?: NavKey;
  className?: string;
  wide?: boolean;
};

function SidebarFallback() {
  return (
    <aside className="hidden h-screen w-60 shrink-0 bg-sidebar md:block" />
  );
}

function MobileHeader({ onOpenMenu }: { onOpenMenu: () => void }) {
  return (
    <header className="sticky top-0 z-30 flex items-center gap-3 border-b border-border bg-background/95 px-4 py-3 backdrop-blur supports-[backdrop-filter]:bg-background/80 md:hidden">
      <button
        type="button"
        onClick={onOpenMenu}
        className="rounded-md border border-border p-2 text-foreground hover:bg-muted"
        aria-label="Open menu"
      >
        <Menu className="h-5 w-5" />
      </button>
      <div className="flex items-center gap-2">
        <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary">
          <span className="font-serif text-sm text-primary-foreground">C</span>
        </div>
        <span className="text-sm font-semibold text-foreground">Career Agent</span>
      </div>
    </header>
  );
}

function AppShellInner({ children, active, className, wide }: AppShellProps) {
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
    <div className="flex min-h-screen bg-background">
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

      <div className="flex min-w-0 flex-1 flex-col">
        <MobileHeader onOpenMenu={() => setMobileNavOpen(true)} />
        <main
          className={cn(
            "flex-1 overflow-x-hidden px-4 py-5 sm:px-6 md:px-9 md:py-7",
            !wide && "md:max-w-[1200px]",
            className,
          )}
        >
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
