
from fastapi import APIRouter
from src.api.auth import router as auth_router
from src.api.analyst import router as analyst_router
from src.api.analyst_report import router as analyst_report_router
from src.api.query_history import router as query_history_router
from src.api.feedback import router as feedback_router

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok", "project": "UP_Police_Data_Agent"}

router.include_router(auth_router, prefix="/auth", tags=["Auth"])
router.include_router(analyst_router, prefix="/analyst", tags=["Analyst"])
router.include_router(analyst_report_router, prefix="/analyst", tags=["Analyst"])
router.include_router(query_history_router, prefix="/analyst", tags=["Analyst"])
router.include_router(feedback_router, prefix="/analyst", tags=["Feedback"])

