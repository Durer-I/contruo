"use client";

import { TopBarCenterProvider } from "@/providers/top-bar-center-provider";
import { TakeoffToolbarSlotProvider } from "@/providers/takeoff-toolbar-slot-provider";
import { TopBar } from "./top-bar";
import { Sidebar } from "./sidebar";
import { StatusBar } from "./status-bar";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <TopBarCenterProvider>
      <TakeoffToolbarSlotProvider>
        <div className="flex h-screen flex-col overflow-hidden">
          <TopBar />
          <div className="flex flex-1 overflow-hidden">
            <Sidebar />
            <main className="flex min-h-0 flex-1 flex-col overflow-hidden">{children}</main>
          </div>
          <StatusBar />
        </div>
      </TakeoffToolbarSlotProvider>
    </TopBarCenterProvider>
  );
}
