"use client";

import { useEffect, useId, useState } from "react";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";

export interface DeleteProjectTarget {
  id: string;
  name: string;
}

interface DeleteProjectDialogProps {
  project: DeleteProjectTarget | null;
  onClose: () => void;
  /** Called after the API delete succeeds, before the dialog closes. */
  onDeleted?: () => void | Promise<void>;
}

export function DeleteProjectDialog({
  project,
  onClose,
  onDeleted,
}: DeleteProjectDialogProps) {
  const inputId = useId();
  const [confirmName, setConfirmName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const open = project !== null;

  useEffect(() => {
    setConfirmName("");
    setError(null);
  }, [project?.id]);

  async function handleDelete() {
    if (!project || confirmName !== project.name) return;
    setError(null);
    setBusy(true);
    try {
      await api.delete(`/api/v1/projects/${project.id}`);
      await onDeleted?.();
      onClose();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not delete project");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
    >
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Delete this project?</DialogTitle>
          <DialogDescription>
            All plans, sheets, and related data for{" "}
            <span className="font-medium text-foreground">{project?.name}</span> will be removed
            from the database and file storage.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2">
          <label htmlFor={inputId} className="text-sm font-medium">
            Type the project name to confirm
          </label>
          <Input
            id={inputId}
            value={confirmName}
            onChange={(e) => setConfirmName(e.target.value)}
            placeholder={project?.name}
            autoComplete="off"
            disabled={busy}
            aria-invalid={
              confirmName.length > 0 && project != null && confirmName !== project.name
            }
          />
        </div>
        {error && (
          <p className="text-xs text-destructive" role="alert">
            {error}
          </p>
        )}
        <DialogFooter>
          <Button type="button" variant="ghost" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button
            type="button"
            variant="destructive"
            disabled={busy || !project?.name || confirmName !== project?.name}
            onClick={() => void handleDelete()}
          >
            {busy ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Deleting…
              </>
            ) : (
              "Delete permanently"
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
