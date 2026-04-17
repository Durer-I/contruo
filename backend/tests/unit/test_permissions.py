"""Tests for the permission service."""

from app.services.permission_service import Permission, has_permission, ROLE_PERMISSIONS


def test_owner_has_all_permissions():
    for perm in Permission:
        assert has_permission("owner", perm), f"Owner missing {perm}"


def test_admin_cannot_manage_billing():
    assert not has_permission("admin", Permission.MANAGE_BILLING)
    assert not has_permission("admin", Permission.DELETE_ORG)
    assert not has_permission("admin", Permission.TRANSFER_OWNERSHIP)


def test_admin_can_manage_team():
    assert has_permission("admin", Permission.INVITE_MEMBERS)
    assert has_permission("admin", Permission.ASSIGN_ROLES)
    assert has_permission("admin", Permission.REMOVE_MEMBERS)
    assert has_permission("admin", Permission.MANAGE_ORG_SETTINGS)


def test_estimator_can_edit():
    assert has_permission("estimator", Permission.EDIT_MEASUREMENTS)
    assert has_permission("estimator", Permission.MANAGE_CONDITIONS)
    assert has_permission("estimator", Permission.UPLOAD_PLANS)
    assert has_permission("estimator", Permission.EXPORT_DATA)


def test_estimator_cannot_manage_team():
    assert not has_permission("estimator", Permission.INVITE_MEMBERS)
    assert not has_permission("estimator", Permission.ASSIGN_ROLES)
    assert not has_permission("estimator", Permission.MANAGE_ORG_SETTINGS)
    assert not has_permission("estimator", Permission.CREATE_PROJECTS)


def test_viewer_is_readonly():
    assert has_permission("viewer", Permission.VIEW_PLANS)
    assert has_permission("viewer", Permission.EXPORT_DATA)
    assert not has_permission("viewer", Permission.EDIT_MEASUREMENTS)
    assert not has_permission("viewer", Permission.MANAGE_CONDITIONS)
    assert not has_permission("viewer", Permission.UPLOAD_PLANS)


def test_guest_view_only():
    assert has_permission("guest", Permission.VIEW_PLANS)
    assert not has_permission("guest", Permission.EXPORT_DATA)
    assert not has_permission("guest", Permission.EDIT_MEASUREMENTS)


def test_unknown_role_has_no_permissions():
    assert not has_permission("nonexistent", Permission.VIEW_PLANS)


def test_all_roles_have_view_plans():
    for role in ROLE_PERMISSIONS:
        assert has_permission(role, Permission.VIEW_PLANS), f"{role} missing VIEW_PLANS"
