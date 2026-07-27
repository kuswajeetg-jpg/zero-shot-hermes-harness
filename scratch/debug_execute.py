import json
from src.db.session import create_db_session
from src.db.models import Upload
from src.graph.nodes import plan, _sanitize_table_name, analyze_source_id
from src.graph.sql_generator import generate_sql, validate_sql
import duckdb

with create_db_session() as session:
    u = session.query(Upload).order_by(Upload.created_at.desc()).first()
    u_id = u.id if u else None
    u_filename = u.filename if u else None
    u_schema_json = u.schema_json if u else None
    u_storage_path = u.storage_path if u else None

state = {
    "run_id": "test_run_123",
    "user_id": "admin@up.gov",
    "session_token": "default_session",
    "source_id": f"csv_{u_id}" if u_id else "none",
    "user_message": "What are the top 10 records in fir_registrations.csv?",
    "schema": json.loads(u_schema_json) if u_schema_json else [],
    "storage_path": u_storage_path,
}

state = plan(state)
plan_obj = state["plan"]

print("--- Running execute inner logic ---")
schema = state.get("schema") or []
columns = [s["name"] for s in schema] if isinstance(schema, list) and schema else []
storage_path = state.get("storage_path")

con = duckdb.connect(database=":memory:")

with create_db_session() as session:
    uploads = session.query(Upload).all()
    for u in uploads:
        if u.storage_path and __import__("pathlib").Path(u.storage_path).exists():
            escaped_u_path = u.storage_path.replace("\\", "/")
            sanitized_name = _sanitize_table_name(u.filename)
            con.execute(f"CREATE OR REPLACE VIEW {sanitized_name} AS SELECT * FROM read_csv_auto('{escaped_u_path}', header=true, encoding='UTF-8', ignore_errors=true)")
            storage_filename = __import__("pathlib").Path(u.storage_path).name
            sanitized_storage_name = _sanitize_table_name(storage_filename)
            if sanitized_storage_name != sanitized_name:
                con.execute(f"CREATE OR REPLACE VIEW {sanitized_storage_name} AS SELECT * FROM read_csv_auto('{escaped_u_path}', header=true, encoding='UTF-8', ignore_errors=true)")

if storage_path and __import__("pathlib").Path(storage_path).exists():
    escaped_path = storage_path.replace("\\", "/")
    con.execute(f"CREATE OR REPLACE VIEW dataset AS SELECT * FROM read_csv_auto('{escaped_path}', header=true, encoding='UTF-8', ignore_errors=true)")

sql_data = generate_sql(plan_obj, state.get("user_message", ""), schema)
sql = sql_data["sql"]
print("Generated SQL:", sql)

safe_sql = sql.strip()
validate_sql(safe_sql)

print("Executing SQL query...")
try:
    res = con.execute(safe_sql).fetchall()
    print("Success! Row count:", len(res))
    print("Sample:", res[:2])
except Exception as e:
    print("Execution failed with exception:", e)
con.close()
