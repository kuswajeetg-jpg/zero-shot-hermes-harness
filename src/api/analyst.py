"""Analyst routes: upload, ask, export."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from src.api._common import api_error, ok
from src.api.auth import get_current_user, require_roles
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
from src.domain.cache import fingerprint, query_cache
from src.graph.analyst_runner import run_analyst
from src.ingest.csv import ingest_file_bytes
from src.observability.events import get_logger

router = APIRouter()

_KPI_CACHE: dict[str, dict[str, Any]] = {}


def _generate_suggested_questions(schema: list[dict], filename: str) -> list[str]:
    idish = {
        "id", "_id", "uuid", "guid", "sl_no", "sno", "serial", "code",
        "num", "reg_num", "registration", "fir_reg", "fir no", "mobile",
        "phone", "contact", "aadhaar", "pan", "fir number", "fir num",
        "employee", "employee_id", "emp_id", "external", "system",
    }
    locish = {
        "district", "district_name", "zone", "range", "state", "city",
        "ps_name", "police station", "station_name", "circle", "area",
        "locality", "division",
    }

    cat_cols = [c["name"] for c in schema if c.get("type") == "text" and c.get("name")]
    num_cols = [c["name"] for c in schema if c.get("type") in ("int", "float") and c.get("name")]
    date_cols = [c["name"] for c in schema if any(d in c.get("name", "").lower() for d in ("date", "dt", "time", "year", "month"))]
    
    good_cats = [c for c in cat_cols if any(k in c.lower() for k in locish) or not any(k in c.lower() for k in idish)]
    good_nums = [c for c in num_cols if not any(k in c.lower() for k in idish)]
    
    best_cat = good_cats[0] if good_cats else (cat_cols[0] if cat_cols else None)
    best_num = good_nums[0] if good_nums else (num_cols[0] if num_cols else None)
    best_date = date_cols[0] if date_cols else None
    
    is_police_hr = any("karma" in c.get("name", "").lower() for c in schema)
    has_completions = any("completion" in c.get("name", "").lower() for c in schema)

    questions = []
    
    if is_police_hr and has_completions:
        questions.append("Show top performers by learning hours and completions")
        if "Designation" in cat_cols or "Group" in cat_cols:
            questions.append("Compare total learning hours across different designations")
    
    if best_cat and len(questions) < 4:
        questions.append(f"Show the top 5 {best_cat}s with the highest number of incidents")
    
    if best_date:
        questions.append(f"What is the trend of cases over {best_date}?")
        
    if best_num and best_cat:
        questions.append(f"Compare the total {best_num} across different {best_cat}s")
        
    if not questions:
        questions.append(f"Show a high-level summary of {filename}")
        
    if len(questions) < 4:
        if best_cat and len(good_cats) > 1:
            questions.append(f"Break down the cases by {best_cat} and {good_cats[1]}")
        elif best_num:
            questions.append(f"What is the total {best_num} across all records?")
        else:
            questions.append(f"List the most recent 10 records")

    return questions[:4]


def _export_dir() -> Path:
    p = Path(get_settings().export_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _unique_storage_path(upload_dir: Path, filename: str) -> Path:
    base = Path(filename).stem
    suffix = Path(filename).suffix
    candidate = upload_dir / filename
    counter = 1
    while candidate.exists():
        candidate = upload_dir / f"{base}_{counter}{suffix}"
        counter += 1
    return candidate


@router.post("/upload", response_model=None)
def upload_csv(
    file: UploadFile = File(...),
    session_token: str = Form("default_session"),
    current: Any = Depends(require_roles("officer", "analyst", "administrator")),
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
    upload_dir = Path("data/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    saved_path = _unique_storage_path(upload_dir, parsed["filename"])
    saved_path.write_bytes(data)

    upload = Upload(
        session_id=session_token,
        filename=parsed["filename"],
        schema_json=json.dumps(parsed["schema"]),
        rows=parsed["rows"],
        storage_path=str(saved_path.resolve()),
        profile_json=None,
    )
    session.add(upload)
    session.flush()
    try:
        from src.ingest.profiler import profile_dataset
        profile = profile_dataset(str(saved_path.resolve()), parsed.get("schema"))
        if profile:
            upload.profile_json = json.dumps(profile)
    except Exception:
        pass

    metadata_json = (
        '{"filename": "' + parsed["filename"] + '", "rows": ' + str(parsed["rows"]) + '}'
    )
    session.add(
        AuditLog(
            user_id=current.user_id,
            action="upload",
            target=upload.id,
            metadata_json=metadata_json,
        )
    )
    session.commit()

    parsed["suggested_questions"] = _generate_suggested_questions(parsed["schema"], parsed["filename"])
    parsed["executive_briefing"] = []
    parsed["kpi_dashboard"] = None
    try:
        from src.domain.advisor import kpi_briefing
        brief = kpi_briefing(parsed["schema"], str(saved_path.resolve()))
        if brief:
            _KPI_CACHE[upload.id] = brief
            parsed["kpi_dashboard"] = brief
            parsed["executive_briefing"] = brief
    except Exception:
        pass

    return ok(UploadResponse(upload_id=upload.id, **parsed).model_dump(by_alias=True))


@router.get("/uploads", response_model=None)
def list_uploads(
    current: Any = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    init_db()
    uploads = session.query(Upload).order_by(Upload.created_at.desc()).all()
    items = []
    for u in uploads:
        import ast
        schema = []
        if u.schema_json:
            try:
                schema = json.loads(u.schema_json)
            except Exception:
                try:
                    schema = ast.literal_eval(u.schema_json)
                except Exception:
                    schema = []
        item = {
            "upload_id": u.id,
            "filename": u.filename,
            "rows": u.rows or 0,
            "schema": schema,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "suggested_questions": _generate_suggested_questions(schema, u.filename),
            "executive_briefing": [],
        }
        if u.storage_path:
            try:
                from src.domain.advisor import kpi_briefing
                if u.id not in _KPI_CACHE:
                    _KPI_CACHE[u.id] = kpi_briefing(schema, u.storage_path)
                brief = _KPI_CACHE[u.id]
                if brief:
                    item["executive_briefing"] = brief
            except Exception:
                pass
        items.append(item)
    return ok({"items": items, "count": len(items)})


@router.get("/schema/{upload_id}")
def get_schema_metadata(
    upload_id: str,
    current: Any = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    init_db()
    upload = session.get(Upload, upload_id)
    if not upload:
        real_id = upload_id.replace("csv_", "") if isinstance(upload_id, str) else upload_id
        upload = session.get(Upload, real_id)
    if not upload:
        raise api_error("not_found", "Upload not found", 404)
    schema = []
    if upload.schema_json:
        try:
            schema = json.loads(upload.schema_json)
        except Exception:
            try:
                import ast
                schema = ast.literal_eval(upload.schema_json)
            except Exception:
                schema = []
    meta = {"filename": upload.filename, "rows": upload.rows or 0}
    if upload.storage_path:
        try:
            import pandas as pd
            from pathlib import Path
            df = pd.read_csv(upload.storage_path, low_memory=False, on_bad_lines="skip")
            samples = {}
            for col in list(df.columns)[:12]:
                vals = [v for v in df[col].dropna().head(5).tolist()]
                samples[col] = vals
            meta["sample_values"] = samples
            meta["row_count_file"] = int(df.shape[0])
        except Exception:
            pass
    return ok({
        "upload_id": upload.id,
        "filename": upload.filename,
        "rows": upload.rows,
        "schema": schema,
        "metadata": meta,
    })


@router.delete("/uploads/{upload_id}", response_model=None)
def delete_upload(
    upload_id: str,
    current: Any = Depends(require_roles("officer", "analyst", "administrator")),
    session: Session = Depends(get_session),
) -> dict:
    init_db()
    u = session.query(Upload).filter(Upload.id == upload_id).first()
    if not u:
        raise api_error("not_found", f"Upload {upload_id} not found", 404)

    if u.storage_path and Path(u.storage_path).exists():
        try:
            Path(u.storage_path).unlink(missing_ok=True)
        except Exception:
            pass

    _KPI_CACHE.pop(upload_id, None)
    session.delete(u)
    session.commit()
    return ok({"message": f"Upload {upload_id} deleted successfully"})


@router.post("/ask", response_model=None)
def ask(
    req: AskRequest,
    current: Any = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    init_db()
    if not req.question or not req.question.strip():
        raise api_error("empty_question", "Question cannot be empty.", 422)

    active_schema = []
    try:
        source_upload_id = req.source_id.replace("csv_", "") if req.source_id else None
        upload_record = session.get(Upload, source_upload_id) if source_upload_id else None
        if not upload_record:
            upload_record = session.query(Upload).order_by(Upload.created_at.desc()).first()
        if upload_record and upload_record.schema_json:
            try:
                active_schema = json.loads(upload_record.schema_json)
            except Exception:
                import ast
                active_schema = ast.literal_eval(upload_record.schema_json)
        effective_source_id = req.source_id or (f"csv_{upload_record.id}" if upload_record else req.source_id)
    except Exception:
        active_schema = []
        effective_source_id = req.source_id

    start = __import__("time").perf_counter()
    cache_key = fingerprint(req.question, req.source_id, None)
    cached = query_cache.get(cache_key)
    if cached:
        return ok({
            "run_id": cached.get("run_id"),
            "answer_text": cached.get("answer_text"),
            "query_result": cached.get("query_result"),
            "chart_spec": cached.get("chart_spec"),
            "fallback_mode": bool(cached.get("fallback_mode")),
            "latency_ms": cached.get("latency_ms"),
            "provider": cached.get("provider"),
            "model": cached.get("model"),
            "status": "cached",
        })

    result = run_analyst(
        user_id=current.user_id,
        session_token=req.session_token,
        source_id=effective_source_id,
        user_message=req.question,
        schema=active_schema,
    )
    query_cache.put(cache_key, result)
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
                    user_id=current.user_id,
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
        provider=result.get("provider"),
        model=result.get("model"),
        status=result.get("status"),
        error=result.get("error"),
        checkpoint=result.get("checkpoint"),
    )
    return ok(resp.model_dump())


@router.post("/export", response_model=None)
def export_query(
    req: ExportRequest,
    current: Any = Depends(require_roles("officer", "analyst", "administrator")),
    session: Session = Depends(get_session),
) -> dict:
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
        file_path.write_text(
            'question,query\n"' + q.replace('"', '\\"') + '","' + (run.query_normalized or "").replace('"', '\\"') + '"\n',
            encoding="utf-8",
        )
    else:
        file_path.write_text(
            "# Query export\n\nQuestion: " + q + "\n\n```\n" + (run.query_normalized or "") + "\n```",
            encoding="utf-8",
        )
    export_row = Export(
        query_run_id=run.id,
        user_id=current.user_id,
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
def get_export(
    export_id: str,
    current: Any = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    init_db()
    export = session.get(Export, export_id)
    if export is None:
        raise api_error("not_found", "Export not found", 404)
    path = Path(export.storage_path)
    if not path.exists():
        raise api_error("missing", "Export file missing", 404)
    return ok({
        "export_id": export.id,
        "path": export.storage_path,
        "format": export.format,
        "expires_at": export.expires_at.isoformat(),
    })


@router.post("/upload-multi", response_model=None)
def upload_csv_multi(
    files: list[UploadFile] = File(...),
    session_token: str = Form("default_session"),
    current: Any = Depends(require_roles("officer", "analyst", "administrator")),
    session: Session = Depends(get_session),
) -> dict:
    init_db()
    results = []
    for file in files:
        if not file.filename or not file.filename.lower().endswith(".csv"):
            continue
        try:
            data = file.file.read()
        finally:
            file.file.close()
        if len(data) > 100 * 1024 * 1024:
            continue
        result = _upload_single_raw(data, file.filename, session_token, current.user_id, session)
        results.append(result)
    return ok({"uploads": results, "count": len(results)})


def _upload_single_raw(data: bytes, filename: str, session_token: str, user_id: str, session: Session) -> dict:
    parsed = ingest_file_bytes(data, filename)
    upload_dir = Path("data/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    saved_path = _unique_storage_path(upload_dir, parsed["filename"])
    saved_path.write_bytes(data)

    upload = Upload(
        session_id=session_token,
        filename=parsed["filename"],
        schema_json=json.dumps(parsed["schema"]),
        rows=parsed["rows"],
        storage_path=str(saved_path.resolve()),
        profile_json=None,
    )
    session.add(upload)
    session.flush()
    try:
        from src.ingest.profiler import profile_dataset
        profile = profile_dataset(str(saved_path.resolve()), parsed.get("schema"))
        if profile:
            upload.profile_json = json.dumps(profile)
    except Exception:
        pass

    metadata_json = (
        '{"filename": "' + parsed["filename"] + '", "rows": ' + str(parsed["rows"]) + '}'
    )
    session.add(
        AuditLog(
            user_id=user_id,
            action="upload",
            target=upload.id,
            metadata_json=metadata_json,
        )
    )
    session.commit()

    parsed["suggested_questions"] = _generate_suggested_questions(parsed["schema"], parsed["filename"])
    parsed["executive_briefing"] = []
    parsed["kpi_dashboard"] = None
    try:
        from src.domain.advisor import kpi_briefing
        brief = kpi_briefing(parsed["schema"], str(saved_path.resolve()))
        if brief:
            parsed["kpi_dashboard"] = brief
            parsed["executive_briefing"] = brief
    except Exception:
        pass

    return UploadResponse(upload_id=upload.id, **parsed).model_dump(by_alias=True)
