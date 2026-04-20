export interface DerivedQuantityInfo {
  assembly_item_id: string;
  name: string;
  unit: string;
  value: number | null;
  error: string | null;
}

export interface MeasurementInfo {
  id: string;
  org_id: string;
  project_id: string;
  sheet_id: string;
  condition_id: string;
  measurement_type: "linear" | "area" | "count";
  geometry: MeasurementGeometry;
  measured_value: number;
  override_value: number | null;
  label: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
  derived_quantities?: DerivedQuantityInfo[];
}

export interface LinearGeometry {
  type: "linear";
  vertices: Array<{ x: number; y: number }>;
}

export interface AreaMetrics {
  gross_area_pdf_sq: number;
  void_area_pdf_sq: number;
  net_area_pdf_sq: number;
  perimeter_outer_pdf: number;
  perimeter_holes_pdf: number;
  perimeter_total_pdf: number;
}

export interface AreaGeometry {
  type: "area";
  shape: "polygon" | "rectangle" | "ellipse";
  outer: Array<{ x: number; y: number }>;
  holes: Array<Array<{ x: number; y: number }>>;
  metrics?: AreaMetrics;
  ellipse?: { cx: number; cy: number; rx: number; ry: number };
  corners?: Array<{ x: number; y: number }>;
}

export interface CountGeometry {
  type: "count";
  position: { x: number; y: number };
}

export type MeasurementGeometry = LinearGeometry | AreaGeometry | CountGeometry;

export interface MeasurementAggregatesResponse {
  sheet_by_condition: Array<{
    condition_id: string;
    measurement_type: string;
    row_count: number;
    sum_measured_value: number;
  }>;
  project_by_condition: Array<{
    condition_id: string;
    measurement_type: string;
    row_count: number;
    sum_measured_value: number;
  }>;
}
