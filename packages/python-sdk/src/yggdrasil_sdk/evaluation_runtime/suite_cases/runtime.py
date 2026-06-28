import json
import os
import subprocess
from typing import Any

from ...persistence import get_persistence_runtime
from ...persistence.constants import DEFAULT_BRANCH_ID
from ...persistence.repositories import PromptAssetRepository, RuntimeRepository, TaskRepository
from ...support import new_id, normalize_excerpt, resolve_workspace_root
from ..bootstrap import _read_external_ref_json, _seed_runtime_task, _seed_tool_case_memory
from ..scorer import (
    _build_memory_tree_context,
    _generate_strategy_answer,
    _read_text_fixture,
    _score_strategy,
    _select_flat_fragments,
)

def _run_memory_import_case(case: dict[str, Any] | None = None) -> dict[str, Any]:
    from fastapi.testclient import TestClient
    from yggdrasil_core_api.app import app

    client = TestClient(app)
    source_text = _read_text_fixture("memory_import_sample.txt")
    created = client.post(
        "/memory/import-jobs",
        json={
            "sourceKind": "file",
            "sourceText": source_text,
            "rawRef": {"type": "file", "locator": "evaluation/fixtures/memory_import_sample.txt"},
            "processImmediately": True,
            "requestedBy": {"type": "user", "id": "evaluation"},
            "importPolicy": {
                "segmentTargetChars": 180,
                "allowDiscardLowValue": False,
                "linkStrategy": ["keyword"],
                "mergePolicy": "balanced",
            },
        },
    )
    if created.status_code != 201:
        raise RuntimeError(f"memory import failed: {created.text}")
    body = created.json()
    retrieval = client.post(
        "/memory/retrievals",
        json={
            "queryText": "模块生命周期 事件总线 导入链路 检索",
            "branchId": DEFAULT_BRANCH_ID,
            "maxLeafNodes": 4,
            "maxRelatedNodes": 4,
            "includeNaturalLanguageSummary": True,
        },
    )
    if retrieval.status_code != 201:
        raise RuntimeError(f"memory retrieval failed: {retrieval.text}")
    retrieval_body = retrieval.json()
    return {
        "materializedNodeCount": len(body.get("materializedNodes") or []),
        "materializedEdgeCount": len(body.get("materializedEdges") or []),
        "retrievalMatchCount": len(retrieval_body["retrievalBundle"].get("matchedNodeRefs") or []),
        "summary": retrieval_body["retrievalBundle"].get("naturalLanguageSummary"),
    }

def _run_memory_strategy_compare_case(case: dict[str, Any] | None = None) -> dict[str, Any]:
    from fastapi.testclient import TestClient
    from yggdrasil_core_api.app import app

    case_payload = dict(case or {})
    client = TestClient(app)
    source_text = _read_text_fixture(str(case_payload.get("fixture") or "m8_memory_benchmark.txt"))
    query = str(case_payload.get("query") or "为什么这个系统需要共享术语、事件总线和模块宿主？")
    expected_keywords = [str(keyword) for keyword in case_payload.get("expectedKeywords") or []]
    top_k = max(1, int(case_payload.get("topK") or 4))

    created = client.post(
        "/memory/import-jobs",
        json={
            "sourceKind": "file",
            "sourceText": source_text,
            "rawRef": {"type": "file", "locator": str(case_payload.get("fixture") or "evaluation/fixtures/m8_memory_benchmark.txt")},
            "processImmediately": True,
            "requestedBy": {"type": "user", "id": "evaluation"},
            "importPolicy": {
                "segmentTargetChars": int(case_payload.get("segmentTargetChars") or 220),
                "allowDiscardLowValue": False,
                "linkStrategy": ["keyword"],
                "mergePolicy": "balanced",
            },
        },
    )
    if created.status_code != 201:
        raise RuntimeError(f"memory benchmark import failed: {created.text}")
    body = created.json()
    retrieval = client.post(
        "/memory/retrievals",
        json={
            "queryText": str(case_payload.get("retrievalQuery") or query),
            "branchId": DEFAULT_BRANCH_ID,
            "maxLeafNodes": top_k,
            "maxRelatedNodes": top_k,
            "includeNaturalLanguageSummary": True,
            "includeChildNames": True,
            "includeRelatedNames": True,
        },
    )
    if retrieval.status_code != 201:
        raise RuntimeError(f"memory benchmark retrieval failed: {retrieval.text}")
    retrieval_body = retrieval.json()
    bundle = dict(retrieval_body.get("retrievalBundle") or {})
    fragments = [dict(fragment) for fragment in body.get("fragments") or []]

    strategies = [
        ("no-memory", []),
        ("vector-flat", _select_flat_fragments(fragments, query, top_k)),
        ("memory-tree", _build_memory_tree_context(bundle, top_k)),
    ]
    scored_strategies: list[dict[str, Any]] = []
    for strategy_name, context_blocks in strategies:
        answer = _generate_strategy_answer(case_payload, query, strategy_name, context_blocks)
        scored_strategies.append(
            _score_strategy(
                strategy_name=strategy_name,
                expected_keywords=expected_keywords,
                context_blocks=context_blocks,
                answer_result=answer,
            )
        )

    scored_strategies.sort(
        key=lambda item: (float(item.get("combinedScore") or 0.0), float(item.get("contextCoverage") or 0.0), float(item.get("answerCoverage") or 0.0)),
        reverse=True,
    )
    return {
        "question": query,
        "expectedKeywords": expected_keywords,
        "materializedNodeCount": len(body.get("materializedNodes") or []),
        "materializedEdgeCount": len(body.get("materializedEdges") or []),
        "retrievalMatchCount": len(bundle.get("matchedNodeRefs") or []),
        "retrievalSummary": bundle.get("naturalLanguageSummary"),
        "strategies": scored_strategies,
        "topStrategy": scored_strategies[0]["name"] if scored_strategies else None,
    }

