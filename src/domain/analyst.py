"""Domain models for analyst backend slice and auth."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AuthRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"


class AuthorizationResponse(BaseModel):
    user_id: str
    email: str
    role: str
    access_token: str


class CurrentUserResponse(BaseModel):
    user_id: str
    email: str


class SessionResponse(BaseModel):
    session_token: str
    schema_info: list[dict[str, str]] = Field(default=[], alias="schema")
    sources: list[dict[str, str]] = []
    files: list[dict[str, str]] = []


class UploadRequest(BaseModel):
    session_token: str = "default_session"
    user_id: str = "local"
    file_name: str = Field(..., max_length=255)
    file_data: bytes


class UploadResponse(BaseModel):
    upload_id: str
    filename: str
    schema_info: list[dict[str, Any]] = Field(..., alias="schema")
    rows: int
    suggested_questions: list[str] = []
    executive_briefing: Any = None
    conversation_prompt: str | None = None

    model_config = {"populate_by_name": True}


class AskRequest(BaseModel):
    session_token: str = "default_session"
    source_id: str = "default_source"
    question: str
    user_id: str = "local"


class AskResponse(BaseModel):
    run_id: str = Field(..., alias="run_id")
    answer_text: str | None = Field(None)
    query_result: dict[str, Any] | None = Field(None)
    chart_spec: dict[str, Any] | None = Field(None)
    advisor: dict[str, Any] | None = Field(None)
    fallback_mode: bool = Field(False)
    latency_ms: int | None = Field(None)
    status: str | None = Field(None)
    provider: str | None = Field(None)
    model: str | None = Field(None)
    error: str | None = Field(None)
    checkpoint: str | None = Field(None)

    model_config = {"populate_by_name": True}


AskResponse.model_rebuild()

class ChartRecommendationRequest(BaseModel):
    columns: list[str]
    question: str


class ChartRecommendationResponse(BaseModel):
    chart_type: str
    encoding: dict[str, Any]


class ExportRequest(BaseModel):
    query_run_id: str
    format: str = "csv"
    user_id: str


class ExportResponse(BaseModel):
    export_id: str
    url: str
    expires_at: str
