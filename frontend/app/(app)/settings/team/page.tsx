"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { api, ApiError } from "@/lib/api";
import { canManageBilling, type Role } from "@/lib/permissions";
import { useAuth } from "@/providers/auth-provider";
import type { MemberInfo, InvitationInfo, MemberListApiResponse } from "@/types/org";
import {
  UserPlus,
  Loader2,
  X,
  MailPlus,
  RotateCcw,
  Ban,
  Shield,
  Eye,
  Pencil,
  Crown,
} from "lucide-react";
import { cn } from "@/lib/utils";

const ROLE_BADGES: Record<string, { label: string; className: string; icon: React.ElementType }> = {
  owner: { label: "Owner", className: "bg-yellow-500/15 text-yellow-400 border-yellow-500/30", icon: Crown },
  admin: { label: "Admin", className: "bg-blue-500/15 text-blue-400 border-blue-500/30", icon: Shield },
  estimator: { label: "Estimator", className: "bg-green-500/15 text-green-400 border-green-500/30", icon: Pencil },
  viewer: { label: "Viewer", className: "bg-gray-500/15 text-gray-400 border-gray-500/30", icon: Eye },
};

function RoleBadge({ role }: { role: string }) {
  const badge = ROLE_BADGES[role] || ROLE_BADGES.viewer;
  const Icon = badge.icon;
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-medium", badge.className)}>
      <Icon className="h-3 w-3" />
      {badge.label}
    </span>
  );
}

