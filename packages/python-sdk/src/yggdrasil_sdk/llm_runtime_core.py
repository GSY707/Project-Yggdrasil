from __future__ import annotations
import fnmatch
from hashlib import sha1
import json
import os
from pathlib import Path
import re
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
def _required_tool_argument_keys(tool_descriptor: dict[str, Any] | None) -> list[str]:
    if not isinstance(tool_descriptor, dict):
        return []
    schema = tool_descriptor.get("inputSchema") if isinstance(tool_descriptor.get("inputSchema"), dict) else {}
    required = schema.get("required") if isinstance(schema.get("required"), list) else []
    return [str(item).strip() for item in required if str(item).strip()]
_NESTED_ARGUMENT_CONTAINER_KEYS = ("arguments", "params", "input", "payload", "kwargs", "data")
_ARGUMENT_KEY_ALIASES: dict[str, tuple[str, ...]] = {
    "path": ("filePath", "filepath", "file", "filename", "targetPath"),
    "content": ("text", "body", "value"),
    "command": ("cmd", "shellCommand", "shell_command"),
    "code": ("python", "pythonCode", "script"),
    "query": ("queryText", "text", "q"),
    "oldText": ("old", "oldValue", "old_value"),
    "newText": ("new", "newValue", "new_value"),
    "workingDirectory": ("cwd", "workingDir", "working_dir"),
    "startLine": ("start", "start_line"),
    "endLine": ("end", "end_line"),
}
def _normalize_argument_key(key: Any) -> str:
    return "".join(char for char in str(key or "").lower() if char.isalnum())
def _argument_alias_candidates(required_key: str) -> set[str]:
    aliases = set(_ARGUMENT_KEY_ALIASES.get(required_key, ()))
    aliases.add(required_key)
    return {_normalize_argument_key(alias) for alias in aliases if str(alias).strip()}
def _parse_argument_container(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return dict(value)
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or not (text.startswith("{") and text.endswith("}")):
        return None
    try:
        parsed = json.loads(text)
    except Exception:
        return None
    return dict(parsed) if isinstance(parsed, dict) else None
def _find_argument_candidate(arguments: dict[str, Any], required_key: str) -> Any:
    if not isinstance(arguments, dict):
        return None
    direct_value = arguments.get(required_key)
    if not _is_placeholder_argument_value(direct_value):
        return direct_value

    aliases = _argument_alias_candidates(required_key)
    for key, value in arguments.items():
        if _is_placeholder_argument_value(value):
            continue
        if _normalize_argument_key(key) in aliases:
            return value
    return None
def _unwrap_nested_arguments(
    arguments: dict[str, Any],
    required_keys: list[str],
) -> tuple[dict[str, Any], bool]:
    repaired = dict(arguments or {})
    changed = False
    for container_key in _NESTED_ARGUMENT_CONTAINER_KEYS:
        nested = _parse_argument_container(repaired.get(container_key))
        if not nested:
            continue
        should_merge = any(_find_argument_candidate(nested, required_key) is not None for required_key in required_keys)
        if not should_merge:
            continue
        repaired.pop(container_key, None)
        for key, value in nested.items():
            if key not in repaired or _is_placeholder_argument_value(repaired.get(key)):
                repaired[key] = value
        changed = True
    return repaired, changed
def _is_placeholder_argument_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, dict):
        return len(value) == 0
    if isinstance(value, (list, tuple, set)):
        return len(value) == 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        return normalized in {"", "{}", "{ }", "null", "none", '"{}"', "'{}'"}
    return False
