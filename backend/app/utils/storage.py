"""Supabase Storage helpers.

Centralizes bucket names and signed-URL generation so that code elsewhere
never has to know bucket conventions or the service-role key details.
"""

from __future__ import annotations

import logging
from typing import Any

from supabase import create_client

from app.config import get_settings

logger = logging.getLogger(__name__)

#: Buckets required by the app. Ensured lazily on first access in development.
PLANS_BUCKET = "plans"
THUMBNAILS_BUCKET = "plan-thumbnails"
#: Generated export files (xlsx/pdf); private bucket, short-lived objects.
EXPORTS_BUCKET = "exports"

#: Default signed URL lifetime for plan/thumbnail access. 1 hour is a reasonable balance:
#: long enough that polling clients don't need to re-request often, short enough that a leaked
#: URL has limited blast radius.
SIGNED_URL_EXPIRES_SEC = 60 * 60


def _admin_client():
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def _is_bucket_exists_error(err: Exception) -> bool:
    msg = str(err).lower()
    return (
        "already exists" in msg
        or "duplicate" in msg
        or "resource already exists" in msg
    )


def ensure_bucket(name: str, *, public: bool = False) -> None:
    """Create the bucket if it doesn't exist. Idempotent."""
    sb = _admin_client()
    try:
        sb.storage.create_bucket(name, options={"public": public})
        logger.info("Created storage bucket '%s' (public=%s)", name, public)
    except Exception as e:
        if _is_bucket_exists_error(e):
            return
        # Some bucket listings work when create fails for policy reasons; swallow in dev.
        logger.warning("Bucket '%s' create failed (possibly pre-existing): %s", name, e)


def upload_bytes(
    bucket: str,
    path: str,
    content: bytes,
    *,
    content_type: str = "application/octet-stream",
    upsert: bool = True,
) -> str:
    """Upload a file and return the storage path."""
    sb = _admin_client()
    sb.storage.from_(bucket).upload(
        path,
        content,
        {"content-type": content_type, "upsert": "true" if upsert else "false"},
    )
    return path


def download_bytes(bucket: str, path: str) -> bytes:
    sb = _admin_client()
    return sb.storage.from_(bucket).download(path)


def signed_url(bucket: str, path: str, expires_sec: int = SIGNED_URL_EXPIRES_SEC) -> str | None:
    """Return a signed URL to the object, or None if the object is missing."""
    sb = _admin_client()
    try:
        result: Any = sb.storage.from_(bucket).create_signed_url(path, expires_sec)
        # supabase-py returns a dict with 'signedURL' or 'signed_url' depending on version
        if isinstance(result, dict):
            return result.get("signedURL") or result.get("signed_url")
        return None
    except Exception as e:
        logger.warning("Failed to create signed URL for %s/%s: %s", bucket, path, e)
        return None


def plan_storage_path(org_id, plan_id, filename: str) -> str:
    """Canonical org-scoped path for an uploaded plan PDF."""
    return f"{org_id}/plans/{plan_id}/{filename}"


def thumbnail_storage_path(org_id, plan_id, page_number: int) -> str:
    return f"{org_id}/plans/{plan_id}/thumbs/page-{page_number}.png"


def remove_files(bucket: str, paths: list[str]) -> None:
    """Best-effort removal of storage objects. Logs warnings on failure (e.g. already deleted)."""
    cleaned = sorted({p.strip() for p in paths if p and p.strip()})
    if not cleaned:
        return
    sb = _admin_client()
    chunk = 100
    for i in range(0, len(cleaned), chunk):
        batch = cleaned[i : i + chunk]
        try:
            sb.storage.from_(bucket).remove(batch)
        except Exception as e:
            logger.warning(
                "Storage remove failed for bucket=%s batch_size=%s: %s",
                bucket,
                len(batch),
                e,
            )
