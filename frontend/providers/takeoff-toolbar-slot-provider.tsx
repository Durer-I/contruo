"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

interface TakeoffToolbarSlotContextValue {
  slot: ReactNode;
  setTakeoffSlot: (node: ReactNode) => void;
}

const TakeoffToolbarSlotContext =
  createContext<TakeoffToolbarSlotContextValue | null>(null);

export function TakeoffToolbarSlotProvider({ children }: { children: ReactNode }) {
  const [slot, setSlotState] = useState<ReactNode>(null);
  const setTakeoffSlot = useCallback((node: ReactNode) => {
    setSlotState(node);
  }, []);
  const value = useMemo(
    () => ({ slot, setTakeoffSlot }),
    [slot, setTakeoffSlot]
  );
  return (
    <TakeoffToolbarSlotContext.Provider value={value}>
      {children}
    </TakeoffToolbarSlotContext.Provider>
  );
}

export function useTakeoffToolbarSlot() {
  const ctx = useContext(TakeoffToolbarSlotContext);
  if (!ctx) {
    throw new Error(
      "useTakeoffToolbarSlot must be used within TakeoffToolbarSlotProvider"
    );
  }
  return ctx;
}
