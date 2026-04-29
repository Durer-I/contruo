"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";

/**
 * Global error boundary for the App Router. Caught here, the segment crash
 * stops cascading and the user gets a clean recovery surface instead of a
 * blank screen.
 */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    if (process.env.NODE_ENV !== "production") {
      // eslint-disable-next-line no-console
      console.error("[Contruo] App-level error:", error);
    }
  }, [error]);

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 px-6 text-center">
      <div className="space-y-2">
        <p className="text-sm font-medium uppercase tracking-wide text-muted-foreground">
          Something broke
        </p>
        <h1 className="text-2xl font-semibold tracking-tight">
          We hit an unexpected error
        </h1>
        <p className="max-w-md text-sm text-muted-foreground">
          The screen failed to render. Try again, or refresh the page. If this
          keeps happening, please contact support with the request id below.
        </p>
        {error.digest ? (
          <p className="font-mono text-xs text-muted-foreground">
            digest: {error.digest}
          </p>
        ) : null}
      </div>
      <div className="flex gap-2">
        <Button onClick={() => reset()}>Try again</Button>
        <Button variant="outline" onClick={() => location.reload()}>
          Refresh
        </Button>
      </div>
    </div>
  );
}
