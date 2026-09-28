"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { GhostButton, GoldButton } from "@/components/ui/Button";
import { PageHeader } from "@/components/ui/PageHeader";
import { ScoreRing } from "@/components/ui/ScoreRing";
import { ListSkeleton } from "@/components/ui/Skeleton";
import { apiFetch } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";

type ApplicationDetail = {
  id: string;
  job_title: string | null;
  company_name: string | null;
  job_description?: string | null;
  submission_evidence?: Record<string, unknown> | null;
};

export default function ApplicationEditPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const [detail, setDetail] = useState<ApplicationDetail | null>(null);
  const [prompt, setPrompt] = useState("");
  const [draft, setDraft] = useState("");
  const [hookSubject, setHookSubject] = useState("");
  const [hookBody, setHookBody] = useState("");
  const [atsScore, setAtsScore] = useState<number | null>(null);
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
        setHookSubject(
          typeof materials.hook_subject === "string" ? materials.hook_subject : "",
        );
        setHookBody(
          typeof materials.hook_body === "string" ? materials.hook_body : "",
        );
        setAtsScore(
          typeof materials.ats_score === "number" ? materials.ats_score : null,
        );
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
      setMessage("Draft updated. Continue to Approvals when you’re happy.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Rewrite failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppShell active="applications" wide>
      <div className="mb-4 flex flex-wrap items-center gap-4">
        <Link
          href={`/applications/${params.id}`}
          className="inline-flex items-center gap-1.5 text-sm text-text-muted hover:text-ink"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Application overview
        </Link>
        <Link
          href={`/approvals?application=${params.id}`}
          className="text-sm font-semibold text-coral hover:underline"
        >
          Back to approvals
        </Link>
      </div>

      {!detail && !error ? <ListSkeleton rows={3} /> : null}
      {error ? <p className="mb-4 text-sm text-destructive">{error}</p> : null}
      {message ? <p className="mb-4 text-sm text-coral">{message}</p> : null}

      {detail ? (
        <article className="space-y-6">
          <PageHeader
            title={`Edit package · ${detail.job_title || "Application"}`}
            subtitle={`${detail.company_name || "Role"} — refine drafts against the job description. We won’t invent experience or metrics.`}
            actions={
              atsScore != null ? (
                <div className="flex items-center gap-3">
                  <ScoreRing value={atsScore} />
                  <p className="max-w-[120px] text-xs text-text-muted">
                    ATS fit vs this JD (when provided by pipeline)
                  </p>
                </div>
              ) : (
                <GhostButton
                  onClick={() => router.push(`/applications/${params.id}`)}
                >
                  View overview
                </GhostButton>
              )
            }
            className="!pb-4"
          />

          <div className="grid gap-6 lg:grid-cols-12">
            <section className="lg:col-span-5">
              <p className="text-xs font-semibold uppercase tracking-wide text-text-faint">
                Job description
              </p>
              <div className="mt-2 max-h-[70vh] overflow-y-auto whitespace-pre-wrap rounded-2xl border border-line bg-paper p-4 text-sm leading-relaxed text-ink shadow-soft">
                {detail.job_description || "No job description captured."}
              </div>
            </section>

            <section className="space-y-5 lg:col-span-7">
              {(hookSubject || hookBody) && (
                <div className="rounded-2xl border border-line bg-white p-4 shadow-card">
                  <p className="text-xs font-semibold uppercase text-text-faint">
                    Hook email
                  </p>
                  {hookSubject ? (
                    <p className="mt-2 text-sm font-semibold text-ink">
                      {hookSubject}
                    </p>
                  ) : null}
                  <pre className="mt-2 whitespace-pre-wrap text-sm text-ink">
                    {hookBody || "—"}
                  </pre>
                </div>
              )}

              <div className="rounded-2xl border border-line bg-white p-4 shadow-card">
                <p className="text-xs font-semibold uppercase tracking-wide text-text-faint">
                  Cover letter / note
                </p>
                <pre className="mt-2 whitespace-pre-wrap text-sm text-ink">
                  {draft || "No draft text yet."}
                </pre>
              </div>

              <div className="rounded-2xl border border-line bg-white p-4 shadow-card">
                <p className="text-xs font-semibold uppercase tracking-wide text-text-faint">
                  How should we change it?
                </p>
                <textarea
                  className="mt-3 min-h-28 w-full rounded-2xl border border-line bg-paper p-3 text-sm text-ink"
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
                    Back to Approvals
                  </GhostButton>
                </div>
              </div>
            </section>
          </div>
        </article>
      ) : null}
    </AppShell>
  );
}
