import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class AssemblyItemResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    condition_id: uuid.UUID
    parent_id: uuid.UUID | None
    name: str
    unit: str
    formula: str
    description: str | None
    sort_order: int
    created_at: datetime
    updated_at: datetime


class AssemblyItemListResponse(BaseModel):
    items: list[AssemblyItemResponse]


class CreateAssemblyItemRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    unit: str = Field(..., min_length=1, max_length=20)
    formula: str = Field(..., min_length=1)
    description: str | None = Field(default=None, max_length=2000)
    sort_order: int | None = Field(default=None, ge=0)


class UpdateAssemblyItemRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    unit: str | None = Field(default=None, min_length=1, max_length=20)
    formula: str | None = Field(default=None, min_length=1)
    description: str | None = Field(default=None, max_length=2000)
    sort_order: int | None = Field(default=None, ge=0)


class ConditionTemplateResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    measurement_type: str
    unit: str
    color: str
    line_style: str
    line_width: float
    fill_opacity: float
    fill_pattern: str
    properties: dict
    trade: str | None
    description: str | None
    assembly_item_count: int = 0
    created_at: datetime
    updated_at: datetime


class ConditionTemplateListResponse(BaseModel):
    templates: list[ConditionTemplateResponse]


class SaveConditionAsTemplateRequest(BaseModel):
    name: str | None = Field(
        default=None,
        max_length=255,
        description="Template name; defaults to the condition name",
    )


class ImportConditionTemplateRequest(BaseModel):
    template_id: uuid.UUID


class PreviewAssemblyFormulaRequest(BaseModel):
    formula: str = Field(..., min_length=1)
    sample_primary: float = Field(default=100.0, description="Sample length / area / count value")
    sample_perimeter: float = Field(
        default=0.0,
        description="Sample perimeter (real units) for area conditions",
    )


class PreviewAssemblyFormulaResponse(BaseModel):
    value: float | None = None
    error: str | None = None
