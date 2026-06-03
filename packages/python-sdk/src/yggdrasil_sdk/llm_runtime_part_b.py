from __future__ import annotations

from typing import Any

from .llm_runtime_core import *  # noqa: F403,F401
from .llm_runtime_tools_and_artifacts import *  # noqa: F403,F401
from .llm_runtime_invoke import *  # noqa: F403,F401
from . import llm_runtime_invoke as _llm_runtime_invoke


start_langfuse_generation = _llm_runtime_invoke.start_langfuse_generation
finish_langfuse_generation = _llm_runtime_invoke.finish_langfuse_generation


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
	_llm_runtime_invoke.start_langfuse_generation = start_langfuse_generation
	_llm_runtime_invoke.finish_langfuse_generation = finish_langfuse_generation
	return _llm_runtime_invoke.invoke_runtime_completion(
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
