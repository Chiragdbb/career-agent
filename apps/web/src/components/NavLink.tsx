"use client";

import Link from "next/link";
import { useLinkStatus } from "next/link";
import type { ComponentProps, ReactNode } from "react";

import { cn } from "@/lib/cn";

type NavLinkProps = Omit<ComponentProps<typeof Link>, "children"> & {
  active?: boolean;
  inactiveClassName?: string;
  activeClassName?: string;
  children: ReactNode;
};

function NavLinkStatus({
  active,
  inactiveClassName,
  activeClassName,
  children,
}: Pick<NavLinkProps, "active" | "inactiveClassName" | "activeClassName" | "children">) {
  const { pending } = useLinkStatus();

  return (
    <span
      className={cn(
        active ? activeClassName : inactiveClassName,
        pending && "opacity-70",
      )}
      aria-busy={pending || undefined}
    >
      {children}
    </span>
  );
}

export function NavLink({
  active,
  className,
  inactiveClassName,
  activeClassName,
  children,
  ...props
}: NavLinkProps) {
  return (
    <Link {...props} className={className}>
      <NavLinkStatus
        active={active}
        inactiveClassName={inactiveClassName}
        activeClassName={activeClassName}
      >
        {children}
      </NavLinkStatus>
    </Link>
  );
}
