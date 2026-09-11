import Link from "next/link";

import { TrailMark } from "@/components/ui/Illustrations";

const footerLinks = [
  { href: "/dashboard", label: "Overview" },
  { href: "/jobs", label: "Opportunities" },
  { href: "/preferences", label: "Preferences" },
];

export function SiteFooter() {
  return (
    <footer className="mt-auto border-t border-line/80 bg-white/60 px-4 py-8 sm:px-6 md:px-10">
      <div className="mx-auto flex max-w-[1280px] flex-col gap-6 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex max-w-sm flex-col gap-2">
          <div className="flex items-center gap-2">
            <TrailMark size={22} />
            <span className="text-sm font-bold text-ink">Waypoint</span>
          </div>
          <p className="text-xs leading-relaxed text-text-muted">
            Thoughtful career intelligence, shaped around your voice and pace.
          </p>
        </div>
        <nav className="flex flex-wrap gap-4 text-xs font-medium text-text-muted">
          {footerLinks.map((link) => (
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
          © {new Date().getFullYear()} Waypoint. Built for intentional careers.
        </p>
      </div>
    </footer>
  );
}
