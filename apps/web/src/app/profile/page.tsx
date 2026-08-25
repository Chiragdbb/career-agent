"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { AppNav } from "@/components/AppNav";
import { apiFetch } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";

type ProfileResponse = {
  id: string;
  display_name: string | null;
  headline: string | null;
  location: string | null;
  linkedin_url: string | null;
  summary: string | null;
};

export default function ProfilePage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [form, setForm] = useState({
    display_name: "",
    headline: "",
    location: "",
    linkedin_url: "",
    summary: "",
  });

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

        const response = await apiFetch("/api/v1/profile");
        if (!response.ok) {
          const body = await response.json().catch(() => null);
          throw new Error(body?.error?.message || `API ${response.status}`);
        }
        const payload = (await response.json()) as ProfileResponse;
        if (!cancelled) {
          setForm({
            display_name: payload.display_name ?? "",
            headline: payload.headline ?? "",
            location: payload.location ?? "",
            linkedin_url: payload.linkedin_url ?? "",
            summary: payload.summary ?? "",
          });
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load profile");
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

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const response = await apiFetch("/api/v1/profile", {
        method: "PUT",
        body: JSON.stringify({
          display_name: form.display_name || null,
          headline: form.headline || null,
          location: form.location || null,
          linkedin_url: form.linkedin_url || null,
          summary: form.summary || null,
        }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.error?.message || `API ${response.status}`);
      }
      setSuccess("Profile saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save profile");
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col gap-6 px-6 py-12">
      <AppNav active="profile" />

      <div>
        <h1 className="text-2xl font-semibold text-zinc-900">Profile</h1>
        <p className="mt-2 text-sm text-zinc-600">
          Your canonical candidate profile used for applications and outreach.
        </p>
      </div>

      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      {success ? <p className="text-sm text-green-700">{success}</p> : null}

      {loading ? (
        <p className="text-sm text-zinc-500">Loading…</p>
      ) : (
        <form onSubmit={(e) => void onSubmit(e)} className="space-y-4">
          <label className="block text-sm">
            <span className="font-medium text-zinc-800">Display name</span>
            <input
              className="mt-1 w-full rounded border border-zinc-300 px-3 py-2"
              value={form.display_name}
              onChange={(e) =>
                setForm((f) => ({ ...f, display_name: e.target.value }))
              }
            />
          </label>
          <label className="block text-sm">
            <span className="font-medium text-zinc-800">Headline</span>
            <input
              className="mt-1 w-full rounded border border-zinc-300 px-3 py-2"
              value={form.headline}
              onChange={(e) =>
                setForm((f) => ({ ...f, headline: e.target.value }))
              }
            />
          </label>
          <label className="block text-sm">
            <span className="font-medium text-zinc-800">Location</span>
            <input
              className="mt-1 w-full rounded border border-zinc-300 px-3 py-2"
              value={form.location}
              onChange={(e) =>
                setForm((f) => ({ ...f, location: e.target.value }))
              }
            />
          </label>
          <label className="block text-sm">
            <span className="font-medium text-zinc-800">LinkedIn URL</span>
            <input
              className="mt-1 w-full rounded border border-zinc-300 px-3 py-2"
              placeholder="https://linkedin.com/in/you"
              value={form.linkedin_url}
              onChange={(e) =>
                setForm((f) => ({ ...f, linkedin_url: e.target.value }))
              }
            />
          </label>
          <label className="block text-sm">
            <span className="font-medium text-zinc-800">Summary</span>
            <textarea
              rows={5}
              className="mt-1 w-full rounded border border-zinc-300 px-3 py-2"
              value={form.summary}
              onChange={(e) =>
                setForm((f) => ({ ...f, summary: e.target.value }))
              }
            />
          </label>
          <button
            type="submit"
            disabled={saving}
            className="rounded bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
          >
            {saving ? "Saving…" : "Save profile"}
          </button>
        </form>
      )}
    </main>
  );
}
