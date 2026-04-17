"use client";

import Link from "next/link";
import { Settings, LogOut } from "lucide-react";
import { useAuth } from "@/providers/auth-provider";
import { useTopBarCenter } from "@/providers/top-bar-center-provider";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";

function getInitials(name: string): string {
  return name
    .split(" ")
    .map((part) => part[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);
}

export function TopBar() {
  const { user, signOut } = useAuth();
  const { center } = useTopBarCenter();

  return (
    <header className="flex h-12 shrink-0 items-center border-b border-border bg-surface px-4">
      {/* Left: Logo */}
      <div className="flex items-center gap-3">
        <Link href="/dashboard" className="flex items-center gap-2">
          <svg
            viewBox="0 0 24 24"
            fill="none"
            className="h-6 w-6 text-primary"
            aria-hidden="true"
          >
            <path
              d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          <span className="text-base font-semibold tracking-tight">
            Contruo
          </span>
        </Link>
      </div>

      {/* Center: Contextual toolbar (populated by plan viewer routes) */}
      <div className="flex min-w-0 flex-1 justify-center px-2">{center}</div>

      {/* Right: Org name + User menu */}
      <div className="flex items-center gap-3">
        {user && (
          <span className="text-xs text-muted-foreground">
            {user.org_name}
          </span>
        )}
        <DropdownMenu>
          <DropdownMenuTrigger className="relative flex h-8 w-8 items-center justify-center rounded-full outline-none hover:bg-surface-overlay">
            <Avatar className="h-8 w-8">
              <AvatarFallback className="bg-primary/20 text-sm text-primary">
                {user ? getInitials(user.full_name) : "?"}
              </AvatarFallback>
            </Avatar>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-52">
            {user && (
              <>
                <div className="px-2 py-1.5">
                  <p className="text-sm font-medium">{user.full_name}</p>
                  <p className="text-xs text-muted-foreground">{user.email}</p>
                </div>
                <DropdownMenuSeparator />
              </>
            )}
            <DropdownMenuItem
              render={<Link href="/settings/account" className="cursor-pointer" />}
            >
              <Settings className="mr-2 h-4 w-4" />
              Profile
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem className="cursor-pointer" onClick={() => signOut()}>
              <LogOut className="mr-2 h-4 w-4" />
              Log out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
