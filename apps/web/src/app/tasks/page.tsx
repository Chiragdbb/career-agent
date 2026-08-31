"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ListSkeleton } from "@/components/ui/Skeleton";
import { PageHeader } from "@/components/ui/PageHeader";
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
  const [loading, setLoading] = useState(true);
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
      } finally {
        if (!cancelled) setLoading(false);
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
    <AppShell active="automations">
      <PageHeader
        title="Automations"
        subtitle="Approvals, CAPTCHAs, unknown questions, and other pauses that need you."
      />
      {error ? <p className="mb-4 text-sm text-destructive">{error}</p> : null}
      {loading ? (
        <ListSkeleton rows={3} />
      ) : tasks.length === 0 ? (
        <EmptyState
          title="No open automations"
          description="Human-in-the-loop tasks will appear here when workflows need your input."
        />
      ) : (
        <ul className="space-y-3">
          {tasks.map((task) => (
            <Card key={task.id}>
              <p className="text-sm font-medium text-foreground">
                {task.title || task.task_type}
              </p>
              <p className="mt-1 text-sm text-muted-foreground">{task.task_type}</p>
              <Button
                variant="secondary"
                className="mt-3"
                disabled={busyId === task.id}
                onClick={() => void resolveTask(task.id)}
              >
                {busyId === task.id ? "Resolving…" : "Resolve & resume"}
              </Button>
            </Card>
          ))}
        </ul>
      )}
    </AppShell>
  );
}
