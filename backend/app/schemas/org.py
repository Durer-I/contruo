import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class UpdateOrgRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    default_units: str | None = Field(None, pattern=r"^(imperial|metric)$")


class OrgResponse(BaseModel):
    id: uuid.UUID
    name: str
    logo_url: str | None
    default_units: str
    created_at: datetime


class MemberResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    is_guest: bool
    deactivated_at: datetime | None
    created_at: datetime


class MemberListResponse(BaseModel):
    members: list[MemberResponse]


class UpdateMemberRoleRequest(BaseModel):
    role: str = Field(..., pattern=r"^(admin|estimator|viewer)$")


class InviteRequest(BaseModel):
    email: str = Field(..., max_length=320)
    role: str = Field(default="estimator", pattern=r"^(admin|estimator|viewer)$")


class InvitationResponse(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    status: str
    expires_at: datetime
    created_at: datetime


class InvitationListResponse(BaseModel):
    invitations: list[InvitationResponse]


class AcceptInvitationRequest(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)


class GuestInviteRequest(BaseModel):
    email: str = Field(..., max_length=320)
    project_id: uuid.UUID
