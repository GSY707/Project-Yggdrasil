from __future__ import annotations

from datetime import datetime
import json
import os
import shlex
import shutil
import socket
import subprocess
from pathlib import Path
from typing import Any

from sqlalchemy.engine import make_url

from .persistence import reset_persistence_runtime
from .persistence.settings import PersistenceSettings
from .support import prepare_runtime_workspace_sandbox, resolve_state_root, resolve_workspace_root, utc_now, write_json


_REAL_USER_VALIDATION_MATERIALS = (
    Path("docs/research/real-user-validation-plan-2026-04-30.md"),
    Path("docs/research/real-user-validation-baseline-freeze-2026-04-30.md"),
    Path("docs/research/real-user-validation-internal-pilot-deepseek-2026-04-30.md"),
    Path("evaluation/fixtures/real-user-validation/task-pack-2026-04-30.md"),
    Path("evaluation/fixtures/real-user-validation/scorecard-template-2026-04-30.csv"),
)


def _port_from_env(name: str, default: int) -> int:
    raw = str(os.environ.get(name) or default).strip()
    try:
        return int(raw)
    except ValueError:
        return default


def resolve_backup_root(workspace_root: Path | None = None) -> Path:
    return resolve_workspace_root(workspace_root) / ".yggdrasil-backups"


def resolve_real_user_validation_root(workspace_root: Path | None = None) -> Path:
    workspace = resolve_workspace_root(workspace_root)
    return workspace.parent / f"{workspace.name}-real-user-validation"


def _timestamp_slug() -> str:
    return utc_now().strftime("%Y%m%dT%H%M%SZ")


def _default_snapshot_dir(workspace_root: Path | None = None) -> Path:
    return resolve_backup_root(workspace_root) / _timestamp_slug()


def _default_real_user_validation_sandbox_dir(workspace_root: Path | None = None) -> Path:
    return resolve_real_user_validation_root(workspace_root) / _timestamp_slug()


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


def _run_git_command(repo_path: Path, *args: str) -> str:
    completed = subprocess.run(["git", "-C", str(repo_path), *args], capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "git command failed"
        raise RuntimeError(detail)
    return completed.stdout.strip()


def _powershell_quote(value: str) -> str:
    return value.replace("`", "``").replace('"', '`"')


def _copy_real_user_validation_materials(materials_root: Path, workspace_root: Path) -> list[dict[str, str]]:
    copied: list[dict[str, str]] = []
    for relative_path in _REAL_USER_VALIDATION_MATERIALS:
        source_path = (workspace_root / relative_path).resolve()
        if not source_path.exists():
            raise FileNotFoundError(f"Real-user validation material missing: {source_path}")
        target_path = (materials_root / relative_path).resolve()
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)
        copied.append(
            {
                "relativePath": relative_path.as_posix(),
                "source": str(source_path),
                "copiedTo": str(target_path),
            }
        )
    return copied


def _initialize_sandbox_git_repo(repo_path: Path) -> dict[str, str]:
    _run_git_command(repo_path, "init", "-b", "main")
    _run_git_command(repo_path, "config", "user.name", "Yggdrasil Pilot")
    _run_git_command(repo_path, "config", "user.email", "pilot@yggdrasil.local")
    _run_git_command(repo_path, "add", ".")
    _run_git_command(repo_path, "commit", "-m", "sandbox snapshot")
    return {
        "branch": _run_git_command(repo_path, "branch", "--show-current"),
        "head": _run_git_command(repo_path, "rev-parse", "HEAD"),
    }


def _write_real_user_activation_scripts(sandbox_root: Path, workspace_path: Path, env_vars: dict[str, str], *, disable_live_llm: bool) -> dict[str, str]:
    powershell_path = sandbox_root / "activate.ps1"
    powershell_lines = [
        "$ErrorActionPreference = \"Stop\"",
        "Remove-Item Env:YGGDRASIL_STATE_DIR -ErrorAction SilentlyContinue",
    ]
    for key, value in env_vars.items():
        powershell_lines.append(f'$env:{key} = "{_powershell_quote(value)}"')
    if disable_live_llm:
        powershell_lines.append('$env:YGGDRASIL_DISABLE_LIVE_LLM = "1"')
    else:
        powershell_lines.append("Remove-Item Env:YGGDRASIL_DISABLE_LIVE_LLM -ErrorAction SilentlyContinue")
    powershell_lines.append(f'Set-Location "{_powershell_quote(str(workspace_path))}"')
    powershell_lines.append('Write-Host "Real-user validation sandbox ready."')
    powershell_path.write_text("\n".join(powershell_lines) + "\n", encoding="utf-8")

    shell_path = sandbox_root / "activate.sh"
    shell_lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "unset YGGDRASIL_STATE_DIR || true",
    ]
    for key, value in env_vars.items():
        shell_lines.append(f"export {key}={shlex.quote(value)}")
    if disable_live_llm:
        shell_lines.append("export YGGDRASIL_DISABLE_LIVE_LLM=1")
    else:
        shell_lines.append("unset YGGDRASIL_DISABLE_LIVE_LLM || true")
    shell_lines.append(f"cd {shlex.quote(str(workspace_path))}")
    shell_lines.append("printf 'Real-user validation sandbox ready.\\n'")
    shell_path.write_text("\n".join(shell_lines) + "\n", encoding="utf-8")

    return {
        "powershell": str(powershell_path),
        "shell": str(shell_path),
    }


