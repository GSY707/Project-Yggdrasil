from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha1
import json
import os
from pathlib import Path
import re
import shutil
from typing import Any
from uuid import uuid4


_WORD_COUNT_PATTERN = re.compile(r"[A-Za-z0-9]+(?:[._'\-][A-Za-z0-9]+)*|[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


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


def estimate_word_count(value: str) -> int:
    """Estimate a stable cross-language word count.

    Latin text is counted by word-like tokens. Chinese Han characters are counted
    one character per token so markdown/document indexes do not collapse to a
    near-zero count when the text has no spaces.
    """
    return len(_WORD_COUNT_PATTERN.findall(value or ""))


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
    "tmp",
}


def runtime_workspace_copy_ignore(_directory: str, names: list[str]) -> set[str]:
    return {name for name in names if name in _RUNTIME_SANDBOX_IGNORED_NAMES}


def _configured_path(raw_path: str, workspace_root: Path | None = None) -> Path:
    candidate = Path(raw_path).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    return (resolve_workspace_root(workspace_root) / candidate).resolve()


def _runtime_workspace_dynamic_ignored_names(
    directory: str,
    source_root: str,
    configured_candidates: tuple[str, ...],
    names: list[str],
) -> set[str]:
    ignored: set[str] = set()
    normalized_directory = os.path.normcase(os.path.normpath(directory))
    for candidate in configured_candidates:
        if candidate != source_root and not candidate.startswith(source_root + os.sep):
            continue
        candidate_parent = os.path.dirname(candidate)
        candidate_name = os.path.basename(candidate)
        if normalized_directory == candidate_parent and candidate_name in names:
            ignored.add(candidate_name)
    return ignored


def runtime_workspace_copy_ignore_for(source_root: Path):
    resolved_source_root = os.path.normcase(os.path.normpath(str(source_root)))
    configured_candidates: list[str] = []
    for env_key in ("YGGDRASIL_STATE_ROOT", "YGGDRASIL_STATE_DIR"):
        raw_path = str(os.environ.get(env_key) or "").strip()
        if not raw_path:
            continue
        candidate_path = os.path.expanduser(raw_path)
        if os.path.isabs(candidate_path):
            candidate = os.path.normcase(os.path.normpath(candidate_path))
        else:
            candidate = os.path.normcase(os.path.normpath(os.path.join(resolved_source_root, candidate_path)))
        configured_candidates.append(candidate)
    configured_candidates_tuple = tuple(dict.fromkeys(configured_candidates))

    def _ignore(directory: str, names: list[str]) -> set[str]:
        ignored = runtime_workspace_copy_ignore(directory, names)
        ignored.update(
            _runtime_workspace_dynamic_ignored_names(directory, resolved_source_root, configured_candidates_tuple, names)
        )
        return ignored

    return _ignore


def resolve_workspace_root(start: Path | None = None) -> Path:
    cursor = (start or Path(__file__).resolve()).resolve()
    if cursor.is_file():
        cursor = cursor.parent

    for candidate in (cursor, *cursor.parents):
        if (candidate / "services").exists() and (candidate / "modules").exists():
            return candidate

    raise FileNotFoundError("Unable to resolve Project Yggdrasil workspace root.")


def load_workspace_dotenv(workspace_root: Path | None = None, *, override: bool = False) -> Path | None:
    env_path = resolve_workspace_root(workspace_root) / ".env"
    if not env_path.exists():
        return None

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            stripped = stripped[7:].lstrip()
        if "=" not in stripped:
            continue

        key, value = stripped.split("=", 1)
        key = key.strip()
        if not key:
            continue

        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]

        existing = os.environ.get(key)
        if not override and existing not in {None, ""}:
            continue
        os.environ[key] = value

    return env_path


def prepare_runtime_workspace_sandbox(destination_root: Path, workspace_root: Path | None = None) -> Path:
    source_root = resolve_workspace_root(workspace_root)
    sandbox_workspace = destination_root / "workspace"
    shutil.copytree(source_root, sandbox_workspace, ignore=runtime_workspace_copy_ignore_for(source_root))
    return sandbox_workspace


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