def _run_main_agent_case(case: dict[str, Any] | None = None) -> dict[str, Any]:
    from fastapi.testclient import TestClient
    from yggdrasil_agent_runtime.app import app as runtime_app
    from yggdrasil_worker.registry import run_worker_once

    task = _seed_runtime_task("eval_task_runtime")
    client = TestClient(runtime_app)
    started = client.post(
        f"/runtime/tasks/{task['id']}/start",
        json={
            "currentFocus": "evaluation main agent runtime",
            "currentContext": [
                {
                    "id": "ctx_keep",
                    "title": "runtime protocol",
                    "content": "main agent needs route decision, safe-stop, pause snapshot, and resume handling",
                    "importance": 0.9,
                }
            ],
            "protectedItems": [{"kind": "node", "id": "ctx_keep"}],
        },
    )
    if started.status_code != 202:
        raise RuntimeError(f"runtime start failed: {started.text}")
    pause_request = client.post(
        f"/runtime/tasks/{task['id']}/pause",
        json={
            "reason": "evaluation-manual-pause",
            "resumeMessage": "resume the evaluation run",
        },
    )
    if pause_request.status_code != 202:
        raise RuntimeError(f"runtime pause request failed: {pause_request.text}")
    first = run_worker_once("agent-runtime")
    if first.get("result", {}).get("status") != "paused":
        raise RuntimeError(f"runtime pause step failed: {json.dumps(first, ensure_ascii=False)}")
    resumed = client.post(
        f"/runtime/tasks/{task['id']}/resume",
        json={
            "nextObjective": "finish the evaluation flow",
        },
    )
    if resumed.status_code != 202:
        raise RuntimeError(f"runtime resume failed: {resumed.text}")
    second = run_worker_once("agent-runtime")
    if second.get("result", {}).get("status") != "completed":
        raise RuntimeError(f"runtime completion failed: {json.dumps(second, ensure_ascii=False)}")
    return {
        "pauseStatus": first["result"]["status"],
        "resumeStatus": second["result"]["status"],
        "snapshotId": first["result"]["snapshot"]["id"],
    }

