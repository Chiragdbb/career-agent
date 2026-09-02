"use client";

import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { PageHeader } from "@/components/ui/PageHeader";
import { apiFetch } from "@/lib/api";
import { useEventStream } from "@/lib/useEventStream";
import { cn } from "@/lib/cn";

type ActivityEntry = {
  id: string;
  timestamp: string;
  entry_type: string;
  message: string;
  workflow_run_id: string | null;
  workflow_type: string | null;
  metadata: Record<string, unknown> | null;
};

export default function ActivityPage() {
  const [entries, setEntries] = useState<ActivityEntry[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    const response = await apiFetch("/api/v1/activity?limit=100");
    if (!response.ok) throw new Error(`API ${response.status}`);
    const rows = (await response.json()) as ActivityEntry[];
    setEntries(rows);
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

  return (
    <AppShell active="dashboard" wide hideActivityBar>
      <PageHeader
        title="Activity log"
        subtitle="Persistent workflow history, oldest to newest."
      />
      {loading ? (
        <p className="text-sm text-text-muted">Loading…</p>
      ) : entries.length === 0 ? (
        <p className="text-sm text-text-muted">No activity yet.</p>
      ) : (
        <div className="rounded-lg border border-line bg-paper-raised">
          <ul className="divide-y divide-line">
            {entries.map((entry) => (
              <li key={entry.id} className="px-4 py-3 text-sm">
                <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                  <time className="shrink-0 tabular-nums text-xs text-text-faint">
                    {new Date(entry.timestamp).toLocaleString()}
                  </time>
                  <span
                    className={cn(
                      "rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide",
                      entry.entry_type === "workflow_run"
                        ? "bg-teal/10 text-teal"
                        : "bg-gold/10 text-gold",
                    )}
                  >
                    {entry.entry_type.replace("_", " ")}
                  </span>
                </div>
                <p className="mt-1 text-ink">{entry.message}</p>
              </li>
            ))}
          </ul>
        </div>
      )}
    </AppShell>
  );
}
