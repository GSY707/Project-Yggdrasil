from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from sqlalchemy.engine import make_url

from .shared import _default_snapshot_dir, _run_command, latest_snapshot_dir
from ..persistence import reset_persistence_runtime
from ..persistence.settings import PersistenceSettings
from ..support import resolve_state_root, utc_now, write_json


def _sqlite_database_path(database_url: str) -> Path:
    url = make_url(database_url)
    if not url.drivername.startswith("sqlite"):
        raise ValueError("Database is not sqlite.")
    if url.database in {None, "", ":memory:"}:
        raise ValueError("SQLite in-memory databases cannot be snapshotted.")
    return Path(url.database).resolve()


def create_runtime_backup(*, workspace_root: Path | None = None, snapshot_dir: Path | None = None) -> dict[str, Any]:
    settings = PersistenceSettings.load()
    snapshot_path = (snapshot_dir or _default_snapshot_dir(workspace_root)).resolve()
    snapshot_path.mkdir(parents=True, exist_ok=True)
    metadata: dict[str, Any] = {
        "createdAt": utc_now().isoformat(),
        "databaseUrl": settings.database_url,
        "snapshotDir": str(snapshot_path),
    }
    reset_persistence_runtime()

    url = make_url(settings.database_url)
    database_kind = url.get_backend_name()
    if database_kind == "sqlite":
        source_db = _sqlite_database_path(settings.database_url)
        target_db = snapshot_path / "database.sqlite"
        target_db.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_db, target_db)
        metadata["databaseKind"] = "sqlite"
        metadata["databaseSnapshot"] = str(target_db)
    elif database_kind == "postgresql":
        target_dump = snapshot_path / "database.sql"
        _run_command(["pg_dump", settings.database_url, "--clean", "--if-exists", "-f", str(target_dump)])
        metadata["databaseKind"] = "postgresql"
        metadata["databaseSnapshot"] = str(target_dump)
    else:
        raise RuntimeError(f"Unsupported database backend for backup: {database_kind}")

    state_root = resolve_state_root(workspace_root)
    state_snapshot = snapshot_path / "state-root"
    if state_root.exists():
        shutil.copytree(state_root, state_snapshot, dirs_exist_ok=True)
        metadata["stateSnapshot"] = str(state_snapshot)
    else:
        metadata["stateSnapshot"] = None

    metadata_path = snapshot_path / "metadata.json"
    write_json(metadata_path, metadata)
    return metadata


def restore_runtime_backup(*, workspace_root: Path | None = None, snapshot_dir: Path | None = None) -> dict[str, Any]:
    settings = PersistenceSettings.load()
    snapshot_path = (snapshot_dir or latest_snapshot_dir(workspace_root)).resolve()
    metadata_path = snapshot_path / "metadata.json"
    if not metadata_path.exists():
        raise FileNotFoundError(f"Backup metadata missing: {metadata_path}")

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    database_kind = str(metadata.get("databaseKind") or make_url(settings.database_url).get_backend_name())
    reset_persistence_runtime()

    if database_kind == "sqlite":
        source_db = snapshot_path / "database.sqlite"
        target_db = _sqlite_database_path(settings.database_url)
        if not source_db.exists():
            raise FileNotFoundError(f"Backup sqlite database missing: {source_db}")
        target_db.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_db, target_db)
    elif database_kind == "postgresql":
        source_dump = snapshot_path / "database.sql"
        if not source_dump.exists():
            raise FileNotFoundError(f"Backup postgres dump missing: {source_dump}")
        _run_command(["psql", settings.database_url, "-f", str(source_dump)])
    else:
        raise RuntimeError(f"Unsupported database backend for restore: {database_kind}")

    state_root = resolve_state_root(workspace_root)
    source_state_root = snapshot_path / "state-root"
    if source_state_root.exists():
        if state_root.exists():
            shutil.rmtree(state_root)
        shutil.copytree(source_state_root, state_root, dirs_exist_ok=True)

    restored = dict(metadata)
    restored["restoredAt"] = utc_now().isoformat()
    return restored

__all__ = [name for name in globals() if not name.startswith("__")]
