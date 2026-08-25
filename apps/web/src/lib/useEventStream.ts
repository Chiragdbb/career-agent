"use client";

import { useEffect, useRef } from "react";

import { createClient } from "@/lib/supabase/client";

const apiBase =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

type UseEventStreamOptions = {
  enabled?: boolean;
  onEvent?: (event: { type: string; payload?: Record<string, unknown> }) => void;
};

/**
 * Authenticated SSE via fetch + Authorization (EventSource cannot set headers).
 */
export function useEventStream({ enabled = true, onEvent }: UseEventStreamOptions) {
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();

    async function connect() {
      try {
        const supabase = createClient();
        const {
          data: { session },
        } = await supabase.auth.getSession();
        if (!session?.access_token) return;

        const response = await fetch(`${apiBase}/api/v1/events/stream`, {
          headers: { Authorization: `Bearer ${session.access_token}` },
          signal: controller.signal,
        });
        if (!response.ok || !response.body) return;

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        while (true) {
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
              // ignore
            }
          }
        }
      } catch (err) {
        if ((err as Error).name === "AbortError") return;
      }
    }

    void connect();
    return () => controller.abort();
  }, [enabled]);
}