export default function TeamPage() {
  const { user } = useAuth();
  const [members, setMembers] = useState<MemberInfo[]>([]);
  const [invitations, setInvitations] = useState<InvitationInfo[]>([]);
  const [loading, setLoading] = useState(true);

  const [showInvite, setShowInvite] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("estimator");
  const [inviting, setInviting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingDeactivation, setPendingDeactivation] = useState<MemberInfo | null>(null);
  const [seatMeta, setSeatMeta] = useState<{
    billable_seats_used: number;
    purchased_seats: number | null;
    can_invite_billable_member: boolean;
    scheduled_billed_seats: number | null;
    scheduled_seat_change_effective_at: string | null;
  } | null>(null);

  const canManageTeam = user?.role === "owner" || user?.role === "admin";
  const canOpenBilling = user?.role ? canManageBilling(user.role as Role) : false;
  const canInviteMember = seatMeta?.can_invite_billable_member !== false;

  const fetchData = useCallback(async () => {
    try {
      const [memberRes, invRes] = await Promise.all([
        api.get<MemberListApiResponse>("/api/v1/org/members"),
        canManageTeam
          ? api.get<{ invitations: InvitationInfo[] }>("/api/v1/org/invitations")
          : Promise.resolve({ invitations: [] }),
      ]);
      setMembers(memberRes.members);
      setInvitations(invRes.invitations);
      setSeatMeta({
        billable_seats_used: memberRes.billable_seats_used ?? 0,
        purchased_seats:
          memberRes.purchased_seats === undefined ? null : memberRes.purchased_seats,
        can_invite_billable_member: memberRes.can_invite_billable_member !== false,
        scheduled_billed_seats: memberRes.scheduled_billed_seats ?? null,
        scheduled_seat_change_effective_at:
          memberRes.scheduled_seat_change_effective_at ?? null,
      });
    } catch {
      setError("Failed to load team data");
    } finally {
      setLoading(false);
    }
  }, [canManageTeam]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  useEffect(() => {
    if (!canInviteMember) setShowInvite(false);
  }, [canInviteMember]);

  async function handleInvite() {
    if (!inviteEmail) return;
    setInviting(true);
    setError(null);
    try {
      await api.post("/api/v1/org/members/invite", {
        email: inviteEmail,
        role: inviteRole,
      });
      setInviteEmail("");
      setShowInvite(false);
      await fetchData();
    } catch (e: unknown) {
      if (e instanceof ApiError && e.code === "NO_SEATS_AVAILABLE") {
        setError(e.message);
      } else {
        setError(e instanceof Error ? e.message : "Failed to send invitation");
      }
    } finally {
      setInviting(false);
    }
  }

  async function handleRoleChange(memberId: string, newRole: string) {
    try {
      await api.patch(`/api/v1/org/members/${memberId}`, { role: newRole });
      await fetchData();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to change role");
    }
  }

  async function handleDeactivate(memberId: string) {
    try {
      await api.delete(`/api/v1/org/members/${memberId}`);
      await fetchData();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to deactivate member");
    }
  }

  async function handleCancelInvitation(invitationId: string) {
    try {
      await api.post(`/api/v1/org/invitations/${invitationId}/cancel`, {});
      await fetchData();
    } catch {
      setError("Failed to cancel invitation");
    }
  }

  async function handleResendInvitation(invitationId: string) {
    try {
      await api.post(`/api/v1/org/invitations/${invitationId}/resend`, {});
      await fetchData();
    } catch {
      setError("Failed to resend invitation");
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-0 flex-1 items-center justify-center p-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const activeMembers = members.filter((m) => !m.deactivated_at && !m.is_guest);
  const guests = members.filter((m) => m.is_guest);
  const deactivated = members.filter((m) => m.deactivated_at && !m.is_guest);
  const pendingInvitations = invitations.filter((i) => i.status === "pending");

  const scheduledSeatWarning =
    seatMeta?.scheduled_billed_seats != null &&
    seatMeta.scheduled_seat_change_effective_at != null
      ? (() => {
          const when = new Date(seatMeta.scheduled_seat_change_effective_at).toLocaleString(
            undefined,
            { dateStyle: "medium", timeStyle: "short" }
          );
          const next = seatMeta.scheduled_billed_seats;
          const used = seatMeta.billable_seats_used;
          const tight = used > next;
          return {
            when,
            next,
            tight,
            used,
          };
        })()
      : null;

  return (
    <div className="min-h-0 flex-1 overflow-y-auto p-6">
      <div className="mx-auto max-w-4xl">
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <h1 className="text-xl font-semibold">Team Members</h1>
        {canManageTeam && (
          <div className="flex flex-col items-stretch gap-2 sm:items-end">
            <Button
              size="sm"
              disabled={!canInviteMember}
              onClick={() => setShowInvite(!showInvite)}
            >
              <UserPlus className="mr-2 h-4 w-4" />
              Invite member
            </Button>
            {!canInviteMember && seatMeta?.purchased_seats != null ? (
              <p className="max-w-sm text-right text-xs text-muted-foreground sm:text-right">
                Every purchased seat has an active member.{" "}
                {canOpenBilling ? (
                  <>
                    <Link href="/settings/billing" className="text-primary underline-offset-4 hover:underline">
                      Add seats in Billing
                    </Link>{" "}
                    to invite more people.
                  </>
                ) : (
                  "Ask an organization owner to add seats in Billing to invite more people."
                )}
              </p>
            ) : null}
            {!canInviteMember && seatMeta?.purchased_seats == null ? (
              <p className="max-w-sm text-right text-xs text-muted-foreground sm:text-right">
                Invites need an active subscription.{" "}
                {canOpenBilling ? (
                  <Link href="/settings/billing" className="text-primary underline-offset-4 hover:underline">
                    Open Billing
                  </Link>
                ) : (
                  "Ask an owner to check Billing."
                )}
              </p>
            ) : null}
          </div>
        )}
      </div>

      {scheduledSeatWarning && (
        <div
          className={cn(
            "mb-4 rounded-md border px-3 py-2 text-sm",
            scheduledSeatWarning.tight
              ? "border-amber-500/50 bg-amber-500/15 text-amber-950 dark:text-amber-50"
              : "border-border bg-muted/40 text-muted-foreground"
          )}
          role="status"
        >
          {scheduledSeatWarning.tight ? (
            <>
              After <span className="font-medium">{scheduledSeatWarning.when}</span> your
              plan drops to <span className="font-medium">{scheduledSeatWarning.next}</span>{" "}
              purchased seats, but you have{" "}
              <span className="font-medium">{scheduledSeatWarning.used}</span> active
              members. Deactivate members in Team or{" "}
              {canOpenBilling ? (
                <Link href="/settings/billing" className="text-primary underline-offset-4 hover:underline">
                  add seats in Billing
                </Link>
              ) : (
                "ask an owner to add seats in Billing"
              )}{" "}
              before renewal.
            </>
          ) : (
            <>
              A seat change is scheduled for{" "}
              <span className="font-medium">{scheduledSeatWarning.when}</span>: purchased seats
              will be <span className="font-medium">{scheduledSeatWarning.next}</span> after
              renewal. Ensure headcount fits, or{" "}
              {canOpenBilling ? (
                <Link href="/settings/billing" className="text-primary underline-offset-4 hover:underline">
                  adjust seats in Billing
                </Link>
              ) : (
                "ask an owner to adjust seats in Billing"
              )}
              .
            </>
          )}
        </div>
      )}

      {error && (
        <div className="mb-4 rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Invite Dialog */}
      {showInvite && (
        <div className="mb-6 rounded-lg border border-border bg-surface-overlay p-4">
          <h3 className="mb-3 text-sm font-medium">Invite a team member</h3>
          <div className="flex gap-3">
            <Input
              placeholder="Email address"
              type="email"
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
              className="flex-1"
            />
            <NativeSelect
              value={inviteRole}
              onChange={(e) => setInviteRole(e.target.value)}
              className="w-32"
              aria-label="Invitation role"
            >
              <option value="admin">Admin</option>
              <option value="estimator">Estimator</option>
              <option value="viewer">Viewer</option>
            </NativeSelect>
            <Button onClick={handleInvite} disabled={inviting || !inviteEmail}>
              {inviting ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <>
                  <MailPlus className="mr-1 h-4 w-4" />
                  Send
                </>
              )}
            </Button>
            <Button variant="ghost" size="icon" onClick={() => setShowInvite(false)}>
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}

      {/* Active Members Table */}
      <div className="rounded-lg border border-border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs text-muted-foreground">
              <th className="px-4 py-3 font-medium">Name</th>
              <th className="px-4 py-3 font-medium">Email</th>
              <th className="px-4 py-3 font-medium">Role</th>
              {canManageTeam && (
                <th className="px-4 py-3 text-right font-medium">Actions</th>
              )}
            </tr>
          </thead>
          <tbody>
            {activeMembers.map((member) => (
              <tr key={member.id} className="border-b border-border last:border-0">
                <td className="px-4 py-3 font-medium">{member.full_name}</td>
                <td className="px-4 py-3 text-muted-foreground">{member.email}</td>
                <td className="px-4 py-3">
                  <RoleBadge role={member.role} />
                </td>
                {canManageTeam && (
                  <td className="px-4 py-3 text-right">
                    {member.role !== "owner" && member.id !== user?.id && (
                      <div className="flex items-center justify-end gap-2">
                        <NativeSelect
                          value={member.role}
                          onChange={(e) => handleRoleChange(member.id, e.target.value)}
                          size="sm"
                          className="w-28"
                          aria-label={`Change role for ${member.full_name}`}
                        >
                          <option value="admin">Admin</option>
                          <option value="estimator">Estimator</option>
                          <option value="viewer">Viewer</option>
                        </NativeSelect>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7 text-red-400 hover:text-red-300"
                          onClick={() => setPendingDeactivation(member)}
                          aria-label={`Deactivate ${member.full_name}`}
                        >
                          <Ban className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    )}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pending Invitations */}
      {canManageTeam && pendingInvitations.length > 0 && (
        <div className="mt-8">
          <h2 className="mb-3 text-sm font-semibold text-muted-foreground">
            Pending Invitations ({pendingInvitations.length})
          </h2>
          <div className="rounded-lg border border-border">
            <table className="w-full text-sm">
              <tbody>
                {pendingInvitations.map((inv) => (
                  <tr key={inv.id} className="border-b border-border last:border-0">
                    <td className="px-4 py-3 text-muted-foreground">{inv.email}</td>
                    <td className="px-4 py-3">
                      <RoleBadge role={inv.role} />
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-7 text-xs"
                          onClick={() => handleResendInvitation(inv.id)}
                        >
                          <RotateCcw className="mr-1 h-3 w-3" />
                          Resend
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-7 text-xs text-red-400"
                          onClick={() => handleCancelInvitation(inv.id)}
                        >
                          <X className="mr-1 h-3 w-3" />
                          Cancel
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Guests */}
      {guests.length > 0 && (
        <div className="mt-8">
          <h2 className="mb-3 text-sm font-semibold text-muted-foreground">
            Guests ({guests.length})
          </h2>
          <div className="rounded-lg border border-border">
            <table className="w-full text-sm">
              <tbody>
                {guests.map((g) => (
                  <tr key={g.id} className="border-b border-border last:border-0">
                    <td className="px-4 py-3 font-medium">{g.full_name}</td>
                    <td className="px-4 py-3 text-muted-foreground">{g.email}</td>
                    <td className="px-4 py-3">
                      <span className="text-xs text-muted-foreground">Guest</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Deactivated */}
      {deactivated.length > 0 && (
        <div className="mt-8">
          <h2 className="mb-3 text-sm font-semibold text-muted-foreground">
            Deactivated ({deactivated.length})
          </h2>
          <div className="rounded-lg border border-border opacity-60">
            <table className="w-full text-sm">
              <tbody>
                {deactivated.map((m) => (
                  <tr key={m.id} className="border-b border-border last:border-0">
                    <td className="px-4 py-3 font-medium">{m.full_name}</td>
                    <td className="px-4 py-3 text-muted-foreground">{m.email}</td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">Deactivated</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      </div>

      <AlertDialog
        open={pendingDeactivation !== null}
        onOpenChange={(open) => {
          if (!open) setPendingDeactivation(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Deactivate member?</AlertDialogTitle>
            <AlertDialogDescription>
              {pendingDeactivation
                ? `${pendingDeactivation.full_name} will lose access to the workspace. Their work will be preserved and they can be reinstated later.`
                : ""}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={() => {
                const target = pendingDeactivation;
                setPendingDeactivation(null);
                if (target) void handleDeactivate(target.id);
              }}
            >
              Deactivate
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
