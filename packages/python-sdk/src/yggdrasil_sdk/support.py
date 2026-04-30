from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha1
import json
import os
from pathlib import Path
import shutil
from typing import Any
from uuid import uuid4


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def new_id(prefix: str, *parts: object, stable: bool = False) -> str:
    normalized = "::".join(str(part) for part in parts if part is not None)
    if stable and normalized:
        digest = sha1(normalized.encode("utf-8")).hexdigest()[:20]
        return f"{prefix}_{digest}"
    return f"{prefix}_{uuid4().hex[:20]}"


def normalize_excerpt(value: str, limit: int) -> str:
    compact = " ".join(value.split())
    if len(compact) <= limit:
        return compact
    return compact[: max(limit - 1, 1)].rstrip() + "…"


_RUNTIME_SANDBOX_IGNORED_NAMES = {
    ".git",
    ".next",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    ".yggdrasil",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "node_modules",
}


def runtime_workspace_copy_ignore(_directory: str, names: list[str]) -> set[str]:
    return {name for name in names if name in _RUNTIME_SANDBOX_IGNORED_NAMES}


def resolve_workspace_root(start: Path | None = None) -> Path:
    cursor = (start or Path(__file__).resolve()).resolve()
    if cursor.is_file():
        cursor = cursor.parent

    for candidate in (cursor, *cursor.parents):
        if (candidate / "services").exists() and (candidate / "modules").exists():
            return candidate

    raise FileNotFoundError("Unable to resolve Project Yggdrasil workspace root.")


def prepare_runtime_workspace_sandbox(destination_root: Path, workspace_root: Path | None = None) -> Path:
    source_root = resolve_workspace_root(workspace_root)
    sandbox_workspace = destination_root / "workspace"
    shutil.copytree(source_root, sandbox_workspace, ignore=runtime_workspace_copy_ignore)
    return sandbox_workspace


def _configured_path(raw_path: str, workspace_root: Path | None = None) -> Path:
    candidate = Path(raw_path).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    return (resolve_workspace_root(workspace_root) / candidate).resolve()


def resolve_state_root(workspace_root: Path | None = None) -> Path:
    configured_root = os.environ.get("YGGDRASIL_STATE_ROOT")
    if configured_root:
        return _configured_path(configured_root, workspace_root)
    return resolve_workspace_root(workspace_root) / ".yggdrasil"


def resolve_state_dir(workspace_root: Path | None = None) -> Path:
    configured_dir = os.environ.get("YGGDRASIL_STATE_DIR")
    if configured_dir:
        return _configured_path(configured_dir, workspace_root)
    return resolve_state_root(workspace_root) / "state"


def ensure_state_dir(workspace_root: Path | None = None) -> Path:
    state_dir = resolve_state_dir(workspace_root)
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir


def ensure_state_subdir(name: str, workspace_root: Path | None = None) -> Path:
    path = ensure_state_dir(workspace_root) / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def relative_workspace_path(path: Path, workspace_root: Path | None = None) -> str:
    root = resolve_workspace_root(workspace_root)
    resolved_path = path.resolve()
    try:
        return resolved_path.relative_to(root).as_posix()
    except ValueError:
        return resolved_path.as_posix()


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def append_jsonl(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def read_jsonl(path: Path, *, limit: int | None = None) -> list[Any]:
    if not path.exists():
        return []
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if limit is not None and limit >= 0:
        return rows[-limit:]
    return rows