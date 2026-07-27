"""Report API: generate CSV and Markdown analysis reports."""
from __future__ import annotations

import csv
import json
import os
from datetime import datetime
from io import StringIO
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class AnalysisReportRequest(BaseModel):
    title: str = "UP Police Data Analysis Report"
    rows: list[dict[str, Any]] | None = None
    columns: list[str] | None = None
    chart_type: str = "bar"
    chart_title: str = "Analytics"
    summary_text: str = ""
    detailed: list[str] | None = None
    findings: list[str] | None = None
    fmt: str = "csv"
    filename_hint: str = "analysis_report"
    use_cache: bool = True
    lang: str = "en"


def _build_csv(rows: list[dict[str, Any]], columns: list[str]) -> str:
    buf = StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns)
    writer.writeheader()
    for row in rows:
        writer.writerow({c: row.get(c, "") for c in columns})
    return buf.getvalue()


def _build_markdown(req: AnalysisReportRequest) -> str:
    lines = [
        f"# {req.title}",
        "",
        f"Generated: {datetime.utcnow().isoformat()}",
        "",
        "## Executive Summary",
        "",
        req.summary_text or "No summary provided.",
        "",
    ]
    if req.findings:
        lines += ["## Key Findings", ""]
        for finding in req.findings:
            lines.append(f"- {finding}")
        lines.append("")
    if req.detailed:
        lines += ["## Detailed Analysis", ""]
        for detail in req.detailed:
            lines.append(f"- {detail}")
        lines.append("")
    if req.rows and req.columns:
        lines += ["## Structured Data Sample", ""]
        lines.append("| " + " | ".join(req.columns) + " |")
        lines.append("| " + " | ".join(["---"] * len(req.columns)) + " |")
        for row in req.rows[:50]:
            lines.append("| " + " | ".join(str(row.get(c, "")) for c in req.columns) + " |")
        lines.append("")
    return "\n".join(lines)


@router.post("/report/analysis")
def analysis_report(req: AnalysisReportRequest):
    try:
        fmt = (req.fmt or "csv").lower()
        rows = req.rows or []
        columns = req.columns or (list(rows[0].keys()) if rows else [])
        filename_hint = req.filename_hint or "analysis_report"
        ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")

        if fmt == "md":
            content = _build_markdown(req)
            file_path = os.path.join("exports", f"{filename_hint}-{ts}.md")
        else:
            content = _build_csv(rows, columns)
            file_path = os.path.join("exports", f"{filename_hint}-{ts}.csv")

        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        return {
            "format": fmt,
            "filename": os.path.basename(file_path),
            "path": file_path,
            "generated_at": datetime.utcnow().isoformat(),
        }
    except Exception as exc:
        raise HTTPException(500, detail=f"Report generation failed: {exc}") from exc
