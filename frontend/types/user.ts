export interface UserInfo {
  id: string;
  email: string;
  full_name: string;
  org_id: string;
  org_name: string;
  role: "owner" | "admin" | "estimator" | "viewer";
  is_guest: boolean;
}

export interface AuthResponse {
  access_token: string;
  refresh_token: string;
  user: UserInfo;
}
