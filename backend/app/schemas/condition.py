import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


MeasurementType = Literal["linear", "area", "count"]
LineStyle = Literal["solid", "dashed", "dotted"]
FillPattern = Literal["solid", "hatch", "crosshatch"]


class CustomPropertyItem(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    value: str = Field(default="", max_length=500)
    unit: str = Field(default="", max_length=50)


class ConditionPropertiesPayload(BaseModel):
    """Stored in `conditions.properties` JSONB."""

    custom: list[CustomPropertyItem] = Field(default_factory=list)


class ConditionBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    measurement_type: MeasurementType
    unit: str = Field(..., min_length=1, max_length=20)
    color: str = Field(..., pattern=r"^#[0-9A-Fa-f]{6}$")
    line_style: LineStyle = "solid"
    line_width: float = Field(default=2.0, ge=0.5, le=16.0)
    fill_opacity: float = Field(default=0.3, ge=0.0, le=1.0)
    fill_pattern: FillPattern = "solid"
    properties: ConditionPropertiesPayload = Field(default_factory=ConditionPropertiesPayload)
    trade: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=10_000)
    notes: str | None = Field(default=None, max_length=10_000)


class CreateConditionRequest(ConditionBase):
    pass


class UpdateConditionRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    measurement_type: MeasurementType | None = None
    unit: str | None = Field(default=None, min_length=1, max_length=20)
    color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    line_style: LineStyle | None = None
    line_width: float | None = Field(default=None, ge=0.5, le=16.0)
    fill_opacity: float | None = Field(default=None, ge=0.0, le=1.0)
    fill_pattern: FillPattern | None = None
    properties: ConditionPropertiesPayload | None = None
    trade: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=10_000)
    notes: str | None = Field(default=None, max_length=10_000)
    sort_order: int | None = Field(default=None, ge=0)


class ConditionResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    project_id: uuid.UUID
    name: str
    measurement_type: str
    unit: str
    color: str
    line_style: str
    line_width: float
    fill_opacity: float
    fill_pattern: str
    properties: ConditionPropertiesPayload
    trade: str | None
    description: str | None
    notes: str | None
    sort_order: int
    measurement_count: int = 0
    total_quantity: float = 0.0
    created_at: datetime
    updated_at: datetime


class ConditionListResponse(BaseModel):
    conditions: list[ConditionResponse]
