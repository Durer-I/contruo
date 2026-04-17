"use client";

import { ThemeProvider } from "next-themes";
import { TooltipProvider } from "@/components/ui/tooltip";

export function AppProviders({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="light"
      enableSystem={false}
      storageKey="contruo-theme"
      disableTransitionOnChange
    >
      <TooltipProvider delay={500}>{children}</TooltipProvider>
    </ThemeProvider>
  );
}