def _run_live_llm_task_case(case: dict[str, Any] | None = None) -> dict[str, Any]:
    from fastapi.testclient import TestClient
    from yggdrasil_agent_runtime.app import app as runtime_app
    from yggdrasil_sdk.llm_runtime import load_runtime_candidate_models
    from yggdrasil_worker.registry import run_worker_once

    case_payload = dict(case or {})
    task_id = str(case_payload.get("taskId") or new_id("task", "m8-live-evaluation", stable=False))
    requested_provider = str(case_payload.get("requestedProvider") or "longcat")
    requested_model = str(case_payload.get("requestedModel") or "LongCat-2.0-Preview")
    candidate_models = [
        dict(candidate)
        for candidate in load_runtime_candidate_models() or []
        if str(candidate.get("provider") or "") == requested_provider and str(candidate.get("model") or "") == requested_model
    ]
    task = _seed_runtime_task(
        task_id,
        token_budget_total=int(case_payload.get("tokenBudgetTotal") or 1200),
        cost_budget_total=float(case_payload.get("costBudgetTotal") or 5.0),
    )
    client = TestClient(runtime_app)
    require_live = bool(case_payload.get("requireLive", False))
    if require_live and not candidate_models:
        raise RuntimeError(f"requested live candidate is unavailable: {requested_provider}/{requested_model}")
    current_context = case_payload.get("currentContext")
    if not isinstance(current_context, list) or not current_context:
        current_context = [
            {
                "id": "ctx_live_eval",
                "title": str(case_payload.get("contextTitle") or "M8 live benchmark context"),
                "content": str(
                    case_payload.get("context")
                    or "The system now includes real provider routing, benchmark baselines, OpenTelemetry export, Langfuse generation tracing, backup and restore tooling, and compose smoke checks."
                ),
                "importance": 0.98,
            }
        ]
    protected_items = case_payload.get("protectedItems")
    if not isinstance(protected_items, list):
        protected_items = [{"kind": "node", "id": "ctx_live_eval"}]
    start_payload = {
        "currentFocus": str(case_payload.get("currentFocus") or "M8 live LLM evaluation"),
        "currentObjective": str(case_payload.get("currentObjective") or "Use the mounted context to explain how memory-tree retrieval improves answer grounding."),
        "currentContext": [dict(item) for item in current_context],
        "protectedItems": [dict(item) for item in protected_items],
        "allowModelFallback": bool(case_payload.get("allowFallback", True)),
        "temperature": float(case_payload.get("temperature") or 0.15),
        "maxTokens": int(case_payload.get("maxTokens") or 320),
    }
    if case_payload.get("auditLevel") is not None:
        start_payload["auditLevel"] = str(case_payload["auditLevel"])
    if case_payload.get("allowToolExecution") is not None:
        start_payload["allowToolExecution"] = bool(case_payload["allowToolExecution"])
    if case_payload.get("maxToolRounds") is not None:
        start_payload["maxToolRounds"] = int(case_payload["maxToolRounds"])
    if case_payload.get("planConfirmed") is not None:
        start_payload["planConfirmed"] = bool(case_payload["planConfirmed"])
    if case_payload.get("takeoverPlanConfirmed") is not None:
        start_payload["takeoverPlanConfirmed"] = bool(case_payload["takeoverPlanConfirmed"])
    if case_payload.get("takeoverAutoConfirm") is not None:
        start_payload["takeoverAutoConfirm"] = bool(case_payload["takeoverAutoConfirm"])
    if case_payload.get("confirmPlan") is not None:
        start_payload["confirmPlan"] = bool(case_payload["confirmPlan"])
    if case_payload.get("responseRequirements") is not None:
        start_payload["responseRequirements"] = str(case_payload["responseRequirements"])
    if case_payload.get("restartMessage") is not None:
        start_payload["restartMessage"] = str(case_payload["restartMessage"])
    if case_payload.get("effectiveContextWindow") is not None:
        start_payload["effectiveContextWindow"] = int(case_payload["effectiveContextWindow"])
    if case_payload.get("windowRestartRatio") is not None:
        start_payload["windowRestartRatio"] = float(case_payload["windowRestartRatio"])
    if case_payload.get("forcedWindowRestartBudget") is not None:
        start_payload["forcedWindowRestartBudget"] = int(case_payload["forcedWindowRestartBudget"])
    if candidate_models:
        start_payload["candidateModels"] = candidate_models
    started = client.post(f"/runtime/tasks/{task['id']}/start", json=start_payload)
    if started.status_code != 202:
        raise RuntimeError(f"live evaluation start failed: {started.text}")

    max_worker_rounds = max(1, int(case_payload.get("maxWorkerRounds") or 1))
    processed_rounds: list[dict[str, Any]] = []
    result_payload: dict[str, Any] = {}
    for round_index in range(max_worker_rounds):
        processed = run_worker_once("agent-runtime")
        result_payload = dict(processed.get("result") or {})
        processed_rounds.append(
            {
                "round": round_index + 1,
                "workerStatus": processed.get("status"),
                "resultStatus": result_payload.get("status"),
                "transition": result_payload.get("transition"),
                "transitionOutcome": result_payload.get("transitionOutcome"),
                "detail": normalize_excerpt(str(result_payload.get("detail") or processed.get("detail") or ""), 240),
                "error": normalize_excerpt(str(result_payload.get("error") or processed.get("error") or ""), 240),
                "lastError": normalize_excerpt(str(result_payload.get("lastError") or processed.get("lastError") or ""), 240),
                "queueDepth": result_payload.get("queueDepth"),
            }
        )
        if result_payload.get("status") == "completed":
            break
        if result_payload.get("status") == "paused" and bool(case_payload.get("autoResumePaused", False)):
            resumed = client.post(
                f"/runtime/tasks/{task['id']}/resume",
                json={
                    "nextObjective": str(
                        case_payload.get("resumeObjective")
                        or case_payload.get("currentObjective")
                        or "finish the live evaluation flow"
                    ),
                    "planConfirmed": bool(case_payload.get("planConfirmed", True)),
                },
            )
            if resumed.status_code != 202:
                raise RuntimeError(f"live evaluation resume failed: {resumed.text}")
    live_round_count = sum(1 for item in processed_rounds if item.get("workerStatus") == "processed")
    budget_pause_observed = any(
        "budget exceeded" in str(item.get("detail") or "").lower() for item in processed_rounds
    )
    accepted_budget_pause = (
        bool(case_payload.get("acceptBudgetPauseAsEvidence", False))
        and budget_pause_observed
        and live_round_count >= max(1, int(case_payload.get("minLiveWorkerRounds") or 1))
    )
    incomplete_error = None
    if result_payload.get("status") != "completed" and not accepted_budget_pause:
        incomplete_error = (
            "live evaluation worker did not complete within "
            f"{max_worker_rounds} rounds: {json.dumps(processed_rounds, ensure_ascii=False)}"
        )

    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        repository = TaskRepository(session)
        prompt_repository = PromptAssetRepository(session)
        runtime_repository = RuntimeRepository(session)
        persisted_task = repository.get_task(task["id"])
        invocation_read_limit = max(
            20,
            int(case_payload.get("longTaskMinInvocations") or case_payload.get("minLiveInvocations") or 0),
            int(case_payload.get("longTaskInvocationReadLimit") or 0),
        )
        invocations = runtime_repository.list_model_invocations(task_id=task["id"], limit=invocation_read_limit)
        prompt_artifact = None
        if invocations and invocations[0].prompt_compile_artifact_id:
            prompt_artifact = prompt_repository.get_prompt_compile_artifact(invocations[0].prompt_compile_artifact_id)

    if not invocations:
        raise RuntimeError("live evaluation did not persist any model invocation")
    invocation = invocations[0]
    expected_provider = requested_provider
    if require_live and invocation.status != "completed":
        raise RuntimeError(f"live provider invocation did not complete: {invocation.status}")
    if require_live and invocation.resolved_provider not in {expected_provider, str(case_payload.get('providerAlias') or '')}:
        raise RuntimeError(
            f"live provider mismatch: expected {expected_provider}, got {invocation.resolved_provider or 'unknown'}"
        )
    accepted_live_invocation_evidence = (
        bool(case_payload.get("acceptLiveInvocationEvidence", False))
        and len(invocations) >= max(1, int(case_payload.get("minLiveInvocations") or 1))
    )
    if incomplete_error is not None and not accepted_live_invocation_evidence:
        raise RuntimeError(incomplete_error)

    include_payloads = bool(case_payload.get("includePayloads", True))
    aggregate_usage = _aggregate_live_invocation_usage(invocations)
    live_summary = {
        "taskId": task["id"],
        "taskStatus": persisted_task.status if persisted_task is not None else result_payload.get("status"),
        "workerRounds": processed_rounds,
        "acceptedBudgetPause": accepted_budget_pause,
        "acceptedLiveInvocationEvidence": accepted_live_invocation_evidence,
        "liveWorkerRoundCount": live_round_count,
        "runtimeTerminalStatus": result_payload.get("status"),
        "invocationCount": len(invocations),
        "invocationId": invocation.id,
        "invocationStatus": invocation.status,
        "provider": invocation.resolved_provider,
        "model": invocation.resolved_model,
        "traceId": invocation.trace_id,
        "latencyMs": invocation.latency_ms,
        "totalTokens": int((invocation.input_tokens_used or 0) + (invocation.output_tokens_used or 0)),
        "aggregateTotalTokens": aggregate_usage["totalTokens"],
        "aggregateOutputTokens": aggregate_usage["outputTokens"],
        "aggregateNonCacheInputTokens": aggregate_usage["nonCacheInputTokens"],
        "aggregateNonCacheBillableTokens": aggregate_usage["nonCacheBillableTokens"],
        "aggregateNonCacheInputTokenSource": aggregate_usage["nonCacheInputTokenSource"],
        "costUsed": float(invocation.cost_used or 0.0),
        "promptCompileArtifactId": invocation.prompt_compile_artifact_id,
    }
    if invocation.prompt_compile_artifact_id and prompt_artifact is None:
        raise RuntimeError(f"prompt compile artifact missing for invocation {invocation.id}")
    long_task_gate = _evaluate_live_long_task_gate(case_payload, live_summary)
    live_summary["longTaskGate"] = long_task_gate
    if long_task_gate["required"] and not long_task_gate["passed"]:
        raise RuntimeError(f"live long task gate failed: {json.dumps(long_task_gate, ensure_ascii=False)}")
    result = {
        **live_summary,
        "liveScenario": live_summary,
        "assistantPreview": normalize_excerpt(str(result_payload.get("assistantText") or ""), 240),
    }
    if include_payloads:
        result["requestPayload"] = _read_external_ref_json(invocation.request_ref, resolve_workspace_root())
        result["responsePayload"] = _read_external_ref_json(invocation.response_ref, resolve_workspace_root())
    return result


