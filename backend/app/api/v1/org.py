import uuid

from fastapi import APIRouter, Depends, Response, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.middleware.auth import AuthContext
from app.services.permission_service import Permission, require_permission
from app.services import billing_service, org_service
from app.schemas.org import (
    UpdateOrgRequest,
    OrgResponse,
    MemberListResponse,
    MemberResponse,
    UpdateMemberRoleRequest,
    InviteRequest,
    InvitationResponse,
    InvitationListResponse,
    AcceptInvitationRequest,
    GuestInviteRequest,
)
from app.schemas.auth import AuthResponse
from app.schemas.assembly import (
    ConditionTemplateDetailResponse,
    ConditionTemplateListResponse,
    ConditionTemplateResponse,
    SaveConditionAsTemplateRequest,
    UpdateConditionTemplateRequest,
)
from app.services import template_service

router = APIRouter(prefix="/org")


# ── Organization Settings ────────────────────────────────────────────

@router.get("", response_model=OrgResponse)
async def get_org(
    auth: AuthContext = Depends(require_permission(Permission.VIEW_PLANS)),
    db: AsyncSession = Depends(get_db),
):
    org = await org_service.get_org(db, auth.org_id)
    return org


@router.patch("", response_model=OrgResponse)
async def update_org(
    body: UpdateOrgRequest,
    auth: AuthContext = Depends(require_permission(Permission.MANAGE_ORG_SETTINGS)),
    db: AsyncSession = Depends(get_db),
):
    org = await org_service.update_org(
        db,
        auth.org_id,
        auth.user_id,
        name=body.name,
        default_units=body.default_units,
    )
    return org


@router.post("/logo", response_model=OrgResponse)
async def upload_logo(
    file: UploadFile = File(...),
    auth: AuthContext = Depends(require_permission(Permission.MANAGE_ORG_SETTINGS)),
    db: AsyncSession = Depends(get_db),
):
    content = await file.read()
    max_size = 2 * 1024 * 1024
    if len(content) > max_size:
        from app.middleware.error_handler import AppException
        raise AppException(code="FILE_TOO_LARGE", message="Logo must be under 2MB", status_code=400)

    ext = (file.filename or "logo.png").rsplit(".", 1)[-1].lower()
    if ext not in ("png", "jpg", "jpeg", "svg", "webp"):
        from app.middleware.error_handler import AppException
        raise AppException(code="INVALID_FILE_TYPE", message="Logo must be PNG, JPG, SVG, or WebP", status_code=400)

    from app.config import get_settings
    from supabase import create_client
    settings = get_settings()
    supabase = create_client(settings.supabase_url, settings.supabase_service_role_key)

    path = f"{auth.org_id}/logo.{ext}"
    supabase.storage.from_("org-assets").upload(
        path, content, {"content-type": file.content_type or "image/png", "upsert": "true"}
    )
    logo_url = f"{settings.supabase_url}/storage/v1/object/public/org-assets/{path}"

    org = await org_service.update_org(db, auth.org_id, auth.user_id, logo_url=logo_url)
    return org


# ── Members ──────────────────────────────────────────────────────────

@router.get("/members", response_model=MemberListResponse)
async def list_members(
    auth: AuthContext = Depends(require_permission(Permission.VIEW_PLANS)),
    db: AsyncSession = Depends(get_db),
):
    await billing_service.refresh_subscription_automatic_transitions(db, auth.org_id)
    members = await org_service.list_members(db, auth.org_id)
    used = await billing_service.count_billable_seats_used(db, auth.org_id)
    sub = await billing_service.get_subscription(db, auth.org_id)
    can_inv = await billing_service.can_invite_billable_member(db, auth.org_id)
    purchased: int | None = None
    if sub is not None and sub.status not in ("cancelled", "suspended"):
        purchased = int(sub.seat_count)
    sched = await billing_service.scheduled_seat_change_for_org(
        db, auth.org_id, skip_refresh=True
    )
    return {
        "members": members,
        "billable_seats_used": used,
        "purchased_seats": purchased,
        "can_invite_billable_member": can_inv,
        "scheduled_billed_seats": sched.get("scheduled_billed_seats"),
        "scheduled_seat_change_effective_at": sched.get("scheduled_seat_change_effective_at"),
    }


