"use client";

import { createContext, useContext } from "react";

import {
  useProcessActivityState,
  type ProcessActivityState,
} from "@/hooks/useProcessActivityState";

const ProcessActivityContext = createContext<ProcessActivityState | null>(null);

export function ProcessActivityProvider({ children }: { children: React.ReactNode }) {
  const value = useProcessActivityState();
  return (
    <ProcessActivityContext.Provider value={value}>
      {children}
    </ProcessActivityContext.Provider>
  );
}

export function useProcessActivity(): ProcessActivityState {
  const ctx = useContext(ProcessActivityContext);
  if (!ctx) {
    throw new Error("useProcessActivity must be used within ProcessActivityProvider");
  }
  return ctx;
}
