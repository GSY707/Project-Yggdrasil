from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path

from .support import resolve_workspace_root, utc_now


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


def _powershell_file_command(script_path: Path) -> str:
    return f'pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File "{_powershell_quote(str(script_path.resolve()))}"'


def _shell_file_command(script_path: Path) -> str:
    return f"bash {shlex.quote(str(script_path.resolve()))}"