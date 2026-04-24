"use client";

import {
  ChevronDown,
  Download,
  MousePointer2,
  Ruler,
  Square,
  Hash,
  Scaling,
  Search,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { ConditionInfo, MeasurementType } from "@/types/condition";

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
  /** Active takeoff condition (Sprint 07). */
  conditions?: ConditionInfo[];
  activeConditionId?: string | null;
  onConditionChange?: (id: string | null) => void;
  conditionPickerDisabled?: boolean;
  /** Quantities export (Sprint 12). */
  onExportClick?: () => void;
  canExport?: boolean;
}

export function TakeoffToolbar({
  active,
  onChange,
  onSearchClick,
  canCalibrateScale = true,
  conditions = [],
  activeConditionId = null,
  onConditionChange,
  conditionPickerDisabled,
  onExportClick,
  canExport = false,
}: TakeoffToolbarProps) {
  const tools = canCalibrateScale ? TOOLS : TOOLS.filter((t) => t.id !== "scale");
  const activeCond =
    activeConditionId == null
      ? null
      : conditions.find((c) => c.id === activeConditionId) ?? null;

  const pickCondition = (c: ConditionInfo) => {
    if (active === "linear" || active === "area" || active === "count") {
      if (c.measurement_type !== active) onChange(c.measurement_type as TakeoffTool);
    }
    onConditionChange?.(c.id);
  };

  const typeShort = (mt: MeasurementType) =>
    mt === "linear" ? "Lin" : mt === "area" ? "Area" : "Cnt";

  return (
    <div className="flex max-w-full items-center gap-0.5 overflow-x-auto rounded-3xl border border-border bg-card/80 p-0.5 shadow-sm">
      {conditions.length > 0 && onConditionChange ? (
        <DropdownMenu>
          <DropdownMenuTrigger
            type="button"
            disabled={conditionPickerDisabled}
            className={cn(
              "flex h-8 max-w-[200px] shrink-0 items-center gap-1.5 rounded-3xl border border-border bg-background px-2 text-xs font-medium",
              "text-foreground hover:bg-surface-overlay",
              conditionPickerDisabled && "pointer-events-none opacity-50"
            )}
          >
            <span
              className="h-2.5 w-2.5 shrink-0 rounded-full border border-border"
              style={{ backgroundColor: activeCond?.color ?? "#71717a" }}
            />
            <span className="min-w-0 truncate">
              {activeCond?.name ?? "No condition"}
            </span>
            <ChevronDown className="h-3.5 w-3.5 shrink-0 opacity-60" />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-56">
            <DropdownMenuGroup>
              <DropdownMenuLabel className="text-xs">Condition</DropdownMenuLabel>
              <DropdownMenuItem
                className="gap-2 text-xs text-muted-foreground"
                onClick={() => onConditionChange?.(null)}
              >
                None
              </DropdownMenuItem>
            </DropdownMenuGroup>
            <DropdownMenuSeparator />
            <DropdownMenuGroup>
              {conditions.length === 0 ? (
                <p className="px-2 py-2 text-[10px] text-muted-foreground">
                  No conditions yet. Create one in the condition panel.
                </p>
              ) : null}
              {conditions.map((c, listIdx) => {
                const showKbd = listIdx < 9;
                return (
                <DropdownMenuItem
                  key={c.id}
                  className="gap-2 text-xs"
                  onClick={() => pickCondition(c)}
                >
                  <span
                    className="h-2.5 w-2.5 shrink-0 rounded-full border border-border"
                    style={{ backgroundColor: c.color }}
                  />
                  <span className="min-w-0 flex-1 truncate">{c.name}</span>
                  <span className="shrink-0 rounded bg-muted/80 px-1 font-mono text-[9px] text-muted-foreground">
                    {typeShort(c.measurement_type)}
                  </span>
                  {showKbd ? (
                    <kbd className="ml-auto rounded bg-muted px-1 font-mono text-[10px] text-muted-foreground">
                      {listIdx + 1}
                    </kbd>
                  ) : null}
                </DropdownMenuItem>
              );
              })}
            </DropdownMenuGroup>
            {conditions.length > 9 ? (
              <p className="px-2 py-1 text-[10px] text-muted-foreground">
                Keys 1–9: first nine in this order. With Linear / Area / Count active, the tool switches to
                match the condition.
              </p>
            ) : null}
          </DropdownMenuContent>
        </DropdownMenu>
      ) : null}
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
        className="ml-1 flex shrink-0 items-center gap-1 rounded-2xl px-2 py-1 text-xs text-muted-foreground hover:bg-surface-overlay hover:text-foreground"
      >
        <Search className="h-3.5 w-3.5" aria-hidden />
        <span className="hidden lg:inline">Find</span>
        <kbd className="hidden rounded bg-background/50 px-1 font-mono text-[10px] opacity-80 sm:inline">
          Ctrl+F
        </kbd>
      </button>
      )}
      {canExport && onExportClick && (
        <button
          type="button"
          title="Export quantities"
          aria-label="Export quantities"
          onClick={onExportClick}
          className="ml-1 flex shrink-0 items-center gap-1 rounded-2xl px-2 py-1 text-xs text-muted-foreground hover:bg-surface-overlay hover:text-foreground"
        >
          <Download className="h-3.5 w-3.5" aria-hidden />
          <span className="hidden lg:inline">Export</span>
          <kbd className="hidden rounded bg-background/50 px-1 font-mono text-[10px] opacity-80 sm:inline">
            Ctrl+E
          </kbd>
        </button>
      )}
    </div>
  );
}
