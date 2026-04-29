import time, os, tempfile
db_path = tempfile.mktemp(suffix='.db')
os.environ['YGGDRASIL_DATABASE_URL'] = 'sqlite+pysqlite:///' + db_path
os.environ['YGGDRASIL_AUTO_CREATE_SCHEMA'] = '1'
os.environ['YGGDRASIL_REDIS_URL'] = 'redis://127.0.0.1:6390/15'
from yggdrasil_sdk import reset_persistence_runtime, initialize_schema, ensure_workspace_bootstrap
t0 = time.perf_counter()
reset_persistence_runtime()
t1 = time.perf_counter()
initialize_schema()
t2 = time.perf_counter()
ensure_workspace_bootstrap()
t3 = time.perf_counter()
print(f'reset_persistence_runtime:  {(t1-t0)*1000:.0f}ms')
print(f'initialize_schema:          {(t2-t1)*1000:.0f}ms')
print(f'ensure_workspace_bootstrap: {(t3-t2)*1000:.0f}ms')
print(f'total per test-fixture:     {(t3-t0)*1000:.0f}ms')
