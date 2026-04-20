"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Loader2, Plus, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { AssemblyItemInfo } from "@/types/assembly";
import type { MeasurementType } from "@/types/condition";

const SAMPLE_PRIMARY = 100;
const SAMPLE_PERIMETER = 40;

function debounce<T extends (...args: Parameters<T>) => void>(fn: T, ms: number): T {
  let t: ReturnType<typeof setTimeout> | undefined;
  return ((...args: Parameters<T>) => {
    if (t) clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  }) as T;
}

export function AssemblyItemsSection({
  conditionId,
  measurementType,
  canManage,
  onAssemblyChanged,
}: {
  conditionId: string;
  measurementType: MeasurementType;
  canManage: boolean;
  onAssemblyChanged: () => void | Promise<void>;
}) {
  const [items, setItems] = useState<AssemblyItemInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [previewById, setPreviewById] = useState<Record<string, string>>({});

  const runPreview = useCallback(
    async (id: string, formula: string) => {
      if (!formula.trim()) {
        setPreviewById((p) => ({ ...p, [id]: "—" }));
        return;
      }
      try {
        const r = await api.post<{ value: number | null; error: string | null }>(
          `/api/v1/conditions/${conditionId}/assembly-formula-preview`,
          {
            formula,
            sample_primary: SAMPLE_PRIMARY,
            sample_perimeter: measurementType === "area" ? SAMPLE_PERIMETER : 0,
          }
        );
        if (r.error) setPreviewById((p) => ({ ...p, [id]: r.error! }));
        else {
          const v = r.value;
          if (typeof v === "number" && !Number.isNaN(v)) {
            setPreviewById((p) => ({
              ...p,
              [id]: v.toLocaleString(undefined, { maximumFractionDigits: 4 }),
            }));
          } else {
            setPreviewById((p) => ({ ...p, [id]: "—" }));
          }
        }
      } catch {
        setPreviewById((p) => ({ ...p, [id]: "Error" }));
      }
    },
    [conditionId, measurementType]
  );

  const debouncedPreview = useRef(debounce(runPreview, 450)).current;

  const load = useCallback(async () => {
    setLoading(true);
    setPreviewById({});
    try {
      const r = await api.get<{ items: AssemblyItemInfo[] }>(
        `/api/v1/conditions/${conditionId}/assembly-items`
      );
      setItems(r.items);
      for (const x of r.items) {
        void runPreview(x.id, x.formula);
      }
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [conditionId, runPreview]);

  useEffect(() => {
    void load();
  }, [load]);

  const primaryHint = useMemo(() => {
    if (measurementType === "linear") return "length";
    if (measurementType === "area") return "area, perimeter";
    return "count";
  }, [measurementType]);

  const patchItem = useCallback(
    async (id: string, patch: Partial<{ name: string; unit: string; formula: string }>) => {
      try {
        await api.patch(`/api/v1/assembly-items/${id}`, patch);
        void onAssemblyChanged();
      } catch {
        //
      }
    },
    [onAssemblyChanged]
  );

  const addItem = useCallback(async () => {
    if (!canManage || adding) return;
    setAdding(true);
    try {
      const created = await api.post<AssemblyItemInfo>(`/api/v1/conditions/${conditionId}/assembly-items`, {
        name: "New item",
        unit: "EA",
        formula: "0",
      });
      setItems((xs) => [...xs, created].sort((a, b) => a.sort_order - b.sort_order || a.id.localeCompare(b.id)));
      void runPreview(created.id, created.formula);
      void onAssemblyChanged();
    } catch {
      //
    } finally {
      setAdding(false);
    }
  }, [adding, canManage, conditionId, onAssemblyChanged, runPreview]);

  const removeItem = useCallback(
    async (id: string) => {
      if (!canManage || deletingId) return;
      setDeletingId(id);
      try {
        await api.delete(`/api/v1/assembly-items/${id}`);
        setItems((xs) => xs.filter((x) => x.id !== id));
        setPreviewById((p) => {
          const next = { ...p };
          delete next[id];
          return next;
        });
        void onAssemblyChanged();
      } catch {
        //
      } finally {
        setDeletingId((cur) => (cur === id ? null : cur));
      }
    },
    [canManage, deletingId, onAssemblyChanged]
  );

  if (loading) {
    return (
      <div className="flex items-center gap-2 py-2 text-[11px] text-muted-foreground">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        Loading assembly…
      </div>
    );
  }

  return (
    <div className="space-y-2 border-t border-border pt-3">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[10px] font-medium uppercase text-muted-foreground">Assembly items</span>
        {canManage ? (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-6 min-w-[4.5rem] gap-1 text-[10px]"
            disabled={adding}
            onClick={() => void addItem()}
          >
            {adding ? (
              <Loader2 className="h-3 w-3 shrink-0 animate-spin" aria-hidden />
            ) : (
              <Plus className="h-3 w-3 shrink-0" aria-hidden />
            )}
            {adding ? "Adding…" : "Add"}
          </Button>
        ) : null}
      </div>
      <p className="text-[10px] leading-snug text-muted-foreground">
        Variables: <span className="font-mono text-foreground/90">{primaryHint}</span>, plus custom property names
        (save the condition after editing properties). Functions: round, ceil, floor, min, max, abs. Preview uses
        sample{" "}
        {measurementType === "area"
          ? `area=${SAMPLE_PRIMARY}, perimeter=${SAMPLE_PERIMETER}`
          : `value=${SAMPLE_PRIMARY}`}
        .
      </p>
      {items.length === 0 ? (
        <p className="text-[11px] text-muted-foreground">No assembly items. Add materials or labor lines with formulas.</p>
      ) : (
        <div className="space-y-2">
          {items.map((it) => {
            const rowDeleting = deletingId === it.id;
            return (
            <div
              key={it.id}
              className={cn(
                "space-y-1 rounded-md border border-border bg-card/40 p-2 transition-opacity",
                rowDeleting && "pointer-events-none opacity-60"
              )}
            >
              <div className="grid grid-cols-2 gap-1">
                <Input
                  className="h-7 text-[11px]"
                  disabled={!canManage || rowDeleting}
                  value={it.name}
                  onChange={(e) => {
                    const v = e.target.value;
                    setItems((xs) => xs.map((x) => (x.id === it.id ? { ...x, name: v } : x)));
                  }}
                  onBlur={(e) => void patchItem(it.id, { name: e.target.value })}
                />
                <Input
                  className="h-7 text-[11px]"
                  disabled={!canManage || rowDeleting}
                  value={it.unit}
                  onChange={(e) => {
                    const v = e.target.value;
                    setItems((xs) => xs.map((x) => (x.id === it.id ? { ...x, unit: v } : x)));
                  }}
                  onBlur={(e) => void patchItem(it.id, { unit: e.target.value })}
                />
              </div>
              <Input
                className="h-7 font-mono text-[10px]"
                disabled={!canManage || rowDeleting}
                value={it.formula}
                placeholder="e.g. length * height / 32"
                onChange={(e) => {
                  const v = e.target.value;
                  setItems((xs) => xs.map((x) => (x.id === it.id ? { ...x, formula: v } : x)));
                  debouncedPreview(it.id, v);
                }}
                onBlur={(e) => void patchItem(it.id, { formula: e.target.value })}
              />
              <div className="flex items-center justify-between gap-2">
                <span className="truncate font-mono text-[10px] text-muted-foreground" title="Preview">
                  Preview: {previewById[it.id] ?? "…"}
                </span>
                {canManage ? (
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    className="h-7 w-7 shrink-0"
                    disabled={!!deletingId}
                    aria-busy={rowDeleting}
                    aria-label={rowDeleting ? "Removing…" : "Remove line"}
                    onClick={() => void removeItem(it.id)}
                  >
                    {rowDeleting ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
                    ) : (
                      <Trash2 className="h-3.5 w-3.5" aria-hidden />
                    )}
                  </Button>
                ) : null}
              </div>
            </div>
          );
          })}
        </div>
      )}
    </div>
  );
}
