import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.middleware.auth import AuthContext
from app.services.permission_service import Permission, require_permission
from app.services import plan_service, sheet_service
from app.schemas.plan import PatchSheetScaleRequest, SheetResponse

router = APIRouter(prefix="/sheets")


@router.patch("/{sheet_id}/scale", response_model=SheetResponse)
async def patch_sheet_scale(
    sheet_id: uuid.UUID,
    body: PatchSheetScaleRequest,
    auth: AuthContext = Depends(require_permission(Permission.EDIT_MEASUREMENTS)),
    db: AsyncSession = Depends(get_db),
):
    """Set sheet scale from a calibration line (real distance / PDF segment length)."""
    sheet = await sheet_service.update_sheet_scale(
        db,
        auth.org_id,
        sheet_id,
        pdf_line_length_points=body.pdf_line_length_points,
        real_distance=body.real_distance,
        real_unit=body.real_unit,
    )
    return SheetResponse(
        id=sheet.id,
        plan_id=sheet.plan_id,
        project_id=sheet.project_id,
        page_number=sheet.page_number,
        sheet_name=sheet.sheet_name,
        scale_value=sheet.scale_value,
        scale_unit=sheet.scale_unit,
        scale_label=sheet.scale_label,
        scale_source=sheet.scale_source,
        width_px=sheet.width_px,
        height_px=sheet.height_px,
        thumbnail_url=plan_service.sheet_thumbnail_url(sheet),
        created_at=sheet.created_at,
    )
