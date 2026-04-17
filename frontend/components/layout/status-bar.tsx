"use client";

export function StatusBar() {
  return (
    <footer className="flex h-7 shrink-0 items-center border-t border-border bg-surface px-4 text-xs text-muted-foreground">
      <span>Ready</span>
      <span className="mx-2">•</span>
      <span>v0.1.0</span>
    </footer>
  );
}
