export const CONDITION_COLORS = [
  { name: "Red", hex: "#ef4444" },
  { name: "Blue", hex: "#3b82f6" },
  { name: "Green", hex: "#22c55e" },
  { name: "Orange", hex: "#f97316" },
  { name: "Purple", hex: "#a855f7" },
  { name: "Yellow", hex: "#eab308" },
  { name: "Cyan", hex: "#06b6d4" },
  { name: "Pink", hex: "#ec4899" },
  { name: "Lime", hex: "#84cc16" },
  { name: "Indigo", hex: "#6366f1" },
  { name: "Teal", hex: "#14b8a6" },
  { name: "Rose", hex: "#f43f5e" },
] as const;

export const MEASUREMENT_TYPES = ["linear", "area", "count"] as const;

export const UNIT_OPTIONS = {
  linear: ["LF", "m"],
  area: ["SF", "m²"],
  count: ["EA"],
} as const;

export const ROLES = ["owner", "admin", "estimator", "viewer"] as const;

export const MIN_VIEWPORT_WIDTH = 1024;

export const SIDEBAR_WIDTH = 240;
export const SIDEBAR_COLLAPSED_WIDTH = 48;
export const TOP_BAR_HEIGHT = 48;
export const STATUS_BAR_HEIGHT = 28;
