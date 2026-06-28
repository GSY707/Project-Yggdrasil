from __future__ import annotations

from typing import Any

from .state import (
    AGENT_RUNTIME_QUEUE,
    TaskSnapshotSummary,
    TaskTakeoverProtocol,
    WorkContextStack,
    _build_pause_snapshot_state,
    _build_window_execution_record,
    _cache_package_entry,
    _persist_runtime_event,
    _persist_window_execution_artifact,
    advance_takeover_after_delivery,
    build_takeover_continuation_request,
    normalize_excerpt,
    perf_counter,
    persist_stack_snapshot,
    persist_task_takeover_protocol,
    switch_current_work_node,
    sync_takeover_runtime_state,
    utc_now,
)
from ..fork_runtime import ForkResultEnvelope, merge_fork_result_and_plan_next_batch
from ..root_mount import _elapsed_ms


def _work_tree_all_leaves_complete(work_tree: Any) -> bool:
	if work_tree is None:
		return False
	root_node_id = str(getattr(work_tree, "root_node_id", None) or "")
	nodes = getattr(work_tree, "nodes", None) or []
	terminal = {"completed", "failed", "skipped"}
	leaf_nodes = [node for node in nodes if str(getattr(node, "id", "") or "") != root_node_id]
	if not leaf_nodes:
		return False
	return all(str(getattr(node, "status", "") or "") in terminal for node in leaf_nodes)


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


