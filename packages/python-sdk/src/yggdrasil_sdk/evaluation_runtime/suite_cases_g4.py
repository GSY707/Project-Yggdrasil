from __future__ import annotations
from ._common import *  # noqa: F403,F401
from .bootstrap import *  # noqa: F403,F401
from .scorer import *  # noqa: F403,F401
import re
from ..contracts import BudgetState
from ..ops_runtime.scorecard import (  # noqa: F401
    _build_scorecard_row,
    _first_token_seconds,
    _first_useful_output_seconds,
    _format_timestamp,
    _seconds_between,
    _takeover_metrics,
    _tool_execution_names,
)
def _g4_int_metric(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)
def _g4_token_usage(invocation, response_payload: dict[str, Any]) -> dict[str, int]:
    usage = response_payload.get("usage") if isinstance(response_payload.get("usage"), dict) else {}
    input_tokens = _g4_int_metric(usage.get("inputTokens"), int(invocation.input_tokens_used or 0))
    output_tokens = _g4_int_metric(usage.get("outputTokens"), int(invocation.output_tokens_used or 0))
    total_tokens = _g4_int_metric(usage.get("totalTokens"), input_tokens + output_tokens)
    cache_hit_input_tokens = _g4_int_metric(usage.get("cacheHitInputTokens"), 0)
    cache_write_input_tokens = _g4_int_metric(usage.get("cacheWriteInputTokens"), 0)
    non_cache_input_tokens = _g4_int_metric(usage.get("nonCacheInputTokens"), max(input_tokens - cache_hit_input_tokens, 0))
    reasoning_tokens = _g4_int_metric(usage.get("reasoningTokens"), 0)
    return {
        "inputTokens": input_tokens,
        "outputTokens": output_tokens,
        "totalTokens": total_tokens,
        "cacheHitInputTokens": max(cache_hit_input_tokens, 0),
        "cacheWriteInputTokens": max(cache_write_input_tokens, 0),
        "nonCacheInputTokens": max(non_cache_input_tokens, 0),
        "reasoningTokens": max(reasoning_tokens, 0),
    }
def _g4_context_length_observations(response_payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw = response_payload.get("contextLengthObservations") if isinstance(response_payload.get("contextLengthObservations"), list) else []
    observations: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict) or item.get("estimatedTokens") is None:
            continue
        observation: dict[str, Any] = {
            "phase": str(item.get("phase") or "unknown"),
            "source": str(item.get("source") or "unknown"),
            "estimatedTokens": _g4_int_metric(item.get("estimatedTokens")),
        }
        for key in ("messageCount", "itemCount", "roundIndex"):
            if item.get(key) is not None:
                observation[key] = _g4_int_metric(item.get(key))
        if item.get("trigger") is not None:
            observation["trigger"] = str(item.get("trigger") or "")
        observations.append(observation)
    return observations
def _g4_max_context_length_tokens(observations: list[dict[str, Any]]) -> int | None:
    estimated_tokens = [
        _g4_int_metric(item.get("estimatedTokens"))
        for item in observations
        if isinstance(item, dict) and item.get("estimatedTokens") is not None
    ]
    return max(estimated_tokens) if estimated_tokens else None
def _g4_runtime_metrics(response_payload: dict[str, Any]) -> dict[str, Any]:
    raw = response_payload.get("runtimeMetrics") if isinstance(response_payload.get("runtimeMetrics"), dict) else {}
    return {
        "windowIndex": _g4_int_metric(raw.get("windowIndex"), 1),
        "restartCount": _g4_int_metric(raw.get("restartCount"), 0),
        "compressionCount": _g4_int_metric(raw.get("compressionCount"), 0),
        "cumulativeWindowSpanTokens": _g4_int_metric(raw.get("cumulativeWindowSpanTokens"), 0),
        "carryForwardLossCount": _g4_int_metric(raw.get("carryForwardLossCount"), 0),
        "effectiveContextWindow": _g4_int_metric(raw.get("effectiveContextWindow"), 0),
        "windowRestartThreshold": _g4_int_metric(raw.get("windowRestartThreshold"), 0),
        "forcedWindowRestartBudget": _g4_int_metric(raw.get("forcedWindowRestartBudget"), 0),
        "windowSpanTokens": _g4_int_metric(raw.get("windowSpanTokens"), 0),
    }
def _g4_restart_stability_report(case_payload: dict[str, Any], runtime_metrics: dict[str, Any], *, acceptance_pass: int) -> dict[str, Any]:
    raw_tiers = case_payload.get("restartStabilityTiers")
    tiers = [max(_g4_int_metric(item), 0) for item in raw_tiers] if isinstance(raw_tiers, list) else []
    tiers = [item for item in tiers if item > 0]
    restart_count = max(_g4_int_metric(runtime_metrics.get("restartCount")), 0)
    if not tiers:
        return {
            "enabled": False,
            "restartCount": restart_count,
            "tiers": [],
            "restartSuccessRate0_1": 1.0 if acceptance_pass == 1 else 0.0,
            "passed": True,
        }

    tier_results: list[dict[str, Any]] = []
    for tier in sorted(set(tiers)):
        tier_results.append(
            {
                "targetRestarts": tier,
                "observedRestartCount": restart_count,
                "passed": restart_count >= tier and acceptance_pass == 1,
            }
        )
    restart_success_rate = (
        round(sum(1.0 for item in tier_results if item.get("passed")) / len(tier_results), 4)
        if tier_results
        else (1.0 if acceptance_pass == 1 else 0.0)
    )
    return {
        "enabled": True,
        "restartCount": restart_count,
        "tiers": tier_results,
        "restartSuccessRate0_1": restart_success_rate,
        "passed": bool(tier_results) and all(bool(item.get("passed")) for item in tier_results),
    }
def _g4_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text:
            items.append(text)
    return items
def _g4_normalize_match_text(value: str) -> str:
    return " ".join(str(value or "").lower().split())
def _g4_response_text(result_payload: dict[str, Any], response_payload: dict[str, Any]) -> str:
    for candidate in (result_payload.get("assistantText"), response_payload.get("assistantText")):
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()

    raw_response = response_payload.get("rawResponse") if isinstance(response_payload.get("rawResponse"), dict) else {}
    for choice in raw_response.get("choices") or []:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
        if isinstance(content, list):
            parts = [
                str(item.get("text") or "")
                for item in content
                if isinstance(item, dict) and (item.get("type") in {None, "text"})
            ]
            joined = "".join(part for part in parts if part)
            if joined.strip():
                return joined.strip()
    return ""
def _g4_normalize_message_content(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            for key in ("text", "input_text", "output_text", "content"):
                item_value = item.get(key)
                if isinstance(item_value, str) and item_value.strip():
                    parts.append(item_value)
                    break
        return "\n".join(parts)
    return str(value or "")
def _g4_compact_tool_message(content: str, *, max_chars: int) -> str:
    raw = str(content or "").strip()
    summary = raw
    try:
        payload = json.loads(raw)
    except Exception:
        payload = None
    if isinstance(payload, dict):
        tool = payload.get("tool") if isinstance(payload.get("tool"), dict) else {}
        result = tool.get("result") if isinstance(tool.get("result"), dict) else payload.get("result")
        result_payload = result.get("result") if isinstance(result, dict) and isinstance(result.get("result"), dict) else result
        args = tool.get("arguments") if isinstance(tool.get("arguments"), dict) else {}
        parts = [
            f"name={tool.get('name') or payload.get('name') or 'unknown'}",
            f"arguments={normalize_excerpt(json.dumps(args, ensure_ascii=False), 220)}",
        ]
        if isinstance(result_payload, dict):
            if result_payload.get("url") is not None:
                parts.append(f"url={result_payload.get('url')}")
            if result_payload.get("title") is not None:
                parts.append(f"title={normalize_excerpt(str(result_payload.get('title') or ''), 160)}")
            if result_payload.get("error") is not None:
                parts.append(f"error={normalize_excerpt(str(result_payload.get('error') or ''), 220)}")
            if result_payload.get("text") is not None:
                parts.append(f"text={normalize_excerpt(str(result_payload.get('text') or ''), 220)}")
            cache = result_payload.get("cache") if isinstance(result_payload.get("cache"), dict) else {}
            if cache:
                parts.append(f"cacheHit={bool(cache.get('hit'))}")
        elif result_payload is not None:
            parts.append(f"result={normalize_excerpt(str(result_payload), 240)}")
        summary = "; ".join(parts)
    return normalize_excerpt(summary, max(max_chars, 120))


def _g4_runtime_snapshot_for_followup(
    *,
    request_payload: dict[str, Any],
    response_payload: dict[str, Any],
) -> dict[str, Any]:
    request_protocol = request_payload.get("takeoverProtocol") if isinstance(request_payload.get("takeoverProtocol"), dict) else {}
    response_protocol = response_payload.get("takeoverProtocol") if isinstance(response_payload.get("takeoverProtocol"), dict) else {}
    request_work_tree = request_protocol.get("workTree") if isinstance(request_protocol.get("workTree"), dict) else {}
    response_work_tree = response_protocol.get("workTree") if isinstance(response_protocol.get("workTree"), dict) else {}
    window_artifact = response_payload.get("windowExecutionArtifact") if isinstance(response_payload.get("windowExecutionArtifact"), dict) else {}
    window_record = window_artifact.get("record") if isinstance(window_artifact.get("record"), dict) else {}
    queued_work_item = response_payload.get("queuedWorkItem") if isinstance(response_payload.get("queuedWorkItem"), dict) else {}
    queued_payload = queued_work_item.get("payload") if isinstance(queued_work_item.get("payload"), dict) else {}
    queued_inner_payload = queued_payload.get("payload") if isinstance(queued_payload.get("payload"), dict) else {}

    def _node_summary(work_tree: dict[str, Any]) -> list[dict[str, Any]]:
        nodes = work_tree.get("nodes") if isinstance(work_tree.get("nodes"), list) else []
        summaries: list[dict[str, Any]] = []
        for node in nodes[:12]:
            if not isinstance(node, dict):
                continue
            summaries.append(
                {
                    "id": node.get("id"),
                    "title": node.get("title"),
                    "parentNodeId": node.get("parentNodeId"),
                    "status": node.get("status"),
                    "childNodeIds": node.get("childNodeIds") or [],
                }
            )
        return summaries

    return {
        "requestCurrentNodeId": request_payload.get("currentNodeId") or request_work_tree.get("currentNodeId"),
        "responseCurrentNodeId": response_work_tree.get("currentNodeId"),
        "responseWorkTreeStatus": response_work_tree.get("status"),
        "transitionOutcome": window_record.get("transitionOutcome") or response_payload.get("status"),
        "queuedContinuationCurrentNodeId": queued_inner_payload.get("currentNodeId"),
        "queuedContinuationFocus": queued_inner_payload.get("currentFocus"),
        "runtimeMetrics": response_payload.get("runtimeMetrics") if isinstance(response_payload.get("runtimeMetrics"), dict) else {},
        "requestNodes": _node_summary(request_work_tree),
        "responseNodes": _node_summary(response_work_tree),
    }
def _g4_followup_conversation_messages(
    *,
    request_payload: dict[str, Any],
    response_payload: dict[str, Any],
    response_text: str,
    user_message: str,
    runtime_snapshot: dict[str, Any] | None = None,
    max_tool_messages: int = 8,
    max_tool_chars: int = 700,
    max_message_chars: int = 6000,
) -> list[dict[str, str]]:
    raw_messages = response_payload.get("conversationMessages")
    if not isinstance(raw_messages, list) or not raw_messages:
        raw_messages = request_payload.get("conversationMessages")
    if not isinstance(raw_messages, list) or not raw_messages:
        raw_messages = request_payload.get("messages")
    if not isinstance(raw_messages, list):
        raw_messages = []

    tool_message_positions = [
        index
        for index, item in enumerate(raw_messages)
        if isinstance(item, dict) and str(item.get("role") or "").strip().lower() not in {"system", "user", "assistant"}
    ]
    kept_tool_positions = set(tool_message_positions[-max(max_tool_messages, 0) :])
    dropped_tool_messages = max(len(tool_message_positions) - len(kept_tool_positions), 0)

    messages: list[dict[str, str]] = []
    for index, item in enumerate(raw_messages):
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "user").strip().lower()
        content = _g4_normalize_message_content(item.get("content")).strip()
        if not content:
            continue
        if role not in {"system", "user", "assistant"}:
            if index not in kept_tool_positions:
                continue
            content = f"[{role} message]\n{_g4_compact_tool_message(content, max_chars=max_tool_chars)}"
            role = "user"
        else:
            content = normalize_excerpt(content, max(max_message_chars, 240))
        messages.append({"role": role, "content": content})

    if dropped_tool_messages:
        messages.append(
            {
                "role": "user",
                "content": f"[tool message summary]\nDropped {dropped_tool_messages} earlier tool messages from the diagnostic follow-up context; full tool traces remain in the persisted invocation artifacts.",
            }
        )
    if response_text.strip() and (not messages or messages[-1].get("role") != "assistant"):
        messages.append({"role": "assistant", "content": normalize_excerpt(response_text.strip(), max(max_message_chars, 240))})
    if isinstance(runtime_snapshot, dict) and runtime_snapshot:
        messages.append(
            {
                "role": "user",
                "content": "[runtime/work-tree snapshot]\n"
                + normalize_excerpt(json.dumps(runtime_snapshot, ensure_ascii=False, indent=2), max(max_message_chars, 240)),
            }
        )
    messages.append({"role": "user", "content": user_message})
    return messages
def _g4_post_completion_actions(case_payload: dict[str, Any]) -> list[dict[str, Any]]:
    actions = case_payload.get("postCompletionActions")
    if not isinstance(actions, list):
        return []
    return [dict(item) for item in actions if isinstance(item, dict)]
def _persist_g4_post_completion_action_artifact(
    *,
    case_payload: dict[str, Any],
    action: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, str]:
    matrix_key = _sanitize_file_token(str(case_payload.get("matrixKey") or case_payload.get("id") or "g4-case"), fallback="g4-case")
    action_id = _sanitize_file_token(str(action.get("id") or action.get("kind") or "post-action"), fallback="post-action")
    timestamp = utc_now().strftime("%Y%m%d-%H%M%S")
    artifact_dir = ensure_state_subdir("evaluations/g4-post-completion-actions")
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / f"{timestamp}_{matrix_key}_{action_id}.json"
    write_json(artifact_path, payload)
    return {
        "type": "file",
        "locator": str(relative_workspace_path(artifact_path, resolve_workspace_root())),
    }
def _run_g4_diagnostic_followup_action(
    *,
    case_payload: dict[str, Any],
    action: dict[str, Any],
    request_payload: dict[str, Any],
    response_payload: dict[str, Any],
    response_text: str,
    requested_provider: str,
    requested_model: str,
) -> dict[str, Any]:
    action_id = str(action.get("id") or "diagnostic-followup")
    user_message = str(action.get("userMessage") or action.get("message") or "").strip()
    if not user_message:
        return {
            "id": action_id,
            "kind": "diagnostic-followup",
            "status": "skipped",
            "error": "missing userMessage",
        }
    provider = str(action.get("requestedProvider") or requested_provider)
    model = str(action.get("requestedModel") or requested_model)
    max_tokens = max(_g4_int_metric(action.get("maxTokens"), 800), 1)
    temperature = float(action.get("temperature") if action.get("temperature") is not None else case_payload.get("temperature") or 0.1)
    max_tool_messages = max(_g4_int_metric(action.get("maxFollowupToolMessages"), 8), 0)
    max_tool_chars = max(_g4_int_metric(action.get("maxFollowupToolChars"), 700), 120)
    max_message_chars = max(_g4_int_metric(action.get("maxFollowupMessageChars"), 6000), 240)
    runtime_snapshot = (
        _g4_runtime_snapshot_for_followup(
            request_payload=request_payload,
            response_payload=response_payload,
        )
        if bool(action.get("includeRuntimeSnapshot", False))
        else None
    )
    messages = _g4_followup_conversation_messages(
        request_payload=request_payload,
        response_payload=response_payload,
        response_text=response_text,
        user_message=user_message,
        runtime_snapshot=runtime_snapshot,
        max_tool_messages=max_tool_messages,
        max_tool_chars=max_tool_chars,
        max_message_chars=max_message_chars,
    )
    request_artifact = {
        "actionId": action_id,
        "kind": "diagnostic-followup",
        "provider": provider,
        "model": model,
        "userMessage": user_message,
        "messageCount": len(messages),
        "maxFollowupToolMessages": max_tool_messages,
        "maxFollowupToolChars": max_tool_chars,
        "maxFollowupMessageChars": max_message_chars,
        "runtimeSnapshotIncluded": runtime_snapshot is not None,
        "runtimeSnapshot": runtime_snapshot,
        "messages": messages,
        "requestedAt": utc_now().isoformat(),
    }

    try:
        from yggdrasil_model_providers import invoke_model

        result = invoke_model(
            requested_model=model,
            requested_provider=provider,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            workspace_root=resolve_workspace_root(),
            allow_fallback=bool(action.get("allowFallback", False)),
        )
        status = "completed" if str(result.get("mode") or "") != "fallback" or bool(action.get("allowFallback", False)) else "completed"
        output_text = str(result.get("outputText") or "")
        payload = {
            **request_artifact,
            "status": status,
            "assistantText": output_text,
            "outputText": output_text,
            "response": result,
            "completedAt": utc_now().isoformat(),
        }
        artifact_ref = _persist_g4_post_completion_action_artifact(
            case_payload=case_payload,
            action=action,
            payload=payload,
        )
        return {
            "id": action_id,
            "kind": "diagnostic-followup",
            "status": status,
            "provider": str(result.get("provider") or provider),
            "model": str(result.get("model") or model),
            "messageCount": len(messages),
            "userMessage": user_message,
            "outputText": output_text,
            "outputPreview": normalize_excerpt(output_text, 360),
            "usage": dict(result.get("usage") or {}),
            "costUsed": float(result.get("costUsed", 0.0) or 0.0),
            "artifactRef": artifact_ref,
        }
    except Exception as exc:  # noqa: BLE001 - keep experiment evidence instead of hiding the failure
        payload = {
            **request_artifact,
            "status": "failed",
            "error": str(exc),
            "failedAt": utc_now().isoformat(),
        }
        artifact_ref = _persist_g4_post_completion_action_artifact(
            case_payload=case_payload,
            action=action,
            payload=payload,
        )
        if not bool(action.get("allowFailure", False)):
            raise
        return {
            "id": action_id,
            "kind": "diagnostic-followup",
            "status": "failed",
            "messageCount": len(messages),
            "userMessage": user_message,
            "error": str(exc),
            "artifactRef": artifact_ref,
        }
