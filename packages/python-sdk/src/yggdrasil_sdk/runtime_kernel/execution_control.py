from datetime import timedelta
from hashlib import sha256

from ._common import *  # noqa: F403,F401
from .root_mount import *  # noqa: F403,F401
from .snapshot import *  # noqa: F403,F401
from .snapshot_store import commit_snapshot_manifest, read_snapshot_entry, read_state_file_ref, verify_snapshot_manifest
from .takeover import *  # noqa: F403,F401


def _enqueue_runtime_work_item(
    *,
    task_repository: TaskRepository,
    coordinator: RedisCoordinator,
    queue: str,
    payload: dict[str, Any],
) -> tuple[Any, int]:
    work_item = task_repository.create_work_item(queue, payload)
    wake_payload = {"workItemId": work_item.id, "queue": queue, "activity": work_item.activity}
    queue_depth = coordinator.enqueue_job(queue, wake_payload)
    return work_item, queue_depth


def _snapshot_payload(snapshot: TaskSnapshotSummary) -> dict[str, Any]:
    if snapshot.storage_manifest_ref is not None:
        manifest = verify_snapshot_manifest(snapshot.storage_manifest_ref, snapshot.manifest_checksum)
        return {
            "rootMount": read_snapshot_entry(manifest, "rootMount", default={}) or {},
            "currentContext": read_snapshot_entry(manifest, "currentContext", default=[]) or [],
            "requestState": read_snapshot_entry(manifest, "requestState", default={}) or {},
            "pendingActions": read_snapshot_entry(manifest, "pendingActions", default=list(snapshot.pending_actions)) or [],
            "pendingWrites": read_snapshot_entry(
                manifest,
                "pendingWrites",
                default=[reference.model_dump(mode="json") for reference in snapshot.pending_writes],
            )
            or [],
            "toolState": read_snapshot_entry(manifest, "toolState", default={}) or {},
            "budgetState": read_snapshot_entry(manifest, "budgetState", default={}) or {},
            "routingState": read_snapshot_entry(manifest, "routingState", default={}) or {},
        }
    root_mount = (
        read_state_file_ref(snapshot.root_mount_ref, default=None)
        if snapshot.root_mount_ref.type == "state-file"
        else load_package_entry(snapshot.root_mount_ref.locator)
    )
    current_context = (
        read_state_file_ref(snapshot.context_ref, default=None)
        if snapshot.context_ref.type == "state-file"
        else load_package_entry(snapshot.context_ref.locator)
    )
    request_state: dict[str, Any] = {}
    for action in snapshot.pending_actions:
        if isinstance(action, dict) and action.get("kind") == "runtime-request-state" and isinstance(action.get("requestState"), dict):
            request_state = dict(action["requestState"])
            break
    return {
        "rootMount": root_mount if isinstance(root_mount, dict) else {},
        "currentContext": current_context if isinstance(current_context, list) else [],
        "requestState": request_state,
        "pendingActions": [action for action in snapshot.pending_actions if isinstance(action, dict)],
        "pendingWrites": [reference.model_dump(mode="json") for reference in snapshot.pending_writes],
        "toolState": {},
        "budgetState": {},
        "routingState": {},
    }


def _clone_snapshot_for_task(
    *,
    task_repository: TaskRepository,
    source_snapshot: TaskSnapshotSummary,
    target_task,
    retention_class: str,
    snapshot_type: str,
    status: str = "restorable",
    label: str | None = None,
    saved_by_user_id: str | None = None,
    expires_at: Any | None = None,
    agent_run_id: str | None = None,
) -> TaskSnapshotSummary:
    snapshot_id = new_id("snap", target_task.id, retention_class, utc_now().isoformat())
    payload = _snapshot_payload(source_snapshot)
    durable_snapshot = commit_snapshot_manifest(
        project_id=target_task.project_id,
        task_id=target_task.id,
        snapshot_id=snapshot_id,
        retention_class=retention_class,
        snapshot_type=snapshot_type,
        root_mount=payload["rootMount"],
        current_context=payload["currentContext"],
        request_state=payload["requestState"],
        pending_actions=payload["pendingActions"],
        pending_writes=payload["pendingWrites"],
        tool_state=payload["toolState"],
        budget_state=payload["budgetState"],
        routing_state=payload["routingState"],
        metadata={
            "clonedFromSnapshotId": source_snapshot.id,
            "savedLabel": label,
            "savedByUserId": saved_by_user_id,
        },
    )
    resume_token = new_id("resume", target_task.id, snapshot_id)
    snapshot = TaskSnapshotSummary(
        id=snapshot_id,
        appId=target_task.app_id,
        taskId=target_task.id,
        agentRunId=agent_run_id,
        projectId=target_task.project_id,
        branchId=target_task.branch_id,
        snapshotType=snapshot_type,
        status=status,
        retentionClass=retention_class,
        storageManifestRef=durable_snapshot["manifestRef"],
        manifestChecksum=durable_snapshot["manifestChecksum"],
        resumeTokenHash=sha256(resume_token.encode("utf-8")).hexdigest(),
        resumeToken=resume_token,
        contextRef=durable_snapshot["entryRefs"]["currentContext"],
        rootMountRef=durable_snapshot["entryRefs"]["rootMount"],
        pendingWrites=source_snapshot.pending_writes,
        pendingActions=[action for action in payload["pendingActions"] if isinstance(action, dict)],
        resumeMessage=source_snapshot.resume_message,
        safeStopReason=source_snapshot.safe_stop_reason,
        blockerCode=source_snapshot.blocker_code,
        blockerMessage=source_snapshot.blocker_message,
        savedLabel=label,
        savedByUserId=saved_by_user_id,
        expiresAt=expires_at,
        createdAt=utc_now(),
        verifiedAt=utc_now(),
        safeToPause=source_snapshot.safe_to_pause,
        currentNodeId=source_snapshot.current_node_id,
        workingNodeAnnotation=source_snapshot.working_node_annotation,
        pcMemo=source_snapshot.pc_memo,
        topFrameId=source_snapshot.top_frame_id,
        stackDigest=source_snapshot.stack_digest,
        blockers=list(source_snapshot.blockers),
    )
    return task_repository.create_snapshot(snapshot)


