import type { NavKey } from "@/components/AppTopNav";

export type { NavKey };

type AppShellProps = {
  children: React.ReactNode;
  active?: NavKey;
  className?: string;
  wide?: boolean;
  hideActivityBar?: boolean;
};

/** @deprecated Shell lives in WorkspaceShell via RouteChrome; this wrapper is a no-op. */
export function AppShell({ children }: AppShellProps) {
  return children;
}
