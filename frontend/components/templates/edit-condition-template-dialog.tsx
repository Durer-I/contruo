"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Loader2, Plus, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ConditionColorPicker } from "@/components/conditions/condition-color-picker";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import type {
  ConditionTemplateAssemblySnapshotItem,
  ConditionTemplateDetail,
} from "@/types/assembly";

const LINE_STYLES = ["solid", "dashed", "dotted"] as const;
const FILL_PATTERNS = ["solid", "hatch", "crosshatch"] as const;

type AssemblyFormRow = ConditionTemplateAssemblySnapshotItem & { rowKey: string };

function newRowKey(): string {
  if (typeof globalThis.crypto !== "undefined" && globalThis.crypto.randomUUID) {
    return globalThis.crypto.randomUUID();
  }
  return `row-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function typeLabel(t: string): string {
  if (t === "linear") return "Linear";
  if (t === "area") return "Area";
  if (t === "count") return "Count";
  return t;
}

type FormState = {
  name: string;
  unit: string;
  color: string;
  line_style: string;
  line_width: string;
  fill_opacity: string;
  fill_pattern: string;
  trade: string;
  description: string;
  properties: { custom: Array<{ name: string; value: string; unit: string }> };
  assembly_rows: AssemblyFormRow[];
};

function detailToForm(d: ConditionTemplateDetail): FormState {
  return {
    name: d.name,
    unit: d.unit,
    color: d.color,
    line_style: d.line_style,
    line_width: String(d.line_width),
    fill_opacity: String(d.fill_opacity),
    fill_pattern: d.fill_pattern,
    trade: d.trade ?? "",
    description: d.description ?? "",
    properties: {
      custom: (d.properties?.custom ?? []).map((x) => ({
        name: x.name,
        value: x.value,
        unit: x.unit,
      })),
    },
    assembly_rows: (d.assembly_items ?? []).map((r) => ({
      name: r.name,
      unit: r.unit,
      formula: r.formula,
      description: r.description ?? null,
      sort_order: r.sort_order,
      rowKey: newRowKey(),
    })),
  };
}

function serializeAssembly(rows: AssemblyFormRow[]): ConditionTemplateAssemblySnapshotItem[] {
  return rows
    .filter((r) => r.name.trim().length > 0)
    .map((r, i) => ({
      name: r.name.trim().slice(0, 255),
      unit: (r.unit.trim() || "EA").slice(0, 20),
      formula: (r.formula.trim() || "0"),
      description: r.description?.trim() ? r.description.trim().slice(0, 2000) : null,
      sort_order: i,
    }));
}

export function EditConditionTemplateDialog({
  templateId,
  open,
  onOpenChange,
  onSaved,
}: {
  templateId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
}) {
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [measurementType, setMeasurementType] = useState<string>("linear");
  const [form, setForm] = useState<FormState | null>(null);

  const primaryHint = useMemo(() => {
    if (measurementType === "linear") return "length";
    if (measurementType === "area") return "area, perimeter";
    return "count";
  }, [measurementType]);

  const load = useCallback(async () => {
    if (!templateId) return;
    setLoading(true);
    setError(null);
    try {
      const d = await api.get<ConditionTemplateDetail>(
        `/api/v1/org/condition-templates/${templateId}`
      );
      setMeasurementType(d.measurement_type);
      setForm(detailToForm(d));
    } catch (e) {
      setForm(null);
      setError(e instanceof ApiError ? e.message : "Could not load template");
    } finally {
      setLoading(false);
    }
  }, [templateId]);

  useEffect(() => {
    if (open && templateId) void load();
    if (!open) {
      setForm(null);
      setError(null);
    }
  }, [open, templateId, load]);

  const showFill = measurementType === "area";
  const showStroke = measurementType === "linear" || measurementType === "area";

  const addAssemblyRow = useCallback(() => {
    setForm((f) => {
      if (!f) return f;
      const nextOrder =
        f.assembly_rows.length === 0
          ? 0
          : Math.max(...f.assembly_rows.map((r) => r.sort_order), -1) + 1;
      return {
        ...f,
        assembly_rows: [
          ...f.assembly_rows,
          {
            rowKey: newRowKey(),
            name: "New item",
            unit: "EA",
            formula: "0",
            description: null,
            sort_order: nextOrder,
          },
        ],
      };
    });
  }, []);

  const removeAssemblyRow = useCallback((rowKey: string) => {
    setForm((f) =>
      f ? { ...f, assembly_rows: f.assembly_rows.filter((r) => r.rowKey !== rowKey) } : f
    );
  }, []);

  const patchAssemblyRow = useCallback(
    (rowKey: string, patch: Partial<ConditionTemplateAssemblySnapshotItem>) => {
      setForm((f) =>
        f
          ? {
              ...f,
              assembly_rows: f.assembly_rows.map((r) =>
                r.rowKey === rowKey ? { ...r, ...patch } : r
              ),
            }
          : f
      );
    },
    []
  );

  async function handleSave() {
    if (!templateId || !form) return;
    const lw = Number(form.line_width);
    const fo = Number(form.fill_opacity);
    if (!/^#[0-9A-Fa-f]{6}$/i.test(form.color.trim())) {
      setError("Color must be a valid hex value like #RRGGBB.");
      return;
    }
    if (!Number.isFinite(lw) || lw < 0.5 || lw > 16) {
      setError("Line width must be between 0.5 and 16.");
      return;
    }
    if (!Number.isFinite(fo) || fo < 0 || fo > 1) {
      setError("Fill opacity must be between 0 and 1.");
      return;
    }
    if (form.assembly_rows.some((r) => !r.name.trim())) {
      setError("Each assembly line needs a name, or delete empty rows.");
      return;
    }
    const assemblyPayload = serializeAssembly(form.assembly_rows);
    setSaving(true);
    setError(null);
    try {
      await api.patch<ConditionTemplateDetail>(`/api/v1/org/condition-templates/${templateId}`, {
        name: form.name.trim(),
        unit: form.unit.trim(),
        color: form.color.trim().toLowerCase(),
        line_style: form.line_style,
        line_width: lw,
        fill_opacity: fo,
        fill_pattern: form.fill_pattern,
        trade: form.trade.trim() || null,
        description: form.description.trim() || null,
        properties: {
          custom: form.properties.custom.filter((r) => r.name.trim().length > 0),
        },
        assembly_items: assemblyPayload.map((r) => ({
          name: r.name,
          unit: r.unit,
          formula: r.formula,
          description: r.description ?? null,
          sort_order: r.sort_order,
        })),
      });
      onOpenChange(false);
      onSaved();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[min(92vh,820px)] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Edit template</DialogTitle>
          <DialogDescription>
            Update the org library snapshot. Measurement type stays{" "}
            <span className="font-medium text-foreground">{typeLabel(measurementType)}</span> (change
            by re-saving from a project condition if needed).
          </DialogDescription>
        </DialogHeader>

        {loading ? (
          <div className="flex items-center justify-center gap-2 py-10 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading…
          </div>
        ) : null}

        {error && !loading ? (
          <p className="rounded-md border border-destructive/30 bg-destructive/10 px-2 py-1.5 text-xs text-destructive">
            {error}
          </p>
        ) : null}

        {form && !loading ? (
          <div className="space-y-3 py-1">
            <label className="block space-y-1">
              <span className="text-[10px] uppercase tracking-wide text-muted-foreground">Name</span>
              <Input
                value={form.name}
                onChange={(e) => setForm((f) => (f ? { ...f, name: e.target.value } : f))}
                maxLength={255}
                className="h-8 text-sm"
              />
            </label>
            <label className="block space-y-1">
              <span className="text-[10px] uppercase tracking-wide text-muted-foreground">Unit</span>
              <Input
                value={form.unit}
                onChange={(e) => setForm((f) => (f ? { ...f, unit: e.target.value } : f))}
                maxLength={20}
                className="h-8 text-sm"
              />
            </label>
            <div className="space-y-1">
              <span className="text-[10px] uppercase tracking-wide text-muted-foreground">Color</span>
              <ConditionColorPicker
                value={form.color}
                onChange={(hex) => setForm((f) => (f ? { ...f, color: hex } : f))}
              />
            </div>
            {showStroke ? (
              <>
                <label className="block space-y-1">
                  <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
                    Line style
                  </span>
                  <select
                    className={cn(
                      "h-8 w-full rounded-md border border-input bg-background px-2 text-sm",
                      "outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40"
                    )}
                    value={form.line_style}
                    onChange={(e) =>
                      setForm((f) => (f ? { ...f, line_style: e.target.value } : f))
                    }
                  >
                    {LINE_STYLES.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block space-y-1">
                  <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
                    Line width
                  </span>
                  <Input
                    type="number"
                    step="0.5"
                    min={0.5}
                    max={16}
                    value={form.line_width}
                    onChange={(e) =>
                      setForm((f) => (f ? { ...f, line_width: e.target.value } : f))
                    }
                    className="h-8 text-sm"
                  />
                </label>
              </>
            ) : null}
            {showFill ? (
              <>
                <label className="block space-y-1">
                  <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
                    Fill opacity
                  </span>
                  <Input
                    type="number"
                    step="0.05"
                    min={0}
                    max={1}
                    value={form.fill_opacity}
                    onChange={(e) =>
                      setForm((f) => (f ? { ...f, fill_opacity: e.target.value } : f))
                    }
                    className="h-8 text-sm"
                  />
                </label>
                <label className="block space-y-1">
                  <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
                    Fill pattern
                  </span>
                  <select
                    className={cn(
                      "h-8 w-full rounded-md border border-input bg-background px-2 text-sm",
                      "outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40"
                    )}
                    value={form.fill_pattern}
                    onChange={(e) =>
                      setForm((f) => (f ? { ...f, fill_pattern: e.target.value } : f))
                    }
                  >
                    {FILL_PATTERNS.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                </label>
              </>
            ) : null}
            <label className="block space-y-1">
              <span className="text-[10px] uppercase tracking-wide text-muted-foreground">Trade</span>
              <Input
                value={form.trade}
                onChange={(e) => setForm((f) => (f ? { ...f, trade: e.target.value } : f))}
                maxLength={100}
                className="h-8 text-sm"
              />
            </label>
            <label className="block space-y-1">
              <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
                Description
              </span>
              <textarea
                className="min-h-[72px] w-full rounded-md border border-input bg-background px-2 py-1.5 text-xs outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40"
                value={form.description}
                onChange={(e) =>
                  setForm((f) => (f ? { ...f, description: e.target.value } : f))
                }
              />
            </label>

            <div className="space-y-2 border-t border-border pt-3">
              <div className="flex items-center justify-between gap-2">
                <span className="text-[10px] font-medium uppercase text-muted-foreground">
                  Assembly items
                </span>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-6 min-w-[4.5rem] gap-1 text-[10px]"
                  onClick={addAssemblyRow}
                >
                  <Plus className="h-3 w-3 shrink-0" aria-hidden />
                  Add line
                </Button>
              </div>
              <p className="text-[10px] leading-snug text-muted-foreground">
                Variables: <span className="font-mono text-foreground/90">{primaryHint}</span>, plus
                custom property names from this template. Functions: round, ceil, floor, min, max,
                abs. Live formula preview is available on project conditions; here you edit the
                stored template snapshot.
              </p>
              {form.assembly_rows.length === 0 ? (
                <p className="text-[11px] text-muted-foreground">
                  No assembly lines. Add materials or labor with formulas, or leave empty.
                </p>
              ) : (
                <div className="max-h-64 space-y-2 overflow-y-auto pr-0.5">
                  {form.assembly_rows.map((it) => (
                    <div
                      key={it.rowKey}
                      className="space-y-1 rounded-md border border-border bg-card/40 p-2"
                    >
                      <div className="grid grid-cols-2 gap-1">
                        <Input
                          className="h-7 text-[11px]"
                          value={it.name}
                          placeholder="Name"
                          onChange={(e) =>
                            patchAssemblyRow(it.rowKey, { name: e.target.value })
                          }
                        />
                        <Input
                          className="h-7 text-[11px]"
                          value={it.unit}
                          placeholder="Unit"
                          onChange={(e) =>
                            patchAssemblyRow(it.rowKey, { unit: e.target.value })
                          }
                        />
                      </div>
                      <Input
                        className="h-7 font-mono text-[10px]"
                        value={it.formula}
                        placeholder="e.g. length * height / 32"
                        onChange={(e) =>
                          patchAssemblyRow(it.rowKey, { formula: e.target.value })
                        }
                      />
                      <Input
                        className="h-7 text-[10px]"
                        value={it.description ?? ""}
                        placeholder="Description (optional)"
                        onChange={(e) =>
                          patchAssemblyRow(it.rowKey, {
                            description: e.target.value.trim() || null,
                          })
                        }
                      />
                      <div className="flex justify-end">
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon-sm"
                          className="h-7 w-7 shrink-0 text-muted-foreground hover:text-destructive"
                          aria-label="Remove assembly line"
                          onClick={() => removeAssemblyRow(it.rowKey)}
                        >
                          <Trash2 className="h-3.5 w-3.5" aria-hidden />
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ) : null}

        <DialogFooter className="gap-2 sm:gap-0">
          <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            type="button"
            disabled={!form || saving || loading}
            onClick={() => void handleSave()}
          >
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
