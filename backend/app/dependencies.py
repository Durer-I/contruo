import logging
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.db_connect_args import asyncpg_connect_args

logger = logging.getLogger(__name__)
settings = get_settings()


def _asyncpg_database_url(url: str) -> str:
    """SQLAlchemy async requires postgresql+asyncpg://; plain postgresql:// selects psycopg2."""
    u = url.strip()
    if u.startswith("postgresql+asyncpg://"):
        return u
    if u.startswith("postgresql://"):
        return "postgresql+asyncpg://" + u.removeprefix("postgresql://")
    if u.startswith("postgres://"):
        return "postgresql+asyncpg://" + u.removeprefix("postgres://")
    return u


def _parsed_db_host_port(url: str) -> tuple[str | None, int | None]:
    """Parse host/port for logging only (no credentials)."""
    u = url.strip()
    if "://" in u:
        scheme, rest = u.split("://", 1)
        u = "postgresql://" + rest
    p = urlparse(u)
    return p.hostname, p.port


_async_url = _asyncpg_database_url(settings.database_url)
_db_host, _db_port = _parsed_db_host_port(settings.database_url)

if settings.is_development:
    logger.warning(
        "DATABASE_URL resolves to host=%r port=%r (if host looks wrong, URL-encode special chars in the password)",
        _db_host,
        _db_port,
    )

engine = create_async_engine(
    _async_url,
    echo=settings.is_development,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    connect_args=asyncpg_connect_args(settings.database_url),
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:  # type: ignore[misc]
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
