export interface AssemblyItemInfo {
  id: string;
  org_id: string;
  condition_id: string;
  parent_id: string | null;
  name: string;
  unit: string;
  formula: string;
  description: string | null;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface ConditionTemplateInfo {
  id: string;
  org_id: string;
  name: string;
  measurement_type: string;
  unit: string;
  color: string;
  line_style?: string;
  line_width?: number;
  fill_opacity?: number;
  fill_pattern?: string;
  properties?: { custom: Array<{ name: string; value: string; unit: string }> };
  trade?: string | null;
  description?: string | null;
  assembly_item_count: number;
  created_at: string;
  updated_at: string;
}

export interface ConditionTemplateAssemblySnapshotItem {
  name: string;
  unit: string;
  formula: string;
  description?: string | null;
  sort_order: number;
}

/** Full template from GET /org/condition-templates/:id (includes assembly snapshot). */
export interface ConditionTemplateDetail extends ConditionTemplateInfo {
  line_style: string;
  line_width: number;
  fill_opacity: number;
  fill_pattern: string;
  properties: { custom: Array<{ name: string; value: string; unit: string }> };
  trade: string | null;
  description: string | null;
  assembly_items: ConditionTemplateAssemblySnapshotItem[];
}