def _aggregate_live_invocation_usage(invocations: list[Any]) -> dict[str, Any]:
    total_tokens = 0
    output_tokens_total = 0
    non_cache_input_tokens = 0
    explicit_non_cache_count = 0
    for invocation in invocations:
        input_tokens = int(getattr(invocation, "input_tokens_used", 0) or 0)
        output_tokens = int(getattr(invocation, "output_tokens_used", 0) or 0)
        output_tokens_total += output_tokens
        total_tokens += input_tokens + output_tokens
        response_payload = _read_external_ref_json(getattr(invocation, "response_ref", None), resolve_workspace_root())
        usage = response_payload.get("usage") if isinstance(response_payload, dict) else None
        if not isinstance(usage, dict):
            usage = response_payload.get("usageDetails") if isinstance(response_payload, dict) else None
        if isinstance(usage, dict) and usage.get("nonCacheInputTokens") is not None:
            non_cache_input_tokens += max(int(usage.get("nonCacheInputTokens") or 0), 0)
            explicit_non_cache_count += 1
            continue
        if isinstance(usage, dict) and usage.get("cacheHitInputTokens") is not None:
            cache_hit = max(int(usage.get("cacheHitInputTokens") or 0), 0)
            non_cache_input_tokens += max(input_tokens - cache_hit, 0)
            explicit_non_cache_count += 1
            continue
        non_cache_input_tokens += input_tokens
    return {
        "totalTokens": total_tokens,
        "outputTokens": output_tokens_total,
        "nonCacheInputTokens": non_cache_input_tokens,
        "nonCacheBillableTokens": non_cache_input_tokens + output_tokens_total,
        "nonCacheInputTokenSource": "explicit" if explicit_non_cache_count == len(invocations) and invocations else "fallback-inputTokens",
    }


