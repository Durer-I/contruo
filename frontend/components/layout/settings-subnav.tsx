"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useAuth } from "@/providers/auth-provider";
import {
  canManageBilling,
  canManageTeam,
  type Role,
} from "@/lib/permissions";

const tabs: { href: string; label: string; perm?: "team" | "billing" }[] = [
  // { href: "/settings", label: "General" },
  { href: "/settings/team", label: "Team", perm: "team" },
  { href: "/settings/account", label: "Account" },
  { href: "/settings/billing", label: "Billing", perm: "billing" },
];

export function SettingsSubnav() {
  const pathname = usePathname();
  const { user } = useAuth();
  const role = (user?.role ?? "viewer") as Role;

  const visible = tabs.filter((t) => {
    if (t.perm === "team") return canManageTeam(role);
    if (t.perm === "billing") return canManageBilling(role);
    return true;
  });

  return (
    <div className="border-b border-border bg-surface px-6 pt-4">
      <nav className="flex gap-1" aria-label="Settings sections">
        {visible.map((t) => {
          const active =
            t.href === "/settings"
              ? pathname === "/settings"
              : pathname === t.href || pathname.startsWith(t.href + "/");
          return (
            <Link
              key={t.href}
              href={t.href}
              className={cn(
                "rounded-t-md px-3 py-2 text-sm font-medium transition-colors",
                active
                  ? "bg-surface-overlay text-foreground border border-b-0 border-border"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {t.label}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
