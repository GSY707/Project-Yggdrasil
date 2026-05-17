from __future__ import annotations

from dataclasses import dataclass
import os


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_float(value: str | None, default: float) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _coordination_backend(value: str | None) -> str:
    normalized = str(value or "auto").strip().lower()
    if normalized in {"auto", "redis", "memory"}:
        return normalized
    return "auto"


@dataclass(slots=True)
class PersistenceSettings:
    database_url: str
    redis_url: str
    coordination_backend: str
    nats_url: str
    nats_stream: str
    nats_subject_prefix: str
    auto_create_schema: bool
    echo_sql: bool
    queue_namespace: str
    cache_namespace: str
    module_failure_threshold: int
    redis_socket_connect_timeout: float
    redis_failure_ttl_seconds: float
    sqlite_connect_timeout_seconds: float
    sqlite_busy_timeout_ms: int
    sqlite_enable_wal: bool
    sqlite_lock_retry_max_attempts: int
    sqlite_lock_retry_backoff_ms: float
    operation_queue_enabled: bool

    @classmethod
    def load(cls) -> "PersistenceSettings":
        return cls(
            database_url=os.getenv(
                "YGGDRASIL_DATABASE_URL",
                "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/yggdrasil",
            ),
            redis_url=os.getenv("YGGDRASIL_REDIS_URL", "redis://127.0.0.1:6379/0"),
            coordination_backend=_coordination_backend(os.getenv("YGGDRASIL_COORDINATION_BACKEND")),
            nats_url=os.getenv("YGGDRASIL_NATS_URL", "nats://127.0.0.1:4222"),
            nats_stream=os.getenv("YGGDRASIL_NATS_STREAM", "YGGDRASIL"),
            nats_subject_prefix=os.getenv("YGGDRASIL_NATS_SUBJECT_PREFIX", "yggdrasil.events"),
            auto_create_schema=_as_bool(os.getenv("YGGDRASIL_AUTO_CREATE_SCHEMA"), False),
            echo_sql=_as_bool(os.getenv("YGGDRASIL_SQL_ECHO"), False),
            queue_namespace=os.getenv("YGGDRASIL_QUEUE_NAMESPACE", "worker"),
            cache_namespace=os.getenv("YGGDRASIL_CACHE_NAMESPACE", "yggdrasil"),
            module_failure_threshold=max(1, int(os.getenv("YGGDRASIL_MODULE_FAILURE_THRESHOLD", "3"))),
            redis_socket_connect_timeout=max(
                0.0,
                _as_float(os.getenv("YGGDRASIL_REDIS_SOCKET_CONNECT_TIMEOUT"), 0.2),
            ),
            redis_failure_ttl_seconds=max(
                0.0,
                _as_float(os.getenv("YGGDRASIL_REDIS_FAILURE_TTL_SECONDS"), 5.0),
            ),
            sqlite_connect_timeout_seconds=max(
                0.0,
                _as_float(os.getenv("YGGDRASIL_SQLITE_CONNECT_TIMEOUT_SECONDS"), 30.0),
            ),
            sqlite_busy_timeout_ms=max(
                0,
                int(os.getenv("YGGDRASIL_SQLITE_BUSY_TIMEOUT_MS", "30000")),
            ),
            sqlite_enable_wal=_as_bool(os.getenv("YGGDRASIL_SQLITE_ENABLE_WAL"), True),
            sqlite_lock_retry_max_attempts=max(
                1,
                int(os.getenv("YGGDRASIL_SQLITE_LOCK_RETRY_MAX_ATTEMPTS", "3")),
            ),
            sqlite_lock_retry_backoff_ms=max(
                0.0,
                _as_float(os.getenv("YGGDRASIL_SQLITE_LOCK_RETRY_BACKOFF_MS"), 50.0),
            ),
            operation_queue_enabled=_as_bool(os.getenv("YGGDRASIL_OPERATION_QUEUE_ENABLED"), True),
        )