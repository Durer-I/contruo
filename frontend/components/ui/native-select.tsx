"use client";

import * as React from "react";
import { ChevronDown } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * shadcn/ui-style wrapper around a native ``<select>`` element.
 *
 * Use this for dense forms where the full Select primitive (with portal,
 * positioner, popup, list, item) would be overkill — e.g. unit pickers,
 * row-level inline editors, settings dropdowns. Renders a consistent border,
 * focus ring, height, and chevron so we stop accumulating one-off styled
 * native selects across the codebase.
 *
 * For richer needs (search, custom item rendering, async data) reach for the
 * ``Select`` primitive in ``./select.tsx`` instead.
 */
export interface NativeSelectProps
  extends Omit<React.SelectHTMLAttributes<HTMLSelectElement>, "size"> {
  size?: "sm" | "default";
}

export const NativeSelect = React.forwardRef<HTMLSelectElement, NativeSelectProps>(
  function NativeSelect({ className, size = "default", children, ...props }, ref) {
    return (
      <div className="relative inline-flex w-full">
        <select
          ref={ref}
          className={cn(
            "w-full appearance-none rounded-md border border-border bg-background pl-2 pr-7 text-foreground",
            "shadow-sm transition-colors hover:bg-muted/40",
            "focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40",
            "disabled:cursor-not-allowed disabled:opacity-50",
            size === "sm" ? "h-7 text-[11px]" : "h-8 text-xs",
            className
          )}
          {...props}
        >
          {children}
        </select>
        <ChevronDown
          aria-hidden
          className="pointer-events-none absolute right-2 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground"
        />
      </div>
    );
  }
);
