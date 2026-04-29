"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";

/** Project-scoped error boundary so a viewer crash doesn't take down the whole shell. */
export default function ProjectError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    if (process.env.NODE_ENV !== "production") {
      // eslint-disable-next-line no-console
      console.error("[Contruo] Project workspace error:", error);
    }
  }, [error]);

  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center">
      <h2 className="text-lg font-semibold">Couldn&apos;t load this project</h2>
      <p className="max-w-sm text-sm text-muted-foreground">
        Something went wrong inside the takeoff workspace. The team has been
        notified. You can retry, or go back to the dashboard.
      </p>
      {error.digest ? (
        <p className="font-mono text-xs text-muted-foreground">
          digest: {error.digest}
        </p>
      ) : null}
      <div className="mt-2 flex gap-2">
        <Button onClick={() => reset()}>Retry</Button>
        <Button variant="outline" onClick={() => (location.href = "/dashboard")}>
          Back to dashboard
        </Button>
      </div>
    </div>
  );
}
