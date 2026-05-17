from __future__ import annotations

from hashlib import sha1
import json
import os
from pathlib import Path
from time import perf_counter
from typing import Any

from .contracts import BudgetCheckResult, BudgetOverrunResult, ExternalRef, ToolExecutionFailure, ToolExecutionResult
from .domain import PromptProfileVersionRecord, SeedTemplateVersionRecord
from .observability_exporters import finish_langfuse_generation
from .observability_exporters import start_langfuse_generation
from .observability import observe_span, record_log, record_metric
from .persistence import PromptAssetRepository, RuntimeRepository
from .prompting import compile_runtime_prompt, get_prompt_profile_definition, get_seed_template_definition
from .support import ensure_state_subdir, new_id, normalize_excerpt, relative_workspace_path, resolve_workspace_root, utc_now, write_json
from .tool_runtime import build_llm_tool_specs, execute_registered_tool, tool_result_to_message_content


def _is_shutdown_requested() -> bool:
    """Lazy check for graceful shutdown. Avoids circular import with runtime_kernel."""
    try:
        from .runtime_kernel.shutdown_control import is_shutdown_requested
        return is_shutdown_requested()
    except ImportError:
        return False


def _should_checkpoint_for_pause(task: Any, request: dict[str, Any]) -> bool:
    return _is_shutdown_requested() or bool(getattr(task, "pause_requested", False)) or bool(request.get("pauseRequested", False))


FALLBACK_ROUTE_CANDIDATE = {
    "model": "yggdrasil-fallback",
    "provider": "fallback",
    "quality": 0.35,
    "costPer1k": 0.0,
    "latencyMs": 25,
    "contextWindow": 64000,
    "freeTier": True,
}

_AUDIT_LEVELS = {"strict", "default", "lean"}

_PENDING_TOOL_CALLS_KIND = "pending-tool-calls"
_DUPLICATE_TOOL_ROUND_THRESHOLD = 2
_USAGE_COUNTER_FIELDS = (
    "inputTokens",
    "outputTokens",
    "totalTokens",
    "cacheHitInputTokens",
    "cacheWriteInputTokens",
    "nonCacheInputTokens",
    "reasoningTokens",
)

# P2 constants for budget management and tool execution
_MAX_TOOL_RETRIES = 2
_COST_BUDGET_BUFFER = 0.01
_TOKEN_BUDGET_SAFETY_MARGIN = 32
_TOOL_EXECUTION_TIMEOUT_MS = 5000


class SafeShutdownInterrupt(Exception):
    """Raised when a graceful shutdown is requested while tool calls are pending."""

    def __init__(
        self,
        *,
        pending_tool_calls: list[dict[str, Any]],
        conversation_messages: list[dict[str, Any]],
        invocation_id: str,
        round_index: int,
        usage_totals: dict[str, int],
        accumulated_cost: float,
        round_summaries: list[dict[str, Any]],
        round_modes: list[str],
        assistant_tool_calls_payload: list[dict[str, Any]],
        assistant_message: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(f"Safe shutdown requested at round {round_index} with {len(pending_tool_calls)} pending tool call(s).")
        self.pending_tool_calls = pending_tool_calls
        self.conversation_messages = conversation_messages
        self.invocation_id = invocation_id
        self.round_index = round_index
        self.usage_totals = usage_totals
        self.accumulated_cost = accumulated_cost
        self.round_summaries = round_summaries
        self.round_modes = round_modes
        self.assistant_tool_calls_payload = assistant_tool_calls_payload
        self.assistant_message = dict(assistant_message) if isinstance(assistant_message, dict) else None


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


def _check_pre_invocation_budget(
    task: Any,
    request: dict[str, Any],
    estimated_input_tokens: int = 1000,
    estimated_output_tokens: int = 500,
    estimated_cost: float = 0.01,
) -> BudgetCheckResult:
    """Validate budget headroom before invoking the model."""
    budget = task.budget if hasattr(task, "budget") else None
    if not budget:
        return BudgetCheckResult(
            checkPassed=True,
            reason=None,
            availableTokenBudget=999_999,
            availableCostBudget=999_999.0,
            estimatedTotalTokens=estimated_input_tokens + estimated_output_tokens,
            estimatedCost=estimated_cost,
        )

    estimated_total_tokens = estimated_input_tokens + estimated_output_tokens
    available_token_budget = (
        budget.token_budget_total - budget.token_budget_used
        if budget.token_budget_total is not None
        else float("inf")
    )
    available_cost_budget = (
        budget.cost_budget_total - budget.cost_budget_used
        if budget.cost_budget_total is not None
        else float("inf")
    )

    check_passed = True
    violation_reason = None

    if budget.token_budget_total is not None:
        required_tokens = estimated_total_tokens + _TOKEN_BUDGET_SAFETY_MARGIN
        if available_token_budget < required_tokens:
            violation_reason = (
                f"Insufficient token budget: required {required_tokens}, "
                f"available {int(available_token_budget)}"
            )
            check_passed = False

    if budget.cost_budget_total is not None and check_passed:
        required_cost = estimated_cost + _COST_BUDGET_BUFFER
        if available_cost_budget < required_cost:
            violation_reason = (
                f"Insufficient cost budget: required {required_cost:.6f}, "
                f"available {available_cost_budget:.6f}"
            )
            check_passed = False

    return BudgetCheckResult(
        checkPassed=check_passed,
        reason=violation_reason,
        availableTokenBudget=(int(available_token_budget) if available_token_budget != float("inf") else 999_999),
        availableCostBudget=(float(available_cost_budget) if available_cost_budget != float("inf") else 999_999.0),
        estimatedTotalTokens=estimated_total_tokens,
        estimatedCost=estimated_cost,
    )


def _check_post_invocation_budget(
    task: Any,
    input_tokens_used: int,
    output_tokens_used: int,
    cost_used: float,
) -> BudgetOverrunResult:
    """Validate consumed budget and report any overrun details."""
    budget = task.budget if hasattr(task, "budget") else None
    if not budget:
        return BudgetOverrunResult(
            isOverrun=False,
            violationType=None,
            tokensUsed=input_tokens_used + output_tokens_used,
            costUsed=cost_used,
            tokensExceededBy=0,
            costExceededBy=0.0,
        )

    total_tokens_used = input_tokens_used + output_tokens_used
    violation_type: str | None = None
    tokens_exceeded_by = 0
    cost_exceeded_by = 0.0

    if budget.token_budget_total is not None:
        new_total = budget.token_budget_used + total_tokens_used
        if new_total > budget.token_budget_total:
            tokens_exceeded_by = new_total - budget.token_budget_total
            violation_type = "token"

    if budget.cost_budget_total is not None:
        new_total = budget.cost_budget_used + cost_used
        if new_total > budget.cost_budget_total:
            cost_exceeded_by = new_total - budget.cost_budget_total
            violation_type = "both" if violation_type == "token" else "cost"

    return BudgetOverrunResult(
        isOverrun=violation_type is not None,
        violationType=violation_type,
        tokensUsed=total_tokens_used,
        costUsed=cost_used,
        tokensExceededBy=tokens_exceeded_by,
        costExceededBy=cost_exceeded_by,
    )


def _is_retryable_tool_exception(exc: Exception) -> bool:
    """Use class names to avoid hard dependency on provider-specific exception types."""
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return True
    error_name = exc.__class__.__name__.lower()
    return "timeout" in error_name or "connection" in error_name


def _execute_tool_with_isolation(
    *,
    call: dict[str, Any],
    tool_call_id: str,
    task: Any,
    run: Any,
    root_mount: dict[str, Any],
    current_context: list[dict[str, Any]],
    max_retries: int = _MAX_TOOL_RETRIES,
) -> ToolExecutionResult:
    """Execute a single tool call with retryable-failure isolation and structured result."""
    tool_name = str(call.get("name") or "")
    arguments = call.get("arguments") if isinstance(call.get("arguments"), dict) else {}
    last_error: Exception | None = None
    started_at = perf_counter()

    for attempt in range(max(0, int(max_retries)) + 1):
        try:
            execution = execute_registered_tool(
                tool_name,
                arguments,
                task=task,
                run=run,
                root_mount=root_mount,
                current_context=current_context,
            )
            return ToolExecutionResult(
                toolName=tool_name,
                toolCallId=tool_call_id,
                success=True,
                result=execution if isinstance(execution, dict) else {"value": execution},
                failure=None,
                durationMs=int(round((perf_counter() - started_at) * 1000.0)),
            )
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            retryable = _is_retryable_tool_exception(exc)
            if retryable and attempt < max_retries:
                continue
            failure = ToolExecutionFailure(
                toolName=tool_name,
                errorMessage=str(exc),
                errorType=exc.__class__.__name__,
                retryCount=attempt,
                isRetryable=retryable,
            )
            return ToolExecutionResult(
                toolName=tool_name,
                toolCallId=tool_call_id,
                success=False,
                result={"status": "error", "error": str(exc)},
                failure=failure,
                durationMs=int(round((perf_counter() - started_at) * 1000.0)),
            )

    assert last_error is not None
    return ToolExecutionResult(
        toolName=tool_name,
        toolCallId=tool_call_id,
        success=False,
        result={"status": "error", "error": str(last_error)},
        failure=ToolExecutionFailure(
            toolName=tool_name,
            errorMessage=str(last_error),
            errorType=last_error.__class__.__name__,
            retryCount=max(0, int(max_retries)),
            isRetryable=_is_retryable_tool_exception(last_error),
        ),
        durationMs=int(round((perf_counter() - started_at) * 1000.0)),
    )


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
    run_type: str,
    task_type: str,
    root_mount: dict[str, Any],
    current_context: list[dict[str, Any]],
    request: dict[str, Any],
    resume_path: str | None,
) -> list[dict[str, Any]]:
    compiled = compile_runtime_prompt(
        task=task,
        run_type=run_type,
        task_type=task_type,
        root_mount=root_mount,
        current_context=current_context,
        request=request,
        resume_path=resume_path,
    )
    return [dict(message) for message in compiled.messages]


