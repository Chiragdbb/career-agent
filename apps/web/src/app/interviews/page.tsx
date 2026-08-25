"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { AppNav } from "@/components/AppNav";
import { apiFetch } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";

type Interview = {
  id: string;
  application_id: string;
  status: string;
  title: string | null;
  scheduled_at: string | null;
  round: number | null;
  format: string | null;
  interviewer: string | null;
};

type Offer = {
  id: string;
  application_id: string;
  status: string;
  compensation: string | null;
  equity: string | null;
  location: string | null;
  offer_deadline: string | null;
};

type Application = { id: string; job_title: string | null; company_name: string | null };

export default function InterviewsPage() {
  const router = useRouter();
  const [interviews, setInterviews] = useState<Interview[]>([]);
  const [offers, setOffers] = useState<Offer[]>([]);
  const [applications, setApplications] = useState<Application[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [applicationId, setApplicationId] = useState("");
  const [title, setTitle] = useState("Phone screen");

  async function reload() {
    const [iRes, oRes, aRes] = await Promise.all([
      apiFetch("/api/v1/interviews"),
      apiFetch("/api/v1/offers"),
      apiFetch("/api/v1/applications"),
    ]);
    if (!iRes.ok || !oRes.ok) {
      throw new Error("Failed to load interviews/offers");
    }
    setInterviews((await iRes.json()) as Interview[]);
    setOffers((await oRes.json()) as Offer[]);
    if (aRes.ok) {
      const apps = (await aRes.json()) as Application[];
      setApplications(apps);
      if (!applicationId && apps[0]) setApplicationId(apps[0].id);
    }
  }

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
        await reload();
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load");
        }
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router]);

  async function onCreateInterview(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      const response = await apiFetch("/api/v1/interviews", {
        method: "POST",
        body: JSON.stringify({
          application_id: applicationId,
          title,
          round: 1,
          format: "video",
          status: "scheduled",
        }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.error?.message || `API ${response.status}`);
      }
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create failed");
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col gap-6 px-6 py-12">
      <AppNav active="interviews" />
      <div>
        <h1 className="text-2xl font-semibold text-zinc-900">
          Interviews & offers
        </h1>
        <p className="mt-2 text-sm text-zinc-600">
          Track rounds and offer decisions on your applications.
        </p>
      </div>
      {error ? <p className="text-sm text-red-600">{error}</p> : null}

      <form
        onSubmit={(e) => void onCreateInterview(e)}
        className="flex flex-wrap items-end gap-3 rounded border border-zinc-200 p-4"
      >
        <label className="text-sm">
          <span className="text-zinc-600">Application</span>
          <select
            className="mt-1 block rounded border border-zinc-300 px-2 py-1"
            value={applicationId}
            onChange={(e) => setApplicationId(e.target.value)}
            required
          >
            {applications.map((a) => (
              <option key={a.id} value={a.id}>
                {a.job_title || a.id} {a.company_name ? `· ${a.company_name}` : ""}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          <span className="text-zinc-600">Title</span>
          <input
            className="mt-1 block rounded border border-zinc-300 px-2 py-1"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </label>
        <button
          type="submit"
          className="rounded border border-zinc-300 px-3 py-1.5 text-sm"
          disabled={!applicationId}
        >
          Add interview
        </button>
      </form>

      <section className="rounded border border-zinc-200 p-4">
        <h2 className="font-medium text-zinc-900">Interviews</h2>
        <ul className="mt-3 space-y-2 text-sm">
          {interviews.map((i) => (
            <li key={i.id}>
              {i.title || "Interview"} · round {i.round ?? "—"} · {i.status}
              {i.scheduled_at ? ` · ${i.scheduled_at}` : ""}
            </li>
          ))}
          {!interviews.length ? (
            <li className="text-zinc-500">No interviews yet</li>
          ) : null}
        </ul>
      </section>

      <section className="rounded border border-zinc-200 p-4">
        <h2 className="font-medium text-zinc-900">Offers</h2>
        <ul className="mt-3 space-y-2 text-sm">
          {offers.map((o) => (
            <li key={o.id}>
              {o.status}
              {o.compensation ? ` · ${o.compensation}` : ""}
              {o.location ? ` · ${o.location}` : ""}
            </li>
          ))}
          {!offers.length ? <li className="text-zinc-500">No offers yet</li> : null}
        </ul>
      </section>
    </main>
  );
}
