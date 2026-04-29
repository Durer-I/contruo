"use client";

import { useEffect, useState } from "react";
import { TopBarCenterProvider } from "@/providers/top-bar-center-provider";
import { TakeoffToolbarSlotProvider } from "@/providers/takeoff-toolbar-slot-provider";
import { StatusBarSlotProvider } from "@/providers/status-bar-slot-provider";
import { TopBar } from "./top-bar";
import { Sidebar } from "./sidebar";
import { StatusBar } from "./status-bar";
import { useAuth } from "@/providers/auth-provider";
import { cn } from "@/lib/utils";

function DesktopViewportWarning() {
  // Design system minimum is 1280×720; warn anything below that.
  const [narrow, setNarrow] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 1279px)");
    const apply = () => setNarrow(mq.matches);
    apply();
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  }, []);
  if (!narrow) return null;
  return (
    <div
      className="shrink-0 border-b border-amber-500/40 bg-amber-500/15 px-3 py-2 text-center text-xs text-amber-950 dark:text-amber-100"
      role="status"
    >
      Contruo is built for desktop estimating. For the intended layout, use a window at least{" "}
      <strong>1280px</strong> wide (larger is better).
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const banner = user?.billing_banner;
  const seatOverage = user?.seat_overage;

  return (
    <TopBarCenterProvider>
      <TakeoffToolbarSlotProvider>
        <StatusBarSlotProvider>
          <div className="flex h-screen flex-col overflow-hidden">
            <TopBar />
            {banner ? (
              <div
                className={cn(
                  "shrink-0 border-b px-4 py-2 text-center text-sm",
                  seatOverage
                    ? "border-rose-500/40 bg-rose-500/10 text-rose-950 dark:text-rose-100"
                    : "border-amber-500/40 bg-amber-500/10 text-amber-950 dark:text-amber-100"
                )}
                role="status"
              >
                {banner}
              </div>
            ) : null}
            <div className="flex flex-1 overflow-hidden">
              <Sidebar />
              <main className="flex min-h-0 flex-1 flex-col overflow-hidden">
                <DesktopViewportWarning />
                {children}
              </main>
            </div>
            <StatusBar />
          </div>
        </StatusBarSlotProvider>
      </TakeoffToolbarSlotProvider>
    </TopBarCenterProvider>
  );
}