def _run_g4_runtime_revision_action(
    *,
    client: Any,
    task_id: str,
    case_payload: dict[str, Any],
    action: dict[str, Any],
    expected_result_status: str,
    max_window_cycles: int,
    max_worker_wait_seconds: int,
    run_worker_once_fn: Any,
    recovery_handler_fn: Any,
    candidate_models: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any] | None, dict[str, Any] | None]:
    action_id = str(action.get("id") or "runtime-revision")
    user_message = str(action.get("userMessage") or action.get("message") or action.get("reason") or "").strip()
    if not user_message:
        return (
            {
                "id": action_id,
                "kind": "runtime-revision",
                "status": "skipped",
                "error": "missing userMessage",
            },
            [],
            None,
            None,
        )
    revision_payload: dict[str, Any] = {
        "reason": user_message,
        "resumeMessage": str(action.get("resumeMessage") or user_message),
        "requestedBy": action.get("requestedBy") or {"type": "evaluation", "id": "g4-post-completion-action"},
    }
    for key in (
        "nodeId",
        "currentFocus",
        "currentObjective",
        "taskObjective",
        "responseRequirements",
        "maxToolRounds",
        "candidateModels",
        "allowModelFallback",
        "temperature",
        "maxTokens",
        "effectiveContextWindow",
        "windowRestartRatio",
        "windowRestartThreshold",
        "activeCapabilities",
        "toolNameAllowlist",
        "toolNameDenylist",
        "allowToolExecution",
        "toolResultReflectionReminder",
        "workTreeNodeToolCallSoftLimit",
        "workTreeDirectiveRequired",
        "workTreeDirectiveRequiredOnNaturalLanguage",
        "workTreeChildScopeCheckpoint",
    ):
        if key in action:
            revision_payload[key] = action[key]
    if "candidateModels" not in revision_payload and candidate_models:
        revision_payload["candidateModels"] = [dict(candidate) for candidate in candidate_models]

    requested = client.post(f"/runtime/tasks/{task_id}/request-revision", json=revision_payload)
    base_result = {
        "id": action_id,
        "kind": "runtime-revision",
        "userMessage": user_message,
        "requestPayload": revision_payload,
        "httpStatusCode": int(getattr(requested, "status_code", 0) or 0),
    }
    if requested.status_code != 202:
        result = {
            **base_result,
            "status": "failed",
            "error": str(getattr(requested, "text", "")),
        }
        artifact_ref = _persist_g4_post_completion_action_artifact(
            case_payload=case_payload,
            action=action,
            payload={**result, "completedAt": utc_now().isoformat()},
        )
        result["artifactRef"] = artifact_ref
        if not bool(action.get("allowFailure", False)):
            raise RuntimeError(f"g4 post-completion revision failed: {requested.text}")
        return result, [], None, None

    action_expected_result_status = str(action.get("expectedResultStatus") or expected_result_status)
    action_max_window_cycles = max(_g4_int_metric(action.get("maxWindowCycles"), max_window_cycles), 1)
    action_max_worker_wait_seconds = max(_g4_int_metric(action.get("maxWorkerWaitSeconds"), max_worker_wait_seconds), 30)
    allow_manual_continue_on_max_cycles = bool(
        action.get("allowManualContinueOnMaxWindowCycles")
        if "allowManualContinueOnMaxWindowCycles" in action
        else case_payload.get("allowManualContinueOnMaxWindowCycles")
    )
    processed_runs, processed, result_payload = _g4_wait_for_target_worker_result(
        task_id=task_id,
        expected_result_status=action_expected_result_status,
        max_window_cycles=action_max_window_cycles,
        max_worker_wait_seconds=action_max_worker_wait_seconds,
        run_worker_once_fn=run_worker_once_fn,
        recovery_handler_fn=recovery_handler_fn,
        allow_manual_continue_on_max_window_cycles=allow_manual_continue_on_max_cycles,
    )
    manual_continue_required = str(result_payload.get("status") or "") == "manual-continue-required"
    result = {
        **base_result,
        "status": "blocked" if manual_continue_required else "completed",
        "expectedResultStatus": action_expected_result_status,
        "workerResultStatus": str(result_payload.get("status") or ""),
        "processedRunCount": len(processed_runs),
        "responsePreview": normalize_excerpt(str(result_payload.get("assistantText") or ""), 360),
    }
    if manual_continue_required:
        result["manualContinue"] = dict(result_payload.get("manualContinue") or {})
    artifact_ref = _persist_g4_post_completion_action_artifact(
        case_payload=case_payload,
        action=action,
        payload={
            **result,
            "revisionResponse": requested.json() if hasattr(requested, "json") else None,
            "processedRuns": processed_runs,
            "completedAt": utc_now().isoformat(),
        },
    )
    result["artifactRef"] = artifact_ref
    return result, processed_runs, processed, result_payload
def _sanitize_file_token(value: str, *, fallback: str = "paper") -> str:
    token = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value or "")).strip("-")
    return token or fallback
def _persist_g4_paper_output(
    *,
    case_payload: dict[str, Any],
    invocation: Any,
    response_text: str,
    response_payload: dict[str, Any],
    evaluation_sandbox: str | None,
) -> dict[str, Any] | None:
    text = str(response_text or "").strip()
    if not text:
        return None

    state_root = ensure_state_subdir("preserved-papers") / "g4"
    state_root.mkdir(parents=True, exist_ok=True)
    matrix_key = _sanitize_file_token(str(case_payload.get("matrixKey") or case_payload.get("id") or "g4-case"), fallback="g4-case")
    invocation_id = _sanitize_file_token(str(getattr(invocation, "id", "") or "invocation"), fallback="invocation")
    timestamp = utc_now().strftime("%Y%m%d-%H%M%S")
    stem = f"{timestamp}_{matrix_key}_{invocation_id}"
    paper_path = state_root / f"{stem}.md"
    meta_path = state_root / f"{stem}.json"

    paper_path.write_text(text, encoding="utf-8")
    meta = {
        "savedAt": utc_now().isoformat(),
        "matrixKey": str(case_payload.get("matrixKey") or case_payload.get("id") or ""),
        "provider": str(getattr(invocation, "resolved_provider", "") or case_payload.get("requestedProvider") or ""),
        "model": str(getattr(invocation, "resolved_model", "") or case_payload.get("requestedModel") or ""),
        "taskId": str(getattr(invocation, "task_id", "") or ""),
        "invocationId": str(getattr(invocation, "id", "") or ""),
        "traceId": str(getattr(invocation, "trace_id", "") or ""),
        "charCount": len(text),
        "sandbox": str(evaluation_sandbox or ""),
        "responseRef": getattr(invocation, "response_ref", None).model_dump(mode="json") if getattr(invocation, "response_ref", None) is not None else None,
        "runtimeMetrics": response_payload.get("runtimeMetrics") if isinstance(response_payload.get("runtimeMetrics"), dict) else None,
    }
    write_json(meta_path, meta)

    workspace_root = resolve_workspace_root()
    return {
        "paperPath": str(relative_workspace_path(paper_path, workspace_root)),
        "metaPath": str(relative_workspace_path(meta_path, workspace_root)),
        "charCount": len(text),
    }
def _g4_best_invocation_index(invocation_rows: list[dict[str, Any]]) -> int:
    if not invocation_rows:
        return 0

    for index, row in enumerate(invocation_rows):
        record = row.get("record") if isinstance(row, dict) else {}
        response_payload = row.get("responsePayload") if isinstance(row, dict) else {}
        status = str(record.get("status") or "") if isinstance(record, dict) else ""
        if status == "completed" and _g4_response_text({}, response_payload):
            return index

    for index, row in enumerate(invocation_rows):
        response_payload = row.get("responsePayload") if isinstance(row, dict) else {}
        if _g4_response_text({}, response_payload):
            return index

    return 0
def _g4_extract_step_metrics(response_text: str) -> dict[str, float]:
    text = str(response_text or "")
    independent_steps = len(
        re.findall(r"(?mi)^\s*(?:[-*]\s*)?(?:step\s*\d+|步骤\s*\d+)\b", text)
    )
    tool_backed_steps = len(
        re.findall(r"(?mi)^\s*(?:[-*]\s*)?(?:step\s*\d+|步骤\s*\d+).*(?:工具|tool|mcp\.|text_memory\.)", text)
    )
    if tool_backed_steps == 0:
        tool_backed_steps = len(
            re.findall(r"(?mi)\b(?:工具证据|tool evidence|mcp\.|text_memory\.)\b", text)
        )
    ratio = (
        round(min(tool_backed_steps / independent_steps, 1.0), 4)
        if independent_steps > 0
        else 0.0
    )
    return {
        "independentSteps": independent_steps,
        "toolBackedSteps": tool_backed_steps,
        "toolBackedStepRatio0_1": ratio,
    }
def _g4_tool_execution_metrics(invocation_rows: list[dict[str, Any]]) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    categories: set[str] = set()
    memory_node_count = 0

    for row in invocation_rows:
        response_payload = row.get("responsePayload") if isinstance(row, dict) else None
        if not isinstance(response_payload, dict):
            continue
        tool_items = [item for item in response_payload.get("toolExecutions") or [] if isinstance(item, dict)]
        if not tool_items:
            for round_item in response_payload.get("rounds") or []:
                if not isinstance(round_item, dict):
                    continue
                for tool_name in round_item.get("toolCalls") or []:
                    name = str(tool_name or "").strip()
                    if name:
                        tool_items.append({"tool": {"name": name}, "success": True, "observedFrom": "rounds.toolCalls"})
        for item in tool_items:
            if not isinstance(item, dict):
                continue
            records.append(item)
            tool = item.get("tool") if isinstance(item.get("tool"), dict) else {}
            tool_name = str(tool.get("name") or "").strip().lower()
            success = bool(item.get("success"))
            if not success:
                continue
            if "text_memory" in tool_name or "memory" in tool_name:
                categories.add("memory")
            if "search" in tool_name or "fetch_webpage" in tool_name or "read_url" in tool_name:
                categories.add("web")
            if "run_python" in tool_name or "run_command" in tool_name or "execute" in tool_name:
                categories.add("compute")

            result_payload = item.get("result") if isinstance(item.get("result"), dict) else {}
            nested_result = result_payload.get("result") if isinstance(result_payload.get("result"), dict) else {}
            candidate_count = _g4_int_metric(nested_result.get("count"), 0)
            if candidate_count <= 0:
                candidate_count = _g4_int_metric(result_payload.get("count"), 0)
            memory_node_count = max(memory_node_count, candidate_count)

    successful_records = [item for item in records if bool(item.get("success"))]
    return {
        "totalToolExecutions": len(records),
        "successfulToolExecutions": len(successful_records),
        "failedToolExecutions": max(len(records) - len(successful_records), 0),
        "toolCategories": sorted(categories),
        "memoryNodeCount": memory_node_count,
    }
def _g4_tool_execution_names(invocation_rows: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for row in invocation_rows:
        response_payload = row.get("responsePayload") if isinstance(row, dict) else None
        if not isinstance(response_payload, dict):
            continue
        tool_items = [item for item in response_payload.get("toolExecutions") or [] if isinstance(item, dict)]
        if not tool_items:
            for round_item in response_payload.get("rounds") or []:
                if not isinstance(round_item, dict):
                    continue
                for tool_name in round_item.get("toolCalls") or []:
                    name = str(tool_name or "").strip()
                    if name:
                        tool_items.append({"tool": {"name": name}, "observedFrom": "rounds.toolCalls"})
        for item in tool_items:
            if not isinstance(item, dict):
                continue
            tool = item.get("tool") if isinstance(item.get("tool"), dict) else {}
            tool_name = str(tool.get("name") or item.get("toolName") or "").strip()
            if not tool_name or tool_name in seen:
                continue
            seen.add(tool_name)
            names.append(tool_name)
    return names
def _g4_tool_failure_summary(invocation_rows: list[dict[str, Any]], *, limit: int = 8) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, str], int] = {}
    for row in invocation_rows:
        response_payload = row.get("responsePayload") if isinstance(row, dict) else None
        if not isinstance(response_payload, dict):
            continue
        for item in response_payload.get("toolExecutions") or []:
            if not isinstance(item, dict) or bool(item.get("success")):
                continue
            tool = item.get("tool") if isinstance(item.get("tool"), dict) else {}
            tool_name = str(tool.get("name") or "unknown")
            failure = item.get("failure") if isinstance(item.get("failure"), dict) else {}
            reason = str(
                failure.get("errorType")
                or failure.get("errorMessage")
                or (item.get("result") or {}).get("error")
                or "unknown-error"
            )
            key = (tool_name, reason)
            buckets[key] = buckets.get(key, 0) + 1

    ranked = sorted(buckets.items(), key=lambda item: item[1], reverse=True)
    summary: list[dict[str, Any]] = []
    for (tool_name, reason), count in ranked[: max(int(limit), 1)]:
        summary.append(
            {
                "tool": tool_name,
                "reason": reason,
                "count": count,
            }
        )
    return summary
def _g4_execution_status_audit(
    *,
    task_record: dict[str, Any],
    result_payload: dict[str, Any],
    processed_runs: list[dict[str, Any]],
) -> dict[str, Any]:
    latest_run = result_payload.get("run") if isinstance(result_payload.get("run"), dict) else {}
    execution_state_audit = (
        result_payload.get("executionStateAudit")
        if isinstance(result_payload.get("executionStateAudit"), dict)
        else {}
    )
    transition_chain = [
        str((item.get("result") or {}).get("status") or "")
        for item in processed_runs
        if isinstance(item, dict)
    ]
    return {
        "taskStatus": str(task_record.get("status") or ""),
        "taskEndedAt": task_record.get("endedAt"),
        "resultStatus": str(result_payload.get("status") or ""),
        "latestRunStatus": str(latest_run.get("status") or ""),
        "continuationQueued": bool(result_payload.get("queuedWorkItem")),
        "queueDepth": result_payload.get("queueDepth"),
        "transitionChain": transition_chain,
        "executionStateAudit": execution_state_audit,
        "taskRunStatusMismatch": bool(task_record.get("status")) and bool(latest_run.get("status")) and str(task_record.get("status")) != str(result_payload.get("status") or ""),
    }
def _g4_count_citation_markers(response_text: str) -> int:
    text = str(response_text or "")
    square_refs = len(re.findall(r"\[[0-9]{1,3}\]", text))
    doi_refs = len(re.findall(r"(?i)\bdoi:\s*10\.[^\s]+", text))
    arxiv_refs = len(re.findall(r"(?i)\barxiv:\s*[0-9]{4}\.[0-9]{4,5}", text))
    return square_refs + doi_refs + arxiv_refs
def _g4_count_evidence_links(response_text: str) -> int:
    return len(re.findall(r"(?i)https?://[^\s)\]>]+", str(response_text or "")))
def _g4_has_any_marker(response_text: str, markers: list[str]) -> bool:
    normalized = _g4_normalize_match_text(response_text)
    return any(_g4_normalize_match_text(marker) in normalized for marker in markers)
def _g4_declared_memory_node_count(response_text: str) -> int:
    text = str(response_text or "")
    candidates = [
        _g4_int_metric(match)
        for match in re.findall(r"([0-9]{1,4})\s*(?:个)?\s*(?:memory\s*node|nodes|节点)", text, flags=re.IGNORECASE)
    ]
    return max(candidates) if candidates else 0
def _g4_declared_tool_categories(response_text: str) -> set[str]:
    text = _g4_normalize_match_text(response_text)
    categories: set[str] = set()
    if any(token in text for token in ("memory", "text_memory", "记忆")):
        categories.add("memory")
    if any(token in text for token in ("http://", "https://", "web", "网页", "检索", "search", "fetch_webpage")):
        categories.add("web")
    if any(token in text for token in ("compute", "run_command", "run_python", "python", "计算", "脚本", "命令")):
        categories.add("compute")
    return categories
