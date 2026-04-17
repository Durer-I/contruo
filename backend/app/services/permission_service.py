"""Centralized role-based permission checking.

Maps the permission matrix from roles-and-permissions.md into code.
All API endpoints use require_permission() instead of scattered role checks.
"""

from enum import Enum
from app.middleware.auth import AuthContext
from app.middleware.error_handler import ForbiddenException


class Permission(str, Enum):
    VIEW_PLANS = "view_plans"
    EDIT_MEASUREMENTS = "edit_measurements"
    MANAGE_CONDITIONS = "manage_conditions"
    IMPORT_TEMPLATES = "import_templates"
    EXPORT_DATA = "export_data"
    CREATE_PROJECTS = "create_projects"
    UPLOAD_PLANS = "upload_plans"
    INVITE_MEMBERS = "invite_members"
    ASSIGN_ROLES = "assign_roles"
    REMOVE_MEMBERS = "remove_members"
    MANAGE_ORG_SETTINGS = "manage_org_settings"
    MANAGE_TEMPLATE_LIBRARY = "manage_template_library"
    MANAGE_BILLING = "manage_billing"
    DELETE_ORG = "delete_org"
    TRANSFER_OWNERSHIP = "transfer_ownership"


# Maps role -> set of permissions. Guest permissions are scoped to shared projects at the API layer.
ROLE_PERMISSIONS: dict[str, set[Permission]] = {
    "owner": set(Permission),
    "admin": {
        Permission.VIEW_PLANS,
        Permission.EDIT_MEASUREMENTS,
        Permission.MANAGE_CONDITIONS,
        Permission.IMPORT_TEMPLATES,
        Permission.EXPORT_DATA,
        Permission.CREATE_PROJECTS,
        Permission.UPLOAD_PLANS,
        Permission.INVITE_MEMBERS,
        Permission.ASSIGN_ROLES,
        Permission.REMOVE_MEMBERS,
        Permission.MANAGE_ORG_SETTINGS,
        Permission.MANAGE_TEMPLATE_LIBRARY,
    },
    "estimator": {
        Permission.VIEW_PLANS,
        Permission.EDIT_MEASUREMENTS,
        Permission.MANAGE_CONDITIONS,
        Permission.IMPORT_TEMPLATES,
        Permission.EXPORT_DATA,
        Permission.UPLOAD_PLANS,
    },
    "viewer": {
        Permission.VIEW_PLANS,
        Permission.EXPORT_DATA,
    },
    "guest": {
        Permission.VIEW_PLANS,
    },
}


def has_permission(role: str, permission: Permission) -> bool:
    perms = ROLE_PERMISSIONS.get(role, set())
    return permission in perms


def check_permission(auth: AuthContext, permission: Permission) -> None:
    if not has_permission(auth.role, permission):
        raise ForbiddenException(
            f"Role '{auth.role}' does not have '{permission.value}' permission"
        )


def require_permission(*permissions: Permission):
    """FastAPI dependency factory that checks the user has ALL of the listed permissions."""
    from fastapi import Depends
    from app.middleware.auth import get_current_user

    async def _check(user: AuthContext = Depends(get_current_user)) -> AuthContext:
        for perm in permissions:
            check_permission(user, perm)
        return user

    return _check
