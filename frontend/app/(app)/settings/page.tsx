"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { api } from "@/lib/api";
import type { OrgInfo } from "@/types/org";
import { Upload, Loader2 } from "lucide-react";

export default function SettingsPage() {
  const [org, setOrg] = useState<OrgInfo | null>(null);
  const [name, setName] = useState("");
  const [units, setUnits] = useState<"imperial" | "metric">("imperial");
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    api.get<OrgInfo>("/api/v1/org").then((data) => {
      setOrg(data);
      setName(data.name);
      setUnits(data.default_units);
    });
  }, []);

  async function handleSave() {
    setSaving(true);
    try {
      const updated = await api.patch<OrgInfo>("/api/v1/org", {
        name,
        default_units: units,
      });
      setOrg(updated);
      toast.success("Settings saved");
    } catch {
      toast.error("Failed to save settings");
    } finally {
      setSaving(false);
    }
  }

  async function handleLogoUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1/org/logo`,
        {
          method: "POST",
          body: formData,
          headers: {
            Authorization: `Bearer ${(await import("@/lib/supabase").then((m) => m.createClient())).auth.getSession().then((s) => s.data.session?.access_token) ?? ""}`,
          },
        }
      );
      if (res.ok) {
        const updated: OrgInfo = await res.json();
        setOrg(updated);
        toast.success("Logo uploaded");
      } else {
        toast.error("Failed to upload logo");
      }
    } catch {
      toast.error("Failed to upload logo");
    } finally {
      setUploading(false);
    }
  }

  if (!org) {
    return (
      <div className="flex min-h-0 flex-1 items-center justify-center p-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="min-h-0 flex-1 overflow-y-auto p-6">
      <div className="mx-auto max-w-2xl">
      <h1 className="mb-6 text-xl font-semibold">Organization Settings</h1>
      <div className="space-y-6">
        {/* Logo */}
        <div className="space-y-2">
          <span className="block text-sm font-medium">Logo</span>
          <div className="flex items-center gap-4">
            {org.logo_url ? (
              <Image
                src={org.logo_url}
                alt="Org logo"
                width={64}
                height={64}
                className="h-16 w-16 rounded-lg border border-border object-cover"
              />
            ) : (
              <div className="flex h-16 w-16 items-center justify-center rounded-lg border border-dashed border-border text-muted-foreground">
                <Upload className="h-5 w-5" />
              </div>
            )}
            <Button
              variant="outline"
              disabled={uploading}
              nativeButton={false}
              render={<label className="cursor-pointer" />}
            >
              {uploading ? "Uploading..." : "Upload Logo"}
              <input
                type="file"
                accept=".png,.jpg,.jpeg,.svg,.webp"
                className="hidden"
                onChange={handleLogoUpload}
                disabled={uploading}
              />
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            PNG, JPG, SVG, or WebP. Max 2MB.
          </p>
        </div>

        {/* Name */}
        <div className="space-y-2">
          <Label htmlFor="org-name">Organization Name</Label>
          <Input
            id="org-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>

        {/* Unit System */}
        <div className="space-y-2">
          <span className="block text-sm font-medium">Default Unit System</span>
          <RadioGroup
            value={units}
            onValueChange={(v) => setUnits(v as "imperial" | "metric")}
            className="flex flex-row gap-4 text-sm"
          >
            <Label htmlFor="units-imperial" className="cursor-pointer">
              <RadioGroupItem id="units-imperial" value="imperial" />
              Imperial (ft, in, SF, LF)
            </Label>
            <Label htmlFor="units-metric" className="cursor-pointer">
              <RadioGroupItem id="units-metric" value="metric" />
              Metric (m, cm, m², m)
            </Label>
          </RadioGroup>
        </div>

        <Button onClick={handleSave} disabled={saving}>
          {saving ? "Saving..." : "Save Changes"}
        </Button>
      </div>
      </div>
    </div>
  );
}
