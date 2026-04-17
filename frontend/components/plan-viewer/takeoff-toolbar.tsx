"use client";

import { MousePointer2, Ruler, Square, Hash, Scaling, Search } from "lucide-react";
import { cn } from "@/lib/utils";

export type TakeoffTool = "select" | "linear" | "area" | "count" | "scale";

const TOOLS: {
  id: TakeoffTool;
  label: string;
  shortcut: string;
  Icon: typeof MousePointer2;
}[] = [
  { id: "select", label: "Select", shortcut: "V", Icon: MousePointer2 },
  { id: "linear", label: "Linear", shortcut: "L", Icon: Ruler },
  { id: "area", label: "Area", shortcut: "A", Icon: Square },
  { id: "count", label: "Count", shortcut: "C", Icon: Hash },
  { id: "scale", label: "Scale", shortcut: "S", Icon: Scaling },
];

interface TakeoffToolbarProps {
  active: TakeoffTool;
  onChange: (t: TakeoffTool) => void;
  onSearchClick?: () => void;
  /** When false, scale tool is hidden (e.g. viewer role). */
  canCalibrateScale?: boolean;
}

export function TakeoffToolbar({
  active,
  onChange,
  onSearchClick,
  canCalibrateScale = true,
}: TakeoffToolbarProps) {
  const tools = canCalibrateScale ? TOOLS : TOOLS.filter((t) => t.id !== "scale");
  return (
    <div className="flex max-w-full items-center gap-0.5 overflow-x-auto rounded-3xl border border-border bg-card/80 p-0.5 shadow-sm">
      {tools.map(({ id, label, shortcut, Icon }) => (
        <button
          key={id}
          type="button"
          title={`${label} (${shortcut})`}
          onClick={() => onChange(id)}
          className={cn(
            "flex h-8 shrink-0 items-center gap-1.5 rounded-3xl px-2 text-xs font-medium transition-colors",
            active === id
              ? "bg-primary text-primary-foreground"
              : "text-muted-foreground hover:bg-surface-overlay hover:text-foreground"
          )}
        >
          <Icon className="h-3.5 w-3.5" aria-hidden />
          <span className="hidden lg:inline">{label}</span>
          <kbd className="hidden rounded bg-background/50 px-1 font-mono text-[10px] opacity-80 sm:inline">
            {shortcut}
          </kbd>
        </button>
      ))}
      {onSearchClick && (
        <button
        type="button"
        title="Search"
        aria-label="Search"
        onClick={onSearchClick}
        className="ml-1 shrink-0 rounded-2xl  px-2 py-1 text-xs text-muted-foreground hover:bg-surface-overlay hover:text-foreground flex items-center gap-1"
      >
        <Search className="h-3.5 w-3.5" aria-hidden />
        <span className="hidden lg:inline">Find</span>
        <kbd className="hidden rounded bg-background/50 px-1 font-mono text-[10px] opacity-80 sm:inline">
            Ctrl+F
          </kbd>
      </button>
      )}
    </div>
  );
}
