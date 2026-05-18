from __future__ import annotations

from typing import Any

from .execution_loop_part_a import *  # noqa: F401,F403
from .root_mount import _elapsed_ms


def _handle_window_restart_transition(
	*,
	session,
	coordinator,
	task_repository,
	task,
	run,
	route_decision,
	task_id: str,
	request: dict[str, Any],
	root_mount: dict[str, Any],
	runtime_metrics: dict[str, Any],
	context_length_observations: list[dict[str, Any]],
	effective_context: list[dict[str, Any]],
	pre_retrieval_context: list[dict[str, Any]],
	protected_items: list[dict[str, Any]],
	pruning_result,
	pruning_events,
	run_created_event,
	route_event,
	resume_event_payload,
	rehydration_result,
	runtime_timings: dict[str, Any],
	work_started_at: float,
	restart_trigger: str,
	window_span_tokens: int,
) -> dict[str, Any]:
	_append_context_length_observation(
		context_length_observations,
		phase="beforeWindowRestart",
		source="effectiveContext",
		items=effective_context,
		trigger=restart_trigger,
	)
	request["contextLengthObservations"] = [dict(item) for item in context_length_observations]
	restart_transition_started_at = perf_counter()
	source_window_span_tokens = max(window_span_tokens, _estimate_context_tokens(pre_retrieval_context))
	restart_state = _build_restart_snapshot_state(
		task_id,
		{
			**request,
			"projectId": task.project_id,
			"branchId": task.branch_id,
			"spaceId": task.space_id,
			"agentRunId": run.id,
			"currentContextState": effective_context,
			"rootMountPreview": root_mount,
			"restartMessage": request.get("restartMessage") or task.restart_message or f"Continue task {task.id} from the carry-forward package.",
			"windowIndex": runtime_metrics["windowIndex"],
			"restartCount": runtime_metrics["restartCount"],
			"compressionCount": runtime_metrics["compressionCount"],
			"cumulativeWindowSpanTokens": runtime_metrics["cumulativeWindowSpanTokens"],
			"carryForwardLossCount": runtime_metrics["carryForwardLossCount"],
			"forcedWindowRestartBudget": runtime_metrics["forcedWindowRestartBudget"],
			"effectiveContextWindow": runtime_metrics["effectiveContextWindow"],
			"windowRestartThreshold": runtime_metrics["windowRestartThreshold"],
			"windowSpanTokens": source_window_span_tokens,
			"protectedItems": protected_items,
		},
	)
	restart_snapshot_summary: TaskSnapshotSummary = restart_state["snapshot"]
	task_repository.supersede_snapshots(task_id)
	task_repository.create_snapshot(restart_snapshot_summary)
	window_execution_artifact = _persist_window_execution_artifact(
		session,
		task=task,
		run=run,
		record=_build_window_execution_record(
			task=task,
			run=run,
			request=request,
			root_mount=root_mount,
			runtime_metrics=runtime_metrics,
			current_context=effective_context,
			pre_retrieval_context=pre_retrieval_context,
			protected_items=protected_items,
			transition_stage="window-restart",
			transition_outcome="restart-requested",
			resume_path=(resume_event_payload or {}).get("resumePath") if isinstance(resume_event_payload, dict) else None,
			restart_trigger=restart_trigger,
			source_snapshot_id=(resume_event_payload or {}).get("snapshot", {}).get("id") if isinstance((resume_event_payload or {}).get("snapshot"), dict) else None,
			target_snapshot_id=restart_snapshot_summary.id,
			next_window_index=_int_metric(restart_state["runtimeMetrics"].get("windowIndex"), 0) or None,
			rehydration_result=rehydration_result,
		),
	)
	snapshot_created_event = _persist_runtime_event(
		session,
		project_id=task.project_id,
		aggregate_type="task-snapshot",
		aggregate_id=restart_snapshot_summary.id,
		event_type="task.snapshot.created",
		locator=f"agent-runtime/tasks/{task_id}/snapshots/{restart_snapshot_summary.id}",
	)
	restart_request_locator = f"agent-runtime/tasks/{task.id}/restart-requests/{restart_snapshot_summary.id}"
	_cache_package_entry(
		coordinator,
		restart_request_locator,
		{
			"snapshotId": restart_snapshot_summary.id,
			"resumeToken": restart_snapshot_summary.resume_token,
			"sourceWindowIndex": runtime_metrics["windowIndex"],
			"targetWindowIndex": restart_state["runtimeMetrics"]["windowIndex"],
			"effectiveContextWindow": restart_state["runtimeMetrics"]["effectiveContextWindow"],
			"windowRestartThreshold": restart_state["runtimeMetrics"]["windowRestartThreshold"],
			"windowSpanTokens": restart_state["runtimeMetrics"]["windowSpanTokens"],
		},
	)
	restart_requested_event = _persist_runtime_event(
		session,
		project_id=task.project_id,
		aggregate_type="task",
		aggregate_id=task.id,
		event_type="context.restart.requested",
		locator=restart_request_locator,
	)
	queued_work_item = {
		"activity": "core.agent.main.execute",
		"taskId": task_id,
		"command": "resume",
		"requestedAt": utc_now().isoformat(),
		"payload": {
			"resumeToken": restart_snapshot_summary.resume_token,
			"parentRunId": run.id,
		},
	}
	queue_depth = coordinator.enqueue_job(AGENT_RUNTIME_QUEUE, queued_work_item)
	task = task_repository.update_task(
		task_id,
		{
			"status": "restarting",
			"pauseRequested": False,
			"activeSnapshotId": restart_snapshot_summary.id,
			"lastSafeStopAt": utc_now(),
			"resumeMessage": restart_snapshot_summary.resume_message,
			"restartMessage": None,
			"currentFocus": "window-restart-handoff",
			"windowIndex": restart_state["runtimeMetrics"]["windowIndex"],
			"restartCount": restart_state["runtimeMetrics"]["restartCount"],
			"cumulativeWindowSpanTokens": restart_state["runtimeMetrics"]["cumulativeWindowSpanTokens"],
			"carryForwardLossCount": restart_state["runtimeMetrics"]["carryForwardLossCount"],
		},
	)
	run = task_repository.update_agent_run(
		run.id,
		{
			"status": "aborted",
			"windowIndex": runtime_metrics["windowIndex"],
			"restartCount": restart_state["runtimeMetrics"]["restartCount"],
			"cumulativeWindowSpanTokens": restart_state["runtimeMetrics"]["cumulativeWindowSpanTokens"],
		},
	)
	runtime_timings["restartTransitionMs"] = _elapsed_ms(restart_transition_started_at)
	runtime_timings["totalMs"] = _elapsed_ms(work_started_at)
	return {
		"status": "restarting",
		"task": task.model_dump(by_alias=True, mode="json"),
		"run": run.model_dump(by_alias=True, mode="json"),
		"routeDecision": route_decision.model_dump(by_alias=True, mode="json"),
		"rootMount": root_mount,
		"snapshot": restart_snapshot_summary.model_dump(by_alias=True, mode="json"),
		"queuedWorkItem": queued_work_item,
		"queueDepth": queue_depth,
		"pruning": pruning_result,
		"pruningEvents": pruning_events,
		"runtimeMetrics": restart_state["runtimeMetrics"],
		"windowExecutionArtifact": window_execution_artifact,
		"outboxRecords": {
			"runCreated": run_created_event.model_dump(by_alias=True, mode="json"),
			"routeSelected": route_event.model_dump(by_alias=True, mode="json"),
			"snapshotCreated": snapshot_created_event.model_dump(by_alias=True, mode="json"),
			"contextRestartRequested": restart_requested_event.model_dump(by_alias=True, mode="json"),
			"windowExecutionPersisted": window_execution_artifact["outboxRecord"],
		},
		"resume": resume_event_payload,
		"rehydration": rehydration_result,
		"runtimeTimings": dict(runtime_timings),
	}