def _extract_required_value_from_arguments_text(call: dict[str, Any], required_key: str) -> Any:
    raw_text = call.get("argumentsText")
    if not isinstance(raw_text, str):
        return None
    arguments_text = raw_text.strip()
    if not arguments_text or arguments_text in {"{}", "{ }"}:
        return None

    json_candidates = [arguments_text]
    first_brace = arguments_text.find("{")
    last_brace = arguments_text.rfind("}")
    if first_brace >= 0 and last_brace > first_brace:
        fragment = arguments_text[first_brace : last_brace + 1].strip()
        if fragment and fragment not in json_candidates:
            json_candidates.append(fragment)

    for json_candidate in json_candidates:
        try:
            parsed = json.loads(json_candidate)
        except Exception:
            continue
        if not isinstance(parsed, dict):
            continue
        candidate = _find_argument_candidate(parsed, required_key)
        if _is_placeholder_argument_value(candidate):
            continue
        for container_key in _NESTED_ARGUMENT_CONTAINER_KEYS:
            nested = _parse_argument_container(parsed.get(container_key))
            if not nested:
                continue
            candidate = _find_argument_candidate(nested, required_key)
            if _is_placeholder_argument_value(candidate):
                continue
            return candidate
        if _is_placeholder_argument_value(candidate):
            continue
        return candidate

    key_pattern = re.escape(required_key)
    match = re.search(
        rf"(?is)(?:\"{key_pattern}\"|'{key_pattern}'|\b{key_pattern}\b)\s*[:=]\s*(?:\"([^\"]+)\"|'([^']+)'|([^,;\s\]\}}]+))",
        arguments_text,
    )
    if match:
        candidate = next((group for group in match.groups() if group is not None), None)
        if candidate is not None and not _is_placeholder_argument_value(candidate):
            return candidate.strip()

    return None
def _repair_tool_arguments(
    call: dict[str, Any],
    arguments: dict[str, Any],
    tool_descriptor: dict[str, Any] | None,
) -> tuple[dict[str, Any], str | None]:
    repaired = dict(arguments or {})
    required_keys = _required_tool_argument_keys(tool_descriptor)
    if not required_keys:
        return repaired, None

    repaired, unwrapped = _unwrap_nested_arguments(repaired, required_keys)
    repair_mode = "nested-arguments-unwrapped" if unwrapped else None

    # Treat placeholder values like "{}" as missing so they won't be forwarded as fake params.
    for key in required_keys:
        if key in repaired and _is_placeholder_argument_value(repaired.get(key)):
            repaired.pop(key, None)

    for key in required_keys:
        if key in repaired and not _is_placeholder_argument_value(repaired.get(key)):
            continue
        candidate_value = _find_argument_candidate(repaired, key)
        if candidate_value is None or _is_placeholder_argument_value(candidate_value):
            continue
        repaired[key] = candidate_value

    extracted_any = False
    for key in required_keys:
        if key in repaired and not _is_placeholder_argument_value(repaired.get(key)):
            continue
        extracted = _extract_required_value_from_arguments_text(call, key)
        if extracted is None or _is_placeholder_argument_value(extracted):
            continue
        repaired[key] = extracted
        extracted_any = True
    if extracted_any:
        return repaired, "argumentsText-required"

    missing_required = [
        key
        for key in required_keys
        if key not in repaired or _is_placeholder_argument_value(repaired.get(key))
    ]
    if not missing_required:
        return repaired, repair_mode

    if len(required_keys) == 1:
        required_key = required_keys[0]
        candidate_value = repaired.get("value")
        if candidate_value is not None and not _is_placeholder_argument_value(candidate_value):
            repaired[required_key] = candidate_value
            repaired.pop("value", None)
            return repaired, "value-to-required"

        extracted_from_arguments_text = _extract_required_value_from_arguments_text(call, required_key)
        if extracted_from_arguments_text is not None:
            repaired[required_key] = extracted_from_arguments_text
            return repaired, "argumentsText-required"

        raw_text = str(repaired.get("_raw") or call.get("argumentsText") or "").strip()
        if raw_text and raw_text not in {"{}", "{ }"} and not (raw_text.startswith("{") and raw_text.endswith("}")):
            repaired[required_key] = raw_text
            repaired.pop("_raw", None)
            return repaired, "raw-to-required"

    return repaired, None
