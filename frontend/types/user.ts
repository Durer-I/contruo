export interface UserInfo {
  id: string;
  email: string;
  full_name: string;
  org_id: string;
  org_name: string;
  role: "owner" | "admin" | "estimator" | "viewer";
  is_guest: boolean;
  subscription_status?: string | null;
  needs_subscription?: boolean | null;
  /** Subscription ended (cancelled/suspended); open Billing to resubscribe */
  reactivation_required?: boolean;
  billing_banner?: string | null;
  /** Active subscription but billable members exceed purchased seats */
  seat_overage?: boolean;
}

export interface AuthResponse {
  access_token: string;
  refresh_token: string;
  user: UserInfo;
}
