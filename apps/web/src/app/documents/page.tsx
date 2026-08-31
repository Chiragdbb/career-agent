"use client";

import { FormEvent, Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Input } from "@/components/ui/Input";
import { PageHeader } from "@/components/ui/PageHeader";
import { ListSkeleton } from "@/components/ui/Skeleton";
import { SegmentedTabs } from "@/components/ui/SegmentedTabs";
import { apiFetch } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";

type Doc = {
  id: string;
  filename: string | null;
  status: string;
  mime_type: string | null;
};

type ResumeSummary = {
  id: string;
  name: string;
  status: string;
  parser_version: string | null;
};

type ResumeDetail = {
  id: string;
  name: string;
  status: string;
  signed_url: string | null;
  latest_version: {
    plain_text: string | null;
    parser_version: string | null;
    structured: {
      contact: { full_name: string | null; email: string | null };
      summary: string | null;
      skills: string[];
    } | null;
  } | null;
};

const tabs = [
  { id: "files" as const, label: "All files" },
  { id: "resumes" as const, label: "Resumes" },
];

function DocumentsContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const activeTab = searchParams.get("tab") === "resumes" ? "resumes" : "files";

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [docs, setDocs] = useState<Doc[]>([]);
  const [resumes, setResumes] = useState<ResumeSummary[]>([]);
  const [selectedResume, setSelectedResume] = useState<ResumeDetail | null>(null);
  const [uploading, setUploading] = useState(false);
  const [resumeName, setResumeName] = useState("");
  const [success, setSuccess] = useState<string | null>(null);

  async function loadDocs() {
    const response = await apiFetch("/api/v1/documents");
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(body?.error?.message || `API ${response.status}`);
    }
    return (await response.json()) as Doc[];
  }

  async function loadResumes() {
    const response = await apiFetch("/api/v1/resumes");
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(body?.error?.message || `API ${response.status}`);
    }
    return (await response.json()) as ResumeSummary[];
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
        const [docRows, resumeRows] = await Promise.all([loadDocs(), loadResumes()]);
        if (!cancelled) {
          setDocs(docRows);
          setResumes(resumeRows);
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
  }, [router]);

  async function onUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const fileInput = form.elements.namedItem("file") as HTMLInputElement | null;
    const file = fileInput?.files?.[0];
    if (!file) {
      setError("Choose a PDF or DOCX file first.");
      return;
    }
    setUploading(true);
    setError(null);
    setSuccess(null);
    try {
      const body = new FormData();
      body.append("file", file);
      if (resumeName.trim()) body.append("name", resumeName.trim());
      const response = await apiFetch("/api/v1/resumes", { method: "POST", body });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.error?.message || `API ${response.status}`);
      }
      const detail = (await response.json()) as ResumeDetail;
      setSelectedResume(detail);
      setSuccess(`Uploaded "${detail.name}".`);
      setResumeName("");
      form.reset();
      setResumes(await loadResumes());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  function setTab(tab: "files" | "resumes") {
    router.replace(tab === "resumes" ? "/documents?tab=resumes" : "/documents");
  }

  return (
    <>
      <PageHeader
        title="Documents"
        large
        subtitle="Resumes, cover letters, and application attachments."
      />

      <SegmentedTabs tabs={tabs} active={activeTab} onChange={setTab} className="mb-4" />

      {error ? <p className="mb-4 text-sm text-destructive">{error}</p> : null}
      {success ? <p className="mb-4 text-sm text-primary">{success}</p> : null}

      {loading ? (
        <ListSkeleton />
      ) : activeTab === "files" ? (
        docs.length === 0 ? (
          <EmptyState
            title="No documents yet"
            description="Application attachments and generated documents will appear here."
          />
        ) : (
          <div className="overflow-hidden rounded-lg border border-border bg-card">
            <ul>
              {docs.map((row) => (
                <li
                  key={row.id}
                  className="flex items-center justify-between border-b border-border px-4 py-3 last:border-0"
                >
                  <div>
                    <p className="text-sm font-medium text-foreground">
                      {row.filename || row.id}
                    </p>
                    <p className="text-xs text-muted-foreground">{row.mime_type}</p>
                  </div>
                  <Badge variant="default">{row.status}</Badge>
                </li>
              ))}
            </ul>
          </div>
        )
      ) : (
        <div className="space-y-4">
          <Card>
            <form onSubmit={(e) => void onUpload(e)} className="space-y-3">
              <Input
                label="Display name (optional)"
                value={resumeName}
                onChange={(e) => setResumeName(e.target.value)}
                placeholder="Software Engineering Master"
              />
              <label className="block text-sm">
                <span className="font-medium text-foreground">File</span>
                <input
                  name="file"
                  type="file"
                  accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                  className="mt-1 block w-full text-sm"
                />
              </label>
              <Button type="submit" disabled={uploading}>
                {uploading ? "Uploading…" : "Upload resume"}
              </Button>
            </form>
          </Card>

          {resumes.length === 0 ? (
            <EmptyState
              title="No resumes uploaded"
              description="Upload a PDF or DOCX master resume. Extracted facts become your canonical candidate source."
            />
          ) : (
            <div className="overflow-hidden rounded-lg border border-border bg-card">
              <ul>
                {resumes.map((resume) => (
                  <li key={resume.id} className="border-b border-border last:border-0">
                    <button
                      type="button"
                      className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-muted/40"
                      onClick={async () => {
                        try {
                          const res = await apiFetch(`/api/v1/resumes/${resume.id}`);
                          if (!res.ok) throw new Error("Failed to load");
                          setSelectedResume((await res.json()) as ResumeDetail);
                        } catch (err) {
                          setError(err instanceof Error ? err.message : "Failed");
                        }
                      }}
                    >
                      <span className="text-sm font-medium text-foreground">
                        {resume.name}
                      </span>
                      <Badge variant="default">{resume.status}</Badge>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {selectedResume ? (
            <Card className="text-sm">
              <h2 className="text-base font-semibold text-foreground">
                {selectedResume.name}
              </h2>
              {selectedResume.signed_url ? (
                <a
                  href={selectedResume.signed_url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-2 inline-block text-primary hover:underline"
                >
                  Open original
                </a>
              ) : null}
              {selectedResume.latest_version?.structured?.summary ? (
                <p className="mt-3 text-muted-foreground">
                  {selectedResume.latest_version.structured.summary}
                </p>
              ) : null}
            </Card>
          ) : null}
        </div>
      )}
    </>
  );
}

export default function DocumentsPage() {
  return (
    <AppShell active="documents" wide className="!max-w-none">
      <Suspense fallback={<ListSkeleton />}>
        <DocumentsContent />
      </Suspense>
    </AppShell>
  );
}
