"""Tests for analyst backend slice."""
from __future__ import annotations

from datetime import datetime
from io import BytesIO

from fastapi.testclient import TestClient

from src.api import create_app
from src.db.models import AuditLog, Export, QueryRun, Upload
from src.db.session import create_db_session, get_session
from src.ingest.csv import ingest_file_bytes
from src.llm.fallback_engine import classify_intent


def _client() -> TestClient:
    return TestClient(create_app())


def _register_and_login(email: str, password: str = "secret123"):
    client = _client()
    reg = client.post("/auth/register", json={"email": email, "password": password})
    assert reg.status_code == 200, reg.text
    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    return client, login.json()["data"]["access_token"]


def test_register_login_returns_token():
    with _client() as client:
        reg = client.post("/auth/register", json={"email": "user@example.com", "password": "secret123"})
        assert reg.status_code == 200

        login = client.post("/auth/login", json={"email": "user@example.com", "password": "secret123"})
        assert login.status_code == 200
        assert login.json()["data"]["access_token"]


def test_upload_csv_creates_upload_and_audit():
    client, token = _register_and_login("a@b.com")
    client.headers = {"Authorization": "Bearer " + token}
    csv = b"id,name,value\n1,alpha,10\n2,beta,20\n"
    res = client.post(
        "/upload",
        data={"session_token": "s1"},
        files={"file": ("data.csv", BytesIO(csv), "text/csv")},
    )
    assert res.status_code == 200
    body = res.json()["data"]
    assert body["rows"] == 2
    assert body["upload_id"]
    assert any(c["name"] == "name" for c in body["schema"])

    with create_db_session() as session:
        upload = session.get(Upload, body["upload_id"])
        assert upload is not None
        logs = session.query(AuditLog).filter(AuditLog.action == "upload").all()
        assert any(log.target == body["upload_id"] for log in logs)


def test_upload_rejects_non_csv_and_empty_question():
    client, token = _register_and_login("c@d.com")
    client.headers = {"Authorization": "Bearer " + token}
    bad = client.post("/upload", data={"session_token": "s2"}, files={"file": ("bad.txt", BytesIO(b"hi"), "text/plain")})
    assert bad.status_code == 422

    ask = client.post("/ask", json={"session_token": "s2", "source_id": "s", "question": "   "})
    assert ask.status_code == 422


def test_ask_returns_answer_and_audit():
    client, token = _register_and_login("e@f.com")
    client.headers = {"Authorization": "Bearer " + token}
    ask = client.post("/ask", json={"session_token": "s3", "source_id": "src1", "question": "How many records?", "user_id": "local"})
    assert ask.status_code == 200
    body = ask.json()["data"]
    assert body["run_id"]

    with create_db_session() as session:
        run = session.get(QueryRun, body["run_id"])
        assert run is not None
        assert run.status in {"completed", "failed"}
        logs = session.query(AuditLog).filter(AuditLog.action == "question").all()
        assert any(log.target == body["run_id"] for log in logs)


def test_export_stores_file_and_ttl():
    client, token = _register_and_login("g@h.com")
    client.headers = {"Authorization": "Bearer " + token}
    ask = client.post("/ask", json={"session_token": "s4", "source_id": "src1", "question": "Top 5", "user_id": "local"}).json()["data"]
    export = client.post("/export", json={"query_run_id": ask["run_id"], "format": "csv", "user_id": "local"})
    assert export.status_code == 200
    export_id = export.json()["data"]["export_id"]

    with create_db_session() as session:
        row = session.get(Export, export_id)
        assert row is not None
        assert row.format == "csv"
        assert row.expires_at > datetime.utcnow()
        assert __import__("pathlib").Path(row.storage_path).exists()


def test_pii_flagging_in_csv_ingest():
    parsed = ingest_file_bytes(b"mobile,aadhaar,name\n1234567890,1234abcd1234,john\n", "x.csv")
    schema = {c["name"]: c["pii"] for c in parsed["schema"]}
    assert schema["mobile"] == "true"
    assert schema["aadhaar"] == "true"
    assert schema["name"] == "false"


def test_semantic_enrichment_rule_based():
    parsed = ingest_file_bytes(b"reg_num,fir_no,district\n1,ABC,Kanpur\n", "semantic.csv")
    by_name = {c["name"]: c for c in parsed["schema"]}
    assert by_name["reg_num"]["description"] == "Registration identifier/number"
    assert "registration number" in by_name["reg_num"]["synonyms"]
    assert by_name["fir_no"]["description"] == "FIR number assigned to the complaint"
    assert "fir id" in by_name["fir_no"]["synonyms"]
    assert by_name["district"]["description"] == "District where the incident was registered"
    assert "jurisdiction" in by_name["district"]["synonyms"]


def test_csv_case_collision_headers_error():
    try:
        ingest_file_bytes(b"ID,id,value\n1,2,3\n", "case.csv")
    except ValueError as exc:
        assert "Duplicate headers" in str(exc)
    else:
        raise AssertionError("Duplicate headers were not rejected")


def test_fallback_intent_classifier():
    assert classify_intent("How many incidents") == "count"
    assert classify_intent("Top stolen vehicles") == "top_n"
    assert classify_intent("Average response time") == "average"
    assert classify_intent("Compare districts") == "compare"
    assert classify_intent("Trend over months") == "trend"
    assert classify_intent("What is the capital?") == "custom_query"
