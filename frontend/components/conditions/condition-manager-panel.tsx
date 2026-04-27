"use client";

import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useMemo,
  useState,
} from "react";
import { Loader2, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { api, ApiError } from "@/lib/api";
import {
  defaultUnitForMeasurementType,
  unitsForMeasurementType,
} from "@/lib/condition-units";
import { TAKEOFF_CONDITION_COLORS } from "@/lib/takeoff-condition-colors";
import { cn } from "@/lib/utils";
import type {
  ConditionCustomProperty,
  ConditionInfo,
  MeasurementType,
} from "@/types/condition";

import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import type { ConditionTemplateInfo } from "@/types/assembly";

import { AssemblyItemsSection } from "./assembly-items-section";
import { ConditionColorPicker } from "./condition-color-picker";
import { DeleteConditionDialog } from "./delete-condition-dialog";

export type ConditionManagerPanelHandle = {
  startNew: () => void;
};

interface ConditionManagerPanelProps {
  projectId: string;
  conditions: ConditionInfo[];
  activeConditionId: string | null;
  onActiveConditionChange: (id: string | null) => void;
  onConditionsChange: () => Promise<void>;
  /** After assembly CRUD: refresh measurements only (keeps condition form from refetching). */
  onSheetMeasurementsRefresh?: () => void | Promise<void>;
  /** After project condition mutations (Liveblocks notify peers). */
  onCollaborationMutation?: () => void;
  canManage: boolean;
}

type FormState = {
  name: string;
  measurement_type: MeasurementType;
  unit: string;
  color: string;
  line_style: "solid" | "dashed" | "dotted";
  line_width: number;
  fill_opacity: number;
  fill_pattern: "solid" | "hatch" | "crosshatch";
  custom: ConditionCustomProperty[];
  trade: string;
  description: string;
  notes: string;
};

const defaultForm = (): FormState => ({
  name: "",
  measurement_type: "linear",
  unit: "LF",
  color: TAKEOFF_CONDITION_COLORS[0].hex,
  line_style: "solid",
  line_width: 2,
  fill_opacity: 0.3,
  fill_pattern: "solid",
  custom: [],
  trade: "",
  description: "",
  notes: "",
});

/** True if the event target is a real control — don't treat as “background” deselect. */
function isPointerOnInteractiveControl(target: EventTarget | null): boolean {
  if (!(target instanceof Element)) return false;
  const el = target as HTMLElement;
  if (
    el.closest(
      '[data-slot="scroll-area-scrollbar"], [data-slot="scroll-area-thumb"]'
    )
  ) {
    return true;
  }
  if (
    el.closest(
      "button, a[href], input, select, textarea, [contenteditable=true], label"
    )
  ) {
    return true;
  }
  return false;
}

function formFromCondition(c: ConditionInfo): FormState {
  return {
    name: c.name,
    measurement_type: c.measurement_type,
    unit: c.unit,
    color: c.color,
    line_style: c.line_style,
    line_width: c.line_width,
    fill_opacity: c.fill_opacity,
    fill_pattern: c.fill_pattern,
    custom: (c.properties?.custom ?? []).map((x) => ({
      name: x.name,
      value: x.value,
      unit: x.unit,
    })),
    trade: c.trade ?? "",
    description: c.description ?? "",
    notes: c.notes ?? "",
  };
}

export const ConditionManagerPanel = forwardRef<
  ConditionManagerPanelHandle,
  ConditionManagerPanelProps
>(function ConditionManagerPanel(
  {
    projectId,
    conditions,
    activeConditionId,
    onActiveConditionChange,
    onConditionsChange,
    onSheetMeasurementsRefresh,
    onCollaborationMutation,
    canManage,
  },
  ref
) {
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState<FormState>(defaultForm);
  const [saving, setSaving] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const [templates, setTemplates] = useState<ConditionTemplateInfo[]>([]);
  const [templatesLoading, setTemplatesLoading] = useState(false);

  const active = useMemo(
    () => conditions.find((c) => c.id === activeConditionId) ?? null,
    [conditions, activeConditionId]
  );

  useEffect(() => {
    setError(null);
    if (creating) {
      setForm(defaultForm());
      return;
    }
    if (active) {
      setForm(formFromCondition(active));
    } else {
      setForm(defaultForm());
    }
  }, [creating, active]);

  const startNew = useCallback(() => {
    if (!canManage) return;
    setCreating(true);
  }, [canManage]);

  useImperativeHandle(ref, () => ({ startNew }), [startNew]);

  const clearSelection = useCallback(() => {
    setCreating(false);
    onActiveConditionChange(null);
  }, [onActiveConditionChange]);

  const cancelNew = useCallback(() => {
    setCreating(false);
    const first = conditions[0];
    if (first) onActiveConditionChange(first.id);
  }, [conditions, onActiveConditionChange]);

  const save = useCallback(async () => {
    if (!canManage) return;
    const hex = form.color.trim();
    if (!/^#[0-9A-Fa-f]{6}$/.test(hex)) {
      setError("Color must be a valid hex value like #RRGGBB.");
      return;
    }
    setSaving(true);
    setError(null);
    const payload = {
      name: form.name.trim(),
      measurement_type: form.measurement_type,
      unit: form.unit.trim(),
      color: hex.toLowerCase(),
      line_style: form.line_style,
      line_width: form.line_width,
      fill_opacity: form.fill_opacity,
      fill_pattern: form.fill_pattern,
      properties: {
        custom: form.custom.filter((r) => r.name.trim().length > 0),
      },
      trade: form.trade.trim() || null,
      description: form.description.trim() || null,
      notes: form.notes.trim() || null,
    };
    if (!payload.name) {
      setError("Name is required.");
      setSaving(false);
      return;
    }
    try {
      if (creating) {
        const created = await api.post<ConditionInfo>(
          `/api/v1/projects/${projectId}/conditions`,
          payload
        );
        setCreating(false);
        onActiveConditionChange(created.id);
      } else if (active) {
        await api.patch(`/api/v1/conditions/${active.id}`, payload);
        onActiveConditionChange(active.id);
      }
      await onConditionsChange();
      onCollaborationMutation?.();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }, [
    canManage,
    form,
    creating,
    active,
    projectId,
    onActiveConditionChange,
    onConditionsChange,
    onCollaborationMutation,
  ]);

  const loadTemplates = useCallback(async () => {
    setTemplatesLoading(true);
    try {
      const r = await api.get<{ templates: ConditionTemplateInfo[] }>(
        "/api/v1/org/condition-templates"
      );
      setTemplates(r.templates);
    } catch {
      setTemplates([]);
    } finally {
      setTemplatesLoading(false);
    }
  }, []);

  const saveAsTemplate = useCallback(async () => {
    if (!active || !canManage) return;
    setSaving(true);
    setError(null);
    try {
      await api.post(`/api/v1/org/conditions/${active.id}/save-as-template`, {
        name: active.name,
      });
      setError(null);
      await loadTemplates();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not save template");
    } finally {
      setSaving(false);
    }
  }, [active, canManage, loadTemplates]);

  const importTemplate = useCallback(
    async (templateId: string) => {
      if (!canManage) return;
      setSaving(true);
      setError(null);
      try {
        const created = await api.post<ConditionInfo>(
          `/api/v1/projects/${projectId}/conditions/import-from-template`,
          { template_id: templateId }
        );
        setImportOpen(false);
        onActiveConditionChange(created.id);
        await onConditionsChange();
        onCollaborationMutation?.();
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "Import failed");
      } finally {
        setSaving(false);
      }
    },
    [canManage, projectId, onActiveConditionChange, onConditionsChange, onCollaborationMutation]
  );

  const confirmDelete = useCallback(async () => {
    if (!active || !canManage) return;
    setSaving(true);
    setError(null);
    try {
      await api.delete(`/api/v1/conditions/${active.id}`);
      setDeleteOpen(false);
      const rest = conditions.filter((c) => c.id !== active.id);
      onActiveConditionChange(rest[0]?.id ?? null);
      await onConditionsChange();
      onCollaborationMutation?.();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Delete failed");
    } finally {
      setSaving(false);
    }
  }, [active, canManage, conditions, onActiveConditionChange, onConditionsChange, onCollaborationMutation]);

  const typeLabel = (t: MeasurementType) =>
    t === "linear" ? "Linear" : t === "area" ? "Area" : "Count";

  const unitOptions = useMemo(() => {
    const allowed = [...unitsForMeasurementType(form.measurement_type)];
    const u = form.unit.trim();
    if (u && !allowed.some((x) => x.toLowerCase() === u.toLowerCase())) {
      return [u, ...allowed];
    }
    return allowed;
  }, [form.measurement_type, form.unit]);

  const showStrokeControls =
    form.measurement_type === "linear" || form.measurement_type === "area";
  const showFillControls = form.measurement_type === "area";

  const onColumnPointerDownCapture = useCallback(
    (e: React.PointerEvent) => {
      if (isPointerOnInteractiveControl(e.target)) return;
      clearSelection();
    },
    [clearSelection]
  );

  return (
    <div
      className="flex min-h-0 flex-1 flex-col"
      onPointerDownCapture={onColumnPointerDownCapture}
    >
      <ScrollArea className="min-h-0 flex-1">
        <ul className="flex flex-col gap-1 p-2">
          {conditions.map((c) => {
            const selected = c.id === activeConditionId && !creating;
            return (
              <li key={c.id}>
                <button
                  type="button"
                  onClick={() => {
                    setCreating(false);
                    onActiveConditionChange(c.id);
                  }}
                  className={cn(
                    "flex w-full items-center gap-2 rounded-md border px-2 py-1.5 text-left text-xs transition-colors",
                    selected
                      ? "border-primary bg-primary/5 ring-1 ring-primary/25"
                      : "border-transparent bg-card hover:border-border hover:bg-surface-overlay"
                  )}
                >
                  <span
                    className="h-2.5 w-2.5 shrink-0 rounded-full border border-border"
                    style={{ backgroundColor: c.color }}
                  />
                  <span className="min-w-0 flex-1 truncate font-medium">{c.name}</span>
                  <span className="shrink-0 text-[10px] text-muted-foreground">
                    {typeLabel(c.measurement_type)}
                  </span>
                  <span className="shrink-0 font-mono text-[10px] text-muted-foreground">
                    {c.total_quantity === 0
                      ? `0 ${c.unit}`
                      : `${c.total_quantity.toLocaleString(undefined, {
                          maximumFractionDigits: 2,
                        })} ${c.unit}`}
                  </span>
                </button>
              </li>
            );
          })}
          {conditions.length === 0 && !creating ? (
            <li className="px-2 py-4 text-center text-[11px] text-muted-foreground">
              No conditions yet.
              {canManage ? " Click New to create one." : ""}
            </li>
          ) : null}
        </ul>
      </ScrollArea>

      <Separator />

      <div className="border-t border-border px-3 py-2">
        <div className="mb-2 text-[11px] font-medium text-muted-foreground">
          {creating ? "New condition" : active ? `Edit: ${active.name}` : "Select a condition"}
        </div>

        {error ? (
          <p className="mb-2 text-[11px] text-destructive">{error}</p>
        ) : null}

        {!active && !creating ? (
          <p className="text-[11px] text-muted-foreground">
            Choose a condition above or create a new one.
          </p>
        ) : (
          <div className="flex max-h-[min(52vh,480px)] flex-col gap-3 overflow-y-auto pr-1">
            <label className="space-y-1">
              <span className="text-[10px] uppercase text-muted-foreground">Name</span>
              <Input
                className="h-8 text-xs"
                value={form.name}
                disabled={!canManage}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              />
            </label>

            <div className="grid grid-cols-2 gap-2">
              <label className="space-y-1">
                <span className="text-[10px] uppercase text-muted-foreground">Type</span>
                <select
                  className="flex h-8 w-full rounded-md border border-border bg-background px-2 text-xs"
                  disabled={!canManage}
                  value={form.measurement_type}
                  onChange={(e) => {
                    const mt = e.target.value as MeasurementType;
                    setForm((f) => {
                      const allowed = unitsForMeasurementType(mt);
                      const cur = f.unit.trim();
                      const stillValid = allowed.some((x) => x.toLowerCase() === cur.toLowerCase());
                      const unit = stillValid ? f.unit : defaultUnitForMeasurementType(mt);
                      return { ...f, measurement_type: mt, unit };
                    });
                  }}
                >
                  <option value="linear">Linear</option>
                  <option value="area">Area</option>
                  <option value="count">Count</option>
                </select>
              </label>
              <label className="space-y-1">
                <span className="text-[10px] uppercase text-muted-foreground">Unit</span>
                <select
                  className="flex h-8 w-full rounded-md border border-border bg-background px-2 text-xs"
                  disabled={!canManage}
                  value={form.unit}
                  onChange={(e) => setForm((f) => ({ ...f, unit: e.target.value }))}
                >
                  {unitOptions.map((u) => (
                    <option key={u} value={u}>
                      {u}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <div className="space-y-1">
              <span className="text-[10px] uppercase text-muted-foreground">Color</span>
              <ConditionColorPicker
                value={form.color}
                disabled={!canManage}
                onChange={(hex) => setForm((f) => ({ ...f, color: hex }))}
              />
            </div>

            {showStrokeControls || showFillControls ? (
              <div className="space-y-1 border-t border-border pt-2">
                <span className="text-[10px] font-medium uppercase text-muted-foreground">
                  {form.measurement_type === "linear"
                    ? "Line appearance"
                    : "Area appearance"}
                </span>
              </div>
            ) : (
              <p className="text-[10px] leading-snug text-muted-foreground">
                {/* Count markers use color only on the plan. */}
              </p>
            )}

            {showStrokeControls ? (
              showFillControls ? (
                <div className="grid grid-cols-2 gap-2">
                  <label className="space-y-1">
                    <span className="text-[10px] uppercase text-muted-foreground">Line style</span>
                    <select
                      className="flex h-8 w-full rounded-md border border-border bg-background px-2 text-xs"
                      disabled={!canManage}
                      value={form.line_style}
                      onChange={(e) =>
                        setForm((f) => ({
                          ...f,
                          line_style: e.target.value as FormState["line_style"],
                        }))
                      }
                    >
                      <option value="solid">Solid</option>
                      <option value="dashed">Dashed</option>
                      <option value="dotted">Dotted</option>
                    </select>
                  </label>
                  <label className="space-y-1">
                    <span className="text-[10px] uppercase text-muted-foreground">
                      Fill pattern
                    </span>
                    <select
                      className="flex h-8 w-full rounded-md border border-border bg-background px-2 text-xs"
                      disabled={!canManage}
                      value={form.fill_pattern}
                      onChange={(e) =>
                        setForm((f) => ({
                          ...f,
                          fill_pattern: e.target.value as FormState["fill_pattern"],
                        }))
                      }
                    >
                      <option value="solid">Solid</option>
                      <option value="hatch">Hatch</option>
                      <option value="crosshatch">Crosshatch</option>
                    </select>
                  </label>
                </div>
              ) : (
                <label className="space-y-1">
                  <span className="text-[10px] uppercase text-muted-foreground">Line style</span>
                  <select
                    className="flex h-8 w-full rounded-md border border-border bg-background px-2 text-xs"
                    disabled={!canManage}
                    value={form.line_style}
                    onChange={(e) =>
                      setForm((f) => ({
                        ...f,
                        line_style: e.target.value as FormState["line_style"],
                      }))
                    }
                  >
                    <option value="solid">Solid</option>
                    <option value="dashed">Dashed</option>
                    <option value="dotted">Dotted</option>
                  </select>
                </label>
              )
            ) : null}

            {showStrokeControls ? (
              <label className="space-y-1">
                <span className="text-[10px] uppercase text-muted-foreground">
                  Line width ({form.line_width}px)
                </span>
                <input
                  type="range"
                  min={0.5}
                  max={8}
                  step={0.5}
                  disabled={!canManage}
                  className="w-full accent-primary"
                  value={form.line_width}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, line_width: Number(e.target.value) }))
                  }
                />
              </label>
            ) : null}

            {showFillControls ? (
              <label className="space-y-1">
                <span className="text-[10px] uppercase text-muted-foreground">
                  Fill opacity ({Math.round(form.fill_opacity * 100)}%)
                </span>
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.05}
                  disabled={!canManage}
                  className="w-full accent-primary"
                  value={form.fill_opacity}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, fill_opacity: Number(e.target.value) }))
                  }
                />
              </label>
            ) : null}

            {/* <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[10px] uppercase text-muted-foreground">
                  Custom properties
                </span>
                {canManage ? (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-6 text-[10px]"
                    onClick={() =>
                      setForm((f) => ({
                        ...f,
                        custom: [...f.custom, { name: "", value: "", unit: "" }],
                      }))
                    }
                  >
                    Add property
                  </Button>
                ) : null}
              </div>
              {form.custom.map((row, idx) => (
                <div key={idx} className="flex gap-1">
                  <Input
                    className="h-7 flex-1 text-[11px]"
                    placeholder="Name"
                    disabled={!canManage}
                    value={row.name}
                    onChange={(e) => {
                      const next = [...form.custom];
                      next[idx] = { ...row, name: e.target.value };
                      setForm((f) => ({ ...f, custom: next }));
                    }}
                  />
                  <Input
                    className="h-7 w-16 text-[11px]"
                    placeholder="Value"
                    disabled={!canManage}
                    value={row.value}
                    onChange={(e) => {
                      const next = [...form.custom];
                      next[idx] = { ...row, value: e.target.value };
                      setForm((f) => ({ ...f, custom: next }));
                    }}
                  />
                  <Input
                    className="h-7 w-12 text-[11px]"
                    placeholder="Unit"
                    disabled={!canManage}
                    value={row.unit}
                    onChange={(e) => {
                      const next = [...form.custom];
                      next[idx] = { ...row, unit: e.target.value };
                      setForm((f) => ({ ...f, custom: next }));
                    }}
                  />
                  {canManage ? (
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-sm"
                      className="h-7 w-7 shrink-0"
                      onClick={() =>
                        setForm((f) => ({
                          ...f,
                          custom: f.custom.filter((_, i) => i !== idx),
                        }))
                      }
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  ) : null}
                </div>
              ))}
            </div> */}

            <label className="space-y-1">
              <span className="text-[10px] uppercase text-muted-foreground">
                Trade / CSI (optional)
              </span>
              <Input
                className="h-8 text-xs"
                value={form.trade}
                disabled={!canManage}
                onChange={(e) => setForm((f) => ({ ...f, trade: e.target.value }))}
              />
            </label>
            <label className="space-y-1">
              <span className="text-[10px] uppercase text-muted-foreground">Description</span>
              <textarea
                className="min-h-[52px] w-full rounded-md border border-border bg-background px-2 py-1.5 text-xs"
                value={form.description}
                disabled={!canManage}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              />
            </label>
            <label className="space-y-1">
              <span className="text-[10px] uppercase text-muted-foreground">Notes</span>
              <textarea
                className="min-h-[52px] w-full rounded-md border border-border bg-background px-2 py-1.5 text-xs"
                value={form.notes}
                disabled={!canManage}
                onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
              />
            </label>

            {active && !creating ? (
              <AssemblyItemsSection
                conditionId={active.id}
                measurementType={active.measurement_type}
                canManage={canManage}
                onAssemblyChanged={onSheetMeasurementsRefresh ?? onConditionsChange}
              />
            ) : null}

            {canManage && active && !creating ? (
              <div className="flex flex-wrap gap-2 border-t border-border pt-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-7 text-[10px]"
                  disabled={saving}
                  onClick={() => void saveAsTemplate()}
                >
                  Save as org template
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-7 text-[10px]"
                  disabled={saving}
                  onClick={() => {
                    setImportOpen(true);
                    void loadTemplates();
                  }}
                >
                  Import from templates
                </Button>
                <Dialog open={importOpen} onOpenChange={setImportOpen}>
                  <DialogContent className="max-w-md">
                    <DialogHeader>
                      <DialogTitle>Import condition</DialogTitle>
                    </DialogHeader>
                    {templatesLoading ? (
                      <p className="flex items-center gap-2 text-xs text-muted-foreground">
                        <Loader2 className="h-4 w-4 animate-spin" /> Loading…
                      </p>
                    ) : templates.length === 0 ? (
                      <p className="text-xs text-muted-foreground">No templates in your org library yet.</p>
                    ) : (
                      <ul className="max-h-64 space-y-1 overflow-auto">
                        {templates.map((t) => (
                          <li key={t.id}>
                            <button
                              type="button"
                              disabled={saving}
                              className="flex w-full items-center gap-2 rounded-md border border-border px-2 py-2 text-left text-xs hover:bg-surface-overlay"
                              onClick={() => void importTemplate(t.id)}
                            >
                              <span
                                className="h-2.5 w-2.5 shrink-0 rounded-full border border-border"
                                style={{ backgroundColor: t.color }}
                              />
                              <span className="min-w-0 flex-1 truncate font-medium">{t.name}</span>
                              <span className="shrink-0 text-[10px] text-muted-foreground">
                                {t.measurement_type} · {t.assembly_item_count} items
                              </span>
                            </button>
                          </li>
                        ))}
                      </ul>
                    )}
                  </DialogContent>
                </Dialog>
              </div>
            ) : null}

            {canManage ? (
              <div className="flex flex-wrap gap-2 pt-1">
                <Button
                  type="button"
                  size="sm"
                  className="h-8"
                  disabled={saving}
                  onClick={() => void save()}
                >
                  {saving ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : creating ? (
                    "Create"
                  ) : (
                    "Save"
                  )}
                </Button>
                {creating ? (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="h-8"
                    disabled={saving}
                    onClick={cancelNew}
                  >
                    Cancel
                  </Button>
                ) : (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="h-8"
                    disabled={saving || !active}
                    onClick={() => active && setDeleteOpen(true)}
                  >
                    Delete
                  </Button>
                )}
              </div>
            ) : null}
          </div>
        )}
      </div>

      {active ? (
        <DeleteConditionDialog
          open={deleteOpen}
          onOpenChange={setDeleteOpen}
          conditionName={active.name}
          measurementCount={active.measurement_count}
          onConfirm={confirmDelete}
          busy={saving}
        />
      ) : null}
    </div>
  );
});

ConditionManagerPanel.displayName = "ConditionManagerPanel";
