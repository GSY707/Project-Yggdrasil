from __future__ import annotations

import shutil

import pytest

from yggdrasil_sdk import close_mcp_bridge_sessions, ensure_workspace_bootstrap, get_persistence_runtime, initialize_schema, reset_persistence_runtime
from yggdrasil_sdk.persistence.coordination import RedisCoordinator


@pytest.fixture(autouse=True)
def persistence_env(tmp_path, monkeypatch):
    database_path = tmp_path / "yggdrasil-test.db"
    state_root = tmp_path / "yggdrasil-state"
    state_dir = state_root / "state"
    monkeypatch.setenv("YGGDRASIL_DATABASE_URL", f"sqlite+pysqlite:///{database_path.as_posix()}")
    monkeypatch.setenv("YGGDRASIL_AUTO_CREATE_SCHEMA", "1")
    monkeypatch.setenv("YGGDRASIL_REDIS_URL", "redis://127.0.0.1:6390/15")
    monkeypatch.setenv("YGGDRASIL_STATE_ROOT", state_root.as_posix())
    monkeypatch.setenv("YGGDRASIL_DISABLE_LIVE_LLM", "1")
    reset_persistence_runtime()
    initialize_schema()
    ensure_workspace_bootstrap()
    try:
        RedisCoordinator(get_persistence_runtime().settings).client().flushdb()
    except Exception:
        pass
    yield
    close_mcp_bridge_sessions()
    reset_persistence_runtime()
    if state_dir.exists():
        shutil.rmtree(state_dir)
