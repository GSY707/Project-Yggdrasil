import yggdrasil_sdk.persistence.coordination as coordination

from yggdrasil_sdk import RedisCoordinator, reset_persistence_runtime
from yggdrasil_sdk.persistence.settings import PersistenceSettings


def test_memory_coordination_backend_skips_redis(monkeypatch) -> None:
    monkeypatch.setenv("YGGDRASIL_COORDINATION_BACKEND", "memory")
    monkeypatch.setenv("YGGDRASIL_REDIS_URL", "redis://127.0.0.1:6390/15")
    reset_persistence_runtime()

    coordinator = RedisCoordinator(PersistenceSettings.load())
    flush_report = coordinator.flushdb()
    ping_report = coordinator.ping()

    assert flush_report["backend"] == "memory"
    assert ping_report["backend"] == "memory"
    assert ping_report["status"] == "ok"

    reset_persistence_runtime()


def test_auto_coordination_caches_recent_redis_failure(monkeypatch) -> None:
    attempts = {"count": 0}

    class BrokenRedisClient:
        def ping(self) -> None:
            raise RuntimeError("redis-offline")

        def close(self) -> None:
            return None

    class BrokenRedisFactory:
        @staticmethod
        def from_url(*args, **kwargs):
            attempts["count"] += 1
            return BrokenRedisClient()

    monkeypatch.setenv("YGGDRASIL_COORDINATION_BACKEND", "auto")
    monkeypatch.setenv("YGGDRASIL_REDIS_FAILURE_TTL_SECONDS", "60")
    monkeypatch.setattr(coordination, "Redis", BrokenRedisFactory)
    reset_persistence_runtime()

    coordinator = coordination.RedisCoordinator(PersistenceSettings.load())
    first_ping = coordinator.ping()
    second_ping = coordinator.ping()

    assert first_ping["status"] == "degraded"
    assert second_ping["status"] == "degraded"
    assert attempts["count"] == 1

    reset_persistence_runtime()