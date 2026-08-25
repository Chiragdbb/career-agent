"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { AppNav } from "@/components/AppNav";
import { apiFetch } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";

type HumanTask = {
  id: string;
  task_type: string;
  title: string | null;
  status: string;
  details: Record<string, unknown>;
  application_id: string | null;
  outreach_id: string | null;
  workflow_run_id: string | null;
};

export default function HumanTasksPage() {
  const router = useRouter();
  const [tasks, setTasks] = useState<HumanTask[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    const response = await apiFetch("/api/v1/human-tasks?status=open");
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(body?.error?.message || `API ${response.status}`);
    }
    setTasks((await response.json()) as HumanTask[]);
  }, []);

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
        await load();
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load");
        }
      }
    }
    void init();
    return () => {
      cancelled = true;
    };
  }, [router, load]);

  async function resolveTask(taskId: string) {
    setBusyId(taskId);
    setError(null);
    try {
      const response = await apiFetch(`/api/v1/human-tasks/${taskId}/resolve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          resolution: { approved: true },
          resume_workflow: true,
          notes: "Resolved from web UI",
        }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.error?.message || `API ${response.status}`);
      }
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Resolve failed");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col gap-6 px-6 py-12">
      <AppNav active="tasks" />
      <div>
        <h1 className="text-2xl font-semibold text-zinc-900">Human tasks</h1>
        <p className="mt-2 text-sm text-zinc-600">
          Approvals, CAPTCHAs, unknown questions, and other pauses that need you.
        </p>
      </div>
      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      {tasks.length === 0 ? (
        <p className="text-sm text-zinc-600">No open tasks.</p>
      ) : (
        <ul className="space-y-3">
          {tasks.map((task) => (
            <li
              key={task.id}
              className="rounded border border-zinc-200 p-4 text-sm"
            >
              <p className="font-medium text-zinc-900">
                {task.title || task.task_type}
              </p>
              <p className="mt-1 text-zinc-600">{task.task_type}</p>
              <button
                type="button"
                className="mt-3 rounded border border-zinc-300 px-3 py-1.5"
                disabled={busyId === task.id}
                onClick={() => void resolveTask(task.id)}
              >
                {busyId === task.id ? "Resolving…" : "Resolve & resume"}
              </button>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
