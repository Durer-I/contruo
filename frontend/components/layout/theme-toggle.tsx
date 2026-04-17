"use client";

import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";

import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface ThemeToggleProps {
  collapsed: boolean;
}

export function ThemeToggle({ collapsed }: ThemeToggleProps) {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const isDark = resolvedTheme === "dark";
  const nextLabel = isDark ? "Switch to light mode" : "Switch to dark mode";

  const icon = mounted ? (
    isDark ? (
      <Sun className="h-5 w-5 shrink-0" aria-hidden />
    ) : (
      <Moon className="h-5 w-5 shrink-0" aria-hidden />
    )
  ) : (
    <Sun className="h-5 w-5 shrink-0 opacity-30" aria-hidden />
  );

  const label = (
    <span className="text-sm font-medium text-muted-foreground">
      {mounted ? (isDark ? "Light mode" : "Dark mode") : "Theme"}
    </span>
  );

  if (collapsed) {
    return (
      <Tooltip>
        <TooltipTrigger
          render={
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="w-full justify-center px-3"
              onClick={() => setTheme(isDark ? "light" : "dark")}
              aria-label={nextLabel}
            />
          }
        >
          {icon}
        </TooltipTrigger>
        <TooltipContent side="right">{nextLabel}</TooltipContent>
      </Tooltip>
    );
  }

  return (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      className="w-full justify-start gap-3 px-3"
      onClick={() => setTheme(isDark ? "light" : "dark")}
      aria-label={nextLabel}
    >
      {icon}
      {label}
    </Button>
  );
}
