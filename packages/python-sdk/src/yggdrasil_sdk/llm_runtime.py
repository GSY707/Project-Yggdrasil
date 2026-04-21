from __future__ import annotations

from hashlib import sha1
import json
from pathlib import Path
from time import perf_counter
from typing import Any

from .contracts import ExternalRef
from .domain import PromptProfileVersionRecord, SeedTemplateVersionRecord
from .observability_exporters import finish_langfuse_generation
from .observability_exporters import start_langfuse_generation
from .observability import observe_span, record_log, record_metric
from .persistence import PromptAssetRepository, RuntimeRepository
from .prompting import compile_runtime_prompt, get_prompt_profile_definition, get_seed_template_definition
from .support import ensure_state_subdir, new_id, normalize_excerpt, relative_workspace_path, resolve_workspace_root, utc_now, write_json
from .tool_runtime import build_llm_tool_specs, execute_registered_tool, tool_result_to_message_content


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


def _merge_usage(total: dict[str, int], usage: dict[str, Any]) -> dict[str, int]:
    total["inputTokens"] += int(usage.get("inputTokens", 0) or 0)
    total["outputTokens"] += int(usage.get("outputTokens", 0) or 0)
    total["totalTokens"] += int(usage.get("totalTokens", 0) or 0)
    return total