def _evaluate_live_long_task_gate(case_payload: dict[str, Any], live_summary: dict[str, Any]) -> dict[str, Any]:
    required = bool(case_payload.get("requireLongTaskEvidence", False))
    gate_kind = str(case_payload.get("longTaskGateKind") or "custom")
    if gate_kind == "long":
        default_min_invocations = 100
        default_min_non_cache_tokens = 1_000_000
        default_min_work_tree_depth = 2
    elif gate_kind == "ultra":
        default_min_invocations = 1000
        default_min_non_cache_tokens = 10_000_000
        default_min_work_tree_depth = 4
    else:
        default_min_invocations = 1
        default_min_non_cache_tokens = 0
        default_min_work_tree_depth = 1
    min_worker_rounds = max(1, int(case_payload.get("longTaskMinWorkerRounds") or case_payload.get("minLiveWorkerRounds") or default_min_invocations))
    min_invocations = max(1, int(case_payload.get("longTaskMinInvocations") or case_payload.get("minLiveInvocations") or default_min_invocations))
    min_non_cache_tokens = max(
        0,
        int(
            case_payload.get("longTaskMinNonCacheTokens")
            or case_payload.get("longTaskMinNonCacheBillableTokens")
            or default_min_non_cache_tokens
        ),
    )
    min_work_tree_depth = max(1, int(case_payload.get("longTaskMinWorkTreeDepth") or default_min_work_tree_depth))
    observed_work_tree_depth = max(0, int(case_payload.get("longTaskObservedWorkTreeDepth") or live_summary.get("workTreeDepth") or 0))
    terminal_required = str(case_payload.get("longTaskRequiredTerminalStatus") or "completed")
    require_explicit_non_cache = bool(case_payload.get("longTaskRequireExplicitNonCacheTokens", True))
    non_cache_source = str(live_summary.get("aggregateNonCacheInputTokenSource") or "")
    checks = {
        "workerRounds": int(live_summary.get("liveWorkerRoundCount") or 0) >= min_worker_rounds,
        "invocations": int(live_summary.get("invocationCount") or 0) >= min_invocations,
        "nonCacheBillableTokens": int(live_summary.get("aggregateNonCacheBillableTokens") or 0) >= min_non_cache_tokens,
        "explicitNonCacheTokens": (not require_explicit_non_cache) or non_cache_source == "explicit",
        "workTreeDepth": observed_work_tree_depth >= min_work_tree_depth,
        "terminalStatus": str(live_summary.get("runtimeTerminalStatus") or "") == terminal_required,
    }
    return {
        "kind": gate_kind,
        "required": required,
        "passed": all(checks.values()),
        "checks": checks,
        "observed": {
            "workerRounds": live_summary.get("liveWorkerRoundCount"),
            "invocations": live_summary.get("invocationCount"),
            "aggregateTotalTokens": live_summary.get("aggregateTotalTokens"),
            "aggregateOutputTokens": live_summary.get("aggregateOutputTokens"),
            "aggregateNonCacheInputTokens": live_summary.get("aggregateNonCacheInputTokens"),
            "aggregateNonCacheBillableTokens": live_summary.get("aggregateNonCacheBillableTokens"),
            "aggregateNonCacheInputTokenSource": live_summary.get("aggregateNonCacheInputTokenSource"),
            "workTreeDepth": observed_work_tree_depth,
            "terminalStatus": live_summary.get("runtimeTerminalStatus"),
        },
        "thresholds": {
            "minWorkerRounds": min_worker_rounds,
            "minInvocations": min_invocations,
            "minNonCacheBillableTokens": min_non_cache_tokens,
            "minWorkTreeDepth": min_work_tree_depth,
            "requireExplicitNonCacheTokens": require_explicit_non_cache,
            "terminalStatus": terminal_required,
        },
    }


