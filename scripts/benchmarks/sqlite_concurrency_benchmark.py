from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import statistics
import tempfile
import threading
import time
from typing import Any

from yggdrasil_sdk import (
    TaskRepository,
    ensure_workspace_bootstrap,
    get_persistence_runtime,
    initialize_schema,
    reset_persistence_runtime,
)
from yggdrasil_sdk.contracts import BudgetState
from yggdrasil_sdk.persistence.constants import DEFAULT_APP_ID, DEFAULT_BRANCH_ID, DEFAULT_PROJECT_ID, DEFAULT_SPACE_ID
from yggdrasil_sdk.persistence.repositories import NodeRepository
from yggdrasil_sdk.support import utc_now


@dataclass
class ScenarioResult:
    scenario: str
    workers: int
    iterations_per_worker: int
    attempted_ops: int
    success_ops: int
    lock_errors: int
    other_errors: int
    duration_seconds: float
    throughput_ops_per_s: float
    p95_latency_ms: float


@dataclass
class BenchmarkResult:
    profile: str
    database_url: str
    queue_enabled: bool
    wal_enabled: bool
    retry_attempts: int
    busy_timeout_ms: int
    scenarios: list[ScenarioResult]


class StatsCollector:
    def __init__(self, total_ops: int) -> None:
        self._total_ops = total_ops
        self._lock = threading.Lock()
        self.success_ops = 0
        self.lock_errors = 0
        self.other_errors = 0
        self.latencies_ms: list[float] = []

    def record(self, latency_ms: float, exc: Exception | None) -> None:
        with self._lock:
            self.latencies_ms.append(latency_ms)
            if exc is None:
                self.success_ops += 1
            else:
                message = str(exc).lower()
                if "database is locked" in message or "database table is locked" in message:
                    self.lock_errors += 1
                else:
                    self.other_errors += 1

    def to_result(self, *, scenario: str, workers: int, iterations_per_worker: int, duration_seconds: float) -> ScenarioResult:
        throughput = self._total_ops / duration_seconds if duration_seconds > 0 else 0.0
        if self.latencies_ms:
            quantiles = statistics.quantiles(self.latencies_ms, n=20, method="inclusive")
            p95_latency_ms = quantiles[-1]
        else:
            p95_latency_ms = 0.0
        return ScenarioResult(
            scenario=scenario,
            workers=workers,
            iterations_per_worker=iterations_per_worker,
            attempted_ops=self._total_ops,
            success_ops=self.success_ops,
            lock_errors=self.lock_errors,
            other_errors=self.other_errors,
            duration_seconds=duration_seconds,
            throughput_ops_per_s=throughput,
            p95_latency_ms=p95_latency_ms,
        )


def _set_profile_env(profile: str) -> dict[str, str | None]:
    tracked = {
        "YGGDRASIL_DATABASE_URL": os.environ.get("YGGDRASIL_DATABASE_URL"),
        "YGGDRASIL_AUTO_CREATE_SCHEMA": os.environ.get("YGGDRASIL_AUTO_CREATE_SCHEMA"),
        "YGGDRASIL_SQLITE_ENABLE_WAL": os.environ.get("YGGDRASIL_SQLITE_ENABLE_WAL"),
        "YGGDRASIL_SQLITE_BUSY_TIMEOUT_MS": os.environ.get("YGGDRASIL_SQLITE_BUSY_TIMEOUT_MS"),
        "YGGDRASIL_SQLITE_LOCK_RETRY_MAX_ATTEMPTS": os.environ.get("YGGDRASIL_SQLITE_LOCK_RETRY_MAX_ATTEMPTS"),
        "YGGDRASIL_SQLITE_LOCK_RETRY_BACKOFF_MS": os.environ.get("YGGDRASIL_SQLITE_LOCK_RETRY_BACKOFF_MS"),
        "YGGDRASIL_OPERATION_QUEUE_ENABLED": os.environ.get("YGGDRASIL_OPERATION_QUEUE_ENABLED"),
    }

    if profile == "baseline":
        os.environ["YGGDRASIL_OPERATION_QUEUE_ENABLED"] = "0"
        os.environ["YGGDRASIL_SQLITE_ENABLE_WAL"] = "0"
        os.environ["YGGDRASIL_SQLITE_BUSY_TIMEOUT_MS"] = "1000"
        os.environ["YGGDRASIL_SQLITE_LOCK_RETRY_MAX_ATTEMPTS"] = "1"
        os.environ["YGGDRASIL_SQLITE_LOCK_RETRY_BACKOFF_MS"] = "0"
    elif profile == "optimized":
        os.environ["YGGDRASIL_OPERATION_QUEUE_ENABLED"] = "1"
        os.environ["YGGDRASIL_SQLITE_ENABLE_WAL"] = "1"
        os.environ["YGGDRASIL_SQLITE_BUSY_TIMEOUT_MS"] = "30000"
        os.environ["YGGDRASIL_SQLITE_LOCK_RETRY_MAX_ATTEMPTS"] = "3"
        os.environ["YGGDRASIL_SQLITE_LOCK_RETRY_BACKOFF_MS"] = "50"
    else:
        raise ValueError(f"Unsupported profile: {profile}")

    return tracked


