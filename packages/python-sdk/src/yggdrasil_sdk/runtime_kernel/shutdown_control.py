"""Thread-safe graceful shutdown flag for the agent worker."""
from __future__ import annotations

import threading

_shutdown_flag: threading.Event = threading.Event()


def request_shutdown() -> None:
    """Signal that the process should shut down after the current safe checkpoint."""
    _shutdown_flag.set()


def is_shutdown_requested() -> bool:
    """Return True if a graceful shutdown has been requested."""
    return _shutdown_flag.is_set()


def clear_shutdown() -> None:
    """Clear the shutdown flag (for testing)."""
    _shutdown_flag.clear()


__all__ = ["request_shutdown", "is_shutdown_requested", "clear_shutdown"]
