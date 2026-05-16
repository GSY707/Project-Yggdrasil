import os
import json
import sqlite3
from pathlib import Path

# Try common db names found
db_candidates = [
    ".yggdrasil/local-dev.db",
    ".yggdrasil/state/evaluation-sandboxes/evalsandbox_a36b08c6576b482694a2/evaluation.db",
    ".yggdrasil/state/evaluation-sandboxes/evalsandbox_d18119b6731849d0b54f/evaluation.db"
]

task_id = "task_memory_tree_runtime"

found_row = None
used_db = None

for db_path in db_candidates:
    if not os.path.exists(db_path):
        continue
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='model_invocations'")
        if not cursor.fetchone():
            conn.close()
            continue
            
        query = "SELECT * FROM model_invocations WHERE task_id = ? ORDER BY created_at DESC LIMIT 1"
        cursor.execute(query, (task_id,))
        row = cursor.fetchone()
        if row:
            found_row = row
            used_db = db_path
            conn.close()
            break
        conn.close()
    except Exception:
        continue

if not found_row:
    print(f"No model invocation found for task_id: {task_id} in checked DBs.")
    exit(0)

print(f"Using DB: {used_db}")
invocation_id = found_row['id']
request_ref = found_row['request_ref']
compiled_ref = found_row['compiled_messages_ref']

print(f"1) Invocation ID: {invocation_id}")

def get_keys_and_content(ref):
    if not ref:
        return "N/A", None
    path = Path(ref)
    # Check if absolute or relative to repo root
    if not path.exists():
        return f"File not found: {ref}", None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return list(data.keys()), data
    except Exception as e:
        return f"Error reading {ref}: {e}", None

req_keys, _ = get_keys_and_content(request_ref)
print(f"2) Request JSON top-level keys: {req_keys}")

compiled_keys, compiled_data = get_keys_and_content(compiled_ref)
print(f"3) Compiled JSON top-level keys: {compiled_keys}")

if compiled_data:
    messages = None
    if 'messages' in compiled_data:
        messages = compiled_data['messages']
    elif 'prompt' in compiled_data and isinstance(compiled_data['prompt'], dict) and 'messages' in compiled_data['prompt']:
        messages = compiled_data['prompt']['messages']
    
    if messages and isinstance(messages, list) and len(messages) > 0:
        last_msg = messages[-1]
        content = ""
        if isinstance(last_msg, dict):
            content = last_msg.get('content', '')
        
        if isinstance(content, list):
             text_parts = [p.get('text', '') for p in content if isinstance(p, dict) and p.get('type') == 'text']
             content = "".join(text_parts)
        
        print(f"4) Last message content (first 600 chars):\n{str(content)[:600]}")
    else:
        print("4) No messages found in compiled JSON.")
