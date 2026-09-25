"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { Card, CardTitle } from "@/components/ui/Card";
import { GhostButton, GoldButton } from "@/components/ui/Button";
import { ListSkeleton } from "@/components/ui/Skeleton";
import { apiFetch } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";

type ApplicationDetail = {
  id: string;
  job_title: string | null;
  company_name: string | null;
  submission_evidence?: Record<string, unknown> | null;
};

export default function ApplicationEditPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const [detail, setDetail] = useState<ApplicationDetail | null>(null);
  const [prompt, setPrompt] = useState("");
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

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
        const response = await apiFetch(`/api/v1/applications/${params.id}`);
        if (!response.ok) {
          const body = await response.json().catch(() => null);
          throw new Error(body?.error?.message || `API ${response.status}`);
        }
        const body = (await response.json()) as ApplicationDetail;
        if (cancelled) return;
        setDetail(body);
        const materials = (body.submission_evidence?.draft_materials ||
          {}) as Record<string, unknown>;
        const text =
          (typeof materials.cover_letter === "string" && materials.cover_letter) ||
          (typeof materials.content === "string" && materials.content) ||
          "";
        setDraft(text);
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
  }, [params.id, router]);

  async function rewrite() {
    if (!prompt.trim()) {
      setError("Tell us how to change the draft.");
      return;
    }
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const response = await apiFetch(
        `/api/v1/applications/${params.id}/refine`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ prompt: prompt.trim() }),
        },
      );
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.error?.message || `API ${response.status}`);
      }
      const body = (await response.json()) as {
        cover_letter?: string | null;
        content?: string | null;
      };
      setDraft(body.cover_letter || body.content || draft);
      setMessage("Draft updated. Save & back to Approvals when you’re happy.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Rewrite failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppShell active="applications" wide>
      <Link
        href={`/approvals?application=${params.id}`}
        className="mb-4 inline-block text-sm text-muted-foreground hover:text-foreground"
      >
        ← Back to Approvals
      </Link>

      {!detail && !error ? <ListSkeleton rows={3} /> : null}
      {error ? <p className="mb-4 text-sm text-destructive">{error}</p> : null}
      {message ? <p className="mb-4 text-sm text-coral">{message}</p> : null}

      {detail ? (
        <article className="space-y-6">
          <header>
            <h1 className="font-serif text-2xl text-foreground">
              Edit draft · {detail.job_title || "Application"}
            </h1>
            <p className="mt-2 text-sm text-muted-foreground">
              {detail.company_name} — tell us how to change the draft, then save.
              We won’t invent experience or metrics.
            </p>
          </header>

          <Card>
            <CardTitle>Current draft</CardTitle>
            <pre className="mt-3 whitespace-pre-wrap rounded-2xl border border-line bg-paper p-4 text-sm text-ink">
              {draft || "No draft text yet."}
            </pre>
          </Card>

          <Card>
            <CardTitle>How should we change it?</CardTitle>
            <textarea
              className="mt-3 min-h-28 w-full rounded-2xl border border-line bg-white p-3 text-sm text-ink"
              placeholder='e.g. "Make it more concise and product-led"'
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
            />
            <div className="mt-4 flex flex-wrap gap-2">
              <GoldButton disabled={busy} onClick={() => void rewrite()}>
                {busy ? "Rewriting…" : "Rewrite with this prompt"}
              </GoldButton>
              <GhostButton
                onClick={() =>
                  router.push(`/approvals?application=${params.id}`)
                }
              >
                Save &amp; back to Approvals
              </GhostButton>
            </div>
          </Card>
        </article>
      ) : null}
    </AppShell>
  );
}