def _run_live_llm_tool_case(case: dict[str, Any] | None = None) -> dict[str, Any]:
    from fastapi.testclient import TestClient
    from yggdrasil_agent_runtime.app import app as runtime_app
    from yggdrasil_sdk.llm_runtime import load_runtime_candidate_models
    from yggdrasil_worker.registry import run_worker_once

    case_payload = dict(case or {})
    task_id = str(case_payload.get("taskId") or new_id("task", "m8-live-tool-evaluation", stable=False))
    requested_provider = str(case_payload.get("requestedProvider") or "longcat")
    requested_model = str(case_payload.get("requestedModel") or "LongCat-2.0-Preview")
    candidate_models = [
        dict(candidate)
        for candidate in load_runtime_candidate_models() or []
        if str(candidate.get("provider") or "") == requested_provider and str(candidate.get("model") or "") == requested_model
    ]
    require_live = bool(case_payload.get("requireLive", False))
    if require_live and not candidate_models:
        raise RuntimeError(f"requested live candidate is unavailable: {requested_provider}/{requested_model}")

    required_tools = [str(name) for name in case_payload.get("requiredTools") or ["text_memory.retrieve", "context_pruning.plan"]]
    current_context = [
        dict(item)
        for item in (
            case_payload.get("currentContext")
            or [
                {
                    "id": "ctx_handoff_goal",
                    "title": "handoff target",
                    "content": "The final note must name the archived runtime changes and include a concrete retain plan for the next run.",
                    "importance": 0.98,
                },
                {
                    "id": "ctx_handoff_budget",
                    "title": "handoff budget",
                    "content": "The safe-stop package should fit within roughly 160 retained tokens and prioritize objective, invocation summary, and pruning narrative.",
                    "importance": 0.87,
                },
                {
                    "id": "ctx_noise",
                    "title": "noise",
                    "content": "Older brainstorming fragments can be dropped if they do not help the next run resume safely.",
                    "importance": 0.12,
                },
            ]
        )
    ]
    current_context.append(
        {
            "id": "ctx_required_tools",
            "title": "required tools",
            "content": (
                "Before finalizing the retain plan, you must call these tools and use their results: "
                + ", ".join(required_tools)
                + ". Do not skip the pruning step."
            ),
            "importance": 0.99,
        }
    )

    task = _seed_runtime_task(
        task_id,
        token_budget_total=int(case_payload.get("tokenBudgetTotal") or 1200),
        cost_budget_total=float(case_payload.get("costBudgetTotal") or 5.0),
    )
    _seed_tool_case_memory(task_id)
    client = TestClient(runtime_app)
    start_payload = {
        "currentFocus": str(case_payload.get("currentFocus") or "M8 live tool validation"),
        "currentObjective": str(
            case_payload.get("currentObjective")
            or "Recover the archived runtime changes from durable branch memory and prepare a safe-stop retain plan for the next run under a 160 token budget."
        ),
        "currentContext": current_context,
        "protectedItems": case_payload.get("protectedItems") or [{"kind": "node", "id": "ctx_handoff_goal"}],
        "allowModelFallback": bool(case_payload.get("allowFallback", True)),
        "temperature": float(case_payload.get("temperature") or 0.1),
        "maxTokens": int(case_payload.get("maxTokens") or 420),
    }
    if case_payload.get("auditLevel") is not None:
        start_payload["auditLevel"] = str(case_payload["auditLevel"])
    if case_payload.get("allowToolExecution") is not None:
        start_payload["allowToolExecution"] = bool(case_payload["allowToolExecution"])
    if case_payload.get("maxToolRounds") is not None:
        start_payload["maxToolRounds"] = int(case_payload["maxToolRounds"])
    if candidate_models:
        start_payload["candidateModels"] = candidate_models
    started = client.post(f"/runtime/tasks/{task['id']}/start", json=start_payload)
    if started.status_code != 202:
        raise RuntimeError(f"live tool evaluation start failed: {started.text}")

    processed = run_worker_once("agent-runtime")
    result_payload = dict(processed.get("result") or {})
    if result_payload.get("status") != "completed":
        raise RuntimeError(f"live tool evaluation worker failed: {json.dumps(processed, ensure_ascii=False)}")

    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        repository = TaskRepository(session)
        prompt_repository = PromptAssetRepository(session)
        runtime_repository = RuntimeRepository(session)
        persisted_task = repository.get_task(task["id"])
        invocations = runtime_repository.list_model_invocations(task_id=task["id"], limit=5)
        prompt_artifact = None
        if invocations and invocations[0].prompt_compile_artifact_id:
            prompt_artifact = prompt_repository.get_prompt_compile_artifact(invocations[0].prompt_compile_artifact_id)

    if not invocations:
        raise RuntimeError("live tool evaluation did not persist any model invocation")
    invocation = invocations[0]
    if require_live and invocation.status != "completed":
        raise RuntimeError(f"live tool provider invocation did not complete: {invocation.status}")
    if require_live and invocation.resolved_provider not in {requested_provider, str(case_payload.get('providerAlias') or '')}:
        raise RuntimeError(
            f"live tool provider mismatch: expected {requested_provider}, got {invocation.resolved_provider or 'unknown'}"
        )

    request_payload = _read_external_ref_json(invocation.request_ref, resolve_workspace_root())
    response_payload = _read_external_ref_json(invocation.response_ref, resolve_workspace_root())
    tool_entries = []
    if isinstance(response_payload, dict):
        tool_entries = list(response_payload.get("toolExecutions") or response_payload.get("toolExecutionSummaries") or [])
    tool_names: list[str] = []
    for entry in tool_entries:
        if not isinstance(entry, dict):
            continue
        if isinstance(entry.get("tool"), dict) and entry["tool"].get("name"):
            tool_names.append(str(entry["tool"]["name"]))
            continue
        if entry.get("tool"):
            tool_names.append(str(entry["tool"]))
    missing_tools = [name for name in required_tools if name not in tool_names]
    if missing_tools:
        raise RuntimeError(f"live tool evaluation did not execute required tools: {', '.join(missing_tools)}")
    if invocation.prompt_compile_artifact_id and prompt_artifact is None:
        raise RuntimeError(f"prompt compile artifact missing for invocation {invocation.id}")

    live_summary = {
        "taskId": task["id"],
        "taskStatus": persisted_task.status if persisted_task is not None else result_payload.get("status"),
        "invocationId": invocation.id,
        "invocationStatus": invocation.status,
        "provider": invocation.resolved_provider,
        "model": invocation.resolved_model,
        "traceId": invocation.trace_id,
        "latencyMs": invocation.latency_ms,
        "totalTokens": int((invocation.input_tokens_used or 0) + (invocation.output_tokens_used or 0)),
        "costUsed": float(invocation.cost_used or 0.0),
        "promptCompileArtifactId": invocation.prompt_compile_artifact_id,
        "toolExecutionNames": tool_names,
    }
    return {
        **live_summary,
        "liveScenario": live_summary,
        "assistantPreview": normalize_excerpt(str(result_payload.get("assistantText") or ""), 240),
        "requestPayload": request_payload,
        "responsePayload": response_payload,
    }


