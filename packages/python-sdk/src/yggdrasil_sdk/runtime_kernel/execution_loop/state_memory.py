from .state_metrics import *  # noqa: F403,F401
from .state_window import *  # noqa: F403,F401

def _context_parent_for_root_branch(root_mount: dict[str, Any], execution_root_id: str, root_branch: str) -> str | None:
    if root_branch == "identity":
        refs = root_mount.get("identityRefs") or []
        return str(refs[0].get("id")) if refs else None
    if root_branch == "execution":
        return execution_root_id
    refs = root_mount.get("contextRefs") or []
    return str(refs[0].get("id")) if refs else None
def _target_parent_for_root_branch(
    task,
    *,
    root_mount: dict[str, Any],
    execution_root_id: str,
    root_branch: str,
    target_branch_id: str,
) -> str | None:
    if target_branch_id == task.branch_id:
        return _context_parent_for_root_branch(root_mount, execution_root_id, root_branch)
    return str(new_id("node", task.project_id, target_branch_id, root_branch, stable=True))
def _materialize_runtime_context_items(
    session,
    *,
    task,
    current_context: list[dict[str, Any]],
    root_mount: dict[str, Any],
    execution_root_id: str,
    window_index: int,
    source_work_tree_node_id: str | None,
    source_run_id: str | None,
) -> list[str]:
    if not current_context:
        return []

    repository = NodeRepository(session)
    actor = {"type": "module", "id": "runtime-kernel"}
    materialized_node_ids: list[str] = []

    for index, item in enumerate(current_context, start=1):
        if not isinstance(item, dict):
            continue
        if str(item.get("kind") or "") in {"retrieval-summary", "carry-forward-package"}:
            continue
        ref = item.get("ref") if isinstance(item.get("ref"), dict) else None
        if ref and ref.get("kind") == "node" and ref.get("id"):
            materialized_node_ids.append(str(ref["id"]))
            continue

        root_branch = str(item.get("rootBranch") or item.get("mode") or "context")
        if root_branch not in {"identity", "context", "execution"}:
            root_branch = "context"
        parent_id = _context_parent_for_root_branch(root_mount, execution_root_id, root_branch)
        if not parent_id:
            continue

        title = str(item.get("title") or item.get("kind") or f"runtime-context-{index}").strip()
        raw_content = str(
            item.get("content")
            or item.get("summary")
            or item.get("normalizedText")
            or item.get("excerpt")
            or ""
        ).strip()
        if not title or not raw_content:
            continue

        node_id = str(item.get("memoryNodeId") or new_id("runtimectx", task.id, item.get("id") or title, stable=True))
        content = normalize_excerpt(raw_content, 200)
        existing_node = repository.get_node(node_id)
        if existing_node is None:
            repository.create_node(
                {
                    "id": node_id,
                    "projectId": task.project_id,
                    "spaceId": task.space_id,
                    "branchId": task.branch_id,
                    "parentId": parent_id,
                    "rootBranch": root_branch,
                    "nodeType": "temporary",
                    "status": "temporary",
                    "title": title,
                    "content": content,
                    "detailLevel": 2,
                    "importance": float(item.get("importance", 0.6)),
                    "stability": 0.5,
                    "forgetRate": 0.25,
                    "feedforwardScore": 0.7,
                    "accessScore": 0.0,
                    "activityK": 0.4,
                    "floatScore": 0.3,
                    "windowIndex": window_index,
                    "sourceWorkTreeNodeId": source_work_tree_node_id,
                    "sourceRunId": source_run_id,
                    "createdBy": actor,
                    "updatedBy": actor,
                    "changeReason": "runtime-context-materialization",
                }
            )
        else:
            repository.append_version(
                node_id,
                {
                    "title": title,
                    "content": content,
                    "windowIndex": window_index,
                    "sourceWorkTreeNodeId": source_work_tree_node_id,
                    "sourceRunId": source_run_id,
                    "changeReason": "runtime-context-materialization",
                    "updatedBy": actor,
                }
            )
        materialized_node_ids.append(node_id)

    return materialized_node_ids