def record_task_side_channel_event(task_id: str, payload: dict[str, Any] | None = None) -> dict[str, object]:
    request = dict(payload or {})
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        runtime_repository = RuntimeRepository(session)
        task = task_repository.get_task(task_id)
        if task is None:
            raise KeyError(f"Task {task_id} not found.")
        event = runtime_repository.create_side_channel_event(
            {
                **request,
                "taskId": task.id,
                "projectId": request.get("projectId") or task.project_id,
            }
        )
    return {"sideChannelEvent": event.model_dump(by_alias=True, mode="json")}


def post_task_mailbox_message(task_id: str, payload: dict[str, Any] | None = None) -> dict[str, object]:
    request = dict(payload or {})
    runtime = get_persistence_runtime()
    should_queue = False
    wake_request = dict(request.get("wakeRequest") or {}) if isinstance(request.get("wakeRequest"), dict) else {}
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        runtime_repository = RuntimeRepository(session)
        task = task_repository.get_task(task_id)
        if task is None:
            raise KeyError(f"Task {task_id} not found.")
        message = runtime_repository.create_mailbox_message(
            {
                **request,
                "taskId": task.id,
                "projectId": request.get("projectId") or task.project_id,
            }
        )
        side_channel_event = runtime_repository.create_side_channel_event(
            {
                "taskId": task.id,
                "projectId": task.project_id,
                "agentRunId": request.get("agentRunId"),
                "source": request.get("sender") or request.get("createdBy") or {"type": "agent", "id": "system"},
                "eventKind": f"mailbox.{message.message_kind}",
                "level": "info",
                "summary": normalize_excerpt(message.subject or message.body or "Mailbox message recorded.", 240),
                "workTreeNodeId": message.work_tree_node_id,
                "payloadRef": request.get("payloadRef"),
            }
        )
        latest_active_run = task_repository.get_latest_agent_run(
            task_id,
            statuses={"initializing", "mounting", "running", "waiting-tool", "draining", "pausing"},
        )
        mailbox_state = runtime_repository.get_mailbox_state(task_id)
        wake_request.setdefault("mailboxState", mailbox_state)
        if message.work_tree_node_id is not None:
            memory_retrieval_state = dict(wake_request.get("memoryRetrievalState") or {})
            memory_retrieval_state.setdefault("workTreeNodeId", message.work_tree_node_id)
            wake_request["memoryRetrievalState"] = memory_retrieval_state
        should_queue = bool(
            message.wake_on_message
            and task.status in {"draft", "queued"}
            and not task.pause_requested
            and latest_active_run is None
        )
    wake_result = queue_main_agent_execution(task_id, wake_request) if should_queue else None
    return {
        "mailboxMessage": message.model_dump(by_alias=True, mode="json"),
        "mailboxState": mailbox_state,
        "sideChannelEvent": side_channel_event.model_dump(by_alias=True, mode="json"),
        "wakeResult": wake_result,
    }

