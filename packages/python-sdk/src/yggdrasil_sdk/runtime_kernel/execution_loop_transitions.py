from __future__ import annotations

from typing import Any

from .execution_loop_part_a import *  # noqa: F401,F403
from .root_mount import _elapsed_ms


def _persist_work_context_stack_ref(
	work_context_stack: WorkContextStack | dict[str, Any] | None,
	*,
	task_id: str,
	run_id: str,
) -> dict[str, Any] | None:
	if work_context_stack is None:
		return None
	try:
		stack_model = WorkContextStack.model_validate(work_context_stack)
	except Exception:
		return None
	return persist_stack_snapshot(stack_model, task_id=task_id, run_id=run_id).model_dump(mode="json")


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
	assistant_work_tree_transition: dict[str, Any] | None = None,
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
		pause_stack_ref = _persist_work_context_stack_ref(
			request.get("workContextStack") if isinstance(request.get("workContextStack"), dict) else None,
			task_id=task_id,
			run_id=run.id,
		)
		pause_snapshot["workContextStackRef"] = pause_stack_ref
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
			"workContextStackRef": pause_stack_ref,
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
	result_status = "completed"
	task_status = "completed"
	transition_outcome = "completed"
	queued_work_item = None
	queue_depth = None
	continuation_event = None
	work_context_stack_ref = None
	evidence_refs = [
		{"kind": "node", "id": created_node.id},
		*[
			{"kind": "node", "id": str(item.get("nodeId"))}
			for item in memory_tag_write_result.get("applied") or []
			if isinstance(item, dict) and item.get("nodeId") is not None
		],
	]
	work_context_stack = request.get("workContextStack") if isinstance(request.get("workContextStack"), dict) else None
	transition_state = None
	if takeover_protocol is not None and takeover_protocol.work_tree is not None:
		if takeover_protocol.status == "needs-clarification":
			result_status = "needs-clarification"
			task_status = "awaiting-approval"
			transition_outcome = "needs-clarification"
		transition_state = assistant_work_tree_transition if isinstance(assistant_work_tree_transition, dict) and assistant_work_tree_transition.get("applied") else None
		if transition_state is None:
			takeover_protocol, work_context_stack, transition_state = advance_takeover_after_delivery(
				takeover_protocol,
				task_id=task_id,
				agent_run_id=run.id,
				assistant_text=str(llm_result.get("assistantText") or ""),
				work_context_stack=work_context_stack,
				evidence_refs=evidence_refs,
			)
		if takeover_protocol is not None and takeover_protocol.work_tree is not None:
			takeover_protocol, work_context_stack = sync_takeover_runtime_state(
				request,
				root_mount,
				takeover_protocol,
				task_id=task_id,
				agent_run_id=run.id,
				current_focus=(transition_state or {}).get("currentFocus") if isinstance(transition_state, dict) else None,
				work_context_stack=work_context_stack,
			)
		delivery_gate_retry_count = max(0, int(request.get("deliveryGateRetryCount") or 0))
		delivery_gate_retry_allowed = (
			isinstance(transition_state, dict)
			and transition_state.get("transition") == "delivery-gate-blocked"
			and work_context_stack is not None
			and delivery_gate_retry_count < 1
		)
		if delivery_gate_retry_allowed and isinstance(transition_state, dict):
			transition_state = {
				**transition_state,
				"transition": "delivery-gate-retry",
				"requiresContinuation": True,
				"currentFocus": str(transition_state.get("currentFocus") or request.get("currentFocus") or "delivery-gate-retry"),
			}
		if takeover_protocol is not None and takeover_protocol.work_tree is not None:
			if takeover_protocol.status == "needs-clarification":
				result_status = "needs-clarification"
				task_status = "awaiting-approval"
				transition_outcome = "needs-clarification"
			elif takeover_protocol.work_tree.status == "awaiting-approval":
				result_status = "awaiting-approval"
				task_status = "awaiting-approval"
				transition_outcome = "awaiting-approval"
			elif takeover_protocol.work_tree.status == "failed":
				result_status = "failed"
				task_status = "failed"
				transition_outcome = "failed"
			elif isinstance(transition_state, dict) and transition_state.get("transition") == "delivery-gate-blocked":
				result_status = "failed"
				task_status = "failed"
				transition_outcome = "delivery-gate-blocked"
			elif bool((transition_state or {}).get("requiresContinuation")) and work_context_stack is not None:
				work_context_stack_ref = _persist_work_context_stack_ref(
					work_context_stack,
					task_id=task_id,
					run_id=run.id,
				)
				continuation_payload = build_takeover_continuation_request(
					request,
					protocol=takeover_protocol,
					work_context_stack=work_context_stack,
					parent_run_id=run.id,
					current_focus=(transition_state or {}).get("currentFocus") if isinstance(transition_state, dict) else None,
				)
				if delivery_gate_retry_allowed:
					blocked_gates = [str(item) for item in (transition_state or {}).get("blockedGates") or [] if str(item).strip()]
					blocked_summary = ", ".join(blocked_gates) if blocked_gates else "delivery.result/evidence/pending/incomplete"
					corrective_tail = (
						"Previous output stopped before the formal delivery contract was satisfied. "
						f"Blocked hard gates: {blocked_summary}. "
						"Continue immediately from the same work-tree node and emit the final delivery now. "
						"Do not add planning preambles, scanning notes, or process narration. "
						"Output Markdown only and satisfy all required delivery sections in one response."
					)
					base_response_requirements = str(continuation_payload.get("responseRequirements") or request.get("responseRequirements") or "").strip()
					continuation_payload["responseRequirements"] = " ".join(
						part for part in (base_response_requirements, corrective_tail) if part
					)
					continuation_payload["resumeMessage"] = corrective_tail
					continuation_payload["deliveryGateRetryCount"] = delivery_gate_retry_count + 1
				if work_context_stack_ref is not None:
					continuation_payload["workContextStackRef"] = work_context_stack_ref
				queued_work_item = {
					"activity": "core.agent.main.execute",
					"taskId": task_id,
					"command": "start",
					"requestedAt": utc_now().isoformat(),
					"payload": continuation_payload,
				}
				queue_depth = coordinator.enqueue_job(AGENT_RUNTIME_QUEUE, queued_work_item)
				continuation_locator = f"agent-runtime/tasks/{task.id}/continuations/{run.id}"
				_cache_package_entry(
					coordinator,
					continuation_locator,
					{
						"sourceRunId": run.id,
						"currentNodeId": continuation_payload.get("currentNodeId"),
						"topFrameId": continuation_payload.get("topFrameId"),
						"stackDigest": continuation_payload.get("stackDigest"),
						"workContextStackRef": work_context_stack_ref,
						"transition": (transition_state or {}).get("transition"),
						"queueDepth": queue_depth,
					},
				)
				continuation_event = _persist_runtime_event(
					session,
					project_id=task.project_id,
					aggregate_type="task",
					aggregate_id=task.id,
					event_type="task.continuation.queued",
					locator=continuation_locator,
				)
				result_status = "continuing"
				task_status = "queued"
				transition_outcome = str((transition_state or {}).get("transition") or "continued")
	task = task_repository.update_task(
		task_id,
		{
			"status": task_status,
			"pauseRequested": False,
			"activeSnapshotId": None,
			"currentFocus": request.get("nextFocus") or (transition_state or {}).get("currentFocus") or request.get("currentFocus") or ("awaiting-approval" if task_status == "awaiting-approval" else "completed"),
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
			transition_outcome=transition_outcome,
			resume_path=(resume_event_payload or {}).get("resumePath") if isinstance(resume_event_payload, dict) else None,
			source_snapshot_id=(resume_event_payload or {}).get("snapshot", {}).get("id") if isinstance((resume_event_payload or {}).get("snapshot"), dict) else None,
			rehydration_result=rehydration_result,
			created_node_id=created_node.id,
		),
	)
	if takeover_protocol is not None and takeover_protocol.work_tree is not None:
		if task_status == "completed":
			takeover_protocol_payload = takeover_protocol.model_dump(by_alias=True, mode="json")
			takeover_protocol_payload["status"] = "completed"
			takeover_protocol_payload["workTree"] = {
				**takeover_protocol_payload.get("workTree", {}),
				"status": "completed",
			}
			takeover_protocol = TaskTakeoverProtocol.model_validate(takeover_protocol_payload)
		takeover_protocol_ref = persist_task_takeover_protocol(takeover_protocol, task_id=task.id, run_id=run.id)
	runtime_timings["completeTransitionMs"] = _elapsed_ms(complete_transition_started_at)
	runtime_timings["totalMs"] = _elapsed_ms(work_started_at)
	return {
		"status": result_status,
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
			"continuationQueued": continuation_event.model_dump(by_alias=True, mode="json") if continuation_event is not None else None,
		},
		"resume": resume_event_payload,
		"memoryTagWrites": memory_tag_write_result,
		"writeValidation": write_validation,
		"rehydration": rehydration_result,
		"windowExecutionArtifact": window_execution_artifact,
		"workContextStackRef": work_context_stack_ref,
		"queuedWorkItem": queued_work_item,
		"queueDepth": queue_depth,
		"runtimeMetricsArtifact": runtime_metrics_artifact,
		"runtimeTimings": {**runtime_timings, "llm": llm_result.get("timings")},
	}