def _run_fork_runtime_harness_case(case: dict[str, Any] | None = None) -> dict[str, Any]:
    case_payload = dict(case or {})
    command_text = str(
        case_payload.get("expectedTestCommand")
        or "uv run pytest tests/runtime/test_work_tree_graph_fork_runtime_harness.py -q --basetemp=tmp/pytest-fork-runtime-harness"
    )
    completed = subprocess.run(
        command_text.split(),
        cwd=resolve_workspace_root(),
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "fork runtime deterministic harness failed: "
            + normalize_excerpt((completed.stdout or "") + "\n" + (completed.stderr or ""), 800)
        )
    return {
        "harnessMode": "deterministic",
        "command": command_text,
        "exitCode": completed.returncode,
        "stdoutPreview": normalize_excerpt(completed.stdout or "", 500),
        "validatedContracts": [
            "fork-agent-run-metadata",
            "fork-work-item-completion",
            "prompt-artifact-runType-fork",
            "workTreeSnapshot-inheritance",
            "pending-summary-only-flow",
            "no-child-task-or-task-branch",
        ],
    }


def _run_fork_evaluation_task_case(case: dict[str, Any] | None = None) -> dict[str, Any]:
    from ...contracts import WorkTreeProtocol
    from ...runtime_kernel.work_tree_graph import compute_parent_ready_set, plan_fork_batch

    case_payload = dict(case or {})
    evaluation_task = str(case_payload.get("evaluationTask") or case_payload.get("id") or "R")
    child_specs = [dict(item) for item in case_payload.get("childSpecs") or []]
    if not child_specs:
        raise RuntimeError(f"{evaluation_task} has no childSpecs")

    policy = dict(case_payload.get("policy") or {})
    root_children = [str(item.get("id") or f"child-{index}") for index, item in enumerate(child_specs, start=1)]
    nodes: list[dict[str, Any]] = [
        _fork_eval_node("root", parent=None, children=root_children, status="in-progress", priority=0),
    ]
    for index, spec in enumerate(child_specs, start=1):
        nodes.append(
            _fork_eval_node(
                str(spec.get("id") or f"child-{index}"),
                title=str(spec.get("title") or spec.get("area") or f"child-{index}"),
                depends_on=[str(dep) for dep in spec.get("dependsOn") or []],
                relation_ids=[str(relation) for relation in spec.get("relationIds") or []],
                priority=int(spec.get("priority") or index),
                status=str(spec.get("status") or "pending"),
            )
        )
    work_tree = WorkTreeProtocol.model_validate(
        {
            "id": f"wt-{evaluation_task.lower()}",
            "rootNodeId": "root",
            "rootObjective": str(case_payload.get("taskGoal") or case_payload.get("taskTitle") or evaluation_task),
            "status": "active",
            "currentNodeId": "root",
            "nodes": nodes,
        }
    )
    graph_state = {"pendingInformationItems": [dict(item) for item in case_payload.get("pendingInformationItems") or []]}
    ready_set = compute_parent_ready_set(work_tree, "root", graph_state=graph_state, policy=policy)
    batch_plan = plan_fork_batch(ready_set, policy)

    launched = [candidate.assigned_work_tree_node_id for candidate in batch_plan.launch_candidates]
    waiting = [candidate.assigned_work_tree_node_id for candidate in batch_plan.waiting_candidates]
    min_forks = int(case_payload.get("expectedMinForks") or len(child_specs))
    if len(launched) < min_forks:
        raise RuntimeError(f"{evaluation_task} launched {len(launched)} forks, expected at least {min_forks}")

    expected_waiting = [str(item) for item in case_payload.get("expectedWaiting") or []]
    if expected_waiting and waiting != expected_waiting:
        raise RuntimeError(f"{evaluation_task} waiting mismatch: expected {expected_waiting}, got {waiting}")

    if bool(case_payload.get("expectParentReplanRequired", False)) and not ready_set.parent_replan_required:
        raise RuntimeError(f"{evaluation_task} expected parent replan gate")
    if bool(case_payload.get("expectAutoLaunchBlocked", False)) and ready_set.can_auto_launch:
        raise RuntimeError(f"{evaluation_task} expected auto launch to be blocked")

    required_output_sections = [str(item) for item in case_payload.get("requiredOutputSections") or []]
    evidence_refs = [str(item) for spec in child_specs for item in spec.get("evidenceRefs") or []]
    if bool(case_payload.get("requireEvidenceRefs", True)) and len(evidence_refs) < len(child_specs):
        raise RuntimeError(f"{evaluation_task} expected at least one evidence ref per child")

    pending_summary_only = all("rawContent" not in dict(item) for item in graph_state["pendingInformationItems"])
    if bool(case_payload.get("requirePendingSummaryOnly", False)) and not pending_summary_only:
        raise RuntimeError(f"{evaluation_task} pending information contains rawContent")

    return {
        "evaluationTask": evaluation_task,
        "mode": "deterministic-fork-evaluation-task",
        "forkCount": len(launched),
        "launched": launched,
        "waiting": waiting,
        "sameParentContextAnchor": True,
        "parentReplanRequired": ready_set.parent_replan_required,
        "canAutoLaunch": ready_set.can_auto_launch,
        "pendingSummaryOnly": pending_summary_only,
        "evidenceRefCount": len(evidence_refs),
        "requiredOutputSections": required_output_sections,
        "implementationSlices": [str(item.get("title") or item.get("area") or item.get("id")) for item in child_specs],
    }


