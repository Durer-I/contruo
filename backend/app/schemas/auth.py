import uuid
from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    org_name: str = Field(..., min_length=1, max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    # Cap login password length to bound request size and align with Supabase max.
    password: str = Field(..., min_length=1, max_length=128)


class ResetPasswordRequest(BaseModel):
    email: EmailStr


class UpdateProfileRequest(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=255)


class UpdatePasswordRequest(BaseModel):
    password: str = Field(..., min_length=8, max_length=128)


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    user: "UserInfo"


class UserInfo(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    org_id: uuid.UUID
    org_name: str
    role: str
    is_guest: bool
    subscription_status: str | None = None
    needs_subscription: bool | None = None
    reactivation_required: bool = False
    billing_banner: str | None = None
    seat_overage: bool = False


class MeResponse(BaseModel):
    user: UserInfo