@router.patch("/members/{member_id}", response_model=MemberResponse)
async def update_member_role(
    member_id: uuid.UUID,
    body: UpdateMemberRoleRequest,
    auth: AuthContext = Depends(require_permission(Permission.ASSIGN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    member = await org_service.update_member_role(
        db, auth.org_id, member_id, body.role, auth.user_id
    )
    # Fetch email from Supabase for response
    from supabase import create_client
    from app.config import get_settings
    s = get_settings()
    sb = create_client(s.supabase_url, s.supabase_service_role_key)
    email = ""
    try:
        auth_user = sb.auth.admin.get_user_by_id(str(member_id))
        email = auth_user.user.email or ""
    except Exception:
        pass
    return MemberResponse(
        id=member.id,
        email=email,
        full_name=member.full_name,
        role=member.role,
        is_guest=member.is_guest,
        deactivated_at=member.deactivated_at,
        created_at=member.created_at,
    )


@router.delete("/members/{member_id}", status_code=200)
async def deactivate_member(
    member_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission(Permission.REMOVE_MEMBERS)),
    db: AsyncSession = Depends(get_db),
):
    await org_service.deactivate_member(db, auth.org_id, member_id, auth.user_id)
    return {"message": "Member deactivated"}


# ── Invitations ──────────────────────────────────────────────────────

@router.post("/members/invite", response_model=InvitationResponse, status_code=201)
async def invite_member(
    body: InviteRequest,
    auth: AuthContext = Depends(require_permission(Permission.INVITE_MEMBERS)),
    db: AsyncSession = Depends(get_db),
):
    invitation = await org_service.create_invitation(
        db, auth.org_id, body.email, body.role, auth.user_id
    )
    return invitation


@router.get("/invitations", response_model=InvitationListResponse)
async def list_invitations(
    auth: AuthContext = Depends(require_permission(Permission.INVITE_MEMBERS)),
    db: AsyncSession = Depends(get_db),
):
    invitations = await org_service.list_invitations(db, auth.org_id)
    return {"invitations": invitations}


@router.post("/invitations/{invitation_id}/resend", response_model=InvitationResponse)
async def resend_invitation(
    invitation_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission(Permission.INVITE_MEMBERS)),
    db: AsyncSession = Depends(get_db),
):
    return await org_service.resend_invitation(db, auth.org_id, invitation_id, auth.user_id)


@router.post("/invitations/{invitation_id}/cancel", status_code=200)
async def cancel_invitation(
    invitation_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission(Permission.INVITE_MEMBERS)),
    db: AsyncSession = Depends(get_db),
):
    await org_service.cancel_invitation(db, auth.org_id, invitation_id, auth.user_id)
    return {"message": "Invitation cancelled"}


@router.post("/invitations/accept/{token}", response_model=AuthResponse, status_code=201)
async def accept_invitation(
    token: str,
    body: AcceptInvitationRequest,
    db: AsyncSession = Depends(get_db),
):
    return await org_service.accept_invitation(db, token, body.full_name, body.password)


# ── Condition templates (org library) ─────────────────────────────────

@router.get("/condition-templates", response_model=ConditionTemplateListResponse)
async def list_condition_templates(
    auth: AuthContext = Depends(require_permission(Permission.VIEW_PLANS)),
    db: AsyncSession = Depends(get_db),
):
    return await template_service.list_templates(db, auth.org_id)


@router.get("/condition-templates/{template_id}", response_model=ConditionTemplateDetailResponse)
async def get_condition_template(
    template_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission(Permission.VIEW_PLANS)),
    db: AsyncSession = Depends(get_db),
):
    return await template_service.get_template(db, auth.org_id, template_id)


@router.patch("/condition-templates/{template_id}", response_model=ConditionTemplateDetailResponse)
async def update_condition_template(
    template_id: uuid.UUID,
    body: UpdateConditionTemplateRequest,
    auth: AuthContext = Depends(require_permission(Permission.MANAGE_CONDITIONS)),
    db: AsyncSession = Depends(get_db),
):
    return await template_service.update_template(
        db, auth.org_id, template_id, auth.user_id, body
    )


@router.post(
    "/conditions/{condition_id}/save-as-template",
    response_model=ConditionTemplateResponse,
    status_code=201,
)
async def save_condition_as_template(
    condition_id: uuid.UUID,
    body: SaveConditionAsTemplateRequest,
    auth: AuthContext = Depends(require_permission(Permission.MANAGE_CONDITIONS)),
    db: AsyncSession = Depends(get_db),
):
    return await template_service.save_condition_as_template(
        db, auth.org_id, condition_id, auth.user_id, body
    )


@router.delete("/condition-templates/{template_id}", status_code=204)
async def delete_condition_template(
    template_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission(Permission.MANAGE_CONDITIONS)),
    db: AsyncSession = Depends(get_db),
):
    await template_service.delete_template(db, auth.org_id, template_id, auth.user_id)
    return Response(status_code=204)


# ── Guest Access ─────────────────────────────────────────────────────

@router.post("/guests/invite", response_model=InvitationResponse, status_code=201)
async def invite_guest(
    body: GuestInviteRequest,
    auth: AuthContext = Depends(require_permission(Permission.INVITE_MEMBERS)),
    db: AsyncSession = Depends(get_db),
):
    return await org_service.invite_guest(
        db, auth.org_id, body.email, body.project_id, auth.user_id
    )


@router.delete("/guests/{guest_id}", status_code=200)
async def revoke_guest(
    guest_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission(Permission.REMOVE_MEMBERS)),
    db: AsyncSession = Depends(get_db),
):
    await org_service.revoke_guest_access(db, auth.org_id, guest_id, auth.user_id)
    return {"message": "Guest access revoked"}
