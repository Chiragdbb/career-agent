"use client";

import { Suspense } from "react";

import { AppTopNav, type NavKey } from "@/components/AppTopNav";
import { SiteFooter } from "@/components/SiteFooter";
import { ActivityBar } from "@/components/ActivityBar";
import { cn } from "@/lib/cn";

export type { NavKey };

type AppShellProps = {
  children: React.ReactNode;
  active?: NavKey;
  className?: string;
  wide?: boolean;
  /** Hide global ActivityBar (e.g. dashboard renders its own inline) */
  hideActivityBar?: boolean;
};

function ShellFallback() {
  return <div className="h-16 border-b border-line bg-white md:h-20" />;
}

function AppShellInner({
  children,
  active,
  className,
  wide,
  hideActivityBar,
}: AppShellProps) {
  return (
    <div className="flex min-h-screen flex-col bg-paper">
      <AppTopNav active={active} />
      <main
        className={cn(
          "mx-auto w-full flex-1 px-4 py-6 sm:px-6 md:px-8 md:py-8",
          wide ? "max-w-[1280px]" : "max-w-[1200px]",
          className,
        )}
      >
        {!hideActivityBar ? (
          <div className="mb-4 flex justify-end">
            <ActivityBar className="mb-0" />
          </div>
        ) : null}
        {children}
      </main>
      <SiteFooter />
    </div>
  );
}

export function AppShell(props: AppShellProps) {
  return (
    <Suspense fallback={<ShellFallback />}>
      <AppShellInner {...props} />
    </Suspense>
  );
}
