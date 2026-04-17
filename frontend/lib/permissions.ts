export type Role = "owner" | "admin" | "estimator" | "viewer" | "guest";

export type Permission =
  | "view_plans"
  | "edit_measurements"
  | "manage_conditions"
  | "import_templates"
  | "export_data"
  | "create_projects"
  | "upload_plans"
  | "invite_members"
  | "assign_roles"
  | "remove_members"
  | "manage_org_settings"
  | "manage_template_library"
  | "manage_billing"
  | "delete_org"
  | "transfer_ownership";

const ROLE_PERMISSIONS: Record<Role, Set<Permission>> = {
  owner: new Set([
    "view_plans", "edit_measurements", "manage_conditions", "import_templates",
    "export_data", "create_projects", "upload_plans", "invite_members",
    "assign_roles", "remove_members", "manage_org_settings",
    "manage_template_library", "manage_billing", "delete_org", "transfer_ownership",
  ]),
  admin: new Set([
    "view_plans", "edit_measurements", "manage_conditions", "import_templates",
    "export_data", "create_projects", "upload_plans", "invite_members",
    "assign_roles", "remove_members", "manage_org_settings", "manage_template_library",
  ]),
  estimator: new Set([
    "view_plans", "edit_measurements", "manage_conditions", "import_templates",
    "export_data", "upload_plans",
  ]),
  viewer: new Set(["view_plans", "export_data"]),
  guest: new Set(["view_plans"]),
};

export function hasPermission(role: Role, permission: Permission): boolean {
  return ROLE_PERMISSIONS[role]?.has(permission) ?? false;
}

export function canManageTeam(role: Role): boolean {
  return hasPermission(role, "invite_members");
}

export function canManageOrgSettings(role: Role): boolean {
  return hasPermission(role, "manage_org_settings");
}

export function canManageBilling(role: Role): boolean {
  return hasPermission(role, "manage_billing");
}
