"""Quantities export — queue generation and poll for download."""

from __future__ import annotations

from celery.result import AsyncResult
from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse

from app.middleware.auth import AuthContext
from app.middleware.error_handler import AppException, NotFoundException
from app.schemas.export import ExportQueuedResponse, ExportRequest, ExportStatusResponse
from app.services.permission_service import Permission, require_permission
from app.tasks.celery_app import celery_app
from app.tasks.export_generation import generate_quantities_export
from app.utils import storage

router = APIRouter(tags=["export"])


@router.post("/projects/{project_id}/export", response_model=ExportQueuedResponse, status_code=202)
async def queue_project_export(
    project_id: str,
    body: ExportRequest,
    auth: AuthContext = Depends(require_permission(Permission.EXPORT_DATA)),
):
    """Queue async export; poll ``GET /exports/{task_id}`` for status and signed download URL."""
    try:
        task = generate_quantities_export.delay(
            str(auth.org_id),
            project_id,
            str(auth.user_id),
            body.format,
        )
    except Exception as e:
        raise AppException(
            code="EXPORT_QUEUE_FAILED",
            message=f"Could not queue export (is Redis/Celery running?): {e}",
            status_code=503,
        ) from e
    return ExportQueuedResponse(task_id=task.id, status="pending")


@router.get("/exports/{task_id}", response_model=ExportStatusResponse)
async def get_export_status(
    task_id: str,
    auth: AuthContext = Depends(require_permission(Permission.EXPORT_DATA)),
):
    r = AsyncResult(task_id, app=celery_app)
    st = (r.state or "").upper()
    if st in ("PENDING", "STARTED", "RETRY"):
        return ExportStatusResponse(status=st.lower())
    if st == "FAILURE":
        err = str(r.result) if r.result else "export failed"
        return ExportStatusResponse(status="failure", error=err[:2000])
    if st == "SUCCESS":
        meta = r.result
        if not isinstance(meta, dict):
            return ExportStatusResponse(status="failure", error="invalid task result")
        if str(meta.get("org_id")) != str(auth.org_id):
            raise NotFoundException("export", task_id)
        path = meta.get("path")
        bucket = meta.get("bucket")
        filename = meta.get("filename") or "export.bin"
        if not path or not bucket:
            return ExportStatusResponse(status="failure", error="missing file metadata")
        url = storage.signed_url(str(bucket), str(path), expires_sec=60 * 60)
        if not url:
            return ExportStatusResponse(status="failure", error="could not create download URL")
        return ExportStatusResponse(status="success", download_url=url, filename=filename)
    return ExportStatusResponse(status=st.lower())


@router.get("/exports/{task_id}/download")
async def download_export_redirect(
    task_id: str,
    auth: AuthContext = Depends(require_permission(Permission.EXPORT_DATA)),
):
    """302 redirect to a time-limited signed URL (optional convenience)."""
    r = AsyncResult(task_id, app=celery_app)
    if not r.ready() or r.state != "SUCCESS":
        raise NotFoundException("export", task_id)
    meta = r.result
    if not isinstance(meta, dict) or str(meta.get("org_id")) != str(auth.org_id):
        raise NotFoundException("export", task_id)
    path = meta.get("path")
    bucket = meta.get("bucket")
    if not path or not bucket:
        raise NotFoundException("export", task_id)
    url = storage.signed_url(str(bucket), str(path), expires_sec=60 * 60)
    if not url:
        raise NotFoundException("export", task_id)
    return RedirectResponse(url=url, status_code=302)
