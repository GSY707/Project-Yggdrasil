def _extract_assistant_memory_write_tags(assistant_text: str, *, enabled: bool) -> dict[str, Any]:
    if not enabled:
        return {
            "cleanAssistantText": str(assistant_text or "").strip(),
            "writes": [],
            "blocked": [],
            "detectedCount": 0,
        }

    parsed_writes: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []

    def _replace(match: re.Match[str]) -> str:
        raw_tag = str(match.group(0) or "")
        attributes = _parse_memory_write_tag_attributes(str(match.group("attrs") or ""))
        content = str(match.group("content") or "").strip()
        node_id = str(attributes.get("nodeid") or "").strip()
        title = str(attributes.get("title") or "").strip()
        action_raw = str(attributes.get("action") or "").strip().lower()
        if not content:
            blocked.append(
                {
                    "status": "blocked",
                    "reason": "empty-content",
                    "tagPreview": normalize_excerpt(raw_tag, 160),
                }
            )
            return ""
        if not node_id and not title:
            blocked.append(
                {
                    "status": "blocked",
                    "reason": "missing-title-or-nodeId",
                    "tagPreview": normalize_excerpt(raw_tag, 160),
                }
            )
            return ""
        if action_raw and action_raw not in {"create", "append", "replace"}:
            blocked.append(
                {
                    "status": "blocked",
                    "reason": "invalid-action",
                    "action": action_raw,
                    "tagPreview": normalize_excerpt(raw_tag, 160),
                }
            )
            return ""
        parsed_writes.append(
            {
                "rawTag": raw_tag,
                "title": title,
                "content": content,
                "nodeId": node_id or None,
                "action": _normalize_memory_tag_action(attributes.get("action"), has_node_id=bool(node_id)),
                "rootBranch": _normalize_memory_tag_root_branch(attributes.get("rootbranch")),
                "importance": min(max(_float_metric(attributes.get("importance"), 0.72), 0.0), 1.0),
                "detailLevel": max(_int_metric(attributes.get("detaillevel"), 2), 1),
                "targetSpaceId": str(attributes.get("spaceid") or "").strip() or None,
                "targetBranchId": str(attributes.get("branchid") or "").strip() or None,
            }
        )
        return ""

    stripped = _MEMORY_WRITE_TAG_PATTERN.sub(_replace, assistant_text)
    clean_text = re.sub(r"\n{3,}", "\n\n", stripped).strip()
    return {
        "cleanAssistantText": clean_text,
        "writes": parsed_writes,
        "blocked": blocked,
        "detectedCount": len(parsed_writes) + len(blocked),
    }
def _split_structured_tag_values(value: str | None, *, fallback: list[str] | None = None) -> list[str]:
    parts = [
        normalize_excerpt(str(item).strip(), 120)
        for item in re.split(r"[|;\n]+", str(value or ""))
        if str(item).strip()
    ]
    normalized = [item for item in parts if item]
    if normalized:
        return normalized
    return [item for item in (fallback or []) if str(item).strip()]
def _extract_assistant_work_tree_actions(assistant_text: str, *, enabled: bool) -> dict[str, Any]:
    if not enabled:
        return {
            "cleanAssistantText": str(assistant_text or "").strip(),
            "actions": [],
            "blocked": [],
            "detectedCount": 0,
        }

    parsed_actions: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []

    def _replace(match: re.Match[str]) -> str:
        raw_tag = str(match.group(0) or "")
        action_name = str(match.group("action") or "create").strip().lower() or "create"
        attributes = _parse_memory_write_tag_attributes(str(match.group("attrs") or ""))
        if action_name == "enter":
            node_id = str(attributes.get("nodeid") or "").strip()
            if not node_id:
                blocked.append(
                    {
                        "status": "blocked",
                        "reason": "missing-nodeid",
                        "tagPreview": normalize_excerpt(raw_tag, 160),
                    }
                )
                return ""
            parsed_actions.append(
                {
                    "action": "enter",
                    "rawTag": raw_tag,
                    "nodeId": node_id,
                    "cursorState": str(attributes.get("cursor") or "parent-selected-existing-child").strip() or "parent-selected-existing-child",
                }
            )
            return ""
        title = str(attributes.get("title") or "").strip()
        parent_node_id = str(attributes.get("parentnodeid") or "").strip() or None
        content = str(match.group("content") or "").strip()
        local_goal = content or str(attributes.get("goal") or "").strip() or title
        if not title:
            blocked.append(
                {
                    "status": "blocked",
                    "reason": "missing-title",
                    "tagPreview": normalize_excerpt(raw_tag, 160),
                }
            )
            return ""
        parsed_actions.append(
            {
                "action": "create",
                "rawTag": raw_tag,
                "title": title,
                "parentNodeId": parent_node_id,
                "phase": str(attributes.get("phase") or "executing").strip() or "executing",
                "localGoal": local_goal,
                "questionsItAnswers": _split_structured_tag_values(attributes.get("questions"), fallback=[title]),
                "expectedEvidence": _split_structured_tag_values(attributes.get("evidence"), fallback=[]),
            }
        )
        return ""

    stripped = _WORK_TREE_ACTION_TAG_PATTERN.sub(_replace, assistant_text)
    clean_text = re.sub(r"\n{3,}", "\n\n", stripped).strip()
    return {
        "cleanAssistantText": clean_text,
        "actions": parsed_actions,
        "blocked": blocked,
        "detectedCount": len(parsed_actions) + len(blocked),
    }