def _default_temperature(task_type: str) -> float:
    if task_type in {"coding", "maintenance"}:
        return 0.15
    if task_type == "research":
        return 0.3
    if task_type == "writing":
        return 0.65
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


def _json_hash(payload: Any) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha1(serialized.encode("utf-8")).hexdigest()


def _local_fallback_result(messages: list[dict[str, Any]], route_payload: dict[str, Any]) -> dict[str, Any]:
    input_tokens = sum(max(1, len(str(message.get("content") or "")) // 4) for message in messages)
    return {
        "mode": "fallback",
        "provider": None,
        "model": route_payload.get("selectedModel") or "fallback-synthetic",
        "outputText": "LLM adapter package is unavailable. Runtime fell back to deterministic execution output.",
        "finishReason": "fallback",
        "usage": {
            "inputTokens": input_tokens,
            "outputTokens": 24,
            "totalTokens": input_tokens + 24,
            "cacheHitInputTokens": 0,
            "cacheWriteInputTokens": 0,
            "nonCacheInputTokens": input_tokens,
            "reasoningTokens": 0,
        },
        "costUsed": 0.0,
        "error": "adapter-unavailable",
        "toolCalls": [],
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


def _empty_usage_totals() -> dict[str, int]:
    return {field: 0 for field in _USAGE_COUNTER_FIELDS}


def _merge_usage(total: dict[str, int], usage: dict[str, Any]) -> dict[str, int]:
    for field in _USAGE_COUNTER_FIELDS:
        total.setdefault(field, 0)
    for key, value in usage.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        total[key] = int(total.get(key, 0) or 0) + int(value)
    return total


def _elapsed_ms(started_at: float) -> float:
    return round((perf_counter() - started_at) * 1000.0, 2)


def _estimate_text_tokens(text: str) -> int:
    compact = " ".join(str(text).split())
    return max(1, len(compact) // 4) if compact else 0


def _estimate_message_tokens(messages: list[dict[str, Any]]) -> int:
    total = 0
    for message in messages:
        if not isinstance(message, dict):
            continue
        parts: list[str] = []
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            parts.append(content)
        elif isinstance(content, list):
            for item in content:
                if isinstance(item, str) and item.strip():
                    parts.append(item)
                elif isinstance(item, dict) and item.get("text"):
                    parts.append(str(item["text"]))
        reasoning_content = message.get("reasoning_content")
        if isinstance(reasoning_content, str) and reasoning_content.strip():
            parts.append(reasoning_content)
        tool_calls = message.get("tool_calls")
        if isinstance(tool_calls, list):
            for call in tool_calls:
                if not isinstance(call, dict):
                    continue
                function_payload = call.get("function") if isinstance(call.get("function"), dict) else {}
                if function_payload.get("name"):
                    parts.append(str(function_payload["name"]))
                if function_payload.get("arguments"):
                    parts.append(str(function_payload["arguments"]))
        total += sum(_estimate_text_tokens(part) for part in parts if part)
    return total


def _append_context_length_observation(
    observations: list[dict[str, Any]],
    *,
    phase: str,
    source: str,
    estimated_tokens: int,
    message_count: int | None = None,
    item_count: int | None = None,
    round_index: int | None = None,
    trigger: str | None = None,
) -> None:
    observation: dict[str, Any] = {
        "phase": phase,
        "source": source,
        "estimatedTokens": max(int(estimated_tokens), 0),
    }
    if message_count is not None:
        observation["messageCount"] = int(message_count)
    if item_count is not None:
        observation["itemCount"] = int(item_count)
    if round_index is not None:
        observation["roundIndex"] = int(round_index)
    if trigger:
        observation["trigger"] = trigger
    observations.append(observation)


def _first_token_latency_ms_from_round_summaries(round_summaries: list[dict[str, Any]]) -> float | None:
    for summary in round_summaries:
        value = summary.get("firstTokenLatencyMs") if isinstance(summary, dict) else None
        if value is not None:
            return float(value)
    return None


def _runtime_audit_level(request: dict[str, Any]) -> str:
    explicit = request.get("auditLevel") if isinstance(request, dict) else None
    candidate = str(explicit or os.getenv("YGGDRASIL_RUNTIME_AUDIT_LEVEL") or "default").strip().lower()
    return candidate if candidate in _AUDIT_LEVELS else "default"


def _requested_thinking_mode(request: dict[str, Any]) -> str | None:
    candidate = request.get("thinking") if isinstance(request, dict) else None
    if isinstance(candidate, dict):
        candidate = candidate.get("type")
    if isinstance(candidate, bool):
        return "enabled" if candidate else "disabled"
    if candidate is None:
        return None
    lowered = str(candidate).strip().lower()
    if lowered in {"1", "true", "enabled", "enable", "on", "thinking"}:
        return "enabled"
    if lowered in {"0", "false", "disabled", "disable", "off", "none"}:
        return "disabled"
    return None


def _requested_reasoning_effort(request: dict[str, Any]) -> str | None:
    raw = None
    if isinstance(request, dict):
        raw = request.get("reasoningEffort")
        if raw is None:
            raw = request.get("reasoning_effort")
    if raw is None:
        return None
    lowered = str(raw).strip().lower()
    if lowered in {"low", "medium", "high"}:
        return "high"
    if lowered in {"xhigh", "max"}:
        return "max"
    return None


def _assistant_tool_round_message(result: dict[str, Any], assistant_tool_calls: list[dict[str, Any]]) -> dict[str, Any]:
    message = {
        "role": "assistant",
        "content": str(result.get("outputText") or ""),
        "tool_calls": assistant_tool_calls,
    }
    reasoning_content = result.get("reasoningContent")
    if reasoning_content:
        message["reasoning_content"] = str(reasoning_content)
    return message


def _assistant_tool_calls_payload(tool_calls: list[dict[str, Any]], round_marker: Any) -> list[dict[str, Any]]:
    return [
        {
            "id": str(call.get("id") or new_id("toolcall", call.get("name"), round_marker)),
            "type": "function",
            "function": {
                "name": str(call.get("name")),
                "arguments": str(call.get("argumentsText") or json.dumps(call.get("arguments") or {}, ensure_ascii=False)),
            },
        }
        for call in tool_calls
        if isinstance(call, dict) and call.get("name")
    ]


def _execute_resumed_tool_calls(
    *,
    tool_calls: list[dict[str, Any]],
    conversation_messages: list[dict[str, Any]],
    tool_executions: list[dict[str, Any]],
    assistant_message: dict[str, Any] | None,
    task: Any,
    run: Any,
    root_mount: dict[str, Any],
    current_context: list[dict[str, Any]],
) -> None:
    assistant_tool_calls = _assistant_tool_calls_payload(tool_calls, "resume")
    if isinstance(assistant_message, dict):
        conversation_messages.append(dict(assistant_message))
    elif assistant_tool_calls:
        conversation_messages.append(_assistant_tool_round_message({}, assistant_tool_calls))
    for call in tool_calls:
        if not isinstance(call, dict) or not call.get("name"):
            continue
        tool_call_id = str(call.get("id") or new_id("toolcall", call.get("name"), "resume"))
        try:
            execution = execute_registered_tool(
                str(call["name"]),
                call.get("arguments") if isinstance(call.get("arguments"), dict) else {},
                task=task,
                run=run,
                root_mount=root_mount,
                current_context=current_context,
            )
            execution["success"] = True
        except Exception as exc:
            execution = {
                "tool": {"name": str(call["name"])},
                "arguments": call.get("arguments") if isinstance(call.get("arguments"), dict) else {},
                "result": {"status": "error", "error": str(exc)},
                "success": False,
            }
        execution["toolCallId"] = tool_call_id
        tool_executions.append(execution)
        conversation_messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "name": str(call["name"]),
                "content": tool_result_to_message_content(execution),
            }
        )


def _message_digest(message: dict[str, Any]) -> dict[str, Any]:
    content = str(message.get("content") or "")
    reasoning_content = str(message.get("reasoning_content") or "")
    tool_calls = message.get("tool_calls") if isinstance(message.get("tool_calls"), list) else []
    return {
        "role": str(message.get("role") or "unknown"),
        "name": str(message.get("name")) if message.get("name") is not None else None,
        "toolCallId": str(message.get("tool_call_id")) if message.get("tool_call_id") is not None else None,
        "contentPreview": normalize_excerpt(content, 240),
        "contentLength": len(content),
        "reasoningContentPreview": normalize_excerpt(reasoning_content, 240) if reasoning_content else None,
        "reasoningContentLength": len(reasoning_content),
        "toolCallNames": [
            str((tool_call.get("function") or {}).get("name") or "")
            for tool_call in tool_calls
            if isinstance(tool_call, dict)
        ],
    }


def _tool_call_signature(call: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": str(call.get("name") or ""),
        "arguments": call.get("arguments") if isinstance(call.get("arguments"), dict) else str(call.get("argumentsText") or ""),
    }


def _tool_round_signature(tool_calls: list[dict[str, Any]]) -> str:
    return _json_hash([_tool_call_signature(call) for call in tool_calls if isinstance(call, dict) and call.get("name")])


def _is_idempotent_tool_round(tool_calls: list[dict[str, Any]], registered_tools_by_name: dict[str, dict[str, Any]]) -> bool:
    if not tool_calls:
        return False
    for call in tool_calls:
        if not isinstance(call, dict) or not call.get("name"):
            return False
        descriptor = registered_tools_by_name.get(str(call.get("name") or "")) or {}
        if not bool(descriptor.get("idempotent")):
            return False
    return True


def _duplicate_tool_loop_result(result: dict[str, Any], invocation_id: str, *, duplicate_streak: int) -> dict[str, Any]:
    return {
        "mode": result.get("mode") or "live",
        "provider": result.get("provider"),
        "model": result.get("model"),
        "outputText": (
            "Detected a repeated idempotent tool loop and stopped further duplicate tool execution. "
            "Hand off to external verification using the files already written in the workspace."
        ),
        "finishReason": "duplicate-tool-loop-short-circuit",
        "usage": dict(result.get("usage") or {}),
        "costUsed": float(result.get("costUsed", 0.0) or 0.0),
        "error": None,
        "toolCalls": [],
        "rawResponse": {
            "status": "short-circuited",
            "reason": "duplicate-tool-loop",
            "duplicateStreak": duplicate_streak,
            "invocationId": invocation_id,
        },
    }


def _message_digests(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_message_digest(message) for message in messages]


def _tool_execution_summary(execution: dict[str, Any]) -> dict[str, Any]:
    tool = execution.get("tool") if isinstance(execution.get("tool"), dict) else {}
    result = execution.get("result") if isinstance(execution.get("result"), dict) else {}
    return {
        "tool": str(tool.get("name") or "unknown"),
        "success": bool(execution.get("success")),
        "status": str(result.get("status") or ("ok" if execution.get("success") else "error")),
        "resultPreview": normalize_excerpt(str(result), 240),
    }


def _tool_execution_summaries(tool_executions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_tool_execution_summary(execution) for execution in tool_executions if isinstance(execution, dict)]


def _tool_specs_summary(tool_specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for spec in tool_specs:
        function = spec.get("function") if isinstance(spec.get("function"), dict) else {}
        parameters = function.get("parameters") if isinstance(function.get("parameters"), dict) else {}
        properties = parameters.get("properties") if isinstance(parameters.get("properties"), dict) else {}
        summaries.append(
            {
                "name": str(function.get("name") or "unknown"),
                "description": str(function.get("description") or ""),
                "parameterCount": len(properties),
            }
        )
    return summaries


def _compiled_prompt_file_payload(audit_level: str, compiled_prompt, invocation_id: str) -> dict[str, Any]:
    payload = {
        "appId": compiled_prompt.app_id,
        "modelInvocationId": invocation_id,
        "auditLevel": audit_level,
        "prompt": compiled_prompt.model_dump(by_alias=True, mode="json", exclude={"messages"}),
    }
    if audit_level == "strict":
        payload["messages"] = compiled_prompt.messages
        return payload
    payload["messageDigests"] = _message_digests([dict(message) for message in compiled_prompt.messages])
    if audit_level == "default":
        payload["messageCount"] = len(compiled_prompt.messages)
    return payload


def _request_file_payload(
    audit_level: str,
    *,
    task: Any,
    run: Any,
    invocation_id: str,
    route_payload: dict[str, Any],
    temperature: float,
    max_tokens: int,
    thinking_mode: str | None,
    reasoning_effort: str | None,
    prompt_artifact_id: str,
    prompt_metadata: dict[str, Any],
    messages: list[dict[str, Any]],
    tool_specs: list[dict[str, Any]],
    conversation_messages: list[dict[str, Any]] | None = None,
    tool_executions: list[dict[str, Any]] | None = None,
    round_summaries: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    payload = {
        "appId": getattr(task, "app_id", None),
        "invocationId": invocation_id,
        "taskId": task.id,
        "agentRunId": run.id,
        "requestedModel": route_payload.get("selectedModel"),
        "requestedProvider": route_payload.get("selectedProvider"),
        "temperature": temperature,
        "maxTokens": max_tokens,
        "thinking": thinking_mode,
        "reasoningEffort": reasoning_effort,
        "promptCompileArtifactId": prompt_artifact_id,
        "promptMetadata": prompt_metadata,
        "auditLevel": audit_level,
    }
    if audit_level == "strict":
        payload["messages"] = messages
        payload["tools"] = tool_specs
        if conversation_messages is not None:
            payload["initialMessages"] = messages
            payload["messages"] = conversation_messages
        if tool_executions is not None:
            payload["toolExecutions"] = tool_executions
        if round_summaries is not None:
            payload["rounds"] = round_summaries
        return payload

    if conversation_messages is None:
        payload["messageDigests"] = _message_digests(messages)
    else:
        payload["initialMessageDigests"] = _message_digests(messages)
        payload["finalMessageDigests"] = _message_digests(conversation_messages)
    payload["toolSpecs"] = _tool_specs_summary(tool_specs)

    if audit_level == "default":
        if tool_executions is not None:
            payload["toolExecutionSummaries"] = _tool_execution_summaries(tool_executions)
        if round_summaries is not None:
            payload["rounds"] = round_summaries
        return payload

    payload["messageCount"] = len(conversation_messages if conversation_messages is not None else messages)
    payload["toolExecutionCount"] = len(tool_executions or [])
    payload["roundCount"] = len(round_summaries or [])
    return payload


def _response_file_payload(
    audit_level: str,
    *,
    task: Any,
    run: Any,
    invocation_id: str,
    prompt_artifact_id: str,
    final_result: dict[str, Any],
    usage_totals: dict[str, int],
    accumulated_cost: float,
    tool_executions: list[dict[str, Any]],
    round_summaries: list[dict[str, Any]],
    local_runtime_timings: dict[str, Any],
    first_token_latency_ms: float | None,
    context_length_observations: list[dict[str, Any]] | None = None,
    runtime_metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "appId": getattr(task, "app_id", None),
        "invocationId": invocation_id,
        "taskId": task.id,
        "agentRunId": run.id,
        "promptCompileArtifactId": prompt_artifact_id,
        "mode": final_result.get("mode"),
        "provider": final_result.get("provider"),
        "model": final_result.get("model"),
        "finishReason": final_result.get("finishReason"),
        "usage": usage_totals,
        "costUsed": accumulated_cost,
        "error": final_result.get("error"),
        "auditLevel": audit_level,
        "localRuntimeTimings": dict(local_runtime_timings),
    }
    if first_token_latency_ms is not None:
        payload["firstTokenLatencyMs"] = first_token_latency_ms
    if context_length_observations:
        payload["contextLengthObservations"] = [dict(item) for item in context_length_observations if isinstance(item, dict)]
    if runtime_metrics:
        payload["runtimeMetrics"] = dict(runtime_metrics)
    if audit_level == "strict":
        payload["toolExecutions"] = tool_executions
        payload["rounds"] = round_summaries
        payload["rawResponse"] = final_result.get("rawResponse")
        return payload

    if audit_level == "default":
        payload["toolExecutionSummaries"] = _tool_execution_summaries(tool_executions)
        payload["rounds"] = round_summaries
        return payload

    payload["toolExecutionCount"] = len(tool_executions)
    payload["roundCount"] = len(round_summaries)
    return payload


def _persist_prompt_assets(
    session,
    *,
    task: Any,
    run: Any,
    invocation_id: str,
    compiled_prompt,
    workspace_root: Path,
    audit_level: str,
):
    repository = PromptAssetRepository(session)
    prompt_profile = get_prompt_profile_definition(
        compiled_prompt.prompt_profile_id,
        app_id=compiled_prompt.app_id,
    )
    seed_template = get_seed_template_definition(
        compiled_prompt.seed_template_id,
        app_id=compiled_prompt.app_id,
    )

    prompt_profile_body = (
        prompt_profile.model_dump(by_alias=True, mode="json")
        if prompt_profile is not None
        else {
            "id": compiled_prompt.prompt_profile_id,
            "version": compiled_prompt.prompt_profile_version,
        }
    )
    prompt_profile_hash = _json_hash(prompt_profile_body)
    prompt_profile_record = repository.upsert_prompt_profile_version(
        PromptProfileVersionRecord(
            id=new_id("promptprof", compiled_prompt.prompt_profile_id, compiled_prompt.prompt_profile_version, prompt_profile_hash, stable=True),
            promptProfileId=compiled_prompt.prompt_profile_id,
            name=str(prompt_profile_body.get("name") or compiled_prompt.prompt_profile_id),
            version=compiled_prompt.prompt_profile_version,
            runScope=str(prompt_profile_body.get("runScope") or "any"),
            body=prompt_profile_body,
            contentHash=prompt_profile_hash,
            createdAt=utc_now(),
        )
    )

    seed_template_record = None
    if seed_template is not None:
        seed_template_body = seed_template.model_dump(by_alias=True, mode="json")
        seed_template_hash = _json_hash(seed_template_body)
        seed_template_record = repository.upsert_seed_template_version(
            SeedTemplateVersionRecord(
                id=new_id("seedtpl", seed_template.id, seed_template.version, seed_template_hash, stable=True),
                seedTemplateId=seed_template.id,
                name=seed_template.name,
                version=seed_template.version,
                domain=seed_template.domain,
                scenario=seed_template.scenario,
                body=seed_template_body,
                contentHash=seed_template_hash,
                createdAt=utc_now(),
            )
        )

    compiled_messages_path = ensure_state_subdir("prompt/compiled", workspace_root) / f"{invocation_id}.json"
    write_json(compiled_messages_path, _compiled_prompt_file_payload(audit_level, compiled_prompt, invocation_id))
    compiled_messages_ref = _invocation_file_ref(compiled_messages_path, workspace_root)
    takeover_protocol_snapshot = (
        compiled_prompt.takeover_protocol.model_dump(by_alias=True, mode="json")
        if compiled_prompt.takeover_protocol is not None
        else None
    )
    work_tree_snapshot = (
        dict(takeover_protocol_snapshot.get("workTree") or {}) if isinstance(takeover_protocol_snapshot, dict) else None
    )
    artifact_hash = _json_hash(
        {
            "promptProfileId": compiled_prompt.prompt_profile_id,
            "seedTemplateId": compiled_prompt.seed_template_id,
            "runType": compiled_prompt.run_type,
            "taskType": compiled_prompt.task_type,
            "scenario": compiled_prompt.scenario,
            "registeredTools": compiled_prompt.registered_tools,
            "systemSections": compiled_prompt.system_sections,
            "userSections": compiled_prompt.user_sections,
            "takeoverProtocol": takeover_protocol_snapshot,
            "messages": compiled_prompt.messages,
        }
    )
    return repository.create_prompt_compile_artifact(
        {
            "appId": compiled_prompt.app_id,
            "projectId": task.project_id,
            "taskId": task.id,
            "agentRunId": run.id,
            "modelInvocationId": invocation_id,
            "promptProfileVersionId": prompt_profile_record.id,
            "seedTemplateVersionId": seed_template_record.id if seed_template_record is not None else None,
            "runType": compiled_prompt.run_type,
            "taskType": compiled_prompt.task_type,
            "scenario": compiled_prompt.scenario,
            "registeredTools": compiled_prompt.registered_tools,
            "systemSections": compiled_prompt.system_sections,
            "userSections": compiled_prompt.user_sections,
            "workTreeSnapshot": work_tree_snapshot,
            "takeoverProtocolSnapshot": takeover_protocol_snapshot,
            "compiledMessagesRef": compiled_messages_ref.model_dump(mode="json"),
            "contentHash": artifact_hash,
            "createdAt": utc_now(),
        }
    )


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
    try:
        from yggdrasil_model_providers import invoke_model
    except Exception:
        invoke_model = None

    workspace_root = resolve_workspace_root()
    runtime_repository = RuntimeRepository(session)
    route_payload = _normalize_route_decision(route_decision)
    run_type = str(request.get("runType") or getattr(run, "run_type", "main"))
    audit_level = _runtime_audit_level(request)
    local_runtime_timings: dict[str, float] = {}
    local_started_at = perf_counter()

    compile_prompt_started_at = perf_counter()
    compiled_prompt = compile_runtime_prompt(
        task=task,
        run_type=run_type,
        task_type=task_type,
        root_mount=root_mount,
        current_context=current_context,
        request=request,
        resume_path=resume_path,
        registered_tools=registered_tools,
    )
    local_runtime_timings["compilePromptMs"] = _elapsed_ms(compile_prompt_started_at)
    prompt_metadata = compiled_prompt.model_dump(by_alias=True, mode="json", exclude={"messages"})
    messages: list[dict[str, Any]] = [dict(message) for message in compiled_prompt.messages]
    temperature = float(request.get("temperature")) if request.get("temperature") is not None else _default_temperature(task_type)
    max_tokens = _default_max_tokens(task, request)
    thinking_mode = _requested_thinking_mode(request)
    reasoning_effort = _requested_reasoning_effort(request)
    allow_fallback = bool(request.get("allowModelFallback", True))
    allow_tool_execution = bool(request.get("allowToolExecution", True))
    build_tool_specs_started_at = perf_counter()
    tool_specs = build_llm_tool_specs(compiled_prompt.registered_tools) if allow_tool_execution else []
    registered_tools_by_name = {
        str(tool.get("name") or ""): dict(tool)
        for tool in compiled_prompt.registered_tools
        if isinstance(tool, dict) and tool.get("name")
    }
    local_runtime_timings["buildToolSpecsMs"] = _elapsed_ms(build_tool_specs_started_at)
    max_tool_rounds = max(0, int(request.get("maxToolRounds") or 4))
    now = utc_now()
    invocation = runtime_repository.create_model_invocation(
        {
            "appId": getattr(task, "app_id", None),
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

    persist_prompt_started_at = perf_counter()
    prompt_artifact = _persist_prompt_assets(
        session,
        task=task,
        run=run,
        invocation_id=invocation.id,
        compiled_prompt=compiled_prompt,
        workspace_root=workspace_root,
        audit_level=audit_level,
    )
    local_runtime_timings["persistPromptAssetsMs"] = _elapsed_ms(persist_prompt_started_at)
    invocation = runtime_repository.update_model_invocation(
        invocation.id,
        {"promptCompileArtifactId": prompt_artifact.id},
    )

    request_path = ensure_state_subdir("llm/requests", workspace_root) / f"{invocation.id}.json"
    write_initial_request_started_at = perf_counter()
    write_json(
        request_path,
        _request_file_payload(
            audit_level,
            task=task,
            run=run,
            invocation_id=invocation.id,
            route_payload=route_payload,
            temperature=temperature,
            max_tokens=max_tokens,
            thinking_mode=thinking_mode,
            reasoning_effort=reasoning_effort,
            prompt_artifact_id=prompt_artifact.id,
            prompt_metadata=prompt_metadata,
            messages=messages,
            tool_specs=tool_specs,
        ),
    )
    local_runtime_timings["writeInitialRequestMs"] = _elapsed_ms(write_initial_request_started_at)
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
                    "tools": tool_specs,
                    "taskId": task.id,
                    "agentRunId": run.id,
                    "invocationId": invocation.id,
                },
                model=str(route_payload.get("selectedModel")) if route_payload.get("selectedModel") is not None else None,
                model_parameters={
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "thinking": thinking_mode,
                    "reasoning_effort": reasoning_effort,
                },
                metadata={
                    "serviceName": service_name,
                    "requestedProvider": route_payload.get("selectedProvider"),
                    "requestedModel": route_payload.get("selectedModel"),
                    "taskType": task_type,
                    "runType": run_type,
                    "promptProfileId": compiled_prompt.prompt_profile_id,
                    "seedTemplateId": compiled_prompt.seed_template_id,
                    "promptScenario": compiled_prompt.scenario,
                },
            )
            conversation_messages = [dict(message) for message in messages]
            usage_totals = _empty_usage_totals()
            accumulated_cost = 0.0
            budget_check_result: dict[str, Any] | None = None
            budget_overrun_result: dict[str, Any] | None = None
            tool_executions: list[dict[str, Any]] = []
            round_summaries: list[dict[str, Any]] = []
            round_modes: list[str] = []
            context_length_observations = [
                dict(item)
                for item in request.get("contextLengthObservations") or []
                if isinstance(item, dict)
            ]
            final_result: dict[str, Any] | None = None
            last_tool_round_signature: str | None = None
            duplicate_tool_round_streak = 0

            # Check for pending tool calls from a safe-shutdown checkpoint
            _resume_tool_calls: list[dict[str, Any]] | None = None
            _resume_conversation_messages: list[dict[str, Any]] | None = None
            _resume_assistant_message: dict[str, Any] | None = None
            _resume_round_state: dict[str, Any] = {}
            for _pending_action in list(request.get("pendingActions") or []):
                if isinstance(_pending_action, dict) and _pending_action.get("kind") == _PENDING_TOOL_CALLS_KIND:
                    _resume_tool_calls = _pending_action.get("toolCalls") if isinstance(_pending_action.get("toolCalls"), list) else None
                    _resume_conversation_messages = _pending_action.get("conversationMessages") if isinstance(_pending_action.get("conversationMessages"), list) else None
                    _resume_assistant_message = _pending_action.get("assistantMessage") if isinstance(_pending_action.get("assistantMessage"), dict) else None
                    _resume_round_state = _pending_action if isinstance(_pending_action, dict) else {}
                    break

            # Restore state from pending-tool-calls checkpoint if present
            if _resume_conversation_messages is not None:
                conversation_messages = [m for m in _resume_conversation_messages if isinstance(m, dict)]
            if isinstance(_resume_round_state.get("usageTotals"), dict):
                usage_totals = dict(_resume_round_state["usageTotals"])
            if isinstance(_resume_round_state.get("accumulatedCost"), (int, float)):
                accumulated_cost = float(_resume_round_state["accumulatedCost"])
            if isinstance(_resume_round_state.get("roundSummaries"), list):
                round_summaries = [s for s in _resume_round_state["roundSummaries"] if isinstance(s, dict)]
            if isinstance(_resume_round_state.get("roundModes"), list):
                round_modes = [str(m) for m in _resume_round_state["roundModes"]]
            _resume_starting_round = int(_resume_round_state.get("roundIndex", -1)) + 1 if _resume_tool_calls is not None else 0

            model_tool_loop_started_at = perf_counter()

            # If resuming from pending tool calls, execute them before the first LLM call
            if _resume_tool_calls is not None:
                _resume_round_started_at = perf_counter()
                _execute_resumed_tool_calls(
                    tool_calls=_resume_tool_calls,
                    conversation_messages=conversation_messages,
                    tool_executions=tool_executions,
                    assistant_message=_resume_assistant_message,
                    task=task,
                    run=run,
                    root_mount=root_mount,
                    current_context=current_context,
                )
                round_summaries.append({
                    "index": _resume_starting_round - 1,
                    "mode": "checkpoint-resume",
                    "finishReason": "tool-execution-resumed",
                    "latencyMs": _elapsed_ms(_resume_round_started_at),
                    "toolCalls": [str(c.get("name")) for c in _resume_tool_calls if isinstance(c, dict)],
                })
                round_modes.append("checkpoint-resume")

            for round_index in range(_resume_starting_round, max_tool_rounds + 1):
                round_started_at = perf_counter()
                _append_context_length_observation(
                    context_length_observations,
                    phase="beforeModelInvocation",
                    source="promptMessages",
                    estimated_tokens=_estimate_message_tokens(conversation_messages),
                    message_count=len(conversation_messages),
                    round_index=round_index,
                )
                estimated_input_tokens = _estimate_message_tokens(conversation_messages)
                estimated_output_tokens = max(1, int(max_tokens))
                selected_cost_per_1k = float(
                    route_payload.get("costPer1k")
                    or route_payload.get("selectedModelCostPer1k")
                    or FALLBACK_ROUTE_CANDIDATE["costPer1k"]
                )
                estimated_cost = round(
                    ((estimated_input_tokens + estimated_output_tokens) * max(selected_cost_per_1k, 0.0)) / 1000.0,
                    6,
                )
                pre_check = _check_pre_invocation_budget(
                    task,
                    request,
                    estimated_input_tokens=estimated_input_tokens,
                    estimated_output_tokens=estimated_output_tokens,
                    estimated_cost=estimated_cost,
                )
                budget_check_result = pre_check.model_dump(by_alias=True, mode="json")
                if not pre_check.check_passed:
                    round_modes.append("budget-check")
                    round_summaries.append(
                        {
                            "index": round_index,
                            "mode": "budget-check",
                            "finishReason": "pre-invocation-budget-check-failed",
                            "latencyMs": _elapsed_ms(round_started_at),
                            "toolCalls": [],
                            "budgetCheckResult": budget_check_result,
                        }
                    )
                    final_result = {
                        "mode": "budget-check",
                        "provider": route_payload.get("selectedProvider"),
                        "model": route_payload.get("selectedModel"),
                        "finishReason": "pre-invocation-budget-check-failed",
                        "outputText": "Task execution halted: pre-invocation budget check failed.",
                        "toolCalls": [],
                        "error": str(pre_check.reason or "pre-invocation-budget-check-failed"),
                    }
                    break
                if invoke_model is None:
                    result = _local_fallback_result(conversation_messages, route_payload)
                else:
                    result = invoke_model(
                        requested_model=str(route_payload.get("selectedModel")) if route_payload.get("selectedModel") is not None else None,
                        requested_provider=str(route_payload.get("selectedProvider")) if route_payload.get("selectedProvider") is not None else None,
                        messages=conversation_messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        workspace_root=workspace_root,
                        allow_fallback=allow_fallback,
                        tools=tool_specs or None,
                        thinking=thinking_mode,
                        reasoning_effort=reasoning_effort,
                    )

                _merge_usage(usage_totals, dict(result.get("usage") or {}))
                accumulated_cost += float(result.get("costUsed", 0.0) or 0.0)
                post_check = _check_post_invocation_budget(
                    task,
                    input_tokens_used=int(usage_totals.get("inputTokens") or 0),
                    output_tokens_used=int(usage_totals.get("outputTokens") or 0),
                    cost_used=accumulated_cost,
                )
                budget_overrun_result = post_check.model_dump(by_alias=True, mode="json")
                round_modes.append(str(result.get("mode") or "unknown"))
                tool_calls = [call for call in result.get("toolCalls") or [] if isinstance(call, dict) and call.get("name")]
                current_tool_round_signature = _tool_round_signature(tool_calls) if tool_calls else None
                if tool_calls and current_tool_round_signature == last_tool_round_signature and _is_idempotent_tool_round(tool_calls, registered_tools_by_name):
                    duplicate_tool_round_streak += 1
                else:
                    duplicate_tool_round_streak = 0
                last_tool_round_signature = current_tool_round_signature
                round_summaries.append(
                    {
                        "index": round_index,
                        "mode": result.get("mode"),
                        "finishReason": result.get("finishReason"),
                        "latencyMs": _elapsed_ms(round_started_at),
                        "reasoningContentPresent": bool(result.get("reasoningContent")),
                        "toolCalls": [str(call.get("name")) for call in tool_calls],
                        "duplicateToolRoundStreak": duplicate_tool_round_streak,
                        "budgetCheckResult": budget_check_result,
                        "budgetOverrunResult": budget_overrun_result,
                    }
                )
                if result.get("firstTokenLatencyMs") is not None:
                    round_summaries[-1]["firstTokenLatencyMs"] = float(result["firstTokenLatencyMs"])
                if post_check.is_overrun:
                    round_modes.append("budget-check")
                    round_summaries[-1]["finishReason"] = "post-invocation-budget-overrun"
                    final_result = {
                        "mode": "budget-check",
                        "provider": route_payload.get("selectedProvider"),
                        "model": route_payload.get("selectedModel"),
                        "finishReason": "post-invocation-budget-overrun",
                        "outputText": "Task execution halted: post-invocation budget overrun.",
                        "toolCalls": [],
                        "error": "post-invocation-budget-overrun",
                    }
                    break
                if not tool_calls:
                    final_result = result
                    break
                if duplicate_tool_round_streak >= _DUPLICATE_TOOL_ROUND_THRESHOLD:
                    round_summaries[-1]["finishReason"] = "duplicate-tool-loop-short-circuit"
                    round_summaries[-1]["duplicateToolRoundShortCircuited"] = True
                    final_result = _duplicate_tool_loop_result(result, invocation.id, duplicate_streak=duplicate_tool_round_streak)
                    break
                if round_index >= max_tool_rounds:
                    raise RuntimeError(f"Tool round limit exceeded for invocation {invocation.id}.")

                # Graceful shutdown checkpoint: if shutdown requested and there are tool calls,
                # save state and raise SafeShutdownInterrupt instead of executing them.
                if tool_calls and _should_checkpoint_for_pause(task, request):
                    assistant_tool_calls_payload = _assistant_tool_calls_payload(tool_calls, round_index)
                    assistant_message = _assistant_tool_round_message(result, assistant_tool_calls_payload)
                    raise SafeShutdownInterrupt(
                        pending_tool_calls=tool_calls,
                        conversation_messages=conversation_messages,
                        invocation_id=invocation.id,
                        round_index=round_index,
                        usage_totals=dict(usage_totals),
                        accumulated_cost=accumulated_cost,
                        round_summaries=list(round_summaries),
                        round_modes=list(round_modes),
                        assistant_tool_calls_payload=assistant_tool_calls_payload,
                        assistant_message=assistant_message,
                    )

                assistant_tool_calls = _assistant_tool_calls_payload(tool_calls, round_index)
                conversation_messages.append(_assistant_tool_round_message(result, assistant_tool_calls))
                round_tool_failures: list[dict[str, Any]] = []
                for call in tool_calls:
                    tool_call_id = str(call.get("id") or new_id("toolcall", call.get("name"), round_index))
                    isolated_result = _execute_tool_with_isolation(
                        call=call,
                        tool_call_id=tool_call_id,
                        task=task,
                        run=run,
                        root_mount=root_mount,
                        current_context=current_context,
                        max_retries=_MAX_TOOL_RETRIES,
                    )
                    execution = {
                        "tool": {"name": isolated_result.tool_name},
                        "arguments": call.get("arguments") if isinstance(call.get("arguments"), dict) else {},
                        "result": dict(isolated_result.result),
                        "success": bool(isolated_result.success),
                        "toolCallId": isolated_result.tool_call_id,
                        "durationMs": int(isolated_result.duration_ms),
                    }
                    if isolated_result.failure is not None:
                        execution["failure"] = isolated_result.failure.model_dump(by_alias=True, mode="json")
                        round_tool_failures.append(execution["failure"])
                    tool_executions.append(execution)
                    conversation_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "name": str(call.get("name")),
                            "content": tool_result_to_message_content(execution),
                        }
                    )
                round_summaries[-1]["toolFailures"] = round_tool_failures

            if final_result is None:
                raise RuntimeError(f"Invocation {invocation.id} finished without a terminal model result.")

            local_runtime_timings["modelToolLoopMs"] = _elapsed_ms(model_tool_loop_started_at)
            first_token_latency_ms = _first_token_latency_ms_from_round_summaries(round_summaries)
            if first_token_latency_ms is not None:
                local_runtime_timings["firstTokenLatencyMs"] = first_token_latency_ms

            final_message = {
                "role": "assistant",
                "content": str(final_result.get("outputText") or ""),
            }
            if final_result.get("reasoningContent"):
                final_message["reasoning_content"] = str(final_result.get("reasoningContent") or "")
            _append_context_length_observation(
                context_length_observations,
                phase="taskEnd",
                source="conversationMessages",
                estimated_tokens=_estimate_message_tokens([*conversation_messages, final_message]),
                message_count=len(conversation_messages) + 1,
                round_index=(int(round_summaries[-1].get("index")) if round_summaries else 0),
            )

            rewrite_request_started_at = perf_counter()
            write_json(
                request_path,
                _request_file_payload(
                    audit_level,
                    task=task,
                    run=run,
                    invocation_id=invocation.id,
                    route_payload=route_payload,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    thinking_mode=thinking_mode,
                    reasoning_effort=reasoning_effort,
                    prompt_artifact_id=prompt_artifact.id,
                    prompt_metadata=prompt_metadata,
                    messages=messages,
                    tool_specs=tool_specs,
                    conversation_messages=conversation_messages,
                    tool_executions=tool_executions,
                    round_summaries=round_summaries,
                ),
            )
            local_runtime_timings["rewriteRequestTranscriptMs"] = _elapsed_ms(rewrite_request_started_at)

            latency_ms = round((perf_counter() - started_counter) * 1000.0, 2)
            response_path = ensure_state_subdir("llm/responses", workspace_root) / f"{invocation.id}.json"
            response_ref = _invocation_file_ref(response_path, workspace_root)
            all_live_rounds = bool(round_modes) and all(mode == "live" for mode in round_modes)
            final_status = "completed" if all_live_rounds else "fallback"
            finalize_invocation_started_at = perf_counter()
            invocation = runtime_repository.update_model_invocation(
                invocation.id,
                {
                    "status": final_status,
                    "traceId": span["traceId"],
                    "resolvedModel": final_result.get("model") or route_payload.get("selectedModel"),
                    "resolvedProvider": final_result.get("provider"),
                    "promptCompileArtifactId": prompt_artifact.id,
                    "responseRef": response_ref.model_dump(mode="json"),
                    "inputTokensUsed": usage_totals["inputTokens"],
                    "outputTokensUsed": usage_totals["outputTokens"],
                    "costUsed": round(accumulated_cost, 6),
                    "latencyMs": latency_ms,
                    "errorSummary": str(final_result.get("error")) if final_result.get("error") is not None else None,
                    "endedAt": utc_now(),
                },
            )
            finish_langfuse_generation(
                langfuse_generation,
                output=final_result.get("outputText"),
                metadata={
                    "invocationId": invocation.id,
                    "status": invocation.status,
                    "provider": invocation.resolved_provider,
                    "mode": final_result.get("mode"),
                    "toolExecutionCount": len(tool_executions),
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
                status_message=str(final_result.get("error")) if invocation.status != "completed" else None,
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
            local_runtime_timings["finalizeInvocationMs"] = _elapsed_ms(finalize_invocation_started_at)
            response_payload = _response_file_payload(
                audit_level,
                task=task,
                run=run,
                invocation_id=invocation.id,
                prompt_artifact_id=prompt_artifact.id,
                final_result=final_result,
                usage_totals=usage_totals,
                accumulated_cost=accumulated_cost,
                tool_executions=tool_executions,
                round_summaries=round_summaries,
                local_runtime_timings={
                    **local_runtime_timings,
                    "preResponseWriteTotalMs": _elapsed_ms(local_started_at),
                },
                first_token_latency_ms=first_token_latency_ms,
                context_length_observations=context_length_observations,
                runtime_metrics=request.get("runtimeMetrics") if isinstance(request.get("runtimeMetrics"), dict) else None,
            )
            write_response_started_at = perf_counter()
            write_json(response_path, response_payload)
            local_runtime_timings["writeResponseMs"] = _elapsed_ms(write_response_started_at)
            local_runtime_timings["totalLocalMs"] = _elapsed_ms(local_started_at)
            return {
                "assistantText": str(final_result.get("outputText") or ""),
                "invocation": invocation.model_dump(by_alias=True, mode="json"),
                "prompt": compiled_prompt.model_dump(by_alias=True, mode="json", exclude={"messages"}),
                "promptArtifact": prompt_artifact.model_dump(by_alias=True, mode="json"),
                "toolExecutions": tool_executions,
                "roundSummaries": round_summaries,
                "usage": dict(usage_totals),
                "costUsed": float(accumulated_cost or 0.0),
                "status": invocation.status,
                "auditLevel": audit_level,
                "budgetCheckResult": budget_check_result,
                "budgetOverrunResult": budget_overrun_result,
                "contextLengthObservations": list(context_length_observations),
                "runtimeMetrics": dict(request.get("runtimeMetrics") or {}),
                "timings": dict(local_runtime_timings),
            }
    except Exception as exc:
        latency_ms = round((perf_counter() - started_counter) * 1000.0, 2)
        failure_messages = conversation_messages if "conversation_messages" in locals() and isinstance(conversation_messages, list) else None
        failure_tool_executions = tool_executions if "tool_executions" in locals() and isinstance(tool_executions, list) else []
        failure_round_summaries = round_summaries if "round_summaries" in locals() and isinstance(round_summaries, list) else []
        failure_usage_totals = usage_totals if "usage_totals" in locals() and isinstance(usage_totals, dict) else _empty_usage_totals()
        failure_cost_used = float(accumulated_cost) if "accumulated_cost" in locals() else 0.0
        failure_prompt_artifact_id = prompt_artifact.id if "prompt_artifact" in locals() else None
        failure_first_token_latency_ms = _first_token_latency_ms_from_round_summaries(failure_round_summaries)
        failure_context_length_observations = (
            list(context_length_observations)
            if "context_length_observations" in locals() and isinstance(context_length_observations, list)
            else []
        )
        failure_result = {
            "mode": (round_modes[-1] if "round_modes" in locals() and round_modes else None),
            "provider": route_payload.get("selectedProvider"),
            "model": route_payload.get("selectedModel"),
            "finishReason": "error",
            "error": str(exc),
        }
        response_ref_payload = None
        try:
            rewrite_request_started_at = perf_counter()
            write_json(
                request_path,
                _request_file_payload(
                    audit_level,
                    task=task,
                    run=run,
                    invocation_id=invocation.id,
                    route_payload=route_payload,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    thinking_mode=thinking_mode,
                    reasoning_effort=reasoning_effort,
                    prompt_artifact_id=str(failure_prompt_artifact_id or prompt_metadata.get("id") or ""),
                    prompt_metadata=prompt_metadata,
                    messages=messages,
                    tool_specs=tool_specs,
                    conversation_messages=failure_messages,
                    tool_executions=failure_tool_executions,
                    round_summaries=failure_round_summaries,
                ),
            )
            local_runtime_timings["rewriteRequestTranscriptMs"] = _elapsed_ms(rewrite_request_started_at)

            response_path = ensure_state_subdir("llm/responses", workspace_root) / f"{invocation.id}.json"
            response_ref_payload = _invocation_file_ref(response_path, workspace_root).model_dump(mode="json")
            write_response_started_at = perf_counter()
            write_json(
                response_path,
                _response_file_payload(
                    audit_level,
                    task=task,
                    run=run,
                    invocation_id=invocation.id,
                    prompt_artifact_id=str(failure_prompt_artifact_id or prompt_metadata.get("id") or ""),
                    final_result=failure_result,
                    usage_totals=failure_usage_totals,
                    accumulated_cost=failure_cost_used,
                    tool_executions=failure_tool_executions,
                    round_summaries=failure_round_summaries,
                    local_runtime_timings={
                        **local_runtime_timings,
                        "preResponseWriteTotalMs": _elapsed_ms(local_started_at),
                    },
                    first_token_latency_ms=failure_first_token_latency_ms,
                    context_length_observations=failure_context_length_observations,
                    runtime_metrics=request.get("runtimeMetrics") if isinstance(request.get("runtimeMetrics"), dict) else None,
                ),
            )
            local_runtime_timings["writeResponseMs"] = _elapsed_ms(write_response_started_at)
        except Exception as persist_exc:
            record_log(
                service_name,
                "warning",
                "Failed to persist model invocation failure artifacts.",
                attributes={
                    "taskId": task.id,
                    "agentRunId": run.id,
                    "invocationId": invocation.id,
                    "errorMessage": str(persist_exc),
                },
                workspace_root=workspace_root,
            )
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
                "resolvedModel": str(route_payload.get("selectedModel") or invocation.requested_model),
                "resolvedProvider": str(route_payload.get("selectedProvider") or invocation.requested_provider or "") or None,
                "responseRef": response_ref_payload,
                "inputTokensUsed": int(failure_usage_totals.get("inputTokens") or 0),
                "outputTokensUsed": int(failure_usage_totals.get("outputTokens") or 0),
                "costUsed": round(failure_cost_used, 6),
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
        local_runtime_timings["totalLocalMs"] = _elapsed_ms(local_started_at)
        raise