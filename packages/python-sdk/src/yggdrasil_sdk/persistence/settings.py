from __future__ import annotations

from dataclasses import dataclass
import os


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(slots=True)
class PersistenceSettings:
    database_url: str
    redis_url: str
    nats_url: str
    nats_stream: str
    nats_subject_prefix: str
    auto_create_schema: bool
    echo_sql: bool
    queue_namespace: str
    cache_namespace: str
    module_failure_threshold: int

    @classmethod
    def load(cls) -> "PersistenceSettings":
        return cls(
            database_url=os.getenv(
                "YGGDRASIL_DATABASE_URL",
                "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/yggdrasil",
            ),
            redis_url=os.getenv("YGGDRASIL_REDIS_URL", "redis://127.0.0.1:6379/0"),
            nats_url=os.getenv("YGGDRASIL_NATS_URL", "nats://127.0.0.1:4222"),
            nats_stream=os.getenv("YGGDRASIL_NATS_STREAM", "YGGDRASIL"),
            nats_subject_prefix=os.getenv("YGGDRASIL_NATS_SUBJECT_PREFIX", "yggdrasil.events"),
            auto_create_schema=_as_bool(os.getenv("YGGDRASIL_AUTO_CREATE_SCHEMA"), False),
            echo_sql=_as_bool(os.getenv("YGGDRASIL_SQL_ECHO"), False),
            queue_namespace=os.getenv("YGGDRASIL_QUEUE_NAMESPACE", "worker"),
            cache_namespace=os.getenv("YGGDRASIL_CACHE_NAMESPACE", "yggdrasil"),
            module_failure_threshold=max(1, int(os.getenv("YGGDRASIL_MODULE_FAILURE_THRESHOLD", "3"))),
        )