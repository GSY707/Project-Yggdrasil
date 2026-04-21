from __future__ import annotations

import json
import time
from collections import defaultdict, deque
from threading import RLock
from typing import Any

from redis import Redis

from .settings import PersistenceSettings


_MEMORY_MUTEX = RLock()
_MEMORY_CACHE: dict[str, str] = {}
_MEMORY_QUEUES: dict[str, deque[str]] = defaultdict(deque)
_MEMORY_LOCKS: dict[str, tuple[str, float]] = {}


def reset_memory_coordination() -> None:
    with _MEMORY_MUTEX:
        _MEMORY_CACHE.clear()
        _MEMORY_QUEUES.clear()
        _MEMORY_LOCKS.clear()


class RedisCoordinator:
    def __init__(self, settings: PersistenceSettings | None = None) -> None:
        self.settings = settings or PersistenceSettings.load()
        self._client: Redis | None = None

    def client(self) -> Redis:
        if self._client is None:
            self._client = Redis.from_url(self.settings.redis_url, decode_responses=True)
        return self._client

    def ping(self) -> dict[str, object]:
        try:
            self.client().ping()
            return {"status": "ok", "redisUrl": self.settings.redis_url}
        except Exception as exc:
            return {
                "status": "degraded",
                "redisUrl": self.settings.redis_url,
                "backend": "memory-fallback",
                "detail": str(exc),
            }

    def cache_json(self, key: str, payload: Any, ttl_seconds: int | None = None) -> None:
        namespaced_key = f"{self.settings.cache_namespace}:cache:{key}"
        serialized = json.dumps(payload, ensure_ascii=False)
        try:
            self.client().set(namespaced_key, serialized, ex=ttl_seconds)
        except Exception:
            with _MEMORY_MUTEX:
                _MEMORY_CACHE[namespaced_key] = serialized

    def load_json(self, key: str) -> Any | None:
        namespaced_key = f"{self.settings.cache_namespace}:cache:{key}"
        try:
            value = self.client().get(namespaced_key)
        except Exception:
            with _MEMORY_MUTEX:
                value = _MEMORY_CACHE.get(namespaced_key)
        if value is None:
            return None
        return json.loads(value)

    def acquire_lock(self, key: str, owner: str, ttl_seconds: int = 30) -> bool:
        lock_key = f"{self.settings.cache_namespace}:lock:{key}"
        try:
            return bool(self.client().set(lock_key, owner, ex=ttl_seconds, nx=True))
        except Exception:
            expires_at = time.monotonic() + ttl_seconds
            with _MEMORY_MUTEX:
                current = _MEMORY_LOCKS.get(lock_key)
                if current is not None and current[1] > time.monotonic() and current[0] != owner:
                    return False
                _MEMORY_LOCKS[lock_key] = (owner, expires_at)
                return True

    def release_lock(self, key: str, owner: str) -> bool:
        lock_key = f"{self.settings.cache_namespace}:lock:{key}"
        try:
            client = self.client()
            if client.get(lock_key) != owner:
                return False
            client.delete(lock_key)
            return True
        except Exception:
            with _MEMORY_MUTEX:
                current = _MEMORY_LOCKS.get(lock_key)
                if current is None or current[0] != owner:
                    return False
                _MEMORY_LOCKS.pop(lock_key, None)
                return True

    def enqueue_job(self, queue: str, payload: Any) -> int:
        queue_key = f"{self.settings.queue_namespace}:{queue}"
        serialized = json.dumps(payload, ensure_ascii=False)
        try:
            return int(self.client().rpush(queue_key, serialized))
        except Exception:
            with _MEMORY_MUTEX:
                _MEMORY_QUEUES[queue_key].append(serialized)
                return len(_MEMORY_QUEUES[queue_key])

    def pop_job(self, queue: str, timeout_seconds: int = 1) -> Any | None:
        queue_key = f"{self.settings.queue_namespace}:{queue}"
        try:
            item = self.client().blpop(queue_key, timeout=timeout_seconds)
            if item is None:
                return None
            _, payload = item
            return json.loads(payload)
        except Exception:
            with _MEMORY_MUTEX:
                if not _MEMORY_QUEUES[queue_key]:
                    return None
                return json.loads(_MEMORY_QUEUES[queue_key].popleft())

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
        self._client = None