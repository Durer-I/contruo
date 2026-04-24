export type ExportFormat = "xlsx" | "pdf";

export interface ExportQueuedResponse {
  task_id: string;
  status: string;
}

export interface ExportStatusResponse {
  status: string;
  error?: string | null;
  download_url?: string | null;
  filename?: string | null;
}
