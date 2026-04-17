"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

interface TopBarCenterContextValue {
  center: ReactNode;
  setCenter: (node: ReactNode) => void;
}

const TopBarCenterContext = createContext<TopBarCenterContextValue | null>(
  null
);

export function TopBarCenterProvider({ children }: { children: ReactNode }) {
  const [center, setCenterState] = useState<ReactNode>(null);
  const setCenter = useCallback((node: ReactNode) => {
    setCenterState(node);
  }, []);

  const value = useMemo(
    () => ({ center, setCenter }),
    [center, setCenter]
  );

  return (
    <TopBarCenterContext.Provider value={value}>
      {children}
    </TopBarCenterContext.Provider>
  );
}

export function useTopBarCenter() {
  const ctx = useContext(TopBarCenterContext);
  if (!ctx) {
    throw new Error("useTopBarCenter must be used within TopBarCenterProvider");
  }
  return ctx;
}
