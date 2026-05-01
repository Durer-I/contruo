/**
 * Sheet-level mutation clients (Sprint AI-02b).
 *
 * Today: inline rename for the sheet index, and the auto-name-sheets trigger
 * that fires the title-block re-extract Celery task. Future plan-viewer
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
  /** Drawing identifier (e.g. "A101"); null until the auto-name flow runs. */
  sheet_number?: string | null;
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

/**
 * 202 response from `POST .../plans/{id}/auto-name-sheets`. The actual
 * rename happens in the background -- see `sheets.auto_named` Liveblocks
 * broadcast and the workspace's polling backstop for completion signaling.
 */
export interface AutoNameSheetsResponse {
  plan_id: string;
  task_id: string;
  queued_at: string;
}

/**
 * Trigger title-block re-extraction for every sheet in a plan.
 *
 * Server enqueues a Celery task that skips manually renamed sheets by default
 * (`sheet_name_source = 'manual'`). Pass `overwriteManual: true` to replace
 * those names too. Returns 202 immediately; the plan viewer
 * refetches sheets when Liveblocks delivers `sheets.auto_named` after the
 * Celery task completes, with polling as a backstop if the broadcast is missed.
 *
 * Errors:
 *   - 409 `PLAN_NOT_READY` when the plan is still processing or errored.
 *   - 503 `AUTO_NAME_DISABLED` when the feature flag is off.
 */
export async function autoNameSheets(
  projectId: string,
  planId: string,
  options?: { overwriteManual?: boolean }
): Promise<AutoNameSheetsResponse> {
  return api.post<AutoNameSheetsResponse>(
    `/api/v1/projects/${projectId}/plans/${planId}/auto-name-sheets`,
    { overwrite_manual: options?.overwriteManual === true }
  );
}
