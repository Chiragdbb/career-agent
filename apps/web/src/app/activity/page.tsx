"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Loader2 } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { Button } from "@/components/ui/Button";
import { PageHeader } from "@/components/ui/PageHeader";
import { ListSkeleton } from "@/components/ui/Skeleton";
import { useEventStream } from "@/lib/useEventStream";
import { cn } from "@/lib/cn";
import {
  ActivityRun,
  cancelWorkflowRun,
  fetchActivityRuns,
  formatEtaRemaining,
  formatWorkflowType,
  isActiveWorkflow,
} from "@/lib/workflows";

function statusLabel(status: string | null | undefined): string {
  if (!status) return "Unknown";
  const s = status.toLowerCase();
  if (s === "completed") return "Completed";
  if (s === "failed") return "Failed";
  if (s === "cancelled") return "Cancelled";
  if (s === "cancelling") return "Cancelling";
  if (s === "running") return "Running";
  if (s === "queued") return "Queued";
  return status;
}

function badgeClass(workflowType: string): string {
  if (workflowType === "job_discovery") return "bg-ai-subtle text-ai";
  if (workflowType === "job_rescrape") return "bg-warning-subtle text-warning";
  if (workflowType === "career_job_pipeline") return "bg-lavender text-lavender-deep";
  return "bg-muted text-muted-foreground";
}

