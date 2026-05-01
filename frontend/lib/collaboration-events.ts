/** Custom Liveblocks broadcast payloads (JSON-serializable). */
export type CollaborationBroadcastEvent =
  | {
      type: "contruo.measurements_changed";
      sheetId: string;
      /** Hint for analytics / future targeted sync; peers still resync lists (debounced). */
      measurementIds?: string[];
      deletedIds?: string[];
    }
  | { type: "contruo.conditions_changed" }
  /** Celery auto-name task finished; clients should refetch project sheets. */
  | {
      type: "sheets.auto_named";
      data: {
        plan_id: string;
        duration_ms?: number;
        counters?: Record<string, unknown>;
      };
    };
