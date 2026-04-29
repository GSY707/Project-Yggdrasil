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
_REDIS_FAILURE_CACHE: dict[str, tuple[float, str]] = {}


def reset_memory_coordination() -> None:
    with _MEMORY_MUTEX:
        _MEMORY_CACHE.clear()
        _MEMORY_QUEUES.clear()
        _MEMORY_LOCKS.clear()
        _REDIS_FAILURE_CACHE.clear()


class RedisCoordinator:
    def __init__(self, settings: PersistenceSettings | None = None) -> None:
        self.settings = settings or PersistenceSettings.load()
        self._client: Redis | None = None

    def _failure_cache_key(self) -> str:
        return f"{self.settings.coordination_backend}:{self.settings.redis_url}"

    def _recent_failure(self) -> str | None:
        ttl_seconds = max(0.0, float(self.settings.redis_failure_ttl_seconds))
        if ttl_seconds <= 0:
            return None
        cache_key = self._failure_cache_key()
        now = time.monotonic()
        with _MEMORY_MUTEX:
            cached = _REDIS_FAILURE_CACHE.get(cache_key)
            if cached is None:
                return None
            recorded_at, detail = cached
            if now - recorded_at < ttl_seconds:
                return detail
            _REDIS_FAILURE_CACHE.pop(cache_key, None)
        return None

    def _remember_failure(self, detail: str) -> None:
        with _MEMORY_MUTEX:
            _REDIS_FAILURE_CACHE[self._failure_cache_key()] = (time.monotonic(), detail)

    def _clear_failure(self) -> None:
        with _MEMORY_MUTEX:
            _REDIS_FAILURE_CACHE.pop(self._failure_cache_key(), None)

    def _fallback_backend_label(self) -> str:
        return "memory-fallback" if self.settings.coordination_backend == "auto" else "redis-unavailable"

    def backend(self) -> str:
        configured = self.settings.coordination_backend
        if configured == "memory":
            return "memory"
        if self._client is not None:
            return "redis"
        recent_failure = self._recent_failure()
        if recent_failure is not None:
            return self._fallback_backend_label()
        return configured

    def _build_client(self) -> Redis:
        kwargs: dict[str, Any] = {"decode_responses": True}
        if self.settings.redis_socket_connect_timeout > 0:
            kwargs["socket_connect_timeout"] = self.settings.redis_socket_connect_timeout
        return Redis.from_url(self.settings.redis_url, **kwargs)

    def client(self) -> Redis:
        if self.settings.coordination_backend == "memory":
            raise RuntimeError("Coordination backend is configured to use in-memory mode.")
        if self._client is None:
            recent_failure = self._recent_failure()
            if recent_failure is not None:
                raise RuntimeError(f"Redis coordination is temporarily unavailable: {recent_failure}")
            client = self._build_client()
            try:
                client.ping()
            except Exception as exc:
                client.close()
                self._remember_failure(str(exc))
                raise
            self._clear_failure()
            self._client = client
        return self._client

    def ping(self) -> dict[str, object]:
        if self.settings.coordination_backend == "memory":
            return {
                "status": "ok",
                "redisUrl": self.settings.redis_url,
                "backend": "memory",
                "detail": "Coordination backend is configured to use in-memory mode.",
            }
        try:
            self.client().ping()
            return {"status": "ok", "redisUrl": self.settings.redis_url, "backend": "redis"}
        except Exception as exc:
            self._remember_failure(str(exc))
            return {
                "status": "degraded",
                "redisUrl": self.settings.redis_url,
                "backend": self._fallback_backend_label(),
                "detail": str(exc),
            }

    def flushdb(self) -> dict[str, object]:
        reset_memory_coordination()
        if self.settings.coordination_backend == "memory":
            return {
                "status": "ok",
                "backend": "memory",
                "redisUrl": self.settings.redis_url,
            }
        try:
            self.client().flushdb()
            return {
                "status": "ok",
                "backend": "redis",
                "redisUrl": self.settings.redis_url,
            }
        except Exception as exc:
            self._remember_failure(str(exc))
            return {
                "status": "degraded",
                "backend": self._fallback_backend_label(),
                "redisUrl": self.settings.redis_url,
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
            if timeout_seconds == 0:
                raw = self.client().lpop(queue_key)
                item = (queue_key, raw) if raw is not None else None
            else:
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