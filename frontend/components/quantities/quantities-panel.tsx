"use client";

import { useVirtualizer } from "@tanstack/react-virtual";
import {
  ChevronDown,
  ChevronRight,
  Loader2,
  PenLine,
  PencilLine,
  RotateCcw,
  Trash2,
} from "lucide-react";
import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { formatAreaQuantity } from "@/lib/area-geometry";
import { formatLength } from "@/lib/linear-geometry";
import {
  effectiveQuantity,
  formatEffectiveQuantity,
  sumEffectiveQuantities,
} from "@/lib/quantity-display";
import { cn } from "@/lib/utils";
import type { ConditionInfo } from "@/types/condition";
import type {
  DerivedQuantityInfo,
  LinearDeductionPolyline,
  MeasurementInfo,
} from "@/types/measurement";
import type { SheetInfo } from "@/types/project";

export type QuantitiesPanelHandle = {
  expandAll: () => void;
  collapseAll: () => void;
};

type FlatRow =
  | { kind: "condition"; id: string; condition: ConditionInfo; depth: 0 }
  | {
      kind: "sheet";
      id: string;
      conditionId: string;
      sheet: SheetInfo;
      sheetSubtotal: number;
      depth: 1;
    }
  | { kind: "measurement"; measurement: MeasurementInfo; depth: 2 }
  | {
      kind: "assembly";
      measurementId: string;
      item: DerivedQuantityInfo;
      depth: 3;
    };

function sheetLabel(sheet: SheetInfo): string {
  return sheet.sheet_name ?? `Page ${sheet.page_number}`;
}

function aggregateAssemblyTotals(
  measurements: MeasurementInfo[],
  conditionId: string
): Array<{ name: string; unit: string; sum: number }> {
  const map = new Map<string, { name: string; unit: string; sum: number }>();
  for (const m of measurements) {
    if (m.condition_id !== conditionId) continue;
    for (const d of m.derived_quantities ?? []) {
      if (d.value == null || Number.isNaN(d.value)) continue;
      const cur = map.get(d.assembly_item_id) ?? {
        name: d.name,
        unit: d.unit,
        sum: 0,
      };
      cur.sum += d.value;
      map.set(d.assembly_item_id, cur);
    }
  }
  return [...map.values()].sort((a, b) => a.name.localeCompare(b.name));
}

export interface QuantitiesPanelProps {
  measurements: MeasurementInfo[];
  conditions: ConditionInfo[];
  sheets: SheetInfo[];
  loading: boolean;
  activeSheetId: string | null;
  selectedIds: Set<string>;
  /** Single click on a measurement row (not ctrl). */
  onMeasurementSelect: (id: string, modifiers: { ctrlKey: boolean; metaKey: boolean }) => void;
  /** Navigate to measurement on plan (switch sheet, pan/zoom). */
  onNavigateToMeasurement: (m: MeasurementInfo) => void;
  onUpdateMeasurement: (
    id: string,
    patch: {
      override_value?: number | null;
      deductions?: LinearDeductionPolyline[];
      label?: string | null;
    }
  ) => Promise<void>;
  onDeleteMeasurement: (id: string) => Promise<void>;
  onReassignCondition: (id: string, conditionId: string) => Promise<void>;
  /** Start drawing deduction segments for a linear measurement (plan workspace). */
  onStartDeductionEdit?: (measurementId: string) => void;
  canEdit: boolean;
}

const ROW_H = 28;

