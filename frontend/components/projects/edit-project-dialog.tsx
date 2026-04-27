"use client";

import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";
import type { ProjectInfo } from "@/types/project";

import { ProjectCoverField } from "./project-cover-field";

interface EditProjectDialogProps {
  project: ProjectInfo | null;
  onClose: () => void;
  onSaved?: (project: ProjectInfo) => void;
}

export function EditProjectDialog({ project, onClose, onSaved }: EditProjectDialogProps) {
  const open = project !== null;
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [coverImage, setCoverImage] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!project) return;
    setName(project.name);
    setDescription(project.description ?? "");
    setCoverImage(null);
    setError(null);
    setSubmitting(false);
  }, [project]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!project) return;
    if (!name.trim()) {
      setError("Project name is required");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      let updated = await api.patch<ProjectInfo>(`/api/v1/projects/${project.id}`, {
        name: name.trim(),
        description: description.trim() || null,
      });
      if (coverImage) {
        updated = await api.uploadFile<ProjectInfo>(
          `/api/v1/projects/${project.id}/cover`,
          coverImage
        );
      }
      onSaved?.(updated);
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to update project");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        if (!v) onClose();
      }}
    >
      <DialogContent className="sm:max-w-lg">
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <DialogHeader>
            <DialogTitle>Edit project</DialogTitle>
            <DialogDescription>
              Update the cover image, title, and description. Plans are managed from the project
              workspace.
            </DialogDescription>
          </DialogHeader>

          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-muted-foreground">Project cover</label>
            <ProjectCoverField
              file={coverImage}
              onFile={setCoverImage}
              existingCoverUrl={project?.cover_image_url ?? null}
              disabled={submitting}
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="edit-project-name" className="text-xs font-medium text-muted-foreground">
              Project name <span className="text-destructive">*</span>
            </label>
            <Input
              id="edit-project-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., Downtown Office Complex"
              required
              maxLength={255}
              disabled={submitting}
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label
              htmlFor="edit-project-description"
              className="text-xs font-medium text-muted-foreground"
            >
              Description (optional)
            </label>
            <Input
              id="edit-project-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Short description or project address"
              maxLength={500}
              disabled={submitting}
            />
          </div>

          {error && (
            <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {error}
            </div>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose} disabled={submitting}>
              Cancel
            </Button>
            <Button type="submit" disabled={submitting || !name.trim()}>
              {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />}
              Save
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
