from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Any

from .contracts import ExternalRef
from .observability_exporters import finish_langfuse_generation
from .observability_exporters import start_langfuse_generation
from .observability import observe_span, record_log, record_metric
from .persistence import RuntimeRepository
from .support import ensure_state_subdir, normalize_excerpt, relative_workspace_path, resolve_workspace_root, utc_now, write_json


FALLBACK_ROUTE_CANDIDATE = {
    "model": "yggdrasil-fallback",
    "provider": "fallback",
    "quality": 0.35,
    "costPer1k": 0.0,
    "latencyMs": 25,
    "contextWindow": 64000,
    "freeTier": True,
}


def load_runtime_candidate_models() -> list[dict[str, Any]] | None:
    try:
        from yggdrasil_model_providers import get_provider_catalog
    except Exception:
        return [dict(FALLBACK_ROUTE_CANDIDATE)]

    try:
        candidates = get_provider_catalog(resolve_workspace_root())
    except Exception:
        return [dict(FALLBACK_ROUTE_CANDIDATE)]
    return candidates or [dict(FALLBACK_ROUTE_CANDIDATE)]


def _normalize_route_decision(route_decision: Any) -> dict[str, Any]:
    if isinstance(route_decision, dict):
        return dict(route_decision)
    if hasattr(route_decision, "model_dump"):
        return route_decision.model_dump(by_alias=True, mode="json")
    return {
        "id": getattr(route_decision, "id", None),
        "selectedModel": getattr(route_decision, "selected_model", None),
        "selectedProvider": getattr(route_decision, "selected_provider", None),
    }


def _context_lines(current_context: list[dict[str, Any]], *, limit: int = 10) -> str:
    lines: list[str] = []
    for index, item in enumerate(current_context[:limit], start=1):
        title = str(item.get("title") or item.get("kind") or f"context-{index}")
        content = normalize_excerpt(str(item.get("content") or item), 240)
        root_branch = str(item.get("rootBranch") or item.get("mode") or "context")
        lines.append(f"{index}. [{root_branch}] {title}: {content}")
    return "\n".join(lines) if lines else "No extra context items were mounted for this execution."


def build_runtime_messages(
    *,
    task: Any,
    task_type: str,
    root_mount: dict[str, Any],
    current_context: list[dict[str, Any]],
    request: dict[str, Any],
    resume_path: str | None,
) -> list[dict[str, str]]:
    objective = str(request.get("taskObjective") or request.get("currentObjective") or task.current_objective or task.goal)
    focus = str(request.get("currentFocus") or task.current_focus or "runtime execution")
    resume_message = str(request.get("resumeMessage") or task.resume_message or "")
    prompt_sections = [
        f"Task title: {task.title}",
        f"Task goal: {task.goal}",
        f"Current objective: {objective}",
        f"Current focus: {focus}",
        f"Task type: {task_type}",
        f"Mounted summary: {root_mount.get('rootSummary') or ''}",
    ]
    if resume_path:
        prompt_sections.append(f"Resume path: {resume_path}")
    if resume_message:
        prompt_sections.append(f"Resume message: {resume_message}")
    prompt_sections.extend(
        [
            "Mounted context items:",
            _context_lines(current_context),
            "Response requirements:",
            "1. Summarize the current situation and the most defensible next step.",
            "2. If the context is insufficient, state the missing information explicitly.",
            "3. Keep the answer grounded in the mounted context instead of inventing state.",
            "4. Write in Chinese unless the task clearly requires another language.",
        ]
    )
    return [
        {
            "role": "system",
            "content": (
                "You are the execution model for Project Yggdrasil. Produce concise, concrete runtime output "
                "that can be persisted as an execution node. Do not mention hidden chain-of-thought."
            ),
        },
        {
            "role": "user",
            "content": "\n\n".join(section for section in prompt_sections if section),
        },
    ]


def _default_temperature(task_type: str) -> float:
    if task_type in {"coding", "maintenance"}:
        return 0.15
    if task_type == "research":
        return 0.3
    return 0.25


def _default_max_tokens(task: Any, request: dict[str, Any]) -> int:
    configured = int(request.get("maxTokens") or 800)
    self_think_limit = task.budget.self_think_token_limit
    if self_think_limit is not None:
        configured = min(configured, self_think_limit)
    if task.budget.token_budget_total is not None:
        remaining = max(task.budget.token_budget_total - task.budget.token_budget_used, 64)
        configured = min(configured, remaining)
    return max(configured, 64)


