"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { useProcessActivity } from "@/hooks/useProcessActivity";
import { cn } from "@/lib/cn";
import {
  cancelWorkflowRun,
  formatEtaRemaining,
  formatWorkflowType,
  isActiveWorkflow,
  WorkflowRun,
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

function runHref(run: WorkflowRun): string {
  const meta = run.metadata || {};
  if (typeof meta.href === "string" && meta.href.startsWith("/")) return meta.href;
  const appId = meta.application_id;
  if (typeof appId === "string" && appId) {
    return `/approvals?application=${appId}`;
  }
  if (run.workflow_type === "job_discovery" || run.workflow_type === "job_rescrape") {
    return "/jobs";
  }
  if (run.workflow_type === "career_job_pipeline") {
    const paused = Boolean(meta.paused);
    if (paused) return "/approvals";
    return "/activity";
  }
  return "/activity";
}

function needsUserAction(run: WorkflowRun): boolean {
  const meta = run.metadata || {};
  return Boolean(meta.paused) || String(meta.current_step || "") === "approval_pause";
}

function dedupeRuns(runs: WorkflowRun[]): WorkflowRun[] {
  const seen = new Set<string>();
  const out: WorkflowRun[] = [];
  for (const run of runs) {
    const meta = run.metadata || {};
    const matchId = typeof meta.job_match_id === "string" ? meta.job_match_id : "";
    const key = `${run.workflow_type}:${matchId || run.id}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(run);
  }
  return out;
}

function ProcessBannerCard({
  run,
  onCancelled,
}: {
  run: WorkflowRun;
  onCancelled: () => void;
}) {
  const [cancelling, setCancelling] = useState(false);
  const [cancelError, setCancelError] = useState<string | null>(null);
  const meta = run.metadata || {};
  const ratio = Number(meta.progress_ratio ?? 0);
  const remainingMs = meta.eta_remaining_ms;
  const eta =
    (typeof meta.eta_label === "string" && meta.eta_label) ||
    formatEtaRemaining(typeof remainingMs === "number" ? remainingMs : undefined);
  const title =
    (typeof meta.human_title === "string" && meta.human_title) ||
    (typeof meta.status_message === "string" && meta.status_message) ||
    formatWorkflowType(run.workflow_type);
  const canCancel = isActiveWorkflow(run.status);
  const actionNeeded = needsUserAction(run);
  const href = runHref(run);
  const completed = Array.isArray(meta.completed_steps)
    ? (meta.completed_steps as string[])
    : [];
  const current = typeof meta.current_step === "string" ? meta.current_step : null;

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
    <div className="rounded-3xl border border-line bg-white p-4 shadow-soft sm:p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="mb-1.5 flex flex-wrap items-center gap-2">
            <span className="h-[7px] w-[7px] shrink-0 rounded-full bg-success shadow-[0_0_0_3px_var(--success-subtle)]" />
            <span className="rounded-full bg-lavender px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-lavender-deep">
              {formatWorkflowType(run.workflow_type)}
            </span>
            <span className="text-xs text-text-muted">{statusLabel(run.status)}</span>
          </div>
          <p className="text-[15px] font-bold leading-snug text-ink">{title}</p>
          <p className="mt-1 text-sm font-semibold text-coral">{eta}</p>
          {actionNeeded ? (
            <p className="mt-1 text-sm text-ink">
              Next: review the draft and Finalize.
            </p>
          ) : (
            <p className="mt-1 text-sm text-text-muted">
              We’re preparing this — you’ll get a notification when it’s ready to
              approve.
            </p>
          )}
        </div>
        <div className="flex shrink-0 flex-col items-end gap-2">
          {actionNeeded ? (
            <Link
              href={href}
              className="inline-flex rounded-full bg-coral px-3 py-1.5 text-xs font-semibold text-white hover:opacity-90"
            >
              Review &amp; approve
            </Link>
          ) : (
            <Link
              href={href}
              className="inline-flex rounded-full border border-line px-3 py-1.5 text-xs font-semibold text-ink hover:bg-paper"
            >
              Open
            </Link>
          )}
          {canCancel ? (
            <Button
              type="button"
              variant="secondary"
              loading={cancelling}
              className="rounded-full px-3 py-1.5 text-xs"
              onClick={() => void handleCancel()}
            >
              {cancelling || run.status === "cancelling" ? "Cancelling…" : "Cancel"}
            </Button>
          ) : null}
        </div>
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

      <ol className="mt-3 max-h-40 space-y-1.5 overflow-y-auto border-t border-line pt-3 text-sm">
        {(completed.length || current
          ? [
              ...completed.map((s) => ({ key: s, done: true, label: s.replace(/_/g, " ") })),
              ...(current && !completed.includes(current)
                ? [{ key: current, done: false, label: current.replace(/_/g, " ") }]
                : []),
            ]
          : []
        ).map((step) => (
          <li key={step.key} className="flex items-center gap-2">
            {step.done ? (
              <span className="text-coral">✓</span>
            ) : (
              <Loader2 className="h-3.5 w-3.5 animate-spin text-coral" />
            )}
            <span
              className={cn(
                "capitalize",
                step.done ? "text-text-muted" : "font-semibold text-ink",
              )}
            >
              {step.label}
            </span>
          </li>
        ))}
        {!completed.length && !current ? (
          <li className="flex items-center gap-2 text-text-muted">
            <Loader2 className="h-3.5 w-3.5 animate-spin text-coral" />
            Waiting for activity…
          </li>
        ) : null}
      </ol>
    </div>
  );
}

export function ProcessBanner({ className }: { className?: string }) {
  const { activeRuns, refresh } = useProcessActivity();
  const runs = useMemo(() => dedupeRuns(activeRuns), [activeRuns]);

  if (runs.length === 0) return null;

  return (
    <div className={cn("mb-4 space-y-3", className)}>
      {runs.map((run) => (
        <ProcessBannerCard key={run.id} run={run} onCancelled={() => void refresh()} />
      ))}
    </div>
  );
}
