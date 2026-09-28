"use client";

import Link from "next/link";
import { FormEvent, Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Bell, Mail } from "lucide-react";

import { SettingsLayout } from "@/components/SettingsLayout";
import { Button, GhostButton } from "@/components/ui/Button";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
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

type ProfileResponse = {
  display_name: string | null;
  headline: string | null;
  location: string | null;
  linkedin_url: string | null;
  summary: string | null;
};

const textareaClassName =
  "rounded-xl border border-line bg-paper-raised px-3 py-2 text-sm text-ink shadow-sm focus:border-coral focus:outline-none focus:ring-2 focus:ring-coral/20";

function SettingsContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const tab = searchParams.get("tab") || "notifications";

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [savingProfile, setSavingProfile] = useState(false);
  const [profile, setProfile] = useState({
    display_name: "",
    headline: "",
    location: "",
    linkedin_url: "",
    summary: "",
  });

  async function loadNotificationsAndMailbox() {
    const nRes = await apiFetch("/api/v1/notifications?status=unread");
    if (!nRes.ok) {
      const body = await nRes.json().catch(() => null);
      throw new Error(body?.error?.message || `API ${nRes.status}`);
    }
    setNotifications((await nRes.json()) as Notification[]);
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

  async function reloadTab() {
    setLoading(true);
    setError(null);
    try {
      if (tab === "profile") {
        await loadProfile();
      } else if (tab === "notifications") {
        await loadNotificationsAndMailbox();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    } finally {
      setLoading(false);
    }
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
        } else if (tab === "notifications") {
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
    if (notifications.length === 0) return;
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
      {error ? (
        <ErrorBanner message={error} onRetry={() => void reloadTab()} />
      ) : null}
      {message ? (
        <p className="mb-4 rounded-2xl border border-line bg-lavender/40 px-4 py-3 text-sm font-medium text-lavender-deep">
          {message}
        </p>
      ) : null}

      {tab === "profile" ? (
        <Card className="border-line bg-white shadow-soft">
          <h2 className="mb-1 text-base font-semibold text-ink">Profile</h2>
          <p className="mb-4 text-sm text-text-muted">
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
              <span className="font-medium text-ink">Summary</span>
              <textarea
                rows={5}
                className={textareaClassName}
                value={profile.summary}
                onChange={(e) =>
                  setProfile((p) => ({ ...p, summary: e.target.value }))
                }
              />
            </label>
            <Button type="submit" loading={savingProfile}>
              {savingProfile ? "Saving…" : "Save profile"}
            </Button>
          </form>
        </Card>
      ) : null}

      {tab === "notifications" ? (
        <Card className="border-line bg-white shadow-soft">
          <CardHeader className="mb-0">
            <CardTitle>Notifications</CardTitle>
            <Button
              variant="secondary"
              disabled={notifications.length === 0}
              onClick={() => void markAllRead()}
            >
              Mark all read
            </Button>
          </CardHeader>
          {notifications.length === 0 ? (
            <EmptyState
              icon={Bell}
              title="No unread notifications"
              description="You're all caught up. New alerts will appear here when workflows need your attention."
              primaryActionLabel="View activity"
              actionHref="/activity"
            />
          ) : (
            <ul className="space-y-3">
              {notifications.map((n) => (
                <li key={n.id} className="border-b border-line pb-3 last:border-0">
                  <p className="text-sm font-medium text-ink">{n.title}</p>
                  <p className="text-sm text-text-muted">{n.body}</p>
                </li>
              ))}
            </ul>
          )}
        </Card>
      ) : null}

      {tab === "email" ? (
        <Card className="border-line bg-white shadow-soft">
          <CardTitle className="text-ink">Email & mailbox</CardTitle>
          <p className="mt-3 text-sm text-text-muted">
            Outbound mail uses your configured sender (Resend/SMTP when keys are
            set). Inbound mailbox connect is planned — replies are not ingested in
            this release.
          </p>
          <div className="mt-4 rounded-2xl border border-dashed border-line bg-paper p-4">
            <div className="flex items-start gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-lavender text-lavender-deep">
                <Mail className="h-5 w-5" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-ink">Send from Approvals</p>
                <p className="mt-1 text-xs text-text-muted">
                  Review and approve each outreach draft before it leaves your
                  workspace. OAuth mailbox sync will land in a future release.
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <GhostButton type="button" onClick={() => router.push("/approvals")}>
                    Open approvals
                  </GhostButton>
                  <Link
                    href="/settings?tab=notifications"
                    className="inline-flex items-center rounded-full border border-line bg-white px-5 py-2.5 text-[13.5px] font-semibold text-ink transition-colors hover:bg-paper"
                  >
                    Notification settings
                  </Link>
                </div>
              </div>
            </div>
          </div>
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
