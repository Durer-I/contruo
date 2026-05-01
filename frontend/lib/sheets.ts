/**
 * Sheet-level mutation clients (Sprint AI-02b).
 *
 * Today: just the inline rename used by `sheet-index.tsx`. Future plan-viewer
 * sheet-level actions (delete, reorder, etc.) belong here so this stays the
 * one entry point for `/api/v1/sheets/{id}` mutations.
 */

import { api } from "@/lib/api";

import type { SheetNameSource } from "@/types/project";

/**
 * Subset of the backend `SheetResponse` returned by the rename endpoint.
 *
 * We intentionally do NOT re-export the full `SheetInfo` shape here -- the
 * project sheet list (`SheetListItemResponse`) and per-sheet detail
 * (`SheetResponse`) are slightly different surfaces and conflating them
 * would force callers to deal with optional fields they don't need.
 */
export interface SheetMutationResponse {
  id: string;
  plan_id: string;
  project_id: string;
  page_number: number;
  sheet_name: string | null;
  sheet_name_source?: SheetNameSource | null;
  scale_value: number | null;
  scale_unit: string | null;
  scale_label: string | null;
  scale_source: string | null;
  width_px: number | null;
  height_px: number | null;
  thumbnail_url: string | null;
  created_at: string;
}

/**
 * Inline-rename a sheet from the sheet index.
 *
 * Server trims whitespace, rejects empty results with 422
 * (`SHEET_NAME_EMPTY`), and sets `sheet_name_source = 'manual'` so any
 * future AI title-block re-extract leaves the user's edit alone.
 *
 * Caller is responsible for optimistic update + rollback on failure -- the
 * UI for the inline edit is small enough that pushing the optimism down
 * into this client would be more friction than it's worth.
 */
export async function renameSheet(
  sheetId: string,
  sheetName: string
): Promise<SheetMutationResponse> {
  return api.patch<SheetMutationResponse>(
    `/api/v1/sheets/${sheetId}`,
    { sheet_name: sheetName }
  );
}
