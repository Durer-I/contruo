"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";
import type { PlanInfo, ProjectInfo } from "@/types/project";

import { PlanUploadZone } from "./plan-upload-zone";
import { ProjectCoverField } from "./project-cover-field";

interface NewProjectDialogProps {
  /** Single-element trigger; use `Button` so Base UI dialog trigger keeps native button semantics. */
  trigger: React.ReactElement;
  onCreated?: (project: ProjectInfo) => void;
}

export function NewProjectDialog({ trigger, onCreated }: NewProjectDialogProps) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [coverImage, setCoverImage] = useState<File | null>(null);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  function reset() {
    setName("");
    setDescription("");
    setCoverImage(null);
    setPendingFile(null);
    setSubmitting(false);
    setError(null);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) {
      setError("Project name is required");
      return;
    }
    if (!coverImage) {
      setError("Add a project cover image (JPEG, PNG, or WebP).");
      return;
    }
    setSubmitting(true);
    setError(null);

    try {
      const project = await api.post<ProjectInfo>("/api/v1/projects", {
        name: name.trim(),
        description: description.trim() || null,
      });

      try {
        await api.uploadFile<ProjectInfo>(`/api/v1/projects/${project.id}/cover`, coverImage);
      } catch (uploadErr) {
        try {
          await api.delete(`/api/v1/projects/${project.id}`);
        } catch {
          // best-effort rollback
        }
        setError(
          uploadErr instanceof ApiError
            ? uploadErr.message
            : "Could not upload the cover image. Try a smaller file or different format."
        );
        setSubmitting(false);
        return;
      }

      // If a plan was staged, upload it now before navigating so the workspace
      // sees a "processing" plan immediately.
      let planId: string | null = null;
      if (pendingFile) {
        const plan = await api.uploadFile<PlanInfo>(
          `/api/v1/projects/${project.id}/plans`,
          pendingFile
        );
        planId = plan.id;
      }

      const href = planId
        ? `/project/${project.id}?plan=${encodeURIComponent(planId)}`
        : `/project/${project.id}`;
      // Navigate before list refresh so the client route always wins over parent re-renders.
      router.replace(href);
      setOpen(false);
      reset();
      queueMicrotask(() => {
        onCreated?.(project);
      });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to create project");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        setOpen(v);
        if (!v) reset();
      }}
    >
      <DialogTrigger render={trigger} />
      <DialogContent className="sm:max-w-lg">
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <DialogHeader>
            <DialogTitle>New Project</DialogTitle>
            <DialogDescription>
              Start a new takeoff with a cover image. You can change it later from the project
              menu. Plans are optional now or after creation.
            </DialogDescription>
          </DialogHeader>

          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-muted-foreground">
              Project cover <span className="text-destructive">*</span>
            </label>
            <ProjectCoverField file={coverImage} onFile={setCoverImage} disabled={submitting} />
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="project-name" className="text-xs font-medium text-muted-foreground">
              Project Name <span className="text-destructive">*</span>
            </label>
            <Input
              id="project-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., Downtown Office Complex"
              autoFocus
              required
              maxLength={255}
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label
              htmlFor="project-description"
              className="text-xs font-medium text-muted-foreground"
            >
              Description (optional)
            </label>
            <Input
              id="project-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Short description or project address"
              maxLength={500}
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-muted-foreground">
              Upload Plans (optional)
            </label>
            <PlanUploadZone file={pendingFile} onFile={setPendingFile} />
          </div>

          {error && (
            <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {error}
            </div>
          )}

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setOpen(false);
                reset();
              }}
              disabled={submitting}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={submitting || !name.trim() || !coverImage}>
              {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Create Project
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
