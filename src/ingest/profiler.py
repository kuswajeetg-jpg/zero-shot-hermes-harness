"""Dataset profiling via DuckDB."""
from __future__ import annotations

import json
from typing import Any


def profile_dataset(storage_path: str, schema: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    try:
        import duckdb
        from pathlib import Path
        p = Path(storage_path)
        if not p.exists():
            return {}
        escaped = str(p).replace("\\", "/")
        con = duckdb.connect(database=":memory:")
        try:
            con.execute(
                f"CREATE OR REPLACE VIEW dataset AS SELECT * FROM read_csv_auto('{escaped}', header=true, encoding='UTF-8', ignore_errors=true)"
            )
            cols = [desc[0] for desc in con.execute("PRAGMA table_info(dataset)").fetchall()]
            if not cols:
                con.close()
                return {}
            profile: dict[str, Any] = {}
            for c in cols:
                try:
                    row = con.execute(
                        f"""
                        SELECT
                            COUNT(*) - COUNT("{c}") AS null_count,
                            COUNT(DISTINCT "{c}") AS unique_count,
                            MIN("{c}") AS min_val,
                            MAX("{c}") AS max_val,
                            AVG(TRY_CAST("{c}" AS DOUBLE)) AS avg_val,
                            STDDEV(TRY_CAST("{c}" AS DOUBLE)) AS std_val,
                            MIN(TRY_CAST("{c}" AS TIMESTAMP)) AS min_date,
                            MAX(TRY_CAST("{c}" AS TIMESTAMP)) AS max_date
                        FROM dataset
                        """
                    ).fetchone()
                    if not row:
                        continue
                    (
                        null_count,
                        unique_count,
                        min_val,
                        max_val,
                        avg_val,
                        std_val,
                        min_date,
                        max_date,
                    ) = row
                    top3 = []
                    try:
                        top3 = [
                            {"value": str(r[0]), "count": int(r[1])}
                            for r in con.execute(
                                f'SELECT "{c}", COUNT(*) AS c FROM dataset WHERE "{c}" IS NOT NULL GROUP BY "{c}" ORDER BY c DESC LIMIT 3'
                            ).fetchall()
                        ]
                    except Exception:
                        pass
                    dtype = "unknown"
                    if schema:
                        matched = next((s for s in schema if s.get("name") == c), None)
                        if matched:
                            dtype = matched.get("type") or dtype
                    else:
                        try:
                            inferred = con.execute(f'SELECT TYPEOF("{c}") FROM dataset LIMIT 1').fetchone()
                            if inferred:
                                raw = str(inferred[0])
                                if "INT" in raw:
                                    dtype = "int"
                                elif "DOUBLE" in raw or "FLOAT" in raw or "DECIMAL" in raw:
                                    dtype = "float"
                                elif "BOOL" in raw:
                                    dtype = "bool"
                                elif "DATE" in raw or "TIMESTAMP" in raw:
                                    dtype = "datetime"
                                elif "VARCHAR" in raw or "TEXT" in raw:
                                    dtype = "text"
                        except Exception:
                            pass
                    stats: dict[str, Any] = {
                        "dtype": dtype,
                        "null_count": int(null_count or 0),
                        "unique_count": int(unique_count or 0),
                        "top_3_values": top3,
                    }
                    if dtype in ("int", "float", "unknown") and any(v is not None for v in [min_val, max_val, avg_val]):
                        stats.update(
                            {
                                "min": min_val,
                                "max": max_val,
                                "avg": avg_val,
                                "std_dev": std_val,
                            }
                        )
                    if dtype == "datetime" or any(v is not None for v in [min_date, max_date]):
                        stats.update(
                            {
                                "min_date": str(min_date) if min_date is not None else None,
                                "max_date": str(max_date) if max_date is not None else None,
                            }
                        )
                    profile[c] = stats
                except Exception:
                    continue
            return profile
        finally:
            con.close()
    except Exception:
        return {}
