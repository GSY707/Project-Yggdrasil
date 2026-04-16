from __future__ import annotations

import shutil

import pytest

from yggdrasil_sdk import ensure_workspace_bootstrap, get_persistence_runtime, initialize_schema, reset_persistence_runtime
from yggdrasil_sdk.persistence.coordination import RedisCoordinator
from yggdrasil_sdk.support import resolve_workspace_root


@pytest.fixture(autouse=True)
def persistence_env(tmp_path, monkeypatch):
    database_path = tmp_path / "yggdrasil-test.db"
    workspace_root = resolve_workspace_root()
    state_root = workspace_root / ".yggdrasil"
    state_dir = state_root / "state"
    backup_dir = tmp_path / "state-backup"
    if state_dir.exists():
        shutil.copytree(state_dir, backup_dir)
    monkeypatch.setenv("YGGDRASIL_DATABASE_URL", f"sqlite+pysqlite:///{database_path.as_posix()}")
    monkeypatch.setenv("YGGDRASIL_AUTO_CREATE_SCHEMA", "1")
    monkeypatch.setenv("YGGDRASIL_REDIS_URL", "redis://127.0.0.1:6390/15")
    reset_persistence_runtime()
    initialize_schema()
    ensure_workspace_bootstrap()
    try:
        RedisCoordinator(get_persistence_runtime().settings).client().flushdb()
    except Exception:
        pass
    yield
    reset_persistence_runtime()
    if state_dir.exists():
        shutil.rmtree(state_dir)
    if backup_dir.exists():
        shutil.copytree(backup_dir, state_dir)