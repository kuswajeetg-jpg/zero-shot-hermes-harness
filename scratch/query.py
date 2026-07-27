import sqlite3
import json

conn = sqlite3.connect('data/app.db')
cursor = conn.cursor()
cursor.execute("SELECT question, query_normalized, chart_spec, provider, model FROM query_runs ORDER BY created_at DESC LIMIT 5")
for r in cursor.fetchall():
    print("QUESTION:", r[0])
    print("QUERY/RESULT:", r[1])
    print("CHART:", r[2])
    print("PROVIDER/MODEL:", r[3], r[4])
    print("-" * 50)
