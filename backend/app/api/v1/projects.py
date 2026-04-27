import uuid

from fastapi import APIRouter, Depends, UploadFile, File, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.middleware.auth import AuthContext
from app.services.permission_service import Permission, require_permission
from app.services import project_service, plan_service, sheet_service, template_service
from app.schemas.project import (
    CreateProjectRequest,
    UpdateProjectRequest,
    ProjectResponse,
    ProjectListResponse,
)
from app.schemas.plan import (
    PlanResponse,
    PlanListResponse,
    SheetListItemResponse,
    SheetListResponse,
    SheetThumbnailUrlsRequest,
    SheetThumbnailUrlsResponse,
    ProjectSearchResponse,
    SearchHit,
)
from app.schemas.assembly import ImportConditionTemplateRequest
from app.schemas.condition import ConditionResponse

router = APIRouter(prefix="/projects")


async def _project_card_counts(
    db: AsyncSession, org_id: uuid.UUID, project_id: uuid.UUID
) -> tuple[int, int]:
    """Sheet total for this project + org-wide active member count (matches list cards)."""
    sc = await project_service.count_sheets_for_project(db, org_id, project_id)
    mc = await project_service.count_active_org_members(db, org_id)
    return sc, mc


# ── Projects ─────────────────────────────────────────────────────────

@router.get("", response_model=ProjectListResponse)
async def list_projects(
    auth: AuthContext = Depends(require_permission(Permission.VIEW_PLANS)),
    db: AsyncSession = Depends(get_db),
):
    projects = await project_service.list_projects(db, auth.org_id)
    return {"projects": projects}


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(
    body: CreateProjectRequest,
    auth: AuthContext = Depends(require_permission(Permission.CREATE_PROJECTS)),
    db: AsyncSession = Depends(get_db),
):
    project = await project_service.create_project(
        db,
        auth.org_id,
        auth.user_id,
        name=body.name,
        description=body.description,
    )
    return ProjectResponse(
        id=project.id,
        org_id=project.org_id,
        name=project.name,
        description=project.description,
        status=project.status,
        created_by=project.created_by,
        created_at=project.created_at,
        updated_at=project.updated_at,
        cover_image_url=None,
        sheet_count=0,
        member_count=0,
    )


@router.get("/{project_id}/search", response_model=ProjectSearchResponse)
async def search_project_plans(
    project_id: uuid.UUID,
    q: str,
    auth: AuthContext = Depends(require_permission(Permission.VIEW_PLANS)),
    db: AsyncSession = Depends(get_db),
):
    """Search extracted text across all sheets in the project."""
    rows = await sheet_service.search_project_sheets(
        db, auth.org_id, project_id, query=q
    )
    return ProjectSearchResponse(
        query=q.strip(),
        matches=[
            SearchHit(
                sheet_id=uuid.UUID(r["sheet_id"]),
                plan_id=uuid.UUID(r["plan_id"]),
                page_number=r["page_number"],
                sheet_name=r["sheet_name"],
                snippet=r["snippet"],
                match_char_offset=r["match_char_offset"],
            )
            for r in rows
        ],
    )


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission(Permission.VIEW_PLANS)),
    db: AsyncSession = Depends(get_db),
):
    project = await project_service.get_project(db, auth.org_id, project_id)
    sheet_count, member_count = await _project_card_counts(db, auth.org_id, project_id)
    return ProjectResponse(
        id=project.id,
        org_id=project.org_id,
        name=project.name,
        description=project.description,
        status=project.status,
        created_by=project.created_by,
        created_at=project.created_at,
        updated_at=project.updated_at,
        cover_image_url=project_service.project_cover_signed_url(project.cover_image_path),
        sheet_count=sheet_count,
        member_count=member_count,
    )


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID,
    body: UpdateProjectRequest,
    auth: AuthContext = Depends(require_permission(Permission.CREATE_PROJECTS)),
    db: AsyncSession = Depends(get_db),
):
    _fields_set = getattr(body, "model_fields_set", None) or set()
    project = await project_service.update_project(
        db,
        auth.org_id,
        project_id,
        auth.user_id,
        name=body.name,
        description=body.description,
        description_provided="description" in _fields_set,
        status=body.status,
    )
    sheet_count, member_count = await _project_card_counts(db, auth.org_id, project_id)
    return ProjectResponse(
        id=project.id,
        org_id=project.org_id,
        name=project.name,
        description=project.description,
        status=project.status,
        created_by=project.created_by,
        created_at=project.created_at,
        updated_at=project.updated_at,
        cover_image_url=project_service.project_cover_signed_url(project.cover_image_path),
        sheet_count=sheet_count,
        member_count=member_count,
    )


