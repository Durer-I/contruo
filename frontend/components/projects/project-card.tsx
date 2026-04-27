"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { ImageIcon } from "lucide-react";

import { cn, formatRelativeTime } from "@/lib/utils";
import type { ProjectInfo } from "@/types/project";

interface ProjectCardProps {
  project: ProjectInfo;
  href: string;
  className?: string;
  /** e.g. overflow dropdown; positioned top-right */
  menu?: ReactNode;
}

export function ProjectCard({ project, href, className, menu }: ProjectCardProps) {
  return (
    <div
      className={cn(
        "group relative overflow-hidden rounded-lg border border-border bg-card transition-colors hover:border-primary/50 hover:bg-surface-overlay",
        className
      )}
    >
      {menu}
      <Link href={href} className="block outline-none focus-visible:ring-2 focus-visible:ring-primary/40 focus-visible:ring-offset-2 focus-visible:ring-offset-background">
        <div className="relative aspect-[4/3] w-full bg-muted">
          {project.cover_image_url ? (
            // eslint-disable-next-line @next/next/no-img-element -- signed remote URL
            <img
              key={project.cover_image_url}
              src={project.cover_image_url}
              alt=""
              className="size-full object-cover"
              loading="lazy"
            />
          ) : (
            <div className="flex size-full flex-col items-center justify-center gap-2 text-muted-foreground">
              <ImageIcon className="h-10 w-10 opacity-35" aria-hidden />
              <span className="text-[10px] font-medium uppercase tracking-wide opacity-70">
                No cover
              </span>
            </div>
          )}
        </div>
        <div className="space-y-2 p-4 pt-3">
          <h3 className="line-clamp-2 font-semibold leading-snug">{project.name}</h3>
          {project.description ? (
            <p className="line-clamp-2 text-xs text-muted-foreground">{project.description}</p>
          ) : null}
          <div className="flex flex-col gap-1 border-t border-border/60 pt-2 text-xs text-muted-foreground">
            <span>
              {project.sheet_count} sheet{project.sheet_count === 1 ? "" : "s"}
            </span>
            <span>Updated {formatRelativeTime(project.updated_at)}</span>
          </div>
        </div>
      </Link>
    </div>
  );
}
