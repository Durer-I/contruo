"""Sprint AI-02: lexical + vision-fallback sheet classifier."""

from __future__ import annotations

import io
import uuid
from unittest.mock import MagicMock

import pytest
from PIL import Image

from app.services import ai_sheet_classifier


def _png(width: int = 16, height: int = 16, color=(255, 255, 255)) -> bytes:
    img = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ── Lexical pass ───────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "name,expected_disc,expected_type",
    [
        ("A-101 Floor Plan", "architectural", "plan"),
        ("A101 Floor Plan", "architectural", "plan"),
        ("M-201 Mechanical Schedule", "mechanical", "schedule"),
        ("E-501 Electrical Details", "electrical", "detail"),
        ("S-301 Foundation Section", "structural", "section"),
        ("P-101 Plumbing Plan", "plumbing", "plan"),
        ("G-001 Cover Sheet", "general", "cover"),
        ("Some random text", "other", "other"),
    ],
)
def test_classify_lexical_basic_combinations(name, expected_disc, expected_type):
    sheet_id = uuid.uuid4()
    r = ai_sheet_classifier.classify_lexical(sheet_id, name)
    assert r.discipline == expected_disc
    assert r.sheet_type == expected_type
    assert r.method == "lexical"


def test_classify_lexical_high_confidence_when_prefix_and_keyword_match():
    r = ai_sheet_classifier.classify_lexical(uuid.uuid4(), "M-501 Mechanical Schedule")
    assert r.confidence >= 0.9


def test_classify_lexical_low_confidence_with_no_signal():
    r = ai_sheet_classifier.classify_lexical(uuid.uuid4(), None)
    assert r.discipline == "other"
    assert r.sheet_type == "other"
    assert r.confidence < 0.5


def test_needs_vision_fallback_skips_uninteresting_types():
    """D6 optimization: cover/index/spec sheets never escalate to vision."""
    cover = ai_sheet_classifier.ClassificationResult(
        sheet_id=uuid.uuid4(),
        discipline="general",
        sheet_type="cover",
        confidence=0.3,  # well below threshold
        method="lexical",
    )
    assert ai_sheet_classifier.needs_vision_fallback(cover, threshold=0.7) is False


def test_needs_vision_fallback_escalates_low_confidence_plan_sheet():
    plan = ai_sheet_classifier.ClassificationResult(
        sheet_id=uuid.uuid4(),
        discipline="other",
        sheet_type="other",
        confidence=0.2,
        method="lexical",
    )
    assert ai_sheet_classifier.needs_vision_fallback(plan, threshold=0.7) is True


def test_needs_vision_fallback_skips_high_confidence_results():
    plan = ai_sheet_classifier.ClassificationResult(
        sheet_id=uuid.uuid4(),
        discipline="architectural",
        sheet_type="plan",
        confidence=0.9,
        method="lexical",
    )
    assert ai_sheet_classifier.needs_vision_fallback(plan, threshold=0.7) is False


# ── Vision-fallback batch dispatch ─────────────────────────────────────────


def test_classify_vision_batch_calls_model_in_groups_of_batch_size():
    sheet_inputs = [
        ai_sheet_classifier.SheetForClassification(
            sheet_id=uuid.uuid4(),
            sheet_name=f"X-{i}",
            content_hash=f"h{i}",
            thumbnail_png=_png(),
        )
        for i in range(7)  # 7 sheets, batch_size=3 -> 3 calls
    ]

    vision_model = MagicMock()
    # Each call returns N entries with index in batch order.
    def _resp(_image_bytes, *, schema):
        n = schema["properties"]["sheets"]["minItems"]
        return {
            "sheets": [
                {
                    "index": i,
                    "discipline": "architectural",
                    "sheet_type": "plan",
                    "confidence": 0.85,
                }
                for i in range(n)
            ]
        }

    vision_model.classify_image.side_effect = _resp

    out = ai_sheet_classifier.classify_vision_batch(
        sheet_inputs,
        vision_model=vision_model,
        batch_size=3,
    )

    assert vision_model.classify_image.call_count == 3  # ceil(7/3)
    assert len(out) == 7
    assert all(r.method == "vision" for r in out)
    assert all(r.discipline == "architectural" for r in out)


