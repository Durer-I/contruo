"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Loader2, Pencil, RefreshCw, Search, Trash2 } from "lucide-react";

import { EditConditionTemplateDialog } from "@/components/templates/edit-condition-template-dialog";

import { Button, buttonVariants } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/providers/auth-provider";
import { api, ApiError } from "@/lib/api";
import { formatMeasurementTypeLabel } from "@/lib/condition-units";
import { hasPermission, type Role } from "@/lib/permissions";
import { cn } from "@/lib/utils";
import type { ConditionTemplateInfo } from "@/types/assembly";

function formatShortDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return "—";
  }
}

export default function TemplatesPage() {
  const { user, loading: authLoading } = useAuth();
  const role = (user?.role ?? "viewer") as Role;
  const canManage = hasPermission(role, "manage_conditions");

  const [templates, setTemplates] = useState<ConditionTemplateInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<ConditionTemplateInfo | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [editTemplateId, setEditTemplateId] = useState<string | null>(null);

  const loadTemplates = useCallback(async (opts?: { silent?: boolean }) => {
    const silent = opts?.silent === true;
    if (silent) setRefreshing(true);
    else setLoading(true);
    setError(null);
    try {
      const r = await api.get<{ templates: ConditionTemplateInfo[] }>(
        "/api/v1/org/condition-templates"
      );
      setTemplates(r.templates);
    } catch (e) {
      setTemplates([]);
      setError(e instanceof ApiError ? e.message : "Could not load templates");
    } finally {
      if (silent) setRefreshing(false);
      else setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!authLoading && user) void loadTemplates();
  }, [authLoading, user, loadTemplates]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return templates;
    return templates.filter((t) => t.name.toLowerCase().includes(q));
  }, [templates, query]);

  async function confirmDelete() {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await api.delete(`/api/v1/org/condition-templates/${deleteTarget.id}`);
      setDeleteTarget(null);
      await loadTemplates({ silent: true });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not delete template");
    } finally {
      setDeleting(false);
    }
  }

  if (authLoading) {
    return (
      <div className="flex min-h-0 flex-1 items-center justify-center p-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!user) {
    return (
      <div className="min-h-0 flex-1 overflow-y-auto p-6">
        <p className="text-sm text-muted-foreground">Sign in to view condition templates.</p>
      </div>
    );
  }

  return (
    <div className="min-h-0 flex-1 overflow-y-auto p-6">
      <div className="mx-auto max-w-4xl">
        <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-xl font-semibold">Condition templates</h1>
            <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
              Org-wide library of saved conditions (including assembly items). Import them into any
              project from the <span className="text-foreground/90">Conditions</span> panel, or add
              new ones with <span className="text-foreground/90">Save as org template</span> while
              editing a condition.
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search templates…"
                className="w-full min-w-[12rem] pl-9 sm:w-56"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                disabled={loading && templates.length === 0}
              />
            </div>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-9 shrink-0"
              disabled={loading || refreshing}
              onClick={() => void loadTemplates({ silent: templates.length > 0 })}
            >
              <RefreshCw className={cn("h-4 w-4", refreshing ? "animate-spin" : "")} />
              <span className="ml-2 hidden sm:inline">Refresh</span>
            </Button>
          </div>
        </div>

        {error ? (
          <div className="mb-4 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
            <button
              type="button"
              className="ml-2 underline underline-offset-2"
              onClick={() => setError(null)}
            >
              Dismiss
            </button>
          </div>
        ) : null}

        {loading && templates.length === 0 ? (
          <div className="flex items-center justify-center py-20 text-sm text-muted-foreground">
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Loading templates…
          </div>
        ) : null}

        {!loading && !error && templates.length === 0 ? (
          <div className="rounded-lg border border-border bg-card/40 px-6 py-10 text-center">
            <p className="text-sm text-muted-foreground">
              No templates yet. Open a project, go to{" "}
              <span className="font-medium text-foreground">Conditions</span>, pick a condition, and
              use <span className="font-medium text-foreground">Save as org template</span>.
            </p>
            <Link
              href="/projects"
              className={cn(buttonVariants({ variant: "default" }), "mt-6 inline-flex")}
            >
              Go to projects
            </Link>
          </div>
        ) : null}

        {templates.length > 0 ? (
          <div className="overflow-hidden rounded-lg border border-border">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/30 text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="px-3 py-2 font-medium">Condition</th>
                  <th className="hidden px-3 py-2 font-medium sm:table-cell">Type</th>
                  <th className="hidden px-3 py-2 font-medium md:table-cell">Unit</th>
                  <th className="hidden px-3 py-2 text-right font-medium lg:table-cell">Assemblies</th>
                  <th className="hidden px-3 py-2 font-medium lg:table-cell">Updated</th>
                  {canManage ? (
                    <th className="w-24 px-2 py-2 text-right font-medium" aria-label="Actions" />
                  ) : null}
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 ? (
                  <tr>
                    <td
                      colSpan={canManage ? 6 : 5}
                      className="px-3 py-8 text-center text-muted-foreground"
                    >
                      No templates match &ldquo;{query.trim()}&rdquo;.
                    </td>
                  </tr>
                ) : (
                  filtered.map((t) => (
                    <tr
                      key={t.id}
                      className="border-b border-border/60 last:border-0 hover:bg-muted/20"
                    >
                      <td className="px-3 py-2">
                        <div className="flex min-w-0 items-center gap-2">
                          <span
                            className="h-2.5 w-2.5 shrink-0 rounded-full border border-border"
                            style={{ backgroundColor: t.color }}
                          />
                          <span className="min-w-0 truncate font-medium text-foreground">
                            {t.name}
                          </span>
                        </div>
                        <div className="mt-0.5 flex flex-wrap gap-x-2 text-[10px] text-muted-foreground sm:hidden">
                          <span>{formatMeasurementTypeLabel(t.measurement_type)}</span>
                          <span>·</span>
                          <span>{t.unit}</span>
                          <span>·</span>
                          <span>{t.assembly_item_count} asm</span>
                        </div>
                      </td>
                      <td className="hidden px-3 py-2 text-muted-foreground sm:table-cell">
                        {formatMeasurementTypeLabel(t.measurement_type)}
                      </td>
                      <td className="hidden px-3 py-2 font-mono text-xs text-muted-foreground md:table-cell">
                        {t.unit}
                      </td>
                      <td className="hidden px-3 py-2 text-right tabular-nums text-muted-foreground lg:table-cell">
                        {t.assembly_item_count}
                      </td>
                      <td className="hidden px-3 py-2 text-xs text-muted-foreground lg:table-cell">
                        {formatShortDate(t.updated_at)}
                      </td>
                      {canManage ? (
                        <td className="px-2 py-1 text-right">
                          <div className="flex justify-end gap-0.5">
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon-sm"
                              className="h-8 w-8 text-muted-foreground hover:text-foreground"
                              aria-label={`Edit template ${t.name}`}
                              onClick={() => setEditTemplateId(t.id)}
                            >
                              <Pencil className="h-4 w-4" />
                            </Button>
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon-sm"
                              className="h-8 w-8 text-muted-foreground hover:text-destructive"
                              aria-label={`Delete template ${t.name}`}
                              onClick={() => setDeleteTarget(t)}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </td>
                      ) : null}
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        ) : null}

        {templates.length > 0 ? (
          <p className="mt-3 text-center text-[11px] text-muted-foreground">
            {filtered.length === templates.length
              ? `${templates.length} template${templates.length === 1 ? "" : "s"}`
              : `${filtered.length} of ${templates.length} shown`}
          </p>
        ) : null}
      </div>

      <EditConditionTemplateDialog
        templateId={editTemplateId}
        open={editTemplateId != null}
        onOpenChange={(o) => {
          if (!o) setEditTemplateId(null);
        }}
        onSaved={() => void loadTemplates({ silent: true })}
      />

      <Dialog open={deleteTarget != null} onOpenChange={(o) => !o && setDeleteTarget(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Delete template?</DialogTitle>
            <DialogDescription>
              Remove &ldquo;{deleteTarget?.name}&rdquo; from the org library. Projects that already
              imported it are unchanged; only the shared template is removed.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button type="button" variant="ghost" onClick={() => setDeleteTarget(null)}>
              Cancel
            </Button>
            <Button
              type="button"
              variant="destructive"
              disabled={deleting}
              onClick={() => void confirmDelete()}
            >
              {deleting ? <Loader2 className="h-4 w-4 animate-spin" /> : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
