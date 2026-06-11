"""Storage helpers for legend symbol PNGs.

Centralized so the variant-grid layout (5 scales x 4 rotations) can be
adjusted in one place; ``ai_legend_extractor`` only sees logical paths.

Path convention (mirrors ``plan_storage_path`` style):

    {org_id}/legends/{plan_id}/{template_hash}_s{scale}_r{rotation}.png

Why hash-based filenames:

* Re-runs of an unchanged sheet produce bit-identical PNGs -> identical
  hashes -> overwrite the same path -> zero orphan growth in the bucket.
* AI-04 / AI-06 looking up "the template for this hash" doesn't need the
  database; the storage path is fully recoverable from the hash + scale +
  rotation. (We still write the path to the DB row for the common-case
  query, but the deterministic mapping is a useful invariant.)

Scales are numerics in the DB (``Numeric(3,2)``) but render as floats here;
the ``f"{scale:.2f}"`` format keeps "1.00" / "0.70" stable across runs so
hashing/equality tests don't flake on representation.
"""
from __future__ import annotations

import hashlib
import re
import uuid


LEGENDS_PREFIX = "legends"


def compute_template_hash(image_bytes: bytes) -> str:
    """SHA-256 of the *primary* (1.00x, 0deg) PNG bytes.

    The hash is derived from the primary variant only -- not from the cropped
    PDF region -- because two visually identical legend symbols on different
    sheets are intentionally collapsed to the same hash so AI-06 can re-use
    matched templates across the project. If we hashed the raw rect bbox
    every sheet would generate a fresh hash even for shared standard
    symbols.

    SHA-256 is overkill for collisions but cheap and matches the
    ``ai_stage_cache.content_hash`` convention.
    """
    return hashlib.sha256(image_bytes).hexdigest()


def variant_filename(*, template_hash: str, scale: float, rotation: int) -> str:
    """Return the deterministic basename for a (hash, scale, rotation) variant."""
    return f"{template_hash}_s{scale:.2f}_r{rotation:03d}.png"


def variant_storage_path(
    org_id: uuid.UUID,
    plan_id: uuid.UUID,
    *,
    template_hash: str,
    scale: float,
    rotation: int,
) -> str:
    """Canonical org-scoped Supabase Storage path for one variant PNG.

    Lives under the same ``{org_id}/...`` prefix as plan PDFs so a single
    org-delete cascade catches everything.
    """
    filename = variant_filename(
        template_hash=template_hash, scale=scale, rotation=rotation
    )
    return f"{org_id}/{LEGENDS_PREFIX}/{plan_id}/{filename}"


_SAFE_LABEL = re.compile(r"[^A-Za-z0-9._-]+")


def safe_label_slug(label: str, *, max_len: int = 40) -> str:
    """Convert a free-form legend label into a filename-safe slug.

    Not used in the canonical storage path (we hash for that), but useful
    for debug exports / internal admin pages that want a human-readable
    filename. Empty / whitespace-only labels collapse to ``"unlabeled"``
    so the caller can still produce a stable filename.
    """
    cleaned = _SAFE_LABEL.sub("_", (label or "").strip())
    cleaned = cleaned.strip("._-")
    if not cleaned:
        return "unlabeled"
    return cleaned[:max_len]
