"use client";

import { Loader2, Plus } from "lucide-react";

import { ProjectCard } from "@/components/projects/project-card";

import { useAuth } from "@/providers/auth-provider";
import { WelcomeModal } from "@/components/auth/welcome-modal";
import { NewProjectDialog } from "@/components/projects/new-project-dialog";
import { Button } from "@/components/ui/button";
import { useProjects } from "@/hooks/use-projects";
import Link from "next/link";
import { hasPermission, type Role } from "@/lib/permissions";

export default function DashboardPage() {
  const { user } = useAuth();
  const { projects, loading, error, refresh } = useProjects();

  const role = (user?.role ?? "viewer") as Role;
  const canCreate = hasPermission(role, "create_projects");

  const recent = projects.slice(0, 6);

  return (
    <div className="min-h-0 flex-1 overflow-y-auto p-6">
      <WelcomeModal />

      <div className="mb-6 flex items-end justify-between">
        <div>
          <h1 className="text-xl font-semibold">Dashboard</h1>
          {user && (
            <p className="mt-1 text-sm text-muted-foreground">
              Welcome back, {user.full_name}. You&apos;re signed in to{" "}
              <span className="text-foreground">{user.org_name}</span>.
            </p>
          )}
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

      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-medium text-muted-foreground">Recent projects</h2>
        {projects.length > recent.length && (
          <Link href="/projects" className="text-xs text-primary hover:underline">
            View all
          </Link>
        )}
      </div>

      {loading && projects.length === 0 && (
        <div className="flex items-center justify-center rounded-md border border-border bg-card py-16 text-sm text-muted-foreground">
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          Loading projects...
        </div>
      )}

      {error && (
        <div className="rounded-md border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
          {error}
        </div>
      )}

      {!loading && !error && recent.length === 0 && (
        <div className="rounded-md border border-dashed border-border bg-card/50 p-10 text-center">
          <h3 className="text-base font-medium">No projects yet</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            {canCreate
              ? "Create your first project to start a takeoff."
              : "Ask an admin to create a project to get started."}
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
                onCreated={() => void refresh()}
              />
            </div>
          )}
        </div>
      )}

      {recent.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {recent.map((project) => (
            <ProjectCard
              key={project.id}
              project={project}
              href={`/project/${project.id}`}
            />
          ))}
        </div>
      )}
    </div>
  );
}
