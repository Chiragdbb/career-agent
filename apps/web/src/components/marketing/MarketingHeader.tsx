"use client";

import Link from "next/link";
import { Menu, X } from "lucide-react";
import { useEffect, useState } from "react";

import { TrailMark } from "@/components/ui/Illustrations";

const links = [
  { href: "#demo", label: "Demo" },
  { href: "#features", label: "Features" },
  { href: "#how-it-works", label: "How it works" },
  { href: "#pricing", label: "Pricing" },
];

export function MarketingHeader() {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    function onScroll() {
      setScrolled(window.scrollY > 8);
    }
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header
      className={`sticky top-0 z-50 transition-[background,box-shadow,border-color] duration-300 ${
        scrolled
          ? "border-b border-mkt-hairline/80 bg-white/85 shadow-[0_8px_30px_-20px_rgba(12,18,34,0.35)] backdrop-blur-md"
          : "border-b border-transparent bg-transparent"
      }`}
    >
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-4 sm:px-6 lg:px-8">
        <Link href="/" className="flex min-w-0 items-center gap-2.5">
          <TrailMark size={30} />
          <span className="truncate text-[15px] font-bold tracking-[-0.02em] text-mkt-ink">
            Waypoint
          </span>
        </Link>

        <nav className="hidden items-center gap-8 lg:flex" aria-label="Primary">
          {links.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="text-sm font-medium text-mkt-muted transition-colors hover:text-mkt-ink"
            >
              {link.label}
            </a>
          ))}
        </nav>

        <div className="hidden items-center gap-2 sm:flex">
          <Link
            href="/login"
            className="rounded-full px-4 py-2 text-sm font-medium text-mkt-ink hover:bg-mkt-canvas-soft"
          >
            Sign in
          </Link>
          <Link
            href="/signup"
            className="rounded-full bg-mkt-indigo px-4 py-2 text-sm font-semibold text-white shadow-[0_12px_28px_-16px_rgba(85,81,255,0.9)] transition-transform hover:translate-y-[-1px] hover:bg-mkt-indigo-deep active:translate-y-0"
          >
            Start free trial
          </Link>
        </div>

        <button
          type="button"
          className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-mkt-hairline text-mkt-ink lg:hidden"
          aria-expanded={open}
          aria-label={open ? "Close menu" : "Open menu"}
          onClick={() => setOpen((v) => !v)}
        >
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>

      {open ? (
        <div className="border-t border-mkt-hairline bg-white px-4 py-4 lg:hidden">
          <nav className="flex flex-col gap-1" aria-label="Mobile">
            {links.map((link) => (
              <a
                key={link.href}
                href={link.href}
                className="rounded-lg px-3 py-2.5 text-sm font-medium text-mkt-ink hover:bg-mkt-canvas-soft"
                onClick={() => setOpen(false)}
              >
                {link.label}
              </a>
            ))}
            <Link
              href="/login"
              className="mt-2 rounded-lg px-3 py-2.5 text-sm font-medium text-mkt-muted"
              onClick={() => setOpen(false)}
            >
              Sign in
            </Link>
            <Link
              href="/signup"
              className="mt-1 rounded-full bg-mkt-indigo px-4 py-2.5 text-center text-sm font-semibold text-white"
              onClick={() => setOpen(false)}
            >
              Start free trial
            </Link>
          </nav>
        </div>
      ) : null}
    </header>
  );
}
