"use client";

import * as React from "react";
import { Eye, EyeOff } from "lucide-react";

import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export type PasswordInputProps = Omit<React.ComponentProps<typeof Input>, "type">;

/** Password field with show/hide toggle (eye icon). */
export function PasswordInput({ className, ...props }: PasswordInputProps) {
  const [visible, setVisible] = React.useState(false);

  return (
    <div className="relative w-full">
      <Input
        type={visible ? "text" : "password"}
        className={cn("h-9 min-h-9 pr-9", className)}
        {...props}
      />
      {/* inset-y-0 + flex center avoids top/translate jitter when toggling type */}
      <div className="pointer-events-none absolute inset-y-0 right-0 z-10 flex w-9 items-center justify-center">
        <Button
          type="button"
          variant="ghost"
          className="pointer-events-auto size-8 shrink-0 rounded-md text-muted-foreground hover:bg-muted/40 hover:text-foreground"
          onClick={() => setVisible((v) => !v)}
          tabIndex={-1}
          aria-label={visible ? "Hide password" : "Show password"}
          aria-pressed={visible}
        >
          <span className="flex size-4 items-center justify-center" aria-hidden>
            {visible ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
          </span>
        </Button>
      </div>
    </div>
  );
}
