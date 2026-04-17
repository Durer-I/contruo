export type ProjectStatus = "active" | "archived";

export interface ProjectInfo {
  id: string;
  org_id: string;
  name: string;
  description: string | null;
  status: ProjectStatus;
  created_by: string;
  created_at: string;
  updated_at: string;
  sheet_count: number;
  member_count: number;
}

export interface PlanDocumentUrlResponse {
  url: string;
  expires_in: number;
}

export type PlanStatus = "processing" | "ready" | "error";

export interface PlanInfo {
  id: string;
  project_id: string;
  filename: string;
  file_size: number | null;
  page_count: number | null;
  status: PlanStatus;
  processed_pages: number;
  error_message: string | null;
  uploaded_by: string;
  created_at: string;
  updated_at: string;
}

export interface SheetInfo {
  id: string;
  plan_id: string;
  project_id: string;
  page_number: number;
  sheet_name: string | null;
  scale_value: number | null;
  scale_unit: string | null;
  scale_label: string | null;
  scale_source: string | null;
  width_px: number | null;
  height_px: number | null;
  thumbnail_url: string | null;
  created_at: string;
}

export interface SearchHit {
  sheet_id: string;
  plan_id: string;
  page_number: number;
  sheet_name: string | null;
  snippet: string;
  match_char_offset: number | null;
}

export interface ProjectSearchResponse {
  query: string;
  matches: SearchHit[];
}