def test_classify_vision_batch_falls_back_to_lexical_on_model_error():
    sheet_id = uuid.uuid4()
    lexical_fb = ai_sheet_classifier.ClassificationResult(
        sheet_id=sheet_id,
        discipline="electrical",
        sheet_type="diagram",
        confidence=0.6,
        method="lexical",
    )
    vision_model = MagicMock()
    vision_model.classify_image.side_effect = RuntimeError("anthropic 500")

    out = ai_sheet_classifier.classify_vision_batch(
        [
            ai_sheet_classifier.SheetForClassification(
                sheet_id=sheet_id,
                sheet_name="ambiguous",
                content_hash="h",
                thumbnail_png=_png(),
            )
        ],
        vision_model=vision_model,
        batch_size=6,
        lexical_by_id={sheet_id: lexical_fb},
    )

    assert len(out) == 1
    # Falls back cleanly to the supplied lexical guess.
    assert out[0].discipline == "electrical"
    assert out[0].sheet_type == "diagram"


def test_classify_vision_batch_skips_sheets_without_thumbnails():
    out = ai_sheet_classifier.classify_vision_batch(
        [
            ai_sheet_classifier.SheetForClassification(
                sheet_id=uuid.uuid4(),
                sheet_name="no-thumb",
                content_hash="h",
                thumbnail_png=None,  # explicitly missing
            )
        ],
        vision_model=MagicMock(),
        batch_size=6,
    )
    assert out == []


# ── bulk_upsert_classifications: SQL bind safety ──────────────────────────


def test_bulk_upsert_compiles_and_executes_with_payload_bind():
    """Regression: ``:payload::jsonb`` confused SQLAlchemy's ``text()`` parser
    and raised ``ArgumentError: This text() construct doesn't define a bound
    parameter named 'payload'`` whenever Stage 2 tried to write back results.

    The fix uses ANSI ``CAST(:payload AS jsonb)``. This test asserts:
      1. ``bulk_upsert_classifications`` does not raise.
      2. ``session.execute`` receives a single positional ``text`` clause + a
         ``{"payload": <json string>}`` mapping that round-trips through
         ``json.loads``.
    """
    import json

    rows = [
        ai_sheet_classifier.ClassificationResult(
            sheet_id=uuid.uuid4(),
            discipline="architectural",
            sheet_type="plan",
            confidence=0.92,
            method="lexical",
        ),
        ai_sheet_classifier.ClassificationResult(
            sheet_id=uuid.uuid4(),
            discipline="mechanical",
            sheet_type="schedule",
            confidence=0.55,
            method="vision",
        ),
    ]

    session = MagicMock()
    fake_result = MagicMock()
    fake_result.rowcount = 2
    session.execute.return_value = fake_result

    written = ai_sheet_classifier.bulk_upsert_classifications(session, rows)
    assert written == 2

    assert session.execute.called
    args, _ = session.execute.call_args
    stmt, params = args[0], args[1]
    # The statement compiles with the bind already attached -- compiling here
    # ensures no ``ArgumentError`` slips through into runtime.
    str(stmt.compile())
    assert "payload" in params
    decoded = json.loads(params["payload"])
    assert isinstance(decoded, list) and len(decoded) == 2
    assert {row["discipline"] for row in decoded} == {"architectural", "mechanical"}


def test_bulk_upsert_classifications_no_op_on_empty_input():
    session = MagicMock()
    written = ai_sheet_classifier.bulk_upsert_classifications(session, [])
    assert written == 0
    session.execute.assert_not_called()


# ── Aggregation counters ──────────────────────────────────────────────────


def test_classification_counters_aggregate_correctly():
    counters = ai_sheet_classifier.ClassificationCounters()
    rows = [
        ai_sheet_classifier.ClassificationResult(
            sheet_id=uuid.uuid4(),
            discipline="architectural",
            sheet_type="plan",
            confidence=0.95,
            method="lexical",
        ),
        ai_sheet_classifier.ClassificationResult(
            sheet_id=uuid.uuid4(),
            discipline="mechanical",
            sheet_type="schedule",
            confidence=0.55,
            method="vision",
        ),
        ai_sheet_classifier.ClassificationResult(
            sheet_id=uuid.uuid4(),
            discipline="architectural",
            sheet_type="elevation",
            confidence=0.75,
            method="lexical",
        ),
    ]
    for r in rows:
        counters.add(r, low_threshold=0.7)

    summary = counters.as_summary()
    assert summary["total"] == 3
    assert summary["lexical_count"] == 2
    assert summary["vision_count"] == 1
    assert summary["low_confidence_count"] == 1
    assert summary["by_discipline"]["architectural"] == 2
    assert summary["by_type"]["plan"] == 1
