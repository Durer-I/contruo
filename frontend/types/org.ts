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

/** GET /api/v1/org/members */
export interface MemberListApiResponse {
  members: MemberInfo[];
  billable_seats_used?: number;
  purchased_seats?: number | null;
  can_invite_billable_member?: boolean;
  scheduled_billed_seats?: number | null;
  scheduled_seat_change_effective_at?: string | null;
}
