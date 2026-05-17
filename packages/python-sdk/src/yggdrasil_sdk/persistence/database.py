from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache
import time
from typing import Callable, TypeVar

import sqlalchemy as sa
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from .settings import PersistenceSettings


T = TypeVar("T")


def _engine_kwargs(settings: PersistenceSettings) -> dict[str, object]:
    database_url = settings.database_url
    kwargs: dict[str, object] = {"echo": settings.echo_sql, "future": True}
    if database_url.startswith("sqlite"):
        kwargs["connect_args"] = {
            "check_same_thread": False,
            "timeout": settings.sqlite_connect_timeout_seconds,
        }
        if ":memory:" in database_url:
            kwargs["poolclass"] = StaticPool
    return kwargs


def _is_sqlite_lock_error(exc: Exception) -> bool:
    if not isinstance(exc, OperationalError):
        return False
    detail = str(exc).lower()
    return "database is locked" in detail or "database table is locked" in detail


class PersistenceRuntime:
    def __init__(self, settings: PersistenceSettings) -> None:
        self.settings = settings
        self._engine: sa.Engine | None = None
        self._session_factory: sessionmaker[Session] | None = None

    def engine(self) -> sa.Engine:
        if self._engine is None:
            self._engine = sa.create_engine(
                self.settings.database_url,
                **_engine_kwargs(self.settings),
            )
            if self.settings.database_url.startswith("sqlite"):
                busy_timeout_ms = max(0, self.settings.sqlite_busy_timeout_ms)
                enable_wal = self.settings.sqlite_enable_wal

                @sa.event.listens_for(self._engine, "connect")
                def _configure_sqlite_connection(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
                    cursor = dbapi_connection.cursor()
                    try:
                        cursor.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
                        if enable_wal:
                            cursor.execute("PRAGMA journal_mode=WAL")
                            cursor.execute("PRAGMA synchronous=NORMAL")
                    finally:
                        cursor.close()
        return self._engine

    def session_factory(self) -> sessionmaker[Session]:
        if self._session_factory is None:
            self._session_factory = sessionmaker(
                bind=self.engine(),
                autoflush=False,
                expire_on_commit=False,
                future=True,
            )
        return self._session_factory

    @contextmanager
    def session_scope(self) -> Session:
        session = self.session_factory()()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def ping_database(self) -> dict[str, object]:
        try:
            with self.engine().connect() as connection:
                connection.execute(sa.text("SELECT 1"))
            return {"status": "ok", "databaseUrl": self.settings.database_url}
        except Exception as exc:
            return {"status": "error", "databaseUrl": self.settings.database_url, "detail": str(exc)}

    def dispose(self) -> None:
        if self._engine is not None:
            self._engine.dispose()
        self._engine = None
        self._session_factory = None

    def run_with_sqlite_lock_retry(self, operation: Callable[[], T]) -> T:
        attempts = max(1, self.settings.sqlite_lock_retry_max_attempts)
        base_backoff_seconds = max(0.0, self.settings.sqlite_lock_retry_backoff_ms / 1000.0)
        for attempt in range(1, attempts + 1):
            try:
                return operation()
            except Exception as exc:
                if not _is_sqlite_lock_error(exc) or attempt == attempts:
                    raise
                time.sleep(base_backoff_seconds * attempt)


@lru_cache(maxsize=1)
def get_persistence_runtime() -> PersistenceRuntime:
    return PersistenceRuntime(PersistenceSettings.load())


def initialize_schema() -> None:
    from .orm import Base

    runtime = get_persistence_runtime()
    Base.metadata.create_all(runtime.engine())


def reset_persistence_runtime() -> None:
    from .coordination import reset_memory_coordination

    runtime = get_persistence_runtime()
    runtime.dispose()
    get_persistence_runtime.cache_clear()
    reset_memory_coordination()