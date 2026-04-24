"""Linear deduction polylines reduce net PDF length (Sprint 15)."""

from app.services.measurement_service import _linear_net_pdf_length, _parse_linear_deductions


def test_net_length_subtracts_deduction_polylines() -> None:
    verts = [{"x": 0.0, "y": 0.0}, {"x": 10.0, "y": 0.0}]
    deductions = [[{"x": 2.0, "y": 0.0}, {"x": 4.0, "y": 0.0}]]
    assert _linear_net_pdf_length(verts, deductions) == 8.0


def test_net_length_never_negative() -> None:
    verts = [{"x": 0.0, "y": 0.0}, {"x": 1.0, "y": 0.0}]
    deductions = [[{"x": 0.0, "y": 0.0}, {"x": 100.0, "y": 0.0}]]
    assert _linear_net_pdf_length(verts, deductions) == 0.0


def test_parse_deductions_accepts_vertex_objects() -> None:
    raw = [{"vertices": [{"x": 0, "y": 0}, {"x": 1, "y": 1}]}]
    rings = _parse_linear_deductions(raw)
    assert len(rings) == 1
    assert len(rings[0]) == 2
    assert rings[0][0]["x"] == 0.0
