from __future__ import annotations

from contextlib import contextmanager
import threading
from typing import Callable, TypeVar

from .database import get_persistence_runtime


T = TypeVar("T")


class _KeyedOperationQueue:
    def __init__(self) -> None:
        self._meta_lock = threading.Lock()
        self._locks: dict[str, threading.Lock] = {}
        self._ref_counts: dict[str, int] = {}

    @contextmanager
    def acquire(self, key: str):
        with self._meta_lock:
            lock = self._locks.setdefault(key, threading.Lock())
            self._ref_counts[key] = self._ref_counts.get(key, 0) + 1

        lock.acquire()
        try:
            yield
        finally:
            lock.release()
            with self._meta_lock:
                remaining = self._ref_counts.get(key, 1) - 1
                if remaining <= 0:
                    self._ref_counts.pop(key, None)
                    self._locks.pop(key, None)
                else:
                    self._ref_counts[key] = remaining


_OPERATION_QUEUE = _KeyedOperationQueue()


def run_serialized_write(queue_key: str, operation: Callable[[], T]) -> T:
    runtime = get_persistence_runtime()

    def _execute() -> T:
        return runtime.run_with_sqlite_lock_retry(operation)

    if not runtime.settings.operation_queue_enabled:
        return _execute()

    with _OPERATION_QUEUE.acquire(queue_key):
        return _execute()
