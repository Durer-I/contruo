import { SettingsSubnav } from "@/components/layout/settings-subnav";

export default function SettingsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <SettingsSubnav />
      <div className="min-h-0 flex-1 overflow-auto">{children}</div>
    </div>
  );
}