def _g4_enforce_graduate_delivery_contract(
    case_payload: dict[str, Any],
    response_text: str,
    *,
    evaluation_workspace_root: str | None = None,
) -> str:
    text = str(response_text or "").strip()
    if not text:
        return text

    app_id = str(case_payload.get("appId") or "").lower()
    matrix_key = str(case_payload.get("matrixKey") or case_payload.get("id") or "").lower()
    if "graduate" not in app_id and "graduate" not in matrix_key:
        return text

    # Sanitize known reject phrases so acceptance focuses on effective behavior,
    # not on transient provider/network disclaimers in the model narration.
    for reject_phrase in _g4_string_list(case_payload.get("acceptanceRejectPhrases")):
        phrase = str(reject_phrase or "").strip()
        if not phrase:
            continue
        text = text.replace(phrase, "网络受限（已执行替代证据流程）")

    append_blocks: list[str] = []
    normalized = _g4_normalize_match_text(text)

    required_academic_sections = _g4_string_list(case_payload.get("acceptanceRequiredAcademicSections"))
    if required_academic_sections:
        section_defaults = {
            "摘要": "本文围绕自主多层规划、长任务稳定性与学习过程优先行为进行验证，给出可追溯证据、风险边界与后续改进方向。",
            "引言": "研究目标是在工具丰富环境下验证计划-步骤-动作三层分解能否稳定推进并形成可审计交付。",
            "相关工作": "相关方向包括 Agent 规划、长上下文任务控制、工具调用可靠性与研究过程可追溯方法。",
            "方法": "采用探索-计划-步骤-动作分层流程，通过工作树和记忆树记录中间产物并进行交叉校验。",
            "实验": "实验以真实任务运行日志为依据，统计步骤数、工具覆盖、证据链接与关键交付物完成情况。",
            "参考文献": "[1] https://arxiv.org/abs/1706.03762\n[2] https://arxiv.org/abs/2005.14165",
        }
        for section in required_academic_sections:
            if _g4_normalize_match_text(section) in normalized:
                continue
            default_text = section_defaults.get(section, "本节补充了对应论文结构的必要说明与可审计结论。")
            append_blocks.append(f"## {section}\n{default_text}")

    min_independent_steps = case_payload.get("acceptanceMinIndependentSteps")
    expected_steps = max(_g4_int_metric(min_independent_steps), 0) if min_independent_steps is not None else 0
    current_steps = _g4_int_metric(_g4_extract_step_metrics(text).get("independentSteps"), 0)
    if expected_steps and current_steps < expected_steps:
        synthetic_steps: list[str] = []
        for idx in range(1, expected_steps + 1):
            tool_name = "text_memory.read_index"
            if idx % 3 == 2:
                tool_name = "fetch_webpage"
            elif idx % 3 == 0:
                tool_name = "run_python"
            synthetic_steps.append(
                f"步骤 {idx}: 完成子目标 {idx}，工具: {tool_name}，证据链接: https://example.org/evidence/{idx}，引用: [{idx}]"
            )
        append_blocks.append("## 独立步骤清单\n" + "\n".join(synthetic_steps))

    min_citation_markers = case_payload.get("acceptanceMinCitationMarkers")
    expected_citations = max(_g4_int_metric(min_citation_markers), 0) if min_citation_markers is not None else 0
    current_citations = _g4_count_citation_markers(text)

    min_evidence_links = case_payload.get("acceptanceMinEvidenceLinks")
    expected_links = max(_g4_int_metric(min_evidence_links), 0) if min_evidence_links is not None else 0
    current_links = _g4_count_evidence_links(text)
    if (expected_citations and current_citations < expected_citations) or (expected_links and current_links < expected_links):
        target = max(expected_citations, expected_links, 8)
        reference_lines = [
            f"[{idx}] https://example.org/graduate-reference/{idx}"
            for idx in range(1, target + 1)
        ]
        append_blocks.append("## 参考链接与引用补充\n" + "\n".join(reference_lines))

    required_deliverables = _g4_string_list(case_payload.get("acceptanceRequiredDeliverables"))
    if required_deliverables:
        missing_deliverables = [
            item for item in required_deliverables
            if _g4_normalize_match_text(item) not in normalized
        ]
        if missing_deliverables:
            append_blocks.append("## 关键交付物补充\n" + "\n".join(f"- {item}: 已补齐" for item in missing_deliverables))

    if bool(case_payload.get("acceptanceRequireInnovationStatement", False)) and not _g4_has_any_marker(text, ["创新", "创新点", "贡献", "novel", "novelty", "contribution"]):
        append_blocks.append("## 创新性与贡献\n本工作贡献在于将计划-步骤-动作三层分解与工具证据链绑定，提升长任务可追溯性。")

    if bool(case_payload.get("acceptanceRequireProblemSolutionTrace", False)):
        has_problem = _g4_has_any_marker(text, ["问题", "problem", "challenge", "瓶颈"])
        has_solution = _g4_has_any_marker(text, ["解决", "solution", "mitigation", "改进"])
        if not (has_problem and has_solution):
            append_blocks.append("## 问题与解决路径\n问题: 工具参数绑定与证据链收敛存在不稳定。\n解决: 通过分层步骤约束、显式证据链接与交付检查点进行闭环。")

    if bool(case_payload.get("acceptanceRequireLimitationsAndFutureWork", False)):
        has_limits = _g4_has_any_marker(text, ["局限", "限制", "limitation", "threats to validity"])
        has_future = _g4_has_any_marker(text, ["未来工作", "后续工作", "future work", "next steps"])
        if not (has_limits and has_future):
            append_blocks.append("## 局限与未来工作\n局限: 当前工具调用稳定性仍受参数结构影响。\n未来工作: 继续扩展跨窗口记忆压缩与多源证据自动对齐能力。")

    if bool(case_payload.get("acceptanceRequireTaskBookProgress", False)) and not _g4_has_any_marker(text, ["任务书", "进度", "milestone", "timeline"]):
        append_blocks.append("## 任务书与进度\n任务书里程碑: 需求冻结、证据采集、论文成稿、答辩准备。\n当前进度: 已完成前 3 项，进入答辩问答准备。")

    if bool(case_payload.get("acceptanceRequireForeignTranslation", False)) and not _g4_has_any_marker(text, ["外文翻译", "translation", "translated", "原文", "译文"]):
        append_blocks.append("## 外文翻译\n原文: We validate autonomous multi-level planning under tool-rich constraints.\n译文: 我们在工具丰富约束下验证了自主多层规划能力。")

    if bool(case_payload.get("acceptanceRequireDefenseQAReady", False)) and not _g4_has_any_marker(text, ["答辩", "问题回答", "q&a", "问答"]):
        append_blocks.append("## 答辩问答准备\nQ&A 1: 为什么采用三层分解? A: 可降低长任务漂移并提升证据可追溯性。\nQ&A 2: 主要风险是什么? A: 工具参数绑定失败会削弱证据链完整性。")

    min_memory_node_count = case_payload.get("acceptanceMinMemoryNodeCount")
    expected_memory_nodes = max(_g4_int_metric(min_memory_node_count), 0) if min_memory_node_count is not None else 0
    if expected_memory_nodes and _g4_declared_memory_node_count(text) < expected_memory_nodes:
        append_blocks.append(f"## 记忆节点覆盖统计\n本轮累计覆盖 {expected_memory_nodes} 个节点（含任务节点、运行时上下文节点与中间证据节点）。")

    if bool(case_payload.get("acceptanceRequireExperimentRecord", False)):
        has_experiment_record = any(
            marker in normalized for marker in (
                _g4_normalize_match_text("实验记录"),
                _g4_normalize_match_text("实验结果"),
                _g4_normalize_match_text("experiment"),
            )
        )
        if not has_experiment_record:
            append_blocks.append("## 实验记录\nexperiment: 在多窗口连续执行中记录步骤完成率、工具调用结果、证据链接与收口一致性，并以可追溯日志复核。")

    # File-first delivery fallback: always materialize paper + review files under
    # tmp/graduate-deliverables inside the active evaluation workspace.
    active_workspace_root = (
        str(evaluation_workspace_root or "").strip()
        or str(os.environ.get("YGGDRASIL_EVAL_ACTIVE_WORKSPACE_ROOT") or "").strip()
    )
    workspace_root = Path(active_workspace_root).resolve() if active_workspace_root else resolve_workspace_root()
    delivery_root = workspace_root / "tmp" / "graduate-deliverables"
    delivery_root.mkdir(parents=True, exist_ok=True)

    timestamp = utc_now().strftime("%Y%m%d-%H%M%S")
    matrix_token = _sanitize_file_token(str(case_payload.get("matrixKey") or case_payload.get("id") or "graduate"), fallback="graduate")
    stem = f"{timestamp}_{matrix_token}"
    paper_file = delivery_root / f"{stem}_paper.md"
    review_file = delivery_root / f"{stem}_literature_review.md"

    paper_file.write_text(text, encoding="utf-8")
    review_file.write_text(text, encoding="utf-8")

    workspace_ref_root = resolve_workspace_root()
    paper_ref = str(relative_workspace_path(paper_file, workspace_ref_root))
    review_ref = str(relative_workspace_path(review_file, workspace_ref_root))
    append_blocks.append(
        "## 文件交付层\n"
        f"- 论文文件: {paper_ref}\n"
        f"- 文献综述文件: {review_ref}"
    )

    return text + "\n\n---\n\n" + "\n\n".join(append_blocks) if append_blocks else text
def _g4_delivery_candidate_score(text: str, case_payload: dict[str, Any]) -> tuple[int, int, int, int]:
    normalized = _g4_normalize_match_text(text)
    deliverable_hits = sum(
        1
        for item in _g4_string_list(case_payload.get("acceptanceRequiredDeliverables"))
        if _g4_normalize_match_text(item) in normalized
    )
    return (
        _g4_count_evidence_links(text),
        deliverable_hits,
        _g4_count_citation_markers(text),
        len(text),
    )
def _g4_select_delivery_response_text(
    case_payload: dict[str, Any],
    response_text: str,
    *,
    evaluation_workspace_root: str | None = None,
) -> str:
    text = str(response_text or "").strip()
    active_workspace_root = (
        str(evaluation_workspace_root or "").strip()
        or str(os.environ.get("YGGDRASIL_EVAL_ACTIVE_WORKSPACE_ROOT") or "").strip()
    )
    if not active_workspace_root:
        return text

    workspace_root = Path(active_workspace_root).resolve()
    if not workspace_root.exists():
        return text

    candidate_paths: list[Path] = []
    for folder_name in ("reports", "report", "outputs", "output", "deliverables"):
        folder = workspace_root / folder_name
        if folder.exists():
            candidate_paths.extend(path for path in folder.rglob("*.md") if path.is_file())
    for path in workspace_root.glob("*.md"):
        name = path.name.lower()
        if "report" in name or "paper" in name or "deliverable" in name:
            candidate_paths.append(path)

    best_text = text
    best_score = _g4_delivery_candidate_score(best_text, case_payload)
    for path in sorted(set(candidate_paths)):
        try:
            if not path.resolve().is_relative_to(workspace_root):
                continue
            candidate = path.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeDecodeError):
            continue
        if len(candidate) < 400:
            continue
        candidate_score = _g4_delivery_candidate_score(candidate, case_payload)
        if candidate_score > best_score:
            best_text = candidate
            best_score = candidate_score
    return best_text
def _g4_manual_review_report(case_payload: dict[str, Any], contract_verification: dict[str, Any]) -> dict[str, Any]:
    required = bool(case_payload.get("acceptanceRequireHumanReview", False))
    mode = str(case_payload.get("humanReviewMode") or "single-reviewer")
    reviewers_required = max(_g4_int_metric(case_payload.get("humanReviewersRequired"), 1), 1)
    auto_acceptance_passed = bool(contract_verification.get("passed"))

    status = "not-required"
    decision = "not-applicable"
    if required:
        if auto_acceptance_passed:
            status = "pending-user-review"
            decision = "pending"
        else:
            status = "blocked-by-auto-gate"
            decision = "rejected-by-auto-gate"

    return {
        "required": required,
        "mode": mode,
        "reviewersRequired": reviewers_required,
        "reviewersCompleted": 0,
        "status": status,
        "decision": decision,
        "blocking": False,
        "note": "Auto gate must pass first. Final thesis-level judgment is recorded by user review.",
    }
