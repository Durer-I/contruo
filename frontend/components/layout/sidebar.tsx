"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  FolderOpen,
  Library,
  Settings,
  CreditCard,
  PanelLeftClose,
  PanelLeft,
} from "lucide-react";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { SIDEBAR_WIDTH, SIDEBAR_COLLAPSED_WIDTH } from "@/lib/constants";
import { useAuth } from "@/providers/auth-provider";
import { canManageOrgSettings, canManageBilling, type Role } from "@/lib/permissions";

const NAV_ITEMS = [
  { id: "dashboard", label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { id: "projects", label: "Projects", href: "/projects", icon: FolderOpen },
  { id: "templates", label: "Templates", href: "/templates", icon: Library },
  { id: "settings", label: "Settings", href: "/settings", icon: Settings, requirePerm: "manage_org_settings" as const },
  { id: "billing", label: "Billing", href: "/settings/billing", icon: CreditCard, requirePerm: "manage_billing" as const },
];

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const pathname = usePathname();
  const { user } = useAuth();
  const role = (user?.role ?? "viewer") as Role;

  const visibleItems = NAV_ITEMS.filter((item) => {
    if (item.requirePerm === "manage_org_settings") return canManageOrgSettings(role);
    if (item.requirePerm === "manage_billing") return canManageBilling(role);
    return true;
  });

  const width = collapsed ? SIDEBAR_COLLAPSED_WIDTH : SIDEBAR_WIDTH;

  return (
    <aside
      className="flex h-full flex-col border-r border-border bg-surface transition-[width] duration-200"
      style={{ width }}
    >
      <nav className="flex flex-1 flex-col gap-1 p-2">
        {visibleItems.map((item) => {
          const isActive =
            pathname === item.href ||
            (item.href !== "/dashboard" && pathname.startsWith(item.href + "/"));
          const Icon = item.icon;

          const link = (
            <Link
              key={item.id}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-surface-overlay text-foreground border-l-2 border-primary"
                  : "text-muted-foreground hover:bg-surface-overlay hover:text-foreground"
              )}
            >
              <Icon className="h-5 w-5 shrink-0" />
              {!collapsed && <span>{item.label}</span>}
            </Link>
          );

          if (collapsed) {
            return (
              <Tooltip key={item.id}>
                <TooltipTrigger
                  render={
                    <Link
                      href={item.href}
                      className={cn(
                        "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                        isActive
                          ? "bg-surface-overlay text-foreground border-l-2 border-primary"
                          : "text-muted-foreground hover:bg-surface-overlay hover:text-foreground"
                      )}
                    />
                  }
                >
                  <Icon className="h-5 w-5 shrink-0" />
                </TooltipTrigger>
                <TooltipContent side="right">{item.label}</TooltipContent>
              </Tooltip>
            );
          }

          return link;
        })}
      </nav>

      {/* Theme + collapse */}
      <div className="space-y-1 border-t border-border p-2">
        <ThemeToggle collapsed={collapsed} />
        <Button
          variant="ghost"
          size="sm"
          className="w-full justify-center"
          onClick={() => setCollapsed(!collapsed)}
        >
          {collapsed ? (
            <PanelLeft className="h-4 w-4" />
          ) : (
            <>
              <PanelLeftClose className="mr-2 h-4 w-4" />
              <span className="text-xs text-muted-foreground">Collapse</span>
            </>
          )}
        </Button>
      </div>
    </aside>
  );
}
