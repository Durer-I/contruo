import * as React from "react";
import { cn } from "@/lib/utils";

/** shadcn/ui-style multiline input. Mirrors ``Input`` but renders a ``<textarea>``. */
export const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(function Textarea({ className, ...props }, ref) {
  return (
    <textarea
      ref={ref}
      className={cn(
        "flex min-h-[72px] w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm text-foreground shadow-sm",
        "placeholder:text-muted-foreground",
        "outline-none transition-colors",
        "focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40",
        "disabled:cursor-not-allowed disabled:opacity-50",
        className
      )}
      {...props}
    />
  );
});