def _fallback_required_argument_value(
    *,
    tool_name: str,
    required_key: str,
    call: dict[str, Any],
    task: Any,
    current_context: list[dict[str, Any]],
) -> Any:
    normalized_tool = str(tool_name or "").strip().lower()
    normalized_key = str(required_key or "").strip()
    if not normalized_tool or not normalized_key:
        return None

    if normalized_tool == "text_memory.read_node" and normalized_key == "nodeId":
        return None

    if normalized_tool in {"text_memory.retrieve", "mcp.search.search_text"} and normalized_key in {"queryText", "query"}:
        raw_text = str(call.get("argumentsText") or "").strip()
        if raw_text and raw_text not in {"{}", "{ }"} and not (raw_text.startswith("{") and raw_text.endswith("}")):
            return raw_text

        for attr_name in ("current_objective", "current_focus", "goal", "title"):
            value = str(getattr(task, attr_name, "") or "").strip()
            if value:
                return value

        for item in current_context:
            if not isinstance(item, dict):
                continue
            for field in ("title", "content"):
                value = str(item.get(field) or "").strip()
                if value:
                    return value

    return None
_TOOL_ARGUMENT_EXAMPLE_OVERRIDES: dict[str, dict[str, Any]] = {
    "mcp.execute.run_command": {"command": "dir", "cwd": ".", "timeoutMs": 10000},
    "mcp.python.run_python": {"code": "print('hello')", "workingDirectory": ".", "timeoutMs": 10000},
    "mcp.edit.write_file": {"path": "tmp/graduate-deliverables/report.md", "content": "# Title\n"},
    "mcp.read.read_file": {"path": "README.md", "startLine": 1, "endLine": 120},
    "mcp.search.search_text": {"query": "double descent", "glob": "**/*.md", "maxResults": 20},
}
def _build_tool_argument_example(tool_name: str, tool_descriptor: dict[str, Any] | None) -> dict[str, Any]:
    normalized_tool_name = str(tool_name or "").strip()
    if normalized_tool_name in _TOOL_ARGUMENT_EXAMPLE_OVERRIDES:
        return dict(_TOOL_ARGUMENT_EXAMPLE_OVERRIDES[normalized_tool_name])

    example: dict[str, Any] = {}
    schema = tool_descriptor.get("inputSchema") if isinstance(tool_descriptor, dict) and isinstance(tool_descriptor.get("inputSchema"), dict) else {}
    properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
    required = _required_tool_argument_keys(tool_descriptor)
    for key in required:
        payload = properties.get(key) if isinstance(properties.get(key), dict) else {}
        value_type = str(payload.get("type") or "string").strip().lower()
        if value_type == "integer":
            example[key] = max(int(payload.get("minimum") or 1), 1)
        elif value_type == "number":
            example[key] = float(payload.get("minimum") or 1.0)
        elif value_type == "boolean":
            example[key] = True
        elif value_type == "array":
            example[key] = []
        elif value_type == "object":
            example[key] = {}
        else:
            example[key] = f"<{key}>"
    return example
def _tool_argument_error_payload(
    *,
    tool_name: str,
    error_message: str,
    required_keys: list[str],
    tool_descriptor: dict[str, Any] | None,
    cause: str,
) -> dict[str, Any]:
    example_arguments = _build_tool_argument_example(tool_name, tool_descriptor)
    return {
        "status": "error",
        "error": error_message,
        "errorType": "ToolCallValidationError",
        "cause": cause,
        "requiredArguments": required_keys,
        "exampleArguments": example_arguments,
        "hint": (
            "Tool is reachable but arguments are invalid. "
            "Please retry with required arguments and valid JSON object shape."
        ),
    }
def _is_tool_argument_error_message(message: str) -> bool:
    lowered = str(message or "").strip().lower()
    if not lowered:
        return False
    markers = (
        "missing required argument",
        "required",
        "is required",
        "invalid argument",
        "unexpected argument",
        "expects",
    )
    return any(marker in lowered for marker in markers)
