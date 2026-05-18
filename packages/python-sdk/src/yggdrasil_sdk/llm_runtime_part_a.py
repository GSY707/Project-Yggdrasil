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


def _context_token_estimate(current_context: list[dict[str, Any]]) -> int:
    estimate = 0
    for item in current_context:
        if not isinstance(item, dict):
            continue
        parts = [
            str(item.get(key) or "")
            for key in ("title", "content", "summary", "normalizedText", "excerpt", "note")
            if item.get(key)
        ]
        for part in parts:
            compact = " ".join(part.split()).strip()
            if compact:
                estimate += max(1, len(compact) // 4)
    return estimate


def _window_execution_metadata_summary(
    request: dict[str, Any],
    root_mount: dict[str, Any],
    current_context: list[dict[str, Any]],
    *,
    resume_path: str | None,
    final_result: dict[str, Any] | None = None,
    tool_executions: list[dict[str, Any]] | None = None,
    round_summaries: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    runtime_metrics = request.get("runtimeMetrics") if isinstance(request.get("runtimeMetrics"), dict) else {}
    takeover_protocol = request.get("takeoverProtocol") if isinstance(request.get("takeoverProtocol"), dict) else {}
    work_tree = takeover_protocol.get("workTree") if isinstance(takeover_protocol.get("workTree"), dict) else {}
    memory_retrieval_state = request.get("memoryRetrievalState") if isinstance(request.get("memoryRetrievalState"), dict) else {}
    current_titles = [
        str(item.get("title") or item.get("kind") or item.get("id") or "").strip()
        for item in current_context
        if isinstance(item, dict)
    ]
    current_titles = [title for title in current_titles if title][:5]
    summary = {
        "windowIndex": int(runtime_metrics.get("windowIndex") or 1),
        "restartCount": int(runtime_metrics.get("restartCount") or 0),
        "resumePath": resume_path or "start",
        "effectiveContextWindow": int(runtime_metrics.get("effectiveContextWindow") or 0),
        "windowRestartThreshold": int(runtime_metrics.get("windowRestartThreshold") or 0),
        "windowSpanTokens": int(runtime_metrics.get("windowSpanTokens") or 0),
        "currentObjective": str(request.get("currentObjective") or request.get("taskObjective") or "").strip() or None,
        "currentFocus": str(request.get("currentFocus") or "").strip() or None,
        "currentContextCount": len([item for item in current_context if isinstance(item, dict)]),
        "currentContextTokenEstimate": _context_token_estimate(current_context),
        "currentContextTitlesPreview": current_titles,
        "workTreeNodeId": str(work_tree.get("currentNodeId") or "").strip() or None,
        "workTreeStatus": str(work_tree.get("status") or "").strip() or None,
        "workTreeRecoveryAnchor": str(work_tree.get("recoveryAnchor") or "").strip() or None,
        "memoryRetrievalRequestId": str(memory_retrieval_state.get("requestId") or "").strip() or None,
        "memoryRetrievalSummary": str(memory_retrieval_state.get("summary") or "").strip() or None,
        "memoryReverseTraceMode": bool(memory_retrieval_state.get("reverseTraceMode", False)),
        "memoryRetrievalWorkTreeNodeId": str(memory_retrieval_state.get("workTreeNodeId") or "").strip() or None,
        "rootSummaryPreview": normalize_excerpt(str(root_mount.get("rootSummary") or ""), 240) or None,
    }
    if final_result is not None:
        assistant_text = str(final_result.get("outputText") or "")
        lowered_text = " ".join(assistant_text.split()).strip().lower()
        planning_stub = int(
            (
                "先总结当前局势" in lowered_text
                or "最稳妥的下一步" in lowered_text
                or "当前局势" in lowered_text
            )
            and "任务价值判断" not in lowered_text
            and "acceptance 对照结论" not in lowered_text
        )
        summary.update(
            {
                "assistantTextSummary": normalize_excerpt(assistant_text, 240) or None,
                "planningStub0_1": planning_stub,
                "finishReason": str(final_result.get("finishReason") or "").strip() or None,
                "toolExecutionCount": len([item for item in tool_executions or [] if isinstance(item, dict)]),
                "roundCount": len([item for item in round_summaries or [] if isinstance(item, dict)]),
            }
        )
    return summary


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


def _estimated_input_tokens_for_precheck(*, raw_message_tokens: int, max_tokens: int, request: dict[str, Any]) -> int:
    configured_estimate = request.get("estimatedInputTokens")
    if configured_estimate is not None:
        try:
            return max(16, int(configured_estimate))
        except (TypeError, ValueError):
            pass
    # Prompt transcript may include heavyweight scaffolding. Cap with max_tokens-derived bound
    # to reduce false negatives in pre-check while keeping a conservative estimate.
    cap = max(96, min(max_tokens, max_tokens // 2))
    return max(16, min(max(1, int(raw_message_tokens)), cap))


def _estimated_output_tokens_for_precheck(*, max_tokens: int, request: dict[str, Any]) -> int:
    configured_estimate = request.get("estimatedOutputTokens")
    if configured_estimate is not None:
        try:
            return max(16, min(int(configured_estimate), max_tokens))
        except (TypeError, ValueError):
            pass
    # maxTokens is an upper bound, not expected usage; keep pre-check conservative but not overly pessimistic.
    return max(32, min(max_tokens, max(64, max_tokens // 4), 128))


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
        "assistantText": str(final_result.get("outputText") or ""),
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


__all__ = [name for name in globals() if not name.startswith("__")]


