import { AuthProvider } from "@/providers/auth-provider";

export const dynamic = "force-dynamic";

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AuthProvider>
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="w-full max-w-md space-y-6 p-8">{children}</div>
      </div>
    </AuthProvider>
  );
}