def _execute_tool_with_isolation(
    *,
    call: dict[str, Any],
    tool_call_id: str,
    task: Any,
    run: Any,
    root_mount: dict[str, Any],
    current_context: list[dict[str, Any]],
    tool_descriptor: dict[str, Any] | None = None,
    max_retries: int = _MAX_TOOL_RETRIES,
) -> ToolExecutionResult:
    """Execute a single tool call with retryable-failure isolation and structured result."""
    tool_name = str(call.get("name") or "")
    arguments = call.get("arguments") if isinstance(call.get("arguments"), dict) else {}
    repaired_arguments, repair_mode = _repair_tool_arguments(call, arguments, tool_descriptor)
    arguments = repaired_arguments
    required_keys = _required_tool_argument_keys(tool_descriptor)
    missing_required = [
        key
        for key in required_keys
        if key not in arguments or _is_placeholder_argument_value(arguments.get(key))
    ]

    if missing_required:
        for required_key in list(missing_required):
            fallback_value = _fallback_required_argument_value(
                tool_name=tool_name,
                required_key=required_key,
                call=call,
                task=task,
                current_context=current_context,
            )
            if fallback_value is not None and not _is_placeholder_argument_value(fallback_value):
                arguments[required_key] = fallback_value

        missing_required = [
            key
            for key in required_keys
            if key not in arguments or _is_placeholder_argument_value(arguments.get(key))
        ]

    if tool_name == "text_memory.read_node" and missing_required == ["nodeId"]:
        missing_required = []

    if missing_required:
        validation_error = (
            f"missing required argument(s): {', '.join(missing_required)} "
            f"for tool '{tool_name}' after normalization"
        )
        validation_payload = _tool_argument_error_payload(
            tool_name=tool_name,
            error_message=validation_error,
            required_keys=required_keys,
            tool_descriptor=tool_descriptor,
            cause="missing-required-arguments",
        )
        return ToolExecutionResult(
            toolName=tool_name,
            toolCallId=tool_call_id,
            success=False,
            result=validation_payload,
            failure=ToolExecutionFailure(
                toolName=tool_name,
                errorMessage=validation_error,
                errorType="ToolCallValidationError",
                retryCount=0,
                isRetryable=False,
            ),
            durationMs=0,
        )

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
            if repair_mode is None:
                repaired_again, repaired_mode = _repair_tool_arguments(call, arguments, tool_descriptor)
                if repaired_mode is not None and repaired_again != arguments:
                    arguments = repaired_again
                    repair_mode = repaired_mode
                    continue
            retryable = _is_retryable_tool_exception(exc)
            if retryable and attempt < max_retries:
                continue
            error_message = str(exc)
            if _is_tool_argument_error_message(error_message):
                error_payload = _tool_argument_error_payload(
                    tool_name=tool_name,
                    error_message=error_message,
                    required_keys=required_keys,
                    tool_descriptor=tool_descriptor,
                    cause="invalid-arguments",
                )
                error_type = "ToolCallValidationError"
            else:
                error_payload = {"status": "error", "error": error_message}
                error_type = exc.__class__.__name__
            failure = ToolExecutionFailure(
                toolName=tool_name,
                errorMessage=error_message,
                errorType=error_type,
                retryCount=attempt,
                isRetryable=retryable,
            )
            return ToolExecutionResult(
                toolName=tool_name,
                toolCallId=tool_call_id,
                success=False,
                result=error_payload,
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
def _tool_name_alias_map(registered_tools_by_name: dict[str, dict[str, Any]]) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for canonical_name in registered_tools_by_name.keys():
        normalized = str(canonical_name or "").strip()
        if not normalized:
            continue
        aliases[normalized] = normalized
        aliases[normalized.lower()] = normalized
        aliases[normalized.replace(".", "_")] = normalized
        aliases[normalized.replace(".", "_").lower()] = normalized
    return aliases
def _canonical_tool_name(raw_name: Any, tool_name_aliases: dict[str, str] | None) -> str:
    name = str(raw_name or "").strip()
    if not name:
        return ""
    if not isinstance(tool_name_aliases, dict) or not tool_name_aliases:
        return name
    return (
        tool_name_aliases.get(name)
        or tool_name_aliases.get(name.lower())
        or name
    )
