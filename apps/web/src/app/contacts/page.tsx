"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Users } from "lucide-react";

import Link from "next/link";

import { AppShell } from "@/components/AppShell";
import { ContactRow } from "@/components/ui/ContactRow";
import { HeroBand } from "@/components/ui/HeroBand";
import { PageHeader } from "@/components/ui/PageHeader";
import { SoftBadge } from "@/components/ui/SoftBadge";
import { EmptyState } from "@/components/ui/EmptyState";
import { ListSkeleton } from "@/components/ui/Skeleton";
import { SegmentedTabs } from "@/components/ui/SegmentedTabs";
import { apiFetch } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";

type Contact = { id: string; name: string | null; status: string };

const tabs = [
  { id: "all" as const, label: "All" },
  { id: "recruiters" as const, label: "Recruiters" },
  { id: "hiring" as const, label: "Hiring Managers" },
  { id: "referrals" as const, label: "Referrals" },
];

export default function ContactsPage() {
  const router = useRouter();
  const [rows, setRows] = useState<Contact[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<(typeof tabs)[number]["id"]>("all");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const supabase = createClient();
        const {
          data: { user },
        } = await supabase.auth.getUser();
        if (!user) {
          router.replace("/login");
          return;
        }
        const response = await apiFetch("/api/v1/contacts");
        if (!response.ok) {
          const body = await response.json().catch(() => null);
          throw new Error(body?.error?.message || `API ${response.status}`);
        }
        if (!cancelled) setRows((await response.json()) as Contact[]);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [router]);

  const filtered = rows.filter((row) => {
    if (activeTab === "all") return true;
    const s = row.status.toLowerCase();
    if (activeTab === "recruiters") return s.includes("recruit");
    if (activeTab === "hiring") return s.includes("hiring") || s.includes("manager");
    if (activeTab === "referrals") return s.includes("referral");
    return true;
  });

  const emptyAll = !loading && rows.length === 0;
  const emptyFilter = !loading && rows.length > 0 && filtered.length === 0;

  return (
    <AppShell active="contacts" wide>
      <HeroBand className="mb-6">
        <SoftBadge tone="lavender" className="mb-3">
          Relationship graph
        </SoftBadge>
        <PageHeader
          className="!pb-0"
          title="Contacts"
          large
          subtitle="People tied to your applications — recruiters, hiring managers, and referral paths. Open a profile to reach their outreach thread."
          actions={
            <Link
              href="/outreach"
              className="text-sm font-semibold text-coral hover:underline"
            >
              Outreach hub →
            </Link>
          }
        />
      </HeroBand>

      <SegmentedTabs
        tabs={tabs}
        active={activeTab}
        onChange={setActiveTab}
        className="mb-4"
      />

      {error ? <p className="mb-4 text-sm text-destructive">{error}</p> : null}

      {loading ? (
        <ListSkeleton />
      ) : emptyAll ? (
        <EmptyState
          icon={Users}
          title="No contacts yet"
          description="Contacts appear after job discovery and company research find real people — we never invent emails."
          primaryActionLabel="Browse jobs"
          actionHref="/jobs"
        />
      ) : emptyFilter ? (
        <EmptyState
          icon={Users}
          title="No contacts in this view"
          description="Try another tab or discover roles to grow your network."
          primaryActionLabel="Show all"
          onPrimaryAction={() => setActiveTab("all")}
        />
      ) : (
        <div className="overflow-hidden rounded-3xl border border-line bg-white shadow-soft">
          {filtered.map((row) => (
            <ContactRow
              key={row.id}
              id={row.id}
              name={row.name || "Unnamed"}
              status={row.status}
            />
          ))}
        </div>
      )}
    </AppShell>
  );
}
