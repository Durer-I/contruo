"use client";

/**
 * Internal AI Stage 3a debug page (Sprint AI-03).
 *
 * Owner / admin only. Surfaces every schedule + legend the run extracted with
 * the metadata downstream sprints (AI-04 resolver, AI-06 symbol matcher) will
 * consume. NOT linked from anywhere in the customer-facing UI -- engineering
 * navigates here directly via /internal/ai/runs/{runId}/extractions.
 *
 * Renders:
 * - Schedule table preview (first 5 rows) with the column-role indicators
 *   from the tag-column scorer.
 * - Legend symbol thumbnails for each detected (label, primary template).
 * - The 5x4 multi-scale / multi-rotation variant grid per symbol so the
 *   template matcher's input matrix is inspectable at a glance.
 */

import { useEffect, useState, use } from "react";
import { Loader2, AlertCircle, ChevronDown, ChevronRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/providers/auth-provider";
import {
  getRunExtractions,
  type AiRunExtractionsResponse,
  type ExtractedLegendRow,
  type ExtractedScheduleRow,
} from "@/lib/internal-ai";
import { cn } from "@/lib/utils";

interface PageProps {
  params: Promise<{ runId: string }>;
}

export default function ExtractionsDebugPage({ params }: PageProps) {
  const { runId } = use(params);
  const { user } = useAuth();
  const [data, setData] = useState<AiRunExtractionsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const isPrivileged = user?.role === "owner" || user?.role === "admin";

  useEffect(() => {
    if (!isPrivileged) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        setLoading(true);
        const resp = await getRunExtractions(runId);
        if (cancelled) return;
        setData(resp);
        setError(null);
      } catch (e) {
        if (cancelled) return;
        if (e instanceof ApiError) setError(`${e.code}: ${e.message}`);
        else setError(String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [runId, isPrivileged]);

  if (!user) {
    return (
      <div className="p-8 text-sm text-muted-foreground">
        <Loader2 className="mr-2 inline-block h-4 w-4 animate-spin" />
        Loading session...
      </div>
    );
  }

  if (!isPrivileged) {
    return (
      <div className="p-8">
        <div className="flex items-start gap-3 rounded-md border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive-foreground">
          <AlertCircle className="mt-0.5 h-4 w-4 flex-none" />
          <div>
            <div className="font-medium">Restricted</div>
            <div className="mt-1 text-muted-foreground">
              The AI extractions debug page is only available to organization
              owners and admins.
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="p-8 text-sm text-muted-foreground">
        <Loader2 className="mr-2 inline-block h-4 w-4 animate-spin" />
        Loading extractions for run {runId.slice(0, 8)}...
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8">
        <div className="flex items-start gap-3 rounded-md border border-destructive/30 bg-destructive/10 p-4 text-sm">
          <AlertCircle className="mt-0.5 h-4 w-4 flex-none text-destructive" />
          <div>
            <div className="font-medium">Failed to load extractions</div>
            <div className="mt-1 text-muted-foreground">{error}</div>
          </div>
        </div>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="space-y-8 p-8">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold">AI run extractions</h1>
        <div className="flex flex-wrap gap-3 text-sm text-muted-foreground">
          <span>Run: {data.ai_run_id.slice(0, 8)}</span>
          <span>Plan: {data.plan_id.slice(0, 8)}</span>
          {data.summary.run_status && (
            <span>Status: {data.summary.run_status}</span>
          )}
          <span>Schedules: {data.summary.schedule_count ?? data.schedules.length}</span>
          <span>Legends: {data.summary.legend_count ?? data.legends.length}</span>
        </div>
        {data.summary.schedules_legends && (
          <pre className="overflow-x-auto rounded-md border bg-muted/30 p-3 text-xs">
            {JSON.stringify(data.summary.schedules_legends, null, 2)}
          </pre>
        )}
      </header>

      <section>
        <h2 className="mb-3 text-lg font-semibold">
          Schedules ({data.schedules.length})
        </h2>
        {data.schedules.length === 0 ? (
          <div className="rounded-md border border-dashed bg-muted/30 p-6 text-center text-sm text-muted-foreground">
            No schedules extracted on this run.
          </div>
        ) : (
          <div className="space-y-4">
            {data.schedules.map((s) => (
              <ScheduleCard key={s.id} schedule={s} />
            ))}
          </div>
        )}
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold">
          Legend symbols ({data.legends.length})
        </h2>
        {data.legends.length === 0 ? (
          <div className="rounded-md border border-dashed bg-muted/30 p-6 text-center text-sm text-muted-foreground">
            No legend symbols extracted on this run.
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {data.legends.map((l) => (
              <LegendCard key={l.id} legend={l} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function ScheduleCard({ schedule }: { schedule: ExtractedScheduleRow }) {
  const [expanded, setExpanded] = useState(false);
  const Icon = expanded ? ChevronDown : ChevronRight;

  return (
    <div className="rounded-md border bg-card">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center justify-between gap-3 border-b border-border/40 p-3 text-left hover:bg-muted/20"
      >
        <div className="flex items-center gap-3 text-sm">
          <Icon className="h-4 w-4 text-muted-foreground" />
          <span className="font-medium">
            {schedule.sheet_number || schedule.sheet_name || "Unnamed sheet"}
          </span>
          <Badge variant="outline" className="font-mono text-xs">
            {schedule.extraction_method}
          </Badge>
          <span className="text-xs text-muted-foreground">
            {schedule.headers.length} columns &middot; {schedule.row_count} rows
          </span>
        </div>
        <ColumnRoleBadges schedule={schedule} />
      </button>

      {expanded && (
        <div className="overflow-x-auto p-3">
          <table className="w-full border-collapse text-xs">
            <thead>
              <tr className="border-b border-border/60">
                {schedule.headers.map((h, i) => (
                  <th
                    key={i}
                    className={cn(
                      "border-r border-border/40 p-2 text-left font-medium",
                      i === schedule.tag_column_index && "bg-purple-500/15",
                      i === schedule.description_column_index && "bg-blue-500/15",
                      i === schedule.quantity_column_index && "bg-green-500/15",
                      i === schedule.material_column_index && "bg-amber-500/15",
                      schedule.dimension_column_indexes?.includes(i) &&
                        "bg-cyan-500/15"
                    )}
                  >
                    <div>{h || <em className="text-muted-foreground">empty</em>}</div>
                    <div className="mt-0.5 font-mono text-[10px] text-muted-foreground">
                      col {i}
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {schedule.sample_rows.map((row, ri) => (
                <tr key={ri} className="border-b border-border/30">
                  {schedule.headers.map((_h, ci) => (
                    <td
                      key={ci}
                      className="border-r border-border/40 p-2 align-top"
                    >
                      {row[ci] ?? ""}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          {schedule.row_count > schedule.sample_rows.length && (
            <div className="mt-2 text-xs text-muted-foreground">
              Showing first {schedule.sample_rows.length} of {schedule.row_count}{" "}
              rows.
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ColumnRoleBadges({ schedule }: { schedule: ExtractedScheduleRow }) {
  const items: Array<{ label: string; value: number | number[] | null; color: string }> = [
    { label: "tag", value: schedule.tag_column_index, color: "bg-purple-500/15 text-purple-400" },
    { label: "desc", value: schedule.description_column_index, color: "bg-blue-500/15 text-blue-400" },
    { label: "qty", value: schedule.quantity_column_index, color: "bg-green-500/15 text-green-400" },
    { label: "mat", value: schedule.material_column_index, color: "bg-amber-500/15 text-amber-400" },
    { label: "dim", value: schedule.dimension_column_indexes, color: "bg-cyan-500/15 text-cyan-400" },
  ];
  return (
    <div className="hidden gap-1 md:flex">
      {items.map((it) => {
        const display =
          it.value == null
            ? "-"
            : Array.isArray(it.value)
              ? it.value.join(",")
              : String(it.value);
        return (
          <span
            key={it.label}
            className={cn(
              "inline-flex items-center gap-1 rounded px-1.5 py-0.5 font-mono text-[10px]",
              it.color
            )}
          >
            {it.label}: {display}
          </span>
        );
      })}
    </div>
  );
}

function LegendCard({ legend }: { legend: ExtractedLegendRow }) {
  const [showVariants, setShowVariants] = useState(false);
  return (
    <div className="rounded-md border bg-card p-3">
      <div className="flex items-start gap-3">
        {legend.primary_signed_url ? (
          // eslint-disable-next-line @next/next/no-img-element -- internal debug page; signed URL works as-is
          <img
            src={legend.primary_signed_url}
            alt={legend.label}
            className="h-20 w-20 flex-none rounded border bg-white object-contain"
          />
        ) : (
          <div className="flex h-20 w-20 flex-none items-center justify-center rounded border bg-muted text-xs text-muted-foreground">
            no preview
          </div>
        )}
        <div className="flex-1 space-y-1 text-sm">
          <div className="font-medium">{legend.label}</div>
          <div className="text-xs text-muted-foreground">
            {legend.sheet_number || legend.sheet_name || "Unknown sheet"}
          </div>
          <div className="flex flex-wrap gap-1">
            <Badge variant="outline" className="font-mono text-[10px]">
              {legend.extraction_method}
            </Badge>
            <Badge variant="outline" className="font-mono text-[10px]">
              hash {legend.template_hash.slice(0, 8)}
            </Badge>
            <Badge variant="outline" className="font-mono text-[10px]">
              {legend.variants.length} variants
            </Badge>
          </div>
        </div>
      </div>
      <Button
        variant="ghost"
        size="sm"
        onClick={() => setShowVariants((v) => !v)}
        className="mt-3 h-7 px-2 text-xs"
      >
        {showVariants ? "Hide variants" : "Show variants"}
      </Button>
      {showVariants && (
        <div className="mt-3 grid grid-cols-5 gap-1">
          {legend.variants.map((v) => (
            <div
              key={`${v.scale}_${v.rotation}`}
              className="flex flex-col items-center gap-1 rounded border bg-muted/20 p-1"
            >
              {v.signed_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={v.signed_url}
                  alt={`${legend.label} ${v.scale}x ${v.rotation}deg`}
                  className="h-12 w-12 bg-white object-contain"
                />
              ) : (
                <div className="flex h-12 w-12 items-center justify-center text-[10px] text-muted-foreground">
                  ?
                </div>
              )}
              <div className="font-mono text-[9px] text-muted-foreground">
                {v.scale.toFixed(2)} / {v.rotation}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