def queue_main_agent_execution(task_id: str, payload: dict[str, Any] | None = None) -> dict[str, object]:
    request = dict(payload or {})
    request.setdefault("workTreeDirectiveRequired", True)
    runtime = get_persistence_runtime()
    coordinator = RedisCoordinator(runtime.settings)
    command = str(request.get("command") or "start")
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        task = task_repository.get_task(task_id)
        if task is None:
            raise KeyError(f"Task {task_id} not found.")
        update_payload: dict[str, Any] = {}
        outbox_record = None
        for key in ("currentFocus", "currentObjective", "resumeMessage", "budget", "budgetState"):
            if key in request:
                update_payload[key] = request[key]
        if command == "resume":
            if task.status not in {"paused", "resume-blocked"}:
                raise ValueError(f"Task {task_id} is not paused and cannot be resumed.")
            if request.get("resumeToken") is not None:
                raise ValueError("Resume tokens are no longer accepted by the public resume API.")
            snapshot = task_repository.get_snapshot(task.active_snapshot_id) if task.active_snapshot_id else None
            if snapshot is None or snapshot.status not in {"restorable", "leased"}:
                raise ValueError(f"Task {task_id} does not have a restorable active snapshot.")
            if snapshot.retention_class == "cancel-audit":
                raise ValueError(f"Task {task_id} cancel-audit snapshots cannot be resumed.")
            existing_attempt = task_repository.get_active_resume_attempt(task_id)
            attempt = task_repository.create_resume_attempt(
                task_id,
                snapshot.id,
                {"requestedBy": request.get("requestedBy") or {"type": "user", "id": "operator"}},
            )
            task = task_repository.update_task(
                task_id,
                {
                    "status": "paused",
                    "pauseRequested": False,
                    "pendingControlIntent": "resume",
                    "activeResumeAttemptId": attempt.id,
                    "resumeBlockedReason": None,
                    "resumeMessage": request.get("resumeMessage") or snapshot.resume_message or task.resume_message,
                },
            )
            work_item = None
            queue_depth = None
            if existing_attempt is None or existing_attempt.id != attempt.id:
                work_item_payload = {
                    "activity": "core.agent.main.execute",
                    "taskId": task_id,
                    "command": "resume",
                    "intent": "resume",
                    "resumeAttemptId": attempt.id,
                    "snapshotId": snapshot.id,
                    "requestedAt": utc_now().isoformat(),
                    "payload": {
                        **request,
                        "command": "resume",
                        "resumeAttemptId": attempt.id,
                        "snapshotId": snapshot.id,
                        "resumeMessage": task.resume_message,
                    },
                }
                work_item, queue_depth = _enqueue_runtime_work_item(
                    task_repository=task_repository,
                    coordinator=coordinator,
                    queue=AGENT_RUNTIME_QUEUE,
                    payload=work_item_payload,
                )
            resume_request_locator = f"agent-runtime/tasks/{task.id}/resume-attempts/{attempt.id}"
            outbox_record = _persist_runtime_event(
                session,
                project_id=task.project_id,
                aggregate_type="task-resume-attempt",
                aggregate_id=attempt.id,
                event_type="task.resume.requested",
                locator=resume_request_locator,
            )
            return {
                "status": "resume-blocked" if attempt.status == "blocked" else "resume-queued",
                "queue": AGENT_RUNTIME_QUEUE,
                "queueDepth": queue_depth,
                "task": task.model_dump(by_alias=True, mode="json"),
                "resumeAttempt": attempt.model_dump(by_alias=True, mode="json"),
                "snapshot": snapshot.model_dump(by_alias=True, mode="json"),
                "workItem": work_item.model_dump(by_alias=True, mode="json") if work_item is not None else None,
                "outboxRecord": outbox_record.model_dump(by_alias=True, mode="json") if outbox_record is not None else None,
            }
        elif command == "retry":
            if task.status != "failed":
                raise ValueError(f"Task {task_id} is in state {task.status} and cannot be retried.")
            update_payload["status"] = "queued"
            update_payload["pauseRequested"] = False
            update_payload["pendingControlIntent"] = None
            retry_request_locator = f"agent-runtime/tasks/{task.id}/retry-requests/{new_id('retry', task.id)}"
            outbox_record = _persist_runtime_event(
                session,
                project_id=task.project_id,
                aggregate_type="task",
                aggregate_id=task.id,
                event_type="task.retry.requested",
                locator=retry_request_locator,
            )
        else:
            if task.status in {"paused", "resume-blocked", "completed", "failed", "cancelled"}:
                raise ValueError(f"Task {task_id} is in state {task.status} and cannot be started directly.")
            update_payload["status"] = "queued"
            update_payload["pauseRequested"] = False
            update_payload["pendingControlIntent"] = None
        task = task_repository.update_task(task_id, update_payload)
        work_payload = {
            "activity": "core.agent.main.execute",
            "taskId": task_id,
            "command": command,
            "intent": command,
            "requestedAt": utc_now().isoformat(),
            "payload": request,
        }
        work_item, queue_depth = _enqueue_runtime_work_item(
            task_repository=task_repository,
            coordinator=coordinator,
            queue=AGENT_RUNTIME_QUEUE,
            payload=work_payload,
        )
    return {
        "status": "queued",
        "queue": AGENT_RUNTIME_QUEUE,
        "queueDepth": queue_depth,
        "task": task.model_dump(by_alias=True, mode="json"),
        "workItem": work_item.model_dump(by_alias=True, mode="json"),
        "outboxRecord": outbox_record.model_dump(by_alias=True, mode="json") if outbox_record is not None else None,
    }

