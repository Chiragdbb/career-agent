"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { AppNav } from "@/components/AppNav";
import { apiFetch } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";

type ResumeSummary = {
  id: string;
  name: string;
  status: string;
  parser_version: string | null;
  created_at: string | null;
};

type StructuredResume = {
  contact: {
    full_name: string | null;
    email: string | null;
    phone: string | null;
    location: string | null;
    linkedin_url: string | null;
  };
  summary: string | null;
  experience: Array<{
    title: string | null;
    company: string | null;
    start_date: string | null;
    end_date: string | null;
    bullets: string[];
  }>;
  projects: Array<{ name: string | null; description: string | null }>;
  education: Array<{
    institution: string | null;
    degree: string | null;
  }>;
  skills: string[];
  certifications: Array<{ name: string | null; issuer: string | null }>;
  parser_version: string;
};

type ResumeDetail = {
  id: string;
  name: string;
  status: string;
  signed_url: string | null;
  latest_version: {
    id: string;
    plain_text: string | null;
    parser_version: string | null;
    structured: StructuredResume | null;
    document: {
      filename: string | null;
      mime_type: string | null;
    } | null;
  } | null;
};

export default function ResumesPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [resumes, setResumes] = useState<ResumeSummary[]>([]);
  const [selected, setSelected] = useState<ResumeDetail | null>(null);
  const [name, setName] = useState("");

  async function loadList() {
    const response = await apiFetch("/api/v1/resumes");
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(body?.error?.message || `API ${response.status}`);
    }
    setResumes((await response.json()) as ResumeSummary[]);
  }

  async function loadDetail(resumeId: string) {
    const response = await apiFetch(`/api/v1/resumes/${resumeId}`);
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(body?.error?.message || `API ${response.status}`);
    }
    setSelected((await response.json()) as ResumeDetail);
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
        await loadList();
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load resumes");
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
      if (name.trim()) body.append("name", name.trim());

      const response = await apiFetch("/api/v1/resumes", {
        method: "POST",
        body,
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.error?.message || `API ${response.status}`);
      }
      const detail = (await response.json()) as ResumeDetail;
      setSelected(detail);
      setSuccess(`Uploaded “${detail.name}”.`);
      setName("");
      form.reset();
      await loadList();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  const structured = selected?.latest_version?.structured;

  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col gap-6 px-6 py-12">
      <AppNav active="resumes" />

      <div>
        <h1 className="text-2xl font-semibold text-zinc-900">Resumes</h1>
        <p className="mt-2 text-sm text-zinc-600">
          Upload a PDF or DOCX master resume. Extracted text and structured
          facts become the canonical candidate source — nothing is invented.
        </p>
      </div>

      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      {success ? <p className="text-sm text-green-700">{success}</p> : null}

      <form
        onSubmit={(e) => void onUpload(e)}
        className="space-y-3 rounded border border-zinc-200 p-4"
      >
        <label className="block text-sm">
          <span className="font-medium text-zinc-800">Display name (optional)</span>
          <input
            className="mt-1 w-full rounded border border-zinc-300 px-3 py-2"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Software Engineering Master"
          />
        </label>
        <label className="block text-sm">
          <span className="font-medium text-zinc-800">File</span>
          <input
            name="file"
            type="file"
            accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            className="mt-1 block w-full text-sm"
          />
        </label>
        <button
          type="submit"
          disabled={uploading}
          className="rounded bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
        >
          {uploading ? "Uploading…" : "Upload resume"}
        </button>
      </form>

      {loading ? (
        <p className="text-sm text-zinc-500">Loading…</p>
      ) : (
        <section className="space-y-2">
          <h2 className="text-sm font-medium text-zinc-900">Your resumes</h2>
          {resumes.length === 0 ? (
            <p className="text-sm text-zinc-500">No resumes uploaded yet.</p>
          ) : (
            <ul className="divide-y divide-zinc-200 rounded border border-zinc-200">
              {resumes.map((resume) => (
                <li key={resume.id}>
                  <button
                    type="button"
                    className="flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-zinc-50"
                    onClick={() => void loadDetail(resume.id).catch((err) => {
                      setError(err instanceof Error ? err.message : "Failed to load");
                    })}
                  >
                    <span className="font-medium text-zinc-900">{resume.name}</span>
                    <span className="text-xs text-zinc-500">{resume.status}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {selected ? (
        <section className="space-y-4 rounded border border-zinc-200 p-4 text-sm">
          <div>
            <h2 className="text-base font-semibold text-zinc-900">{selected.name}</h2>
            <p className="mt-1 text-zinc-500">
              Parser {selected.latest_version?.parser_version ?? "—"} ·{" "}
              {selected.latest_version?.document?.filename ?? "no file"}
            </p>
            {selected.signed_url ? (
              <a
                href={selected.signed_url}
                target="_blank"
                rel="noreferrer"
                className="mt-2 inline-block text-zinc-800 underline underline-offset-2"
              >
                Open original (signed URL)
              </a>
            ) : null}
          </div>

          {structured ? (
            <div className="space-y-3">
              <div>
                <h3 className="font-medium text-zinc-900">Contact</h3>
                <p className="mt-1 text-zinc-700">
                  {[structured.contact.full_name, structured.contact.email, structured.contact.phone]
                    .filter(Boolean)
                    .join(" · ") || "—"}
                </p>
              </div>
              {structured.summary ? (
                <div>
                  <h3 className="font-medium text-zinc-900">Summary</h3>
                  <p className="mt-1 whitespace-pre-wrap text-zinc-700">
                    {structured.summary}
                  </p>
                </div>
              ) : null}
              {structured.skills.length > 0 ? (
                <div>
                  <h3 className="font-medium text-zinc-900">Skills</h3>
                  <p className="mt-1 text-zinc-700">{structured.skills.join(", ")}</p>
                </div>
              ) : null}
              {structured.experience.length > 0 ? (
                <div>
                  <h3 className="font-medium text-zinc-900">Experience</h3>
                  <ul className="mt-1 space-y-2">
                    {structured.experience.map((item, index) => (
                      <li key={`${item.company}-${index}`} className="text-zinc-700">
                        <p className="font-medium">
                          {[item.title, item.company].filter(Boolean).join(" @ ") || "Role"}
                        </p>
                        <p className="text-xs text-zinc-500">
                          {[item.start_date, item.end_date || "Present"]
                            .filter(Boolean)
                            .join(" – ")}
                        </p>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </div>
          ) : null}

          {selected.latest_version?.plain_text ? (
            <details>
              <summary className="cursor-pointer font-medium text-zinc-900">
                Extracted text
              </summary>
              <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap rounded bg-zinc-50 p-3 text-xs text-zinc-700">
                {selected.latest_version.plain_text}
              </pre>
            </details>
          ) : null}
        </section>
      ) : null}
    </main>
  );
}
