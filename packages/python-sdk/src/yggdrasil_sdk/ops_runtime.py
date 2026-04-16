from __future__ import annotations

from datetime import datetime
import json
import os
import shutil
import socket
import subprocess
from pathlib import Path
from typing import Any

from sqlalchemy.engine import make_url

from .persistence import reset_persistence_runtime
from .persistence.settings import PersistenceSettings
from .support import resolve_state_root, resolve_workspace_root, utc_now, write_json


def _port_from_env(name: str, default: int) -> int:
    raw = str(os.environ.get(name) or default).strip()
    try:
        return int(raw)
    except ValueError:
        return default


def resolve_backup_root(workspace_root: Path | None = None) -> Path:
    return resolve_workspace_root(workspace_root) / ".yggdrasil-backups"


def _timestamp_slug() -> str:
    return utc_now().strftime("%Y%m%dT%H%M%SZ")


def _default_snapshot_dir(workspace_root: Path | None = None) -> Path:
    return resolve_backup_root(workspace_root) / _timestamp_slug()


def latest_snapshot_dir(workspace_root: Path | None = None) -> Path:
    backup_root = resolve_backup_root(workspace_root)
    if not backup_root.exists():
        raise FileNotFoundError("No runtime backup snapshots were found.")
    candidates = sorted((path for path in backup_root.iterdir() if path.is_dir()), key=lambda path: path.name, reverse=True)
    if not candidates:
        raise FileNotFoundError("No runtime backup snapshots were found.")
    return candidates[0]


def _run_command(command: list[str]) -> None:
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "command failed"
        raise RuntimeError(detail)


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


def _docker_compose_command(workspace_root: Path | None = None) -> list[str]:
    compose_path = resolve_workspace_root(workspace_root) / "infra" / "docker-compose.yml"
    return ["docker", "compose", "-f", str(compose_path)]


def _tcp_check(port: int, *, host: str = "127.0.0.1", timeout: float = 1.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def run_compose_smoke(*, workspace_root: Path | None = None, ensure_up: bool = False) -> dict[str, Any]:
    command = _docker_compose_command(workspace_root)
    if ensure_up:
        _run_command([*command, "up", "-d"])

    services_output = subprocess.run([*command, "config", "--services"], capture_output=True, text=True, check=False)
    if services_output.returncode != 0:
        detail = services_output.stderr.strip() or services_output.stdout.strip() or "docker compose config failed"
        raise RuntimeError(detail)
    declared_services = [line.strip() for line in services_output.stdout.splitlines() if line.strip()]

    running_output = subprocess.run([*command, "ps", "--services", "--status", "running"], capture_output=True, text=True, check=False)
    if running_output.returncode != 0:
        detail = running_output.stderr.strip() or running_output.stdout.strip() or "docker compose ps failed"
        raise RuntimeError(detail)
    running_services = {line.strip() for line in running_output.stdout.splitlines() if line.strip()}

    port_checks = {
        "postgres": _port_from_env("YGGDRASIL_POSTGRES_PORT", 5432),
        "redis": _port_from_env("YGGDRASIL_REDIS_PORT", 6379),
        "nats": _port_from_env("YGGDRASIL_NATS_PORT", 4222),
        "minio": _port_from_env("YGGDRASIL_MINIO_API_PORT", 9000),
        "temporal": _port_from_env("YGGDRASIL_TEMPORAL_PORT", 7233),
        "temporal-ui": _port_from_env("YGGDRASIL_TEMPORAL_UI_PORT", 8088),
        "otel-collector": _port_from_env("YGGDRASIL_OTEL_COLLECTOR_HTTP_PORT", 4318),
        "jaeger": _port_from_env("YGGDRASIL_JAEGER_UI_PORT", 16686),
    }
    checks = [
        {
            "service": service,
            "declared": service in declared_services,
            "running": service in running_services,
            "port": port,
            "reachable": _tcp_check(port),
        }
        for service, port in port_checks.items()
    ]
    status = "ok" if all(item["declared"] and item["running"] and item["reachable"] for item in checks) else "degraded"
    return {
        "generatedAt": utc_now().isoformat(),
        "status": status,
        "declaredServices": declared_services,
        "runningServices": sorted(running_services),
        "checks": checks,
    }