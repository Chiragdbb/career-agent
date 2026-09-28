import Link from "next/link";

import { TrailMark } from "@/components/ui/Illustrations";

const appLinks = [
  { href: "/dashboard", label: "Today" },
  { href: "/jobs", label: "Opportunities" },
  { href: "/approvals", label: "Approvals" },
  { href: "/preferences", label: "Preferences" },
];

const marketingLinks = [
  { href: "#demo", label: "Demo" },
  { href: "#features", label: "Features" },
  { href: "#pricing", label: "Pricing" },
  { href: "/signup", label: "Sign up" },
  { href: "/login", label: "Sign in" },
];

export function SiteFooter({ variant = "app" }: { variant?: "app" | "marketing" }) {
  const isMarketing = variant === "marketing";
  const links = isMarketing ? marketingLinks : appLinks;

  return (
    <footer
      className={
        isMarketing
          ? "mt-auto border-t border-mkt-hairline bg-white px-4 py-12 sm:px-6 lg:px-8"
          : "mt-auto border-t border-line bg-white px-4 py-8 sm:px-6 md:px-10"
      }
    >
      <div className="mx-auto flex max-w-6xl flex-col gap-8 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex max-w-sm flex-col gap-3">
          <Link href={isMarketing ? "/" : "/dashboard"} className="flex items-center gap-2">
            <TrailMark size={22} />
            <span className="text-sm font-bold text-ink">Waypoint</span>
          </Link>
          <p className="text-sm leading-relaxed text-text-muted">
            Career intelligence with human approval on every outbound action.
          </p>
        </div>
        <nav className="flex flex-wrap gap-x-6 gap-y-2 text-sm font-medium text-text-muted">
          {links.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="hover:text-coral"
            >
              {link.label}
            </Link>
          ))}
        </nav>
        <p className="text-xs text-text-faint">
          © {new Date().getFullYear()} Waypoint
        </p>
      </div>
    </footer>
  );
}