def _fork_result_envelope_from_request(
	request: dict[str, Any],
	llm_result: dict[str, Any],
	evidence_refs: list[dict[str, Any]],
) -> ForkResultEnvelope:
	raw_envelope = request.get("forkResultEnvelope") if isinstance(request.get("forkResultEnvelope"), dict) else {}
	assigned_node_id = str(
		raw_envelope.get("assignedWorkTreeNodeId")
		or request.get("assignedWorkTreeNodeId")
		or request.get("workTreeNodeId")
		or request.get("currentNodeId")
		or ""
	).strip()
	if not assigned_node_id:
		raise ValueError("Fork result merge requires assignedWorkTreeNodeId.")
	proposed_dependency_changes = (
		raw_envelope.get("proposedDependencyChanges")
		if isinstance(raw_envelope.get("proposedDependencyChanges"), list)
		else []
	)
	proposed_relation_changes = (
		raw_envelope.get("proposedRelationChanges")
		if isinstance(raw_envelope.get("proposedRelationChanges"), list)
		else []
	)
	plan_impact = str(raw_envelope.get("planImpact") or request.get("planImpact") or "none")
	if proposed_dependency_changes or proposed_relation_changes:
		plan_impact = "requires-parent-replan"
	return ForkResultEnvelope.model_validate(
		{
			"assignedWorkTreeNodeId": assigned_node_id,
			"status": str(raw_envelope.get("status") or "completed"),
			"summary": normalize_excerpt(
				str(raw_envelope.get("summary") or llm_result.get("assistantText") or "Fork completed."),
				240,
			),
			"evidenceRefs": raw_envelope.get("evidenceRefs") or evidence_refs,
			"failureSummary": raw_envelope.get("failureSummary"),
			"planImpact": plan_impact,
			"proposedDependencyChanges": proposed_dependency_changes,
			"proposedRelationChanges": proposed_relation_changes,
			"pendingInformationItems": raw_envelope.get("pendingInformationItems") or [],
		}
	)


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
				"safeStopReason": request.get("safeStopReason") or "manual-pause",
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
				"retentionClass": pause_snapshot.get("retentionClass"),
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
	is_fork_run = str(request.get("runType") or "").strip().lower() == "fork"
	result_status = "completed"
	task_status = "completed"
	transition_outcome = "completed"
	queued_work_item = None
	queue_depth = None
	continuation_event = None
	work_context_stack_ref = None
	fork_merge_result = None
	fork_queued_work_items: list[dict[str, Any]] = []
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
				work_tree_resolution=request.get("workTreeResolution") if isinstance(request.get("workTreeResolution"), dict) else None,
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
		if takeover_protocol is not None and takeover_protocol.work_tree is not None and transition_state is None:
			current_node_id = takeover_protocol.work_tree.current_node_id
			root_node_id = takeover_protocol.work_tree.root_node_id
			assistant_text = str(llm_result.get("assistantText") or "")
			terminal_candidate = (
				takeover_protocol.status in {"needs-clarification", "completed", "verified"}
				or takeover_protocol.work_tree.status == "awaiting-approval"
			)
			if terminal_candidate and current_node_id != root_node_id:
				work_tree = takeover_protocol.work_tree
				node_by_id = {str(node.id): node for node in work_tree.nodes}
				next_node_id = None
				current_node = node_by_id.get(str(current_node_id or ""))
				if current_node is not None and current_node.parent_node_id is not None:
					parent_node = node_by_id.get(str(current_node.parent_node_id))
					sibling_ids: list[str] = []
					if parent_node is not None and parent_node.child_node_ids:
						sibling_ids = [str(item) for item in parent_node.child_node_ids]
					if not sibling_ids:
						sibling_ids = [
							str(node.id)
							for node in work_tree.nodes
							if str(node.parent_node_id or "") == str(current_node.parent_node_id)
						]
					for sibling_id in sibling_ids:
						if sibling_id == str(current_node_id):
							continue
						sibling_node = node_by_id.get(sibling_id)
						if sibling_node is None:
							continue
						if str(sibling_node.status) not in {"completed", "failed", "skipped"}:
							next_node_id = sibling_id
							break
					if next_node_id is None:
						next_node_id = str(current_node.parent_node_id)
				if next_node_id:
					now = utc_now()
					completed_summary = normalize_excerpt(assistant_text.strip(), 240)
					updated_nodes: list[dict[str, Any]] = []
					for node in work_tree.nodes:
						payload = node.model_dump(by_alias=True, mode="json")
						if str(node.id) == str(current_node_id):
							payload["status"] = "completed"
							if completed_summary:
								payload["executionSummary"] = completed_summary
							payload["updatedAt"] = now
						updated_nodes.append(payload)
					takeover_protocol = TaskTakeoverProtocol.model_validate(
						{
							**takeover_protocol.model_dump(by_alias=True, mode="json"),
							"status": "executing",
							"currentPhase": "execute",
							"workTree": {
								**work_tree.model_dump(by_alias=True, mode="json"),
								"nodes": updated_nodes,
								"status": "active",
								"updatedAt": now,
							},
						}
					)
					takeover_protocol, work_context_stack = switch_current_work_node(
						takeover_protocol,
						task_id=task.id,
						agent_run_id=run.id,
						node_id=next_node_id,
						work_context_stack=work_context_stack,
						cursor_state=f"continue:{next_node_id}",
					)
					transition_state = {
						"transition": "work-tree-continue",
						"requiresContinuation": True,
						"currentFocus": request.get("nextFocus") or request.get("currentFocus") or f"continue:{next_node_id}",
					}
			elif terminal_candidate and current_node_id == root_node_id:
				if _work_tree_all_leaves_complete(takeover_protocol.work_tree):
					takeover_protocol = takeover_protocol.model_copy(
						update={
							"status": "verified",
							"work_tree": takeover_protocol.work_tree.model_copy(update={"status": "awaiting-approval"}),
						}
					)
		# Always enforce hard delivery gates, even when an assistant transition was pre-applied.
		if takeover_protocol is not None and takeover_protocol.verification_items:
			blocked_hard_gates: list[str] = []
			verification_items_payload = (
				takeover_protocol.model_dump(by_alias=True, mode="json").get("verificationItems")
				if hasattr(takeover_protocol, "model_dump")
				else None
			)
			if isinstance(verification_items_payload, list):
				for item in verification_items_payload:
					if not isinstance(item, dict):
						continue
					if str(item.get("gateMode") or item.get("gate_mode") or "").strip().lower() == "hard" and str(item.get("status") or "").strip().lower() != "passed":
						blocked_hard_gates.append(str(item.get("label") or item.get("id") or "unknown"))
			else:
				for item in takeover_protocol.verification_items:
					if isinstance(item, dict):
						gate_mode = str(item.get("gateMode") or item.get("gate_mode") or "").strip().lower()
						status = str(item.get("status") or "").strip().lower()
						if gate_mode == "hard" and status != "passed":
							blocked_hard_gates.append(str(item.get("label") or item.get("id") or "unknown"))
					else:
						gate_mode = str(getattr(item, "gate_mode", "") or "").strip().lower()
						status = str(getattr(item, "status", "") or "").strip().lower()
						if gate_mode == "hard" and status != "passed":
							blocked_hard_gates.append(str(getattr(item, "label", "unknown")))
			if blocked_hard_gates and not (
				isinstance(transition_state, dict)
				and transition_state.get("transition") == "delivery-gate-blocked"
			):
				transition_state = {
					"transition": "delivery-gate-blocked",
					"requiresContinuation": work_context_stack is not None,
					"currentFocus": "delivery-gate-blocked",
					"blockedGates": blocked_hard_gates,
				}
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
				result_status = "needs-clarification"
				task_status = "resume-blocked"
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
					blocked_summary = ", ".join(blocked_gates) if blocked_gates else "delivery evidence or policy"
					corrective_tail = (
						"Previous output did not satisfy a hard safety or evidence gate. "
						f"Blocked gates: {blocked_summary}. "
						"Continue from the same work-tree node, gather or cite the missing evidence if possible, "
						"or state the remaining blocker and the next safe action."
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
					"intent": "continuation",
					"requestedAt": utc_now().isoformat(),
					"payload": continuation_payload,
				}
				queued_record = task_repository.create_work_item(AGENT_RUNTIME_QUEUE, queued_work_item)
				queued_work_item = queued_record.model_dump(by_alias=True, mode="json")
				queue_depth = coordinator.enqueue_job(
					AGENT_RUNTIME_QUEUE,
					{"workItemId": queued_record.id, "queue": AGENT_RUNTIME_QUEUE, "activity": queued_record.activity},
				)
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
	blocked_hard_gates_final: list[str] = []
	if takeover_protocol is not None and takeover_protocol.verification_items:
		verification_items_payload = (
			takeover_protocol.model_dump(by_alias=True, mode="json").get("verificationItems")
			if hasattr(takeover_protocol, "model_dump")
			else None
		)
		if isinstance(verification_items_payload, list):
			for item in verification_items_payload:
				if not isinstance(item, dict):
					continue
				if str(item.get("gateMode") or item.get("gate_mode") or "").strip().lower() == "hard" and str(item.get("status") or "").strip().lower() != "passed":
					blocked_hard_gates_final.append(str(item.get("label") or item.get("id") or "unknown"))
		else:
			for item in takeover_protocol.verification_items:
				if isinstance(item, dict):
					gate_mode = str(item.get("gateMode") or item.get("gate_mode") or "").strip().lower()
					status = str(item.get("status") or "").strip().lower()
					if gate_mode == "hard" and status != "passed":
						blocked_hard_gates_final.append(str(item.get("label") or item.get("id") or "unknown"))
				else:
					gate_mode = str(getattr(item, "gate_mode", "") or "").strip().lower()
					status = str(getattr(item, "status", "") or "").strip().lower()
					if gate_mode == "hard" and status != "passed":
						blocked_hard_gates_final.append(str(getattr(item, "label", "unknown")))
	if not blocked_hard_gates_final:
		request_takeover_protocol = request.get("takeoverProtocol") if isinstance(request.get("takeoverProtocol"), dict) else None
		request_verification_items = (
			request_takeover_protocol.get("verificationItems") if isinstance(request_takeover_protocol, dict) else None
		)
		if isinstance(request_verification_items, list):
			for item in request_verification_items:
				if not isinstance(item, dict):
					continue
				gate_mode = str(item.get("gateMode") or item.get("gate_mode") or "").strip().lower()
				status = str(item.get("status") or "").strip().lower()
				if gate_mode == "hard" and status != "passed":
					blocked_hard_gates_final.append(str(item.get("label") or item.get("id") or "unknown"))
	delivery_gate_blocked_final = (
		str((transition_state or {}).get("transition") or "") == "delivery-gate-blocked"
		or transition_outcome == "delivery-gate-blocked"
	)
	if (blocked_hard_gates_final or delivery_gate_blocked_final) and task_status == "completed":
		result_status = "needs-clarification"
		task_status = "resume-blocked"
		transition_outcome = "delivery-gate-blocked"

	if is_fork_run and result_status == "completed":
		fork_merge_context = request.get("forkMergeContext") if isinstance(request.get("forkMergeContext"), dict) else {}
		work_tree_snapshot = (
			fork_merge_context.get("workTreeSnapshot")
			if isinstance(fork_merge_context.get("workTreeSnapshot"), dict)
			else None
		)
		parent_node_id = str(fork_merge_context.get("parentNodeId") or "").strip()
		if work_tree_snapshot is not None and parent_node_id:
			fork_merge_result = merge_fork_result_and_plan_next_batch(
				task_repository=task_repository,
				task_id=task_id,
				parent_run_id=str(request.get("parentRunId") or run.parent_run_id or run.id),
				parent_node_id=parent_node_id,
				work_tree=work_tree_snapshot,
				result_envelope=_fork_result_envelope_from_request(request, llm_result, evidence_refs),
				policy=(
					fork_merge_context.get("policy")
					if isinstance(fork_merge_context.get("policy"), dict)
					else None
				),
				fork_run_id=run.id,
				fork_root_run_id=str(request.get("forkRootRunId") or run.fork_root_run_id or ""),
				fork_depth=int(request.get("forkDepth") or run.fork_depth or 1),
				auto_launch=bool(fork_merge_context.get("autoLaunchNextBatch", True)),
			)
			if fork_merge_result.next_batch is not None:
				for queued_fork in fork_merge_result.next_batch.queued_forks:
					work_item = queued_fork.work_item
					queue_depth = coordinator.enqueue_job(
						AGENT_RUNTIME_QUEUE,
						{
							"workItemId": work_item.id,
							"queue": AGENT_RUNTIME_QUEUE,
							"activity": work_item.activity,
						},
					)
					fork_queued_work_items.append(work_item.model_dump(by_alias=True, mode="json"))
			request["forkMergeResult"] = fork_merge_result.model_dump(by_alias=True, mode="json")
			root_mount["forkMergeResult"] = request["forkMergeResult"]
			transition_outcome = (
				"fork-parent-replan-required"
				if fork_merge_result.parent_replan_required
				else "fork-result-merged"
			)

	if is_fork_run:
		task_status = task.status
	task = task_repository.update_task(
		task_id,
		{
			"status": task_status,
			"pauseRequested": task.pause_requested if is_fork_run else False,
			"activeSnapshotId": task.active_snapshot_id if is_fork_run else None,
			"currentFocus": task.current_focus if is_fork_run else request.get("nextFocus") or (transition_state or {}).get("currentFocus") or request.get("currentFocus") or ("awaiting-approval" if task_status == "awaiting-approval" else "completed"),
		},
	)
	run_status = "completed"
	if task_status == "failed":
		run_status = "failed"
	elif task_status == "queued" and result_status == "continuing":
		run_status = "aborted"
	run = task_repository.update_agent_run(run.id, {"status": run_status})
	execution_state_audit = {
		"resultStatus": result_status,
		"taskStatus": task_status,
		"runStatus": run_status,
		"transitionOutcome": transition_outcome,
		"transition": (transition_state or {}).get("transition") if isinstance(transition_state, dict) else None,
		"deliveryGateBlocked": bool(delivery_gate_blocked_final),
		"blockedHardGates": blocked_hard_gates_final,
		"continuationQueued": continuation_event is not None,
		"forkResultMerged": fork_merge_result is not None,
		"forkNextBatchQueued": len(fork_queued_work_items),
		"queueDepth": queue_depth,
	}
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
		if blocked_hard_gates_final or delivery_gate_blocked_final:
			takeover_protocol_payload = takeover_protocol.model_dump(by_alias=True, mode="json")
			takeover_protocol_payload["status"] = "needs-clarification"
			takeover_protocol = TaskTakeoverProtocol.model_validate(takeover_protocol_payload)
		if task_status == "completed" and not blocked_hard_gates_final and not delivery_gate_blocked_final:
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
		"forkMergeResult": (
			fork_merge_result.model_dump(by_alias=True, mode="json")
			if fork_merge_result is not None
			else None
		),
		"forkQueuedWorkItems": fork_queued_work_items,
		"queueDepth": queue_depth,
		"executionStateAudit": execution_state_audit,
		"runtimeMetricsArtifact": runtime_metrics_artifact,
		"runtimeTimings": {**runtime_timings, "llm": llm_result.get("timings")},
	}

__all__ = [name for name in globals() if not name.startswith("__")]
