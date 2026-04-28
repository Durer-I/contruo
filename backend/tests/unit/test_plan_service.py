"""Tests for plan_service validation logic (upload gate, retry gating).

Storage and DB interactions are mocked. The goal is to verify input validation
rules — the pieces most likely to cause production incidents.
"""

import sys
import types
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import plan_service
from app.middleware.error_handler import AppException


@pytest.fixture
def _stub_pdf_processing_module():
    """Inject a lightweight stub so dynamic `import app.tasks.pdf_processing` in
    retry_plan resolves without loading PyMuPDF/psycopg at import time.
    """
    existing = sys.modules.get("app.tasks.pdf_processing")
    stub = types.ModuleType("app.tasks.pdf_processing")
    stub.process_plan = MagicMock()
    stub.process_plan.delay = MagicMock()
    sys.modules["app.tasks.pdf_processing"] = stub
    try:
        yield stub
    finally:
        if existing is not None:
            sys.modules["app.tasks.pdf_processing"] = existing
        else:
            sys.modules.pop("app.tasks.pdf_processing", None)


@pytest.fixture
def mock_db():
    db = AsyncMock()
    return db


@pytest.fixture
def project_row():
    p = MagicMock()
    p.id = uuid.uuid4()
    p.org_id = uuid.uuid4()
    return p


@pytest.mark.anyio
async def test_create_plan_rejects_non_pdf_extension(mock_db, project_row):
    with pytest.raises(AppException) as ei:
        await plan_service.create_plan(
            mock_db,
            project_row.org_id,
            project_row.id,
            uuid.uuid4(),
            filename="drawing.dwg",
            content=b"%PDF-1.7\nstuff",
            content_type="application/pdf",
        )
    assert ei.value.code == "INVALID_FILE_TYPE"


@pytest.mark.anyio
async def test_create_plan_rejects_wrong_content_type(mock_db, project_row):
    with pytest.raises(AppException) as ei:
        await plan_service.create_plan(
            mock_db,
            project_row.org_id,
            project_row.id,
            uuid.uuid4(),
            filename="plan.pdf",
            content=b"%PDF-1.7\n",
            content_type="image/png",
        )
    assert ei.value.code == "INVALID_FILE_TYPE"


@pytest.mark.anyio
async def test_create_plan_rejects_empty(mock_db, project_row):
    with pytest.raises(AppException) as ei:
        await plan_service.create_plan(
            mock_db,
            project_row.org_id,
            project_row.id,
            uuid.uuid4(),
            filename="plan.pdf",
            content=b"",
            content_type="application/pdf",
        )
    assert ei.value.code == "EMPTY_FILE"


@pytest.mark.anyio
async def test_create_plan_rejects_too_large(mock_db, project_row):
    huge = b"%PDF-1.7\n" + b"x" * (plan_service.MAX_PLAN_FILE_SIZE + 1)
    with pytest.raises(AppException) as ei:
        await plan_service.create_plan(
            mock_db,
            project_row.org_id,
            project_row.id,
            uuid.uuid4(),
            filename="plan.pdf",
            content=huge,
            content_type="application/pdf",
        )
    assert ei.value.code == "FILE_TOO_LARGE"


@pytest.mark.anyio
async def test_create_plan_rejects_non_pdf_magic(mock_db, project_row):
    with pytest.raises(AppException) as ei:
        await plan_service.create_plan(
            mock_db,
            project_row.org_id,
            project_row.id,
            uuid.uuid4(),
            filename="plan.pdf",
            content=b"This is not a PDF",
            content_type="application/pdf",
        )
    assert ei.value.code == "INVALID_FILE_TYPE"


@pytest.mark.anyio
async def test_retry_plan_rejects_ready_status(mock_db):
    plan = MagicMock()
    plan.id = uuid.uuid4()
    plan.org_id = uuid.uuid4()
    plan.status = "ready"
    plan.project_id = uuid.uuid4()

    with patch(
        "app.services.plan_service.get_plan",
        new_callable=AsyncMock,
        return_value=plan,
    ):
        with pytest.raises(AppException) as ei:
            await plan_service.retry_plan(mock_db, plan.org_id, plan.id, uuid.uuid4())
        assert ei.value.code == "PLAN_NOT_RETRYABLE"


