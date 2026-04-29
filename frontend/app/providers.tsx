"use client";

import { useState } from "react";
import { ThemeProvider } from "next-themes";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TooltipProvider } from "@/components/ui/tooltip";
import { DevHttpInstrumentation } from "@/components/dev/dev-http-instrumentation";

export function AppProviders({ children }: { children: React.ReactNode }) {
  // One QueryClient per browser session; useState ensures a single instance.
  // Defaults are conservative: data is stale immediately for hot reads but kept
  // in cache for 5 minutes so back/forward navigation is instant.
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            gcTime: 5 * 60_000,
            refetchOnWindowFocus: false,
            retry: 1,
          },
          mutations: { retry: 0 },
        },
      })
  );

  return (
    // Dark-first per project design rules; users can still override via the theme switcher.
    <ThemeProvider
      attribute="class"
      defaultTheme="dark"
      enableSystem={false}
      storageKey="contruo-theme"
      disableTransitionOnChange
    >
      <QueryClientProvider client={queryClient}>
        <TooltipProvider delay={500}>
          <DevHttpInstrumentation />
          {children}
        </TooltipProvider>
      </QueryClientProvider>
    </ThemeProvider>
  );
}