def _apply_parsed_assistant_work_tree_actions(
    *,
    task_id: str,
    agent_run_id: str,
    request: dict[str, Any],
    root_mount: dict[str, Any],
    takeover_protocol: TaskTakeoverProtocol | None,
    parsed_actions: dict[str, Any] | None,
) -> tuple[TaskTakeoverProtocol | None, WorkContextStack | None, dict[str, Any]]:
    action_payload = parsed_actions if isinstance(parsed_actions, dict) else {}
    blocked = [dict(item) for item in action_payload.get("blocked") or [] if isinstance(item, dict)]
    actions = [dict(item) for item in action_payload.get("actions") or [] if isinstance(item, dict)]
    work_context_stack = request.get("workContextStack") if isinstance(request.get("workContextStack"), dict) else None

    if takeover_protocol is None or takeover_protocol.work_tree is None or not actions:
        return takeover_protocol, _coerce_work_context_stack(work_context_stack), {
            "detectedCount": int(action_payload.get("detectedCount") or len(blocked)),
            "cleanAssistantText": str(action_payload.get("cleanAssistantText") or ""),
            "applied": [],
            "blocked": blocked,
        }

    current_node = _current_work_tree_node(takeover_protocol)
    default_parent_node_id = (
        current_node.id
        if current_node is not None
        else takeover_protocol.work_tree.current_node_id or takeover_protocol.work_tree.root_node_id
    )
    updated_protocol = takeover_protocol
    updated_stack = _coerce_work_context_stack(work_context_stack)
    applied: list[dict[str, Any]] = []

    for action in actions:
        action_kind = str(action.get("action") or "create").strip().lower() or "create"
        try:
            if action_kind == "enter":
                target_node_id = str(action.get("nodeId") or "").strip()
                if not target_node_id:
                    raise ValueError("Missing target work-tree node id.")
                updated_protocol, updated_stack = switch_current_work_node(
                    updated_protocol,
                    task_id=task_id,
                    agent_run_id=agent_run_id,
                    node_id=target_node_id,
                    work_context_stack=updated_stack,
                    cursor_state=str(action.get("cursorState") or "parent-selected-existing-child").strip() or "parent-selected-existing-child",
                )
                applied.append(
                    {
                        "status": "applied",
                        "action": "enter",
                        "nodeId": target_node_id,
                        "activated": True,
                    }
                )
            else:
                updated_protocol, updated_stack, created_node = create_child_work_node(
                    updated_protocol,
                    task_id=task_id,
                    agent_run_id=agent_run_id,
                    title=str(action.get("title") or "").strip() or "Untitled work node",
                    phase=str(action.get("phase") or "executing").strip() or "executing",
                    parent_node_id=str(action.get("parentNodeId") or "").strip() or default_parent_node_id,
                    questions_it_answers=[
                        str(item)
                        for item in action.get("questionsItAnswers") or []
                        if str(item).strip()
                    ]
                    or [str(action.get("title") or "").strip() or "Untitled work node"],
                    local_goal=str(action.get("localGoal") or action.get("title") or "").strip() or None,
                    expected_evidence=[
                        str(item)
                        for item in action.get("expectedEvidence") or []
                        if str(item).strip()
                    ],
                    work_context_stack=updated_stack,
                    activate=not applied,
                )
                applied.append(
                    {
                        "status": "applied",
                        "action": "create",
                        "title": created_node.title,
                        "parentNodeId": created_node.parent_node_id,
                        "childNodeId": created_node.id,
                        "workingNodeAnnotation": created_node.working_node_annotation,
                        "activated": len(applied) == 0,
                    }
                )
        except Exception as exc:  # noqa: BLE001
            blocked.append(
                {
                    "status": "blocked",
                    "reason": "enter-child-failed" if action_kind == "enter" else "create-child-failed",
                    "title": str(action.get("title") or action.get("nodeId") or "").strip() or None,
                    "detail": str(exc),
                }
            )

    if applied and updated_protocol is not None and updated_protocol.work_tree is not None:
        updated_protocol, updated_stack = sync_takeover_runtime_state(
            request,
            root_mount,
            updated_protocol,
            task_id=task_id,
            agent_run_id=agent_run_id,
            current_focus=_work_tree_focus_label(updated_protocol),
            work_context_stack=updated_stack,
        )

    primary_action = str(applied[0].get("action") or "create") if applied else "create"
    transition = {
        "transition": "enter-existing-child" if primary_action == "enter" else "enter-child",
        "requiresContinuation": bool(applied),
        "currentNodeId": updated_protocol.work_tree.current_node_id if updated_protocol is not None and updated_protocol.work_tree is not None else None,
        "nextNodeId": (
            applied[0].get("nodeId")
            if applied and primary_action == "enter"
            else applied[0].get("childNodeId") if applied else None
        ),
        "currentFocus": _work_tree_focus_label(updated_protocol) if applied else request.get("currentFocus"),
        "createdNodeIds": [item["childNodeId"] for item in applied if item.get("action") == "create" and item.get("childNodeId")],
        "enteredNodeIds": [item["nodeId"] for item in applied if item.get("action") == "enter" and item.get("nodeId")],
    }
    return updated_protocol, updated_stack, {
        "detectedCount": int(action_payload.get("detectedCount") or (len(applied) + len(blocked))),
        "cleanAssistantText": str(action_payload.get("cleanAssistantText") or ""),
        "applied": applied,
        "blocked": blocked,
        **transition,
    }
