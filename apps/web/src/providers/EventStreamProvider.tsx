"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
} from "react";

import { useEventStream } from "@/lib/useEventStream";

export type StreamEvent = {
  type: string;
  payload?: Record<string, unknown>;
};

type Handler = (event: StreamEvent) => void;

type EventStreamContextValue = {
  subscribe: (handler: Handler) => () => void;
};

const EventStreamContext = createContext<EventStreamContextValue | null>(null);

export function EventStreamProvider({ children }: { children: React.ReactNode }) {
  const handlersRef = useRef(new Set<Handler>());

  const subscribe = useCallback((handler: Handler) => {
    handlersRef.current.add(handler);
    return () => {
      handlersRef.current.delete(handler);
    };
  }, []);

  useEventStream({
    onEvent: (event) => {
      handlersRef.current.forEach((handler) => handler(event));
    },
  });

  const value = useMemo(() => ({ subscribe }), [subscribe]);

  return (
    <EventStreamContext.Provider value={value}>{children}</EventStreamContext.Provider>
  );
}

/** Subscribe to the single shared SSE connection (workspace layout). */
export function useStreamEvent(onEvent: (event: StreamEvent) => void) {
  const ctx = useContext(EventStreamContext);
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  useEffect(() => {
    if (!ctx) {
      return;
    }
    return ctx.subscribe((event) => onEventRef.current(event));
  }, [ctx]);
}
