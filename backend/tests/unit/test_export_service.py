"""Unit tests for quantities export builders."""

from datetime import datetime, timezone

from app.services.export_service import (
    ExportBundle,
    ExportConditionBlock,
    ExportMeasurementRow,
    ExportSheetBlock,
    build_pdf_bytes,
    build_xlsx_bytes,
)


def test_build_xlsx_and_pdf_minimal_tree():
    b = ExportBundle(
        project_name="Demo Project",
        exported_at=datetime.now(timezone.utc),
        condition_count=1,
        measurement_count=1,
        sheet_count=1,
        blocks=[
            ExportConditionBlock(
                condition_name="Wall",
                grand_total_display="100",
                unit="LF",
                sheets=[
                    ExportSheetBlock(
                        sheet_name="A1",
                        subtotal_display="100",
                        unit="LF",
                        measurements=[
                            ExportMeasurementRow(label="Run 1", quantity="100 (95.00)", unit="LF"),
                        ],
                    )
                ],
            )
        ],
        naive_numeric_sum=100.0,
    )
    xlsx = build_xlsx_bytes(b)
    assert xlsx[:2] == b"PK"
    pdf = build_pdf_bytes(b)
    assert pdf[:4] == b"%PDF"
