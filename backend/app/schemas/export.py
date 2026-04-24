"""Export API schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


ExportFormat = Literal["xlsx", "pdf"]


class ExportRequest(BaseModel):
    format: ExportFormat = Field(description="Export file format")


class ExportQueuedResponse(BaseModel):
    task_id: str
    status: str = "pending"


class ExportStatusResponse(BaseModel):
    status: str
    error: str | None = None
    download_url: str | None = None
    filename: str | None = None