def _invocation_file_ref(path: Path, workspace_root: Path) -> ExternalRef:
    return ExternalRef(type="file", locator=relative_workspace_path(path, workspace_root))


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
    service_name: str = "agent-runtime",
) -> dict[str, Any]:
    try:
        from yggdrasil_model_providers import invoke_model
    except Exception:
        invoke_model = None

    workspace_root = resolve_workspace_root()
    runtime_repository = RuntimeRepository(session)
    route_payload = _normalize_route_decision(route_decision)
    messages = build_runtime_messages(
        task=task,
        task_type=task_type,
        root_mount=root_mount,
        current_context=current_context,
        request=request,
        resume_path=resume_path,
    )
    temperature = float(request.get("temperature")) if request.get("temperature") is not None else _default_temperature(task_type)
    max_tokens = _default_max_tokens(task, request)
    allow_fallback = bool(request.get("allowModelFallback", True))
    now = utc_now()
    invocation = runtime_repository.create_model_invocation(
        {
            "projectId": task.project_id,
            "taskId": task.id,
            "agentRunId": run.id,
            "routeDecisionId": route_payload.get("id"),
            "requestedModel": route_payload.get("selectedModel"),
            "requestedProvider": route_payload.get("selectedProvider"),
            "status": "running",
            "startedAt": now,
            "createdAt": now,
        }
    )

    request_path = ensure_state_subdir("llm/requests", workspace_root) / f"{invocation.id}.json"
    write_json(
        request_path,
        {
            "invocationId": invocation.id,
            "taskId": task.id,
            "agentRunId": run.id,
            "requestedModel": route_payload.get("selectedModel"),
            "requestedProvider": route_payload.get("selectedProvider"),
            "temperature": temperature,
            "maxTokens": max_tokens,
            "messages": messages,
        },
    )
    request_ref = _invocation_file_ref(request_path, workspace_root)
    invocation = runtime_repository.update_model_invocation(invocation.id, {"requestRef": request_ref.model_dump(mode="json")})

    started_counter = perf_counter()
    langfuse_generation = None
    try:
        with observe_span(
            service_name,
            "llm.chat.completion",
            kind="client",
            attributes={
                "task.id": task.id,
                "agentRun.id": run.id,
                "requested.model": route_payload.get("selectedModel"),
                "requested.provider": route_payload.get("selectedProvider"),
            },
            workspace_root=workspace_root,
        ) as span:
            langfuse_generation = start_langfuse_generation(
                trace_id=span["traceId"],
                name="runtime-llm-completion",
                input_payload={
                    "messages": messages,
                    "taskId": task.id,
                    "agentRunId": run.id,
                    "invocationId": invocation.id,
                },
                model=str(route_payload.get("selectedModel")) if route_payload.get("selectedModel") is not None else None,
                model_parameters={"temperature": temperature, "max_tokens": max_tokens},
                metadata={
                    "serviceName": service_name,
                    "requestedProvider": route_payload.get("selectedProvider"),
                    "requestedModel": route_payload.get("selectedModel"),
                    "taskType": task_type,
                },
            )
            if invoke_model is None:
                result = {
                    "mode": "fallback",
                    "provider": None,
                    "model": route_payload.get("selectedModel") or "fallback-synthetic",
                    "outputText": "LLM adapter package is unavailable. Runtime fell back to deterministic execution output.",
                    "finishReason": "fallback",
                    "usage": {
                        "inputTokens": sum(max(1, len(str(message.get("content") or "")) // 4) for message in messages),
                        "outputTokens": 24,
                        "totalTokens": sum(max(1, len(str(message.get("content") or "")) // 4) for message in messages) + 24,
                    },
                    "costUsed": 0.0,
                    "error": "adapter-unavailable",
                    "rawResponse": {
                        "choices": [
                            {
                                "finish_reason": "fallback",
                                "message": {"role": "assistant", "content": "LLM adapter package is unavailable. Runtime fell back to deterministic execution output."},
                            }
                        ]
                    },
                    "requestPayload": {
                        "model": route_payload.get("selectedModel"),
                        "messages": messages,
                    },
                }
            else:
                result = invoke_model(
                    requested_model=str(route_payload.get("selectedModel")) if route_payload.get("selectedModel") is not None else None,
                    requested_provider=str(route_payload.get("selectedProvider")) if route_payload.get("selectedProvider") is not None else None,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    workspace_root=workspace_root,
                    allow_fallback=allow_fallback,
                )

            latency_ms = round((perf_counter() - started_counter) * 1000.0, 2)
            response_path = ensure_state_subdir("llm/responses", workspace_root) / f"{invocation.id}.json"
            write_json(
                response_path,
                {
                    "invocationId": invocation.id,
                    "taskId": task.id,
                    "agentRunId": run.id,
                    "mode": result.get("mode"),
                    "provider": result.get("provider"),
                    "model": result.get("model"),
                    "finishReason": result.get("finishReason"),
                    "usage": result.get("usage"),
                    "error": result.get("error"),
                    "rawResponse": result.get("rawResponse"),
                },
            )
            response_ref = _invocation_file_ref(response_path, workspace_root)
            final_status = "completed" if result.get("mode") == "live" else "fallback"
            invocation = runtime_repository.update_model_invocation(
                invocation.id,
                {
                    "status": final_status,
                    "traceId": span["traceId"],
                    "resolvedModel": result.get("model") or route_payload.get("selectedModel"),
                    "resolvedProvider": result.get("provider"),
                    "responseRef": response_ref.model_dump(mode="json"),
                    "inputTokensUsed": int((result.get("usage") or {}).get("inputTokens", 0)),
                    "outputTokensUsed": int((result.get("usage") or {}).get("outputTokens", 0)),
                    "costUsed": float(result.get("costUsed", 0.0) or 0.0),
                    "latencyMs": latency_ms,
                    "errorSummary": str(result.get("error")) if result.get("error") is not None else None,
                    "endedAt": utc_now(),
                },
            )
            finish_langfuse_generation(
                langfuse_generation,
                output=result.get("outputText"),
                metadata={
                    "invocationId": invocation.id,
                    "status": invocation.status,
                    "provider": invocation.resolved_provider,
                    "mode": result.get("mode"),
                    "traceId": invocation.trace_id,
                },
                usage_details={
                    "prompt_tokens": int(invocation.input_tokens_used or 0),
                    "completion_tokens": int(invocation.output_tokens_used or 0),
                    "total_tokens": int((invocation.input_tokens_used or 0) + (invocation.output_tokens_used or 0)),
                },
                cost_details={"total_cost": float(invocation.cost_used or 0.0)},
                model=invocation.resolved_model,
                level="WARNING" if invocation.status != "completed" else "DEFAULT",
                status_message=str(result.get("error")) if invocation.status != "completed" else None,
            )
            span["attributes"]["resolved.model"] = invocation.resolved_model
            span["attributes"]["resolved.provider"] = invocation.resolved_provider
            span["attributes"]["invocation.status"] = invocation.status
            span["attributes"]["latency.ms"] = latency_ms
            record_metric(
                service_name,
                "llm.request",
                1,
                kind="counter",
                attributes={
                    "provider": invocation.resolved_provider or "unknown",
                    "model": invocation.resolved_model,
                    "status": invocation.status,
                },
                workspace_root=workspace_root,
            )
            record_metric(
                service_name,
                "llm.tokens.input",
                invocation.input_tokens_used,
                kind="counter",
                unit="token",
                attributes={"provider": invocation.resolved_provider or "unknown", "model": invocation.resolved_model},
                workspace_root=workspace_root,
            )
            record_metric(
                service_name,
                "llm.tokens.output",
                invocation.output_tokens_used,
                kind="counter",
                unit="token",
                attributes={"provider": invocation.resolved_provider or "unknown", "model": invocation.resolved_model},
                workspace_root=workspace_root,
            )
            record_metric(
                service_name,
                "llm.cost.used",
                invocation.cost_used,
                kind="counter",
                unit="usd",
                attributes={"provider": invocation.resolved_provider or "unknown", "model": invocation.resolved_model},
                workspace_root=workspace_root,
            )
            if invocation.status != "completed":
                record_log(
                    service_name,
                    "warning",
                    "Model invocation fell back to deterministic output.",
                    attributes={
                        "taskId": task.id,
                        "agentRunId": run.id,
                        "invocationId": invocation.id,
                        "traceId": invocation.trace_id,
                        "reason": invocation.error_summary,
                    },
                    workspace_root=workspace_root,
                )
            return {
                "assistantText": str(result.get("outputText") or ""),
                "invocation": invocation.model_dump(by_alias=True, mode="json"),
                "usage": dict(result.get("usage") or {}),
                "costUsed": float(result.get("costUsed", 0.0) or 0.0),
                "status": invocation.status,
            }
    except Exception as exc:
        latency_ms = round((perf_counter() - started_counter) * 1000.0, 2)
        finish_langfuse_generation(
            langfuse_generation,
            metadata={
                "invocationId": invocation.id,
                "errorType": exc.__class__.__name__,
                "serviceName": service_name,
            },
            model=str(route_payload.get("selectedModel")) if route_payload.get("selectedModel") is not None else None,
            level="ERROR",
            status_message=str(exc),
        )
        invocation = runtime_repository.update_model_invocation(
            invocation.id,
            {
                "status": "failed",
                "latencyMs": latency_ms,
                "errorSummary": str(exc),
                "endedAt": utc_now(),
            },
        )
        record_log(
            service_name,
            "error",
            "Model invocation failed.",
            attributes={
                "taskId": task.id,
                "agentRunId": run.id,
                "invocationId": invocation.id,
                "errorMessage": str(exc),
            },
            workspace_root=workspace_root,
        )
        raise