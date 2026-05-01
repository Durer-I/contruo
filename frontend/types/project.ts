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
  /** Signed URL for dashboard / project list card; null if no cover uploaded. */
  cover_image_url: string | null;
  sheet_count: number;
  member_count: number;
}

export interface PlanDocumentUrlResponse {
  url: string;
  expires_in: number;
}

export type PlanStatus = "processing" | "ready" | "error";

/** Celery PDF task phase when status is `processing` (see backend `pdf_processing`). */
export type PlanProcessingSubstep = "extract" | "persist";

export interface PlanInfo {
  id: string;
  project_id: string;
  filename: string;
  file_size: number | null;
  page_count: number | null;
  status: PlanStatus;
  processed_pages: number;
  /** Present while a plan PDF is being processed in the worker. */
  processing_substep?: PlanProcessingSubstep | null;
  error_message: string | null;
  uploaded_by: string;
  created_at: string;
  updated_at: string;
}

export type VectorSnapSegment = { x1: number; y1: number; x2: number; y2: number };

export interface SheetVectorSnapResponse {
  segments: VectorSnapSegment[] | null;
}

/** Response from ``POST /api/v1/projects/{id}/sheets/thumbnail-urls``. */
export interface SheetThumbnailUrlsResponse {
  urls: Record<string, string | null>;
}

/**
 * Discipline taxonomy mirrors `backend/app/services/ai_sheet_classifier.ALL_DISCIPLINES`.
 * Keep this in sync; the sheet-index dot-color map is keyed by these values.
 */
export type SheetDiscipline =
  | "architectural"
  | "structural"
  | "mechanical"
  | "electrical"
  | "plumbing"
  | "civil"
  | "landscape"
  | "telecom"
  | "fire_protection"
  | "interiors"
  | "general"
  | "equipment"
  | "other";

/** Mirrors `backend/app/services/ai_sheet_classifier.ALL_SHEET_TYPES`. */
export type SheetType =
  | "plan"
  | "elevation"
  | "section"
  | "detail"
  | "schedule"
  | "legend"
  | "diagram"
  | "cover"
  | "index"
  | "spec"
  | "other";

/** Which path produced the AI-02 classification for a sheet. */
export type SheetClassificationMethod =
  | "lexical"
  | "vision"
  | "manual"
  | "sheet_number";

/** Where the current ``sheet_name`` came from. ``null`` is treated as ``'auto'``
 * by writers so legacy rows are eligible to be overwritten on a future
 * re-extract (AI-02b's title-block flow will reintroduce the auto writer).
 * ``'manual'`` means a user typed it inline -- never overwritten by
 * extraction. */
export type SheetNameSource = "auto" | "manual";

export interface SheetInfo {
  id: string;
  plan_id: string;
  project_id: string;
  page_number: number;
  sheet_name: string | null;
  /**
   * Drawing identifier extracted from the title block (e.g. ``"A101"``,
   * ``"G1.1"``, ``"S-100"``). Null until the AI-02b auto-name flow runs.
   * Guarded by the same ``sheet_name_source`` flag as ``sheet_name``.
   */
  sheet_number?: string | null;
  /** AI-02b: which path produced the current sheet name. */
  sheet_name_source?: SheetNameSource | null;
  scale_value: number | null;
  scale_unit: string | null;
  scale_label: string | null;
  scale_source: string | null;
  width_px: number | null;
  height_px: number | null;
  /** Omitted on project sheet list; use thumbnail-urls batch or PATCH scale. */
  thumbnail_url: string | null;
  created_at: string;
  /** From project sheet list; full segments loaded lazily per active sheet. */
  vector_snap_segment_count: number;
  /** Populated after `GET /api/v1/sheets/{id}/vector-snap` (or PATCH scale response). */
  vector_snap_segments?: VectorSnapSegment[] | null;
  /** AI-02 sheet classification. NULL until the AI run completes Stage 2 for the plan. */
  discipline?: SheetDiscipline | null;
  sheet_type?: SheetType | null;
  classification_confidence?: number | null;
  classification_method?: SheetClassificationMethod | null;
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