def pause_task_execution(task_id: str, payload: dict[str, Any] | None = None) -> dict[str, object]:
    request = payload or {}
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        task = task_repository.get_task(task_id)
        if task is None:
            raise KeyError(f"Task {task_id} not found.")
        if task.status in {"completed", "failed", "cancelled"}:
            raise ValueError(f"Task {task_id} is in terminal state {task.status} and cannot be paused.")
        if task.status == "queued":
            cancelled_work_items = task_repository.cancel_queued_work_items(
                task_id,
                reason=request.get("reason") or "pause-before-worker-claim",
            )
            resume_message = request.get("resumeMessage") or task.resume_message
            current_focus = request.get("currentFocus") or task.current_focus
        else:
            cancelled_work_items = 0
            resume_message = request.get("resumeMessage") or task.resume_message
            current_focus = request.get("currentFocus") or task.current_focus

    if task.status == "queued":
        snapshot_response = prepare_pause_snapshot(
            task_id,
            {
                **request,
                "snapshotType": "pre-start",
                "retentionClass": "active-paused",
                "agentRunId": None,
                "currentResponseState": "idle",
                "safeStopReason": "pause-before-worker-claim",
                "resumeMessage": resume_message,
            },
        )
        with runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            task_repository = TaskRepository(session)
            task = task_repository.update_task(
                task_id,
                {
                    "status": "paused",
                    "pauseRequested": False,
                    "pendingControlIntent": None,
                    "resumeMessage": resume_message,
                    "currentFocus": current_focus,
                    "activeSnapshotId": snapshot_response.get("id"),
                    "lastSafeStopAt": utc_now(),
                },
            )
            event = _persist_runtime_event(
                session,
                project_id=task.project_id,
                aggregate_type="task",
                aggregate_id=task.id,
                event_type="task.paused",
                locator=f"agent-runtime/tasks/{task.id}/pause/{snapshot_response.get('id')}",
            )
            return {
                "status": "paused",
                "task": task.model_dump(by_alias=True, mode="json"),
                "snapshot": snapshot_response,
                "cancelledWorkItems": cancelled_work_items,
                "outboxRecord": event.model_dump(by_alias=True, mode="json"),
            }
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        task = task_repository.get_task(task_id)
        if task is None:
            raise KeyError(f"Task {task_id} not found.")
        task = task_repository.update_task(
            task_id,
            {
                "status": task.status,
                "pauseRequested": True,
                "pendingControlIntent": "pause",
                "resumeMessage": resume_message,
                "currentFocus": current_focus,
            },
        )
        pause_request_payload = {
            "requestedBy": request.get("requestedBy") or {"type": "user", "id": "operator"},
            "reason": request.get("reason") or "manual-pause",
            "pauseMode": request.get("pauseMode") or "manual",
            "waitForSafeStop": bool(request.get("waitForSafeStop", True)),
            "resumeMessage": request.get("resumeMessage"),
            "requestedAt": utc_now().isoformat(),
        }
        pause_request_locator = f"agent-runtime/tasks/{task.id}/pause-intents/{new_id('pause', task.id)}"
        coordinator = RedisCoordinator(runtime.settings)
        _cache_package_entry(coordinator, pause_request_locator, pause_request_payload)
        _cache_package_entry(coordinator, f"runtime/tasks/{task_id}/pause/current", pause_request_payload)
        event = _persist_runtime_event(
            session,
            project_id=task.project_id,
            aggregate_type="task",
            aggregate_id=task.id,
            event_type="task.pause.requested",
            locator=pause_request_locator,
        )
    return {
        "status": "draining" if task.status == "running" else "pause-pending",
        "task": task.model_dump(by_alias=True, mode="json"),
        "outboxRecord": event.model_dump(by_alias=True, mode="json"),
    }


request_task_pause = pause_task_execution


def cancel_task_execution(task_id: str, payload: dict[str, Any] | None = None) -> dict[str, object]:
    request = dict(payload or {})
    runtime = get_persistence_runtime()
    expires_at = utc_now() + timedelta(days=int(request.get("retentionDays") or 30))
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        task = task_repository.get_task(task_id)
        if task is None:
            raise KeyError(f"Task {task_id} not found.")
        if task.status in {"completed", "cancelled"}:
            raise ValueError(f"Task {task_id} is already terminal: {task.status}.")
        task_repository.cancel_queued_work_items(task_id, reason=request.get("reason") or "manual-cancel")
        active_attempt = task_repository.get_active_resume_attempt(task_id)
        if active_attempt is not None:
            task_repository.update_resume_attempt(active_attempt.id, status="cancelled")

        audit_snapshot = None
        source_snapshot = task_repository.get_snapshot(task.active_snapshot_id) if task.active_snapshot_id else None
        if source_snapshot is not None:
            audit_snapshot = _clone_snapshot_for_task(
                task_repository=task_repository,
                source_snapshot=source_snapshot,
                target_task=task,
                retention_class="cancel-audit",
                snapshot_type="audit",
                status="archived",
                label=request.get("label") or "cancel audit",
                saved_by_user_id=str((request.get("requestedBy") or {}).get("id") or request.get("userId") or "operator")
                if isinstance(request.get("requestedBy") or {}, dict)
                else "operator",
                expires_at=expires_at,
            )
        else:
            snapshot_response = prepare_pause_snapshot(
                task_id,
                {
                    **request,
                    "snapshotType": "audit",
                    "retentionClass": "cancel-audit",
                    "agentRunId": None,
                    "currentResponseState": "drained",
                    "safeStopReason": "cancel-audit",
                    "resumeMessage": request.get("reason") or "cancel audit",
                },
            )
            snapshot_id = str(snapshot_response.get("id") or "")
            if snapshot_id:
                audit_snapshot = task_repository.update_snapshot(
                    snapshot_id,
                    status="archived",
                    retention_class="cancel-audit",
                    expires_at=expires_at,
                    saved_label=request.get("label") or "cancel audit",
                )
        task = task_repository.update_task(
            task_id,
            {
                "status": "cancelled",
                "pauseRequested": False,
                "activeSnapshotId": None,
                "activeResumeAttemptId": None,
                "pendingControlIntent": None,
                "resumeBlockedReason": None,
                "currentFocus": request.get("reason") or "cancelled",
            },
        )
        event = _persist_runtime_event(
            session,
            project_id=task.project_id,
            aggregate_type="task",
            aggregate_id=task.id,
            event_type="task.cancelled",
            locator=f"agent-runtime/tasks/{task.id}/cancel",
        )
    return {
        "status": "cancelled",
        "task": task.model_dump(by_alias=True, mode="json"),
        "auditSnapshot": audit_snapshot.model_dump(by_alias=True, mode="json") if audit_snapshot is not None else None,
        "outboxRecord": event.model_dump(by_alias=True, mode="json"),
    }


