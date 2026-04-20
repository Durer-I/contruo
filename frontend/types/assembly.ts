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
  assembly_item_count: number;
  created_at: string;
  updated_at: string;
}
