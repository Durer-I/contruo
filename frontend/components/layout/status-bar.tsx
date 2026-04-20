"use client";

import { useContext } from "react";

import { StatusBarSlotContext } from "@/providers/status-bar-slot-provider";

export function StatusBar() {
  const ctx = useContext(StatusBarSlotContext);

  return (
    <footer className="flex h-7 shrink-0 items-center border-t border-border bg-surface px-4 text-xs text-muted-foreground">
      {ctx?.slot ? (
        <div className="flex min-w-0 flex-1 items-center gap-2 overflow-hidden">
          {ctx.slot}
        </div>
      ) : (
        <>
          <span>Ready</span>
          <span className="mx-2">•</span>
          <span>v0.1.0</span>
        </>
      )}
    </footer>
  );
}