export const QuantitiesPanel = forwardRef<QuantitiesPanelHandle, QuantitiesPanelProps>(
  function QuantitiesPanel(
    {
      measurements,
      conditions,
      sheets,
      loading,
      activeSheetId,
      selectedIds,
      onMeasurementSelect,
      onNavigateToMeasurement,
      onUpdateMeasurement,
      onDeleteMeasurement,
      onReassignCondition,
      canEdit,
    },
    ref
  ) {
  const sheetById = useMemo(() => new Map(sheets.map((s) => [s.id, s])), [sheets]);

  const sortedConditions = useMemo(() => {
    return [...conditions].sort((a, b) => {
      if (a.sort_order !== b.sort_order) return a.sort_order - b.sort_order;
      return a.name.localeCompare(b.name);
    });
  }, [conditions]);

  const [expandedConds, setExpandedConds] = useState<Set<string>>(() => new Set());
  const [expandedSheets, setExpandedSheets] = useState<Set<string>>(() => new Set());
  const [expandedMeas, setExpandedMeas] = useState<Set<string>>(() => new Set());

  useEffect(() => {
    setExpandedConds((prev) => {
      const next = new Set(prev);
      for (const c of sortedConditions) {
        if (!next.has(c.id)) next.add(c.id);
      }
      return next;
    });
  }, [sortedConditions]);

  useEffect(() => {
    if (!activeSheetId) return;
    const keys: string[] = [];
    for (const m of measurements) {
      if (m.sheet_id === activeSheetId) {
        keys.push(`${m.condition_id}:${activeSheetId}`);
      }
    }
    setExpandedSheets((prev) => {
      const next = new Set(prev);
      for (const k of keys) next.add(k);
      return next;
    });
  }, [activeSheetId, measurements]);

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState("");
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameDraft, setRenameDraft] = useState("");
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const renameBlurSkipRef = useRef(false);
  const renameSubmitLockRef = useRef(false);
  const [ctx, setCtx] = useState<{ x: number; y: number; measurementId: string } | null>(
    null
  );

  const parentRef = useRef<HTMLDivElement>(null);

  const flatRows = useMemo((): FlatRow[] => {
    const out: FlatRow[] = [];
    const byCondition = (cid: string) => measurements.filter((m) => m.condition_id === cid);

    for (const cond of sortedConditions) {
      const ms = byCondition(cond.id);
      if (ms.length === 0) continue;

      out.push({
        kind: "condition",
        id: cond.id,
        condition: cond,
        depth: 0,
      });
      if (!expandedConds.has(cond.id)) continue;

      const sheetIds = [...new Set(ms.map((m) => m.sheet_id))].sort((a, b) => {
        const sa = sheetById.get(a);
        const sb = sheetById.get(b);
        const pa = sa?.page_number ?? 0;
        const pb = sb?.page_number ?? 0;
        if (pa !== pb) return pa - pb;
        return a.localeCompare(b);
      });

      for (const sid of sheetIds) {
        const sh = sheetById.get(sid);
        if (!sh) continue;
        const inSheet = ms.filter((m) => m.sheet_id === sid);
        const sub = inSheet.reduce((a, m) => a + effectiveQuantity(m), 0);
        const sk = `${cond.id}:${sid}`;
        out.push({
          kind: "sheet",
          id: sk,
          conditionId: cond.id,
          sheet: sh,
          sheetSubtotal: sub,
          depth: 1,
        });
        if (!expandedSheets.has(sk)) continue;

        for (const m of inSheet) {
          out.push({ kind: "measurement", measurement: m, depth: 2 });
          if (expandedMeas.has(m.id)) {
            for (const item of m.derived_quantities ?? []) {
              out.push({
                kind: "assembly",
                measurementId: m.id,
                item,
                depth: 3,
              });
            }
          }
        }
      }
    }
    return out;
  }, [measurements, sortedConditions, sheetById, expandedConds, expandedSheets, expandedMeas]);

  const rowIndexByMeasurementId = useMemo(() => {
    const map = new Map<string, number>();
    flatRows.forEach((r, i) => {
      if (r.kind === "measurement") map.set(r.measurement.id, i);
    });
    return map;
  }, [flatRows]);

  const virtualizer = useVirtualizer({
    count: flatRows.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => ROW_H,
    overscan: 12,
  });

  const primarySelected = [...selectedIds][selectedIds.size - 1] ?? [...selectedIds][0];

  useLayoutEffect(() => {
    if (!primarySelected) return;
    const idx = rowIndexByMeasurementId.get(primarySelected);
    if (idx == null) return;
    virtualizer.scrollToIndex(idx, { align: "auto" });
  }, [primarySelected, rowIndexByMeasurementId, virtualizer, flatRows.length]);

  useEffect(() => {
    const close = () => setCtx(null);
    window.addEventListener("click", close);
    return () => window.removeEventListener("click", close);
  }, []);

  const toggleCond = useCallback((id: string) => {
    setExpandedConds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const toggleSheet = useCallback((id: string) => {
    setExpandedSheets((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const toggleMeasAsm = useCallback((id: string) => {
    setExpandedMeas((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const expandAll = useCallback(() => {
    const condIds = new Set<string>();
    const sheetKeys = new Set<string>();
    for (const cond of sortedConditions) {
      const ms = measurements.filter((m) => m.condition_id === cond.id);
      if (ms.length === 0) continue;
      condIds.add(cond.id);
      for (const sid of new Set(ms.map((m) => m.sheet_id))) {
        sheetKeys.add(`${cond.id}:${sid}`);
      }
    }
    const measIds = new Set(
      measurements
        .filter((m) => (m.derived_quantities?.length ?? 0) > 0)
        .map((m) => m.id)
    );
    setExpandedConds(condIds);
    setExpandedSheets(sheetKeys);
    setExpandedMeas(measIds);
  }, [sortedConditions, measurements]);

  const collapseAll = useCallback(() => {
    setExpandedConds(new Set());
    setExpandedSheets(new Set());
    setExpandedMeas(new Set());
  }, []);

  useImperativeHandle(
    ref,
    () => ({
      expandAll,
      collapseAll,
    }),
    [expandAll, collapseAll]
  );

  const startEdit = useCallback((m: MeasurementInfo) => {
    if (!canEdit) return;
    const cond = conditions.find((c) => c.id === m.condition_id);
    if (!cond) return;
    setRenamingId(null);
    setEditingId(m.id);
    setEditDraft(String(effectiveQuantity(m)));
  }, [canEdit, conditions]);

  const startRename = useCallback((m: MeasurementInfo) => {
    if (!canEdit) return;
    setEditingId(null);
    setRenamingId(m.id);
    setRenameDraft(m.label?.trim() ?? "");
  }, [canEdit]);

  const submitRename = useCallback(
    async (id: string, draft: string) => {
      if (renameSubmitLockRef.current) return;
      renameSubmitLockRef.current = true;
      try {
        const trimmed = draft.trim();
        const nextLabel = trimmed.length === 0 ? null : trimmed.slice(0, 255);
        const prev = measurements.find((x) => x.id === id)?.label ?? null;
        const prevNorm = (prev && prev.trim()) || null;
        if (prevNorm !== nextLabel) {
          await onUpdateMeasurement(id, { label: nextLabel });
        }
      } catch {
        //
      } finally {
        setRenamingId(null);
        requestAnimationFrame(() => {
          renameSubmitLockRef.current = false;
        });
      }
    },
    [measurements, onUpdateMeasurement]
  );

  const commitEdit = useCallback(async () => {
    if (!editingId) return;
    const n = Number(editDraft.replace(/,/g, ""));
    if (!Number.isFinite(n)) {
      setEditingId(null);
      return;
    }
    try {
      await onUpdateMeasurement(editingId, { override_value: n });
    } finally {
      setEditingId(null);
    }
  }, [editingId, editDraft, onUpdateMeasurement]);

  const resetOverride = useCallback(
    async (id: string) => {
      await onUpdateMeasurement(id, { override_value: null });
      setCtx(null);
    },
    [onUpdateMeasurement]
  );

  if (loading) {
    return (
      <div className="flex flex-1 items-center justify-center gap-2 p-4 text-xs text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading quantities…
      </div>
    );
  }

  if (conditions.length === 0 || measurements.length === 0) {
    return (
      <div className="p-3 text-xs leading-relaxed text-muted-foreground">
        No measurements yet. Pick a condition, choose a tool, and draw on the plan.
      </div>
    );
  }

  return (
    <TooltipProvider delay={300}>
      <div className="flex min-h-0 flex-1 flex-col">
        <div
          ref={parentRef}
          className="min-h-0 flex-1 overflow-auto text-[11px] leading-tight"
        >
          <div
            className="relative w-full"
            style={{ height: `${virtualizer.getTotalSize()}px` }}
          >
            {virtualizer.getVirtualItems().map((vRow) => {
              const row = flatRows[vRow.index];
              if (!row) return null;
              const pad = (d: number) => (d === 0 ? "pl-1" : d === 1 ? "pl-4" : d === 2 ? "pl-7" : "pl-10");

              if (row.kind === "condition") {
                const c = row.condition;
                const ms = measurements.filter((m) => m.condition_id === c.id);
                const grand = sumEffectiveQuantities(measurements, c);
                const scaleU = ms[0] ? sheetById.get(ms[0].sheet_id)?.scale_unit : undefined;
                const grandLabel =
                  c.measurement_type === "count"
                    ? Math.round(grand).toLocaleString()
                    : c.measurement_type === "area"
                      ? formatAreaQuantity(grand, c.unit)
                      : formatLength(grand, scaleU, c.unit);
                const asmTot = aggregateAssemblyTotals(measurements, c.id);
                const asmHint =
                  asmTot.length > 0
                    ? asmTot.map((x) => `${x.name}: ${x.sum.toFixed(2)} ${x.unit}`).join(" · ")
                    : "";
                return (
                  <div
                    key={`cond-${row.id}`}
                    className={cn(
                      "absolute left-0 top-0 flex w-full items-center gap-1 border-b border-border/60 bg-muted/30 py-0.5 pr-1",
                      pad(0)
                    )}
                    style={{ height: ROW_H, transform: `translateY(${vRow.start}px)` }}
                  >
                    <button
                      type="button"
                      className="flex shrink-0 items-center justify-center rounded p-0.5 hover:bg-muted"
                      onClick={() => toggleCond(c.id)}
                      aria-expanded={expandedConds.has(c.id)}
                    >
                      {expandedConds.has(c.id) ? (
                        <ChevronDown className="h-3.5 w-3.5" />
                      ) : (
                        <ChevronRight className="h-3.5 w-3.5" />
                      )}
                    </button>
                    <span
                      className="h-2.5 w-2.5 shrink-0 rounded-full border border-border"
                      style={{ backgroundColor: c.color }}
                    />
                    <span className="min-w-0 flex-1 truncate font-medium text-foreground">
                      {c.name}
                    </span>
                    <Tooltip>
                      <TooltipTrigger className="shrink-0 font-mono text-[10px] text-muted-foreground">
                        {grandLabel}
                      </TooltipTrigger>
                      {asmHint ? (
                        <TooltipContent side="left" className="max-w-xs text-[10px]">
                          Assembly roll-up: {asmHint}
                        </TooltipContent>
                      ) : null}
                    </Tooltip>
                  </div>
                );
              }

              if (row.kind === "sheet") {
                const c = conditions.find((x) => x.id === row.conditionId);
                if (!c) return null;
                return (
                  <div
                    key={`sheet-${row.id}`}
                    className={cn(
                      "absolute left-0 top-0 flex w-full items-center gap-1 border-b border-border/40 py-0.5 pr-1",
                      pad(1),
                      row.sheet.id === activeSheetId ? "bg-primary/5" : ""
                    )}
                    style={{ height: ROW_H, transform: `translateY(${vRow.start}px)` }}
                  >
                    <button
                      type="button"
                      className="flex shrink-0 items-center justify-center rounded p-0.5 hover:bg-muted"
                      onClick={() => toggleSheet(row.id)}
                    >
                      {expandedSheets.has(row.id) ? (
                        <ChevronDown className="h-3 w-3" />
                      ) : (
                        <ChevronRight className="h-3 w-3" />
                      )}
                    </button>
                    <span className="min-w-0 flex-1 truncate text-muted-foreground">
                      {sheetLabel(row.sheet)}
                    </span>
                    <span className="shrink-0 font-mono text-[10px] text-muted-foreground">
                      {formatEffectiveQuantity(
                        {
                          id: "",
                          org_id: "",
                          project_id: "",
                          sheet_id: row.sheet.id,
                          condition_id: c.id,
                          measurement_type: c.measurement_type,
                          geometry: { type: "count", position: { x: 0, y: 0 } },
                          measured_value: row.sheetSubtotal,
                          override_value: null,
                          label: null,
                          created_by: "",
                          created_at: "",
                          updated_at: "",
                        },
                        c,
                        row.sheet.scale_unit
                      )}
                    </span>
                  </div>
                );
              }

              if (row.kind === "measurement") {
                const m = row.measurement;
                const c = conditions.find((x) => x.id === m.condition_id);
                const sh = sheetById.get(m.sheet_id);
                if (!c || !sh) return null;
                const hasAsm = (m.derived_quantities?.length ?? 0) > 0;
                const selected = selectedIds.has(m.id);
                const overridden = m.override_value != null;
                const hasDeductions =
                  m.measurement_type === "linear" &&
                  Array.isArray(m.deductions) &&
                  m.deductions.length > 0;
                const gross =
                  m.measurement_type === "linear" && m.gross_measured_value != null
                    ? m.gross_measured_value
                    : null;

                return (
                  <div
                    key={`m-${m.id}`}
                    className={cn(
                      "group absolute left-0 top-0 flex w-full items-center gap-0.5 border-b border-border/30 py-0.5 pr-1",
                      pad(2),
                      selected ? "bg-primary/15" : "hover:bg-muted/40"
                    )}
                    style={{ height: ROW_H, transform: `translateY(${vRow.start}px)` }}
                    onContextMenu={(e) => {
                      e.preventDefault();
                      setCtx({ x: e.clientX, y: e.clientY, measurementId: m.id });
                    }}
                  >
                    {hasAsm ? (
                      <button
                        type="button"
                        className="flex shrink-0 items-center justify-center rounded p-0.5 hover:bg-muted"
                        onClick={() => toggleMeasAsm(m.id)}
                      >
                        {expandedMeas.has(m.id) ? (
                          <ChevronDown className="h-3 w-3" />
                        ) : (
                          <ChevronRight className="h-3 w-3" />
                        )}
                      </button>
                    ) : (
                      <span className="w-4 shrink-0" />
                    )}
                    {canEdit && renamingId !== m.id ? (
                      <Tooltip>
                        <TooltipTrigger
                          render={
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon-sm"
                              // className="h-5 w-5 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100 focus-visible:opacity-100"
                              className="h-5 w-5 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100 hover:bg-transparent hover:!text-muted-foreground"
                              aria-label="Rename measurement"
                              onClick={(e) => {
                                e.stopPropagation();
                                startRename(m);
                              }}
                            />
                          }
                        >
                          <PenLine className="h-1.5 w-1.5" />
                        </TooltipTrigger>
                        <TooltipContent side="bottom" className="text-[10px]">
                          Rename
                        </TooltipContent>
                      </Tooltip>
                    ) : null}
                    {renamingId === m.id ? (
                      <Input
                        className="box-border min-h-0 min-w-0 flex-1 rounded border border-input bg-background px-1.5 py-0 text-[11px] leading-none shadow-none focus-visible:border-ring focus-visible:ring-1 focus-visible:ring-ring/40 md:text-[11px]"
                        style={{ height: ROW_H - 4 }}
                        value={renameDraft}
                        maxLength={255}
                        placeholder={`Measurement ${m.id.slice(0, 8)}`}
                        onChange={(e) => setRenameDraft(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") {
                            e.preventDefault();
                            void submitRename(m.id, renameDraft);
                          }
                          if (e.key === "Escape") {
                            e.preventDefault();
                            renameBlurSkipRef.current = true;
                            setRenamingId(null);
                          }
                        }}
                        onBlur={() => {
                          if (renameBlurSkipRef.current) {
                            renameBlurSkipRef.current = false;
                            return;
                          }
                          void submitRename(m.id, renameDraft);
                        }}
                        autoFocus
                      />
                    ) : (
                      <button
                        type="button"
                        className="min-w-0 flex-1 truncate text-left text-foreground/95"
                        onClick={(e) => {
                          onMeasurementSelect(m.id, {
                            ctrlKey: e.ctrlKey,
                            metaKey: e.metaKey,
                          });
                          if (e.detail === 2) return;
                          if (!e.ctrlKey && !e.metaKey) {
                            void onNavigateToMeasurement(m);
                          }
                        }}
                      >
                        {m.label?.trim() || `Measurement ${m.id.slice(0, 8)}`}
                      </button>
                    )}
                    {editingId === m.id ? (
                      <Input
                        className="h-6 w-20 shrink-0 px-1 py-0 text-[10px]"
                        value={editDraft}
                        onChange={(e) => setEditDraft(e.target.value)}
                        onBlur={() => void commitEdit()}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") void commitEdit();
                          if (e.key === "Escape") setEditingId(null);
                        }}
                        autoFocus
                      />
                    ) : (
                      <div className="flex shrink-0 items-center gap-0.5">
                        <button
                          type="button"
                          className={cn(
                            "flex shrink-0 items-center gap-0.5 font-mono text-[10px]",
                            overridden ? "text-amber-200" : "text-muted-foreground"
                          )}
                          onClick={(e) => {
                            onMeasurementSelect(m.id, {
                              ctrlKey: e.ctrlKey,
                              metaKey: e.metaKey,
                            });
                            if (e.detail === 2) {
                              e.stopPropagation();
                              startEdit(m);
                              return;
                            }
                            if (!e.ctrlKey && !e.metaKey) {
                              void onNavigateToMeasurement(m);
                            }
                          }}
                        >
                          {overridden ? <PencilLine className="h-3 w-3 shrink-0 opacity-80" /> : null}
                          {hasDeductions && gross != null ? (
                            <span className="tabular-nums">
                              <span className="text-muted-foreground/80">
                                {formatLength(gross, sh.scale_unit, c.unit)}
                              </span>
                              <span className="mx-0.5 text-muted-foreground/60">→</span>
                              {formatEffectiveQuantity(m, c, sh.scale_unit)}
                            </span>
                          ) : (
                            formatEffectiveQuantity(m, c, sh.scale_unit)
                          )}
                        </button>
                        {/*
                          FUTURE: Linear deduction draw tool (quantities minus button).
                          Re-enable by passing onStartDeductionEdit from plan-viewer-workspace and restoring the block below.
                          See roadmap.md → Deferred & follow-on → "Linear deductions (draw tool)".

                        {canEdit &&
                        m.measurement_type === "linear" &&
                        onStartDeductionEdit ? (
                          <Tooltip>
                            <TooltipTrigger
                              render={
                                <Button
                                  type="button"
                                  variant="ghost"
                                  size="icon-sm"
                                  className="inline-flex h-6 w-6 shrink-0 text-orange-300 hover:text-orange-200"
                                  aria-label="Draw deductions"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    onStartDeductionEdit(m.id);
                                  }}
                                />
                              }
                            >
                              <Minus className="h-3.5 w-3.5" />
                            </TooltipTrigger>
                            <TooltipContent side="left" className="max-w-xs text-[10px]">
                              Mark deduction runs (door openings) to reduce net length.
                            </TooltipContent>
                          </Tooltip>
                        ) : null}
                        */}
                      </div>
                    )}
                    {/* <span className="w-7 shrink-0 text-[9px] text-muted-foreground">{c.unit}</span> */}
                  </div>
                );
              }

              const asm = row.item;
              const m = measurements.find((x) => x.id === row.measurementId);
              const c = m ? conditions.find((x) => x.id === m.condition_id) : null;
              return (
                <div
                  key={`asm-${row.measurementId}-${asm.assembly_item_id}`}
                  className={cn(
                    "absolute left-0 top-0 flex w-full items-center gap-1 border-b border-border/20 py-0.5 pr-1 text-muted-foreground",
                    pad(3)
                  )}
                  style={{ height: ROW_H, transform: `translateY(${vRow.start}px)` }}
                >
                  <span className="min-w-0 flex-1 truncate pl-1">{asm.name}</span>
                  <Tooltip>
                    <TooltipTrigger className="shrink-0 font-mono text-[10px]">
                      {asm.error ? "—" : asm.value?.toFixed(2) ?? "—"}
                    </TooltipTrigger>
                    <TooltipContent side="left" className="max-w-sm text-[10px]">
                      {asm.error ? (
                        <span className="text-destructive">{asm.error}</span>
                      ) : m && c ? (
                        <span>
                          Formula uses effective quantity{" "}
                          {formatEffectiveQuantity(m, c, sheetById.get(m.sheet_id)?.scale_unit)} (
                          {overriddenLabel(m)}).
                        </span>
                      ) : null}
                    </TooltipContent>
                  </Tooltip>
                  <span className="w-7 shrink-0 text-[9px]">{asm.unit}</span>
                </div>
              );
            })}
          </div>
        </div>

        <div className="shrink-0 border-t border-border bg-muted/20 px-2 py-1 text-[10px] text-muted-foreground">
          {measurements.length} measurement{measurements.length === 1 ? "" : "s"}
        </div>
      </div>

      {ctx ? (
        <div
          className="fixed z-[100] min-w-[180px] rounded-md border border-border bg-popover p-1 text-[11px] shadow-md"
          style={{ left: ctx.x, top: ctx.y }}
          onClick={(e) => e.stopPropagation()}
        >
          <button
            type="button"
            className="flex w-full rounded px-2 py-1.5 text-left hover:bg-muted"
            onClick={() => {
              const m = measurements.find((x) => x.id === ctx.measurementId);
              if (m) void onNavigateToMeasurement(m);
              setCtx(null);
            }}
          >
            Navigate to
          </button>
          {canEdit ? (
            <>
              <button
                type="button"
                className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left hover:bg-muted"
                onClick={() => {
                  const m = measurements.find((x) => x.id === ctx.measurementId);
                  if (m) startRename(m);
                  setCtx(null);
                }}
              >
                <PenLine className="h-1.5 w-1.5" />
                Rename…
              </button>
              <button
                type="button"
                className="flex w-full rounded px-2 py-1.5 text-left hover:bg-muted"
                onClick={() => {
                  const m = measurements.find((x) => x.id === ctx.measurementId);
                  if (m) startEdit(m);
                  setCtx(null);
                }}
              >
                Override value…
              </button>
              <button
                type="button"
                className="flex w-full rounded px-2 py-1.5 text-left hover:bg-muted"
                onClick={() => {
                  void resetOverride(ctx.measurementId);
                }}
              >
                <RotateCcw className="mr-2 inline h-3 w-3" />
                Reset to measured
              </button>
              <div className="my-1 h-px bg-border" />
              <label className="block px-2 py-0.5 text-[10px] text-muted-foreground">
                Change condition
              </label>
              <select
                className="mx-1 mb-1 w-[calc(100%-8px)] rounded border border-border bg-background px-1 py-1"
                value={
                  measurements.find((x) => x.id === ctx.measurementId)?.condition_id ?? ""
                }
                onChange={(e) => {
                  void onReassignCondition(ctx.measurementId, e.target.value);
                  setCtx(null);
                }}
              >
                {conditions
                  .filter(
                    (co) =>
                      co.measurement_type ===
                      measurements.find((x) => x.id === ctx.measurementId)?.measurement_type
                  )
                  .map((co) => (
                    <option key={co.id} value={co.id}>
                      {co.name}
                    </option>
                  ))}
              </select>
              <button
                type="button"
                className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-destructive hover:bg-destructive/10"
                onClick={() => {
                  setDeleteId(ctx.measurementId);
                  setCtx(null);
                }}
              >
                <Trash2 className="h-3.5 w-3.5" />
                Delete…
              </button>
            </>
          ) : null}
        </div>
      ) : null}

      <Dialog open={deleteId != null} onOpenChange={(o) => !o && setDeleteId(null)}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Delete measurement?</DialogTitle>
            <DialogDescription>
              This removes the takeoff from the plan and the quantities list.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button type="button" variant="ghost" onClick={() => setDeleteId(null)}>
              Cancel
            </Button>
            <Button
              type="button"
              variant="destructive"
              onClick={() => {
                if (deleteId) void onDeleteMeasurement(deleteId);
                setDeleteId(null);
              }}
            >
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </TooltipProvider>
  );
});

QuantitiesPanel.displayName = "QuantitiesPanel";

function overriddenLabel(m: MeasurementInfo): string {
  return m.override_value != null ? "override" : "measured";
}
