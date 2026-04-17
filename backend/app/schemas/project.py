import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CreateProjectRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=5000)


class UpdateProjectRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=5000)
    status: str | None = Field(None, pattern=r"^(active|archived)$")


class ProjectResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    description: str | None
    status: str
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    #: Aggregated counts for dashboard cards (denormalized in the listing query, not persisted).
    sheet_count: int = 0
    member_count: int = 0


class ProjectListResponse(BaseModel):
    projects: list[ProjectResponse]
