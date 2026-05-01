"use client";

/**
 * Plan-viewer left rail: sheet list / thumbnails for the active plan.
 *
 * Extracted from `plan-viewer-workspace.tsx` (Sprint AI-02). Adds AI-02
 * classification surface area on top of behavior-parity with the prior
 * inline JSX:
 *  - Discipline color dot + sheet-type pill per row.
 *  - Low-confidence dotted-outline indicator with tooltip.
 *  - Filter dropdown by discipline + sheet type.
 *  - Plain text search over sheet name + page number.
 *
 * Filtering, search, and view-mode state are owned LOCALLY here -- the parent
 * still owns `activeSheetId` (which is also the canvas's source of truth) and
 * `sheetStripMode` (so layout preference survives unmount). Anything purely
 * UI-internal lives here so the parent doesn't bloat with new state for
 * every iteration of the index.
 */

import { useMemo, useRef, useState, useEffect, useCallback } from "react";
import {
  LayoutGrid,
  List,
  Loader2,
  Search,
  AlertTriangle,
  Filter,
  Pencil,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  Select,
  SelectItem,
  SelectList,
  SelectPopup,
  SelectPortal,
  SelectPositioner,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "@/components/ui/sonner";
import { cn } from "@/lib/utils";
import { renameSheet } from "@/lib/sheets";
import type {
  SheetClassificationMethod,
  SheetDiscipline,
  SheetInfo,
  SheetType,
} from "@/types/project";

export type SheetStripMode = "list" | "thumbs";

export interface SheetIndexProps {
  planSheets: SheetInfo[];
  activeSheetId: string | null;
  onSheetSelect: (sheetId: string) => void;
  sheetThumbUrls: Record<string, string | null>;
  sheetThumbsLoading: boolean;
  sheetStripMode: SheetStripMode;
  onSheetStripModeChange: (mode: SheetStripMode) => void;
  /** Empty-state hint when activePlanId has no sheets yet. */
  emptyStateMessage: string;
  /** Confidence threshold below which a sheet shows the low-confidence badge. */
  lowConfidenceThreshold?: number;
  /** Gates the inline rename pencil; viewers/guests get read-only rows. */
  canEditMeasurements?: boolean;
  /**
   * Called after a successful inline rename so the parent can update its
   * project-sheets cache (the optimistic write inside this component is for
   * the row UI; the parent owns the canonical list).
   */
  onSheetRenamed?: (sheet: {
    id: string;
    sheet_name: string | null;
    sheet_name_source: "auto" | "manual" | null;
  }) => void;
}

const DEFAULT_LOW_CONFIDENCE_THRESHOLD = 0.7;

/**
 * Discipline color map. Picked from the design tokens so the dots match the
 * rest of the AI surface area (status pills, classification chips). Keep
 * synced with `backend/app/services/ai_sheet_classifier.ALL_DISCIPLINES`.
 */
const DISCIPLINE_DOT_CLASS: Record<SheetDiscipline, string> = {
  architectural: "bg-blue-500",
  structural: "bg-orange-500",
  mechanical: "bg-emerald-500",
  electrical: "bg-yellow-500",
  plumbing: "bg-cyan-500",
  civil: "bg-amber-700",
  landscape: "bg-lime-600",
  telecom: "bg-violet-500",
  fire_protection: "bg-red-600",
  interiors: "bg-pink-500",
  general: "bg-zinc-400",
  equipment: "bg-fuchsia-500",
  other: "bg-zinc-500",
};

const DISCIPLINE_LABEL: Record<SheetDiscipline, string> = {
  architectural: "Architectural",
  structural: "Structural",
  mechanical: "Mechanical",
  electrical: "Electrical",
  plumbing: "Plumbing",
  civil: "Civil",
  landscape: "Landscape",
  telecom: "Telecom",
  fire_protection: "Fire Protection",
  interiors: "Interiors",
  general: "General",
  equipment: "Equipment",
  other: "Other",
};

const SHEET_TYPE_LABEL: Record<SheetType, string> = {
  plan: "Plan",
  elevation: "Elevation",
  section: "Section",
  detail: "Detail",
  schedule: "Schedule",
  legend: "Legend",
  diagram: "Diagram",
  cover: "Cover",
  index: "Index",
  spec: "Spec",
  other: "Other",
};

const ALL_DISCIPLINES_KEY = "__all__";
const ALL_TYPES_KEY = "__all__";

function methodLabel(method: SheetClassificationMethod | null | undefined): string {
  switch (method) {
    case "lexical":
      return "Auto-classified from sheet name";
    case "vision":
      return "Auto-classified by vision model";
    case "manual":
      return "Manually classified";
    default:
      return "Not yet classified";
  }
}

export function SheetIndex({
  planSheets,
  activeSheetId,
  onSheetSelect,
  sheetThumbUrls,
  sheetThumbsLoading,
  sheetStripMode,
  onSheetStripModeChange,
  emptyStateMessage,
  lowConfidenceThreshold = DEFAULT_LOW_CONFIDENCE_THRESHOLD,
  canEditMeasurements = false,
  onSheetRenamed,
}: SheetIndexProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [disciplineFilter, setDisciplineFilter] = useState<string>(
    ALL_DISCIPLINES_KEY
  );
  const [typeFilter, setTypeFilter] = useState<string>(ALL_TYPES_KEY);
  /** Sheet id currently in inline-edit mode (null = no edit in progress). */
  const [editingSheetId, setEditingSheetId] = useState<string | null>(null);
  /**
   * Optimistic name + source overrides keyed by sheet id. Cleared once the
   * parent's refetch surfaces the canonical value (we drop the entry as soon
   * as the incoming `sheet.sheet_name` matches what we wrote). Without this
   * the row would flash back to the pre-rename name in the brief window
   * between API success and the parent refetch landing.
   */
  const [optimisticNames, setOptimisticNames] = useState<
    Record<string, { name: string; source: "manual" }>
  >({});

  // Drop optimistic entries whose canonical row already matches.
  useEffect(() => {
    setOptimisticNames((prev) => {
      const next: typeof prev = {};
      let changed = false;
      for (const sheet of planSheets) {
        const optimistic = prev[sheet.id];
        if (!optimistic) continue;
        if (
          sheet.sheet_name === optimistic.name &&
          (sheet.sheet_name_source ?? null) === optimistic.source
        ) {
          changed = true;
          continue;
        }
        next[sheet.id] = optimistic;
      }
      // Preserve identity when nothing changed so we don't churn renders.
      if (!changed && Object.keys(prev).length === Object.keys(next).length) {
        return prev;
      }
      return next;
    });
  }, [planSheets]);

  /** Saving the rename: trims, calls the API, fires onSheetRenamed for parent
   * cache updates. The row component owns the input value + Enter/Esc; this
   * is only the persistence boundary so toast + parent sync happens once. */
  const handleRenameSubmit = useCallback(
    async (sheet: SheetInfo, nextName: string) => {
      const trimmed = nextName.trim();
      if (!trimmed || trimmed === (sheet.sheet_name ?? "").trim()) {
        setEditingSheetId(null);
        return;
      }
      // Optimistic update first so the row doesn't flash the old name in
      // the gap between the API response and the parent's refetch.
      setOptimisticNames((prev) => ({
        ...prev,
        [sheet.id]: { name: trimmed, source: "manual" },
      }));
      setEditingSheetId(null);
      try {
        const updated = await renameSheet(sheet.id, trimmed);
        onSheetRenamed?.({
          id: updated.id,
          sheet_name: updated.sheet_name,
          sheet_name_source: updated.sheet_name_source ?? "manual",
        });
      } catch (err) {
        // Roll back the optimistic write + reopen the editor so the user can
        // fix the input. The toast surfaces the server message (e.g.
        // "Sheet name cannot be empty.").
        setOptimisticNames((prev) => {
          if (!(sheet.id in prev)) return prev;
          const { [sheet.id]: _drop, ...rest } = prev;
          return rest;
        });
        setEditingSheetId(sheet.id);
        const message =
          err instanceof Error ? err.message : "Failed to rename sheet";
        toast.error(message);
      }
    },
    [onSheetRenamed]
  );

  // Available filter options derived from the actual classified sheets, so
  // we never show an option that produces zero rows.
  const availableDisciplines = useMemo(() => {
    const set = new Set<SheetDiscipline>();
    for (const s of planSheets) {
      if (s.discipline) set.add(s.discipline);
    }
    return Array.from(set).sort();
  }, [planSheets]);

  const availableTypes = useMemo(() => {
    const set = new Set<SheetType>();
    for (const s of planSheets) {
      if (s.sheet_type) set.add(s.sheet_type);
    }
    return Array.from(set).sort();
  }, [planSheets]);

  const filteredSheets = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return planSheets.filter((sheet) => {
      if (
        disciplineFilter !== ALL_DISCIPLINES_KEY &&
        sheet.discipline !== disciplineFilter
      ) {
        return false;
      }
      if (typeFilter !== ALL_TYPES_KEY && sheet.sheet_type !== typeFilter) {
        return false;
      }
      if (!q) return true;
      const name = (sheet.sheet_name ?? "").toLowerCase();
      const page = String(sheet.page_number);
      return name.includes(q) || page.includes(q);
    });
  }, [planSheets, searchQuery, disciplineFilter, typeFilter]);

  // Auto-scroll the active row into view when it changes (parity with the
  // previous inline behavior driven by `sheetStripScrollRef`). RAF + smooth
  // matches the prior UX so quantities-panel "navigate to" still slides.
  useEffect(() => {
    if (!activeSheetId) return;
    const root = scrollRef.current;
    if (!root) return;
    const row = root.querySelector<HTMLElement>(
      `[data-sheet-strip-item="${CSS.escape(activeSheetId)}"]`
    );
    if (!row) return;
    const id = requestAnimationFrame(() => {
      row.scrollIntoView({ block: "nearest", behavior: "smooth" });
    });
    return () => cancelAnimationFrame(id);
  }, [activeSheetId, planSheets.length, sheetStripMode]);

  const filtersActive =
    disciplineFilter !== ALL_DISCIPLINES_KEY ||
    typeFilter !== ALL_TYPES_KEY ||
    searchQuery.trim().length > 0;
  const showFilters = availableDisciplines.length + availableTypes.length > 0;

  return (
    <>
      <div className="flex items-center justify-between gap-2 border-b border-border px-2 py-1.5">
        <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Sheets ({filteredSheets.length}
          {filteredSheets.length !== planSheets.length ? `/${planSheets.length}` : ""}
          )
        </span>
        <div className="flex shrink-0 items-center gap-0.5">
          {sheetThumbsLoading ? (
            <Loader2
              className="size-3.5 animate-spin text-muted-foreground"
              aria-hidden
            />
          ) : null}
          <div
            className="flex rounded-md border border-border bg-background p-0.5"
            role="group"
            aria-label="Sheet list layout"
          >
            <Button
              type="button"
              variant={sheetStripMode === "list" ? "secondary" : "ghost"}
              size="sm"
              className="h-7 gap-1 px-2 text-[10px]"
              onClick={() => onSheetStripModeChange("list")}
              aria-pressed={sheetStripMode === "list"}
            >
              <List className="size-3.5 shrink-0" aria-hidden />
              List
            </Button>
            <Button
              type="button"
              variant={sheetStripMode === "thumbs" ? "secondary" : "ghost"}
              size="sm"
              className="h-7 gap-1 px-2 text-[10px]"
              onClick={() => onSheetStripModeChange("thumbs")}
              aria-pressed={sheetStripMode === "thumbs"}
            >
              <LayoutGrid className="size-3.5 shrink-0" aria-hidden />
              Thumbs
            </Button>
          </div>
        </div>
      </div>

      {planSheets.length > 0 ? (
        <div className="flex flex-col gap-1.5 border-b border-border px-2 py-1.5">
          <div className="relative">
            <Search
              className="pointer-events-none absolute left-2 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground"
              aria-hidden
            />
            <Input
              type="search"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search sheets…"
              aria-label="Search sheets"
              className="h-7 pl-7 text-[11px]"
            />
          </div>
          {showFilters ? (
            <div className="flex items-center gap-1">
              <SheetClassificationFilter
                value={disciplineFilter}
                onChange={setDisciplineFilter}
                allKey={ALL_DISCIPLINES_KEY}
                allLabel="All disciplines"
                options={availableDisciplines.map((d) => ({
                  value: d,
                  label: DISCIPLINE_LABEL[d],
                }))}
                ariaLabel="Filter by discipline"
              />
              <SheetClassificationFilter
                value={typeFilter}
                onChange={setTypeFilter}
                allKey={ALL_TYPES_KEY}
                allLabel="All types"
                options={availableTypes.map((t) => ({
                  value: t,
                  label: SHEET_TYPE_LABEL[t],
                }))}
                ariaLabel="Filter by sheet type"
              />
              {filtersActive ? (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-7 px-1.5 text-[10px] text-muted-foreground"
                  onClick={() => {
                    setSearchQuery("");
                    setDisciplineFilter(ALL_DISCIPLINES_KEY);
                    setTypeFilter(ALL_TYPES_KEY);
                  }}
                >
                  Clear
                </Button>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : null}

      <div ref={scrollRef} className="min-h-0 flex-1 overflow-auto p-2">
        {planSheets.length === 0 ? (
          <p className="p-2 text-xs text-muted-foreground">{emptyStateMessage}</p>
        ) : filteredSheets.length === 0 ? (
          <p className="p-2 text-xs text-muted-foreground">
            No sheets match the current filters.
          </p>
        ) : (
          <TooltipProvider>
            <ul className="flex flex-col gap-2">
              {filteredSheets.map((sheet) => {
                const optimistic = optimisticNames[sheet.id];
                const displaySheet: SheetInfo = optimistic
                  ? {
                      ...sheet,
                      sheet_name: optimistic.name,
                      sheet_name_source: optimistic.source,
                    }
                  : sheet;
                return (
                  <SheetIndexRow
                    key={sheet.id}
                    sheet={displaySheet}
                    isActive={sheet.id === activeSheetId}
                    thumbSrc={sheet.thumbnail_url ?? sheetThumbUrls[sheet.id] ?? null}
                    thumbsLoading={sheetThumbsLoading}
                    mode={sheetStripMode}
                    lowConfidenceThreshold={lowConfidenceThreshold}
                    onSelect={() => onSheetSelect(sheet.id)}
                    canEdit={canEditMeasurements}
                    isEditing={editingSheetId === sheet.id}
                    onStartEdit={() => setEditingSheetId(sheet.id)}
                    onCancelEdit={() => setEditingSheetId(null)}
                    onSubmitEdit={(nextName) => handleRenameSubmit(sheet, nextName)}
                  />
                );
              })}
            </ul>
          </TooltipProvider>
        )}
      </div>
    </>
  );
}

interface SheetClassificationFilterProps {
  value: string;
  onChange: (value: string) => void;
  allKey: string;
  allLabel: string;
  options: { value: string; label: string }[];
  ariaLabel: string;
}

function SheetClassificationFilter({
  value,
  onChange,
  allKey,
  allLabel,
  options,
  ariaLabel,
}: SheetClassificationFilterProps) {
  if (options.length === 0) return null;
  return (
    <Select value={value} onValueChange={(val) => onChange(val as string)}>
      <SelectTrigger
        className="h-7 min-w-0 flex-1 px-2 text-[10px]"
        aria-label={ariaLabel}
      >
        <Filter className="size-3 shrink-0 opacity-60" aria-hidden />
        <SelectValue>
          {value === allKey
            ? allLabel
            : options.find((o) => o.value === value)?.label}
        </SelectValue>
      </SelectTrigger>


      {/* <SelectTrigger
        className="h-7 min-w-0 flex-1 px-2 text-[10px]"
        aria-label={ariaLabel}
      >
        <Filter className="size-3 shrink-0 opacity-60" aria-hidden />
        <SelectValue />
      </SelectTrigger> */}

      
      <SelectPortal>
        <SelectPositioner sideOffset={4}>
          <SelectPopup className="min-w-[140px]">
            <SelectList>
              <SelectItem value={allKey}>{allLabel}</SelectItem>
              {options.map((o) => (
                <SelectItem key={o.value} value={o.value}>
                  {o.label}
                </SelectItem>
              ))}
            </SelectList>
          </SelectPopup>
        </SelectPositioner>
      </SelectPortal>
    </Select>
  );
}

interface SheetIndexRowProps {
  sheet: SheetInfo;
  isActive: boolean;
  thumbSrc: string | null;
  thumbsLoading: boolean;
  mode: SheetStripMode;
  lowConfidenceThreshold: number;
  onSelect: () => void;
  canEdit: boolean;
  isEditing: boolean;
  onStartEdit: () => void;
  onCancelEdit: () => void;
  onSubmitEdit: (nextName: string) => void;
}

function SheetIndexRow({
  sheet,
  isActive,
  thumbSrc,
  thumbsLoading,
  mode,
  lowConfidenceThreshold,
  onSelect,
  canEdit,
  isEditing,
  onStartEdit,
  onCancelEdit,
  onSubmitEdit,
}: SheetIndexRowProps) {
  const scaleOk = sheet.scale_value != null;
  const scaleLine = `${
    scaleOk
      ? sheet.scale_label ??
        `${sheet.scale_value?.toPrecision(3)} ${sheet.scale_unit}/pt`
      : "Not calibrated"
  }${sheet.scale_source === "auto" ? " · Auto" : ""}`;
  const title = sheet.sheet_name ?? `Page ${sheet.page_number}`;
  const isManuallyNamed = sheet.sheet_name_source === "manual";

  const discipline = sheet.discipline ?? null;
  const sheetType = sheet.sheet_type ?? null;
  const confidence = sheet.classification_confidence ?? null;
  const isLowConfidence =
    confidence !== null &&
    sheet.classification_method !== "manual" &&
    confidence < lowConfidenceThreshold;
  const tooltipText = `${methodLabel(sheet.classification_method)}${
    confidence !== null ? ` · ${(confidence * 100).toFixed(0)}% confidence` : ""
  }`;

  return (
    <li data-sheet-strip-item={sheet.id}>
      <div
        className={cn(
          "group/sheet relative flex w-full rounded-md border p-2 text-left transition-colors",
          mode === "list"
            ? "flex-row items-center gap-2"
            : "flex-col items-start gap-1",
          isActive
            ? "border-primary bg-primary/5 ring-1 ring-primary/30"
            : "border-transparent bg-card hover:border-primary/40 hover:bg-surface-overlay",
          isLowConfidence && !isActive
            ? "border-dashed border-amber-500/40 hover:border-amber-500/60"
            : null
        )}
      >
        {/* Click-to-select target lives on the thumb / page-number column so
         * the inline-edit input below doesn't fight the row click. The whole
         * row is still keyboard-reachable via this button. */}
        <button
          type="button"
          onClick={onSelect}
          className="flex shrink-0 items-center justify-center rounded-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          aria-label={`Select ${title}`}
        >
          {mode === "thumbs" ? (
            thumbSrc ? (
              // eslint-disable-next-line @next/next/no-img-element -- signed remote URL
              <img
                src={thumbSrc}
                alt=""
                className="aspect-[4/3] w-full rounded-sm border border-border object-cover"
                loading={isActive ? "eager" : "lazy"}
                fetchPriority={isActive ? "high" : "low"}
              />
            ) : (
              <div className="flex aspect-[4/3] w-full items-center justify-center rounded-sm border border-border bg-background text-[10px] text-muted-foreground">
                {thumbsLoading ? (
                  <Loader2 className="size-5 animate-spin opacity-60" aria-hidden />
                ) : (
                  sheet.page_number
                )}
              </div>
            )
          ) : (
            <div className="flex h-10 w-8 items-center justify-center rounded-sm border border-border bg-background text-xs font-medium text-muted-foreground">
              {sheet.page_number}
            </div>
          )}
        </button>
        <div
          className={cn(
            "min-w-0",
            mode === "list" ? "flex flex-1 flex-col gap-0.5" : "w-full"
          )}
        >
          {isEditing && canEdit ? (
            <SheetNameEditor
              initialValue={sheet.sheet_name ?? ""}
              onSubmit={onSubmitEdit}
              onCancel={onCancelEdit}
            />
          ) : (
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={onSelect}
                onDoubleClick={canEdit ? onStartEdit : undefined}
                className={cn(
                  "flex min-w-0 flex-1 items-center gap-1 text-left",
                  // Match the prior single-line click target's size so the
                  // overall row height doesn't shift between view + edit.
                  "py-0.5"
                )}
                title={canEdit ? "Double-click to rename" : undefined}
              >
                <span className="line-clamp-2 min-w-0 text-[11px] font-medium leading-tight">
                  {title}
                </span>
                {isManuallyNamed ? (
                  <></>
                  // <Tooltip>
                  //   <TooltipTrigger >
                  //     <span
                  //       className="inline-block size-1.5 shrink-0 rounded-full bg-primary/70"
                  //       aria-label="Manually edited"
                  //     />
                  //   </TooltipTrigger>
                  //   <TooltipContent>Manually edited</TooltipContent>
                  // </Tooltip>
                ) : null}
              </button>
              {canEdit ? (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="size-5 shrink-0 p-0 text-muted-foreground opacity-0 transition-opacity group-hover/sheet:opacity-100 focus-visible:opacity-100"
                  onClick={(e) => {
                    e.stopPropagation();
                    onStartEdit();
                  }}
                  aria-label="Rename sheet"
                  title="Rename sheet"
                >
                  <Pencil className="size-3" aria-hidden />
                </Button>
              ) : null}
            </div>
          )}
          <span className="text-[10px] text-muted-foreground">{scaleLine}</span>
          {discipline || sheetType || isLowConfidence ? (
            <div className="mt-0.5 flex flex-wrap items-center gap-1">
              {discipline ? (
                <Tooltip>
                  <TooltipTrigger >
                    <span
                      className={cn(
                        "inline-block size-2 shrink-0 rounded-full",
                        DISCIPLINE_DOT_CLASS[discipline]
                      )}
                      aria-label={`Discipline: ${DISCIPLINE_LABEL[discipline]}`}
                    />
                  </TooltipTrigger>
                  <TooltipContent>
                    {DISCIPLINE_LABEL[discipline]}
                  </TooltipContent>
                </Tooltip>
              ) : null}
              {sheetType ? (
                <span className="rounded border border-border bg-background px-1 text-[9px] uppercase tracking-wide text-muted-foreground">
                  {SHEET_TYPE_LABEL[sheetType]}
                </span>
              ) : null}
              {isLowConfidence ? (
                <Tooltip>
                  <TooltipTrigger >
                    <span
                      className="inline-flex items-center gap-0.5 rounded border border-dashed border-amber-500/60 px-1 text-[9px] uppercase tracking-wide text-amber-500"
                      aria-label="Low classification confidence"
                    >
                      <AlertTriangle className="size-2.5" aria-hidden />
                      Low conf
                    </span>
                  </TooltipTrigger>
                  <TooltipContent>{tooltipText}</TooltipContent>
                </Tooltip>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>
    </li>
  );
}

interface SheetNameEditorProps {
  initialValue: string;
  onSubmit: (next: string) => void;
  onCancel: () => void;
}

/** Inline rename input. Auto-focuses + selects so the user can immediately
 * overwrite the name. Enter submits, Esc cancels, blur submits (matches the
 * "save on tab-away" UX users get from spreadsheets). */
function SheetNameEditor({ initialValue, onSubmit, onCancel }: SheetNameEditorProps) {
  const [value, setValue] = useState(initialValue);
  const inputRef = useRef<HTMLInputElement>(null);
  const submittedRef = useRef(false);

  useEffect(() => {
    inputRef.current?.focus();
    inputRef.current?.select();
  }, []);

  const submit = useCallback(() => {
    if (submittedRef.current) return;
    submittedRef.current = true;
    onSubmit(value);
  }, [onSubmit, value]);

  return (
    <Input
      ref={inputRef}
      value={value}
      onChange={(e) => setValue(e.target.value)}
      onKeyDown={(e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          submit();
        } else if (e.key === "Escape") {
          e.preventDefault();
          submittedRef.current = true;
          onCancel();
        }
      }}
      onBlur={submit}
      onClick={(e) => e.stopPropagation()}
      maxLength={200}
      aria-label="Sheet name"
      className="h-6 px-1.5 text-[11px]"
    />
  );
}