def save_current_task_snapshot(task_id: str, payload: dict[str, Any] | None = None) -> dict[str, object]:
    request = dict(payload or {})
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        task = task_repository.get_task(task_id)
        if task is None:
            raise KeyError(f"Task {task_id} not found.")
        source_snapshot = task_repository.get_snapshot(task.active_snapshot_id) if task.active_snapshot_id else None
        if source_snapshot is None:
            raise ValueError(f"Task {task_id} does not have an active snapshot to save.")
        saved_by_user_id = str((request.get("requestedBy") or {}).get("id") or request.get("userId") or "operator") if isinstance(request.get("requestedBy") or {}, dict) else "operator"
        saved_snapshot = _clone_snapshot_for_task(
            task_repository=task_repository,
            source_snapshot=source_snapshot,
            target_task=task,
            retention_class="user-saved",
            snapshot_type=source_snapshot.snapshot_type,
            status="restorable",
            label=request.get("label") or request.get("savedLabel") or "manual snapshot",
            saved_by_user_id=saved_by_user_id,
            agent_run_id=source_snapshot.agent_run_id,
        )
        event = _persist_runtime_event(
            session,
            project_id=task.project_id,
            aggregate_type="task-snapshot",
            aggregate_id=saved_snapshot.id,
            event_type="task.snapshot.user_saved",
            locator=f"agent-runtime/tasks/{task.id}/snapshots/{saved_snapshot.id}",
        )
    return {
        "status": "saved",
        "snapshot": saved_snapshot.model_dump(by_alias=True, mode="json"),
        "outboxRecord": event.model_dump(by_alias=True, mode="json"),
    }


def create_task_branch_from_snapshot(task_id: str, payload: dict[str, Any] | None = None) -> dict[str, object]:
    request = dict(payload or {})
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        parent_task = task_repository.get_task(task_id)
        if parent_task is None:
            raise KeyError(f"Task {task_id} not found.")
        snapshot_id = str(request.get("snapshotId") or "")
        source_snapshot = task_repository.get_snapshot(snapshot_id) if snapshot_id else None
        if source_snapshot is None or source_snapshot.task_id != task_id:
            raise ValueError(f"Snapshot {snapshot_id or '<none>'} does not belong to task {task_id}.")
        if source_snapshot.retention_class != "user-saved":
            raise ValueError("Task branches can only be created from user-saved snapshots.")
        label = str(request.get("label") or source_snapshot.saved_label or "snapshot branch")
        child_task = task_repository.create_task(
            {
                "title": request.get("title") or f"{parent_task.title} / {label}",
                "goal": request.get("goal") or parent_task.goal,
                "status": "paused",
                "projectId": parent_task.project_id,
                "spaceId": parent_task.space_id,
                "branchId": parent_task.branch_id,
                "appId": parent_task.app_id,
                "ownerProfileId": parent_task.owner_profile_id,
                "resumeMessage": source_snapshot.resume_message,
            }
        )
        child_snapshot = _clone_snapshot_for_task(
            task_repository=task_repository,
            source_snapshot=source_snapshot,
            target_task=child_task,
            retention_class="active-paused",
            snapshot_type=source_snapshot.snapshot_type,
            status="restorable",
            label=label,
            saved_by_user_id=str((request.get("requestedBy") or {}).get("id") or request.get("userId") or "operator")
            if isinstance(request.get("requestedBy") or {}, dict)
            else "operator",
            agent_run_id=None,
        )
        child_task = task_repository.update_task(
            child_task.id,
            {
                "status": "paused",
                "activeSnapshotId": child_snapshot.id,
                "resumeMessage": child_snapshot.resume_message,
                "lastSafeStopAt": child_snapshot.created_at,
            },
        )
        branch = task_repository.create_task_branch(
            {
                "parentTaskId": parent_task.id,
                "childTaskId": child_task.id,
                "sourceSnapshotId": source_snapshot.id,
                "sourceSnapshotChecksum": source_snapshot.manifest_checksum or "",
                "label": label,
                "createdByUserId": str((request.get("requestedBy") or {}).get("id") or request.get("userId") or "operator")
                if isinstance(request.get("requestedBy") or {}, dict)
                else "operator",
            }
        )
        event = _persist_runtime_event(
            session,
            project_id=parent_task.project_id,
            aggregate_type="task-branch",
            aggregate_id=branch.id,
            event_type="task.branch.created",
            locator=f"agent-runtime/tasks/{parent_task.id}/branches/{branch.id}",
        )
    return {
        "status": "created",
        "branch": branch.model_dump(by_alias=True, mode="json"),
        "childTask": child_task.model_dump(by_alias=True, mode="json"),
        "childSnapshot": child_snapshot.model_dump(by_alias=True, mode="json"),
        "sourceSnapshot": source_snapshot.model_dump(by_alias=True, mode="json"),
        "outboxRecord": event.model_dump(by_alias=True, mode="json"),
    }


