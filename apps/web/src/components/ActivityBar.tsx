"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  Brain,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Loader2,
  XCircle,
} from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { useProcessActivity } from "@/hooks/useProcessActivity";
import { cn } from "@/lib/cn";
import { useEventStream } from "@/lib/useEventStream";
import {
  cancelWorkflowRun,
  fetchWorkflowRun,
  fetchWorkflowTasks,
  formatWorkflowType,
  isActiveWorkflow,
  workflowStatusVariant,
  WorkflowRun,
  WorkflowTask,
} from "@/lib/workflows";

type LogEntry = {
  id: string;
  time: Date;
  message: string;
  phase: "thinking" | "working" | "result" | "error";
  step?: string;
  detail?: Record<string, unknown>;
};

function formatTime(date: Date): string {
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function formatDetail(data: Record<string, unknown>): string | null {
  const parts: string[] = [];
  if (data.provider) parts.push(`provider: ${String(data.provider)}`);
  if (data.query) parts.push(`query: “${String(data.query)}”`);
  if (data.url) parts.push(`url: ${String(data.url)}`);
  if (data.title) parts.push(`title: ${String(data.title)}`);
  if (data.company) parts.push(`company: ${String(data.company)}`);
  if (data.content_source) parts.push(`source: ${String(data.content_source)}`);
  if (data.fallback) parts.push(`fallback: ${String(data.fallback)}`);
  if (data.result_count != null) parts.push(`results: ${String(data.result_count)}`);
  if (Array.isArray(data.urls) && data.urls.length > 0) {
    parts.push(`urls: ${(data.urls as string[]).slice(0, 3).join(", ")}`);
  }
  if (data.error) parts.push(`error: ${String(data.error)}`);
  return parts.length > 0 ? parts.join(" · ") : null;
}

function phaseIcon(phase: LogEntry["phase"], active: boolean) {
  if (phase === "error") return <XCircle className="h-3.5 w-3.5 text-destructive" />;
  if (phase === "result") return <CheckCircle2 className="h-3.5 w-3.5 text-primary" />;
  if (active) return <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />;
  return <Brain className="h-3.5 w-3.5 text-muted-foreground" />;
}

function isJobDiscoveryRun(run: WorkflowRun): boolean {
  return run.workflow_type === "job_discovery";
}

function JobDiscoveryDetail({ runId }: { runId: string }) {
  const [run, setRun] = useState<WorkflowRun | null>(null);
  const [tasks, setTasks] = useState<WorkflowTask[]>([]);
  const [log, setLog] = useState<LogEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const seenRef = useRef(new Set<string>());

  const appendLog = useCallback((entry: Omit<LogEntry, "id" | "time"> & { id?: string }) => {
    const key = entry.id || `${entry.step}-${entry.message}-${entry.phase}`;
    if (seenRef.current.has(key)) return;
    seenRef.current.add(key);
    setLog((prev) => [
      ...prev,
      {
        id: key,
        time: new Date(),
        message: entry.message,
        phase: entry.phase,
        step: entry.step,
        detail: entry.detail,
      },
    ]);
  }, []);

  const refresh = useCallback(async () => {
    try {
      const [runData, taskData] = await Promise.all([
        fetchWorkflowRun(runId),
        fetchWorkflowTasks(runId),
      ]);
      setRun(runData);
      setTasks(taskData);
      setError(null);

      if (runData.metadata?.status_message) {
        appendLog({
          id: `meta-${runData.metadata.current_step}`,
          message: String(runData.metadata.status_message),
          phase: isActiveWorkflow(runData.status) ? "thinking" : "result",
          step: String(runData.metadata.current_step || ""),
        });
      }

      for (const task of taskData) {
        const input = task.input_payload || {};
        if (task.task_type === "search" && input.query) {
          appendLog({
            id: `task-search-${task.id}`,
            message:
              task.status === "failed"
                ? `Search failed for “${String(input.query)}”`
                : `Searched “${String(input.query)}”`,
            phase: task.status === "failed" ? "error" : "result",
            step: "search",
            detail: { ...input, ...(task.output_payload || {}), error: task.error },
          });
        }
        if (task.task_type === "ingest_url" && input.url) {
          const output = task.output_payload || {};
          appendLog({
            id: `task-ingest-${task.id}`,
            message:
              task.status === "failed"
                ? `Failed to process ${String(input.url)}`
                : output.title
                  ? `Extracted “${String(output.title)}”`
                  : `Processed ${String(input.url)}`,
            phase:
              task.status === "failed"
                ? "error"
                : task.status === "completed"
                  ? "result"
                  : "thinking",
            step: "ingest_url",
            detail: { ...input, ...output, error: task.error },
          });
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load progress");
    }
  }, [runId, appendLog]);

  useEventStream({
    onEvent: (event) => {
      if (event.type === "heartbeat") return;
      const payload = event.payload;
      if (payload?.workflow_run_id !== runId) return;

      if (event.type === "workflow_cancelled") {
        appendLog({
          id: `evt-cancelled-${runId}`,
          message: "Discovery cancelled",
          phase: "error",
          step: "cancelled",
        });
      }

      if (event.type === "workflow_progress" && payload.message) {
        const data = (payload.data as Record<string, unknown>) || {};
        const phase =
          (payload.phase as LogEntry["phase"]) ||
          (data.phase as LogEntry["phase"]) ||
          "thinking";
        appendLog({
          id: `evt-${payload.step}-${payload.message}-${phase}`,
          message: String(payload.message),
          phase,
          step: String(payload.step || ""),
          detail: data,
        });
      }
      void refresh();
    },
  });

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (!run || !isActiveWorkflow(run.status)) return;
    const timer = setInterval(() => void refresh(), 2000);
    return () => clearInterval(timer);
  }, [run, refresh]);

  const active = run ? isActiveWorkflow(run.status) : false;

  const handleCancel = useCallback(async () => {
    if (!active || cancelling) return;
    setCancelling(true);
    try {
      const updated = await cancelWorkflowRun(runId);
      setRun(updated);
      appendLog({
        id: `cancel-${runId}`,
        message: "Discovery cancelled",
        phase: "error",
        step: "cancelled",
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to cancel discovery");
    } finally {
      setCancelling(false);
    }
  }, [active, cancelling, runId, appendLog]);

  if (error) {
    return <p className="text-xs text-destructive">{error}</p>;
  }

  if (!run) {
    return (
      <div className="flex items-center gap-2 py-2">
        <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
        <p className="text-xs text-muted-foreground">Loading discovery progress…</p>
      </div>
    );
  }

  return (
    <div className="rounded-md border border-border bg-muted/20">
      <div className="flex items-center justify-between gap-2 border-b border-border px-3 py-2">
        <p className="text-xs font-medium text-foreground">Job discovery progress</p>
        {active ? (
          <Button
            type="button"
            variant="secondary"
            disabled={cancelling}
            className="px-2 py-1 text-[10px]"
            onClick={() => void handleCancel()}
          >
            {cancelling ? "Cancelling…" : "Cancel"}
          </Button>
        ) : null}
      </div>

      <div className="max-h-48 overflow-y-auto px-3 py-2">
        {log.length === 0 ? (
          <p className="text-xs text-muted-foreground">Waiting for activity…</p>
        ) : (
          <ul className="space-y-2">
            {log.map((entry, index) => {
              const isLatest = index === log.length - 1 && active;
              const detail = entry.detail ? formatDetail(entry.detail) : null;
              return (
                <li key={entry.id} className="flex gap-2">
                  <div className="mt-0.5 shrink-0">{phaseIcon(entry.phase, isLatest)}</div>
                  <div className="min-w-0 flex-1">
                    <p
                      className={cn(
                        "text-xs leading-relaxed",
                        entry.phase === "error" ? "text-destructive" : "text-foreground",
                        isLatest && entry.phase === "thinking" && "animate-pulse",
                      )}
                    >
                      {entry.message}
                    </p>
                    {detail ? (
                      <p className="mt-0.5 break-all text-[10px] text-muted-foreground">{detail}</p>
                    ) : null}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {run.metadata ? (
        <dl className="grid grid-cols-2 gap-x-3 gap-y-1 border-t border-border px-3 py-2 text-[10px] sm:grid-cols-4">
          {run.metadata.created_jobs != null ? (
            <>
              <dt className="text-muted-foreground">New jobs</dt>
              <dd>{String(run.metadata.created_jobs)}</dd>
            </>
          ) : null}
          {run.metadata.duplicate_jobs != null ? (
            <>
              <dt className="text-muted-foreground">Existing</dt>
              <dd>{String(run.metadata.duplicate_jobs)}</dd>
            </>
          ) : null}
          {run.metadata.urls_found != null ? (
            <>
              <dt className="text-muted-foreground">URLs found</dt>
              <dd>{String(run.metadata.urls_found)}</dd>
            </>
          ) : null}
          {run.metadata.skipped_invalid != null ? (
            <>
              <dt className="text-muted-foreground">Skipped</dt>
              <dd>{String(run.metadata.skipped_invalid)}</dd>
            </>
          ) : null}
        </dl>
      ) : null}

      {tasks.length > 0 ? (
        <p className="border-t border-border px-3 py-1.5 text-[10px] text-muted-foreground">
          {run.completed_task_count}/{run.task_count} steps
          {run.failed_task_count > 0 ? ` · ${run.failed_task_count} failed` : ""}
        </p>
      ) : null}
    </div>
  );
}

export function ActivityBar() {
  const { activeRuns, events, loading } = useProcessActivity();
  const [expanded, setExpanded] = useState(false);

  const discoveryRuns = useMemo(
    () => activeRuns.filter(isJobDiscoveryRun),
    [activeRuns],
  );

  const hasActivity = activeRuns.length > 0 || events.length > 0;
  if (loading && !hasActivity) return null;
  if (!hasActivity) return null;

  return (
    <div className="mb-4 rounded-lg border border-border bg-card">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center gap-3 px-4 py-2.5 text-left"
      >
        {activeRuns.length > 0 ? (
          <Loader2 className="h-4 w-4 shrink-0 animate-spin text-primary" />
        ) : (
          <Activity className="h-4 w-4 shrink-0 text-primary" />
        )}
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-foreground">
            {activeRuns.length > 0
              ? `${activeRuns.length} process${activeRuns.length > 1 ? "es" : ""} running`
              : "Recent activity"}
          </p>
          {activeRuns[0] ? (
            <p className="truncate text-xs text-muted-foreground">
              {(activeRuns[0].metadata?.status_message as string) ||
                `${formatWorkflowType(activeRuns[0].workflow_type)} — ${activeRuns[0].status}`}
            </p>
          ) : events[0] ? (
            <p className="truncate text-xs text-muted-foreground">{events[0].message}</p>
          ) : null}
        </div>
        {expanded ? (
          <ChevronUp className="h-4 w-4 shrink-0 text-muted-foreground" />
        ) : (
          <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
        )}
      </button>

      {expanded ? (
        <div className="border-t border-border px-4 py-3">
          {activeRuns.length > 0 ? (
            <section className="mb-4">
              <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Active processes
              </h3>
              <ul className="space-y-2">
                {activeRuns.map((run) => (
                  <li
                    key={run.id}
                    className="flex items-start justify-between gap-2 rounded-md bg-muted/40 px-3 py-2"
                  >
                    <div className="min-w-0">
                      <p className="text-xs font-medium text-foreground">
                        {formatWorkflowType(run.workflow_type)}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {(run.metadata?.status_message as string) ||
                          (run.metadata?.current_step as string) ||
                          run.status}
                      </p>
                      {run.task_count > 0 ? (
                        <p className="text-xs text-muted-foreground">
                          {run.completed_task_count}/{run.task_count} steps
                        </p>
                      ) : null}
                    </div>
                    <Badge
                      variant={workflowStatusVariant(run.status)}
                      className="shrink-0 capitalize"
                    >
                      {isActiveWorkflow(run.status) ? (
                        <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                      ) : null}
                      {run.status}
                    </Badge>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          {discoveryRuns.length > 0 ? (
            <section className="mb-4 space-y-3">
              <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Discovery details
              </h3>
              {discoveryRuns.map((run) => (
                <JobDiscoveryDetail key={run.id} runId={run.id} />
              ))}
            </section>
          ) : null}

          {events.length > 0 ? (
            <section>
              <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Activity log
              </h3>
              <ul className="max-h-48 space-y-1 overflow-y-auto">
                {events.slice(0, 15).map((event) => (
                  <li
                    key={event.id}
                    className={cn(
                      "rounded px-2 py-1.5 text-xs",
                      event.type === "workflow_failed" && "bg-destructive/5",
                    )}
                  >
                    <div className="flex items-start gap-2">
                      <span className="shrink-0 tabular-nums text-muted-foreground">
                        {formatTime(event.timestamp)}
                      </span>
                      <div className="min-w-0 flex-1">
                        <span className="text-foreground">{event.message}</span>
                        {event.detail ? (
                          <p className="mt-0.5 break-all text-[10px] text-muted-foreground">
                            {event.detail}
                          </p>
                        ) : null}
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
