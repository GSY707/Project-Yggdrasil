from __future__ import annotations

from .suite_cases_g4__part01 import *  # noqa: F403,F401

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
                "resumeToken": snapshot.resume_token,
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
                raise RuntimeError(
                    f"g4 provider matrix exceeded maxWindowCycles={max_window_cycles}: {json.dumps(processed_runs[-1], ensure_ascii=False)}"
                )
            continue
        if recovery_handler_fn is not None and recovery_handler_fn(processed_runs=processed_runs, processed=processed, result_payload=result_payload):
            if len(processed_runs) >= max_window_cycles:
                raise RuntimeError(
                    f"g4 provider matrix exceeded maxWindowCycles={max_window_cycles} during recovery: {json.dumps(processed_runs[-1], ensure_ascii=False)}"
                )
            continue
        if result_payload.get("status") != expected_result_status:
            raise RuntimeError(f"g4 provider matrix worker failed: {json.dumps(processed, ensure_ascii=False)}")
        return processed_runs, processed, result_payload
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
    requested_model = str(case_payload.get("requestedModel") or "LongCat-2.0-Preview")
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
    started = client.post(f"/runtime/tasks/{task['id']}/start", json=start_payload)
    if started.status_code != 202:
        raise RuntimeError(f"g4 provider matrix start failed: {started.text}")

    max_window_cycles = max(int(case_payload.get("maxWindowCycles") or 12), int(case_payload.get("forcedWindowRestartBudget") or 0) + 4)
    max_worker_wait_seconds = max(
        int(case_payload.get("maxWorkerWaitSeconds") or os.environ.get("YGGDRASIL_G4_MAX_WORKER_WAIT_SECONDS") or 180),
        30,
    )
    recovery_state = {"budgetTopUpAttempts": 0, "budgetRetryAttempts": 0}
    processed_runs, processed, result_payload = _g4_wait_for_target_worker_result(
        task_id=str(task["id"]),
        expected_result_status=expected_result_status,
        max_window_cycles=max_window_cycles,
        max_worker_wait_seconds=max_worker_wait_seconds,
        run_worker_once_fn=run_worker_once,
        recovery_handler_fn=lambda **kwargs: _g4_recover_live_budget_pause_or_failure(
            client=client,
            task_id=str(task["id"]),
            case_payload=case_payload,
            recovery_state=recovery_state,
            result_payload=dict(kwargs.get("result_payload") or {}),
        ),
    )

    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        task_repository = TaskRepository(session)
        prompt_repository = PromptAssetRepository(session)
        runtime_repository = RuntimeRepository(session)
        persisted_task = task_repository.get_task(task["id"])
        invocations = runtime_repository.list_model_invocations(task_id=task["id"], limit=64)
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
    final_task_status = str((persisted_task.status if persisted_task is not None else None) or result_payload.get("status") or "")
    if final_task_status != expected_task_status:
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
        "toolExecutionNames": _tool_execution_names(invocation_rows),
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
        "topToolFailures": tool_failure_summary,
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
            "promptCompileArtifactId": invocation.prompt_compile_artifact_id,
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
        "processedRuns": [dict(item) for item in processed_runs],
        "assistantPreview": assistant_preview,
    }
__all__ = [name for name in globals() if not name.startswith("__")]