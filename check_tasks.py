import sqlite3
import os

db_candidates = [
    ".yggdrasil/local-dev.db",
    ".yggdrasil/state/evaluation-sandboxes/evalsandbox_a36b08c6576b482694a2/evaluation.db",
    ".yggdrasil/state/evaluation-sandboxes/evalsandbox_d18119b6731849d0b54f/evaluation.db"
]

for db_path in db_candidates:
    if not os.path.exists(db_path):
        continue
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print(f"\n--- Checking {db_path} ---")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='model_invocations'")
    if not cursor.fetchone():
        print("Table 'model_invocations' not found.")
        conn.close()
        continue
        
    cursor.execute("SELECT DISTINCT task_id FROM model_invocations LIMIT 20")
    tasks = [r['task_id'] for r in cursor.fetchall()]
    print(f"Sample task_ids in this DB: {tasks}")
    
    cursor.execute("SELECT COUNT(*) as cnt FROM model_invocations")
    count = cursor.fetchone()['cnt']
    print(f"Total model invocations: {count}")
    
    conn.close()
