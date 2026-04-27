"use client";

import { Select as SelectPrimitive } from "@base-ui/react/select";
import { CheckIcon, ChevronDownIcon, ChevronsUpDownIcon } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

function SelectRoot({ ...props }: React.ComponentProps<typeof SelectPrimitive.Root>) {
  return <SelectPrimitive.Root data-slot="select" {...props} />;
}

function SelectTrigger({
  className,
  size = "default",
  variant = "default",
  children,
  ...props
}: React.ComponentProps<typeof SelectPrimitive.Trigger> & {
  size?: "default" | "sm";
  /** Borderless, transparent trigger; chevrons up–down icon. */
  variant?: "default" | "bare";
}) {
  return (
    <SelectPrimitive.Trigger
      data-slot="select-trigger"
      data-variant={variant}
      className={cn(
        "w-full min-w-0 cursor-pointer text-left text-foreground outline-none transition-colors",
        "data-disabled:pointer-events-none data-disabled:opacity-50",
        variant === "default" &&
          "flex items-center justify-between gap-1.5 rounded-lg border border-border bg-background px-2 text-sm shadow-sm hover:bg-muted/60 focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40 data-popup-open:border-ring data-popup-open:ring-2 data-popup-open:ring-ring/30",
        variant === "bare" &&
          "grid grid-cols-[minmax(0,1fr)_auto] items-center gap-1 rounded-md border-2 border-primary/80 bg-transparent px-2 py-1 text-sm shadow-none hover:border-primary/100 hover:bg-transparent focus-visible:border-primary focus-visible:ring-1 focus-visible:ring-primary/35 data-popup-open:border-primary data-popup-open:ring-1 data-popup-open:ring-primary/25",
        variant === "default" && size === "sm" && "h-7 text-[10px]",
        variant === "default" && size === "default" && "h-8 text-xs",
        variant === "bare" && size === "sm" && "min-h-6 text-xs",
        variant === "bare" && size === "default" && "h-6 text-xs",
        className
      )}
      {...props}
    >
      {children}
      <SelectPrimitive.Icon
        data-slot="select-icon"
        className={cn(
          "pointer-events-none shrink-0 text-muted-foreground [&_svg]:size-3.5",
          variant === "bare" && "[&_svg]:size-4"
        )}
      >
        {variant === "bare" ? <ChevronsUpDownIcon /> : <ChevronDownIcon />}
      </SelectPrimitive.Icon>
    </SelectPrimitive.Trigger>
  );
}

function SelectValue({ className, ...props }: React.ComponentProps<typeof SelectPrimitive.Value>) {
  return (
    <SelectPrimitive.Value
      data-slot="select-value"
      className={cn("min-w-0 flex-1 truncate", className)}
      {...props}
    />
  );
}

function SelectPortal({ ...props }: React.ComponentProps<typeof SelectPrimitive.Portal>) {
  return <SelectPrimitive.Portal data-slot="select-portal" {...props} />;
}

function SelectPositioner({
  className,
  sideOffset = 4,
  align = "start",
  ...props
}: React.ComponentProps<typeof SelectPrimitive.Positioner>) {
  return (
    <SelectPrimitive.Positioner
      data-slot="select-positioner"
      className={cn("isolate z-50 outline-none", className)}
      sideOffset={sideOffset}
      align={align}
      {...props}
    />
  );
}

function SelectPopup({ className, ...props }: React.ComponentProps<typeof SelectPrimitive.Popup>) {
  return (
    <SelectPrimitive.Popup
      data-slot="select-popup"
      className={cn(
        "max-h-(--available-height) min-w-(--anchor-width) origin-(--transform-origin) overflow-y-auto rounded-lg border border-border bg-popover p-1 text-popover-foreground shadow-none",
        "data-open:animate-in data-open:fade-in-0 data-open:zoom-in-95",
        "data-closed:animate-out data-closed:fade-out-0 data-closed:zoom-out-95",
        className
      )}
      {...props}
    />
  );
}

function SelectList({ className, ...props }: React.ComponentProps<typeof SelectPrimitive.List>) {
  return (
    <SelectPrimitive.List data-slot="select-list" className={cn("py-0.5", className)} {...props} />
  );
}

function SelectItem({
  className,
  children,
  ...props
}: React.ComponentProps<typeof SelectPrimitive.Item>) {
  return (
    <SelectPrimitive.Item
      data-slot="select-item"
      className={cn(
        "relative flex cursor-pointer select-none items-center gap-2 rounded-md py-1.5 pr-8 pl-2 text-xs text-foreground outline-none",
        "data-highlighted:bg-muted data-highlighted:text-foreground",
        "data-disabled:pointer-events-none data-disabled:opacity-50",
        className
      )}
      {...props}
    >
      <SelectPrimitive.ItemText className="min-w-0 flex-1">{children}</SelectPrimitive.ItemText>
      <span className="pointer-events-none absolute right-1.5 flex size-4 items-center justify-center">
        <SelectPrimitive.ItemIndicator>
          <CheckIcon className="size-3.5 text-primary" />
        </SelectPrimitive.ItemIndicator>
      </span>
    </SelectPrimitive.Item>
  );
}

export {
  SelectRoot as Select,
  SelectTrigger,
  SelectValue,
  SelectPortal,
  SelectPositioner,
  SelectPopup,
  SelectList,
  SelectItem,
};