def _assistant_memory_write_annotation(
    *,
    task,
    run,
    invocation_id: str,
    write: dict[str, Any],
    index: int,
) -> dict[str, Any]:
    return {
        "id": new_id("srcann", task.id, run.id, "assistant-memory-tag", index, stable=True),
        "sourceType": "assistant-memory-tag",
        "sourceRef": {
            "type": "package-entry",
            "locator": f"agent-runtime/runtime/model-invocations/{invocation_id}#memory-write-{index}",
        },
        "excerpt": normalize_excerpt(str(write.get("rawTag") or ""), 240),
        "inferenceSummary": f"Assistant output memory tag ({write.get('action') or 'create'}) was applied at a safe stop.",
        "confidence": 0.95,
        "createdBy": {"type": "module", "id": "runtime-kernel"},
    }
def _apply_memory_write_annotations(
    node_repository: NodeRepository,
    *,
    node_id: str,
    task,
    branch_id: str,
    annotations: list[dict[str, Any]],
) -> None:
    for index, annotation in enumerate([item for item in annotations if isinstance(item, dict)], start=1):
        node_repository.add_source_annotation(
            "node",
            node_id,
            {
                "id": annotation.get("id") or new_id("srcann", node_id, index, stable=True),
                "projectId": task.project_id,
                "branchId": branch_id,
                "sourceType": annotation.get("sourceType") or "memory",
                "sourceRef": annotation.get("sourceRef"),
                "excerpt": annotation.get("excerpt"),
                "inferenceSummary": annotation.get("inferenceSummary") or annotation.get("summary"),
                "evidenceRefs": annotation.get("evidenceRefs") or [],
                "confidence": float(annotation.get("confidence", 0.85)),
                "createdBy": annotation.get("createdBy") or {"type": "module", "id": "runtime-kernel"},
            },
        )
