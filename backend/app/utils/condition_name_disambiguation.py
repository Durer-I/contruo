"""Pick a unique condition display name within a project (e.g. for template import)."""

from __future__ import annotations

from app.middleware.error_handler import AppException


def disambiguate_condition_name(base: str, taken: set[str]) -> str:
    """
    Return ``base`` if not in ``taken``, else ``f"{base} (2)"``, ``(3)``, …
    Truncates the base prefix so the final string fits in 255 characters.
    """
    b = base.strip()[:255]
    if not b:
        b = "Condition"
    if b not in taken:
        return b
    n = 2
    while n < 2000:
        suffix = f" ({n})"
        max_base = 255 - len(suffix)
        prefix = b[:max_base] if max_base > 0 else b[:200]
        candidate = f"{prefix}{suffix}"
        if candidate not in taken:
            return candidate
        n += 1
    raise AppException(
        code="NAME_COLLISION",
        message="Could not find a unique condition name for import",
        status_code=409,
    )
