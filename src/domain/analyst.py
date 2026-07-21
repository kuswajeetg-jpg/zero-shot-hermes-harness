"""Domain models for analyst backend slice and auth."""
from __future__ import annotations

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
    access_token: str


class CurrentUserResponse(BaseModel):
    user_id: str
    email: str


class SessionResponse(BaseModel):
    session_token: str
    schema: list[dict[str, str]] = []
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
    schema: list[dict[str, str]]
    rows: int


class AskRequest(BaseModel):
    session_token: str = "default_session"
    source_id: str = "default_source"
    question: str
    user_id: str = "local"


class AskResponse(BaseModel):
    run_id: str
    answer_text: str | None = None
    query_result: dict | list | None = None
    chart_spec: dict | None = None
    fallback_mode: bool = False
    latency_ms: int | None = None
    status: str | None = "completed"


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
