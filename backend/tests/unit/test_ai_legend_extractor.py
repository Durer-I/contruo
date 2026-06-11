"""Legend extractor persistence + cache fast-path (Sprint AI-03).

We don't render real PDF crops in unit tests -- the crop function and the
PIL transforms are exercised via integration tests later. Here we mock the
fitz page + storage helpers and verify:

* The primary upload + DB row write happens once per candidate.
* Only the primary template is uploaded (no variant grid).
* ``persist_from_cached_metadata`` writes DB rows from cached entries
  without invoking the storage uploader.
"""

from __future__ import annotations

import io
import uuid
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from app.config import get_settings
from app.services import ai_legend_extractor as le
from app.services.ai_legend_detector import LegendCandidate


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _make_png(width: int = 32, height: int = 32) -> bytes:
    img = Image.new("RGB", (width, height), color=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class _FakeFitzPage:
    pass


def test_persist_legend_candidates_uploads_primary_only():
    candidate = LegendCandidate(
        bbox_pdf={"x0": 100, "y0": 100, "x1": 132, "y1": 132},
        label="AC-1",
        extraction_method="pdfplumber_rects_label_right",
        confidence=0.85,
        sibling_count=3,
    )

    db = MagicMock()
    # Mock id so persist code paths that need legend.id work.
    def _refresh(obj):
        if not getattr(obj, "id", None):
            obj.id = uuid.uuid4()
    db.refresh.side_effect = _refresh

    primary_png = _make_png()
    with (
        patch.object(le, "_render_primary_png", return_value=primary_png),
        patch.object(le, "upload_bytes") as upload,
    ):
        persisted = le.persist_legend_candidates(
            db=db,
            fitz_page=_FakeFitzPage(),
            candidates=[candidate],
            org_id=uuid.uuid4(),
            plan_id=uuid.uuid4(),
            sheet_id=uuid.uuid4(),
            ai_run_id=uuid.uuid4(),
        )

    assert len(persisted) == 1
    assert persisted[0].label == "AC-1"
    assert persisted[0].variant_count == 0
    assert upload.call_count == 1


def test_persist_skips_duplicate_hashes_within_sheet():
    candidate = LegendCandidate(
        bbox_pdf={"x0": 0, "y0": 0, "x1": 32, "y1": 32},
        label="AC-1",
        extraction_method="pdfplumber_rects_label_right",
        confidence=0.85,
    )
    primary_png = _make_png()
    db = MagicMock()
    def _refresh(obj):
        if not getattr(obj, "id", None):
            obj.id = uuid.uuid4()
    db.refresh.side_effect = _refresh
    with (
        patch.object(le, "_render_primary_png", return_value=primary_png),
        patch.object(le, "upload_bytes"),
    ):
        persisted = le.persist_legend_candidates(
            db=db,
            fitz_page=_FakeFitzPage(),
            candidates=[candidate, candidate, candidate],
            org_id=uuid.uuid4(),
            plan_id=uuid.uuid4(),
            sheet_id=uuid.uuid4(),
            ai_run_id=uuid.uuid4(),
        )
    # Same image bytes -> same hash -> only one persisted row.
    assert len(persisted) == 1


def test_persist_from_cached_metadata_skips_uploads():
    db = MagicMock()
    def _refresh(obj):
        if not getattr(obj, "id", None):
            obj.id = uuid.uuid4()
    db.refresh.side_effect = _refresh
    cached = [
        {
            "label": "AC-1",
            "template_hash": "a" * 64,
            "primary_storage_path": "org/legends/plan/aaaa_s1.00_r000.png",
            "variant_count": 0,
            "confidence": 0.85,
            "bbox_pdf": {"x0": 0, "y0": 0, "x1": 32, "y1": 32},
            "extraction_method": "pdfplumber_rects_label_right",
            "notes": {},
        }
    ]
    with patch.object(le, "upload_bytes") as upload:
        persisted = le.persist_from_cached_metadata(
            db=db,
            cached=cached,
            org_id=uuid.uuid4(),
            plan_id=uuid.uuid4(),
            sheet_id=uuid.uuid4(),
            ai_run_id=uuid.uuid4(),
        )

    assert len(persisted) == 1
    assert persisted[0].label == "AC-1"
    assert persisted[0].variant_count == 0
    upload.assert_not_called()


def test_persist_from_cached_metadata_skips_invalid_entries():
    db = MagicMock()
    cached = [
        {"label": "", "template_hash": "x", "primary_storage_path": "p"},
        {"label": "valid", "template_hash": "", "primary_storage_path": "p"},
        {"label": "valid", "template_hash": "x", "primary_storage_path": ""},
    ]
    with patch.object(le, "upload_bytes"):
        persisted = le.persist_from_cached_metadata(
            db=db,
            cached=cached,
            org_id=uuid.uuid4(),
            plan_id=uuid.uuid4(),
            sheet_id=uuid.uuid4(),
            ai_run_id=uuid.uuid4(),
        )
    assert persisted == []