def _context_item_from_retrieved_node(node_payload: dict[str, Any]) -> dict[str, Any]:
    ref = node_payload.get("ref") if isinstance(node_payload.get("ref"), dict) else None
    content_lines = [str(node_payload.get("content") or "")]
    child_names = [str(item) for item in node_payload.get("childNames") or [] if item]
    related_names = [str(item) for item in node_payload.get("relatedNames") or [] if item]
    if child_names:
        content_lines.append("Children: " + ", ".join(child_names[:8]))
    if related_names:
        content_lines.append("Related: " + ", ".join(related_names[:8]))
    return {
        "id": str((ref or {}).get("id") or node_payload.get("id") or new_id("retrieved-node", node_payload.get("title") or "context")),
        "ref": ref,
        "title": str(node_payload.get("title") or "memory-node"),
        "content": "\n".join(part for part in content_lines if part).strip(),
        "rootBranch": str(node_payload.get("rootBranch") or "context"),
    }
def _memory_retrieval_token_budget(request: dict[str, Any]) -> int | None:
    explicit_budget = max(_int_metric(request.get("maxRetainedTokens"), 0), 0)
    if explicit_budget > 0:
        return explicit_budget

    request_metrics = request.get("runtimeMetrics") if isinstance(request.get("runtimeMetrics"), dict) else {}
    effective_context_window = max(
        _int_metric(request.get("effectiveContextWindow"), _int_metric(request_metrics.get("effectiveContextWindow"), 0)),
        0,
    )
    restart_ratio = _float_metric(request.get("windowRestartRatio"), _float_metric(request_metrics.get("windowRestartRatio"), 0.75))
    restart_ratio = min(max(restart_ratio, 0.1), 1.0)
    restart_threshold = max(
        _int_metric(request.get("windowRestartThreshold"), _int_metric(request_metrics.get("windowRestartThreshold"), 0)),
        0,
    )
    if restart_threshold <= 0 and effective_context_window > 0:
        restart_threshold = max(1, min(effective_context_window, int(effective_context_window * restart_ratio)))

    if restart_threshold > 0:
        return max(32, restart_threshold - 8)
    if effective_context_window > 0:
        return max(32, effective_context_window - 8)
    return None
