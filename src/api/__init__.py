"""FastAPI app factory + lifespan. Serves the static frontend at /app."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

_FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "public"


@asynccontextmanager
async def _lifespan(app: FastAPI):
    from src.config.settings import get_settings
    from src.db.session import init_db
    from src.observability.events import configure_logging

    configure_logging(get_settings().log_level)
    init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="UP Police Analyst", version="0.2.0", lifespan=_lifespan)

    from src.api import health, runs, auth, analyst, sources, merge
    from src.api import analyst_report, query_history, feedback
    from src.config.settings import get_settings

    api_router = APIRouter(prefix="/api")
    api_router.include_router(health.router)
    api_router.include_router(runs.router)
    api_router.include_router(auth.router)
    api_router.include_router(analyst.router)
    api_router.include_router(sources.router)
    api_router.include_router(merge.router)
    api_router.include_router(analyst_report.router, prefix="/analyst")
    api_router.include_router(query_history.router, prefix="/analyst")
    api_router.include_router(feedback.router, prefix="/analyst")
    app.include_router(api_router)

    app.include_router(health.router)
    app.include_router(runs.router)
    app.include_router(auth.router)
    app.include_router(analyst.router)
    app.include_router(sources.router)
    app.include_router(merge.router)
    app.include_router(analyst_report.router, prefix="/analyst")
    app.include_router(query_history.router, prefix="/analyst")
    app.include_router(feedback.router, prefix="/analyst")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().allowed_origins if hasattr(get_settings(), "allowed_origins") else ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if _FRONTEND_DIR.is_dir():
        app.mount("/app", StaticFiles(directory=_FRONTEND_DIR, html=True), name="frontend")

    return app


app = create_app()
