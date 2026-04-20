export type MeasurementType = "linear" | "area" | "count";

export interface ConditionCustomProperty {
  name: string;
  value: string;
  unit: string;
}

export interface ConditionInfo {
  id: string;
  org_id: string;
  project_id: string;
  name: string;
  measurement_type: MeasurementType;
  unit: string;
  color: string;
  line_style: "solid" | "dashed" | "dotted";
  line_width: number;
  fill_opacity: number;
  fill_pattern: "solid" | "hatch" | "crosshatch";
  properties: { custom: ConditionCustomProperty[] };
  trade: string | null;
  description: string | null;
  notes: string | null;
  sort_order: number;
  measurement_count: number;
  total_quantity: number;
  created_at: string;
  updated_at: string;
}
