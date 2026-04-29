from __future__ import annotations

import os
import shutil

import pytest
import sqlalchemy as sa

from yggdrasil_sdk import close_mcp_bridge_sessions, ensure_workspace_bootstrap, get_persistence_runtime, initialize_schema, reset_persistence_runtime
from yggdrasil_sdk.app_catalog import invalidate_application_catalog_cache
from yggdrasil_sdk.catalog import invalidate_catalog_cache
from yggdrasil_sdk.prompting import invalidate_prompt_registry_cache
from yggdrasil_sdk.persistence.coordination import RedisCoordinator
from yggdrasil_sdk.tool_runtime import invalidate_tool_descriptor_cache


def _truncate_all_tables() -> None:
    from yggdrasil_sdk.persistence.orm import Base
    runtime = get_persistence_runtime()
    with runtime.engine().connect() as conn:
        conn.execute(sa.text("PRAGMA foreign_keys = OFF"))
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(sa.delete(table))
        conn.execute(sa.text("PRAGMA foreign_keys = ON"))
        conn.commit()


@pytest.fixture(scope="session", autouse=True)
def _shared_db(tmp_path_factory):
    """Initialize schema once per session; all tests share the same SQLite file."""
    db_dir = tmp_path_factory.mktemp("shared_db")
    db_path = db_dir / "yggdrasil-shared.db"
    os.environ["YGGDRASIL_DATABASE_URL"] = f"sqlite+pysqlite:///{db_path.as_posix()}"
    os.environ["YGGDRASIL_AUTO_CREATE_SCHEMA"] = "0"
    os.environ["YGGDRASIL_COORDINATION_BACKEND"] = "memory"
    os.environ["YGGDRASIL_REDIS_URL"] = "redis://127.0.0.1:6390/15"
    reset_persistence_runtime()
    initialize_schema()
    yield
    reset_persistence_runtime()


@pytest.fixture(autouse=True)
def persistence_env(_shared_db, tmp_path, monkeypatch):
    state_root = tmp_path / "yggdrasil-state"
    state_dir = state_root / "state"
    monkeypatch.setenv("YGGDRASIL_STATE_ROOT", state_root.as_posix())
    monkeypatch.setenv("YGGDRASIL_DISABLE_LIVE_LLM", "1")
    reset_persistence_runtime()
    invalidate_application_catalog_cache()
    invalidate_catalog_cache()
    invalidate_prompt_registry_cache()
    invalidate_tool_descriptor_cache()
    _truncate_all_tables()
    ensure_workspace_bootstrap()
    RedisCoordinator(get_persistence_runtime().settings).flushdb()
    yield
    close_mcp_bridge_sessions()
    reset_persistence_runtime()
    if state_dir.exists():
        shutil.rmtree(state_dir)