@pytest.mark.anyio
async def test_retry_plan_allowed_for_error_status(mock_db, _stub_pdf_processing_module):
    plan = MagicMock()
    plan.id = uuid.uuid4()
    plan.org_id = uuid.uuid4()
    plan.status = "error"
    plan.error_message = "something broke"
    plan.processed_pages = 0
    plan.project_id = uuid.uuid4()

    with (
        patch(
            "app.services.plan_service.get_plan",
            new_callable=AsyncMock,
            return_value=plan,
        ),
        patch("app.services.plan_service.log_event", new_callable=AsyncMock),
    ):
        result = await plan_service.retry_plan(mock_db, plan.org_id, plan.id, uuid.uuid4())
        assert result.status == "processing"
        _stub_pdf_processing_module.process_plan.delay.assert_called_once()


@pytest.mark.anyio
async def test_delete_plan_rejects_last_remaining_plan(mock_db):
    """Last plan in a project must not be deletable — it would orphan measurements/scale."""
    plan = MagicMock()
    plan.id = uuid.uuid4()
    plan.org_id = uuid.uuid4()
    plan.project_id = uuid.uuid4()
    plan.storage_path = "org/plans/plan/file.pdf"
    plan.filename = "plan.pdf"

    count_result = MagicMock()
    count_result.scalar_one = MagicMock(return_value=1)
    mock_db.execute = AsyncMock(return_value=count_result)

    with patch(
        "app.services.plan_service.get_plan",
        new_callable=AsyncMock,
        return_value=plan,
    ):
        with pytest.raises(AppException) as ei:
            await plan_service.delete_plan(
                mock_db, plan.org_id, plan.id, uuid.uuid4()
            )
    assert ei.value.code == "LAST_PLAN_REQUIRED"
    assert ei.value.status_code == 400


@pytest.mark.anyio
async def test_delete_plan_succeeds_when_other_plans_exist(mock_db):
    """With >1 plan, delete the row, log the event, and clean up storage paths."""
    plan = MagicMock()
    plan.id = uuid.uuid4()
    plan.org_id = uuid.uuid4()
    plan.project_id = uuid.uuid4()
    plan.storage_path = "org/plans/plan/file.pdf"
    plan.filename = "plan.pdf"

    count_result = MagicMock()
    count_result.scalar_one = MagicMock(return_value=2)
    thumb_result = MagicMock()
    thumb_result.all = MagicMock(
        return_value=[("org/plans/plan/thumbs/page-1.png",), (None,)]
    )
    delete_result = MagicMock()

    # execute is called: (1) count remaining plans, (2) load thumbnail paths, (3) DELETE row.
    mock_db.execute = AsyncMock(
        side_effect=[count_result, thumb_result, delete_result]
    )
    mock_db.flush = AsyncMock()

    with (
        patch(
            "app.services.plan_service.get_plan",
            new_callable=AsyncMock,
            return_value=plan,
        ),
        patch("app.services.plan_service.log_event", new_callable=AsyncMock) as log_mock,
        patch("app.services.plan_service.storage.remove_files") as remove_mock,
    ):
        await plan_service.delete_plan(mock_db, plan.org_id, plan.id, uuid.uuid4())

    assert mock_db.execute.await_count == 3
    log_mock.assert_awaited_once()
    # PDF + thumbnails are both cleaned up; the None thumbnail is filtered out.
    paths_removed = {call.args[0]: call.args[1] for call in remove_mock.call_args_list}
    assert paths_removed["plans"] == ["org/plans/plan/file.pdf"]
    assert paths_removed["plan-thumbnails"] == ["org/plans/plan/thumbs/page-1.png"]
