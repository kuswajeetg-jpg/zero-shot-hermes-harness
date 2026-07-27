import json
from src.db.session import create_db_session
from src.db.models import Upload
from src.graph.sql_generator import generate_sql
import duckdb

with create_db_session() as session:
    u = session.query(Upload).order_by(Upload.created_at.desc()).first()
    u_schema = json.loads(u.schema_json)
    u_path = u.storage_path

question = "What are the top 10 records in fir_registrations.csv?"
plan = {
  "intent": "top_n",
  "table_name": "fir_registrations",
  "target_column": None,
  "group_by": None,
  "aggregation": "NONE",
  "filters": [],
  "sort_order": "DESC",
  "limit": 10,
}

sql_data = generate_sql(plan, question, u_schema)
sql = sql_data["sql"]
print("Generated SQL:", sql)

con = duckdb.connect(database=":memory:")
escaped_path = u_path.replace("\\", "/")
print("Escaped path:", escaped_path)
con.execute(f"CREATE OR REPLACE VIEW fir_registrations AS SELECT * FROM read_csv_auto('{escaped_path}', header=true, encoding='UTF-8', ignore_errors=true)")

try:
    res = con.execute(sql).fetchall()
    print("Result:", res[:2])
    print("Columns:", [desc[0] for desc in con.description])
except Exception as e:
    print("DuckDB query failed:", e)
con.close()