def _persist_prompt_assets(
    session,
    *,
    task: Any,
    run: Any,
    invocation_id: str,
    compiled_prompt,
    workspace_root: Path,
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
    write_json(
        compiled_messages_path,
        {
            "appId": compiled_prompt.app_id,
            "modelInvocationId": invocation_id,
            "prompt": compiled_prompt.model_dump(by_alias=True, mode="json", exclude={"messages"}),
            "messages": compiled_prompt.messages,
        },
    )
    compiled_messages_ref = _invocation_file_ref(compiled_messages_path, workspace_root)
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
    compiled_prompt = compile_runtime_prompt(
        task=task,
        run_type=run_type,
        task_type=task_type,
        root_mount=root_mount,
        current_context=current_context,
        request=request,
        resume_path=resume_path,
    )
    messages: list[dict[str, Any]] = [dict(message) for message in compiled_prompt.messages]
    temperature = float(request.get("temperature")) if request.get("temperature") is not None else _default_temperature(task_type)
    max_tokens = _default_max_tokens(task, request)
    allow_fallback = bool(request.get("allowModelFallback", True))
    allow_tool_execution = bool(request.get("allowToolExecution", True))
    tool_specs = build_llm_tool_specs(compiled_prompt.registered_tools) if allow_tool_execution else []
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

    prompt_artifact = _persist_prompt_assets(
        session,
        task=task,
        run=run,
        invocation_id=invocation.id,
        compiled_prompt=compiled_prompt,
        workspace_root=workspace_root,
    )
    invocation = runtime_repository.update_model_invocation(
        invocation.id,
        {"promptCompileArtifactId": prompt_artifact.id},
    )

    request_path = ensure_state_subdir("llm/requests", workspace_root) / f"{invocation.id}.json"
    write_json(
        request_path,
        {
            "appId": getattr(task, "app_id", None),
            "invocationId": invocation.id,
            "taskId": task.id,
            "agentRunId": run.id,
            "requestedModel": route_payload.get("selectedModel"),
            "requestedProvider": route_payload.get("selectedProvider"),
            "temperature": temperature,
            "maxTokens": max_tokens,
            "promptCompileArtifactId": prompt_artifact.id,
            "promptMetadata": compiled_prompt.model_dump(by_alias=True, mode="json", exclude={"messages"}),
            "messages": messages,
            "tools": tool_specs,
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
                    "tools": tool_specs,
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
                    "runType": run_type,
                    "promptProfileId": compiled_prompt.prompt_profile_id,
                    "seedTemplateId": compiled_prompt.seed_template_id,
                    "promptScenario": compiled_prompt.scenario,
                },
            )
            conversation_messages = [dict(message) for message in messages]
            usage_totals = {"inputTokens": 0, "outputTokens": 0, "totalTokens": 0}
            accumulated_cost = 0.0
            tool_executions: list[dict[str, Any]] = []
            round_summaries: list[dict[str, Any]] = []
            round_modes: list[str] = []
            final_result: dict[str, Any] | None = None

            for round_index in range(max_tool_rounds + 1):
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
                    )

                _merge_usage(usage_totals, dict(result.get("usage") or {}))
                accumulated_cost += float(result.get("costUsed", 0.0) or 0.0)
                round_modes.append(str(result.get("mode") or "unknown"))
                tool_calls = [call for call in result.get("toolCalls") or [] if isinstance(call, dict) and call.get("name")]
                round_summaries.append(
                    {
                        "index": round_index,
                        "mode": result.get("mode"),
                        "finishReason": result.get("finishReason"),
                        "toolCalls": [str(call.get("name")) for call in tool_calls],
                    }
                )
                if not tool_calls:
                    final_result = result
                    break
                if round_index >= max_tool_rounds:
                    raise RuntimeError(f"Tool round limit exceeded for invocation {invocation.id}.")

                assistant_tool_calls = [
                    {
                        "id": str(call.get("id") or new_id("toolcall", call.get("name"), round_index)),
                        "type": "function",
                        "function": {
                            "name": str(call.get("name")),
                            "arguments": str(call.get("argumentsText") or json.dumps(call.get("arguments") or {}, ensure_ascii=False)),
                        },
                    }
                    for call in tool_calls
                ]
                conversation_messages.append(
                    {
                        "role": "assistant",
                        "content": str(result.get("outputText") or ""),
                        "tool_calls": assistant_tool_calls,
                    }
                )
                for call in tool_calls:
                    tool_call_id = str(call.get("id") or new_id("toolcall", call.get("name"), round_index))
                    try:
                        execution = execute_registered_tool(
                            str(call.get("name")),
                            call.get("arguments") if isinstance(call.get("arguments"), dict) else {},
                            task=task,
                            run=run,
                            root_mount=root_mount,
                            current_context=current_context,
                        )
                        execution["success"] = True
                    except Exception as exc:
                        execution = {
                            "tool": {"name": str(call.get("name"))},
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
                            "name": str(call.get("name")),
                            "content": tool_result_to_message_content(execution),
                        }
                    )

            if final_result is None:
                raise RuntimeError(f"Invocation {invocation.id} finished without a terminal model result.")

            write_json(
                request_path,
                {
                    "appId": getattr(task, "app_id", None),
                    "invocationId": invocation.id,
                    "taskId": task.id,
                    "agentRunId": run.id,
                    "requestedModel": route_payload.get("selectedModel"),
                    "requestedProvider": route_payload.get("selectedProvider"),
                    "temperature": temperature,
                    "maxTokens": max_tokens,
                    "promptCompileArtifactId": prompt_artifact.id,
                    "promptMetadata": compiled_prompt.model_dump(by_alias=True, mode="json", exclude={"messages"}),
                    "initialMessages": messages,
                    "messages": conversation_messages,
                    "tools": tool_specs,
                    "toolExecutions": tool_executions,
                    "rounds": round_summaries,
                },
            )

            latency_ms = round((perf_counter() - started_counter) * 1000.0, 2)
            response_path = ensure_state_subdir("llm/responses", workspace_root) / f"{invocation.id}.json"
            write_json(
                response_path,
                {
                    "appId": getattr(task, "app_id", None),
                    "invocationId": invocation.id,
                    "taskId": task.id,
                    "agentRunId": run.id,
                    "promptCompileArtifactId": prompt_artifact.id,
                    "mode": final_result.get("mode"),
                    "provider": final_result.get("provider"),
                    "model": final_result.get("model"),
                    "finishReason": final_result.get("finishReason"),
                    "usage": usage_totals,
                    "costUsed": accumulated_cost,
                    "error": final_result.get("error"),
                    "toolExecutions": tool_executions,
                    "rounds": round_summaries,
                    "rawResponse": final_result.get("rawResponse"),
                },
            )
            response_ref = _invocation_file_ref(response_path, workspace_root)
            all_live_rounds = bool(round_modes) and all(mode == "live" for mode in round_modes)
            final_status = "completed" if all_live_rounds else "fallback"
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
            return {
                "assistantText": str(final_result.get("outputText") or ""),
                "invocation": invocation.model_dump(by_alias=True, mode="json"),
                "prompt": compiled_prompt.model_dump(by_alias=True, mode="json", exclude={"messages"}),
                "promptArtifact": prompt_artifact.model_dump(by_alias=True, mode="json"),
                "toolExecutions": tool_executions,
                "usage": dict(usage_totals),
                "costUsed": float(accumulated_cost or 0.0),
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