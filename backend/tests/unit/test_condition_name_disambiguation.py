import pytest

from app.middleware.error_handler import AppException
from app.utils.condition_name_disambiguation import disambiguate_condition_name


def test_returns_base_when_free():
    assert disambiguate_condition_name("Wall A", {"Other"}) == "Wall A"


def test_appends_suffix_when_base_taken():
    taken = {"Wall A"}
    assert disambiguate_condition_name("Wall A", taken) == "Wall A (2)"


def test_increments_suffix():
    taken = {"Wall A", "Wall A (2)", "Wall A (3)"}
    assert disambiguate_condition_name("Wall A", taken) == "Wall A (4)"


def test_empty_base_uses_condition():
    assert disambiguate_condition_name("", set()) == "Condition"
    assert disambiguate_condition_name("   ", {"Condition"}) == "Condition (2)"


def test_truncates_long_base_with_suffix():
    base = "W" * 250
    taken = {base}
    out = disambiguate_condition_name(base, taken)
    assert out.endswith(" (2)")
    assert len(out) <= 255
    assert out not in taken


def test_raises_when_no_slot(monkeypatch):
    """If every candidate is taken, eventually raises."""
    taken = {f"X ({i})" for i in range(2, 2000)} | {"X"}
    with pytest.raises(AppException) as exc:
        disambiguate_condition_name("X", taken)
    assert exc.value.code == "NAME_COLLISION"