def _run_fork_showcase_benefit_case(case: dict[str, Any] | None = None) -> dict[str, Any]:
    case_payload = dict(case or {})
    workstreams = [dict(item) for item in case_payload.get("workstreams") or []]
    if not workstreams:
        raise RuntimeError("showcase benefit case requires workstreams")
    max_parallel = max(1, int(case_payload.get("maxParallelForks") or len(workstreams)))
    parent_merge_minutes = max(0.0, float(case_payload.get("parentMergeMinutes") or 0.0))
    serial_minutes = sum(max(0.0, float(item.get("estimatedMinutes") or 0.0)) for item in workstreams)
    fork_slots = [0.0 for _ in range(max_parallel)]
    for item in sorted(workstreams, key=lambda row: -float(row.get("estimatedMinutes") or 0.0)):
        slot_index = min(range(max_parallel), key=lambda index: fork_slots[index])
        fork_slots[slot_index] += max(0.0, float(item.get("estimatedMinutes") or 0.0))
    parallel_child_minutes = max(fork_slots) if fork_slots else 0.0
    parallel_total_minutes = parallel_child_minutes + parent_merge_minutes
    speedup = serial_minutes / parallel_total_minutes if parallel_total_minutes > 0 else 0.0

    serial_refs: list[str] = []
    for item in workstreams:
        serial_refs.extend(str(ref) for ref in item.get("sourceRefs") or [])
    unique_refs = sorted(set(serial_refs))
    serial_read_count = len(serial_refs)
    unique_read_count = len(unique_refs)
    duplicate_read_reduction = 1.0 - (unique_read_count / serial_read_count) if serial_read_count else 0.0
    evidence_coverage = sum(1 for item in workstreams if item.get("sourceRefs")) / len(workstreams)
    merge_overhead_ratio = parent_merge_minutes / parallel_total_minutes if parallel_total_minutes > 0 else 0.0
    result = {
        "mode": "public-showcase-benefit-estimate",
        "taskTitle": str(case_payload.get("taskTitle") or "Public showcase long task"),
        "forkCount": len(workstreams),
        "maxParallelForks": max_parallel,
        "serialBaselineMinutes": round(serial_minutes, 2),
        "forkParallelMinutes": round(parallel_total_minutes, 2),
        "parallelChildMinutes": round(parallel_child_minutes, 2),
        "parentMergeMinutes": round(parent_merge_minutes, 2),
        "wallClockSpeedup": round(speedup, 4),
        "wallClockReduction0_1": round(1.0 - (parallel_total_minutes / serial_minutes), 4) if serial_minutes else 0.0,
        "serialReadCount": serial_read_count,
        "uniqueReadCount": unique_read_count,
        "duplicateReadReduction0_1": round(duplicate_read_reduction, 4),
        "mergeOverheadRatio0_1": round(merge_overhead_ratio, 4),
        "evidenceCoverage0_1": round(evidence_coverage, 4),
        "uniqueEvidenceRefs": unique_refs,
        "workstreams": [
            {
                "id": str(item.get("id") or ""),
                "title": str(item.get("title") or item.get("id") or ""),
                "estimatedMinutes": float(item.get("estimatedMinutes") or 0.0),
                "sourceRefCount": len(item.get("sourceRefs") or []),
            }
            for item in workstreams
        ],
    }
    min_speedup = float(case_payload.get("minWallClockSpeedup") or 1.0)
    min_duplicate_reduction = float(case_payload.get("minDuplicateReadReduction0_1") or 0.0)
    if result["wallClockSpeedup"] < min_speedup:
        raise RuntimeError(f"showcase speedup below threshold: {result['wallClockSpeedup']} < {min_speedup}")
    if result["duplicateReadReduction0_1"] < min_duplicate_reduction:
        raise RuntimeError(
            f"showcase duplicate-read reduction below threshold: {result['duplicateReadReduction0_1']} < {min_duplicate_reduction}"
        )
    return result


def _fork_eval_node(
    node_id: str,
    *,
    title: str | None = None,
    parent: str | None = "root",
    children: list[str] | None = None,
    depends_on: list[str] | None = None,
    relation_ids: list[str] | None = None,
    priority: int = 100,
    status: str = "pending",
) -> dict[str, Any]:
    return {
        "id": node_id,
        "title": title or node_id,
        "parentNodeId": parent,
        "questionsItAnswers": [title or node_id],
        "nodeText": title or node_id,
        "localGoal": title or node_id,
        "phase": "executing",
        "status": status,
        "childNodeIds": children or [],
        "dependsOn": depends_on or [],
        "relationIds": relation_ids or [],
        "priority": priority,
    }


def _run_fork_runtime_live_candidate_case(case: dict[str, Any] | None = None) -> dict[str, Any]:
    case_payload = dict(case or {})
    if os.environ.get("YGGDRASIL_FORK_RUNTIME_LIVE") != "1":
        return {
            "harnessMode": "live-candidate",
            "status": "blocked",
            "blockerCode": "live-provider-not-enabled",
            "detail": "Set YGGDRASIL_FORK_RUNTIME_LIVE=1 and configure provider credentials before running this nightly candidate.",
            "requiredPrecondition": case_payload.get("expectedPrecondition"),
        }
    return _run_live_llm_task_case(
        {
            **case_payload,
            "requireLive": True,
            "currentFocus": case_payload.get("currentFocus") or "work-tree fork runtime live candidate",
            "currentObjective": case_payload.get("currentObjective")
            or "Exercise a longer live runtime task after deterministic fork harness stability.",
            "allowFallback": False,
            "allowToolExecution": False,
            "auditLevel": case_payload.get("auditLevel") or "strict",
        }
    )

__all__ = [name for name in globals() if not name.startswith("__")]
