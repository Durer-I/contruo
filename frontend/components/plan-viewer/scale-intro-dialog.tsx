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

interface ScaleIntroDialogProps {
  open: boolean;
  onContinue: () => void;
  onCancel: () => void;
}

export function ScaleIntroDialog({ open, onContinue, onCancel }: ScaleIntroDialogProps) {
  return (
    <Dialog open={open} onOpenChange={() => {}} disablePointerDismissal modal>
      <DialogContent className="sm:max-w-md" showCloseButton={false}>
        <DialogHeader>
          <DialogTitle>Calibrate scale</DialogTitle>
          <DialogDescription className="text-left text-sm leading-relaxed">
            Click two points on the plan that match a known real-world distance (for example, a
            dimension line or a wall length). Then you will be prompted to enter that distance
            and unit.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button type="button" variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
          <Button type="button" onClick={onContinue}>
            Continue
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
