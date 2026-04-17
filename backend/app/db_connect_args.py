"""asyncpg SSL connect_args derived from DATABASE_URL and settings."""
from __future__ import annotations

import logging
import ssl
from urllib.parse import urlparse

from app.config import get_settings

logger = logging.getLogger(__name__)


def _hostname_from_database_url(url: str) -> str | None:
    u = url.strip()
    if "://" in u:
        u = "postgresql://" + u.split("://", 1)[1]
    return urlparse(u).hostname


def asyncpg_connect_args(url: str) -> dict:
    """
    Remote Supabase hosts require TLS. Use DATABASE_SSL_VERIFY=false only for local
    dev when certificate verification fails (e.g. corporate TLS inspection).
    """
    settings = get_settings()
    host = _hostname_from_database_url(url) or ""
    if not host:
        return {}
    if "supabase.co" not in host and "pooler.supabase.com" not in host:
        return {}

    if not settings.database_ssl_verify:
        if settings.is_production:
            logger.error(
                "DATABASE_SSL_VERIFY is disabled while ENVIRONMENT=production — insecure"
            )
        else:
            logger.warning(
                "DATABASE_SSL_VERIFY=false: TLS server certificate verification is disabled "
                "(dev only; fix trust store for production)"
            )
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return {"ssl": ctx}

    return {"ssl": True}
