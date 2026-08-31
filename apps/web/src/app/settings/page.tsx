"use client";

import { FormEvent, Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { SettingsLayout } from "@/components/SettingsLayout";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Input } from "@/components/ui/Input";
import { ListSkeleton } from "@/components/ui/Skeleton";
import { apiFetch } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";

type Notification = {
  id: string;
  title: string | null;
  body: string | null;
  status: string;
};

type Mailbox = {
  provider: string;
  status: string;
  email_address: string | null;
  has_encrypted_token: boolean;
  error: string | null;
};

type ProfileResponse = {
  display_name: string | null;
  headline: string | null;
  location: string | null;
  linkedin_url: string | null;
  summary: string | null;
};

function SettingsContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const tab = searchParams.get("tab") || "notifications";

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [mailbox, setMailbox] = useState<Mailbox | null>(null);
  const [savingProfile, setSavingProfile] = useState(false);
  const [profile, setProfile] = useState({
    display_name: "",
    headline: "",
    location: "",
    linkedin_url: "",
    summary: "",
  });

  async function loadNotificationsAndMailbox() {
    const [nRes, mRes] = await Promise.all([
      apiFetch("/api/v1/notifications?status=unread"),
      apiFetch("/api/v1/settings/mailbox"),
    ]);
    if (!nRes.ok) {
      const body = await nRes.json().catch(() => null);
      throw new Error(body?.error?.message || `API ${nRes.status}`);
    }
    setNotifications((await nRes.json()) as Notification[]);
    if (mRes.ok) setMailbox((await mRes.json()) as Mailbox);
  }

  async function loadProfile() {
    const response = await apiFetch("/api/v1/profile");
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(body?.error?.message || `API ${response.status}`);
    }
    const payload = (await response.json()) as ProfileResponse;
    setProfile({
      display_name: payload.display_name ?? "",
      headline: payload.headline ?? "",
      location: payload.location ?? "",
      linkedin_url: payload.linkedin_url ?? "",
      summary: payload.summary ?? "",
    });
  }

  useEffect(() => {
    let cancelled = false;
    async function init() {
      try {
        const supabase = createClient();
        const {
          data: { user },
        } = await supabase.auth.getUser();
        if (!user) {
          router.replace("/login");
          return;
        }
        if (tab === "profile") {
          await loadProfile();
        } else {
          await loadNotificationsAndMailbox();
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void init();
    return () => {
      cancelled = true;
    };
  }, [router, tab]);

  async function markAllRead() {
    setError(null);
    setMessage(null);
    try {
      const response = await apiFetch("/api/v1/notifications/read-all", {
        method: "POST",
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.error?.message || `API ${response.status}`);
      }
      setMessage("Marked all notifications read");
      await loadNotificationsAndMailbox();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    }
  }

  async function onSaveProfile(event: FormEvent) {
    event.preventDefault();
    setSavingProfile(true);
    setError(null);
    setMessage(null);
    try {
      const response = await apiFetch("/api/v1/profile", {
        method: "PUT",
        body: JSON.stringify({
          display_name: profile.display_name || null,
          headline: profile.headline || null,
          location: profile.location || null,
          linkedin_url: profile.linkedin_url || null,
          summary: profile.summary || null,
        }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.error?.message || `API ${response.status}`);
      }
      setMessage("Profile saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save profile");
    } finally {
      setSavingProfile(false);
    }
  }

  if (loading) return <ListSkeleton rows={4} />;

  return (
    <>
      {error ? <p className="mb-4 text-sm text-destructive">{error}</p> : null}
      {message ? <p className="mb-4 text-sm text-primary">{message}</p> : null}

      {tab === "profile" ? (
        <Card>
          <h2 className="mb-1 text-base font-semibold text-foreground">Profile</h2>
          <p className="mb-4 text-sm text-muted-foreground">
            Your canonical candidate profile used for applications and outreach.
          </p>
          <form onSubmit={(e) => void onSaveProfile(e)} className="space-y-4">
            <Input
              label="Display name"
              value={profile.display_name}
              onChange={(e) =>
                setProfile((p) => ({ ...p, display_name: e.target.value }))
              }
            />
            <Input
              label="Headline"
              value={profile.headline}
              onChange={(e) =>
                setProfile((p) => ({ ...p, headline: e.target.value }))
              }
            />
            <Input
              label="Location"
              value={profile.location}
              onChange={(e) =>
                setProfile((p) => ({ ...p, location: e.target.value }))
              }
            />
            <Input
              label="LinkedIn URL"
              placeholder="https://linkedin.com/in/you"
              value={profile.linkedin_url}
              onChange={(e) =>
                setProfile((p) => ({ ...p, linkedin_url: e.target.value }))
              }
            />
            <label className="flex flex-col gap-1.5 text-sm">
              <span className="font-medium text-foreground">Summary</span>
              <textarea
                rows={5}
                className="rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-ring/30"
                value={profile.summary}
                onChange={(e) =>
                  setProfile((p) => ({ ...p, summary: e.target.value }))
                }
              />
            </label>
            <Button type="submit" disabled={savingProfile}>
              {savingProfile ? "Saving…" : "Save profile"}
            </Button>
          </form>
        </Card>
      ) : null}

      {tab === "notifications" ? (
        <Card>
          <CardHeader className="mb-0">
            <CardTitle>Notifications</CardTitle>
            <Button variant="secondary" onClick={() => void markAllRead()}>
              Mark all read
            </Button>
          </CardHeader>
          {notifications.length === 0 ? (
            <EmptyState
              title="No unread notifications"
              description="You're all caught up. New alerts will appear here."
            />
          ) : (
            <ul className="space-y-3">
              {notifications.map((n) => (
                <li key={n.id} className="border-b border-border pb-3 last:border-0">
                  <p className="text-sm font-medium text-foreground">{n.title}</p>
                  <p className="text-sm text-muted-foreground">{n.body}</p>
                </li>
              ))}
            </ul>
          )}
        </Card>
      ) : null}

      {tab === "email" ? (
        <Card>
          <CardTitle>Email & mailbox</CardTitle>
          {mailbox ? (
            <dl className="mt-3 space-y-2 text-sm">
              <div className="flex justify-between border-b border-border py-2">
                <dt className="text-muted-foreground">Provider</dt>
                <dd className="font-medium capitalize">{mailbox.provider}</dd>
              </div>
              <div className="flex justify-between border-b border-border py-2">
                <dt className="text-muted-foreground">Status</dt>
                <dd className="font-medium capitalize">{mailbox.status}</dd>
              </div>
              <div className="flex justify-between py-2">
                <dt className="text-muted-foreground">Email</dt>
                <dd className="font-medium">{mailbox.email_address || "—"}</dd>
              </div>
            </dl>
          ) : (
            <p className="mt-2 text-sm text-muted-foreground">Loading…</p>
          )}
          <p className="mt-4 text-xs text-muted-foreground">
            Gmail/Outlook OAuth is stubbed — connect in a later step.
          </p>
        </Card>
      ) : null}
    </>
  );
}

export default function SettingsPage() {
  return (
    <SettingsLayout>
      <Suspense fallback={<ListSkeleton rows={4} />}>
        <SettingsContent />
      </Suspense>
    </SettingsLayout>
  );
}
