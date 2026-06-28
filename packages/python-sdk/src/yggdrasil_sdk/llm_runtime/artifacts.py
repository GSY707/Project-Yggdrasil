from __future__ import annotations

from .core import *  # noqa: F403,F401

def _normalize_tool_calls(
    tool_calls: list[dict[str, Any]],
    tool_name_aliases: dict[str, str] | None,
) -> list[dict[str, Any]]:
    normalized_calls: list[dict[str, Any]] = []
    for call in tool_calls:
        if not isinstance(call, dict) or not call.get("name"):
            continue
        normalized_call = dict(call)
        canonical_name = _canonical_tool_name(call.get("name"), tool_name_aliases)
        if canonical_name and canonical_name != str(call.get("name") or ""):
            normalized_call["requestedName"] = str(call.get("name") or "")
            normalized_call["name"] = canonical_name
        normalized_calls.append(normalized_call)
    return normalized_calls
def _normalize_tool_name_patterns(raw_patterns: Any) -> list[str]:
    if raw_patterns is None:
        return []
    if isinstance(raw_patterns, (str, bytes)):
        candidates = [raw_patterns]
    elif isinstance(raw_patterns, list):
        candidates = raw_patterns
    else:
        candidates = [raw_patterns]
    patterns: list[str] = []
    for item in candidates:
        pattern = str(item or "").strip()
        if pattern:
            patterns.append(pattern)
    return patterns
def _tool_name_matches_patterns(tool_name: str, patterns: list[str]) -> bool:
    normalized_name = str(tool_name or "").strip().lower()
    if not normalized_name or not patterns:
        return False
    for pattern in patterns:
        normalized_pattern = str(pattern or "").strip().lower()
        if not normalized_pattern:
            continue
        if fnmatch.fnmatch(normalized_name, normalized_pattern):
            return True
    return False
