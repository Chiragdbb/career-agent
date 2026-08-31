"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { ContactRow } from "@/components/ui/ContactRow";
import { PageHeader } from "@/components/ui/PageHeader";
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

  return (
    <AppShell active="contacts" wide>
      <PageHeader title="Contacts" large serif subtitle="People tied to your applications — recruiters, hiring managers, referrals." />

      <SegmentedTabs
        tabs={tabs}
        active={activeTab}
        onChange={setActiveTab}
        className="mb-4"
      />

      {error ? <p className="mb-4 text-sm text-destructive">{error}</p> : null}

      {loading ? (
        <ListSkeleton />
      ) : filtered.length === 0 ? (
        <EmptyState
          title="No contacts yet"
          description="Contacts discovered during research and outreach will appear here."
        />
      ) : (
        <div className="overflow-hidden rounded-lg border border-border bg-card">
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
