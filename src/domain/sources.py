"""Domain models for MsSQL source management."""
from __future__ import annotations

from pydantic import BaseModel, Field


class SourceCreate(BaseModel):
    source_id: str = Field(..., min_length=1, max_length=255)
    display_name: str = Field(..., min_length=1, max_length=255)
    connection_string: str = Field(..., min_length=1, max_length=2000)
    allowed_tables: list[str] = []


class SourceResponse(BaseModel):
    source_id: str
    display_name: str
    connection_health: bool
    tables: list[str] = []
