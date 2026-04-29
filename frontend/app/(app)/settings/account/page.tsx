"use client";

import { useState, useEffect } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PasswordInput } from "@/components/ui/password-input";
import { useAuth } from "@/providers/auth-provider";
import { api } from "@/lib/api";
import { Loader2 } from "lucide-react";

export default function AccountPage() {
  const { user, refreshMe } = useAuth();
  const [fullName, setFullName] = useState(user?.full_name ?? "");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (user?.full_name !== undefined) {
      setFullName(user.full_name);
    }
  }, [user?.full_name]);

  async function handleSaveProfile() {
    setSaving(true);
    try {
      await api.patch("/api/v1/auth/me", { full_name: fullName });
      await refreshMe();
      toast.success("Profile updated");
    } catch {
      toast.error("Failed to update profile");
    } finally {
      setSaving(false);
    }
  }

  async function handleChangePassword() {
    if (newPassword.length < 8) {
      toast.error("Password must be at least 8 characters");
      return;
    }
    if (newPassword !== confirmPassword) {
      toast.error("Passwords do not match");
      return;
    }
    setSaving(true);
    try {
      const { createClient } = await import("@/lib/supabase");
      const supabase = createClient();
      const { error } = await supabase.auth.updateUser({
        password: newPassword,
      });
      if (error) throw error;
      setNewPassword("");
      setConfirmPassword("");
      toast.success("Password changed");
    } catch {
      toast.error("Failed to change password");
    } finally {
      setSaving(false);
    }
  }

  if (!user) {
    return (
      <div className="flex min-h-0 flex-1 items-center justify-center p-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="min-h-0 flex-1 overflow-y-auto p-6">
      <div className="mx-auto max-w-2xl">
      <h1 className="mb-6 text-xl font-semibold">Account</h1>

      <div className="space-y-8">
        {/* Profile */}
        <section className="space-y-4">
          <h2 className="text-sm font-medium text-muted-foreground">Profile</h2>
          <div className="space-y-2">
            <Label htmlFor="full-name">Full Name</Label>
            <Input
              id="full-name"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input id="email" value={user.email} disabled className="opacity-60" />
            <p className="text-xs text-muted-foreground">
              Email cannot be changed at this time.
            </p>
          </div>
          <Button onClick={handleSaveProfile} disabled={saving}>
            {saving ? "Saving..." : "Save Profile"}
          </Button>
        </section>

        <hr className="border-border" />

        {/* Password */}
        <section className="space-y-4">
          <h2 className="text-sm font-medium text-muted-foreground">
            Change Password
          </h2>
          <div className="space-y-2">
            <Label htmlFor="new-pass">New Password</Label>
            <PasswordInput
              id="new-pass"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder="At least 8 characters"
              autoComplete="new-password"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="confirm-pass">Confirm Password</Label>
            <PasswordInput
              id="confirm-pass"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              autoComplete="new-password"
            />
          </div>
          <Button
            onClick={handleChangePassword}
            disabled={saving || !newPassword}
            variant="outline"
          >
            Change Password
          </Button>
        </section>
      </div>
      </div>
    </div>
  );
}
