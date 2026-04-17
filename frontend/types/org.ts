export interface OrgInfo {
  id: string;
  name: string;
  logo_url: string | null;
  default_units: "imperial" | "metric";
  created_at: string;
}

export interface MemberInfo {
  id: string;
  email: string;
  full_name: string;
  role: "owner" | "admin" | "estimator" | "viewer";
  is_guest: boolean;
  deactivated_at: string | null;
  created_at: string;
}

export interface InvitationInfo {
  id: string;
  email: string;
  role: string;
  status: "pending" | "accepted" | "cancelled" | "expired";
  expires_at: string;
  created_at: string;
}