def retry_task_execution(task_id: str, payload: dict[str, Any] | None = None) -> dict[str, object]:
    request = dict(payload or {})
    request["command"] = "retry"
    request.setdefault("reason", "manual-retry")
    return queue_main_agent_execution(task_id, request)


def _latest_takeover_protocol(task_repository: TaskRepository, task_id: str) -> tuple[Any | None, TaskTakeoverProtocol | None]:
    latest_run = task_repository.get_latest_agent_run(task_id)
    if latest_run is None:
        return None, None
    return latest_run, load_persisted_task_takeover_protocol(task_id, latest_run.id)


def approve_task_completion(task_id: str, payload: dict[str, Any] | None = None) -> dict[str, object]:
    request = payload or {}
    runtime = get_persistence_runtime()
    coordinator = RedisCoordinator(runtime.settings)
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        task = task_repository.get_task(task_id)
        if task is None:
            raise KeyError(f"Task {task_id} not found.")
        if task.status != "awaiting-approval":
            raise ValueError(f"Task {task_id} is in state {task.status} and cannot be approved.")

        latest_run, takeover_protocol = _latest_takeover_protocol(task_repository, task_id)
        takeover_ref = None
        if takeover_protocol is not None and latest_run is not None:
            takeover_protocol = approve_takeover_completion(takeover_protocol)
            if takeover_protocol is not None:
                takeover_ref = persist_task_takeover_protocol(takeover_protocol, task_id=task.id, run_id=latest_run.id)

        task = task_repository.update_task(
            task_id,
            {
                "status": "completed",
                "pauseRequested": False,
                "activeSnapshotId": None,
                "currentFocus": request.get("currentFocus") or "completed",
            },
        )
        approval_locator = f"agent-runtime/tasks/{task.id}/approval/{new_id('approval', task.id)}"
        _cache_package_entry(
            coordinator,
            approval_locator,
            {
                "taskId": task.id,
                "approvedAt": utc_now().isoformat(),
                "approvedBy": request.get("approvedBy") or {"type": "user", "id": "operator"},
                "runId": latest_run.id if latest_run is not None else None,
                "takeoverProtocolRef": takeover_ref.model_dump(mode="json") if takeover_ref is not None else None,
            },
        )
        event = _persist_runtime_event(
            session,
            project_id=task.project_id,
            aggregate_type="task",
            aggregate_id=task.id,
            event_type="task.completion.approved",
            locator=approval_locator,
        )
    return {
        "status": "completed",
        "task": task.model_dump(by_alias=True, mode="json"),
        "takeoverProtocol": takeover_protocol.model_dump(by_alias=True, mode="json") if takeover_protocol is not None else None,
        "takeoverProtocolRef": takeover_ref.model_dump(mode="json") if takeover_ref is not None else None,
        "outboxRecord": event.model_dump(by_alias=True, mode="json"),
    }


def _takeover_protocol_has_unfinished_work_nodes(protocol: TaskTakeoverProtocol | None) -> bool:
    if protocol is None or protocol.work_tree is None:
        return False
    unfinished_statuses = {"pending", "in-progress", "summarizing", "blocked", "failed"}
    return any(str(node.status) in unfinished_statuses for node in protocol.work_tree.nodes)


_DEFAULT_REVISION_CONTROL_ANALYSIS_MESSAGE = (
    "程序检测到工作树仍有未标记为终态的节点；这只是 runtime 状态信号，不代表实际工作一定没完成。"
    "先做任务控制分析：对照工作树快照、currentNodeId、未终态 child/sibling、已完成 child summary、"
    "报告/证据产物和父节点职责；优先调用只读工具 "
    "task_takeover.list_unfinished_work_nodes 取得未完成节点清单和 suggestedBatchPruneNodeIds，判断应该回到父节点评估、"
    "进入/创建 leaf、清理废旧节点、用 confirmChildren=\"true\" 确认关闭已吸收的子树，还是宣告当前节点完成。然后继续执行，不要只解释原因。"
)
_DEFAULT_REVISION_RESPONSE_REQUIREMENTS = (
    "Revision control requirement: first output a concise Task Control Analysis identifying currentNodeId, "
    "runtime work-tree state, non-terminal child/sibling nodes, completed child summaries, existing report/evidence artifacts, "
    "and whether the runtime signal is only bookkeeping for nodes not marked terminal rather than actual unfinished work, "
    "using task_takeover.list_unfinished_work_nodes first when available instead of manually scanning the whole workTree JSON. "
    "and whether any child is obsolete or duplicate. If an unfinished child is obsolete or already covered by completed real work, "
    "emit exactly one <work-node-skip nodeId=\"...\">reason</work-node-skip> or "
    "<work-node-prune nodeIds=\"id1,id2\">reason</work-node-prune> and stop. "
    "If the current node's subtree is already absorbed but descendants remain non-terminal in runtime state, emit exactly one "
    "<work-node-complete status=\"completed\" confirmChildren=\"true\">...</work-node-complete> and stop. "
    "If all children are terminal and delivery artifacts are present, emit exactly one "
    "<work-node-complete status=\"completed\">...</work-node-complete> from the current parent/root. "
    "If more work is genuinely needed, emit exactly one <work-node-create ...></work-node-create> or "
    "<work-node-enter nodeId=\"...\"></work-node-enter> directive and stop. "
    "Do not emit multiple current-node-changing work-tree directives in one window; natural language never changes currentNodeId."
)


