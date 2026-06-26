from __future__ import annotations

from time import perf_counter
from typing import Any

from .artifacts import (
    _execute_resumed_tool_calls,
    _filter_tool_calls_by_allowed_names,
    _is_idempotent_tool_round,
    _normalize_tool_calls,
    _persist_prompt_assets,
    _request_file_payload,
    _resolve_tool_name_policy,
    _response_file_payload,
    _runtime_metrics_for_response,
    _assistant_tool_calls_payload,
    _to_serialized_messages,
    _tool_round_limit_result,
    _tool_round_signature,
    _upsert_task_conversation_record,
)
from .core import (
    FALLBACK_ROUTE_CANDIDATE,
    _DUPLICATE_TOOL_ROUND_THRESHOLD,
    _MAX_TOOL_RETRIES,
    _PENDING_TOOL_CALLS_KIND,
    RuntimeRepository,
    SafeShutdownInterrupt,
    _append_context_length_observation,
    _assistant_tool_round_message,
    _canonical_tool_name,
    _check_post_invocation_budget,
    _check_pre_invocation_budget,
    _default_max_tokens,
    _default_temperature,
    _elapsed_ms,
    _empty_usage_totals,
    _estimate_message_tokens,
    _estimated_input_tokens_for_precheck,
    _estimated_output_tokens_for_precheck,
    _execute_tool_with_isolation,
    _first_token_latency_ms_from_round_summaries,
    _invocation_file_ref,
    _local_fallback_result,
    _merge_usage,
    _normalize_route_decision,
    _requested_reasoning_effort,
    _requested_thinking_mode,
    _runtime_audit_level,
    _should_checkpoint_for_pause,
    _tool_name_alias_map,
    build_llm_tool_specs,
    compile_runtime_prompt,
    ensure_state_subdir,
    finish_langfuse_generation,
    new_id,
    observe_span,
    record_log,
    record_metric,
    resolve_workspace_root,
    start_langfuse_generation,
    tool_result_to_message_content,
    utc_now,
    write_json,
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
    response_runtime_metrics = _runtime_metrics_for_response(task, request)
    allow_fallback = bool(request.get("allowModelFallback", True))
    allow_tool_execution = bool(request.get("allowToolExecution", True))
    all_registered_tools_by_name = {
        str(tool.get("name") or ""): dict(tool)
        for tool in compiled_prompt.registered_tools
        if isinstance(tool, dict) and tool.get("name")
    }
    tool_name_policy = _resolve_tool_name_policy(request, all_registered_tools_by_name)
    allowed_tool_names = set(tool_name_policy.get("allowedNames") or []) if allow_tool_execution else set()
    effective_registered_tools = [
        dict(tool)
        for tool in compiled_prompt.registered_tools
        if isinstance(tool, dict) and str(tool.get("name") or "") in allowed_tool_names
    ]
    build_tool_specs_started_at = perf_counter()
    tool_specs = build_llm_tool_specs(effective_registered_tools) if allow_tool_execution else []
    registered_tools_by_name = {
        str(tool.get("name") or ""): dict(tool)
        for tool in effective_registered_tools
        if isinstance(tool, dict) and tool.get("name")
    }
    tool_name_aliases = _tool_name_alias_map(registered_tools_by_name)
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
                    tool_name_aliases=tool_name_aliases,
                    allowed_tool_names=allowed_tool_names,
                )
                round_summaries.append({
                    "index": _resume_starting_round - 1,
                    "mode": "checkpoint-resume",
                    "finishReason": "tool-execution-resumed",
                    "latencyMs": _elapsed_ms(_resume_round_started_at),
                    "toolCalls": [
                        _canonical_tool_name(c.get("name"), tool_name_aliases)
                        for c in _resume_tool_calls
                        if isinstance(c, dict)
                    ],
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
                raw_message_tokens = _estimate_message_tokens(conversation_messages)
                estimated_input_tokens = _estimated_input_tokens_for_precheck(
                    raw_message_tokens=raw_message_tokens,
                    max_tokens=max(1, int(max_tokens)),
                    request=request,
                )
                estimated_output_tokens = _estimated_output_tokens_for_precheck(
                    max_tokens=max(1, int(max_tokens)),
                    request=request,
                )
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
                raw_tool_calls = [call for call in result.get("toolCalls") or [] if isinstance(call, dict) and call.get("name")]
                ignored_tool_calls = [str(call.get("name")) for call in raw_tool_calls] if not allow_tool_execution else []
                if not allow_tool_execution:
                    raw_tool_calls = []
                tool_calls = _normalize_tool_calls(raw_tool_calls, tool_name_aliases)
                tool_calls, blocked_tool_calls = _filter_tool_calls_by_allowed_names(tool_calls, allowed_tool_names)
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
                        "ignoredToolCalls": ignored_tool_calls,
                        "blockedToolCalls": blocked_tool_calls,
                        "duplicateToolRoundStreak": duplicate_tool_round_streak,
                        "budgetCheckResult": budget_check_result,
                        "budgetOverrunResult": budget_overrun_result,
                    }
                )
                if blocked_tool_calls:
                    conversation_messages.append(
                        {
                            "role": "system",
                            "content": (
                                "Tool-name policy blocked tool calls in this round: "
                                + ", ".join(sorted(set(blocked_tool_calls)))
                                + ". Continue using allowed tools only."
                            ),
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
                    round_summaries[-1]["finishReason"] = "duplicate-tool-loop-blocked-continue"
                    round_summaries[-1]["duplicateToolRoundBlocked"] = True
                    conversation_messages.append(
                        {
                            "role": "system",
                            "content": (
                                "Duplicate idempotent tool loop detected. Do not call any tools in the next response. "
                                "Use already collected evidence and produce the final Markdown delivery now. "
                                "Must include: comparison matrix, contradiction resolution, source table, and the four headings "
                                "## 结果 / ## 证据 / ## 风险 / ## 已知问题."
                            ),
                        }
                    )
                    final_round_started_at = perf_counter()
                    if invoke_model is None:
                        final_result = _local_fallback_result(conversation_messages, route_payload)
                    else:
                        final_result = invoke_model(
                            requested_model=str(route_payload.get("selectedModel")) if route_payload.get("selectedModel") is not None else None,
                            requested_provider=str(route_payload.get("selectedProvider")) if route_payload.get("selectedProvider") is not None else None,
                            messages=conversation_messages,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            workspace_root=workspace_root,
                            allow_fallback=allow_fallback,
                            tools=None,
                            thinking=thinking_mode,
                            reasoning_effort=reasoning_effort,
                        )
                    _merge_usage(usage_totals, dict(final_result.get("usage") or {}))
                    accumulated_cost += float(final_result.get("costUsed", 0.0) or 0.0)
                    round_modes.append(str(final_result.get("mode") or "unknown"))
                    round_summaries.append(
                        {
                            "index": round_index + 1,
                            "mode": final_result.get("mode"),
                            "finishReason": str(final_result.get("finishReason") or "forced-final-delivery-after-duplicate-loop"),
                            "latencyMs": _elapsed_ms(final_round_started_at),
                            "toolCalls": [],
                            "forcedNoToolRound": True,
                        }
                    )
                    break
                if round_index >= max_tool_rounds:
                    round_summaries[-1]["finishReason"] = "tool-round-limit-short-circuit"
                    round_summaries[-1]["toolRoundLimitShortCircuited"] = True
                    final_result = _tool_round_limit_result(result, invocation.id, max_tool_rounds=max_tool_rounds)
                    break

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
                        tool_descriptor=registered_tools_by_name.get(str(call.get("name") or "")),
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
                    requested_tool_name = str(call.get("requestedName") or "").strip()
                    if requested_tool_name:
                        execution["tool"]["requestedName"] = requested_tool_name
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
                runtime_metrics=response_runtime_metrics,
            )
            write_response_started_at = perf_counter()
            write_json(response_path, response_payload)
            local_runtime_timings["writeResponseMs"] = _elapsed_ms(write_response_started_at)

            final_message = {
                "role": "assistant",
                "content": str(final_result.get("outputText") or ""),
            }
            invocation_entry = {
                "invocationId": invocation.id,
                "taskId": task.id,
                "agentRunId": run.id,
                "promptCompileArtifactId": prompt_artifact.id,
                "status": invocation.status,
                "requestedModel": route_payload.get("selectedModel"),
                "requestedProvider": route_payload.get("selectedProvider"),
                "resolvedModel": invocation.resolved_model,
                "resolvedProvider": invocation.resolved_provider,
                "windowIndex": response_runtime_metrics.get("windowIndex"),
                "restartCount": response_runtime_metrics.get("restartCount"),
                "cumulativeWindowSpanTokens": response_runtime_metrics.get("cumulativeWindowSpanTokens"),
                "contextLengthObservations": [dict(item) for item in context_length_observations if isinstance(item, dict)],
                "messages": _to_serialized_messages(messages),
                "conversationMessages": _to_serialized_messages([*conversation_messages, final_message]),
                "assistantText": str(final_result.get("outputText") or ""),
                "error": final_result.get("error"),
                "endedAt": utc_now().isoformat(),
            }
            _upsert_task_conversation_record(
                workspace_root=workspace_root,
                task_id=str(task.id),
                invocation_entry=invocation_entry,
            )

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
                "runtimeMetrics": dict(response_runtime_metrics),
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
        failure_runtime_metrics = response_runtime_metrics if "response_runtime_metrics" in locals() else _runtime_metrics_for_response(task, request)
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
                    runtime_metrics=failure_runtime_metrics,
                ),
            )
            local_runtime_timings["writeResponseMs"] = _elapsed_ms(write_response_started_at)

            failure_final_message = {
                "role": "assistant",
                "content": str(failure_result.get("outputText") or ""),
            }
            failure_entry = {
                "invocationId": invocation.id,
                "taskId": task.id,
                "agentRunId": run.id,
                "promptCompileArtifactId": str(failure_prompt_artifact_id or prompt_metadata.get("id") or ""),
                "status": "failed",
                "requestedModel": route_payload.get("selectedModel"),
                "requestedProvider": route_payload.get("selectedProvider"),
                "resolvedModel": route_payload.get("selectedModel"),
                "resolvedProvider": route_payload.get("selectedProvider"),
                "windowIndex": failure_runtime_metrics.get("windowIndex"),
                "restartCount": failure_runtime_metrics.get("restartCount"),
                "cumulativeWindowSpanTokens": failure_runtime_metrics.get("cumulativeWindowSpanTokens"),
                "contextLengthObservations": [
                    dict(item)
                    for item in failure_context_length_observations
                    if isinstance(item, dict)
                ],
                "messages": _to_serialized_messages(messages),
                "conversationMessages": _to_serialized_messages([*(failure_messages or []), failure_final_message]),
                "assistantText": str(failure_result.get("outputText") or ""),
                "error": str(exc),
                "endedAt": utc_now().isoformat(),
            }
            _upsert_task_conversation_record(
                workspace_root=workspace_root,
                task_id=str(task.id),
                invocation_entry=failure_entry,
            )
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

__all__ = [name for name in globals() if not name.startswith("__")]
