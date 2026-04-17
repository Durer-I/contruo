"use client";

import { ChevronDown, ChevronUp, Search, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import type { SearchHit } from "@/types/project";

interface PlanSearchPanelProps {
  open: boolean;
  query: string;
  onQueryChange: (q: string) => void;
  onClose: () => void;
  matches: SearchHit[];
  loading: boolean;
  activeSheetId: string | null;
  onPickSheet: (sheetId: string) => void;
  localMatchIndex: number;
  localMatchCount: number;
  onPrevLocal: () => void;
  onNextLocal: () => void;
}

export function PlanSearchPanel({
  open,
  query,
  onQueryChange,
  onClose,
  matches,
  loading,
  activeSheetId,
  onPickSheet,
  localMatchIndex,
  localMatchCount,
  onPrevLocal,
  onNextLocal,
}: PlanSearchPanelProps) {
  if (!open) return null;

  return (
    <div
      className={cn(
        "absolute right-3 top-14 z-20 flex w-[min(100%,22rem)] flex-col rounded-md border border-border bg-card shadow-lg"
      )}
    >
      <div className="flex items-center gap-1 border-b border-border p-2">
        <Search className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
        <Input
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          placeholder="Find in plans…"
          className="h-8 flex-1 text-xs"
          autoFocus
        />
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          title="Close"
          onClick={onClose}
        >
          <X className="h-4 w-4" />
        </Button>
      </div>

      <div className="flex items-center justify-between gap-2 border-b border-border px-2 py-1.5 text-[11px] text-muted-foreground">
        <span className="min-w-0 flex-1 leading-snug">
          {query.trim().length >= 2 && matches.length > 0 && (
            <span className="block text-foreground/90">
              {matches.length} sheet{matches.length === 1 ? "" : "s"} with hits
            </span>
          )}
          {localMatchCount > 0
            ? `On this page: ${localMatchIndex + 1} / ${localMatchCount}`
            : query.trim().length >= 2
              ? "No matches on this page"
              : "Type at least 2 characters"}
        </span>
        <div className="flex gap-0.5">
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            title="Previous match on page (Shift+Enter)"
            disabled={localMatchCount === 0}
            onClick={onPrevLocal}
          >
            <ChevronUp className="h-4 w-4" />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            title="Next match on page (Enter)"
            disabled={localMatchCount === 0}
            onClick={onNextLocal}
          >
            <ChevronDown className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <div className="max-h-56 overflow-auto p-1">
        {loading && (
          <p className="px-2 py-3 text-center text-xs text-muted-foreground">
            Searching…
          </p>
        )}
        {!loading && matches.length === 0 && query.trim().length >= 2 && (
          <p className="px-2 py-3 text-center text-xs text-muted-foreground">
            No sheets contain that text.
          </p>
        )}
        {!loading &&
          matches.map((m) => (
            <button
              key={`${m.sheet_id}-${m.page_number}`}
              type="button"
              onClick={() => onPickSheet(m.sheet_id)}
              className={cn(
                "flex w-full flex-col gap-0.5 rounded-sm px-2 py-1.5 text-left text-xs transition-colors",
                m.sheet_id === activeSheetId
                  ? "bg-primary/10 text-foreground"
                  : "hover:bg-surface-overlay"
              )}
            >
              <span className="font-medium leading-tight">
                {m.sheet_name ?? `Page ${m.page_number}`}
              </span>
              <span className="line-clamp-2 text-[10px] text-muted-foreground">
                {m.snippet}
              </span>
            </button>
          ))}
      </div>
    </div>
  );
}
