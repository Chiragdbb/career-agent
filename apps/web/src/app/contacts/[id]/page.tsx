"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Send } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { Badge } from "@/components/ui/Badge";
import { GhostButton } from "@/components/ui/Button";
import { Card, CardTitle } from "@/components/ui/Card";
import { ListSkeleton } from "@/components/ui/Skeleton";
import { apiFetch } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";

type Contact = {
  id: string;
  name: string | null;
  title: string | null;
  status: string;
  company_name?: string | null;
};

export default function ContactDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const [contact, setContact] = useState<Contact | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

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
        const response = await apiFetch(`/api/v1/contacts/${params.id}`);
        if (!response.ok) {
          const body = await response.json().catch(() => null);
          throw new Error(body?.error?.message || `API ${response.status}`);
        }
        if (!cancelled) setContact((await response.json()) as Contact);
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
  }, [params.id, router]);

  const name = contact?.name || "Contact";
  const initials = name
    .split(" ")
    .filter(Boolean)
    .map((p) => p[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return (
    <AppShell active="contacts" wide>
      <Link
        href="/contacts"
        className="mb-4 inline-block text-sm text-text-muted hover:text-foreground"
      >
        ← Back to contacts
      </Link>

      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      {loading ? (
        <ListSkeleton rows={3} />
      ) : contact ? (
        <div className="max-w-lg space-y-4">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="flex h-14 w-14 items-center justify-center rounded-full bg-gold-bg font-serif text-lg font-semibold text-[#7A551D]">
                {initials}
              </div>
              <div>
                <h1 className="font-serif text-2xl text-ink">{name}</h1>
                {contact.title ? (
                  <p className="text-sm text-text-muted">{contact.title}</p>
                ) : null}
                {contact.company_name ? (
                  <p className="text-xs text-text-faint">{contact.company_name}</p>
                ) : null}
                <Badge variant="default" className="mt-1 capitalize">
                  {contact.status}
                </Badge>
              </div>
            </div>
            <GhostButton icon={Send} onClick={() => router.push("/outreach")}>
              Draft outreach
            </GhostButton>
          </div>
          <Card>
            <CardTitle>Contact details</CardTitle>
            <dl className="mt-3 space-y-2 text-sm">
              <div className="flex flex-col gap-1 border-b border-line py-2 sm:flex-row sm:justify-between sm:gap-4">
                <dt className="text-text-muted">Status</dt>
                <dd className="font-medium capitalize">{contact.status}</dd>
              </div>
            </dl>
          </Card>
        </div>
      ) : null}
    </AppShell>
  );
}