def _apply_assistant_memory_write_tags(
    session,
    *,
    task,
    run,
    request: dict[str, Any],
    root_mount: dict[str, Any],
    execution_root_id: str,
    llm_result: dict[str, Any],
    execution_actor_id: str,
) -> dict[str, Any]:
    memory_tag_writes_enabled = bool(request.get("memoryWriteTagsEnabled", True))
    parsed = _extract_assistant_memory_write_tags(
        str(llm_result.get("assistantText") or ""),
        enabled=memory_tag_writes_enabled,
    )
    llm_result["assistantText"] = parsed["cleanAssistantText"]
    writes = [item for item in parsed["writes"] if isinstance(item, dict)]
    work_tree_node_id = _work_tree_node_id_from_request(request)
    runtime_metrics = request.get("runtimeMetrics") if isinstance(request.get("runtimeMetrics"), dict) else {}
    window_index = max(_int_metric(runtime_metrics.get("windowIndex"), _int_metric(request.get("windowIndex"), 1)), 1)
    if not writes:
        return {
            "detectedCount": int(parsed["detectedCount"]),
            "cleanAssistantText": str(llm_result.get("assistantText") or ""),
            "applied": [],
            "blocked": [dict(item) for item in parsed["blocked"] if isinstance(item, dict)],
            "events": [],
        }

    node_repository = NodeRepository(session)
    applied: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = [dict(item) for item in parsed["blocked"] if isinstance(item, dict)]
    events: list[dict[str, Any]] = []
    active_modules = root_mount.get("activeCapabilities") or None
    subject = request.get("subject") or (f"profile:{task.owner_profile_id}" if task.owner_profile_id else None)
    invocation_id = str((llm_result.get("invocation") or {}).get("id") or run.id)

    for index, write in enumerate(writes, start=1):
        try:
            node_id = str(write.get("nodeId") or "").strip() or None
            existing_node = node_repository.get_node(node_id) if node_id is not None else None
            if node_id is not None and existing_node is None:
                blocked.append(
                    {
                        "status": "blocked",
                        "reason": "missing-node",
                        "nodeId": node_id,
                        "action": write.get("action"),
                    }
                )
                continue

            resolved_root_branch = str(existing_node.root_branch) if existing_node is not None else str(write.get("rootBranch") or "context")
            target_space_id = str(write.get("targetSpaceId") or (existing_node.space_id if existing_node is not None else task.space_id))
            target_branch_id = str(write.get("targetBranchId") or (existing_node.branch_id if existing_node is not None else task.branch_id))
            title = str(write.get("title") or (existing_node.title if existing_node is not None else "")).strip()
            if existing_node is not None:
                if str(write.get("action")) == "replace":
                    content = str(write.get("content") or "").strip()
                else:
                    existing_content = str(existing_node.content or "").strip()
                    new_fragment = str(write.get("content") or "").strip()
                    content = "\n".join(part for part in [existing_content, new_fragment] if part)
            else:
                content = str(write.get("content") or "").strip()

            candidate_parent_id = (
                str(existing_node.parent_id) if existing_node is not None and existing_node.parent_id is not None else None
            )
            if candidate_parent_id is None:
                candidate_parent_id = _target_parent_for_root_branch(
                    task,
                    root_mount=root_mount,
                    execution_root_id=execution_root_id,
                    root_branch=resolved_root_branch,
                    target_branch_id=target_branch_id,
                )
            if candidate_parent_id is None:
                blocked.append(
                    {
                        "status": "blocked",
                        "reason": "missing-parent",
                        "rootBranch": resolved_root_branch,
                        "title": title,
                    }
                )
                continue

            validation_payload = {
                "taskId": task.id,
                "projectId": task.project_id,
                "hostSpaceId": task.space_id,
                "spaceId": task.space_id,
                "branchId": task.branch_id,
                "ownerProfileId": task.owner_profile_id,
                "subject": subject,
                "relation": "write",
                "targetSpaceId": target_space_id,
                "targetBranchId": target_branch_id,
                "nodePayload": {"title": title, "content": content},
                "candidateNodes": [
                    {
                        "id": node_id or new_id("candnode", task.id, run.id, "assistant-memory-tag", index, stable=True),
                        "title": title,
                        "content": content,
                        "parentId": candidate_parent_id,
                        "rootBranch": resolved_root_branch,
                        "nodeType": str(existing_node.node_type) if existing_node is not None else "detail",
                    }
                ],
                "candidateEdges": [],
                "rootMount": root_mount,
            }
            write_validation = validate_memory_write(validation_payload, module_ids=active_modules)
            if not write_validation["allowed"]:
                blocked.append(
                    {
                        "status": "blocked",
                        "reason": "validation-failed",
                        "title": title,
                        "nodeId": node_id,
                        "action": write.get("action"),
                        "blockers": list(write_validation.get("blockers") or []),
                    }
                )
                continue

            resolved_space_id = str(write_validation.get("targetSpaceId") or target_space_id)
            resolved_branch_id = str(write_validation.get("targetBranchId") or target_branch_id)
            if existing_node is not None and (
                resolved_space_id != str(existing_node.space_id) or resolved_branch_id != str(existing_node.branch_id)
            ):
                blocked.append(
                    {
                        "status": "blocked",
                        "reason": "retarget-existing-node-unsupported",
                        "title": title,
                        "nodeId": node_id,
                        "action": write.get("action"),
                    }
                )
                continue

            annotations = [
                _assistant_memory_write_annotation(
                    task=task,
                    run=run,
                    invocation_id=invocation_id,
                    write=write,
                    index=index,
                ),
                *[annotation for annotation in write_validation.get("annotations") or [] if isinstance(annotation, dict)],
            ]

            if existing_node is None:
                if resolved_space_id != task.space_id or resolved_branch_id != task.branch_id:
                    WorkspaceBootstrapRepository(session).ensure_branch_workspace(
                        branch_id=resolved_branch_id,
                        project_id=task.project_id,
                        space_id=resolved_space_id,
                    )
                parent_id = _target_parent_for_root_branch(
                    task,
                    root_mount=root_mount,
                    execution_root_id=execution_root_id,
                    root_branch=resolved_root_branch,
                    target_branch_id=resolved_branch_id,
                )
                if parent_id is None:
                    blocked.append(
                        {
                            "status": "blocked",
                            "reason": "missing-parent",
                            "rootBranch": resolved_root_branch,
                            "title": title,
                        }
                    )
                    continue
                created_node = node_repository.create_node(
                    {
                        "projectId": task.project_id,
                        "spaceId": resolved_space_id,
                        "branchId": resolved_branch_id,
                        "parentId": parent_id,
                        "rootBranch": resolved_root_branch,
                        "nodeType": "detail",
                        "title": title,
                        "content": content,
                        "detailLevel": int(write.get("detailLevel") or 2),
                        "importance": float(write.get("importance", 0.72)),
                        "windowIndex": window_index,
                        "sourceWorkTreeNodeId": work_tree_node_id,
                        "createdBy": {"type": "agent", "id": execution_actor_id},
                        "updatedBy": {"type": "agent", "id": execution_actor_id},
                        "changeReason": "assistant-output-memory-tag",
                    }
                )
                _apply_memory_write_annotations(
                    node_repository,
                    node_id=created_node.id,
                    task=task,
                    branch_id=resolved_branch_id,
                    annotations=annotations,
                )
                event = _persist_runtime_event(
                    session,
                    project_id=task.project_id,
                    aggregate_type="node",
                    aggregate_id=created_node.id,
                    event_type="node.created",
                    locator=f"agent-runtime/tasks/{task.id}/memory-tag-writes/{created_node.id}",
                )
                applied.append(
                    {
                        "status": "created",
                        "nodeId": created_node.id,
                        "title": created_node.title,
                        "rootBranch": created_node.root_branch,
                        "action": write.get("action"),
                    }
                )
                events.append(event.model_dump(by_alias=True, mode="json"))
                continue

            node_repository.append_version(
                existing_node.id,
                {
                    "title": title,
                    "content": content,
                    "importance": float(write.get("importance", existing_node.importance)),
                    "windowIndex": window_index,
                    "sourceWorkTreeNodeId": work_tree_node_id,
                    "changeReason": "assistant-output-memory-tag",
                    "updatedBy": {"type": "agent", "id": execution_actor_id},
                },
            )
            _apply_memory_write_annotations(
                node_repository,
                node_id=existing_node.id,
                task=task,
                branch_id=existing_node.branch_id,
                annotations=annotations,
            )
            event = _persist_runtime_event(
                session,
                project_id=task.project_id,
                aggregate_type="node",
                aggregate_id=existing_node.id,
                event_type="node.updated",
                locator=f"agent-runtime/tasks/{task.id}/memory-tag-writes/{existing_node.id}",
            )
            applied.append(
                {
                    "status": "updated",
                    "nodeId": existing_node.id,
                    "title": title,
                    "rootBranch": existing_node.root_branch,
                    "action": write.get("action"),
                }
            )
            events.append(event.model_dump(by_alias=True, mode="json"))
        except Exception as exc:  # noqa: BLE001
            blocked.append(
                {
                    "status": "blocked",
                    "reason": "unexpected-error",
                    "title": str(write.get("title") or ""),
                    "nodeId": write.get("nodeId"),
                    "action": write.get("action"),
                    "detail": str(exc),
                }
            )

    return {
        "detectedCount": int(parsed["detectedCount"]),
        "cleanAssistantText": str(llm_result.get("assistantText") or ""),
        "applied": applied,
        "blocked": blocked,
        "events": events,
    }
__all__ = [name for name in globals() if not name.startswith("__")]
