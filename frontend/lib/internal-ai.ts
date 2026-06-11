/**
 * Internal AI extractions client (Sprint AI-03).
 *
 * Owner / admin only. Backs the internal debug page that lets engineering
 * spot-check Stage 3a output (extracted schedules + legend symbols + their
 * multi-scale variant grids) without queries.
 */

import { api } from "@/lib/api";

export interface ExtractedScheduleRow {
  id: string;
  sheet_id: string;
  sheet_name: string | null;
  sheet_number: string | null;
  page_number: number | null;
  bbox_pdf: { x0: number; y0: number; x1: number; y1: number };
  extraction_method: string;
  tag_column_index: number | null;
  description_column_index: number | null;
  quantity_column_index: number | null;
  dimension_column_indexes: number[] | null;
  material_column_index: number | null;
  headers: string[];
  row_count: number;
  sample_rows: string[][];
}

export interface ExtractedLegendVariantRow {
  scale: number;
  rotation: number;
  template_storage_path: string;
  signed_url: string | null;
}

export interface ExtractedLegendRow {
  id: string;
  sheet_id: string;
  sheet_name: string | null;
  sheet_number: string | null;
  page_number: number | null;
  label: string;
  bbox_pdf: { x0: number; y0: number; x1: number; y1: number };
  template_hash: string;
  template_storage_path: string;
  primary_signed_url: string | null;
  extraction_method: string;
  variants: ExtractedLegendVariantRow[];
}

export interface AiRunExtractionsResponse {
  ai_run_id: string;
  plan_id: string;
  project_id: string;
  schedules: ExtractedScheduleRow[];
  legends: ExtractedLegendRow[];
  summary: {
    schedules_legends?: Record<string, number | string>;
    run_status?: string;
    schedule_count?: number;
    legend_count?: number;
  };
}

export async function getRunExtractions(
  aiRunId: string
): Promise<AiRunExtractionsResponse> {
  return api.get<AiRunExtractionsResponse>(
    `/api/v1/internal/ai/runs/${aiRunId}/extractions`
  );
}
