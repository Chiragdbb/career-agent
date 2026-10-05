"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { useStreamEvent } from "@/providers/EventStreamProvider";
import {
  ActivityEvent,
  fetchWorkflowRuns,
  formatEventDetail,
  formatEventMessage,
  isActiveWorkflow,
  WorkflowRun,
} from "@/lib/workflows";

type UseProcessActivityOptions = {
  enabled?: boolean;
  pollIntervalMs?: number;
};

export type ProcessActivityState = {
  runs: WorkflowRun[];
  activeRuns: WorkflowRun[];
  recentRuns: WorkflowRun[];
  events: ActivityEvent[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  addEvent: (type: string, payload?: Record<string, unknown>) => void;
};

export function useProcessActivityState({
  enabled = true,
  pollIntervalMs = 3000,
}: UseProcessActivityOptions = {}): ProcessActivityState {
  const [runs, setRuns] = useState<WorkflowRun[]>([]);
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const eventCounter = useRef(0);

  const addEvent = useCallback((type: string, payload?: Record<string, unknown>) => {
    eventCounter.current += 1;
    const entry: ActivityEvent = {
      id: `${Date.now()}-${eventCounter.current}`,
      type,
      message: formatEventMessage(type, payload),
      timestamp: new Date(),
      phase: (payload?.phase as string) || undefined,
      step: (payload?.step as string) || undefined,
      detail: formatEventDetail(payload) || undefined,
      payload,
    };
    setEvents((prev) => [entry, ...prev].slice(0, 50));
  }, []);

  const refresh = useCallback(async () => {
    if (!enabled) return;
    try {
      const rows = await fetchWorkflowRuns({ limit: 10 });
      setRuns(rows);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load workflows");
    } finally {
      setLoading(false);
    }
  }, [enabled]);

  useStreamEvent((event) => {
    if (!enabled) return;
    if (event.type === "heartbeat") return;
    addEvent(event.type, event.payload);
    void refresh();
  });

  useEffect(() => {
    if (!enabled) return;
    void refresh();
  }, [enabled, refresh]);

  useEffect(() => {
    if (!enabled) return;
    const hasActive = runs.some((run) => isActiveWorkflow(run.status));
    if (!hasActive) return;
    const timer = setInterval(() => void refresh(), pollIntervalMs);
    return () => clearInterval(timer);
  }, [enabled, runs, pollIntervalMs, refresh]);

  const activeRuns = runs.filter((run) => isActiveWorkflow(run.status));
  const recentRuns = runs.slice(0, 5);

  return {
    runs,
    activeRuns,
    recentRuns,
    events,
    loading,
    error,
    refresh,
    addEvent,
  };
}
