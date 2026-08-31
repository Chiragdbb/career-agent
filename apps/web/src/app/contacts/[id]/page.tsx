"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { Badge } from "@/components/ui/Badge";
import { Card, CardTitle } from "@/components/ui/Card";
import { ListSkeleton } from "@/components/ui/Skeleton";
import { apiFetch } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";

type Contact = {
  id: string;
  name: string | null;
  status: string;
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
        className="mb-4 inline-block text-sm text-muted-foreground hover:text-foreground"
      >
        ← Back to contacts
      </Link>

      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      {loading ? (
        <ListSkeleton rows={3} />
      ) : contact ? (
        <div className="space-y-4">
          <div className="flex items-center gap-4">
            <div className="flex h-14 w-14 items-center justify-center rounded-full bg-primary-subtle text-lg font-semibold text-primary">
              {initials}
            </div>
            <div>
              <h1 className="font-serif text-2xl text-foreground">{name}</h1>
              <Badge variant="default" className="mt-1 capitalize">
                {contact.status}
              </Badge>
            </div>
          </div>
          <Card>
            <CardTitle>Contact details</CardTitle>
            <dl className="mt-3 space-y-2 text-sm">
              <div className="flex flex-col gap-1 border-b border-border py-2 sm:flex-row sm:justify-between sm:gap-4">
                <dt className="text-muted-foreground">Status</dt>
                <dd className="font-medium capitalize">{contact.status}</dd>
              </div>
              <div className="flex flex-col gap-1 py-2 sm:flex-row sm:justify-between sm:gap-4">
                <dt className="text-muted-foreground">ID</dt>
                <dd className="break-all font-mono text-xs">{contact.id}</dd>
              </div>
            </dl>
          </Card>
        </div>
      ) : null}
    </AppShell>
  );
}
