"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { Search } from "lucide-react";

import { cn } from "@/lib/cn";

const JUMP_TARGETS = [
  { href: "/dashboard", label: "Today", keywords: "dashboard overview home" },
  { href: "/jobs", label: "Opportunities", keywords: "jobs roles search" },
  { href: "/approvals", label: "Approvals", keywords: "tasks seal approve" },
  { href: "/outreach", label: "Conversations", keywords: "outreach messages" },
  { href: "/applications", label: "Applications", keywords: "pipeline board" },
  { href: "/interviews", label: "Interviews", keywords: "prep cockpit" },
  { href: "/preferences", label: "Preferences", keywords: "discover wizard" },
  { href: "/documents", label: "Documents", keywords: "resumes files" },
  { href: "/contacts", label: "Contacts", keywords: "network people" },
  { href: "/analytics", label: "Analytics", keywords: "metrics charts" },
  { href: "/settings", label: "Settings", keywords: "profile account" },
  { href: "/activity", label: "Activity", keywords: "log history" },
];

type CommandPaletteProps = {
  open: boolean;
  onClose: () => void;
};

export function CommandPalette({ open, onClose }: CommandPaletteProps) {
  const router = useRouter();
  const [query, setQuery] = useState("");

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return JUMP_TARGETS;
    return JUMP_TARGETS.filter(
      (t) =>
        t.label.toLowerCase().includes(q) ||
        t.keywords.includes(q) ||
        t.href.includes(q),
    );
  }, [query]);

  useEffect(() => {
    if (!open) setQuery("");
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-start justify-center bg-ink/30 px-4 pt-[12vh] backdrop-blur-sm">
      <button
        type="button"
        className="absolute inset-0 cursor-default"
        aria-label="Close command palette"
        onClick={onClose}
      />
      <div className="relative z-10 w-full max-w-lg overflow-hidden rounded-2xl border border-line bg-white shadow-card">
        <div className="flex items-center gap-2 border-b border-line px-4 py-3">
          <Search className="h-4 w-4 text-text-faint" />
          <input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Jump to role, note, or prompt…"
            className="flex-1 bg-transparent text-sm text-ink outline-none placeholder:text-text-faint"
            onKeyDown={(e) => {
              if (e.key === "Enter" && results[0]) {
                router.push(results[0].href);
                onClose();
              }
            }}
          />
          <kbd className="rounded-md border border-line bg-paper px-1.5 py-0.5 text-[10px] font-semibold text-text-faint">
            esc
          </kbd>
        </div>
        <ul className="max-h-72 overflow-y-auto p-2">
          {results.length === 0 ? (
            <li className="px-3 py-4 text-sm text-text-muted">No matches</li>
          ) : (
            results.map((item) => (
              <li key={item.href}>
                <Link
                  href={item.href}
                  onClick={onClose}
                  className={cn(
                    "flex items-center justify-between rounded-xl px-3 py-2.5 text-sm text-ink",
                    "hover:bg-lavender/60",
                  )}
                >
                  <span className="font-medium">{item.label}</span>
                  <span className="text-xs text-text-faint">{item.href}</span>
                </Link>
              </li>
            ))
          )}
        </ul>
      </div>
    </div>
  );
}
