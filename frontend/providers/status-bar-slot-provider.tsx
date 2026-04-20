"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

interface StatusBarSlotContextValue {
  slot: ReactNode;
  setStatusBarSlot: (node: ReactNode) => void;
}

export const StatusBarSlotContext =
  createContext<StatusBarSlotContextValue | null>(null);

export function StatusBarSlotProvider({ children }: { children: ReactNode }) {
  const [slot, setSlotState] = useState<ReactNode>(null);
  const setStatusBarSlot = useCallback((node: ReactNode) => {
    setSlotState(node);
  }, []);
  const value = useMemo(
    () => ({ slot, setStatusBarSlot }),
    [slot, setStatusBarSlot]
  );
  return (
    <StatusBarSlotContext.Provider value={value}>
      {children}
    </StatusBarSlotContext.Provider>
  );
}

export function useStatusBarSlot() {
  const ctx = useContext(StatusBarSlotContext);
  if (!ctx) {
    throw new Error(
      "useStatusBarSlot must be used within StatusBarSlotProvider"
    );
  }
  return ctx;
}
