import sqlite3
import os

db_path = 'd:/zero-shot-hermes-harness/zero-shot-hermes-harness/data/app.db'
print("Exists:", os.path.exists(db_path))
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    print('Tables:', cursor.fetchall())
    try:
        cursor.execute("SELECT id, user_id, action, target, created_at FROM audit_logs ORDER BY created_at ASC")
        print('All Audit Logs:', cursor.fetchall())
    except Exception as e:
        print('Error:', e)
    conn.close()
