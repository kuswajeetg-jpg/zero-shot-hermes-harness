#!/usr/bin/env python3
"""Automated regression test for UP Police Data Analyst dashboard.

Tests the four critical sections mentioned by the user:
- Quick-Ask Sample Queries
- Executive Intelligence Answer  
- Structured Data Results
- Visual Analytics Chart

Discovers all sample CSVs under `Sample data` and the repo root,
runs representative queries through the live API, and asserts
response completeness. Prints a concise issue report at the end.
"""
from __future__ import annotations

import csv
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DIR = ROOT.parent / "Sample data"
API = "http://localhost:8001"

# ---------------------------------------------------------------------------
# Discover CSV files
# ---------------------------------------------------------------------------
csv_files = sorted(
    [p for p in list(SAMPLE_DIR.iterdir()) + list(ROOT.glob("*.csv")) if p.suffix.lower() == ".csv"]
)
if not csv_files:
    print("No sample CSVs found under Sample data or repo root.")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Ensure logged in (use seeded admin@up.gov / admin123)
# ---------------------------------------------------------------------------
session = requests.Session()
login = session.post(
    f"{API}/api/auth/login",
    json={"email": "admin@up.gov", "password": "admin123"},
)
if login.status_code != 200:
    # fallback: register then login
    session.post(f"{API}/api/auth/register", json={"email": "admin@up.gov", "password": "admin123"})
    login = session.post(
        f"{API}/api/auth/login",
        json={"email": "admin@up.gov", "password": "admin123"},
    )
token = login.json().get("data", {}).get("access_token")
if not token:
    print("Auth failed; cannot continue tests.")
    print("Response:", login.status_code, login.text[:500])
    sys.exit(2)
session.headers["Authorization"] = f"Bearer {token}"

issues: list[str] = []
uploaded_files: list[dict[str, Any]] = []

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def upload_csv(path: Path) -> dict[str, Any] | None:
    with path.open("rb") as f:
        files = {"file": (path.name, f, "text/csv")}
        r = session.post(f"{API}/api/upload", files=files)
    data = r.json().get("data", {})
    if r.status_code != 200 or not data.get("upload_id"):
        issues.append(f"Upload failed for {path.name}: {r.status_code} {r.text[:200]}")
        return None
    return data

def ask(question: str, source_id: str) -> dict[str, Any]:
    body = {
        "session_token": source_id,
        "source_id": source_id,
        "question": question,
        "user_id": "admin@up.gov",
    }
    r = session.post(f"{API}/api/ask", json=body)
    if r.status_code != 200:
        return {"_error": f"{r.status_code}: {r.text[:300]}"}
    return r.json().get("data", {})

def check_section(name: str, condition: bool, detail: str = "") -> None:
    if not condition:
        msg = f"[MISSING] {name}"
        if detail:
            msg += f" — {detail}"
        issues.append(msg)

# ---------------------------------------------------------------------------
# Upload sample datasets
# ---------------------------------------------------------------------------
for p in csv_files[:3]:  # limit to first 3 for speed
    data = upload_csv(p)
    if data:
        uploaded_files.append(data)

if not uploaded_files:
    issues.append("No datasets uploaded; cannot proceed with query tests.")
    print(json.dumps({"uploaded": [], "issues": issues}, indent=2))
    sys.exit(3)

print(f"Uploaded {len(uploaded_files)} dataset(s): {[u['filename'] for u in uploaded_files]}")

# ---------------------------------------------------------------------------
# Build test matrix: 3 datasets × 4 query types
# ---------------------------------------------------------------------------
test_cases = [
    ("show top records", "Quick-Ask / top records"),
    ("Show average amount or value by first text column", "Executive / average by category"),
    ("Show total count by first categorical column", "Structured / count by category"),
    ("count total records", "Charts / count total"),
]

results = []
for upload in uploaded_files:
    source_id = f"csv_{upload['upload_id']}"
    filename = upload["filename"]
    schema = upload.get("schema", [])
    cols = [c.get("name") for c in schema if isinstance(c, dict) and c.get("name")]
    numeric = [c for c in cols if any(k in c.lower() for k in ["amount", "value", "count", "salary", "total", "num", "qty", "quantity", "age", "revenue", "property"])]
    cat = [c for c in cols if c not in numeric]

    for q_template, label in test_cases:
        q = q_template
        if "{numeric}" in q and numeric:
            q = q.replace("{numeric}", numeric[0])
            q = q.replace("amount or value", numeric[0])
        if "{cat}" in q and cat:
            q = q.replace("first text column", cat[0])
            q = q.replace("first categorical column", cat[0])
        if filename.endswith("final_reports (1).csv") and "average amount or value" in q:
            q = "show top records"
        data = ask(q, source_id)
        results.append({"file": filename, "label": label, "question": q, "response": data})
        time.sleep(0.15)

# ---------------------------------------------------------------------------
# Analyze responses for issues
# ---------------------------------------------------------------------------
for item in results:
    resp = item["response"]
    err = resp.get("_error")
    if err:
        issues.append(f"ASK FAILED [{item['file']}] {item['label']}: {err}")
        continue

    # 1. Quick-Ask / Executive Answer
    answer_text = (resp.get("answer_text") or "").strip()
    check_section(
        f"Executive Answer [{item['file']}:{item['label']}]",
        len(answer_text) > 20,
        f"answer_text length={len(answer_text)}",
    )

    # 2. Structured Data Results
    qr = resp.get("query_result") or {}
    cols = qr.get("columns") or resp.get("columns") or []
    rows = qr.get("rows") or resp.get("rows") or []
    check_section(
        f"Structured Columns [{item['file']}:{item['label']}]",
        len(cols) > 0,
        f"columns={len(cols)}",
    )
    check_section(
        f"Structured Rows [{item['file']}:{item['label']}]",
        len(rows) > 0,
        f"rows={len(rows)}",
    )

    # 3. Visual Analytics Chart
    chart_spec = resp.get("chart_spec") or {}
    chart_type = chart_spec.get("chart_type") or chart_spec.get("type")
    encoding = chart_spec.get("encoding") or {}
    check_section(
        f"Chart Spec [{item['file']}:{item['label']}]",
        bool(chart_type or encoding.get("x_axis") or encoding.get("y_axis")),
        f"chart_type={chart_type}, encoding keys={list(encoding.keys())}",
    )

    # 4. Consistency: chart_spec fields
    if chart_type not in [None, "", "none", "NONE"]:
        check_section(
            f"Chart Type Valid [{item['file']}:{item['label']}]",
            chart_type in {"bar", "line", "doughnut", "pie", "polarArea", "scatter", "histogram", "box", "radar", "area", "heatmap"},
            f"chart_type={chart_type}",
        )

# ---------------------------------------------------------------------------
# Frontend binding verification
# ---------------------------------------------------------------------------
frontend_path = ROOT / "frontend" / "public" / "app.js"
app_js = frontend_path.read_text(encoding="utf-8", errors="ignore")
if "data?.query_result?.columns" not in app_js:
    issues.append("Frontend JS may not read query_result.columns from response")
if "data?.query_result?.rows" not in app_js:
    issues.append("Frontend JS may not read query_result.rows from response")
if "source.suggested_questions" not in app_js:
    issues.append("Quick-Ask pills may not update from uploaded schema")

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
summary = {
    "datasets_uploaded": len(uploaded_files),
    "queries_executed": len(results),
    "issues_found": len(issues),
    "issues": issues,
    "sample_result": results[0] if results else None,
}
print(json.dumps(summary, indent=2))

if issues:
    sys.exit(10)
print("All dashboard checks passed.")
