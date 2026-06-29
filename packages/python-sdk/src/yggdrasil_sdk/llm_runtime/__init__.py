from __future__ import annotations

from typing import Any

from .core import *  # noqa: F403,F401
from .artifacts import *  # noqa: F403,F401
from .behavior_recorder import *  # noqa: F403,F401
from .invoke import *  # noqa: F403,F401
from . import invoke as _invoke_module

start_langfuse_generation = _invoke_module.start_langfuse_generation
finish_langfuse_generation = _invoke_module.finish_langfuse_generation


def invoke_runtime_completion(
    session,
    *,
    task: Any,
    run: Any,
    route_decision: Any,
    task_type: str,
    root_mount: dict[str, Any],
    current_context: list[dict[str, Any]],
    request: dict[str, Any],
    resume_path: str | None,
    registered_tools: list[dict[str, Any]] | None = None,
    service_name: str = "agent-runtime",
) -> dict[str, Any]:
    _invoke_module.start_langfuse_generation = start_langfuse_generation
    _invoke_module.finish_langfuse_generation = finish_langfuse_generation
    return _invoke_module.invoke_runtime_completion(
        session,
        task=task,
        run=run,
        route_decision=route_decision,
        task_type=task_type,
        root_mount=root_mount,
        current_context=current_context,
        request=request,
        resume_path=resume_path,
        registered_tools=registered_tools,
        service_name=service_name,
    )


__all__ = [name for name in globals() if not name.startswith("__")]
