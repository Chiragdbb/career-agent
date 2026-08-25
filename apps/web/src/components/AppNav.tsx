"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

type AppNavProps = {
  active?: "dashboard" | "profile" | "preferences" | "resumes" | "jobs";
};

const links = [
  { href: "/dashboard", key: "dashboard" as const, label: "Dashboard" },
  { href: "/jobs", key: "jobs" as const, label: "Jobs" },
  { href: "/profile", key: "profile" as const, label: "Profile" },
  { href: "/preferences", key: "preferences" as const, label: "Job Preferences" },
  { href: "/resumes", key: "resumes" as const, label: "Resumes" },
];

export function AppNav({ active }: AppNavProps) {
  const router = useRouter();

  async function signOut() {
    const { createClient } = await import("@/lib/supabase/client");
    const supabase = createClient();
    await supabase.auth.signOut();
    router.replace("/login");
    router.refresh();
  }

  return (
    <header className="flex flex-wrap items-start justify-between gap-4 border-b border-zinc-200 pb-4">
      <div>
        <p className="text-sm uppercase tracking-wide text-zinc-500">
          Career Agent
        </p>
        <nav className="mt-2 flex flex-wrap gap-3 text-sm">
          {links.map((link) => (
            <Link
              key={link.key}
              href={link.href}
              className={
                active === link.key
                  ? "font-medium text-zinc-900 underline underline-offset-4"
                  : "text-zinc-600 hover:text-zinc-900"
              }
            >
              {link.label}
            </Link>
          ))}
        </nav>
      </div>
      <button
        type="button"
        onClick={() => void signOut()}
        className="rounded border border-zinc-300 px-3 py-1.5 text-sm"
      >
        Sign out
      </button>
    </header>
  );
}
