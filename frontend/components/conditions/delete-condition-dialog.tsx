"use client";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

interface DeleteConditionDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  conditionName: string;
  measurementCount: number;
  onConfirm: () => void | Promise<void>;
  busy?: boolean;
}

export function DeleteConditionDialog({
  open,
  onOpenChange,
  conditionName,
  measurementCount,
  onConfirm,
  busy,
}: DeleteConditionDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Delete condition?</DialogTitle>
          <DialogDescription className="space-y-2 text-left">
            <span>
              Delete <span className="font-medium text-foreground">{conditionName}</span>
              ? This cannot be undone.
            </span>
            {measurementCount > 0 ? (
              <span className="block text-amber-200">
                This condition has {measurementCount} measurement
                {measurementCount === 1 ? "" : "s"}. Deleting it will remove all associated
                measurements.
              </span>
            ) : null}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter className="gap-2 sm:gap-0">
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={busy}
          >
            Cancel
          </Button>
          <Button
            type="button"
            variant="destructive"
            disabled={busy}
            onClick={() => void onConfirm()}
          >
            {busy ? "Deleting…" : "Delete"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
