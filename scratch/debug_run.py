import json
from src.graph.nodes import plan, execute_read_only, intake
from src.db.session import create_db_session
from src.db.models import Upload

with create_db_session() as session:
    u = session.query(Upload).order_by(Upload.created_at.desc()).first()
    u_id = u.id if u else None
    u_filename = u.filename if u else None
    u_schema_json = u.schema_json if u else None
    u_storage_path = u.storage_path if u else None
    print("Latest upload name:", u_filename)
    print("Latest upload schema length:", len(json.loads(u_schema_json)) if u else None)
    print("Latest upload path:", u_storage_path)

state = {
    "run_id": "test_run_123",
    "user_id": "admin@up.gov",
    "session_token": "default_session",
    "source_id": f"csv_{u_id}" if u_id else "none",
    "user_message": "What are the top 10 records in fir_registrations.csv?",
    "schema": json.loads(u_schema_json) if u_schema_json else [],
    "storage_path": u_storage_path,
    "plan": None,
    "query_result": None,
    "chart_spec": None,
    "answer_text": None,
    "fallback_mode": False,
    "latency_ms": None,
    "error": None,
    "checkpoint": None,
    "advisor": None,
}

print("Running plan...")
state = plan(state)
print("Plan error:", state.get("error"))
print("Plan plan:", json.dumps(state.get("plan"), indent=2))

print("\nRunning execute...")
state = execute_read_only(state)
print("Execute error:", state.get("error"))
print("State keys:", list(state.keys()))
print("Result query_result:", state.get("query_result"))
print("Result rows count:", len(state.get("query_result", {}).get("rows", [])) if state.get("query_result") else None)
print("Result columns:", state.get("query_result", {}).get("columns") if state.get("query_result") else None)
print("Result rows sample:", state.get("query_result", {}).get("rows")[:2] if state.get("query_result") else None)