@router.post("/{project_id}/cover", response_model=ProjectResponse)
async def upload_project_cover(
    project_id: uuid.UUID,
    file: UploadFile = File(...),
    auth: AuthContext = Depends(require_permission(Permission.CREATE_PROJECTS)),
    db: AsyncSession = Depends(get_db),
):
    """Upload or replace the project card cover image (JPEG, PNG, or WebP)."""
    content = await file.read()
    project = await project_service.upload_project_cover(
        db,
        auth.org_id,
        project_id,
        auth.user_id,
        content=content,
        content_type=file.content_type,
    )
    sheet_count, member_count = await _project_card_counts(db, auth.org_id, project_id)
    return ProjectResponse(
        id=project.id,
        org_id=project.org_id,
        name=project.name,
        description=project.description,
        status=project.status,
        created_by=project.created_by,
        created_at=project.created_at,
        updated_at=project.updated_at,
        cover_image_url=project_service.project_cover_signed_url(project.cover_image_path),
        sheet_count=sheet_count,
        member_count=member_count,
    )


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission(Permission.CREATE_PROJECTS)),
    db: AsyncSession = Depends(get_db),
):
    """Permanently delete the project, all plans/sheets, guest access, and Supabase files."""
    await project_service.delete_project(db, auth.org_id, project_id, auth.user_id)
    return Response(status_code=204)


# ── Plans (upload + list) ────────────────────────────────────────────

@router.post("/{project_id}/plans", response_model=PlanResponse, status_code=201)
async def upload_plan(
    project_id: uuid.UUID,
    file: UploadFile = File(...),
    auth: AuthContext = Depends(require_permission(Permission.UPLOAD_PLANS)),
    db: AsyncSession = Depends(get_db),
):
    content = await file.read()
    plan = await plan_service.create_plan(
        db,
        auth.org_id,
        project_id,
        auth.user_id,
        filename=file.filename or "plan.pdf",
        content=content,
        content_type=file.content_type,
    )
    return PlanResponse(
        id=plan.id,
        project_id=plan.project_id,
        filename=plan.filename,
        file_size=plan.file_size,
        page_count=plan.page_count,
        status=plan.status,
        processed_pages=plan.processed_pages,
        processing_substep=plan.processing_substep,
        error_message=plan.error_message,
        uploaded_by=plan.uploaded_by,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )


@router.get("/{project_id}/plans", response_model=PlanListResponse)
async def list_project_plans(
    project_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission(Permission.VIEW_PLANS)),
    db: AsyncSession = Depends(get_db),
):
    plans = await plan_service.list_project_plans(db, auth.org_id, project_id)
    return {
        "plans": [
            PlanResponse(
                id=p.id,
                project_id=p.project_id,
                filename=p.filename,
                file_size=p.file_size,
                page_count=p.page_count,
                status=p.status,
                processed_pages=p.processed_pages,
                processing_substep=p.processing_substep,
                error_message=p.error_message,
                uploaded_by=p.uploaded_by,
                created_at=p.created_at,
                updated_at=p.updated_at,
            )
            for p in plans
        ]
    }


@router.get("/{project_id}/sheets", response_model=SheetListResponse)
async def list_project_sheets(
    project_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission(Permission.VIEW_PLANS)),
    db: AsyncSession = Depends(get_db),
):
    sheets = await plan_service.list_project_sheets(db, auth.org_id, project_id)

    return {
        "sheets": [
            SheetListItemResponse(
                id=s.id,
                plan_id=s.plan_id,
                project_id=s.project_id,
                page_number=s.page_number,
                sheet_name=s.sheet_name,
                scale_value=s.scale_value,
                scale_unit=s.scale_unit,
                scale_label=s.scale_label,
                scale_source=s.scale_source,
                width_px=s.width_px,
                height_px=s.height_px,
                thumbnail_url=None,
                created_at=s.created_at,
                vector_snap_segment_count=s.vector_snap_segment_count,
            )
            for s in sheets
        ]
    }


@router.post(
    "/{project_id}/sheets/thumbnail-urls",
    response_model=SheetThumbnailUrlsResponse,
)
async def post_sheet_thumbnail_urls(
    project_id: uuid.UUID,
    body: SheetThumbnailUrlsRequest,
    auth: AuthContext = Depends(require_permission(Permission.VIEW_PLANS)),
    db: AsyncSession = Depends(get_db),
):
    """Signed thumbnail URLs for up to 100 sheets (batch; parallel signing on server)."""
    urls = await plan_service.resolve_thumbnail_urls_for_sheets(
        db, auth.org_id, project_id, body.sheet_ids
    )
    return SheetThumbnailUrlsResponse(urls=urls)


@router.post(
    "/{project_id}/conditions/import-from-template",
    response_model=ConditionResponse,
    status_code=201,
)
async def import_condition_from_template(
    project_id: uuid.UUID,
    body: ImportConditionTemplateRequest,
    auth: AuthContext = Depends(require_permission(Permission.IMPORT_TEMPLATES)),
    db: AsyncSession = Depends(get_db),
):
    return await template_service.import_template_to_project(
        db, auth.org_id, project_id, auth.user_id, body.template_id
    )
