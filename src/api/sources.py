"""Source routes: register IT-provisioned MsSQL sources."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api._common import api_error, ok
from src.db.models import AuditLog, Session as SessionRow
from src.db.session import get_session, init_db
from src.domain.sources import SourceCreate, SourceResponse
from src.observability.events import get_logger

router = APIRouter()


@router.post("/sources")
def create_source(req: SourceCreate, session: Session = Depends(get_session)) -> dict:
    init_db()
    source = SessionRow(
        user_id="local",
        source_type="mssql",
        source_config=req.model_dump_json(),
    )
    session.add(source)
    session.flush()
    session.add(
        AuditLog(
            action="source_create",
            target=source.id,
            metadata_json=f'{{"source_id": "{req.source_id}"}}',
        )
    )
    session.commit()
    return ok(
        SourceResponse(source_id=req.source_id, display_name=req.display_name, connection_health=True).model_dump()
    )


@router.get("/sources")
def list_sources(session: Session = Depends(get_session)) -> dict:
    init_db()
    rows = session.query(SessionRow).filter(SessionRow.source_type == "mssql").all()
    out = []
    for row in rows:
        try:
            cfg = SourceCreate.model_validate_json(row.source_config or "{}")
            out.append(
                SourceResponse(
                    source_id=cfg.source_id,
                    display_name=cfg.display_name,
                    connection_health=True,
                    tables=cfg.allowed_tables,
                ).model_dump()
            )
        except Exception:
            continue
    return ok({"items": out, "count": len(out)})