def _append_unique_text(existing: Any, addition: str) -> str:
    existing_text = str(existing or "").strip()
    addition_text = str(addition or "").strip()
    if not addition_text:
        return existing_text
    if addition_text in existing_text:
        return existing_text
    if not existing_text:
        return addition_text
    return existing_text + "\n\n" + addition_text


def _apply_default_revision_control_request(request: dict[str, Any]) -> dict[str, Any]:
    request.setdefault("nodeId", "auto-unfinished")
    request.setdefault("workTreeDirectiveRequired", True)
    request.setdefault("resumeMessage", _DEFAULT_REVISION_CONTROL_ANALYSIS_MESSAGE)
    if not str(request.get("reason") or "").strip():
        request["reason"] = str(request.get("userMessage") or request.get("resumeMessage") or _DEFAULT_REVISION_CONTROL_ANALYSIS_MESSAGE)
    if str(request.get("userMessage") or "").strip():
        request["resumeMessage"] = _append_unique_text(request.get("resumeMessage"), str(request["userMessage"]))
    request["responseRequirements"] = _append_unique_text(
        request.get("responseRequirements"),
        _DEFAULT_REVISION_RESPONSE_REQUIREMENTS,
    )
    return request


def request_task_revision(task_id: str, payload: dict[str, Any] | None = None) -> dict[str, object]:
    request = _apply_default_revision_control_request(dict(payload or {}))
    runtime = get_persistence_runtime()
    coordinator = RedisCoordinator(runtime.settings)
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        task = task_repository.get_task(task_id)
        if task is None:
            raise KeyError(f"Task {task_id} not found.")
        latest_run, takeover_protocol = _latest_takeover_protocol(task_repository, task_id)
        has_unfinished_work_tree = _takeover_protocol_has_unfinished_work_nodes(takeover_protocol)
        if task.status != "awaiting-approval" and not (task.status == "completed" and has_unfinished_work_tree):
            raise ValueError(f"Task {task_id} is in state {task.status} and cannot be reopened for revision.")

        if takeover_protocol is None:
            raise ValueError(f"Task {task_id} does not have a persisted takeover protocol to reopen.")
        revision_target_node_id = str(request.get("nodeId") or "").strip() or None
        revision_reason = str(request.get("reason") or request.get("resumeMessage") or "revision-requested").strip() or None
        reopened_protocol, reopened_stack = reopen_takeover_work_node_for_revision(
            takeover_protocol,
            task_id=task.id,
            agent_run_id=latest_run.id if latest_run is not None else new_id("run", task.id, "revision-preview"),
            node_id=revision_target_node_id,
            revision_reason=revision_reason,
            work_context_stack=request.get("workContextStack") if isinstance(request.get("workContextStack"), dict) else None,
        )
        takeover_ref = persist_task_takeover_protocol(
            reopened_protocol,
            task_id=task.id,
            run_id=latest_run.id if latest_run is not None else new_id("run", task.id, "revision-state", stable=True),
        )
        request.setdefault("currentObjective", task.current_objective or reopened_protocol.objective)
        request.setdefault("taskObjective", reopened_protocol.objective)
        request.setdefault("resumeMessage", revision_reason or f"Revise work-tree node {reopened_protocol.work_tree.current_node_id}.")
        request_payload = build_takeover_continuation_request(
            request,
            protocol=reopened_protocol,
            work_context_stack=reopened_stack,
            parent_run_id=latest_run.id if latest_run is not None else None,
            current_focus=request.get("currentFocus") or _work_tree_focus_label(reopened_protocol),
        )
        task = task_repository.update_task(
            task_id,
            {
                "status": "queued",
                "pauseRequested": False,
                "activeSnapshotId": None,
                "currentFocus": request_payload.get("currentFocus") or task.current_focus,
                "currentObjective": request_payload.get("currentObjective") or task.current_objective,
                "resumeMessage": request_payload.get("resumeMessage") or task.resume_message,
            },
        )
        work_item = {
            "activity": "core.agent.main.execute",
            "taskId": task_id,
            "command": "start",
            "intent": "revision",
            "requestedAt": utc_now().isoformat(),
            "payload": request_payload,
        }
        work_item_record, queue_depth = _enqueue_runtime_work_item(
            task_repository=task_repository,
            coordinator=coordinator,
            queue=AGENT_RUNTIME_QUEUE,
            payload=work_item,
        )
        revision_locator = f"agent-runtime/tasks/{task.id}/revision-requests/{new_id('revision', task.id)}"
        _cache_package_entry(
            coordinator,
            revision_locator,
            {
                "taskId": task.id,
                "requestedAt": utc_now().isoformat(),
                "reason": revision_reason,
                "targetNodeId": reopened_protocol.work_tree.current_node_id if reopened_protocol.work_tree is not None else None,
                "takeoverProtocolRef": takeover_ref.model_dump(mode="json"),
                "queueDepth": queue_depth,
            },
        )
        event = _persist_runtime_event(
            session,
            project_id=task.project_id,
            aggregate_type="task",
            aggregate_id=task.id,
            event_type="task.revision.requested",
            locator=revision_locator,
        )
    return {
        "status": "queued",
        "queue": AGENT_RUNTIME_QUEUE,
        "queueDepth": queue_depth,
        "task": task.model_dump(by_alias=True, mode="json"),
        "workItem": work_item_record.model_dump(by_alias=True, mode="json"),
        "takeoverProtocol": reopened_protocol.model_dump(by_alias=True, mode="json"),
        "takeoverProtocolRef": takeover_ref.model_dump(mode="json"),
        "outboxRecord": event.model_dump(by_alias=True, mode="json"),
    }

