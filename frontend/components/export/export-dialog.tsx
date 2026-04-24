"use client";

import { useCallback, useState } from "react";
import { Download, FileSpreadsheet, FileText, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { ExportFormat, ExportStatusResponse } from "@/types/export";

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}

async function pollExport(taskId: string): Promise<ExportStatusResponse> {
  const deadline = Date.now() + 120_000;
  while (Date.now() < deadline) {
    const s = await api.get<ExportStatusResponse>(`/api/v1/exports/${taskId}`);
    if (s.status === "success" && s.download_url) return s;
    if (s.status === "failure") {
      throw new Error(s.error || "Export failed");
    }
    await sleep(750);
  }
  throw new Error("Export timed out — try again or check the worker is running.");
}

async function downloadFile(url: string, filename: string) {
  const res = await fetch(url, { mode: "cors" });
  if (!res.ok) {
    window.open(url, "_blank", "noopener,noreferrer");
    return;
  }
  const blob = await res.blob();
  const u = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = u;
  a.download = filename;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(u);
}

export interface ExportDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectId: string;
  projectName: string;
  summary: { conditions: number; measurements: number; sheets: number };
}

export function ExportDialog({
  open,
  onOpenChange,
  projectId,
  projectName,
  summary,
}: ExportDialogProps) {
  const [format, setFormat] = useState<ExportFormat>("xlsx");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runExport = useCallback(async () => {
    setError(null);
    setBusy(true);
    try {
      const q = await api.post<{ task_id: string }>(`/api/v1/projects/${projectId}/export`, {
        format,
      });
      const done = await pollExport(q.task_id);
      if (done.download_url && done.filename) {
        await downloadFile(done.download_url, done.filename);
      }
      onOpenChange(false);
    } catch (e) {
      const msg =
        e instanceof ApiError ? e.message : e instanceof Error ? e.message : "Export failed";
      setError(msg);
    } finally {
      setBusy(false);
    }
  }, [format, projectId, onOpenChange]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Download className="h-4 w-4" aria-hidden />
            Export quantities
          </DialogTitle>
          <DialogDescription>
            Full project export — same grouped layout as the Quantities panel. Assembly breakdowns are
            not included.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3 text-sm">
          <div className="rounded-md border border-border bg-muted/30 px-3 py-2 text-xs">
            <div className="font-medium text-foreground">{projectName}</div>
            <div className="mt-1 text-muted-foreground">
              Scope: <span className="text-foreground/90">Full project</span>
            </div>
            <div className="mt-0.5 font-mono text-[11px] text-muted-foreground">
              {summary.conditions} conditions · {summary.measurements} measurements · {summary.sheets}{" "}
              sheets
            </div>
          </div>

          <div className="text-xs font-medium text-muted-foreground">Format</div>
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              disabled={busy}
              onClick={() => setFormat("xlsx")}
              className={cn(
                "flex flex-col items-start gap-1 rounded-lg border px-3 py-2 text-left text-xs transition-colors",
                format === "xlsx"
                  ? "border-primary bg-primary/10 text-foreground"
                  : "border-border hover:bg-muted/50"
              )}
            >
              <FileSpreadsheet className="h-4 w-4" />
              <span className="font-medium">Excel</span>
              <span className="text-[10px] text-muted-foreground">.xlsx</span>
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => setFormat("pdf")}
              className={cn(
                "flex flex-col items-start gap-1 rounded-lg border px-3 py-2 text-left text-xs transition-colors",
                format === "pdf"
                  ? "border-primary bg-primary/10 text-foreground"
                  : "border-border hover:bg-muted/50"
              )}
            >
              <FileText className="h-4 w-4" />
              <span className="font-medium">PDF</span>
              <span className="text-[10px] text-muted-foreground">print-ready</span>
            </button>
          </div>

          {error ? <p className="text-xs text-destructive">{error}</p> : null}
        </div>

        <DialogFooter className="gap-2 sm:gap-0">
          <Button type="button" variant="ghost" disabled={busy} onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button type="button" disabled={busy} onClick={() => void runExport()}>
            {busy ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Generating…
              </>
            ) : (
              <>
                <Download className="mr-2 h-4 w-4" />
                Export
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
