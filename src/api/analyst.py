"""Analyst routes: upload, ask, export."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from src.api._common import api_error, ok
from src.config.settings import get_settings
from src.db.models import AuditLog, Export, QueryRun, Upload
from src.db.session import get_session, init_db
from src.domain.analyst import (
    AskRequest,
    AskResponse,
    ExportRequest,
    ExportResponse,
    UploadResponse,
)
from src.graph.analyst_runner import run_analyst
from src.ingest.csv import ingest_file_bytes
from src.observability.events import get_logger

router = APIRouter()


def _export_dir() -> Path:
    p = Path(get_settings().export_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p


@router.post("/upload", response_model=None)
def upload_csv(
    file: UploadFile = File(...),
    session_token: str = Form(...),
    session: Session = Depends(get_session),
) -> dict:
    init_db()
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise api_error("bad_upload", "Only .csv uploads are supported", 422)
    try:
        data = file.file.read()
    finally:
        file.file.close()
    if len(data) > 100 * 1024 * 1024:
        raise api_error("too_large", "File too large. Max 100MB.", 422)
    parsed = ingest_file_bytes(data, file.filename)
    upload = Upload(
        session_id=session_token,
        filename=parsed["filename"],
        schema_json=str(parsed["schema"]),
        rows=parsed["rows"],
    )
    session.add(upload)
    session.flush()
    filename = parsed["filename"]
    metadata_json = (
        '{"rows": '
        + str(parsed["rows"])
        + ', "filename": "'
        + filename.replace('"', '\\"')
        + '"}'
    )
    session.add(
        AuditLog(
            action="upload",
            target=upload.id,
            metadata_json=metadata_json,
        )
    )
    session.commit()
    return ok(UploadResponse(upload_id=upload.id, **parsed).model_dump())


@router.post("/ask", response_model=None)
def ask(req: AskRequest, session: Session = Depends(get_session)) -> dict:
    init_db()
    if not req.question or not req.question.strip():
        raise api_error("empty_question", "Question cannot be empty.", 422)

    start = __import__("time").perf_counter()
    result = run_analyst(
        user_id="local",
        session_token=req.session_token,
        source_id=req.source_id,
        user_message=req.question,
        schema=[],
    )
    latency = int((__import__("time").perf_counter() - start) * 1000)

    run_row = None
    try:
        run_row = session.get(QueryRun, result["run_id"])
        if run_row is not None:
            run_row.latency_ms = latency
            session.add(run_row)
            fallback_str = "true" if result.get("fallback_mode") else "false"
            session.add(
                AuditLog(
                    action="question",
                    target=result["run_id"],
                    metadata_json='{"latency_ms": ' + str(latency) + ', "fallback": ' + fallback_str + '}',
                )
            )
            session.commit()
    except Exception:
        pass

    resp = AskResponse(
        run_id=result["run_id"],
        answer_text=result.get("answer_text"),
        query_result=result.get("query_result"),
        chart_spec=result.get("chart_spec"),
        fallback_mode=bool(result.get("fallback_mode")),
        latency_ms=latency,
    )
    return ok(resp.model_dump())


@router.post("/export", response_model=None)
def export_query(req: ExportRequest, session: Session = Depends(get_session)) -> dict:
    init_db()
    run = session.get(QueryRun, req.query_run_id)
    if run is None:
        raise api_error("not_found", "Query run not found", 404)
    out_dir = _export_dir()
    fmt = req.format.lower()
    ts = __import__("datetime").datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    file_name = "export-" + str(run.run_id) + "-" + ts + "." + fmt
    file_path = out_dir / file_name
    q = (run.question or "").replace("\n", " ")
    if fmt == "csv":
        file_path.write_text('question,query\n"' + q.replace('"', '\\"') + '","' + (run.query_normalized or "").replace('"', '\\"') + '"\n', encoding="utf-8")
    else:
        file_path.write_text(
            "# Query export\n\nQuestion: " + q + "\n\n```\n" + (run.query_normalized or "") + "\n```",
            encoding="utf-8",
        )
    export_row = Export(
        query_run_id=run.id,
        user_id=run.user_id,
        format=fmt,
        storage_path=str(file_path),
        expires_at=__import__("datetime").datetime.utcnow() + __import__("datetime").timedelta(days=30),
    )
    session.add(export_row)
    session.commit()
    url = "/exports/" + export_row.id
    return ok(
        ExportResponse(
            export_id=export_row.id,
            url=url,
            expires_at=export_row.expires_at.isoformat(),
        ).model_dump()
    )


@router.get("/exports/{export_id}")
def get_export(export_id: str, session: Session = Depends(get_session)) -> dict:
    init_db()
    export = session.get(Export, export_id)
    if export is None:
        raise api_error("not_found", "Export not found", 404)
    path = Path(export.storage_path)
    if not path.exists():
        raise api_error("missing", "Export file missing", 404)
    from fastapi.responses import FileResponse
    return FileResponse(path, filename=path.name)