def _load_snapshot_context(snapshot: TaskSnapshotSummary | None) -> list[dict[str, Any]]:
    if snapshot is None:
        return []
    payload = (
        read_state_file_ref(snapshot.context_ref, default=None)
        if snapshot.context_ref.type == "state-file"
        else load_package_entry(snapshot.context_ref.locator)
    )
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []

def _build_execution_write_payload(
    *,
    task,
    task_type: str,
    root_mount: dict[str, Any],
    route_decision: dict[str, Any],
    model_output: str,
    model_invocation: dict[str, Any] | None,
    tool_executions: list[dict[str, Any]] | None,
    pruning_result: dict[str, Any] | None,
    resume_path: str | None,
    takeover_protocol: TaskTakeoverProtocol | None,
    takeover_protocol_ref: ExternalRef | None,
) -> dict[str, str]:
    lines = [model_output.strip() or "Model output was empty.", "", "Execution metadata:"]
    lines.extend(
        [
            f"Task goal: {task.goal}",
            f"Task objective: {task.current_objective or task.goal}",
            f"Current focus: {task.current_focus or 'runtime execution'}",
            f"Mounted summary: {root_mount['rootSummary']}",
            f"Route decision: {route_decision['selectedModel']} via {route_decision.get('selectedProvider') or 'unknown'}.",
            f"Task type: {task_type}",
        ]
    )
    if model_invocation is not None:
        lines.extend(
            [
                f"Invocation status: {model_invocation.get('status')}",
                f"Resolved model: {model_invocation.get('resolvedModel') or model_invocation.get('requestedModel')}",
                f"Resolved provider: {model_invocation.get('resolvedProvider') or 'unknown'}",
                f"Trace id: {model_invocation.get('traceId') or 'n/a'}",
                f"Prompt artifact: {model_invocation.get('promptCompileArtifactId') or 'n/a'}",
            ]
        )
    if tool_executions:
        lines.append(
            "Tool executions: "
            + "; ".join(
                f"{(execution.get('tool') or {}).get('name') or 'unknown'}={'ok' if execution.get('success') else 'error'}"
                for execution in tool_executions[:6]
                if isinstance(execution, dict)
            )
        )
    if resume_path:
        lines.append(f"Resume path: {resume_path}")
    if pruning_result is not None:
        lines.append(pruning_result.get("compressedNarrative") or pruning_result["plan"]["rationale"])
    if takeover_protocol is not None:
        lines.extend(
            [
                "",
                "Task takeover protocol:",
                f"Objective summary: {takeover_protocol.objective_summary}",
                f"Plan quality: {takeover_protocol.metrics.plan_quality_score_0_100}",
                f"Verification pass rate: {takeover_protocol.metrics.verification_pass_rate}",
                f"Delivery completeness: {takeover_protocol.metrics.delivery_completeness_score_0_100}",
            ]
        )
    if takeover_protocol_ref is not None:
        lines.append(f"Takeover artifact: {takeover_protocol_ref.locator}")
    return {
        "title": task.current_objective or task.title,
        "content": "\n".join(lines),
    }

def _record_pruning_events(session, task, plan_result: dict[str, Any], execute_result: dict[str, Any]) -> dict[str, Any]:
    planned = _persist_runtime_event(
        session,
        project_id=task.project_id,
        aggregate_type="task",
        aggregate_id=task.id,
        event_type="context.pruning.planned",
        locator=f"agent-runtime/tasks/{task.id}/pruning/{plan_result['id']}",
    )
    completed = _persist_runtime_event(
        session,
        project_id=task.project_id,
        aggregate_type="task",
        aggregate_id=task.id,
        event_type="context.pruning.completed",
        locator=f"agent-runtime/tasks/{task.id}/pruning/{plan_result['id']}/completed",
    )
    return {
        "planned": planned.model_dump(by_alias=True, mode="json"),
        "completed": completed.model_dump(by_alias=True, mode="json"),
    }


__all__ = [name for name in globals() if not name.startswith("__")]
