"use client";

import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";

const UNITS = ["ft", "in", "m", "mm", "cm"] as const;

interface ScaleCalibrationDialogProps {
  open: boolean;
  onCancel: () => void;
  pdfLineLengthPoints: number;
  initialDistance?: string;
  initialUnit?: string;
  onSubmit: (realDistance: number, realUnit: string) => Promise<void>;
}

export function ScaleCalibrationDialog({
  open,
  onCancel,
  pdfLineLengthPoints,
  initialDistance,
  initialUnit,
  onSubmit,
}: ScaleCalibrationDialogProps) {
  const [distance, setDistance] = useState(initialDistance ?? "");
  const [unit, setUnit] = useState(initialUnit ?? "ft");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setDistance(initialDistance ?? "");
      setUnit(initialUnit ?? "ft");
      setError(null);
    }
  }, [open, initialDistance, initialUnit]);

  async function submit() {
    setError(null);
    const n = parseFloat(distance.replace(",", "."));
    if (!Number.isFinite(n) || n <= 0) {
      setError("Enter a positive number.");
      return;
    }
    setBusy(true);
    try {
      await onSubmit(n, unit);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save scale");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={() => {}} disablePointerDismissal modal>
      <DialogContent className="sm:max-w-md" showCloseButton={false}>
        <DialogHeader>
          <DialogTitle>Enter real-world distance</DialogTitle>
        </DialogHeader>
        <p className="text-xs text-muted-foreground">
          PDF segment length:{" "}
          <span className="font-mono text-foreground">
            {pdfLineLengthPoints.toFixed(2)}
          </span>{" "}
          pt (PDF space). Enter the real-world distance this line represents.
        </p>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1.5">
            <label htmlFor="real-dist" className="text-sm font-medium">
              Distance
            </label>
            <Input
              id="real-dist"
              value={distance}
              onChange={(e) => setDistance(e.target.value)}
              placeholder="e.g. 10"
              className="font-mono"
            />
          </div>
          <div className="space-y-1.5">
            <label htmlFor="real-unit" className="text-sm font-medium">
              Unit
            </label>
            <NativeSelect
              id="real-unit"
              value={unit}
              onChange={(e) => setUnit(e.target.value)}
            >
              {UNITS.map((u) => (
                <option key={u} value={u}>
                  {u}
                </option>
              ))}
            </NativeSelect>
          </div>
        </div>
        {error && (
          <p className="text-xs text-destructive" role="alert">
            {error}
          </p>
        )}
        <DialogFooter>
          <Button type="button" variant="ghost" onClick={onCancel} disabled={busy}>
            Cancel
          </Button>
          <Button type="button" onClick={() => void submit()} disabled={busy}>
            {busy ? "Saving..." : "Save scale"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