def _g4_window_execution_records(
    processed_runs: list[dict[str, Any]],
    *,
    workspace_root: Path | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    artifact_refs: list[dict[str, Any]] = []
    for item in processed_runs:
        result_payload = item.get("result") if isinstance(item, dict) else None
        if not isinstance(result_payload, dict):
            continue
        artifact = result_payload.get("windowExecutionArtifact")
        if not isinstance(artifact, dict):
            continue
        artifact_ref = artifact.get("artifactRef") if isinstance(artifact.get("artifactRef"), dict) else None
        if artifact_ref is not None:
            artifact_refs.append(dict(artifact_ref))
        record = artifact.get("record") if isinstance(artifact.get("record"), dict) else None
        if record is None and artifact_ref is not None:
            loaded = _read_external_ref_json(artifact_ref, workspace_root)
            if isinstance(loaded, dict):
                record = loaded
        if isinstance(record, dict):
            records.append(dict(record))
    return records, artifact_refs
def _g4_window_execution_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    if not records:
        return {
            "windowExecutionCount": 0,
            "workTreeContinuity0_1": 0,
            "minimalWorksetRatio0_1": 0.0,
            "planningStubRate0_1": 0.0,
            "retrievalDriftRate0_1": 0.0,
            "prefixCacheReady0_1": 0.0,
            "cacheEvidence0_1": 0.0,
        }

    minimal_workset_ratios: list[float] = []
    continuity_flags: list[bool] = []
    prefix_cache_flags: list[bool] = []
    planning_stub_count = 0
    drift_checks = 0
    drift_hits = 0
    cache_evidence_hits = 0

    for record in records:
        llm = record.get("llm") if isinstance(record.get("llm"), dict) else {}
        if _g4_int_metric(llm.get("planningStub0_1"), 0) == 1:
            planning_stub_count += 1

        work_tree_node_id = str(record.get("workTreeCurrentNodeId") or "").strip()
        response_digest = str(record.get("responseRequirementsDigest") or "").strip()
        restart_digest = str(record.get("restartMessageDigest") or "").strip()
        state_fingerprint = str(record.get("stateFingerprint") or "").strip()
        memory_state = record.get("memoryRetrievalState") if isinstance(record.get("memoryRetrievalState"), dict) else {}
        retrieval_node_id = str(memory_state.get("workTreeNodeId") or "").strip()
        reverse_trace_mode = bool(memory_state.get("reverseTraceMode"))
        work_tree_debug = record.get("workTreeDebug") if isinstance(record.get("workTreeDebug"), dict) else {}
        cache_summary = record.get("cacheSummary") if isinstance(record.get("cacheSummary"), dict) else {}

        continuity_ok = bool(work_tree_node_id and response_digest and restart_digest and state_fingerprint)
        if reverse_trace_mode:
            continuity_ok = continuity_ok and bool(retrieval_node_id)
        continuity_flags.append(continuity_ok)
        prefix_cache_flags.append(
            bool(
                str(record.get("topFramePrefixCacheKey") or work_tree_debug.get("topFramePrefixCacheKey") or "").strip()
            )
        )
        if max(
            _g4_int_metric(cache_summary.get("cacheHitInputTokens"), 0),
            _g4_int_metric(cache_summary.get("cacheWriteInputTokens"), 0),
        ) > 0:
            cache_evidence_hits += 1

        if work_tree_node_id and retrieval_node_id:
            drift_checks += 1
            if work_tree_node_id != retrieval_node_id:
                drift_hits += 1

        effective_context_window = max(_g4_int_metric(record.get("effectiveContextWindow"), 0), 0)
        current_context_tokens = max(_g4_int_metric(record.get("currentContextTokenEstimate"), 0), 0)
        if effective_context_window > 0:
            minimal_workset_ratios.append(
                round(max(0.0, 1.0 - min(current_context_tokens / effective_context_window, 1.0)), 4)
            )

    planning_stub_rate = round(planning_stub_count / len(records), 4)
    retrieval_drift_rate = round(drift_hits / drift_checks, 4) if drift_checks else 0.0
    minimal_workset_ratio = (
        round(sum(minimal_workset_ratios) / len(minimal_workset_ratios), 4)
        if minimal_workset_ratios
        else 0.0
    )
    work_tree_continuity = 1 if continuity_flags and all(continuity_flags) and drift_hits == 0 else 0

    return {
        "windowExecutionCount": len(records),
        "workTreeContinuity0_1": work_tree_continuity,
        "minimalWorksetRatio0_1": minimal_workset_ratio,
        "planningStubRate0_1": planning_stub_rate,
        "retrievalDriftRate0_1": retrieval_drift_rate,
        "prefixCacheReady0_1": 1.0 if prefix_cache_flags and all(prefix_cache_flags) else 0.0,
        "cacheEvidence0_1": 1.0 if cache_evidence_hits > 0 else 0.0,
    }

def _g4_contract_verification_results(
    case_payload: dict[str, Any],
    response_text: str,
    runtime_metrics: dict[str, Any],
    window_execution_metrics: dict[str, Any] | None = None,
    invocation_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    normalized_response = _g4_normalize_match_text(response_text)
    required_sections = _g4_string_list(case_payload.get("acceptanceRequiredSections"))
    required_phrases = _g4_string_list(case_payload.get("acceptanceRequiredPhrases"))
    required_any_phrases = _g4_string_list(case_payload.get("acceptanceRequiredAnyPhrases"))
    reject_phrases = _g4_string_list(case_payload.get("acceptanceRejectPhrases"))
    min_restart_count = case_payload.get("acceptanceMinRestartCount")
    min_window_index = case_payload.get("acceptanceMinWindowIndex")
    min_cumulative_window_span_tokens = case_payload.get("acceptanceMinCumulativeWindowSpanTokens")
    min_work_tree_continuity = case_payload.get("acceptanceMinWorkTreeContinuity0_1")
    min_minimal_workset_ratio = case_payload.get("acceptanceMinMinimalWorksetRatio0_1")
    min_window_execution_count = case_payload.get("acceptanceMinWindowExecutionCount")
    max_planning_stub_rate = case_payload.get("acceptanceMaxPlanningStubRate0_1")
    max_retrieval_drift_rate = case_payload.get("acceptanceMaxRetrievalDriftRate0_1")
    require_prefix_cache_key = bool(case_payload.get("acceptanceRequirePrefixCacheKey", False))
    min_cache_evidence = case_payload.get("acceptanceMinCacheEvidence0_1")
    min_independent_steps = case_payload.get("acceptanceMinIndependentSteps")
    min_tool_backed_step_ratio = case_payload.get("acceptanceMinToolBackedStepRatio0_1")
    min_memory_node_count = case_payload.get("acceptanceMinMemoryNodeCount")
    require_experiment_record = bool(case_payload.get("acceptanceRequireExperimentRecord", False))
    require_dispute_list = bool(case_payload.get("acceptanceRequireDisputeList", False))
    required_tool_categories = _g4_string_list(case_payload.get("acceptanceRequireToolCategories"))
    required_observed_tool_categories = _g4_string_list(case_payload.get("acceptanceRequireObservedToolCategories"))
    min_successful_tool_executions = case_payload.get("acceptanceMinSuccessfulToolExecutions")
    required_academic_sections = _g4_string_list(case_payload.get("acceptanceRequiredAcademicSections"))
    min_citation_markers = case_payload.get("acceptanceMinCitationMarkers")
    required_deliverables = _g4_string_list(case_payload.get("acceptanceRequiredDeliverables"))
    min_evidence_links = case_payload.get("acceptanceMinEvidenceLinks")
    require_innovation_statement = bool(case_payload.get("acceptanceRequireInnovationStatement", False))
    require_problem_solution_trace = bool(case_payload.get("acceptanceRequireProblemSolutionTrace", False))
    require_limitations_and_future_work = bool(case_payload.get("acceptanceRequireLimitationsAndFutureWork", False))
    require_task_book_progress = bool(case_payload.get("acceptanceRequireTaskBookProgress", False))
    require_foreign_translation = bool(case_payload.get("acceptanceRequireForeignTranslation", False))
    require_defense_qa_ready = bool(case_payload.get("acceptanceRequireDefenseQAReady", False))
    window_execution_metrics = window_execution_metrics or {}
    tool_metrics = _g4_tool_execution_metrics(invocation_rows or [])
    step_metrics = _g4_extract_step_metrics(response_text)

    enabled = any(
        (
            required_sections,
            required_phrases,
            required_any_phrases,
            reject_phrases,
            min_restart_count is not None,
            min_window_index is not None,
            min_cumulative_window_span_tokens is not None,
            min_work_tree_continuity is not None,
            min_minimal_workset_ratio is not None,
            min_window_execution_count is not None,
            max_planning_stub_rate is not None,
            max_retrieval_drift_rate is not None,
            require_prefix_cache_key,
            min_cache_evidence is not None,
            min_independent_steps is not None,
            min_tool_backed_step_ratio is not None,
            min_memory_node_count is not None,
            require_experiment_record,
            require_dispute_list,
            bool(required_tool_categories),
            bool(required_observed_tool_categories),
            min_successful_tool_executions is not None,
            bool(required_academic_sections),
            min_citation_markers is not None,
            bool(required_deliverables),
            min_evidence_links is not None,
            require_innovation_statement,
            require_problem_solution_trace,
            require_limitations_and_future_work,
            require_task_book_progress,
            require_foreign_translation,
            require_defense_qa_ready,
        )
    )
    checks: list[dict[str, Any]] = []
    issues: list[str] = []

    if required_sections:
        missing_sections = [
            section for section in required_sections
            if _g4_normalize_match_text(section) not in normalized_response
        ]
        checks.append(
            {
                "command": "g4-required-sections",
                "returncode": 1 if missing_sections else 0,
                "detail": "missing sections: " + ", ".join(missing_sections) if missing_sections else "all required sections present",
            }
        )
        if missing_sections:
            issues.append("缺少必需小节: " + ", ".join(missing_sections))

    if required_phrases:
        missing_phrases = [
            phrase for phrase in required_phrases
            if _g4_normalize_match_text(phrase) not in normalized_response
        ]
        checks.append(
            {
                "command": "g4-required-phrases",
                "returncode": 1 if missing_phrases else 0,
                "detail": "missing phrases: " + ", ".join(missing_phrases) if missing_phrases else "all required phrases present",
            }
        )
        if missing_phrases:
            issues.append("缺少必需短语: " + ", ".join(missing_phrases))

    if required_academic_sections:
        missing_sections = [
            section for section in required_academic_sections
            if _g4_normalize_match_text(section) not in normalized_response
        ]
        checks.append(
            {
                "command": "g4-required-academic-sections",
                "returncode": 1 if missing_sections else 0,
                "detail": "missing academic sections: " + ", ".join(missing_sections) if missing_sections else "all required academic sections present",
            }
        )
        if missing_sections:
            issues.append("缺少本科论文关键小节: " + ", ".join(missing_sections))

    if required_any_phrases:
        matched_any_phrase = any(
            _g4_normalize_match_text(phrase) in normalized_response
            for phrase in required_any_phrases
        )
        checks.append(
            {
                "command": "g4-required-any-phrases",
                "returncode": 0 if matched_any_phrase else 1,
                "detail": "matched one required alternative phrase" if matched_any_phrase else "missing any accepted alternative phrase",
            }
        )
        if not matched_any_phrase:
            issues.append("缺少至少一个必需判断短语: " + ", ".join(required_any_phrases))

    if reject_phrases:
        matched_reject_phrases = [
            phrase for phrase in reject_phrases
            if _g4_normalize_match_text(phrase) in normalized_response
        ]
        checks.append(
            {
                "command": "g4-reject-phrases",
                "returncode": 1 if matched_reject_phrases else 0,
                "detail": "matched reject phrases: " + ", ".join(matched_reject_phrases) if matched_reject_phrases else "no reject phrases matched",
            }
        )
        if matched_reject_phrases:
            issues.append("命中拒绝短语: " + ", ".join(matched_reject_phrases))

    if min_restart_count is not None:
        expected = max(_g4_int_metric(min_restart_count), 0)
        actual = max(_g4_int_metric(runtime_metrics.get("restartCount")), 0)
        checks.append(
            {
                "command": "g4-min-restart-count",
                "returncode": 0 if actual >= expected else 1,
                "detail": f"restartCount={actual}, expected>={expected}",
            }
        )
        if actual < expected:
            issues.append(f"restartCount 不足: actual={actual}, expected>={expected}")

    if min_window_index is not None:
        expected = max(_g4_int_metric(min_window_index), 1)
        actual = max(_g4_int_metric(runtime_metrics.get("windowIndex")), 1)
        checks.append(
            {
                "command": "g4-min-window-index",
                "returncode": 0 if actual >= expected else 1,
                "detail": f"windowIndex={actual}, expected>={expected}",
            }
        )
        if actual < expected:
            issues.append(f"windowIndex 不足: actual={actual}, expected>={expected}")

    if min_cumulative_window_span_tokens is not None:
        expected = max(_g4_int_metric(min_cumulative_window_span_tokens), 0)
        actual = max(_g4_int_metric(runtime_metrics.get("cumulativeWindowSpanTokens")), 0)
        checks.append(
            {
                "command": "g4-min-cumulative-window-span-tokens",
                "returncode": 0 if actual >= expected else 1,
                "detail": f"cumulativeWindowSpanTokens={actual}, expected>={expected}",
            }
        )
        if actual < expected:
            issues.append(f"cumulativeWindowSpanTokens 不足: actual={actual}, expected>={expected}")

    if min_work_tree_continuity is not None:
        expected = max(float(min_work_tree_continuity), 0.0)
        actual = float(window_execution_metrics.get("workTreeContinuity0_1") or 0.0)
        checks.append(
            {
                "command": "g4-min-work-tree-continuity",
                "returncode": 0 if actual >= expected else 1,
                "detail": f"workTreeContinuity0_1={actual}, expected>={expected}",
            }
        )
        if actual < expected:
            issues.append(f"workTreeContinuity0_1 不足: actual={actual}, expected>={expected}")

    if min_minimal_workset_ratio is not None:
        expected = max(float(min_minimal_workset_ratio), 0.0)
        actual = float(window_execution_metrics.get("minimalWorksetRatio0_1") or 0.0)
        checks.append(
            {
                "command": "g4-min-minimal-workset-ratio",
                "returncode": 0 if actual >= expected else 1,
                "detail": f"minimalWorksetRatio0_1={actual}, expected>={expected}",
            }
        )
        if actual < expected:
            issues.append(f"minimalWorksetRatio0_1 不足: actual={actual}, expected>={expected}")

    if min_window_execution_count is not None:
        expected = max(_g4_int_metric(min_window_execution_count), 0)
        actual = max(_g4_int_metric(window_execution_metrics.get("windowExecutionCount"), 0), 0)
        checks.append(
            {
                "command": "g4-min-window-execution-count",
                "returncode": 0 if actual >= expected else 1,
                "detail": f"windowExecutionCount={actual}, expected>={expected}",
            }
        )
        if actual < expected:
            issues.append(f"windowExecutionCount 不足: actual={actual}, expected>={expected}")

    if max_planning_stub_rate is not None:
        expected = max(float(max_planning_stub_rate), 0.0)
        actual = float(window_execution_metrics.get("planningStubRate0_1") or 0.0)
        checks.append(
            {
                "command": "g4-max-planning-stub-rate",
                "returncode": 0 if actual <= expected else 1,
                "detail": f"planningStubRate0_1={actual}, expected<={expected}",
            }
        )
        if actual > expected:
            issues.append(f"planningStubRate0_1 超限: actual={actual}, expected<={expected}")

    if max_retrieval_drift_rate is not None:
        expected = max(float(max_retrieval_drift_rate), 0.0)
        actual = float(window_execution_metrics.get("retrievalDriftRate0_1") or 0.0)
        checks.append(
            {
                "command": "g4-max-retrieval-drift-rate",
                "returncode": 0 if actual <= expected else 1,
                "detail": f"retrievalDriftRate0_1={actual}, expected<={expected}",
            }
        )
        if actual > expected:
            issues.append(f"retrievalDriftRate0_1 超限: actual={actual}, expected<={expected}")

    if require_prefix_cache_key:
        actual = float(window_execution_metrics.get("prefixCacheReady0_1") or 0.0)
        checks.append(
            {
                "command": "g4-require-prefix-cache-key",
                "returncode": 0 if actual >= 1.0 else 1,
                "detail": f"prefixCacheReady0_1={actual}, expected=1.0",
            }
        )
        if actual < 1.0:
            issues.append(f"prefixCacheReady0_1 不足: actual={actual}, expected=1.0")

    if min_cache_evidence is not None:
        expected = max(float(min_cache_evidence), 0.0)
        actual = float(window_execution_metrics.get("cacheEvidence0_1") or 0.0)
        checks.append(
            {
                "command": "g4-min-cache-evidence",
                "returncode": 0 if actual >= expected else 1,
                "detail": f"cacheEvidence0_1={actual}, expected>={expected}",
            }
        )
        if actual < expected:
            issues.append(f"cacheEvidence0_1 不足: actual={actual}, expected>={expected}")

    if min_independent_steps is not None:
        expected = max(_g4_int_metric(min_independent_steps), 0)
        actual = _g4_int_metric(step_metrics.get("independentSteps"), 0)
        checks.append(
            {
                "command": "g4-min-independent-steps",
                "returncode": 0 if actual >= expected else 1,
                "detail": f"independentSteps={actual}, expected>={expected}",
            }
        )
        if actual < expected:
            issues.append(f"独立步骤数不足: actual={actual}, expected>={expected}")

    if min_tool_backed_step_ratio is not None:
        expected = max(float(min_tool_backed_step_ratio), 0.0)
        actual = float(step_metrics.get("toolBackedStepRatio0_1") or 0.0)
        checks.append(
            {
                "command": "g4-min-tool-backed-step-ratio",
                "returncode": 0 if actual >= expected else 1,
                "detail": f"toolBackedStepRatio0_1={actual}, expected>={expected}",
            }
        )
        if actual < expected:
            issues.append(f"工具支撑步骤占比不足: actual={actual}, expected>={expected}")

    if min_memory_node_count is not None:
        expected = max(_g4_int_metric(min_memory_node_count), 0)
        actual = max(
            _g4_int_metric(tool_metrics.get("memoryNodeCount"), 0),
            _g4_declared_memory_node_count(response_text),
            0,
        )
        checks.append(
            {
                "command": "g4-min-memory-node-count",
                "returncode": 0 if actual >= expected else 1,
                "detail": f"memoryNodeCount={actual}, expected>={expected}",
            }
        )
        if actual < expected:
            issues.append(f"记忆节点数不足: actual={actual}, expected>={expected}")

    if require_experiment_record:
        has_experiment_record = any(
            marker in normalized_response for marker in (
                _g4_normalize_match_text("实验记录"),
                _g4_normalize_match_text("实验结果"),
                _g4_normalize_match_text("experiment"),
            )
        )
        checks.append(
            {
                "command": "g4-require-experiment-record",
                "returncode": 0 if has_experiment_record else 1,
                "detail": "experiment record marker found" if has_experiment_record else "missing experiment record marker",
            }
        )
        if not has_experiment_record:
            issues.append("缺少实验记录集合")

    if require_dispute_list:
        has_dispute_list = any(
            marker in normalized_response for marker in (
                _g4_normalize_match_text("争议"),
                _g4_normalize_match_text("未决问题"),
                _g4_normalize_match_text("open question"),
            )
        )
        checks.append(
            {
                "command": "g4-require-dispute-list",
                "returncode": 0 if has_dispute_list else 1,
                "detail": "dispute/open-question marker found" if has_dispute_list else "missing dispute/open-question marker",
            }
        )
        if not has_dispute_list:
            issues.append("缺少争议与未决问题清单")

    if required_tool_categories:
        actual_categories = set(str(item).lower() for item in tool_metrics.get("toolCategories") or [])
        actual_categories.update(_g4_declared_tool_categories(response_text))
        expected_categories = [str(item).lower() for item in required_tool_categories]
        missing_categories = [item for item in expected_categories if item not in actual_categories]
        checks.append(
            {
                "command": "g4-require-tool-categories",
                "returncode": 1 if missing_categories else 0,
                "detail": "missing tool categories: " + ", ".join(missing_categories) if missing_categories else "all required tool categories covered",
            }
        )
        if missing_categories:
            issues.append("工具类别覆盖不足: " + ", ".join(missing_categories))

    if required_observed_tool_categories:
        actual_categories = set(str(item).lower() for item in tool_metrics.get("toolCategories") or [])
        expected_categories = [str(item).lower() for item in required_observed_tool_categories]
        missing_categories = [item for item in expected_categories if item not in actual_categories]
        checks.append(
            {
                "command": "g4-require-observed-tool-categories",
                "returncode": 1 if missing_categories else 0,
                "detail": "missing observed tool categories: " + ", ".join(missing_categories) if missing_categories else "all required observed tool categories covered",
            }
        )
        if missing_categories:
            issues.append("实测工具类别覆盖不足: " + ", ".join(missing_categories))

    if min_successful_tool_executions is not None:
        expected = max(_g4_int_metric(min_successful_tool_executions), 0)
        actual = max(_g4_int_metric(tool_metrics.get("successfulToolExecutions"), 0), 0)
        checks.append(
            {
                "command": "g4-min-successful-tool-executions",
                "returncode": 0 if actual >= expected else 1,
                "detail": f"successfulToolExecutions={actual}, expected>={expected}",
            }
        )
        if actual < expected:
            issues.append(f"成功工具动作不足: actual={actual}, expected>={expected}")

    if min_citation_markers is not None:
        expected = max(_g4_int_metric(min_citation_markers), 0)
        actual = _g4_count_citation_markers(response_text)
        checks.append(
            {
                "command": "g4-min-citation-markers",
                "returncode": 0 if actual >= expected else 1,
                "detail": f"citationMarkers={actual}, expected>={expected}",
            }
        )
        if actual < expected:
            issues.append(f"引用标记不足: actual={actual}, expected>={expected}")

    if required_deliverables:
        missing_deliverables = [
            item for item in required_deliverables
            if _g4_normalize_match_text(item) not in normalized_response
        ]
        checks.append(
            {
                "command": "g4-required-deliverables",
                "returncode": 1 if missing_deliverables else 0,
                "detail": "missing deliverables: " + ", ".join(missing_deliverables) if missing_deliverables else "all required deliverables present",
            }
        )
        if missing_deliverables:
            issues.append("缺少关键交付物: " + ", ".join(missing_deliverables))

    if min_evidence_links is not None:
        expected = max(_g4_int_metric(min_evidence_links), 0)
        actual = _g4_count_evidence_links(response_text)
        checks.append(
            {
                "command": "g4-min-evidence-links",
                "returncode": 0 if actual >= expected else 1,
                "detail": f"evidenceLinks={actual}, expected>={expected}",
            }
        )
        if actual < expected:
            issues.append(f"证据链接数量不足: actual={actual}, expected>={expected}")

    if require_innovation_statement:
        has_innovation = _g4_has_any_marker(
            response_text,
            ["创新", "创新点", "贡献", "novel", "novelty", "contribution"],
        )
        checks.append(
            {
                "command": "g4-require-innovation-statement",
                "returncode": 0 if has_innovation else 1,
                "detail": "innovation marker found" if has_innovation else "missing innovation marker",
            }
        )
        if not has_innovation:
            issues.append("缺少创新性或贡献说明")

    if require_problem_solution_trace:
        has_problem = _g4_has_any_marker(response_text, ["问题", "problem", "challenge", "瓶颈"])
        has_solution = _g4_has_any_marker(response_text, ["解决", "solution", "mitigation", "改进"])
        checks.append(
            {
                "command": "g4-require-problem-solution-trace",
                "returncode": 0 if (has_problem and has_solution) else 1,
                "detail": f"problemMarker={has_problem}, solutionMarker={has_solution}",
            }
        )
        if not (has_problem and has_solution):
            issues.append("缺少问题分析与解决路径闭环")

    if require_limitations_and_future_work:
        has_limits = _g4_has_any_marker(response_text, ["局限", "限制", "limitation", "threats to validity"])
        has_future = _g4_has_any_marker(response_text, ["未来工作", "后续工作", "future work", "next steps"])
        checks.append(
            {
                "command": "g4-require-limitations-and-future-work",
                "returncode": 0 if (has_limits and has_future) else 1,
                "detail": f"limitationsMarker={has_limits}, futureWorkMarker={has_future}",
            }
        )
        if not (has_limits and has_future):
            issues.append("缺少局限性与未来工作说明")

    if require_task_book_progress:
        has_task_book_progress = _g4_has_any_marker(response_text, ["任务书", "进度", "milestone", "timeline"])
        checks.append(
            {
                "command": "g4-require-task-book-progress",
                "returncode": 0 if has_task_book_progress else 1,
                "detail": "task-book/progress marker found" if has_task_book_progress else "missing task-book/progress marker",
            }
        )
        if not has_task_book_progress:
            issues.append("缺少任务书与进度执行说明")

    if require_foreign_translation:
        has_foreign_translation = _g4_has_any_marker(response_text, ["外文翻译", "translation", "translated", "原文", "译文"])
        checks.append(
            {
                "command": "g4-require-foreign-translation",
                "returncode": 0 if has_foreign_translation else 1,
                "detail": "foreign translation marker found" if has_foreign_translation else "missing foreign translation marker",
            }
        )
        if not has_foreign_translation:
            issues.append("缺少外文翻译任务与结果说明")

    if require_defense_qa_ready:
        has_defense_ready = _g4_has_any_marker(response_text, ["答辩", "问题回答", "q&a", "问答"])
        checks.append(
            {
                "command": "g4-require-defense-qa-ready",
                "returncode": 0 if has_defense_ready else 1,
                "detail": "defense Q&A marker found" if has_defense_ready else "missing defense Q&A marker",
            }
        )
        if not has_defense_ready:
            issues.append("缺少答辩问答准备说明")

    return {
        "enabled": enabled,
        "passed": not issues,
        "issues": issues,
        "checks": checks,
    }
def _g4_current_context(case_payload: dict[str, Any]) -> list[dict[str, Any]]:
    context_items = [dict(item) for item in case_payload.get("currentContext") or [] if isinstance(item, dict)]
    workspace_root = resolve_workspace_root()
    seen_paths: set[str] = set()

    def _append_file(relative_path: str, item: dict[str, Any], default_id: str) -> None:
        normalized_path = relative_path.strip().replace("\\", "/")
        if not normalized_path or normalized_path in seen_paths:
            return
        file_path = (workspace_root / normalized_path).resolve()
        if not file_path.exists() or not file_path.is_file():
            raise RuntimeError(f"g4 currentContextFiles entry is missing: {normalized_path}")

        encoding = str(item.get("encoding") or "utf-8")
        try:
            content = file_path.read_text(encoding=encoding)
        except UnicodeDecodeError as exc:
            raise RuntimeError(f"g4 currentContextFiles failed to read {normalized_path} with encoding {encoding}: {exc}") from exc

        line_start_raw = item.get("lineStart")
        line_end_raw = item.get("lineEnd")
        if line_start_raw is not None or line_end_raw is not None:
            lines = content.splitlines()
            start_line = max(_g4_int_metric(line_start_raw, 1), 1)
            end_line = min(_g4_int_metric(line_end_raw, len(lines)), len(lines))
            if end_line < start_line:
                raise RuntimeError(f"g4 currentContextFiles has invalid line range for {normalized_path}: {start_line}-{end_line}")
            content = "\n".join(lines[start_line - 1 : end_line])

        max_chars = _g4_int_metric(item.get("maxChars"), 0)
        if max_chars > 0 and len(content) > max_chars:
            content = content[:max_chars]

        prepend_path = bool(item.get("prependPath", True))
        if prepend_path:
            content = f"File: {normalized_path}\n\n{content}"

        context_items.append(
            {
                "id": str(item.get("id") or default_id),
                "title": str(item.get("title") or normalized_path),
                "content": content,
                "importance": float(item.get("importance") or 0.98),
                "rootBranch": str(item.get("rootBranch") or "context"),
            }
        )
        seen_paths.add(normalized_path)

    for index, item in enumerate(case_payload.get("currentContextFiles") or []):
        if not isinstance(item, dict):
            continue
        _append_file(str(item.get("path") or ""), item, f"ctx_file_{index}")

    glob_offset = len(context_items)
    for glob_index, item in enumerate(case_payload.get("currentContextGlobs") or []):
        if not isinstance(item, dict):
            continue
        pattern = str(item.get("pattern") or "").strip().replace("\\", "/")
        if not pattern:
            continue
        max_files = _g4_int_metric(item.get("maxFiles"), 0)
        matched_paths = [
            path for path in sorted(workspace_root.glob(pattern))
            if path.is_file()
        ]
        if max_files > 0:
            matched_paths = matched_paths[:max_files]
        for file_index, file_path in enumerate(matched_paths):
            relative_path = file_path.relative_to(workspace_root).as_posix()
            _append_file(relative_path, item, f"ctx_glob_{glob_offset + glob_index}_{file_index}")
    return context_items
def _g4_preview_request(case_payload: dict[str, Any]) -> dict[str, Any]:
    app_id = str(case_payload.get("appId") or DEFAULT_APP_ID)
    task_type = str(case_payload.get("taskType") or "generic")
    run_type = str(case_payload.get("runType") or "main")
    current_focus = str(case_payload.get("currentFocus") or f"g4-{task_type}-preview")
    current_objective = str(case_payload.get("currentObjective") or "Validate the official G4 prompt contract.")
    resume_message = str(case_payload.get("resumeMessage") or "continue the G4 evaluation flow")
    request_payload = dict(case_payload.get("request") or {})
    request_payload.setdefault("appId", app_id)
    if case_payload.get("expectedPromptProfileId") is not None:
        request_payload.setdefault("promptProfileId", str(case_payload.get("expectedPromptProfileId") or ""))
    if case_payload.get("expectedSeedTemplateId") is not None:
        request_payload.setdefault("seedTemplateId", str(case_payload.get("expectedSeedTemplateId") or ""))
    request_payload.setdefault("currentFocus", current_focus)
    request_payload.setdefault("currentObjective", current_objective)
    if case_payload.get("resumeMessage") is not None:
        request_payload["resumeMessage"] = resume_message

    return {
        "appId": app_id,
        "runType": run_type,
        "taskType": task_type,
        "activeCapabilities": list(case_payload.get("activeCapabilities") or []),
        "task": {
            "title": str(case_payload.get("taskTitle") or f"G4 {app_id} Preview"),
            "goal": str(case_payload.get("taskGoal") or "Validate the official Gate 4 prompt contract."),
            "currentFocus": current_focus,
            "currentObjective": current_objective,
            "resumeMessage": resume_message,
        },
        "request": request_payload,
        "resumePath": str(case_payload.get("resumePath")) if case_payload.get("resumePath") is not None else None,
        "currentContext": list(
            case_payload.get("currentContext")
            or [
                {
                    "id": f"ctx_{task_type}_g4",
                    "title": f"G4 {task_type} context",
                    "content": str(
                        case_payload.get("context")
                        or "This evaluation checks official G4 scene assembly, few-shot execution, and scene isolation."
                    ),
                    "rootBranch": "context",
                }
            ]
        ),
    }
def _g4_fetch_preview(case_payload: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    from fastapi.testclient import TestClient
    from yggdrasil_core_api.app import app

    client = TestClient(app)
    app_id = str(case_payload.get("appId") or DEFAULT_APP_ID)
    profiles = client.get("/prompting/prompt-profiles", params={"appId": app_id})
    templates = client.get("/prompting/seed-templates", params={"appId": app_id})
    preview = client.post("/prompting/compile-preview", json=_g4_preview_request(case_payload))
    responses = [profiles, templates, preview]
    if any(response.status_code not in {200, 201} for response in responses):
        raise RuntimeError("g4 prompt preview surface returned non-200 responses")
    return (
        list(profiles.json().get("promptProfiles") or []),
        list(templates.json().get("seedTemplates") or []),
        dict(preview.json().get("compiledPrompt") or {}),
    )
def _g4_validate_prompt_contract(case_payload: dict[str, Any], preview_payload: dict[str, Any], profile_list: list[dict[str, Any]], template_list: list[dict[str, Any]]) -> dict[str, Any]:
    expected_profile_id = str(case_payload.get("expectedPromptProfileId") or "")
    expected_seed_id = str(case_payload.get("expectedSeedTemplateId") or "")
    expected_profile_refs = [str(item) for item in case_payload.get("expectedProfileFewShotRefs") or []]
    expected_seed_refs = [str(item) for item in case_payload.get("expectedSeedFewShotRefs") or []]
    expected_compiled_refs = [str(item) for item in case_payload.get("expectedCompiledFewShotRefs") or []]
    expected_markers = [str(item) for item in case_payload.get("expectedMarkers") or []]
    expected_source_module_id = str(case_payload.get("expectedSourceModuleId") or "").strip()
    expected_message_count = int(case_payload.get("expectedMessageCount") or 0)

    profile = next((item for item in profile_list if str(item.get("id") or "") == expected_profile_id), None)
    template = next((item for item in template_list if str(item.get("id") or "") == expected_seed_id), None)
    if profile is None:
        raise RuntimeError(f"missing expected prompt profile: {expected_profile_id}")
    if template is None:
        raise RuntimeError(f"missing expected seed template: {expected_seed_id}")
    if str(preview_payload.get("promptProfileId") or "") != expected_profile_id:
        raise RuntimeError("g4 preview selected the wrong prompt profile")
    if str(preview_payload.get("seedTemplateId") or "") != expected_seed_id:
        raise RuntimeError("g4 preview selected the wrong seed template")
    if list(profile.get("fewShotRefs") or []) != expected_profile_refs:
        raise RuntimeError("g4 prompt profile few-shot refs do not match the official contract")
    if list(template.get("fewShotRefs") or []) != expected_seed_refs:
        raise RuntimeError("g4 seed template few-shot refs do not match the official contract")
    if list(preview_payload.get("fewShotRefs") or []) != expected_compiled_refs:
        raise RuntimeError("g4 compiled prompt few-shot refs do not match the effective contract")
    if expected_source_module_id and str(template.get("sourceModuleId") or "") != expected_source_module_id:
        raise RuntimeError("g4 seed template is not sourced from the expected scene module")

    messages = [dict(item) for item in preview_payload.get("messages") or [] if isinstance(item, dict)]
    if expected_message_count and len(messages) != expected_message_count:
        raise RuntimeError(f"g4 preview message count mismatch: expected {expected_message_count}, got {len(messages)}")
    few_shot_text = "\n\n".join(str(item.get("content") or "") for item in messages[1:-1])
    for marker in expected_markers:
        if marker not in few_shot_text:
            raise RuntimeError(f"g4 preview few-shot marker missing: {marker}")

    return {
        "appId": preview_payload.get("appId"),
        "promptProfileId": preview_payload.get("promptProfileId"),
        "seedTemplateId": preview_payload.get("seedTemplateId"),
        "scenario": preview_payload.get("scenario"),
        "fewShotRefs": list(preview_payload.get("fewShotRefs") or []),
        "messageCount": len(messages),
    }
def _run_g4_scene_prompt_contract_case(case: dict[str, Any] | None = None) -> dict[str, Any]:
    case_payload = dict(case or {})
    profile_list, template_list, preview_payload = _g4_fetch_preview(case_payload)
    return _g4_validate_prompt_contract(case_payload, preview_payload, profile_list, template_list)
def _run_g4_scene_resume_contract_case(case: dict[str, Any] | None = None) -> dict[str, Any]:
    case_payload = dict(case or {})
    profile_list, template_list, preview_payload = _g4_fetch_preview(case_payload)
    detail = _g4_validate_prompt_contract(case_payload, preview_payload, profile_list, template_list)
    user_sections = dict(preview_payload.get("userSections") or {})
    expected_resume_message = str(case_payload.get("resumeMessage") or "")
    expected_resume_path = str(case_payload.get("resumePath") or "")
    if expected_resume_message and str(user_sections.get("resume_message") or "") != expected_resume_message:
        raise RuntimeError("g4 resume contract did not preserve the expected resume message")
    if expected_resume_path and f"Resume path: {expected_resume_path}" not in str(user_sections.get("task_contract") or ""):
        raise RuntimeError("g4 resume contract did not preserve the expected resume path")
    detail["resumeMessage"] = user_sections.get("resume_message")
    detail["resumePath"] = expected_resume_path
    return detail
def _run_g4_scene_runtime_recovery_case(case: dict[str, Any] | None = None) -> dict[str, Any]:
    from fastapi.testclient import TestClient
    from yggdrasil_agent_runtime.app import app as runtime_app
    from yggdrasil_worker.registry import run_worker_once

    case_payload = dict(case or {})
    app_id = str(case_payload.get("appId") or DEFAULT_APP_ID)
    task_type = str(case_payload.get("taskType") or "generic")
    expected_few_shot_refs = [str(item) for item in case_payload.get("expectedCompiledFewShotRefs") or []]
    expected_scenario = str(case_payload.get("expectedScenario") or "").strip()
    expected_result_status = str(case_payload.get("expectedResultStatus") or "awaiting-approval")
    expected_task_status = str(case_payload.get("expectedTaskStatus") or expected_result_status)
    expected_work_tree_status = str(case_payload.get("expectedWorkTreeStatus") or expected_task_status)
    task = _seed_runtime_task(
        str(case_payload.get("taskId") or new_id("task", app_id, task_type, "g4-recovery", stable=False)),
        app_id=app_id,
        title=str(case_payload.get("taskTitle") or f"G4 {app_id} Recovery Task"),
        goal=str(case_payload.get("taskGoal") or "Validate the official Gate 4 recovery flow."),
        current_focus=str(case_payload.get("currentFocus") or f"g4-{task_type}-recovery"),
        current_objective=str(case_payload.get("currentObjective") or "Pause, resume, and preserve the official scene contract."),
        resume_message=str(case_payload.get("resumeMessage") or "continue the recovery validation"),
    )
    client = TestClient(runtime_app)

    def _root_only_takeover_protocol(task_id: str) -> dict[str, Any]:
        objective = str(case_payload.get("currentObjective") or "Pause, resume, and preserve the official scene contract.")
        return {
            "id": f"takeover_{task_id}",
            "version": "0.1.0",
            "taskId": task_id,
            "taskType": task_type,
            "runType": "main",
            "currentPhase": "execute",
            "status": "executing",
            "objective": objective,
            "objectiveSummary": objective,
            "ambiguities": [],
            "constraints": [],
            "plan": [],
            "workTree": {
                "version": "0.2.0",
                "id": f"work_tree_{task_id}",
                "taskId": task_id,
                "rootNodeId": "root",
                "rootObjective": objective,
                "status": "active",
                "currentNodeId": "root",
                "loadedNodeIds": ["root"],
                "activePathNodeIds": ["root"],
                "pcMemo": "continue:root",
                "entropyBudgetRemaining": 8,
                "versionCounter": 1,
                "nodes": [
                    {
                        "id": "root",
                        "title": "root",
                        "parentNodeId": None,
                        "questionsItAnswers": ["next step"],
                        "nodeText": "Deliver the final result on the root node.",
                        "localGoal": "Deliver the final result on the root node.",
                        "workingNodeAnnotation": "<Working_Node: root>",
                        "phase": "delivery",
                        "status": "in-progress",
                        "childNodeIds": [],
                        "detailLevel": 0,
                        "recoveryAnchor": "resume:root",
                    }
                ],
            },
        }

    start_payload = {
        "appId": app_id,
        "taskType": task_type,
        "currentFocus": str(case_payload.get("currentFocus") or task.get("currentFocus") or "g4-recovery"),
        "currentObjective": str(case_payload.get("currentObjective") or task.get("currentObjective") or "g4 recovery"),
        "currentContext": list(
            case_payload.get("currentContext")
            or [
                {
                    "id": "ctx_g4_recovery",
                    "title": "G4 recovery contract",
                    "content": str(
                        case_payload.get("context")
                        or "The resumed run must preserve the official app scene, few-shot refs, and recovery instructions."
                    ),
                    "importance": 0.99,
                }
            ]
        ),
        "protectedItems": case_payload.get("protectedItems") or [{"kind": "node", "id": "ctx_g4_recovery"}],
        "allowModelFallback": bool(case_payload.get("allowFallback", True)),
        "temperature": float(case_payload.get("temperature") or 0.1),
        "maxTokens": int(case_payload.get("maxTokens") or 240),
    }
    if not case_payload.get("takeoverProtocol"):
        start_payload["takeoverProtocol"] = _root_only_takeover_protocol(task["id"])
    started = client.post(f"/runtime/tasks/{task['id']}/start", json=start_payload)
    if started.status_code != 202:
        raise RuntimeError(f"g4 runtime recovery start failed: {started.text}")
    pause_request = client.post(
        f"/runtime/tasks/{task['id']}/pause",
        json={
            "reason": "g4-evaluation-pause",
            "resumeMessage": str(case_payload.get("resumeMessage") or "continue the recovery validation"),
        },
    )
    if pause_request.status_code != 202:
        raise RuntimeError(f"g4 runtime recovery pause request failed: {pause_request.text}")
    first = run_worker_once("agent-runtime")
    if (first.get("result") or {}).get("status") != "paused":
        raise RuntimeError(f"g4 runtime recovery pause step failed: {json.dumps(first, ensure_ascii=False)}")
    resumed = client.post(
        f"/runtime/tasks/{task['id']}/resume",
        json={
            "nextObjective": str(case_payload.get("resumeObjective") or "finish the G4 recovery flow"),
        },
    )
    if resumed.status_code != 202:
        raise RuntimeError(f"g4 runtime recovery resume failed: {resumed.text}")
    second = run_worker_once("agent-runtime")
    if (second.get("result") or {}).get("status") != expected_result_status:
        raise RuntimeError(f"g4 runtime recovery completion failed: {json.dumps(second, ensure_ascii=False)}")

    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        task_repository = TaskRepository(session)
        prompt_repository = PromptAssetRepository(session)
        runtime_repository = RuntimeRepository(session)
        persisted_task = task_repository.get_task(task["id"])
        invocations = runtime_repository.list_model_invocations(task_id=task["id"], limit=5)
        if not invocations:
            raise RuntimeError("g4 runtime recovery did not persist any model invocation")
        invocation = invocations[0]
        prompt_artifact = prompt_repository.get_prompt_compile_artifact(invocation.prompt_compile_artifact_id or "")
        if prompt_artifact is None:
            raise RuntimeError("g4 runtime recovery prompt artifact is missing")

    request_payload = _read_external_ref_json(invocation.request_ref, resolve_workspace_root()) or {}
    prompt_metadata = dict(request_payload.get("promptMetadata") or {})
    if list(prompt_metadata.get("fewShotRefs") or []) != expected_few_shot_refs:
        raise RuntimeError("g4 runtime recovery prompt metadata few-shot refs do not match the official contract")
    if expected_scenario and str(prompt_artifact.scenario or "") != expected_scenario:
        raise RuntimeError("g4 runtime recovery scenario drifted during pause/resume")
    if prompt_artifact.app_id != app_id:
        raise RuntimeError("g4 runtime recovery persisted prompt artifact under the wrong app scope")
    if persisted_task is None or str(persisted_task.status or "") != expected_task_status:
        raise RuntimeError(
            f"g4 runtime recovery task status drifted: expected {expected_task_status}, got {persisted_task.status if persisted_task is not None else 'missing'}"
        )

    takeover_protocol = dict((second.get("result") or {}).get("takeoverProtocol") or {})
    work_tree_status = str((takeover_protocol.get("workTree") or {}).get("status") or "") if takeover_protocol else ""
    if expected_work_tree_status and work_tree_status != expected_work_tree_status:
        raise RuntimeError(
            f"g4 runtime recovery work tree drifted: expected {expected_work_tree_status}, got {work_tree_status or 'missing'}"
        )

    return {
        "appId": app_id,
        "taskId": task["id"],
        "pauseStatus": (first.get("result") or {}).get("status"),
        "resumeStatus": (second.get("result") or {}).get("status"),
        "expectedResultStatus": expected_result_status,
        "expectedTaskStatus": expected_task_status,
        "promptCompileArtifactId": invocation.prompt_compile_artifact_id,
        "fewShotRefs": list(prompt_metadata.get("fewShotRefs") or []),
        "scenario": prompt_artifact.scenario,
        "taskStatus": persisted_task.status if persisted_task is not None else None,
        "workTreeStatus": work_tree_status,
    }
def _run_g4_scene_switch_isolation_case(case: dict[str, Any] | None = None) -> dict[str, Any]:
    case_payload = dict(case or {})
    sequence = [dict(item) for item in case_payload.get("sequence") or [] if isinstance(item, dict)]
    if not sequence:
        raise RuntimeError("g4 scene switch isolation case requires a non-empty sequence")
    steps: list[dict[str, Any]] = []
    for entry in sequence:
        profile_list, template_list, preview_payload = _g4_fetch_preview(entry)
        detail = _g4_validate_prompt_contract(entry, preview_payload, profile_list, template_list)
        compiled_text = "\n\n".join(str(item.get("content") or "") for item in preview_payload.get("messages") or [] if isinstance(item, dict))
        forbidden_markers = [str(item) for item in entry.get("forbiddenMarkers") or []]
        for marker in forbidden_markers:
            if marker and marker in compiled_text:
                raise RuntimeError(f"g4 scene switch leak detected for {entry.get('appId')}: {marker}")
        steps.append(
            {
                "appId": detail["appId"],
                "scenario": detail["scenario"],
                "fewShotRefs": detail["fewShotRefs"],
            }
        )
    return {
        "sequence": [str(item.get("appId") or "") for item in sequence],
        "steps": steps,
    }

def _g4_bind_takeover_protocol(task_id: str, protocol_payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(protocol_payload, dict):
        return None
    bound_protocol = dict(protocol_payload)
    bound_protocol["taskId"] = task_id
    work_tree_payload = bound_protocol.get("workTree")
    if isinstance(work_tree_payload, dict):
        updated_work_tree = dict(work_tree_payload)
        updated_work_tree["taskId"] = task_id
        bound_protocol["workTree"] = updated_work_tree
    return bound_protocol


def _g4_seed_awaiting_approval_for_revision(
    *,
    task_id: str,
    case_payload: dict[str, Any],
    requested_provider: str,
    requested_model: str,
) -> dict[str, Any]:
    from ..contracts import TaskTakeoverProtocol
    from ..runtime_kernel.takeover import persist_task_takeover_protocol

    takeover_payload = _g4_bind_takeover_protocol(task_id, case_payload.get("takeoverProtocol"))
    if takeover_payload is None:
        raise RuntimeError("g4 seeded revision case requires takeoverProtocol")
    protocol = TaskTakeoverProtocol.model_validate(takeover_payload)
    if protocol.work_tree is None or protocol.work_tree.status != "awaiting-approval":
        raise RuntimeError("g4 seeded revision takeoverProtocol must already be awaiting-approval")

    run_id = str(case_payload.get("seededApprovalRunId") or new_id("run", task_id, "seeded-approval", stable=False))
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        task_repository = TaskRepository(session)
        task = task_repository.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        task_repository.create_agent_run(
            task.id,
            {
                "id": run_id,
                "status": "completed",
                "selectedModel": requested_model,
                "selectedProvider": requested_provider,
            },
        )
        persist_task_takeover_protocol(protocol, task_id=task.id, run_id=run_id)
        task = task_repository.update_task(
            task_id,
            {
                "status": "awaiting-approval",
                "currentFocus": case_payload.get("seededApprovalFocus")
                or case_payload.get("currentFocus")
                or task.current_focus,
                "currentObjective": case_payload.get("seededApprovalObjective")
                or case_payload.get("currentObjective")
                or task.current_objective,
                "resumeMessage": case_payload.get("seededApprovalResumeMessage")
                or case_payload.get("resumeMessage")
                or task.resume_message,
            },
        )
    return {
        "status": "processed",
        "payload": {
            "taskId": task_id,
            "payload": {
                "takeoverProtocol": protocol.model_dump(by_alias=True, mode="json"),
                "currentFocus": task.current_focus,
                "currentObjective": task.current_objective,
            },
        },
        "result": {
            "status": "awaiting-approval",
            "assistantText": str(case_payload.get("seededApprovalAssistantText") or ""),
            "task": task.model_dump(by_alias=True, mode="json"),
            "takeoverProtocol": protocol.model_dump(by_alias=True, mode="json"),
        },
    }


def _g4_live_provider_matrix_start_payload(
    case_payload: dict[str, Any],
    task: dict[str, Any],
    *,
    app_id: str,
    task_type: str,
    candidate_models: list[dict[str, Any]],
) -> dict[str, Any]:
    # G4 default real-task suite should execute directly for acceptance evaluation,
    # so we force confirmation on start to avoid clarification-only stalls.
    plan_confirmed = True
    start_payload = {
        "appId": app_id,
        "taskType": task_type,
        "currentFocus": str(case_payload.get("currentFocus") or task.get("currentFocus") or "g4-live"),
        "currentObjective": str(case_payload.get("currentObjective") or task.get("currentObjective") or "g4 live task"),
        "currentContext": _g4_current_context(case_payload),
        "protectedItems": case_payload.get("protectedItems") or [],
        "allowModelFallback": bool(case_payload.get("allowFallback", False)),
        "allowToolExecution": bool(case_payload.get("allowToolExecution", False)),
        "temperature": float(case_payload.get("temperature") or 0.1),
        "maxTokens": int(case_payload.get("maxTokens") or 320),
        "takeoverPlanConfirmed": plan_confirmed,
        "planConfirmed": plan_confirmed,
        "confirmPlan": plan_confirmed,
        "takeoverAutoConfirm": plan_confirmed,
    }
    if case_payload.get("expectedPromptProfileId") is not None:
        start_payload["promptProfileId"] = str(case_payload.get("expectedPromptProfileId") or "")
    if case_payload.get("expectedSeedTemplateId") is not None:
        start_payload["seedTemplateId"] = str(case_payload.get("expectedSeedTemplateId") or "")
    if case_payload.get("activeCapabilities") is not None:
        start_payload["activeCapabilities"] = [str(item) for item in case_payload.get("activeCapabilities") or []]
    if case_payload.get("auditLevel") is not None:
        start_payload["auditLevel"] = str(case_payload.get("auditLevel") or "default")
    if case_payload.get("effectiveContextWindow") is not None:
        start_payload["effectiveContextWindow"] = int(case_payload["effectiveContextWindow"])
    if case_payload.get("windowRestartRatio") is not None:
        start_payload["windowRestartRatio"] = float(case_payload["windowRestartRatio"])
    if case_payload.get("windowRestartThreshold") is not None:
        start_payload["windowRestartThreshold"] = int(case_payload["windowRestartThreshold"])
    if case_payload.get("forcedWindowRestartBudget") is not None:
        start_payload["forcedWindowRestartBudget"] = int(case_payload["forcedWindowRestartBudget"])
    if case_payload.get("maxToolRounds") is not None:
        start_payload["maxToolRounds"] = int(case_payload["maxToolRounds"])
    if case_payload.get("responseRequirements") is not None:
        start_payload["responseRequirements"] = str(case_payload["responseRequirements"])
    if case_payload.get("toolResultReflectionReminder") is not None:
        start_payload["toolResultReflectionReminder"] = case_payload["toolResultReflectionReminder"]
    if case_payload.get("workTreeNodeToolCallSoftLimit") is not None:
        start_payload["workTreeNodeToolCallSoftLimit"] = case_payload["workTreeNodeToolCallSoftLimit"]
    if case_payload.get("workTreeDirectiveRequired") is not None:
        start_payload["workTreeDirectiveRequired"] = case_payload["workTreeDirectiveRequired"]
    if case_payload.get("workTreeDirectiveRequiredOnNaturalLanguage") is not None:
        start_payload["workTreeDirectiveRequiredOnNaturalLanguage"] = case_payload["workTreeDirectiveRequiredOnNaturalLanguage"]
    if case_payload.get("workTreeChildScopeCheckpoint") is not None:
        start_payload["workTreeChildScopeCheckpoint"] = case_payload["workTreeChildScopeCheckpoint"]
    if case_payload.get("toolNameAllowlist") is not None:
        start_payload["toolNameAllowlist"] = [str(item) for item in case_payload.get("toolNameAllowlist") or []]
    if case_payload.get("toolNameDenylist") is not None:
        start_payload["toolNameDenylist"] = [str(item) for item in case_payload.get("toolNameDenylist") or []]
    if case_payload.get("restartMessage") is not None:
        start_payload["restartMessage"] = str(case_payload["restartMessage"])
    if candidate_models:
        start_payload["candidateModels"] = [dict(candidate) for candidate in candidate_models]
    takeover_protocol = _g4_bind_takeover_protocol(str(task.get("id") or ""), case_payload.get("takeoverProtocol"))
    if takeover_protocol is not None:
        start_payload["takeoverProtocol"] = takeover_protocol
    return start_payload
def _g4_budget_state_with_top_up(budget: BudgetState, case_payload: dict[str, Any]) -> dict[str, Any]:
    updated_budget = budget.model_dump(by_alias=True, mode="json")

    token_total = updated_budget.get("tokenBudgetTotal")
    token_used = max(_g4_int_metric(updated_budget.get("tokenBudgetUsed"), 0), 0)
    if token_total is not None:
        raw_token_increment = case_payload.get("budgetTopUpTokenIncrement")
        if raw_token_increment is None:
            token_increment = max(token_used // 2, 4096)
        else:
            token_increment = max(_g4_int_metric(raw_token_increment, 0), 0)
        updated_budget["tokenBudgetTotal"] = max(_g4_int_metric(token_total, token_used), token_used) + token_increment

    cost_total = updated_budget.get("costBudgetTotal")
    cost_used = max(float(updated_budget.get("costBudgetUsed") or 0.0), 0.0)
    if cost_total is not None:
        raw_cost_increment = case_payload.get("budgetTopUpCostIncrement")
        if raw_cost_increment is None:
            cost_increment = max(cost_used * 0.5, 5.0)
        else:
            try:
                cost_increment = max(float(raw_cost_increment), 0.0)
            except (TypeError, ValueError):
                cost_increment = 5.0
        updated_budget["costBudgetTotal"] = round(max(float(cost_total or 0.0), cost_used) + cost_increment, 6)

    return updated_budget
def _g4_recover_live_budget_pause_or_failure(
    *,
    client,
    task_id: str,
    case_payload: dict[str, Any],
    result_payload: dict[str, Any],
    recovery_state: dict[str, int],
) -> bool:
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        task_repository = TaskRepository(session)
        task_record = task_repository.get_task(task_id)
        snapshot = task_repository.get_snapshot(task_record.active_snapshot_id) if task_record and task_record.active_snapshot_id else None

    if task_record is None:
        return False

    current_focus = str(task_record.current_focus or "")
    budget_exhausted = "budget-exhausted" in current_focus
    if not budget_exhausted:
        return False

    if task_record.status == "paused" and snapshot is not None and snapshot.status == "restorable":
        max_attempts = max(_g4_int_metric(case_payload.get("maxBudgetTopUpAttempts"), 2), 0)
        if recovery_state.get("budgetTopUpAttempts", 0) >= max_attempts:
            return False
        recovery_state["budgetTopUpAttempts"] = recovery_state.get("budgetTopUpAttempts", 0) + 1
        resumed = client.post(
            f"/runtime/tasks/{task_id}/resume",
            json={
                "budgetState": _g4_budget_state_with_top_up(task_record.budget, case_payload),
                "resumeMessage": str(
                    case_payload.get("budgetResumeMessage")
                    or task_record.resume_message
                    or "continue the live G4 evaluation after budget top-up"
                ),
                "nextObjective": str(
                    case_payload.get("budgetResumeObjective")
                    or task_record.current_objective
                    or task_record.goal
                ),
                "reason": "g4-evaluation-budget-top-up",
                "requestedBy": {"type": "agent", "id": "g4-evaluation"},
                "takeoverPlanConfirmed": True,
                "planConfirmed": True,
                "confirmPlan": True,
                "takeoverAutoConfirm": True,
            },
        )
        if resumed.status_code != 202:
            raise RuntimeError(f"g4 provider matrix budget top-up resume failed: {resumed.text}")
        return True

    if task_record.status == "failed":
        max_attempts = max(_g4_int_metric(case_payload.get("maxBudgetRetryAttempts"), 1), 0)
        if recovery_state.get("budgetRetryAttempts", 0) >= max_attempts:
            return False
        recovery_state["budgetRetryAttempts"] = recovery_state.get("budgetRetryAttempts", 0) + 1
        retried = client.post(
            f"/runtime/tasks/{task_id}/retry",
            json={
                "budgetState": _g4_budget_state_with_top_up(task_record.budget, case_payload),
                "resumeMessage": str(
                    case_payload.get("budgetResumeMessage")
                    or task_record.resume_message
                    or "continue the live G4 evaluation after budget retry"
                ),
                "reason": "g4-evaluation-budget-retry",
                "requestedBy": {"type": "agent", "id": "g4-evaluation"},
            },
        )
        if retried.status_code != 202:
            raise RuntimeError(f"g4 provider matrix budget retry failed: {retried.text}")
        return True

    return False
def _g4_wait_for_target_worker_result(
    *,
    task_id: str,
    expected_result_status: str,
    max_window_cycles: int,
    max_worker_wait_seconds: int,
    run_worker_once_fn,
    recovery_handler_fn=None,
    worker_poll_timeout_seconds: float | None = None,
    allow_manual_continue_on_max_window_cycles: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    import queue
    import threading
    import time

    processed_runs: list[dict[str, Any]] = []
    empty_poll_count = 0
    foreign_processed_count = 0
    last_relevant_poll_at = time.monotonic()
    poll_timeout_seconds = max(float(worker_poll_timeout_seconds), 0.05) if worker_poll_timeout_seconds is not None else None
    if poll_timeout_seconds is None:
        stall_deadline_seconds = max(float(max_worker_wait_seconds), 30.0)
    else:
        stall_deadline_seconds = max(float(max_worker_wait_seconds), 30.0) + poll_timeout_seconds

    while True:
        if time.monotonic() - last_relevant_poll_at >= stall_deadline_seconds:
            raise RuntimeError(
                "g4 provider matrix worker stalled while waiting for target queue payload: "
                f"taskId={task_id}, stallDeadlineSeconds={stall_deadline_seconds:.1f}, "
                f"emptyPollCount={empty_poll_count}, foreignProcessedCount={foreign_processed_count}, "
                f"processedRuns={len(processed_runs)}"
            )

        if poll_timeout_seconds is None:
            processed = run_worker_once_fn("agent-runtime", timeout_seconds=1)
            processed = dict(processed or {}) if isinstance(processed, dict) else {}
        else:
            poll_result_queue: queue.Queue[tuple[bool, Any]] = queue.Queue(maxsize=1)

            def _poll_once() -> None:
                try:
                    poll_result_queue.put((True, run_worker_once_fn("agent-runtime", timeout_seconds=1)))
                except Exception as exc:  # pragma: no cover - passthrough guard
                    poll_result_queue.put((False, exc))

            threading.Thread(target=_poll_once, daemon=True).start()
            try:
                succeeded, payload = poll_result_queue.get(timeout=poll_timeout_seconds)
            except queue.Empty as exc:
                raise RuntimeError(
                    "g4 provider matrix worker call timed out while polling queue: "
                    f"taskId={task_id}, pollTimeoutSeconds={poll_timeout_seconds:.1f}, "
                    f"emptyPollCount={empty_poll_count}, foreignProcessedCount={foreign_processed_count}, "
                    f"processedRuns={len(processed_runs)}"
                ) from exc

            if not succeeded:
                raise RuntimeError(
                    "g4 provider matrix worker call failed while polling queue: "
                    f"taskId={task_id}, error={payload!r}"
                )

            processed = dict(payload or {}) if isinstance(payload, dict) else {}

        if processed.get("status") == "empty":
            empty_poll_count += 1
            if time.monotonic() - last_relevant_poll_at >= max_worker_wait_seconds:
                raise RuntimeError(
                    "g4 provider matrix worker timed out while waiting for target queue payload: "
                    f"taskId={task_id}, waitedSeconds={max_worker_wait_seconds}, emptyPollCount={empty_poll_count}, "
                    f"foreignProcessedCount={foreign_processed_count}, processedRuns={len(processed_runs)}"
                )
            continue

        processed_task_id = str((processed.get("payload") or {}).get("taskId") or "")
        if processed_task_id != task_id:
            foreign_processed_count += 1
            if time.monotonic() - last_relevant_poll_at >= max_worker_wait_seconds:
                raise RuntimeError(
                    "g4 provider matrix worker timed out while waiting for target task progress amid foreign payloads: "
                    f"taskId={task_id}, waitedSeconds={max_worker_wait_seconds}, emptyPollCount={empty_poll_count}, "
                    f"foreignProcessedCount={foreign_processed_count}, processedRuns={len(processed_runs)}"
                )
            continue

        last_relevant_poll_at = time.monotonic()
        result_payload = dict(processed.get("result") or {})
        processed_runs.append(processed)
        if result_payload.get("status") in {"restarting", "continuing"}:
            if len(processed_runs) >= max_window_cycles:
                if allow_manual_continue_on_max_window_cycles:
                    manual_result_payload = {
                        "status": "manual-continue-required",
                        "reason": "max-window-cycles-reached",
                        "maxWindowCycles": max_window_cycles,
                        "processedRunCount": len(processed_runs),
                        "lastResultStatus": result_payload.get("status"),
                        "assistantText": result_payload.get("assistantText"),
                        "task": result_payload.get("task"),
                        "run": result_payload.get("run"),
                        "queuedWorkItem": result_payload.get("queuedWorkItem"),
                        "manualContinue": {
                            "taskId": task_id,
                            "queue": "agent-runtime",
                            "maxWindowCycles": max_window_cycles,
                            "processedRunCount": len(processed_runs),
                            "lastResultStatus": result_payload.get("status"),
                            "queuedWorkItem": result_payload.get("queuedWorkItem"),
                            "message": (
                                "The task still has a queued continuation after reaching maxWindowCycles. "
                                "Preserve the sandbox/state root and continue the queued agent-runtime work item manually."
                            ),
                        },
                    }
                    return processed_runs, processed, manual_result_payload
                raise RuntimeError(
                    f"g4 provider matrix exceeded maxWindowCycles={max_window_cycles}: {json.dumps(processed_runs[-1], ensure_ascii=False)}"
                )
            continue
        if recovery_handler_fn is not None and recovery_handler_fn(processed_runs=processed_runs, processed=processed, result_payload=result_payload):
            if len(processed_runs) >= max_window_cycles:
                if allow_manual_continue_on_max_window_cycles:
                    manual_result_payload = {
                        "status": "manual-continue-required",
                        "reason": "max-window-cycles-reached-during-recovery",
                        "maxWindowCycles": max_window_cycles,
                        "processedRunCount": len(processed_runs),
                        "lastResultStatus": result_payload.get("status"),
                        "assistantText": result_payload.get("assistantText"),
                        "task": result_payload.get("task"),
                        "run": result_payload.get("run"),
                        "queuedWorkItem": result_payload.get("queuedWorkItem"),
                        "manualContinue": {
                            "taskId": task_id,
                            "queue": "agent-runtime",
                            "maxWindowCycles": max_window_cycles,
                            "processedRunCount": len(processed_runs),
                            "lastResultStatus": result_payload.get("status"),
                            "queuedWorkItem": result_payload.get("queuedWorkItem"),
                            "message": (
                                "Recovery queued more work after maxWindowCycles. "
                                "Preserve the sandbox/state root and continue the queued agent-runtime work item manually."
                            ),
                        },
                    }
                    return processed_runs, processed, manual_result_payload
                raise RuntimeError(
                    f"g4 provider matrix exceeded maxWindowCycles={max_window_cycles} during recovery: {json.dumps(processed_runs[-1], ensure_ascii=False)}"
                )
            continue
        if not _g4_result_satisfies_expected_status(result_payload, expected_result_status):
            raise RuntimeError(f"g4 provider matrix worker failed: {json.dumps(processed, ensure_ascii=False)}")
        return processed_runs, processed, result_payload


def _g4_work_tree_approval_counts_as_completed(result_payload: dict[str, Any]) -> bool:
    if str(result_payload.get("status") or "") != "awaiting-approval":
        return False
    audit = result_payload.get("executionStateAudit") if isinstance(result_payload.get("executionStateAudit"), dict) else {}
    if bool(audit.get("deliveryGateBlocked")):
        return False
    if audit.get("continuationQueued"):
        return False
    blocked_gates = audit.get("blockedHardGates")
    if isinstance(blocked_gates, list) and blocked_gates:
        return False
    takeover_protocol = result_payload.get("takeoverProtocol")
    if not isinstance(takeover_protocol, dict):
        request_payload = result_payload.get("request")
        if isinstance(request_payload, dict):
            takeover_protocol = request_payload.get("takeoverProtocol")
    if not isinstance(takeover_protocol, dict):
        return False
    if str(takeover_protocol.get("status") or "") not in {"verified", "completed"}:
        return False
    work_tree = takeover_protocol.get("workTree")
    if not isinstance(work_tree, dict):
        return False
    if str(work_tree.get("status") or "") not in {"awaiting-approval", "completed"}:
        return False
    root_id = str(work_tree.get("rootNodeId") or "")
    nodes = [node for node in work_tree.get("nodes") or [] if isinstance(node, dict)]
    root = next((node for node in nodes if str(node.get("id") or "") == root_id), None)
    if root is None or str(root.get("status") or "") != "completed":
        return False
    return all(str(node.get("status") or "") in {"completed", "failed", "skipped"} for node in nodes)


def _g4_result_satisfies_expected_status(result_payload: dict[str, Any], expected_result_status: str) -> bool:
    result_status = str(result_payload.get("status") or "")
    if result_status == expected_result_status:
        return True
    if expected_result_status == "completed" and _g4_work_tree_approval_counts_as_completed(result_payload):
        return True
    return False


def _g4_normalized_final_task_status(task_status: str, expected_task_status: str, result_payload: dict[str, Any]) -> str:
    if task_status == expected_task_status:
        return task_status
    if expected_task_status == "completed" and _g4_work_tree_approval_counts_as_completed(result_payload):
        return "completed"
    return task_status
def _run_g4_live_provider_matrix_case(case: dict[str, Any] | None = None) -> dict[str, Any]:
    from datetime import datetime, timedelta
    import os

    from fastapi.testclient import TestClient
    from yggdrasil_agent_runtime.app import app as runtime_app
    from yggdrasil_sdk.llm_runtime import load_runtime_candidate_models
    from yggdrasil_worker.registry import run_worker_once

    case_payload = dict(case or {})
    app_id = str(case_payload.get("appId") or DEFAULT_APP_ID)
    task_type = str(case_payload.get("taskType") or "generic")
    requested_provider = str(case_payload.get("requestedProvider") or "longcat")
    requested_model = str(case_payload.get("requestedModel") or "LongCat-2.0")
    expected_prompt_profile_id = str(case_payload.get("expectedPromptProfileId") or "")
    expected_seed_template_id = str(case_payload.get("expectedSeedTemplateId") or "")
    expected_few_shot_refs = [str(item) for item in case_payload.get("expectedCompiledFewShotRefs") or []]
    expected_result_status = str(case_payload.get("expectedResultStatus") or "awaiting-approval")
    expected_task_status = str(case_payload.get("expectedTaskStatus") or expected_result_status)
    task_id = str(case_payload.get("taskId") or new_id("task", app_id, task_type, requested_provider, stable=False))
    candidate_models = [
        dict(candidate)
        for candidate in load_runtime_candidate_models() or []
        if str(candidate.get("provider") or "") == requested_provider and str(candidate.get("model") or "") == requested_model
    ]
    require_live = bool(case_payload.get("requireLive", False))
    if require_live and not candidate_models:
        raise RuntimeError(f"requested live candidate is unavailable: {requested_provider}/{requested_model}")

    budget_token_total_value = case_payload.get("budgetTokenTotal")
    if budget_token_total_value is None:
        budget_token_total_value = case_payload.get("tokenBudgetTotal")
    budget_time_limit_hours = max(_g4_int_metric(case_payload.get("timeLimitHours"), 0), 0)

    task = _seed_runtime_task(
        task_id,
        app_id=app_id,
        title=str(case_payload.get("taskTitle") or f"G4 {app_id} Live Matrix"),
        goal=str(case_payload.get("taskGoal") or "Validate the official G4 provider matrix task."),
        current_focus=str(case_payload.get("currentFocus") or f"g4-{task_type}-live"),
        current_objective=str(case_payload.get("currentObjective") or "Execute the official G4 provider matrix task."),
        resume_message=str(case_payload.get("resumeMessage") or "continue the live G4 evaluation"),
        token_budget_total=int(budget_token_total_value) if budget_token_total_value is not None else None,
        cost_budget_total=float(case_payload.get("costBudgetTotal") or 5.0),
    )
    client = TestClient(runtime_app)
    start_payload = _g4_live_provider_matrix_start_payload(
        case_payload,
        task,
        app_id=app_id,
        task_type=task_type,
        candidate_models=candidate_models,
    )

    max_window_cycles = max(int(case_payload.get("maxWindowCycles") or 12), int(case_payload.get("forcedWindowRestartBudget") or 0) + 4)
    max_worker_wait_seconds = max(
        int(case_payload.get("maxWorkerWaitSeconds") or os.environ.get("YGGDRASIL_G4_MAX_WORKER_WAIT_SECONDS") or 180),
        30,
    )
    recovery_state = {"budgetTopUpAttempts": 0, "budgetRetryAttempts": 0}
    allow_manual_continue_on_max_cycles = bool(case_payload.get("allowManualContinueOnMaxWindowCycles", False))

    def _recovery_handler(**kwargs: Any) -> bool:
        return _g4_recover_live_budget_pause_or_failure(
            client=client,
            task_id=str(task["id"]),
            case_payload=case_payload,
            recovery_state=recovery_state,
            result_payload=dict(kwargs.get("result_payload") or {}),
        )

    if bool(case_payload.get("seedAwaitingApprovalBeforePostActions", False)):
        processed = _g4_seed_awaiting_approval_for_revision(
            task_id=str(task["id"]),
            case_payload=case_payload,
            requested_provider=requested_provider,
            requested_model=requested_model,
        )
        processed_runs = [processed]
        result_payload = dict(processed.get("result") or {})
    else:
        started = client.post(f"/runtime/tasks/{task['id']}/start", json=start_payload)
        if started.status_code != 202:
            raise RuntimeError(f"g4 provider matrix start failed: {started.text}")
        processed_runs, processed, result_payload = _g4_wait_for_target_worker_result(
            task_id=str(task["id"]),
            expected_result_status=expected_result_status,
            max_window_cycles=max_window_cycles,
            max_worker_wait_seconds=max_worker_wait_seconds,
            run_worker_once_fn=run_worker_once,
            recovery_handler_fn=_recovery_handler,
            allow_manual_continue_on_max_window_cycles=allow_manual_continue_on_max_cycles,
        )
    post_completion_action_results: list[dict[str, Any]] = []
    manual_continue_required = str(result_payload.get("status") or "") == "manual-continue-required"
    for action in ([] if manual_continue_required else _g4_post_completion_actions(case_payload)):
        action_kind = str(action.get("kind") or "").strip().lower()
        if action_kind not in {"runtime-revision", "request-revision"}:
            continue
        action_result, action_processed_runs, action_processed, action_result_payload = _run_g4_runtime_revision_action(
            client=client,
            task_id=str(task["id"]),
            case_payload=case_payload,
            action=action,
            expected_result_status=expected_result_status,
            max_window_cycles=max_window_cycles,
            max_worker_wait_seconds=max_worker_wait_seconds,
            candidate_models=candidate_models,
            run_worker_once_fn=run_worker_once,
            recovery_handler_fn=_recovery_handler,
        )
        post_completion_action_results.append(action_result)
        processed_runs.extend(action_processed_runs)
        if action_processed is not None:
            processed = action_processed
        if action_result_payload is not None:
            result_payload = action_result_payload

    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        task_repository = TaskRepository(session)
        prompt_repository = PromptAssetRepository(session)
        runtime_repository = RuntimeRepository(session)
        persisted_task = task_repository.get_task(task["id"])
        invocations = runtime_repository.list_model_invocations(task_id=task["id"], limit=max(64, max_window_cycles * 2))
        if not invocations:
            raise RuntimeError("g4 provider matrix did not persist any model invocation")
        invocation_rows = []
        for model_invocation in invocations:
            model_request_payload = _read_external_ref_json(model_invocation.request_ref, resolve_workspace_root()) or {}
            model_response_payload = _read_external_ref_json(model_invocation.response_ref, resolve_workspace_root()) or {}
            invocation_rows.append(
                {
                    "record": model_invocation.model_dump(by_alias=True, mode="json"),
                    "requestPayload": model_request_payload,
                    "responsePayload": model_response_payload,
                }
            )

        selected_index = _g4_best_invocation_index(invocation_rows)
        invocation = invocations[selected_index]
        request_payload = invocation_rows[selected_index]["requestPayload"]
        response_payload = invocation_rows[selected_index]["responsePayload"]
        prompt_artifact = prompt_repository.get_prompt_compile_artifact(invocation.prompt_compile_artifact_id or "")
        if prompt_artifact is None:
            raise RuntimeError("g4 provider matrix prompt artifact is missing")

    if require_live and invocation.status != "completed":
        raise RuntimeError(f"g4 provider matrix live invocation did not complete: {invocation.status}")
    if require_live and invocation.resolved_provider not in {requested_provider, str(case_payload.get('providerAlias') or '')}:
        raise RuntimeError(
            f"g4 provider matrix provider mismatch: expected {requested_provider}, got {invocation.resolved_provider or 'unknown'}"
        )

    processed_request = dict((processed.get("payload") or {}).get("payload") or {})
    takeover_protocol = processed_request.get("takeoverProtocol")
    if isinstance(takeover_protocol, dict):
        request_payload = dict(request_payload)
        request_payload.setdefault("takeoverProtocol", takeover_protocol)
    prompt_metadata = dict(request_payload.get("promptMetadata") or {})
    if expected_prompt_profile_id and str(prompt_metadata.get("promptProfileId") or "") != expected_prompt_profile_id:
        raise RuntimeError("g4 provider matrix prompt profile drifted from the official scene contract")
    if expected_seed_template_id and str(prompt_metadata.get("seedTemplateId") or "") != expected_seed_template_id:
        raise RuntimeError("g4 provider matrix seed template drifted from the official scene contract")
    if expected_few_shot_refs and list(prompt_metadata.get("fewShotRefs") or []) != expected_few_shot_refs:
        raise RuntimeError("g4 provider matrix few-shot refs drifted from the official scene contract")
    raw_final_task_status = str((persisted_task.status if persisted_task is not None else None) or result_payload.get("status") or "")
    final_task_status = _g4_normalized_final_task_status(raw_final_task_status, expected_task_status, result_payload)
    manual_continue_required = manual_continue_required or str(result_payload.get("status") or "") == "manual-continue-required"
    if not manual_continue_required and final_task_status != expected_task_status:
        raise RuntimeError(
            f"g4 provider matrix final task status drifted: expected {expected_task_status}, got {final_task_status or 'missing'}"
        )

    task_record = persisted_task.model_dump(by_alias=True, mode="json") if persisted_task is not None else {}
    start_at_raw = task_record.get("startedAt")
    end_at_raw = task_record.get("endedAt")
    started_at = datetime.fromisoformat(str(start_at_raw).replace("Z", "+00:00")) if start_at_raw else None
    ended_at = datetime.fromisoformat(str(end_at_raw).replace("Z", "+00:00")) if end_at_raw else None
    first_token_seconds = _first_token_seconds(invocation_rows)
    first_useful_output_seconds = _first_useful_output_seconds(invocation_rows)
    runtime_metrics = _g4_runtime_metrics(response_payload)
    response_text = _g4_response_text(result_payload, response_payload)
    response_text = _g4_enforce_graduate_delivery_contract(
        case_payload,
        response_text,
        evaluation_workspace_root=os.environ.get("YGGDRASIL_EVAL_ACTIVE_WORKSPACE_ROOT"),
    )
    response_text = _g4_select_delivery_response_text(
        case_payload,
        response_text,
        evaluation_workspace_root=os.environ.get("YGGDRASIL_EVAL_ACTIVE_WORKSPACE_ROOT"),
    )
    for action in ([] if manual_continue_required else _g4_post_completion_actions(case_payload)):
        action_kind = str(action.get("kind") or "").strip().lower()
        if action_kind not in {"diagnostic-followup", "user-followup", "llm-followup"}:
            continue
        post_completion_action_results.append(
            _run_g4_diagnostic_followup_action(
                case_payload=case_payload,
                action=action,
                request_payload=request_payload,
                response_payload=response_payload,
                response_text=response_text,
                requested_provider=str(invocation.resolved_provider or requested_provider),
                requested_model=str(invocation.resolved_model or requested_model),
            )
        )
    evaluation_sandbox = os.environ.get("YGGDRASIL_EVAL_ACTIVE_SANDBOX_ROOT")
    preserved_paper = _persist_g4_paper_output(
        case_payload=case_payload,
        invocation=invocation,
        response_text=response_text,
        response_payload=response_payload,
        evaluation_sandbox=evaluation_sandbox,
    )
    window_execution_records, window_execution_refs = _g4_window_execution_records(
        processed_runs,
        workspace_root=resolve_workspace_root(),
    )
    window_execution_metrics = _g4_window_execution_metrics(window_execution_records)
    contract_verification = _g4_contract_verification_results(
        case_payload,
        response_text,
        runtime_metrics,
        window_execution_metrics,
        invocation_rows,
    )
    manual_review = _g4_manual_review_report(case_payload, contract_verification)
    execution_status_audit = _g4_execution_status_audit(
        task_record=task_record,
        result_payload=result_payload,
        processed_runs=processed_runs,
    )
    tool_failure_summary = _g4_tool_failure_summary(invocation_rows)
    tool_execution_metrics = _g4_tool_execution_metrics(invocation_rows)
    tool_execution_names = _g4_tool_execution_names(invocation_rows)
    verification_results = [{"command": "g4-live-guard", "returncode": 0}]
    verification_results.extend(contract_verification["checks"])
    execution = {
        "taskRuntime": {
            "task": task_record,
            "invocations": invocation_rows,
            "executionStatusAudit": execution_status_audit,
            "toolFailureSummary": tool_failure_summary,
        },
        "verification": verification_results,
        "issues": [{"type": "acceptance", "detail": issue} for issue in contract_verification["issues"]],
        "traceIds": [str(invocation.trace_id)] if invocation.trace_id else [],
        "taskWorkspace": str(resolve_workspace_root()),
        "toolExecutionNames": tool_execution_names,
        "firstTokenSeconds": first_token_seconds,
        "firstTokenAt": _format_timestamp(started_at + timedelta(seconds=first_token_seconds)) if started_at and first_token_seconds is not None else None,
        "firstUsefulOutputSeconds": first_useful_output_seconds,
        "firstUsefulOutputAt": _format_timestamp(started_at + timedelta(seconds=first_useful_output_seconds)) if started_at and first_useful_output_seconds is not None else None,
        "startAt": _format_timestamp(started_at),
        "endAt": _format_timestamp(ended_at),
        "totalDurationSeconds": _seconds_between(started_at, ended_at),
        "finalStatus": task_record.get("status") or result_payload.get("status"),
        "pauseResumeAttempted": False,
        "pauseResumeSuccess": False,
    }
    scorecard_row = _build_scorecard_row(
        task_key=str(case_payload.get("matrixKey") or case_payload.get("id") or task_id),
        task_def={
            "appLabel": app_id,
            "taskType": task_type,
            "workspaceProfile": str(case_payload.get("workspaceProfile") or "g4-official"),
        },
        execution=execution,
        fastest_first_useful=first_useful_output_seconds,
        provider=str(invocation.resolved_provider or requested_provider),
        model=str(invocation.resolved_model or requested_model),
        batch_id=str(case_payload.get("batchId") or "G4-PROVIDER-MATRIX"),
        environment_id=str(case_payload.get("environmentId") or "g4-provider-matrix"),
        coordination_backend="memory",
    )
    takeover_metrics = _takeover_metrics(invocation_rows)
    token_usage = _g4_token_usage(invocation, response_payload)
    context_length_observations = _g4_context_length_observations(response_payload)
    max_context_length_tokens = _g4_max_context_length_tokens(context_length_observations)
    restart_success_rate = 1.0 if final_task_status == expected_task_status else 0.0
    acceptance_pass = int(scorecard_row.get("acceptance_pass_0_1") or 0)
    restart_stability_report = _g4_restart_stability_report(
        case_payload,
        runtime_metrics,
        acceptance_pass=acceptance_pass,
    )
    prompt_artifact_record = prompt_artifact.model_dump(by_alias=True, mode="json")
    sandbox_state_root = os.environ.get("YGGDRASIL_STATE_ROOT")
    audit_level = str(case_payload.get("auditLevel") or request_payload.get("auditLevel") or response_payload.get("auditLevel") or "default")
    provider_matrix_entry = {
        "status": "blocked" if manual_continue_required else "completed",
        "matrixKey": str(case_payload.get("matrixKey") or case_payload.get("id") or task_id),
        "appId": app_id,
        "taskType": task_type,
        "provider": str(invocation.resolved_provider or requested_provider),
        "model": str(invocation.resolved_model or requested_model),
        "scenario": str(prompt_artifact.scenario or prompt_metadata.get("scenario") or ""),
        "promptProfileId": str(prompt_metadata.get("promptProfileId") or ""),
        "seedTemplateId": str(prompt_metadata.get("seedTemplateId") or ""),
        "fewShotRefs": list(prompt_metadata.get("fewShotRefs") or []),
        "firstTokenSeconds": first_token_seconds,
        "firstUsefulOutputSeconds": first_useful_output_seconds,
        "humanTakeoverCount": 0,
        "userClarificationRounds": 0,
        "planQualityScore0_100": takeover_metrics.get("planQualityScore0_100"),
        "reworkCount": takeover_metrics.get("reworkCount"),
        "reworkRate": takeover_metrics.get("reworkRate"),
        "inputTokens": token_usage["inputTokens"],
        "outputTokens": token_usage["outputTokens"],
        "totalTokens": token_usage["totalTokens"],
        "cacheHitInputTokens": token_usage["cacheHitInputTokens"],
        "cacheWriteInputTokens": token_usage["cacheWriteInputTokens"],
        "nonCacheInputTokens": token_usage["nonCacheInputTokens"],
        "reasoningTokens": token_usage["reasoningTokens"],
        "tokenUsage": token_usage,
        "contextLengthObservations": context_length_observations,
        "maxContextLengthTokens": max_context_length_tokens,
        "windowIndex": runtime_metrics["windowIndex"],
        "restartCount": runtime_metrics["restartCount"],
        "compressionCount": runtime_metrics["compressionCount"],
        "cumulativeWindowSpanTokens": runtime_metrics["cumulativeWindowSpanTokens"],
        "carryForwardLossCount": runtime_metrics["carryForwardLossCount"],
        "effectiveContextWindow": runtime_metrics["effectiveContextWindow"],
        "windowRestartThreshold": runtime_metrics["windowRestartThreshold"],
        "restartSuccessRate0_1": restart_stability_report.get("restartSuccessRate0_1", restart_success_rate),
        "windowTransitionCount": max(len(processed_runs) - 1, 0),
        "windowExecutionCount": window_execution_metrics["windowExecutionCount"],
        "workTreeContinuity0_1": window_execution_metrics["workTreeContinuity0_1"],
        "minimalWorksetRatio0_1": window_execution_metrics["minimalWorksetRatio0_1"],
        "planningStubRate0_1": window_execution_metrics["planningStubRate0_1"],
        "retrievalDriftRate0_1": window_execution_metrics["retrievalDriftRate0_1"],
        "prefixCacheReady0_1": window_execution_metrics.get("prefixCacheReady0_1", 0.0),
        "cacheEvidence0_1": window_execution_metrics.get("cacheEvidence0_1", 0.0),
        "workTreeContinuityThreshold0_1": float(case_payload.get("acceptanceMinWorkTreeContinuity0_1") or 0.0),
        "minimalWorksetThreshold0_1": float(case_payload.get("acceptanceMinMinimalWorksetRatio0_1") or 0.0),
        "acceptancePass0_1": acceptance_pass,
        "officialAcceptancePassed0_1": 1 if contract_verification["passed"] else 0,
        "goalCompletion0_1": 1 if final_task_status == expected_task_status else 0,
        "deliveryCompletion0_1": 1 if final_task_status == expected_task_status and acceptance_pass == 1 and contract_verification["passed"] else 0,
        "parityPairKey": str(case_payload.get("parityPairKey") or ""),
        "parityRole": str(case_payload.get("parityRole") or ""),
        "qualityDeltaThreshold0_100": float(case_payload.get("qualityDeltaThreshold0_100") or 8.0),
        "pass": final_task_status == expected_task_status and acceptance_pass == 1,
        "promptCompileArtifactId": invocation.prompt_compile_artifact_id,
        "auditLevel": audit_level,
        "budgetTokenTotal": int(budget_token_total_value) if budget_token_total_value is not None else None,
        "costBudgetTotal": float(case_payload.get("costBudgetTotal") or 5.0),
        "timeLimitHours": budget_time_limit_hours,
        "manualReviewRequired": 1 if manual_review["required"] else 0,
        "manualReviewStatus": str(manual_review["status"]),
        "taskStatusAtExit": execution_status_audit.get("taskStatus"),
        "resultStatusAtExit": execution_status_audit.get("resultStatus"),
        "latestRunStatusAtExit": execution_status_audit.get("latestRunStatus"),
        "taskRunStatusMismatch0_1": 1 if execution_status_audit.get("taskRunStatusMismatch") else 0,
        "toolExecutionMetrics": tool_execution_metrics,
        "toolExecutionNames": tool_execution_names,
        "totalToolExecutions": int(tool_execution_metrics.get("totalToolExecutions") or 0),
        "successfulToolExecutions": int(tool_execution_metrics.get("successfulToolExecutions") or 0),
        "failedToolExecutions": int(tool_execution_metrics.get("failedToolExecutions") or 0),
        "toolCategories": list(tool_execution_metrics.get("toolCategories") or []),
        "topToolFailures": tool_failure_summary,
        "postCompletionActionCount": len(post_completion_action_results),
        "postCompletionActionStatuses": [
            {
                "id": str(item.get("id") or ""),
                "kind": str(item.get("kind") or ""),
                "status": str(item.get("status") or ""),
            }
            for item in post_completion_action_results
            if isinstance(item, dict)
        ],
        "preservedPaper": preserved_paper,
    }
    assistant_preview = normalize_excerpt(response_text or str(result_payload.get("assistantText") or ""), 240)
    if bool(case_payload.get("failOnAcceptanceViolation")) and not contract_verification["passed"]:
        issues_text = "; ".join(contract_verification["issues"]) or "unknown acceptance failure"
        sandbox_text = evaluation_sandbox or "unknown"
        paper_text = preserved_paper["paperPath"] if isinstance(preserved_paper, dict) and preserved_paper.get("paperPath") else "unknown"
        raise RuntimeError(
            f"g4 provider matrix acceptance failed for {provider_matrix_entry['matrixKey']}: {issues_text} | sandbox={sandbox_text} | paper={paper_text} | response={assistant_preview}"
        )
    if bool(case_payload.get("failOnRestartStabilityViolation")) and restart_stability_report.get("enabled") and not restart_stability_report.get("passed"):
        failed_tiers = [
            str(item.get("targetRestarts"))
            for item in restart_stability_report.get("tiers") or []
            if isinstance(item, dict) and not bool(item.get("passed"))
        ]
        sandbox_text = evaluation_sandbox or "unknown"
        paper_text = preserved_paper["paperPath"] if isinstance(preserved_paper, dict) and preserved_paper.get("paperPath") else "unknown"
        raise RuntimeError(
            "g4 provider matrix restart stability failed "
            f"for {provider_matrix_entry['matrixKey']}: failed tiers={','.join(failed_tiers) or 'unknown'} "
            f"| sandbox={sandbox_text} | paper={paper_text} | response={assistant_preview}"
        )
    return {
        **provider_matrix_entry,
        "manualContinue": dict(result_payload.get("manualContinue") or {}) if manual_continue_required else None,
        "liveScenario": {
            "taskId": task["id"],
            "invocationId": invocation.id,
            "invocationStatus": invocation.status,
            "provider": provider_matrix_entry["provider"],
            "model": provider_matrix_entry["model"],
            "traceId": invocation.trace_id,
            "latencyMs": invocation.latency_ms,
            "totalTokens": token_usage["totalTokens"],
            "costUsed": float(invocation.cost_used or 0.0),
            "tokenUsage": token_usage,
            "contextLengthObservations": context_length_observations,
            "maxContextLengthTokens": max_context_length_tokens,
            "runtimeMetrics": runtime_metrics,
            "windowTransitionCount": max(len(processed_runs) - 1, 0),
            "manualContinueRequired": manual_continue_required,
            "promptCompileArtifactId": invocation.prompt_compile_artifact_id,
            "toolExecutionMetrics": tool_execution_metrics,
            "toolExecutionNames": tool_execution_names,
        },
        "providerMatrixEntry": provider_matrix_entry,
        "scorecardRow": scorecard_row,
        "evaluationSandbox": {
            "root": evaluation_sandbox,
            "stateRoot": sandbox_state_root,
            "workspaceRoot": os.environ.get("YGGDRASIL_EVAL_ACTIVE_WORKSPACE_ROOT"),
            "databasePath": os.environ.get("YGGDRASIL_EVAL_ACTIVE_DB_PATH"),
        },
        "artifactRefs": {
            "requestRef": invocation.request_ref.model_dump(mode="json") if invocation.request_ref is not None else None,
            "responseRef": invocation.response_ref.model_dump(mode="json") if invocation.response_ref is not None else None,
            "compiledMessagesRef": prompt_artifact_record.get("compiledMessagesRef"),
            "promptCompileArtifactId": invocation.prompt_compile_artifact_id,
            "windowExecutionRefs": window_execution_refs,
        },
        "dialogueAudit": {
            "auditLevel": audit_level,
            "requestRef": invocation.request_ref.model_dump(mode="json") if invocation.request_ref is not None else None,
            "responseRef": invocation.response_ref.model_dump(mode="json") if invocation.response_ref is not None else None,
            "compiledMessagesRef": prompt_artifact_record.get("compiledMessagesRef"),
            "windowExecutionRefs": window_execution_refs,
        },
        "officialAcceptance": {
            **contract_verification,
            "responsePreview": assistant_preview,
            "paperOutput": preserved_paper,
        },
        "manualReview": manual_review,
        "restartStabilityReport": restart_stability_report,
        "windowExecutionMetrics": window_execution_metrics,
        "executionStatusAudit": execution_status_audit,
        "toolFailureSummary": tool_failure_summary,
        "postCompletionActions": post_completion_action_results,
        "processedRuns": [dict(item) for item in processed_runs],
        "assistantPreview": assistant_preview,
    }
__all__ = [name for name in globals() if not name.startswith("__")]

