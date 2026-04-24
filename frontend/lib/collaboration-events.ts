/** Custom Liveblocks broadcast payloads (JSON-serializable). */
export type CollaborationBroadcastEvent =
  | { type: "contruo.measurements_changed"; sheetId: string }
  | { type: "contruo.conditions_changed" };
