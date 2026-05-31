from __future__ import annotations

from hashlib import sha1
import json
from pathlib import Path
from time import time
from typing import Any, Callable

from ..support import ensure_state_subdir


def _cache_root() -> Path:
    return ensure_state_subdir("mcp-tool-cache")


def _cache_file_path(namespace: str, cache_key: str) -> Path:
    digest = sha1(cache_key.encode("utf-8")).hexdigest()
    safe_namespace = "".join(char if char.isalnum() else "_" for char in str(namespace or "cache"))
    return _cache_root() / f"{safe_namespace}_{digest}.json"


def _read_cache(path: Path) -> dict[str, Any] | None:
    if not path.exists() or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _write_cache(path: Path, *, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "createdAt": time(),
        "value": value,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def cached_call(
    *,
    namespace: str,
    cache_key: str,
    ttl_seconds: int,
    loader: Callable[[], Any],
) -> tuple[Any, dict[str, Any]]:
    ttl = max(int(ttl_seconds or 0), 0)
    if ttl <= 0:
        return loader(), {"enabled": False, "hit": False, "ttlSeconds": ttl}

    path = _cache_file_path(namespace, cache_key)
    cached = _read_cache(path)
    now = time()
    if cached is not None:
        created_at = float(cached.get("createdAt") or 0.0)
        age = max(now - created_at, 0.0)
        if age <= ttl:
            return cached.get("value"), {
                "enabled": True,
                "hit": True,
                "ttlSeconds": ttl,
                "ageSeconds": round(age, 3),
                "path": str(path),
            }

    value = loader()
    _write_cache(path, value=value)
    return value, {
        "enabled": True,
        "hit": False,
        "ttlSeconds": ttl,
        "ageSeconds": 0.0,
        "path": str(path),
    }
