import { AuthProvider } from "@/providers/auth-provider";
import { AppShell } from "@/components/layout/app-shell";

export const dynamic = "force-dynamic";

export default function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AuthProvider>
      <AppShell>{children}</AppShell>
    </AuthProvider>
  );
}
