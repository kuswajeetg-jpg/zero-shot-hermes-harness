"""Health check — reports which provider is active (presence only, never keys)."""
from __future__ import annotations

from fastapi import APIRouter

from src.api._common import ok
from src.config.settings import get_settings

router = APIRouter()


@router.get("/health")
def health() -> dict:
    s = get_settings()
    provider = s.resolve_provider()
    return ok(
        {
            "status": "ok",
            "provider": provider,
            "model": s.resolve_model(),
            "key_configured": provider != "stub",
        }
    )