function LiveProcessBanner({
  run,
  onCancelled,
}: {
  run: ActivityRun;
  onCancelled: () => void;
}) {
  const [cancelling, setCancelling] = useState(false);
  const [cancelError, setCancelError] = useState<string | null>(null);
  const ratio = Number(run.metadata?.progress_ratio ?? 0);
  const remainingMs = run.metadata?.eta_remaining_ms;
  const eta =
    run.eta_label ||
    formatEtaRemaining(
      typeof remainingMs === "number" ? remainingMs : undefined,
    );
  const title =
    run.human_title ||
    run.message ||
    formatWorkflowType(run.workflow_type);
  const canCancel = isActiveWorkflow(run.status);

  const handleCancel = async () => {
    if (cancelling) return;
    setCancelling(true);
    setCancelError(null);
    try {
      await cancelWorkflowRun(run.id);
      onCancelled();
    } catch (err) {
      setCancelError(err instanceof Error ? err.message : "Failed to cancel");
    } finally {
      setCancelling(false);
    }
  };

  return (
    <div className="sticky top-0 z-10 rounded-3xl border border-line bg-white p-4 shadow-soft sm:p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="mb-1.5 flex flex-wrap items-center gap-2">
            <span className="h-[7px] w-[7px] shrink-0 rounded-full bg-success shadow-[0_0_0_3px_var(--success-subtle)]" />
            <span
              className={cn(
                "rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide",
                badgeClass(run.workflow_type),
              )}
            >
              {formatWorkflowType(run.workflow_type)}
            </span>
            <span className="text-xs text-text-muted">{statusLabel(run.status)}</span>
          </div>
          <p className="text-[15px] font-bold leading-snug text-ink">{title}</p>
          <p className="mt-1 text-sm font-semibold text-coral">{eta}</p>
        </div>
        {canCancel ? (
          <Button
            type="button"
            variant="secondary"
            loading={cancelling}
            className="shrink-0 rounded-full px-3 py-1.5 text-xs"
            onClick={() => void handleCancel()}
          >
            {cancelling || run.status === "cancelling" ? "Cancelling…" : "Cancel"}
          </Button>
        ) : null}
      </div>
      {cancelError ? (
        <p className="mt-2 text-xs text-destructive">{cancelError}</p>
      ) : null}

      <div className="mt-3.5 h-1.5 overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-coral transition-[width] duration-500"
          style={{ width: `${Math.max(4, Math.min(100, ratio * 100))}%` }}
        />
      </div>

      <div className="mt-3 max-h-44 space-y-2 overflow-y-auto border-t border-line pt-3 text-sm">
        {run.steps.length === 0 ? (
          <p className="flex items-center gap-2 text-text-muted">
            <Loader2 className="h-3.5 w-3.5 animate-spin text-coral" />
            Waiting for activity…
          </p>
        ) : (
          run.steps.map((step, index) => {
            const isLatest = index === run.steps.length - 1;
            return (
              <div key={step.id} className="flex gap-2.5">
                <time className="w-10 shrink-0 tabular-nums text-[11px] text-text-faint">
                  {new Date(step.timestamp).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </time>
                <p
                  className={cn(
                    "min-w-0 leading-relaxed",
                    step.phase === "error"
                      ? "text-destructive"
                      : isLatest
                        ? "font-semibold text-ink"
                        : "text-text-muted",
                    isLatest && step.phase !== "error" && isActiveWorkflow(run.status)
                      ? "animate-pulse"
                      : null,
                  )}
                >
                  {step.message}
                </p>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

export default function ActivityPage() {
  const [runs, setRuns] = useState<ActivityRun[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    const rows = await fetchActivityRuns(100);
    setRuns(rows);
  }, []);

  useEffect(() => {
    void load().finally(() => setLoading(false));
  }, [load]);

  useEventStream({
    onEvent: (event) => {
      if (event.type === "heartbeat") return;
      void load();
    },
  });

  const activeRuns = useMemo(
    () => runs.filter((r) => isActiveWorkflow(r.status)),
    [runs],
  );
  const historyRuns = useMemo(
    () => runs.filter((r) => !isActiveWorkflow(r.status)),
    [runs],
  );

  return (
    <AppShell active="activity" wide hideActivityBar>
      <PageHeader
        title="Activity log"
        subtitle="Live processes and past requests, with human-readable steps."
      />

      {loading ? (
        <ListSkeleton rows={5} />
      ) : (
        <div className="flex flex-col gap-6">
          {activeRuns.length > 0 ? (
            <section className="space-y-3">
              {activeRuns.map((run) => (
                <LiveProcessBanner
                  key={run.id}
                  run={run}
                  onCancelled={() => void load()}
                />
              ))}
            </section>
          ) : null}

          <section>
            <h2 className="mb-3 text-sm font-bold text-ink">
              {activeRuns.length > 0 ? "Earlier" : "History"}
            </h2>
            {historyRuns.length === 0 && activeRuns.length === 0 ? (
              <p className="text-sm text-text-muted">No activity yet.</p>
            ) : historyRuns.length === 0 ? (
              <p className="text-sm text-text-muted">No earlier activity.</p>
            ) : (
              <div className="overflow-hidden rounded-3xl border border-line bg-white shadow-soft">
                <ul className="divide-y divide-line">
                  {historyRuns.map((run) => {
                    const created =
                      typeof run.metadata?.created_jobs === "number"
                        ? run.metadata.created_jobs
                        : null;
                    const summary =
                      run.workflow_type === "job_discovery" && created != null
                        ? `Found ${created} new job${created === 1 ? "" : "s"}`
                        : run.message;
                    return (
                      <li key={run.id} className="px-4 py-3.5 sm:px-5">
                        <div className="mb-1 flex flex-wrap items-center gap-2">
                          <span
                            className={cn(
                              "rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide",
                              badgeClass(run.workflow_type),
                            )}
                          >
                            {formatWorkflowType(run.workflow_type)}
                          </span>
                          {run.created_at ? (
                            <time className="text-[11px] text-text-faint">
                              {new Date(run.created_at).toLocaleString()}
                            </time>
                          ) : null}
                          <span
                            className={cn(
                              "text-[11px] font-semibold",
                              run.status === "completed"
                                ? "text-success"
                                : run.status === "failed" || run.status === "cancelled"
                                  ? "text-destructive"
                                  : "text-text-muted",
                            )}
                          >
                            {statusLabel(run.status)}
                          </span>
                        </div>
                        <p className="text-sm text-ink">
                          {run.human_title ? (
                            <span className="font-medium">{run.human_title}</span>
                          ) : null}
                          {run.human_title ? " · " : null}
                          {summary}
                        </p>
                        {run.steps.length > 0 ? (
                          <details className="mt-2">
                            <summary className="cursor-pointer text-xs font-medium text-coral">
                              Show {run.steps.length} steps
                            </summary>
                            <ul className="mt-2 space-y-1.5 border-l border-line pl-3">
                              {run.steps.map((step) => (
                                <li
                                  key={step.id}
                                  className="text-xs leading-relaxed text-text-muted"
                                >
                                  {step.message}
                                </li>
                              ))}
                            </ul>
                          </details>
                        ) : null}
                      </li>
                    );
                  })}
                </ul>
              </div>
            )}
          </section>
        </div>
      )}
    </AppShell>
  );
}