def _finalize_execution_transition(
	*,
	session,
	coordinator,
	task_repository,
	task_id: str,
	task,
	run,
	route_decision,
	request: dict[str, Any],
	root_mount: dict[str, Any],
	created_node,
	llm_result: dict[str, Any],
	pruning_result,
	pruning_events,
	takeover_protocol,
	takeover_protocol_ref,
	model_invocation_event,
	run_created_event,
	route_event,
	write_event,
	resume_event_payload,
	memory_tag_write_result,
	write_validation,
	rehydration_result,
	runtime_metrics_artifact,
	runtime_timings: dict[str, Any],
	work_started_at: float,
	current_context: list[dict[str, Any]],
) -> dict[str, Any]:
	if task.pause_requested or bool(request.get("pauseAfterWrite", False)):
		pause_transition_started_at = perf_counter()
		pause_resume_message = request.get("resumeMessage") or task.resume_message or f"Resume task {task.id} after the last safe stop."
		pending_write_refs = [
			{"kind": "node", "id": created_node.id},
			*[
				{"kind": "node", "id": str(item.get("nodeId"))}
				for item in memory_tag_write_result.get("applied") or []
				if isinstance(item, dict) and item.get("nodeId") is not None
			],
		]
		pause_state = _build_pause_snapshot_state(
			task_id,
			{
				"projectId": task.project_id,
				"branchId": task.branch_id,
				"spaceId": task.space_id,
				"agentRunId": run.id,
				"pendingWrites": pending_write_refs,
				"pendingActions": request.get("pendingActions") if isinstance(request.get("pendingActions"), list) else [],
				"currentResponseState": "completed",
				"currentContextState": pruning_result.get("retainedItems") if isinstance(pruning_result, dict) else current_context,
				"rootMountPreview": root_mount,
				"resumeMessage": pause_resume_message,
				"taskObjective": task.current_objective or task.goal,
				"takeoverProtocol": request.get("takeoverProtocol"),
				"memoryRetrievalState": request.get("memoryRetrievalState"),
				"memoryTagWrites": request.get("memoryTagWrites"),
				"runtimeMetrics": request.get("runtimeMetrics"),
				"selectedModel": run.selected_model,
				"selectedProvider": run.selected_provider,
				"safeStopReason": request.get("safeStopReason") or "pause-requested",
			},
		)
		pause_snapshot_summary: TaskSnapshotSummary = pause_state["snapshot"]
		task_repository.supersede_snapshots(task_id)
		task_repository.create_snapshot(pause_snapshot_summary)
		snapshot_created_event = _persist_runtime_event(
			session,
			project_id=task.project_id,
			aggregate_type="task-snapshot",
			aggregate_id=pause_snapshot_summary.id,
			event_type="task.snapshot.created",
			locator=f"agent-runtime/tasks/{task_id}/snapshots/{pause_snapshot_summary.id}",
		)
		pause_snapshot = pause_snapshot_summary.model_dump(by_alias=True, mode="json")
		pause_snapshot["safeStop"] = pause_snapshot_summary.safe_to_pause
		pause_snapshot["activeToolCalls"] = pause_state["activeToolCalls"]
		pause_snapshot["rootMountPreview"] = pause_state["rootMountPreview"]
		pause_snapshot["flushedWrites"] = pause_state["flushedWrites"]
		pause_snapshot["persisted"] = True
		pause_snapshot["rootMountCached"] = pause_state["rootMountCached"]
		pause_snapshot["contextCached"] = pause_state["contextCached"]
		task = task_repository.update_task(
			task_id,
			{
				"status": "paused",
				"pauseRequested": False,
				"activeSnapshotId": pause_snapshot["id"],
				"lastSafeStopAt": utc_now(),
				"resumeMessage": pause_snapshot["resumeMessage"],
				"currentFocus": "paused-at-safe-stop",
			},
		)
		run = task_repository.update_agent_run(run.id, {"status": "paused"})
		paused_locator = f"agent-runtime/tasks/{task.id}/pause/{pause_snapshot['id']}"
		_cache_package_entry(
			coordinator,
			paused_locator,
			{
				"snapshotId": pause_snapshot["id"],
				"flushedWrites": pause_state["flushedWrites"],
				"pendingExternalActions": pause_snapshot_summary.pending_actions,
				"resumeToken": pause_snapshot["resumeToken"],
			},
		)
		paused_event = _persist_runtime_event(
			session,
			project_id=task.project_id,
			aggregate_type="task",
			aggregate_id=task.id,
			event_type="task.paused",
			locator=paused_locator,
		)
		window_execution_artifact = _persist_window_execution_artifact(
			session,
			task=task,
			run=run,
			record=_build_window_execution_record(
				task=task,
				run=run,
				request=request,
				root_mount=root_mount,
				runtime_metrics=request.get("runtimeMetrics") if isinstance(request.get("runtimeMetrics"), dict) else {},
				current_context=pruning_result.get("retainedItems") if isinstance(pruning_result, dict) and isinstance(pruning_result.get("retainedItems"), list) else current_context,
				llm_result=llm_result,
				memory_tag_write_result=memory_tag_write_result,
				transition_stage="window-delivery",
				transition_outcome="paused",
				resume_path=(resume_event_payload or {}).get("resumePath") if isinstance(resume_event_payload, dict) else None,
				source_snapshot_id=(resume_event_payload or {}).get("snapshot", {}).get("id") if isinstance((resume_event_payload or {}).get("snapshot"), dict) else None,
				rehydration_result=rehydration_result,
				created_node_id=created_node.id,
			),
		)
		runtime_timings["pauseTransitionMs"] = _elapsed_ms(pause_transition_started_at)
		runtime_timings["totalMs"] = _elapsed_ms(work_started_at)
		return {
			"status": "paused",
			"task": task.model_dump(by_alias=True, mode="json"),
			"run": run.model_dump(by_alias=True, mode="json"),
			"routeDecision": route_decision.model_dump(by_alias=True, mode="json"),
			"assistantText": str(llm_result.get("assistantText") or ""),
			"rootMount": root_mount,
			"createdNode": created_node.model_dump(by_alias=True, mode="json"),
			"snapshot": pause_snapshot,
			"pruning": pruning_result,
			"pruningEvents": pruning_events,
			"takeoverProtocol": takeover_protocol.model_dump(by_alias=True, mode="json") if takeover_protocol is not None else None,
			"takeoverProtocolRef": takeover_protocol_ref.model_dump(mode="json") if takeover_protocol_ref is not None else None,
			"outboxRecords": {
				"modelInvocationCompleted": model_invocation_event.model_dump(by_alias=True, mode="json"),
				"runCreated": run_created_event.model_dump(by_alias=True, mode="json"),
				"routeSelected": route_event.model_dump(by_alias=True, mode="json"),
				"snapshotCreated": snapshot_created_event.model_dump(by_alias=True, mode="json"),
				"writeCreated": write_event.model_dump(by_alias=True, mode="json"),
				"taskPaused": paused_event.model_dump(by_alias=True, mode="json"),
			},
			"resume": resume_event_payload,
			"memoryTagWrites": memory_tag_write_result,
			"writeValidation": write_validation,
			"rehydration": rehydration_result,
			"windowExecutionArtifact": window_execution_artifact,
			"runtimeMetricsArtifact": runtime_metrics_artifact,
			"runtimeTimings": {**runtime_timings, "llm": llm_result.get("timings")},
		}

	complete_transition_started_at = perf_counter()
	task = task_repository.update_task(
		task_id,
		{
			"status": "completed",
			"pauseRequested": False,
			"activeSnapshotId": None,
			"currentFocus": request.get("nextFocus") or "completed",
		},
	)
	run = task_repository.update_agent_run(run.id, {"status": "completed"})
	window_execution_artifact = _persist_window_execution_artifact(
		session,
		task=task,
		run=run,
		record=_build_window_execution_record(
			task=task,
			run=run,
			request=request,
			root_mount=root_mount,
			runtime_metrics=request.get("runtimeMetrics") if isinstance(request.get("runtimeMetrics"), dict) else {},
			current_context=pruning_result.get("retainedItems") if isinstance(pruning_result, dict) and isinstance(pruning_result.get("retainedItems"), list) else current_context,
			llm_result=llm_result,
			memory_tag_write_result=memory_tag_write_result,
			transition_stage="window-delivery",
			transition_outcome="completed",
			resume_path=(resume_event_payload or {}).get("resumePath") if isinstance(resume_event_payload, dict) else None,
			source_snapshot_id=(resume_event_payload or {}).get("snapshot", {}).get("id") if isinstance((resume_event_payload or {}).get("snapshot"), dict) else None,
			rehydration_result=rehydration_result,
			created_node_id=created_node.id,
		),
	)
	if takeover_protocol is not None and takeover_protocol.work_tree is not None:
		takeover_protocol = takeover_protocol.model_copy(
			update={
				"status": "completed",
				"work_tree": takeover_protocol.work_tree.model_copy(update={"status": "completed"}),
			}
		)
		takeover_protocol_ref = persist_task_takeover_protocol(takeover_protocol, task_id=task.id, run_id=run.id)
	runtime_timings["completeTransitionMs"] = _elapsed_ms(complete_transition_started_at)
	runtime_timings["totalMs"] = _elapsed_ms(work_started_at)
	return {
		"status": "completed",
		"task": task.model_dump(by_alias=True, mode="json"),
		"run": run.model_dump(by_alias=True, mode="json"),
		"routeDecision": route_decision.model_dump(by_alias=True, mode="json"),
		"assistantText": str(llm_result.get("assistantText") or ""),
		"rootMount": root_mount,
		"createdNode": created_node.model_dump(by_alias=True, mode="json"),
		"pruning": pruning_result,
		"pruningEvents": pruning_events,
		"takeoverProtocol": takeover_protocol.model_dump(by_alias=True, mode="json") if takeover_protocol is not None else None,
		"takeoverProtocolRef": takeover_protocol_ref.model_dump(mode="json") if takeover_protocol_ref is not None else None,
		"modelInvocation": llm_result["invocation"],
		"outboxRecords": {
			"modelInvocationCompleted": model_invocation_event.model_dump(by_alias=True, mode="json"),
			"runCreated": run_created_event.model_dump(by_alias=True, mode="json"),
			"routeSelected": route_event.model_dump(by_alias=True, mode="json"),
			"writeCreated": write_event.model_dump(by_alias=True, mode="json"),
		},
		"resume": resume_event_payload,
		"memoryTagWrites": memory_tag_write_result,
		"writeValidation": write_validation,
		"rehydration": rehydration_result,
		"windowExecutionArtifact": window_execution_artifact,
		"runtimeMetricsArtifact": runtime_metrics_artifact,
		"runtimeTimings": {**runtime_timings, "llm": llm_result.get("timings")},
	}