def _restore_env(previous: dict[str, str | None]) -> None:
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def _run_node_write_scenario(workers: int, iterations_per_worker: int) -> ScenarioResult:
    total_ops = workers * iterations_per_worker
    stats = StatsCollector(total_ops)
    runtime = get_persistence_runtime()

    def _worker(worker_idx: int) -> None:
        for iteration in range(iterations_per_worker):
            t0 = time.perf_counter()
            err: Exception | None = None
            try:
                with runtime.session_scope() as session:
                    node_repo = NodeRepository(session)
                    node_repo.create_node(
                        {
                            "projectId": DEFAULT_PROJECT_ID,
                            "spaceId": DEFAULT_SPACE_ID,
                            "branchId": DEFAULT_BRANCH_ID,
                            "nodeType": "detail",
                            "title": f"bench-node-{worker_idx}-{iteration}",
                            "content": "benchmark content",
                            "importance": 0.5,
                        }
                    )
            except Exception as exc:  # noqa: BLE001
                err = exc
            finally:
                latency_ms = (time.perf_counter() - t0) * 1000.0
                stats.record(latency_ms, err)

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for worker_idx in range(workers):
            executor.submit(_worker, worker_idx)
    duration = time.perf_counter() - started
    return stats.to_result(
        scenario="node_write_contention",
        workers=workers,
        iterations_per_worker=iterations_per_worker,
        duration_seconds=duration,
    )


def _prepare_task_update_seed() -> str:
    runtime = get_persistence_runtime()
    task_id = "bench_snapshot_task"
    with runtime.session_scope() as session:
        repo = TaskRepository(session)
        repo.create_task(
            {
                "id": task_id,
                "appId": DEFAULT_APP_ID,
                "title": "Benchmark snapshot task",
                "goal": "Measure snapshot contention",
                "status": "running",
            }
        )
    return task_id


def _run_task_update_scenario(workers: int, iterations_per_worker: int) -> ScenarioResult:
    total_ops = workers * iterations_per_worker
    stats = StatsCollector(total_ops)
    runtime = get_persistence_runtime()
    task_id = _prepare_task_update_seed()

    def _worker(worker_idx: int) -> None:
        for iteration in range(iterations_per_worker):
            t0 = time.perf_counter()
            err: Exception | None = None
            try:
                now = utc_now()
                with runtime.session_scope() as session:
                    repo = TaskRepository(session)
                    repo.update_task(
                        task_id,
                        {
                            "currentFocus": f"focus-{worker_idx}-{iteration}",
                            "currentObjective": "benchmark-task-update",
                            "windowIndex": 1 + (iteration % 8),
                            "cumulativeWindowSpanTokens": iteration * 128,
                            "budgetState": BudgetState(
                                tokenBudgetTotal=20000,
                                tokenBudgetUsed=iteration * 32,
                                costBudgetTotal=20.0,
                                costBudgetUsed=min(20.0, iteration * 0.02),
                            ).model_dump(by_alias=True),
                            "updatedAt": now,
                        },
                    )
            except Exception as exc:  # noqa: BLE001
                err = exc
            finally:
                latency_ms = (time.perf_counter() - t0) * 1000.0
                stats.record(latency_ms, err)

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for worker_idx in range(workers):
            executor.submit(_worker, worker_idx)
    duration = time.perf_counter() - started
    return stats.to_result(
        scenario="task_update_contention",
        workers=workers,
        iterations_per_worker=iterations_per_worker,
        duration_seconds=duration,
    )


def run_profile(profile: str, *, workers: int, iterations_per_worker: int) -> BenchmarkResult:
    previous = _set_profile_env(profile)
    try:
        with tempfile.TemporaryDirectory(prefix=f"ygg-bench-{profile}-") as temp_dir:
            db_path = Path(temp_dir) / "benchmark.db"
            os.environ["YGGDRASIL_DATABASE_URL"] = f"sqlite+pysqlite:///{db_path.as_posix()}"
            os.environ["YGGDRASIL_AUTO_CREATE_SCHEMA"] = "0"

            reset_persistence_runtime()
            initialize_schema()
            ensure_workspace_bootstrap()

            node_result = _run_node_write_scenario(workers, iterations_per_worker)
            task_update_result = _run_task_update_scenario(workers, iterations_per_worker)

            runtime = get_persistence_runtime()
            result = BenchmarkResult(
                profile=profile,
                database_url=runtime.settings.database_url,
                queue_enabled=runtime.settings.operation_queue_enabled,
                wal_enabled=runtime.settings.sqlite_enable_wal,
                retry_attempts=runtime.settings.sqlite_lock_retry_max_attempts,
                busy_timeout_ms=runtime.settings.sqlite_busy_timeout_ms,
                scenarios=[node_result, task_update_result],
            )
            reset_persistence_runtime()
            return result
    finally:
        _restore_env(previous)
        reset_persistence_runtime()


def benchmark_result_to_dict(result: BenchmarkResult) -> dict[str, Any]:
    payload = asdict(result)
    payload["scenarios"] = [asdict(item) for item in result.scenarios]
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Run SQLite concurrency benchmark profiles.")
    parser.add_argument("--profile", choices=["baseline", "optimized"], default="optimized")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--iterations", type=int, default=40, dest="iterations_per_worker")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    result = run_profile(args.profile, workers=args.workers, iterations_per_worker=args.iterations_per_worker)
    payload = benchmark_result_to_dict(result)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    print(text)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
