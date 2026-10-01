"use client";

import { Suspense } from "react";
import { usePathname } from "next/navigation";
import { MotionConfig } from "motion/react";

import { AppTopNav } from "@/components/AppTopNav";
import { PageTransition } from "@/components/PageTransition";
import { ProcessBanner } from "@/components/ProcessBanner";
import { SiteFooter } from "@/components/SiteFooter";
import { EventStreamProvider } from "@/providers/EventStreamProvider";
import { ProcessActivityProvider } from "@/providers/ProcessActivityProvider";
import { QueryProvider } from "@/providers/QueryProvider";
import { cn } from "@/lib/cn";

function ShellFallback() {
  return <div className="h-16 border-b border-line bg-white md:h-20" />;
}

function mainOptions(pathname: string) {
  const hideActivityBar =
    pathname.startsWith("/dashboard") || pathname.startsWith("/activity");
  const wide = !pathname.startsWith("/preferences");
  const className = pathname.startsWith("/documents") ? "!max-w-none" : undefined;
  return { hideActivityBar, wide, className };
}

function WorkspaceShellInner({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { hideActivityBar, wide, className } = mainOptions(pathname);

  return (
    <div className="app-shell flex min-h-screen flex-col bg-paper">
      <Suspense fallback={<ShellFallback />}>
        <AppTopNav />
      </Suspense>
      <main
        className={cn(
          "mx-auto w-full flex-1 px-4 py-6 sm:px-6 md:px-8 md:py-8",
          wide ? "max-w-[1280px]" : "max-w-[1200px]",
          className,
        )}
      >
        {!hideActivityBar ? <ProcessBanner /> : null}
        <PageTransition>{children}</PageTransition>
      </main>
      <SiteFooter />
    </div>
  );
}

export function WorkspaceShell({ children }: { children: React.ReactNode }) {
  return (
    <MotionConfig reducedMotion="user">
      <QueryProvider>
        <EventStreamProvider>
          <ProcessActivityProvider>
            <WorkspaceShellInner>{children}</WorkspaceShellInner>
          </ProcessActivityProvider>
        </EventStreamProvider>
      </QueryProvider>
    </MotionConfig>
  );
}
