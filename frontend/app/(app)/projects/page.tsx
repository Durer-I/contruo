"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { Loader2, MoreVertical, Plus, Search } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { DeleteProjectDialog } from "@/components/projects/delete-project-dialog";
import { NewProjectDialog } from "@/components/projects/new-project-dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useProjects } from "@/hooks/use-projects";
import { useAuth } from "@/providers/auth-provider";
import { formatRelativeTime } from "@/lib/utils";
import { hasPermission, type Role } from "@/lib/permissions";

export default function ProjectsPage() {
  const { user } = useAuth();
  const { projects, loading, error, refresh } = useProjects();
  const [query, setQuery] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; name: string } | null>(null);

  const role = (user?.role ?? "viewer") as Role;
  const canCreate = hasPermission(role, "create_projects");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return projects;
    return projects.filter((p) => p.name.toLowerCase().includes(q));
  }, [projects, query]);

  return (
    <div className="min-h-0 flex-1 overflow-y-auto p-6">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-xl font-semibold">Projects</h1>
        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search projects..."
              className="w-64 pl-9"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          {canCreate && (
            <NewProjectDialog
              trigger={
                <Button>
                  <Plus className="mr-2 h-4 w-4" />
                  New Project
                </Button>
              }
              onCreated={() => void refresh()}
            />
          )}
        </div>
      </div>

      {loading && projects.length === 0 && (
        <div className="flex items-center justify-center py-24 text-sm text-muted-foreground">
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          Loading projects...
        </div>
      )}

      {error && (
        <div className="rounded-md border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
          {error}
        </div>
      )}

      {!loading && !error && filtered.length === 0 && (
        <EmptyState canCreate={canCreate} hasFilter={query.length > 0} onCreated={refresh} />
      )}

      {filtered.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {filtered.map((project) => (
            <div
              key={project.id}
              className="group relative rounded-md border border-border bg-card transition-colors hover:border-primary/50 hover:bg-surface-overlay"
            >
              <Link
                href={`/project/${project.id}`}
                className="block p-4 pr-11 transition-colors"
              >
                <h3 className="font-medium">{project.name}</h3>
                {project.description && (
                  <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">
                    {project.description}
                  </p>
                )}
                <div className="mt-3 flex flex-col gap-1 text-sm text-muted-foreground">
                  <span>
                    {project.sheet_count} sheet{project.sheet_count === 1 ? "" : "s"}
                  </span>
                  <span>Updated {formatRelativeTime(project.updated_at)}</span>
                  {/* <span>
                    {project.member_count} member{project.member_count === 1 ? "" : "s"}
                  </span> */}
                </div>
              </Link>
              {canCreate && (
                <DropdownMenu>
                  <DropdownMenuTrigger
                    type="button"
                    className="absolute right-1 top-1 z-10 flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground outline-none hover:bg-surface-overlay hover:text-foreground focus-visible:ring-2 focus-visible:ring-primary/40"
                    aria-label="Project actions"
                    onPointerDown={(e) => e.stopPropagation()}
                  >
                    <MoreVertical className="h-4 w-4" aria-hidden />
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="w-48">
                    <DropdownMenuItem
                      variant="destructive"
                      className="cursor-pointer" 
                      onClick={() =>
                        setDeleteTarget({ id: project.id, name: project.name })
                      }
                    >
                      Delete project
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              )}
            </div>
          ))}
        </div>
      )}

      <DeleteProjectDialog
        project={deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onDeleted={refresh}
      />
    </div>
  );
}

function EmptyState({
  canCreate,
  hasFilter,
  onCreated,
}: {
  canCreate: boolean;
  hasFilter: boolean;
  onCreated: () => Promise<void>;
}) {
  if (hasFilter) {
    return (
      <div className="rounded-md border border-border bg-card p-8 text-center text-sm text-muted-foreground">
        No projects match your search.
      </div>
    );
  }
  return (
    <div className="rounded-md border border-dashed border-border bg-card/50 p-10 text-center">
      <h3 className="text-base font-medium">No projects yet</h3>
      <p className="mt-1 text-sm text-muted-foreground">
        Create your first project to start a takeoff.
      </p>
      {canCreate && (
        <div className="mt-4 flex justify-center">
          <NewProjectDialog
            trigger={
              <Button>
                <Plus className="mr-2 h-4 w-4" />
                New Project
              </Button>
            }
            onCreated={() => void onCreated()}
          />
        </div>
      )}
    </div>
  );
}
