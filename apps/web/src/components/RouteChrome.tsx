"use client";

import { usePathname } from "next/navigation";

import { WorkspaceShell } from "@/components/WorkspaceShell";

function isMarketingPath(pathname: string) {
  return (
    pathname === "/" ||
    pathname.startsWith("/login") ||
    pathname.startsWith("/signup")
  );
}

export function RouteChrome({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  if (isMarketingPath(pathname)) {
    return children;
  }

  return <WorkspaceShell>{children}</WorkspaceShell>;
}
