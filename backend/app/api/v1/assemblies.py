import uuid

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.middleware.auth import AuthContext
from app.schemas.assembly import (
    AssemblyItemListResponse,
    AssemblyItemResponse,
    CreateAssemblyItemRequest,
    PreviewAssemblyFormulaRequest,
    PreviewAssemblyFormulaResponse,
    UpdateAssemblyItemRequest,
)
from app.services import assembly_service
from app.services.permission_service import Permission, require_permission

router = APIRouter()


@router.post(
    "/conditions/{condition_id}/assembly-formula-preview",
    response_model=PreviewAssemblyFormulaResponse,
)
async def preview_assembly_formula(
    condition_id: uuid.UUID,
    body: PreviewAssemblyFormulaRequest,
    auth: AuthContext = Depends(require_permission(Permission.VIEW_PLANS)),
    db: AsyncSession = Depends(get_db),
):
    return await assembly_service.preview_assembly_formula(db, auth.org_id, condition_id, body)


@router.get("/conditions/{condition_id}/assembly-items", response_model=AssemblyItemListResponse)
async def list_assembly_items(
    condition_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission(Permission.VIEW_PLANS)),
    db: AsyncSession = Depends(get_db),
):
    return await assembly_service.list_assembly_items(db, auth.org_id, condition_id)


@router.post(
    "/conditions/{condition_id}/assembly-items",
    response_model=AssemblyItemResponse,
    status_code=201,
)
async def create_assembly_item(
    condition_id: uuid.UUID,
    body: CreateAssemblyItemRequest,
    auth: AuthContext = Depends(require_permission(Permission.MANAGE_CONDITIONS)),
    db: AsyncSession = Depends(get_db),
):
    return await assembly_service.create_assembly_item(
        db, auth.org_id, condition_id, auth.user_id, body
    )


@router.patch("/assembly-items/{assembly_item_id}", response_model=AssemblyItemResponse)
async def update_assembly_item(
    assembly_item_id: uuid.UUID,
    body: UpdateAssemblyItemRequest,
    auth: AuthContext = Depends(require_permission(Permission.MANAGE_CONDITIONS)),
    db: AsyncSession = Depends(get_db),
):
    return await assembly_service.update_assembly_item(
        db, auth.org_id, assembly_item_id, auth.user_id, body
    )


@router.delete("/assembly-items/{assembly_item_id}", status_code=204)
async def delete_assembly_item(
    assembly_item_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission(Permission.MANAGE_CONDITIONS)),
    db: AsyncSession = Depends(get_db),
):
    await assembly_service.delete_assembly_item(db, auth.org_id, assembly_item_id, auth.user_id)
    return Response(status_code=204)