def _write_real_user_validation_readme(sandbox_root: Path, manifest_path: Path) -> Path:
    readme_path = sandbox_root / "README.md"
    readme_path.write_text(
        "# Real User Validation Sandbox\n\n"
        "This directory is an isolated runtime sandbox for internal pilot runs.\n\n"
        "## Contents\n\n"
        "- workspace/: copied Project Yggdrasil workspace snapshot\n"
        "- .yggdrasil/: isolated runtime state root and sqlite database target\n"
        "- materials/: frozen task pack, scorecard, and validation research notes\n"
        "- activate.ps1 / activate.sh: environment activation scripts\n"
        f"- sandbox-manifest.json: generated manifest ({manifest_path.name})\n",
        encoding="utf-8",
    )
    return readme_path


def prepare_real_user_validation_sandbox(*, workspace_root: Path | None = None, output_dir: Path | None = None, disable_live_llm: bool = False) -> dict[str, Any]:
    workspace = resolve_workspace_root(workspace_root)
    sandbox_root = (output_dir or _default_real_user_validation_sandbox_dir(workspace_root)).expanduser().resolve()
    try:
        sandbox_root.relative_to(workspace)
    except ValueError:
        pass
    else:
        raise ValueError(f"Sandbox output must be outside the workspace root: {sandbox_root}")

    if sandbox_root.exists() and any(sandbox_root.iterdir()):
        raise FileExistsError(f"Sandbox output directory already exists and is not empty: {sandbox_root}")

    sandbox_root.mkdir(parents=True, exist_ok=True)
    state_root = sandbox_root / ".yggdrasil"
    state_root.mkdir(parents=True, exist_ok=True)
    sandbox_workspace = prepare_runtime_workspace_sandbox(sandbox_root, workspace)
    materials = _copy_real_user_validation_materials(sandbox_root / "materials", workspace)
    git_summary = _initialize_sandbox_git_repo(sandbox_workspace)
    env_vars = {
        "YGGDRASIL_DATABASE_URL": f"sqlite+pysqlite:///{(state_root / 'runtime.db').resolve().as_posix()}",
        "YGGDRASIL_AUTO_CREATE_SCHEMA": "1",
        "YGGDRASIL_COORDINATION_BACKEND": "memory",
        "YGGDRASIL_REDIS_URL": "redis://127.0.0.1:6390/15",
        "YGGDRASIL_STATE_ROOT": str(state_root.resolve()),
        "YGGDRASIL_GIT_REPO_PATH": str(sandbox_workspace.resolve()),
        "YGGDRASIL_MCP_PROJECT_WORKSPACE": str(sandbox_workspace.resolve()),
    }
    activation_scripts = _write_real_user_activation_scripts(sandbox_root, sandbox_workspace, env_vars, disable_live_llm=disable_live_llm)
    manifest_path = sandbox_root / "sandbox-manifest.json"
    readme_path = _write_real_user_validation_readme(sandbox_root, manifest_path)
    manifest = {
        "createdAt": utc_now().isoformat(),
        "status": "ready",
        "sandboxRoot": str(sandbox_root),
        "sourceWorkspace": str(workspace),
        "workspaceRoot": str(sandbox_workspace.resolve()),
        "stateRoot": str(state_root.resolve()),
        "materialsRoot": str((sandbox_root / "materials").resolve()),
        "workspaceIsolationConfirmed": True,
        "env": env_vars,
        "disableLiveLlm": disable_live_llm,
        "activationScripts": activation_scripts,
        "git": git_summary,
        "materials": materials,
        "readme": str(readme_path),
    }
    write_json(manifest_path, manifest)
    return manifest


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