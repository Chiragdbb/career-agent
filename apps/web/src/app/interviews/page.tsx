"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { Button } from "@/components/ui/Button";
import { Card, CardTitle } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
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
    <AppShell active="interviews" wide>
      <PageHeader
        title="Interviews & offers"
        subtitle="Track rounds and offer decisions on your applications."
      />
      {error ? <p className="mb-4 text-sm text-destructive">{error}</p> : null}

      <Card className="mb-4">
        <form
          onSubmit={(e) => void onCreateInterview(e)}
          className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end"
        >
          <label className="w-full text-sm sm:w-auto sm:min-w-[12rem]">
            <span className="text-muted-foreground">Application</span>
            <select
              className="mt-1 block w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm"
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
          <label className="w-full text-sm sm:w-auto sm:min-w-[10rem]">
            <span className="text-muted-foreground">Title</span>
            <input
              className="mt-1 block w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </label>
          <Button type="submit" variant="secondary" disabled={!applicationId} className="w-full sm:w-auto">
            Add interview
          </Button>
        </form>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardTitle>Interviews</CardTitle>
          <ul className="mt-3 space-y-2 text-sm">
            {interviews.map((i) => (
              <li key={i.id} className="text-muted-foreground">
                {i.title || "Interview"} · round {i.round ?? "—"} · {i.status}
                {i.scheduled_at ? ` · ${i.scheduled_at}` : ""}
              </li>
            ))}
            {!interviews.length ? (
              <li className="text-muted-foreground">No interviews yet</li>
            ) : null}
          </ul>
        </Card>

        <Card>
          <CardTitle>Offers</CardTitle>
          <ul className="mt-3 space-y-2 text-sm">
            {offers.map((o) => (
              <li key={o.id} className="text-muted-foreground">
                {o.status}
                {o.compensation ? ` · ${o.compensation}` : ""}
                {o.location ? ` · ${o.location}` : ""}
              </li>
            ))}
            {!offers.length ? (
              <li className="text-muted-foreground">No offers yet</li>
            ) : null}
          </ul>
        </Card>
      </div>
    </AppShell>
  );
}
