from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

from .contracts import EventEnvelope, EventHandlingResult


HookHandler = Callable[[dict[str, Any]], dict[str, Any] | list[dict[str, Any]] | None]


@dataclass(slots=True)
class HookRegistration:
    name: str
    handler: HookHandler
    order: int = 100
    timeout_ms: int = 3000
    idempotent: bool = True
    side_effects: str = "read-only"


class BaseModulePlugin(ABC):
    module_id: str

    @abstractmethod
    def manifest_path(self) -> Path:
        raise NotImplementedError

    def register_hooks(self) -> Sequence[HookRegistration]:
        return ()

    def register_tools(self) -> Sequence[dict[str, Any]]:
        return ()

    def handle_event(self, event: EventEnvelope) -> EventHandlingResult:
        return EventHandlingResult(status="ignored", handled=False, summary=f"{self.module_id} ignored {event.event_type}.")