def _trim_context_items_to_token_budget(context_items: list[dict[str, Any]], token_budget: int | None) -> list[dict[str, Any]]:
    if token_budget is None or token_budget <= 0 or not context_items:
        return context_items

    trimmed_items = [dict(item) for item in context_items if isinstance(item, dict)]
    while len(trimmed_items) > 1 and _estimate_context_tokens(trimmed_items) > token_budget:
        trimmed_items.pop()

    if trimmed_items and _estimate_context_tokens(trimmed_items) > token_budget:
        summary_item = dict(trimmed_items[0])
        summary_content = str(summary_item.get("content") or "")
        target_chars = max(64, token_budget * 4)
        while summary_content and _estimate_context_tokens([summary_item]) > token_budget and len(summary_content) > 64:
            summary_content = normalize_excerpt(summary_content, target_chars)
            summary_item["content"] = summary_content
            target_chars = max(64, len(summary_content) // 2)
        trimmed_items[0] = summary_item

    return trimmed_items
def _count_uncompressed_tail_segments(current_context: list[dict[str, Any]]) -> int | None:
    last_compressed_index = None
    for index, item in enumerate(current_context):
        if not isinstance(item, dict):
            continue
        if str(item.get("kind") or "") == "carry-forward-package":
            last_compressed_index = index
    if last_compressed_index is None:
        return None

    tail_count = 0
    for item in current_context[last_compressed_index + 1 :]:
        if not isinstance(item, dict):
            continue
        if str(item.get("kind") or "") == "carry-forward-package":
            continue
        tail_count += 1
    return tail_count
def _should_trim_retrieved_context(current_context: list[dict[str, Any]], *, request: dict[str, Any] | None = None) -> bool:
    has_compressed_segment = any(
        str(item.get("kind") or "") == "carry-forward-package"
        for item in current_context
        if isinstance(item, dict)
    )
    if not has_compressed_segment:
        return False

    # Auto-decompress when the trailing uncompressed segment count is small enough.
    tail_count = _count_uncompressed_tail_segments(current_context)
    max_tail = _max_uncompressed_tail_before_decompress(request)
    if tail_count is not None and 0 < tail_count <= max_tail:
        return False
    return True
def _parse_memory_write_tag_attributes(attribute_text: str) -> dict[str, str]:
    attributes: dict[str, str] = {}
    for match in _MEMORY_WRITE_ATTR_PATTERN.finditer(attribute_text):
        attributes[str(match.group("name") or "").strip().lower()] = str(match.group("value") or "").strip()
    return attributes
def _normalize_memory_tag_root_branch(value: str | None) -> str:
    candidate = str(value or "context").strip().lower()
    return candidate if candidate in {"identity", "context", "execution"} else "context"
def _normalize_memory_tag_action(value: str | None, *, has_node_id: bool) -> str:
    candidate = str(value or ("append" if has_node_id else "create")).strip().lower()
    return candidate if candidate in {"create", "append", "replace"} else ("append" if has_node_id else "create")
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


def _split_work_tree_node_ids(value: str | None) -> list[str]:
    return [
        normalize_excerpt(str(item).strip(), 120)
        for item in re.split(r"[,|;\n]+", str(value or ""))
        if str(item).strip()
    ]


def _coerce_work_tree_directive_required_config(request: dict[str, Any]) -> dict[str, Any]:
    raw_value = None
    for key in ("workTreeDirectiveRequired", "workTreeDirectiveRequiredOnNaturalLanguage"):
        if key in request:
            raw_value = request.get(key)
            break
    if raw_value is None:
        return {"enabled": True}
    if isinstance(raw_value, bool):
        return {"enabled": raw_value}
    if isinstance(raw_value, dict):
        enabled = raw_value.get("enabled")
        if enabled is None:
            enabled = True
        return {
            "enabled": bool(enabled),
            "message": str(raw_value.get("message") or raw_value.get("correctionMessage") or "").strip(),
        }
    text = str(raw_value).strip()
    if not text or text.lower() in {"0", "false", "no", "off", "disabled"}:
        return {"enabled": False}
    if text.lower() in {"1", "true", "yes", "on", "enabled"}:
        return {"enabled": True}
    return {"enabled": True, "message": text}


def _natural_language_work_tree_claims(text: str) -> list[str]:
    claims: list[str] = []
    for match in _WORK_TREE_NATURAL_LANGUAGE_DIRECTIVE_CLAIM_PATTERN.finditer(str(text or "")):
        claim = normalize_excerpt(str(match.group(0) or "").strip(), 120)
        if claim and claim not in claims:
            claims.append(claim)
    return claims[:8]


def _claims_include_child_delivery(claims: list[str]) -> bool:
    delivery_pattern = re.compile(
        r"(handoff|交接|移交|返回父节点|回到父节点|交给父节点|return(?:ed|ing)?\s+to\s+parent)",
        re.IGNORECASE,
    )
    return any(delivery_pattern.search(str(claim or "")) for claim in claims)


def _blocked_directives_include_child_delivery(blocked: list[dict[str, Any]]) -> bool:
    for item in blocked:
        reason = str(item.get("reason") or "").strip().lower()
        preview = str(item.get("tagPreview") or "").strip().lower()
        if reason in {"missing-completion-summary", "invalid-completion-status"}:
            return True
        if "work-node-complete" in preview or "work-node-handoff" in preview:
            return True
    return False


def _work_tree_valid_delivery_example(current_node_id: str, current_node_title: str) -> str:
    node_label = current_node_title or current_node_id or "当前 child/leaf"
    return (
        "如果当前 child/leaf 已到停止点，正确交付路径是输出一个可应用的完成 directive 并停止，例如：\n"
        '<work-node-complete status="completed">\n'
        f"Scope: {node_label}\n"
        "Result: 已完成本节点负责的具体调查/实现/验证。\n"
        "Evidence: 列出本节点实际使用的工具结果、文件、链接、测试或记忆引用。\n"
        "Gaps/Risks: 列出仍不确定、失败尝试、已废弃路线和风险。\n"
        "Parent next: 请父节点评估本交付，决定继续开下一个 leaf、补证据，或收束最终交付。\n"
        "</work-node-complete>"
    )


def _work_tree_directive_required_transition(
    *,
    request: dict[str, Any],
    takeover_protocol: TaskTakeoverProtocol | None,
    action_payload: dict[str, Any],
    blocked: list[dict[str, Any]],
) -> dict[str, Any] | None:
    config = _coerce_work_tree_directive_required_config(request)
    if not bool(config.get("enabled")):
        return None
    if takeover_protocol is None or takeover_protocol.work_tree is None:
        return None

    assistant_text = str(action_payload.get("cleanAssistantText") or "")
    claims = _natural_language_work_tree_claims(assistant_text)
    malformed_directives = bool(blocked) and int(action_payload.get("detectedCount") or 0) > 0
    if not claims and not malformed_directives:
        return None
    current_node = _current_work_tree_node(takeover_protocol)
    current_node_id = (
        str(takeover_protocol.work_tree.current_node_id or "")
        if takeover_protocol.work_tree is not None
        else ""
    )
    current_node_title = str(getattr(current_node, "title", "") or "").strip()
    reason = "malformed-work-tree-directive" if malformed_directives and not claims else "natural-language-node-switch-without-directive"
    custom_message = str(config.get("message") or "").strip()
    if custom_message:
        correction_message = custom_message
    elif _claims_include_child_delivery(claims) or _blocked_directives_include_child_delivery(blocked):
        correction_message = (
            "工作树流程漂移提醒：你刚才用自然语言声称 leaf handoff/返回父节点，"
            "但 runtime 没有收到可应用的完成 directive，所以当前 child/leaf 没有被标记完成，"
            "父节点也没有拿到可评估的交付。"
            + "\n"
            + _work_tree_valid_delivery_example(current_node_id, current_node_title)
            + "\n不要继续调用资料、搜索、编辑或计算工具；先输出且只输出一个真正的工作树完成 directive。"
        )
    else:
        correction_message = (
            "工作树流程漂移提醒：你刚才用自然语言声称创建、进入或切换工作节点，"
            "但 runtime 没有收到可应用的 <work-node-create ...></work-node-create>、"
            "<work-node-enter nodeId=\"...\"></work-node-enter> 或 "
            '<work-node-complete status="completed">...</work-node-complete> directive，所以工作树状态没有变化。'
            "先输出一个真正的工作树 directive；不要继续调用资料、搜索、编辑或计算工具，也不要把父节点当 leaf 继续执行。"
        )
    return {
        "transition": "work-tree-directive-required",
        "requiresContinuation": True,
        "currentNodeId": current_node_id,
        "nextNodeId": current_node_id,
        "currentFocus": "work-tree-directive-required",
        "reason": reason,
        "detectedClaims": claims,
        "currentNodeTitle": current_node_title,
        "correctionMessage": correction_message,
        "blockedDirectives": blocked,
    }


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
        if action_name in {"skip", "prune"}:
            node_id = str(attributes.get("nodeid") or "").strip()
            node_ids = _split_work_tree_node_ids(attributes.get("nodeids"))
            if node_id and node_id not in node_ids:
                node_ids.insert(0, node_id)
            reason = str(match.group("content") or attributes.get("reason") or "").strip()
            confirm_children = str(attributes.get("confirmchildren") or "").strip().lower() in {
                "1",
                "true",
                "yes",
                "confirmed",
            }
            if not node_ids:
                blocked.append(
                    {
                        "status": "blocked",
                        "reason": "missing-nodeid",
                        "tagPreview": normalize_excerpt(raw_tag, 160),
                    }
                )
                return ""
            if not reason:
                blocked.append(
                    {
                        "status": "blocked",
                        "reason": "missing-skip-reason",
                        "tagPreview": normalize_excerpt(raw_tag, 160),
                    }
                )
                return ""
            parsed_actions.append(
                {
                    "action": "skip",
                    "rawTag": raw_tag,
                    "nodeId": node_ids[0],
                    "nodeIds": node_ids,
                    "reason": reason,
                    "confirmChildren": confirm_children,
                }
            )
            return ""
        if action_name in {"complete", "handoff"}:
            status_raw = str(attributes.get("status") or "completed").strip().lower()
            confirm_children = str(attributes.get("confirmchildren") or "").strip().lower() in {
                "1",
                "true",
                "yes",
                "confirmed",
            }
            if status_raw in {"complete", "done", "success", "succeeded"}:
                status_raw = "completed"
            if status_raw in {"failure", "error"}:
                status_raw = "failed"
            if status_raw not in {"completed", "failed"}:
                blocked.append(
                    {
                        "status": "blocked",
                        "reason": "invalid-completion-status",
                        "statusValue": status_raw,
                        "tagPreview": normalize_excerpt(raw_tag, 160),
                    }
                )
                return ""
            summary = str(match.group("content") or attributes.get("summary") or "").strip()
            if not summary:
                blocked.append(
                    {
                        "status": "blocked",
                        "reason": "missing-completion-summary",
                        "tagPreview": normalize_excerpt(raw_tag, 160),
                    }
                )
                return ""
            parsed_actions.append(
                {
                    "action": "complete",
                    "rawTag": raw_tag,
                    "completionStatus": status_raw,
                    "summary": summary,
                    "confirmChildren": confirm_children,
                }
            )
            return ""
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
        result = {
            "detectedCount": int(action_payload.get("detectedCount") or len(blocked)),
            "cleanAssistantText": str(action_payload.get("cleanAssistantText") or ""),
            "applied": [],
            "blocked": blocked,
        }
        directive_required = _work_tree_directive_required_transition(
            request=request,
            takeover_protocol=takeover_protocol,
            action_payload=action_payload,
            blocked=blocked,
        )
        if directive_required is not None:
            normalized_protocol, normalized_stack = normalize_takeover_runtime_state(
                takeover_protocol,
                task_id=task_id,
                agent_run_id=agent_run_id,
                work_context_stack=work_context_stack,
            )
            if normalized_protocol is not None:
                takeover_protocol = normalized_protocol
                if normalized_protocol.work_tree is not None:
                    directive_required["currentNodeId"] = normalized_protocol.work_tree.current_node_id
                    directive_required["nextNodeId"] = normalized_protocol.work_tree.current_node_id
            if normalized_stack is not None:
                work_context_stack = normalized_stack
            result.update(directive_required)
            result["directiveRequired"] = True
        return takeover_protocol, _coerce_work_context_stack(work_context_stack), result

    current_node = _current_work_tree_node(takeover_protocol)
    default_parent_node_id = (
        current_node.id
        if current_node is not None
        else takeover_protocol.work_tree.current_node_id or takeover_protocol.work_tree.root_node_id
    )
    multi_state_transition_blocked: list[dict[str, Any]] = []
    if len(actions) > 1 and any(str(item.get("action") or "").strip().lower() in {"enter", "complete", "skip"} for item in actions):
        first_action = actions[0]
        for extra_action in actions[1:]:
            multi_state_transition_blocked.append(
                {
                    "status": "blocked",
                    "reason": "multiple-work-tree-state-directives-in-one-window",
                    "action": str(extra_action.get("action") or "").strip() or None,
                    "tagPreview": normalize_excerpt(str(extra_action.get("rawTag") or ""), 160),
                }
            )
        actions = [first_action]
        blocked.extend(multi_state_transition_blocked)

    updated_protocol = takeover_protocol
    updated_stack = _coerce_work_context_stack(work_context_stack)
    applied: list[dict[str, Any]] = []
    action_transition: dict[str, Any] | None = None

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
            elif action_kind == "skip":
                target_node_ids = [
                    str(item).strip()
                    for item in action.get("nodeIds") or [action.get("nodeId")]
                    if str(item).strip()
                ]
                if not target_node_ids:
                    raise ValueError("Missing target work-tree node id.")
                updated_protocol, updated_stack, action_transition = skip_work_tree_nodes(
                    updated_protocol,
                    task_id=task_id,
                    agent_run_id=agent_run_id,
                    node_ids=target_node_ids,
                    reason=str(action.get("reason") or "").strip(),
                    work_context_stack=updated_stack,
                    confirm_children=bool(action.get("confirmChildren")),
                )
                applied.append(
                    {
                        "status": "applied",
                        "action": "skip",
                        "nodeId": target_node_ids[0],
                        "nodeIds": target_node_ids,
                        "summary": normalize_excerpt(str(action.get("reason") or ""), 160),
                        "confirmChildren": bool(action.get("confirmChildren")),
                        "activated": False,
                    }
                )
            elif action_kind == "complete":
                if updated_protocol is None or updated_protocol.work_tree is None:
                    raise ValueError("Takeover protocol does not have a work tree.")
                completed_node = _current_work_tree_node(updated_protocol)
                if completed_node is None:
                    raise ValueError("Current work-tree node is missing.")
                completion_status = str(action.get("completionStatus") or "completed").strip().lower()
                summary = str(action.get("summary") or "").strip()
                if completion_status == "failed":
                    updated_protocol, updated_stack, action_transition = fail_current_work_node(
                        updated_protocol,
                        task_id=task_id,
                        agent_run_id=agent_run_id,
                        failure_summary=summary,
                        work_context_stack=updated_stack,
                    )
                else:
                    updated_protocol, updated_stack, action_transition = complete_current_work_node(
                        updated_protocol,
                        task_id=task_id,
                        agent_run_id=agent_run_id,
                        execution_summary=summary,
                        work_context_stack=updated_stack,
                        evidence_refs=[],
                        confirm_children=bool(action.get("confirmChildren")),
                    )
                applied.append(
                    {
                        "status": "applied",
                        "action": "complete",
                        "nodeId": completed_node.id,
                        "parentNodeId": completed_node.parent_node_id,
                        "completionStatus": completion_status,
                        "summary": normalize_excerpt(summary, 160),
                        "confirmChildren": bool(action.get("confirmChildren")),
                        "activated": False,
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
                    "reason": (
                        "enter-child-failed"
                        if action_kind == "enter"
                        else "complete-child-failed" if action_kind == "complete" else "skip-child-failed" if action_kind == "skip" else "create-child-failed"
                    ),
                    "title": str(action.get("title") or action.get("nodeId") or "").strip() or None,
                    "detail": str(exc),
                }
            )

    if not applied:
        result = {
            "detectedCount": int(action_payload.get("detectedCount") or len(blocked)),
            "cleanAssistantText": str(action_payload.get("cleanAssistantText") or ""),
            "applied": [],
            "blocked": blocked,
        }
        directive_required = _work_tree_directive_required_transition(
            request=request,
            takeover_protocol=takeover_protocol,
            action_payload=action_payload,
            blocked=blocked,
        )
        if directive_required is not None:
            result.update(directive_required)
            result["directiveRequired"] = True
        return updated_protocol, updated_stack, result

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
    if action_transition is not None:
        transition = {
            **action_transition,
            "completedNodeIds": [
                item["nodeId"]
                for item in applied
                if item.get("action") == "complete" and item.get("completionStatus") == "completed" and item.get("nodeId")
            ],
            "failedNodeIds": [
                item["nodeId"]
                for item in applied
                if item.get("action") == "complete" and item.get("completionStatus") == "failed" and item.get("nodeId")
            ],
        }
    else:
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
        }
    transition.update(
        {
            "createdNodeIds": [item["childNodeId"] for item in applied if item.get("action") == "create" and item.get("childNodeId")],
            "enteredNodeIds": [item["nodeId"] for item in applied if item.get("action") == "enter" and item.get("nodeId")],
            "skippedNodeIds": [
                node_id
                for item in applied
                if item.get("action") == "skip"
                for node_id in (item.get("nodeIds") or [item.get("nodeId")])
                if node_id
            ],
        }
    )
    if len(transition.get("skippedNodeIds") or []) == 1:
        transition.setdefault("skippedNodeId", transition["skippedNodeIds"][0])
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
