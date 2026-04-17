from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    ResetPasswordRequest,
    UpdateProfileRequest,
    AuthResponse,
    MeResponse,
)
from app.services import auth_service
from app.middleware.auth import get_current_user, AuthContext

router = APIRouter(prefix="/auth")


@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    result = await auth_service.register_user(
        db,
        full_name=body.full_name,
        email=body.email,
        password=body.password,
        org_name=body.org_name,
    )
    return result


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    tokens = await auth_service.login_user(body.email, body.password)

    user_info = await auth_service.get_user_with_org(db, tokens["supabase_user_id"])
    user_info["email"] = body.email
    return {
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "user": user_info,
    }


@router.post("/reset-password", status_code=200)
async def reset_password(body: ResetPasswordRequest):
    await auth_service.request_password_reset(body.email)
    return {"message": "If that email exists, a reset link has been sent."}


@router.post("/logout", status_code=200)
async def logout(request: Request):
    """Optional: revoke server-side session. Prefer browser `supabase.auth.signOut()` as the single logout to avoid double /logout (session_not_found)."""
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
    if token:
        await auth_service.logout_user(token)
    return {"message": "Logged out"}


@router.get("/me", response_model=MeResponse)
async def me(
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_info = await auth_service.get_user_with_org(db, auth.user_id)
    user_info["email"] = auth.email
    return {"user": user_info}


@router.patch("/me", response_model=MeResponse)
async def patch_me(
    body: UpdateProfileRequest,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_info = await auth_service.update_profile(
        db, user_id=auth.user_id, full_name=body.full_name
    )
    user_info["email"] = auth.email
    return {"user": user_info}
