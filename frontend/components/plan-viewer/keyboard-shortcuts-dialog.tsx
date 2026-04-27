"use client";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

const SECTIONS: { title: string; rows: { keys: string; action: string }[] }[] = [
  {
    title: "Tools",
    rows: [
      { keys: "V", action: "Select" },
      { keys: "L", action: "Linear takeoff" },
      { keys: "A", action: "Area takeoff" },
      { keys: "C", action: "Count takeoff" },
      { keys: "S", action: "Scale calibration" },
    ],
  },
  {
    title: "Conditions & sheets",
    rows: [
      { keys: "1–9", action: "Select first nine conditions (order in menu)" },
      { keys: "[", action: "Previous sheet" },
      { keys: "]", action: "Next sheet" },
    ],
  },
  {
    title: "Drawing",
    rows: [
      { keys: "Enter", action: "Complete linear or polygon area" },
      { keys: "Escape", action: "Cancel draft, exit count mode, or clear selection" },
      { keys: "Delete / Backspace", action: "Delete selected measurement(s)" },
      { keys: "Ctrl+Z", action: "Undo last vertex while drawing; then undo last created measurement" },
      { keys: "Ctrl+Shift+Z", action: "Redo last undone measurement" },
      { keys: "Double-click", action: "Complete linear takeoff while drawing" },
    ],
  },
  {
    title: "Workspace",
    rows: [
      { keys: "Ctrl+F", action: "Find text in plans" },
      { keys: "Ctrl+E", action: "Export quantities" },
      { keys: "Ctrl+0", action: "Fit page" },
      { keys: "Ctrl+2", action: "Fit width" },
      { keys: "+ / −", action: "Zoom in / out" },
      { keys: "Space + drag", action: "Pan (on canvas)" },
      { keys: "?", action: "Open this help" },
    ],
  },
];

interface KeyboardShortcutsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function KeyboardShortcutsDialog({
  open,
  onOpenChange,
}: KeyboardShortcutsDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] max-w-lg overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Keyboard shortcuts</DialogTitle>
          <DialogDescription>
            Shortcuts are disabled while typing in a field or when a modal has focus. On Mac,{" "}
            <kbd className="rounded bg-muted px-1 font-mono text-xs">⌘</kbd> works in place of{" "}
            <kbd className="rounded bg-muted px-1 font-mono text-xs">Ctrl</kbd>.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 text-sm">
          {SECTIONS.map((sec) => (
            <div key={sec.title}>
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {sec.title}
              </h3>
              <ul className="space-y-1.5">
                {sec.rows.map((row) => (
                  <li
                    key={row.keys + row.action}
                    className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 border-b border-border/60 py-1.5 last:border-0"
                  >
                    <span className="text-muted-foreground">{row.action}</span>
                    <kbd className="shrink-0 rounded border border-border bg-muted/60 px-1.5 py-0.5 font-mono text-xs text-foreground">
                      {row.keys}
                    </kbd>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}
