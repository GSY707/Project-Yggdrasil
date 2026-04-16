from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha1
import json
from pathlib import Path
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


def resolve_workspace_root(start: Path | None = None) -> Path:
    cursor = (start or Path(__file__).resolve()).resolve()
    if cursor.is_file():
        cursor = cursor.parent

    for candidate in (cursor, *cursor.parents):
        if (candidate / "services").exists() and (candidate / "modules").exists():
            return candidate

    raise FileNotFoundError("Unable to resolve Project Yggdrasil workspace root.")


def ensure_state_dir(workspace_root: Path | None = None) -> Path:
    state_dir = resolve_workspace_root(workspace_root) / ".yggdrasil" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir


def ensure_state_subdir(name: str, workspace_root: Path | None = None) -> Path:
    path = ensure_state_dir(workspace_root) / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def relative_workspace_path(path: Path, workspace_root: Path | None = None) -> str:
    root = resolve_workspace_root(workspace_root)
    return path.resolve().relative_to(root).as_posix()


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")