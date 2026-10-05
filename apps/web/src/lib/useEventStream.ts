"use client";

import { useEffect, useRef } from "react";

import { createClient } from "@/lib/supabase/client";

const apiBase =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

const INITIAL_BACKOFF_MS = 1_000;
const MAX_BACKOFF_MS = 30_000;

type UseEventStreamOptions = {
  enabled?: boolean;
  onEvent?: (event: { type: string; payload?: Record<string, unknown> }) => void;
};

/**
 * Authenticated SSE via fetch + Authorization (EventSource cannot set headers).
 * Reconnects with exponential backoff after disconnects or errors.
 */
export function useEventStream({ enabled = true, onEvent }: UseEventStreamOptions) {
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    let closed = false;
    let backoffMs = INITIAL_BACKOFF_MS;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

    async function connect() {
      if (closed) return;
      try {
        const supabase = createClient();
        const {
          data: { session },
        } = await supabase.auth.getSession();
        if (!session?.access_token || closed) return;

        const response = await fetch(`${apiBase}/api/v1/events/stream`, {
          headers: { Authorization: `Bearer ${session.access_token}` },
          signal: controller.signal,
        });
        if (!response.ok || !response.body) {
          scheduleReconnect();
          return;
        }

        backoffMs = INITIAL_BACKOFF_MS;
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        while (!closed) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const chunks = buffer.split("\n\n");
          buffer = chunks.pop() || "";
          for (const chunk of chunks) {
            const line = chunk
              .split("\n")
              .find((l) => l.startsWith("data: "));
            if (!line) continue;
            try {
              const data = JSON.parse(line.slice(6)) as {
                type: string;
                payload?: Record<string, unknown>;
              };
              onEventRef.current?.(data);
            } catch {
              // ignore malformed frames
            }
          }
        }
        if (!closed) scheduleReconnect();
      } catch (err) {
        if ((err as Error).name === "AbortError" || closed) return;
        scheduleReconnect();
      }
    }

    function scheduleReconnect() {
      if (closed || controller.signal.aborted) return;
      if (reconnectTimer != null) return;
      const delay = backoffMs;
      backoffMs = Math.min(MAX_BACKOFF_MS, backoffMs * 2);
      reconnectTimer = setTimeout(() => {
        reconnectTimer = null;
        void connect();
      }, delay);
    }

    void connect();
    return () => {
      closed = true;
      if (reconnectTimer != null) clearTimeout(reconnectTimer);
      controller.abort();
    };
  }, [enabled]);
}