def _resolve_tool_name_policy(
    request: dict[str, Any],
    registered_tools_by_name: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    all_tool_names = sorted(name for name in registered_tools_by_name if str(name or "").strip())
    allow_patterns = _normalize_tool_name_patterns(request.get("toolNameAllowlist") if isinstance(request, dict) else None)
    deny_patterns = _normalize_tool_name_patterns(request.get("toolNameDenylist") if isinstance(request, dict) else None)

    allowed_names = set(all_tool_names)
    if allow_patterns:
        allowed_names = {
            name
            for name in allowed_names
            if _tool_name_matches_patterns(name, allow_patterns)
        }
    if deny_patterns:
        allowed_names = {
            name
            for name in allowed_names
            if not _tool_name_matches_patterns(name, deny_patterns)
        }

    return {
        "allowPatterns": allow_patterns,
        "denyPatterns": deny_patterns,
        "allowedNames": sorted(allowed_names),
        "blockedNames": sorted(name for name in all_tool_names if name not in allowed_names),
    }
def _filter_tool_calls_by_allowed_names(
    tool_calls: list[dict[str, Any]],
    allowed_names: set[str] | None,
) -> tuple[list[dict[str, Any]], list[str]]:
    if allowed_names is None:
        return list(tool_calls), []
    allowed: list[dict[str, Any]] = []
    blocked: list[str] = []
    for call in tool_calls:
        if not isinstance(call, dict):
            continue
        call_name = str(call.get("name") or "").strip()
        if not call_name:
            continue
        if call_name in allowed_names:
            allowed.append(call)
            continue
        blocked.append(call_name)
    return allowed, blocked
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
    tool_name_aliases: dict[str, str] | None = None,
    allowed_tool_names: set[str] | None = None,
) -> None:
    normalized_tool_calls = _normalize_tool_calls(tool_calls, tool_name_aliases)
    normalized_tool_calls, blocked_tool_calls = _filter_tool_calls_by_allowed_names(normalized_tool_calls, allowed_tool_names)
    assistant_tool_calls = _assistant_tool_calls_payload(normalized_tool_calls, "resume")
    if isinstance(assistant_message, dict):
        conversation_messages.append(dict(assistant_message))
    elif assistant_tool_calls:
        conversation_messages.append(_assistant_tool_round_message({}, assistant_tool_calls))
    for call in normalized_tool_calls:
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

    for blocked_name in blocked_tool_calls:
        tool_call_id = new_id("toolcall", blocked_name, "resume-blocked")
        execution = {
            "tool": {"name": blocked_name},
            "arguments": {},
            "result": {"status": "error", "error": f"Tool {blocked_name} is blocked by tool-name policy."},
            "success": False,
            "toolCallId": tool_call_id,
        }
        tool_executions.append(execution)
        conversation_messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "name": blocked_name,
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
            "检测到重复的幂等工具循环，已停止继续发起相同工具调用。"
            "此前轮次的工具输出与来源工件已保留在工作区；下一步应按当前任务目标决定，"
            "直接综合已有材料，或只做必要的非重复核查。"
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
def _tool_round_limit_result(result: dict[str, Any], invocation_id: str, *, max_tool_rounds: int) -> dict[str, Any]:
    return {
        "mode": result.get("mode") or "live",
        "provider": result.get("provider"),
        "model": result.get("model"),
        "outputText": (
            "已达到配置的工具轮次上限，本窗口停止继续调用工具。"
            "本轮工具执行轨迹和来源工件已保留；后续应按当前任务目标继续综合，"
            "或明确说明仍缺的任务相关证据。"
        ),
        "finishReason": "tool-round-limit-short-circuit",
        "usage": dict(result.get("usage") or {}),
        "costUsed": float(result.get("costUsed", 0.0) or 0.0),
        "error": None,
        "toolCalls": [],
        "rawResponse": {
            "status": "short-circuited",
            "reason": "tool-round-limit",
            "maxToolRounds": max_tool_rounds,
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
def _normalize_conversation_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            for key in ("text", "input_text", "output_text", "content"):
                value = item.get(key)
                if isinstance(value, str) and value.strip():
                    parts.append(value)
                    break
        return "\n".join(parts)
    return ""
def _to_serialized_messages(messages: list[dict[str, Any]]) -> list[dict[str, str]]:
    serialized: list[dict[str, str]] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        serialized.append(
            {
                "role": str(message.get("role") or "unknown"),
                "content": _normalize_conversation_content(message.get("content")),
            }
        )
    return serialized
def _safe_load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None
def _runtime_metrics_for_response(task: Any, request: dict[str, Any]) -> dict[str, Any]:
    request_metrics = request.get("runtimeMetrics") if isinstance(request.get("runtimeMetrics"), dict) else {}
    merged = dict(request_metrics)
    merged["windowIndex"] = max(int(merged.get("windowIndex") or 0), int(getattr(task, "window_index", 0) or 0))
    merged["restartCount"] = max(int(merged.get("restartCount") or 0), int(getattr(task, "restart_count", 0) or 0))
    merged["cumulativeWindowSpanTokens"] = max(
        int(merged.get("cumulativeWindowSpanTokens") or 0),
        int(getattr(task, "cumulative_window_span_tokens", 0) or 0),
    )
    merged["carryForwardLossCount"] = max(
        int(merged.get("carryForwardLossCount") or 0),
        int(getattr(task, "carry_forward_loss_count", 0) or 0),
    )
    return merged
def _upsert_task_conversation_record(
    *,
    workspace_root: Path,
    task_id: str,
    invocation_entry: dict[str, Any],
) -> None:
    now = utc_now().isoformat()

    state_dir = ensure_state_subdir("llm/task-conversations", workspace_root)
    state_record_path = state_dir / f"task_{task_id}.json"
    state_index_path = state_dir / "index.json"

    tmp_dir = workspace_root / "tmp" / "task-conversations" / "data"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_record_path = tmp_dir / f"task_{task_id}.json"
    tmp_index_path = tmp_dir / "index.json"

    for record_path, index_path in (
        (state_record_path, state_index_path),
        (tmp_record_path, tmp_index_path),
    ):
        record_payload = _safe_load_json(record_path) or {
            "taskId": task_id,
            "createdAt": now,
            "updatedAt": now,
            "invocations": [],
        }
        invocations = [
            item
            for item in (record_payload.get("invocations") or [])
            if isinstance(item, dict) and str(item.get("invocationId") or "") != str(invocation_entry.get("invocationId") or "")
        ]
        invocations.append(dict(invocation_entry))
        invocations.sort(
            key=lambda item: (
                int(item.get("windowIndex") or 0),
                str(item.get("endedAt") or ""),
                str(item.get("invocationId") or ""),
            )
        )
        record_payload["taskId"] = task_id
        record_payload["updatedAt"] = now
        record_payload["invocationCount"] = len(invocations)
        record_payload["invocations"] = invocations
        if invocations:
            latest = invocations[-1]
            record_payload["latestInvocationId"] = latest.get("invocationId")
            record_payload["latestWindowIndex"] = latest.get("windowIndex")
            record_payload["latestStatus"] = latest.get("status")
        write_json(record_path, record_payload)

        index_payload = _safe_load_json(index_path) or {"updatedAt": now, "tasks": []}
        tasks = [item for item in (index_payload.get("tasks") or []) if isinstance(item, dict)]
        task_items = [item for item in tasks if str(item.get("taskId") or "") != task_id]
        latest_entry = invocations[-1] if invocations else {}
        task_items.append(
            {
                "taskId": task_id,
                "recordPath": record_path.name,
                "invocationCount": len(invocations),
                "latestInvocationId": latest_entry.get("invocationId"),
                "latestWindowIndex": latest_entry.get("windowIndex"),
                "latestStatus": latest_entry.get("status"),
                "updatedAt": now,
            }
        )
        task_items.sort(key=lambda item: str(item.get("updatedAt") or ""), reverse=True)
        index_payload["updatedAt"] = now
        index_payload["tasks"] = task_items
        write_json(index_path, index_payload)
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
