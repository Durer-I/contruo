import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


MeasurementType = Literal["linear", "area", "count"]


class LinearGeometry(BaseModel):
    type: Literal["linear"] = "linear"
    vertices: list[dict[str, float]] = Field(..., min_length=2)

    @field_validator("vertices")
    @classmethod
    def vertex_keys(cls, v: list[dict[str, float]]) -> list[dict[str, float]]:
        for p in v:
            if "x" not in p or "y" not in p:
                raise ValueError("each vertex must have x and y")
        return v


class CreateMeasurementRequest(BaseModel):
    sheet_id: uuid.UUID
    condition_id: uuid.UUID
    measurement_type: MeasurementType = "linear"
    geometry: dict[str, Any]
    label: str | None = Field(default=None, max_length=255)
    override_value: float | None = None
    #: Linear only: list of ``{"vertices": [{x,y}, ...]}`` polylines subtracted from gross length.
    deductions: list[dict[str, Any]] = Field(default_factory=list)


class UpdateMeasurementRequest(BaseModel):
    geometry: dict[str, Any] | None = None
    condition_id: uuid.UUID | None = None
    label: str | None = Field(default=None, max_length=255)
    override_value: float | None = None
    deductions: list[dict[str, Any]] | None = None


class DerivedQuantityItem(BaseModel):
    assembly_item_id: uuid.UUID
    name: str
    unit: str
    value: float | None = None
    error: str | None = None


class MeasurementResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    project_id: uuid.UUID
    sheet_id: uuid.UUID
    condition_id: uuid.UUID
    measurement_type: str
    geometry: dict[str, Any]
    measured_value: float
    override_value: float | None
    label: str | None
    created_by: uuid.UUID
    #: Optimistic-lock counter; clients pass it back via ``If-Match`` on PATCH.
    version: int = 1
    created_at: datetime
    updated_at: datetime
    derived_quantities: list[DerivedQuantityItem] = Field(default_factory=list)
    deductions: list[dict[str, Any]] = Field(default_factory=list)
    #: Linear: full path length before deductions (same unit as ``measured_value``). Omitted for non-linear.
    gross_measured_value: float | None = None


class MeasurementConditionAggregate(BaseModel):
    condition_id: uuid.UUID
    measurement_type: str
    row_count: int
    sum_measured_value: float


class MeasurementAggregates(BaseModel):
    """Per-sheet and project-wide sums when ``include_aggregates`` is requested."""

    sheet_by_condition: list[MeasurementConditionAggregate] = Field(default_factory=list)
    project_by_condition: list[MeasurementConditionAggregate] = Field(default_factory=list)


class MeasurementListResponse(BaseModel):
    measurements: list[MeasurementResponse]
    aggregates: MeasurementAggregates | None = None
    #: Opaque cursor (ISO timestamp + id) clients pass back as ``cursor`` to fetch
    #: the next page. ``None`` when this page completed the list.
    next_cursor: str | None = None
