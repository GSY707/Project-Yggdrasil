from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from .settings import PersistenceSettings


def _engine_kwargs(database_url: str, echo_sql: bool) -> dict[str, object]:
    kwargs: dict[str, object] = {"echo": echo_sql, "future": True}
    if database_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if ":memory:" in database_url:
            kwargs["poolclass"] = StaticPool
    return kwargs


class PersistenceRuntime:
    def __init__(self, settings: PersistenceSettings) -> None:
        self.settings = settings
        self._engine: sa.Engine | None = None
        self._session_factory: sessionmaker[Session] | None = None

    def engine(self) -> sa.Engine:
        if self._engine is None:
            self._engine = sa.create_engine(
                self.settings.database_url,
                **_engine_kwargs(self.settings.database_url, self.settings.echo_sql),
            )
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