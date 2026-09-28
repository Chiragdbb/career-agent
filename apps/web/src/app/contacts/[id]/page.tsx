"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Mail, Send } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { ActionCard } from "@/components/ui/ActionCard";
import { Badge } from "@/components/ui/Badge";
import { GhostButton, GoldButton } from "@/components/ui/Button";
import { ListSkeleton } from "@/components/ui/Skeleton";
import { SoftBadge } from "@/components/ui/SoftBadge";
import { apiFetch } from "@/lib/api";
import { isDraftedOutreachStatus } from "@/lib/outreach";
import { createClient } from "@/lib/supabase/client";

type Contact = {
  id: string;
  name: string | null;
  title: string | null;
  status: string;
  company_name?: string | null;
};

type OutreachRow = {
  id: string;
  contact_id: string;
  status: string;
  subject: string | null;
};

export default function ContactDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const [contact, setContact] = useState<Contact | null>(null);
  const [outreachForContact, setOutreachForContact] = useState<OutreachRow | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const loadOutreach = useCallback(async (contactId: string) => {
    const response = await apiFetch("/api/v1/outreach");
    if (!response.ok) return null;
    const rows = (await response.json()) as OutreachRow[];
    return rows.find((r) => r.contact_id === contactId) ?? null;
  }, []);

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
        const data = (await response.json()) as Contact;
        const outreach = await loadOutreach(data.id);
        if (!cancelled) {
          setContact(data);
          setOutreachForContact(outreach);
        }
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
  }, [params.id, router, loadOutreach]);

  const name = contact?.name || "Contact";
  const initials = name
    .split(" ")
    .filter(Boolean)
    .map((p) => p[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  function openOutreach() {
    if (outreachForContact) {
      router.push(`/outreach/${outreachForContact.id}`);
      return;
    }
    router.push("/jobs");
  }

  return (
    <AppShell active="contacts" wide>
      <Link
        href="/contacts"
        className="mb-4 inline-flex items-center gap-1.5 text-sm text-text-muted hover:text-ink"
      >
        <ArrowLeft className="h-3.5 w-3.5" /> Back to contacts
      </Link>

      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      {loading ? (
        <ListSkeleton rows={3} />
      ) : contact ? (
        <div className="grid gap-6 lg:grid-cols-12">
          <div className="space-y-4 lg:col-span-8">
            <ActionCard>
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="flex items-center gap-4">
                  <div className="flex h-14 w-14 items-center justify-center rounded-full bg-lavender font-serif text-lg font-semibold text-lavender-deep">
                    {initials}
                  </div>
                  <div>
                    <h1 className="text-2xl font-bold tracking-tight text-ink">
                      {name}
                    </h1>
                    {contact.title ? (
                      <p className="text-sm text-text-muted">{contact.title}</p>
                    ) : null}
                    {contact.company_name ? (
                      <p className="text-xs text-text-faint">{contact.company_name}</p>
                    ) : null}
                    <Badge variant="default" className="mt-2 capitalize">
                      {contact.status}
                    </Badge>
                  </div>
                </div>
              </div>
            </ActionCard>

            <ActionCard>
              <p className="text-xs font-semibold uppercase tracking-wide text-text-faint">
                Details
              </p>
              <dl className="mt-3 space-y-2 text-sm">
                <div className="flex flex-col gap-1 border-b border-line py-2 sm:flex-row sm:justify-between sm:gap-4">
                  <dt className="text-text-muted">Status</dt>
                  <dd className="font-medium capitalize">{contact.status}</dd>
                </div>
              </dl>
            </ActionCard>
          </div>

          <aside className="space-y-4 lg:col-span-4">
            <ActionCard>
              <p className="text-sm font-semibold text-ink">Outreach</p>
              {outreachForContact ? (
                <>
                  <SoftBadge
                    tone={
                      isDraftedOutreachStatus(outreachForContact.status)
                        ? "ember"
                        : "lavender"
                    }
                    className="mt-2"
                  >
                    {outreachForContact.status}
                  </SoftBadge>
                  <p className="mt-2 text-sm text-text-muted">
                    {outreachForContact.subject || "Draft thread on file"}
                  </p>
                  <GoldButton
                    className="mt-4 w-full justify-center"
                    icon={Mail}
                    onClick={() => router.push(`/outreach/${outreachForContact.id}`)}
                  >
                    Open outreach thread
                  </GoldButton>
                  {isDraftedOutreachStatus(outreachForContact.status) ? (
                    <GhostButton
                      className="mt-2 w-full justify-center"
                      onClick={() => router.push("/approvals")}
                    >
                      Review in Approvals
                    </GhostButton>
                  ) : null}
                </>
              ) : (
                <>
                  <p className="mt-2 text-sm text-text-muted">
                    No draft thread yet for this person. Outreach is created from job
                    packages — discover a role first.
                  </p>
                  <GoldButton
                    className="mt-4 w-full justify-center"
                    icon={Send}
                    onClick={openOutreach}
                  >
                    Browse jobs
                  </GoldButton>
                </>
              )}
            </ActionCard>
          </aside>
        </div>
      ) : null}
    </AppShell>
  );
}
