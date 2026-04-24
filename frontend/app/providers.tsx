"use client";

import { ThemeProvider } from "next-themes";
import { TooltipProvider } from "@/components/ui/tooltip";
import { DevHttpInstrumentation } from "@/components/dev/dev-http-instrumentation";

export function AppProviders({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="light"
      enableSystem={false}
      storageKey="contruo-theme"
      disableTransitionOnChange
    >
      <TooltipProvider delay={500}>
        <DevHttpInstrumentation />
        {children}
      </TooltipProvider>
    </ThemeProvider>
  );
}
