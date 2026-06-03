from .context import *  # noqa: F401,F403
from .context import (
    _cache_package_entry,
    _collect_branch_changes,
    _normalize_actor,
    _record_package_event,
    _root_ids,
    _subagent_work_tree_node_id,
)
from ..contracts import TaskTakeoverProtocol
from ..runtime_kernel.execution_control import post_task_mailbox_message
from ..runtime_kernel.takeover import (
    bootstrap_takeover_state_for_work_node,
    build_takeover_continuation_request,
    load_persisted_task_takeover_protocol,
    load_persisted_work_context_stack,
    merge_child_takeover_completion_into_parent,
    normalize_takeover_runtime_state,
    persist_stack_snapshot,
    persist_task_takeover_protocol,
)

def create_pull_request(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    request = payload or {}
    runtime = get_persistence_runtime()
    coordinator = RedisCoordinator(runtime.settings)
    adapter = GitCollaborationAdapter(request)
    actor = _normalize_actor(request.get("createdBy"), default_id="subagent")
    work_tree_node_id = _subagent_work_tree_node_id(request)
    budget_decision = request.get("subagentBudgetDecision") if isinstance(request.get("subagentBudgetDecision"), dict) else None

    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        collaboration_repository = CollaborationRepository(session)
        source_branch_id = str(request.get("sourceBranchId"))
        target_branch_id = str(request.get("targetBranchId") or DEFAULT_BRANCH_ID)

        source_branch = collaboration_repository.get_branch(source_branch_id)
        if source_branch is None:
            raise KeyError(source_branch_id)
        target_branch = collaboration_repository.get_branch(target_branch_id)
        if target_branch is None:
            raise KeyError(target_branch_id)

        changes = _collect_branch_changes(session, source_branch.id)
        title = str(request.get("title") or f"Merge {source_branch.name} into {target_branch.name}")
        summary = normalize_excerpt(
            str(
                request.get("summary")
                or f"Sub-Agent proposes {len(changes['changedEntities'])} persisted entities from {source_branch.name} into {target_branch.name}."
            ),
            240,
        )
        pr = collaboration_repository.upsert_pull_request(
            PullRequestRecord(
                id=str(request.get("id") or new_id("pr", source_branch.id, target_branch.id)),
                projectId=source_branch.project_id,
                sourceBranchId=source_branch.id,
                targetBranchId=target_branch.id,
                title=title,
                summary=summary,
                status="open",
                createdBy=actor,
                reviewedBy=None,
                externalId=None,
                externalUrl=None,
                mergeCommitRef=None,
                mergedAt=None,
                createdAt=utc_now(),
            )
        )

        manifest_path = f".yggdrasil/collaboration/{source_branch.id}/pull-request.json"
        manifest = {
            "pullRequest": pr.model_dump(by_alias=True, mode="json"),
            "sourceBranch": source_branch.model_dump(by_alias=True, mode="json"),
            "targetBranch": target_branch.model_dump(by_alias=True, mode="json"),
            "sourceTaskId": request.get("sourceTaskId"),
            "sourceRunId": request.get("sourceRunId"),
            "readonlyContextRef": request.get("readonlyContextRef"),
            "changedEntities": changes["changedEntities"],
            "generatedAt": utc_now().isoformat(),
        }
        if work_tree_node_id is not None:
            manifest["workTreeNodeId"] = work_tree_node_id
        if budget_decision is not None:
            manifest["subagentBudgetDecision"] = budget_decision
        git_result = adapter.write_manifest_commit(
            branch_name=source_branch.name,
            base_ref=target_branch.name,
            relative_path=manifest_path,
            payload=manifest,
            commit_message=f"chore(collaboration): open {pr.id}",
        )
        source_branch = collaboration_repository.update_branch(source_branch.id, {"headRef": git_result["headRef"]})

        review_comment = collaboration_repository.add_review_comment(
            ReviewCommentRecord(
                id=new_id("review", pr.id, "open", stable=True),
                prId=pr.id,
                author=ActorRef(type="module", id="subagent-pr"),
                targetKind="package",
                targetId=manifest_path,
                body=normalize_excerpt(
                    f"Review required before merge. Changed entities: {', '.join(entity['id'] for entity in changes['changedEntities'][:6]) or 'none'}.",
                    240,
                ),
                status="open",
                createdAt=utc_now(),
                resolvedAt=None,
            )
        )

        remote_pr = adapter.create_remote_pull_request(
            title=pr.title,
            body=f"{pr.summary}\n\nInternal manifest: {manifest_path}",
            head=source_branch.name,
            base=target_branch.name,
        )
        if remote_pr is not None:
            pr = collaboration_repository.update_pull_request(
                pr.id,
                {
                    "externalId": str(remote_pr.get("number")),
                    "externalUrl": remote_pr.get("html_url"),
                },
            )

        locator = f"collaboration/pull-requests/{pr.id}/current"
        response = {
            "pullRequest": pr.model_dump(by_alias=True, mode="json"),
            "reviewComments": [review_comment.model_dump(by_alias=True, mode="json")],
            "changedEntities": changes["changedEntities"],
            "manifestPath": manifest_path,
            "git": git_result,
            "github": remote_pr,
        }
        if work_tree_node_id is not None:
            response["workTreeNodeId"] = work_tree_node_id
        if budget_decision is not None:
            response["subagentBudgetDecision"] = budget_decision
        _cache_package_entry(coordinator, locator, response)
        pr_created_event = _record_package_event(
            session,
            project_id=pr.project_id,
            aggregate_type="pull-request",
            aggregate_id=pr.id,
            event_type="pr.created",
            locator=locator,
        )

    return {
        **response,
        "outboxRecord": pr_created_event.model_dump(by_alias=True, mode="json"),
    }


def _merge_branch_entities(session, *, source_branch_id: str, target_branch_id: str, actor: ActorRef) -> dict[str, Any]:
    collaboration_repository = CollaborationRepository(session)
    node_repository = NodeRepository(session)
    source_branch = collaboration_repository.get_branch(source_branch_id)
    target_branch = collaboration_repository.get_branch(target_branch_id)
    if source_branch is None or target_branch is None:
        raise KeyError("Source or target branch not found.")

    source_roots = _root_ids(source_branch.project_id, source_branch.id)
    target_roots = _root_ids(target_branch.project_id, target_branch.id)
    source_root_by_id = {node_id: root_branch for root_branch, node_id in source_roots.items()}

    created_nodes: list[dict[str, Any]] = []
    created_edges: list[dict[str, Any]] = []
    created_annotations: list[dict[str, Any]] = []
    node_mapping: dict[str, str] = {}
    edge_mapping: dict[str, str] = {}

    source_nodes = [node for node in node_repository.list_nodes(branch_id=source_branch_id, limit=5000) if node.node_type != "root"]
    for node in source_nodes:
        parent_id = None
        if node.parent_id is not None:
            if node.parent_id in node_mapping:
                parent_id = node_mapping[node.parent_id]
            elif node.parent_id in source_root_by_id:
                parent_id = target_roots[source_root_by_id[node.parent_id]]
        if parent_id is None and node.root_branch in target_roots:
            parent_id = target_roots[node.root_branch]

        created = node_repository.create_node(
            {
                "projectId": target_branch.project_id,
                "spaceId": target_branch.space_id,
                "branchId": target_branch.id,
                "parentId": parent_id,
                "rootBranch": node.root_branch,
                "nodeType": node.node_type,
                "status": "active",
                "title": node.title,
                "content": node.content,
                "detailLevel": node.detail_level,
                "importance": node.importance,
                "stability": node.stability,
                "forgetRate": node.forget_rate,
                "feedforwardScore": node.feedforward_score,
                "accessScore": node.access_score,
                "activityK": node.activity_k,
                "floatScore": node.float_score,
                "createdBy": node.created_by.model_dump(mode="json"),
                "updatedBy": actor.model_dump(mode="json"),
                "changeReason": f"merge-from:{source_branch.id}",
            }
        )
        node_mapping[node.id] = created.id
        created_nodes.append(created.model_dump(by_alias=True, mode="json"))

    for edge in node_repository.list_edges(branch_id=source_branch_id, limit=5000):
        from_node_id = node_mapping.get(edge.from_node_id)
        to_node_id = node_mapping.get(edge.to_node_id)
        if edge.from_node_id in source_root_by_id:
            from_node_id = target_roots[source_root_by_id[edge.from_node_id]]
        if edge.to_node_id in source_root_by_id:
            to_node_id = target_roots[source_root_by_id[edge.to_node_id]]
        if from_node_id is None or to_node_id is None:
            continue
        created = node_repository.create_edge(
            {
                "projectId": target_branch.project_id,
                "spaceId": target_branch.space_id,
                "branchId": target_branch.id,
                "fromNodeId": from_node_id,
                "toNodeId": to_node_id,
                "relationType": edge.relation_type,
                "weight": edge.weight,
                "reason": edge.reason,
                "evidenceAnnotationIds": [],
                "status": "active",
                "createdBy": edge.created_by.model_dump(mode="json"),
                "updatedBy": actor.model_dump(mode="json"),
            }
        )
        edge_mapping[edge.id] = created.id
        created_edges.append(created.model_dump(by_alias=True, mode="json"))

    for annotation in node_repository.list_source_annotations(branch_id=source_branch_id, limit=5000):
        owner_id = annotation.owner_id
        if annotation.owner_kind == "node":
            owner_id = node_mapping.get(annotation.owner_id)
        elif annotation.owner_kind == "edge":
            owner_id = edge_mapping.get(annotation.owner_id)
        if owner_id is None:
            continue
        evidence_refs = []
        for ref in annotation.evidence_refs:
            mapped_id = ref.id
            if ref.kind == "node":
                mapped_id = node_mapping.get(ref.id)
            elif ref.kind == "edge":
                mapped_id = edge_mapping.get(ref.id)
            if mapped_id is None:
                continue
            evidence_refs.append({"kind": ref.kind, "id": mapped_id})
        created = node_repository.add_source_annotation(
            annotation.owner_kind,
            owner_id,
            {
                "projectId": target_branch.project_id,
                "branchId": target_branch.id,
                "sourceType": annotation.source_type,
                "sourceRef": annotation.source_ref.model_dump(mode="json") if annotation.source_ref else None,
                "excerpt": annotation.excerpt,
                "inferenceSummary": annotation.inference_summary,
                "evidenceRefs": evidence_refs,
                "confidence": annotation.confidence,
                "createdBy": annotation.created_by.model_dump(mode="json"),
            },
        )
        created_annotations.append(created.model_dump(by_alias=True, mode="json"))

    return {
        "nodes": created_nodes,
        "edges": created_edges,
        "sourceAnnotations": created_annotations,
        "counts": {
            "nodes": len(created_nodes),
            "edges": len(created_edges),
            "sourceAnnotations": len(created_annotations),
        },
    }


def review_pull_request(pr_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    request = payload or {}
    decision = str(request.get("decision") or "approved").lower()
    if decision in {"approve", "approved"}:
        decision = "approved"
    elif decision in {"reject", "rejected"}:
        decision = "rejected"
    else:
        raise ValueError(f"Unsupported review decision: {decision}")

    runtime = get_persistence_runtime()
    coordinator = RedisCoordinator(runtime.settings)
    adapter = GitCollaborationAdapter(request)
    actor = _normalize_actor(request.get("reviewedBy"), default_id="main-agent")

    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        collaboration_repository = CollaborationRepository(session)
        pull_request = collaboration_repository.get_pull_request(pr_id)
        if pull_request is None:
            raise KeyError(pr_id)
        source_branch = collaboration_repository.get_branch(pull_request.source_branch_id)
        target_branch = collaboration_repository.get_branch(pull_request.target_branch_id)
        if source_branch is None or target_branch is None:
            raise KeyError("Source or target branch missing.")

        review_comment = collaboration_repository.add_review_comment(
            ReviewCommentRecord(
                id=str(request.get("reviewCommentId") or new_id("review", pr_id, decision, utc_now().isoformat())),
                prId=pr_id,
                author=actor,
                targetKind="plan",
                targetId=pr_id,
                body=normalize_excerpt(
                    str(request.get("comment") or f"Pull request {pr_id} reviewed with decision {decision}."),
                    240,
                ),
                status="resolved" if decision == "approved" else "rejected",
                createdAt=utc_now(),
                resolvedAt=utc_now(),
            )
        )

        remote_review = None
        if pull_request.external_id:
            remote_review = adapter.submit_remote_review(
                external_id=pull_request.external_id,
                decision=decision,
                body=review_comment.body,
            )

        pr_status = "approved" if decision == "approved" else "rejected"
        merge_summary = None
        git_merge = None
        remote_merge = None
        merged_at = None
        merge_commit_ref = pull_request.merge_commit_ref

        if decision == "approved" and bool(request.get("mergeImmediately", False)):
            merge_summary = _merge_branch_entities(
                session,
                source_branch_id=source_branch.id,
                target_branch_id=target_branch.id,
                actor=actor,
            )
            git_merge = adapter.merge_branch(
                source_branch=source_branch.name,
                target_branch=target_branch.name,
                message=f"chore(collaboration): merge {pull_request.id}",
            )
            merge_commit_ref = git_merge["mergeCommitRef"]
            if pull_request.external_id:
                remote_merge = adapter.merge_remote_pull_request(external_id=pull_request.external_id, commit_title=pull_request.title)
                if remote_merge is not None and remote_merge.get("sha"):
                    merge_commit_ref = str(remote_merge["sha"])
            merged_at = utc_now()
            pr_status = "merged"
            collaboration_repository.update_branch(source_branch.id, {"status": "merged"})
            collaboration_repository.update_branch(target_branch.id, {"headRef": merge_commit_ref})

        pull_request = collaboration_repository.update_pull_request(
            pr_id,
            {
                "status": pr_status,
                "reviewedBy": actor.model_dump(mode="json"),
                "mergedAt": merged_at,
                "mergeCommitRef": merge_commit_ref,
            },
        )

        locator = f"collaboration/pull-requests/{pr_id}/review/{review_comment.id}"
        response = {
            "pullRequest": pull_request.model_dump(by_alias=True, mode="json"),
            "reviewComment": review_comment.model_dump(by_alias=True, mode="json"),
            "mergeSummary": merge_summary,
            "git": git_merge,
            "githubReview": remote_review,
            "githubMerge": remote_merge,
        }
        _cache_package_entry(coordinator, locator, response)
        reviewed_event = _record_package_event(
            session,
            project_id=pull_request.project_id,
            aggregate_type="pull-request",
            aggregate_id=pull_request.id,
            event_type="pr.reviewed",
            locator=locator,
        )
        merged_event = None
        if pr_status == "merged":
            merged_event = _record_package_event(
                session,
                project_id=pull_request.project_id,
                aggregate_type="pull-request",
                aggregate_id=pull_request.id,
                event_type="pr.merged",
                locator=f"collaboration/pull-requests/{pr_id}/merge",
            )

    return {
        **response,
        "outboxRecords": {
            "reviewed": reviewed_event.model_dump(by_alias=True, mode="json"),
            "merged": merged_event.model_dump(by_alias=True, mode="json") if merged_event is not None else None,
        },
    }


def _coerce_task_takeover_protocol(candidate: Any) -> TaskTakeoverProtocol | None:
    if not isinstance(candidate, dict):
        return None
    try:
        return TaskTakeoverProtocol.model_validate(candidate)
    except Exception:
        return None


def _subagent_completion_summary(request: dict[str, Any], execution_result: dict[str, Any], pr_result: dict[str, Any]) -> str:
    return normalize_excerpt(
        str(
            request.get("parentSummary")
            or pr_result.get("pullRequest", {}).get("summary")
            or execution_result.get("assistantText")
            or execution_result.get("createdNode", {}).get("content")
            or "Sub-agent completed and is ready for parent summarization."
        ),
        240,
    ) or "Sub-agent completed and is ready for parent summarization."


def _publish_subagent_completion_to_parent(
    work_item: dict[str, Any],
    request: dict[str, Any],
    execution_result: dict[str, Any],
    pr_result: dict[str, Any],
) -> dict[str, Any] | None:
    parent_task_id = str(work_item.get("parentTaskId") or request.get("parentTaskId") or "").strip() or None
    if parent_task_id is None:
        return None

    parent_run_id = str(work_item.get("parentRunId") or request.get("parentRunId") or "").strip() or None
    parent_node_id = _subagent_work_tree_node_id(request)
    child_summary = _subagent_completion_summary(request, execution_result, pr_result)
    child_task_id = str(execution_result.get("task", {}).get("id") or request.get("sourceTaskId") or "").strip() or None
    child_run_id = str(execution_result.get("run", {}).get("id") or request.get("sourceRunId") or "").strip() or None
    child_protocol = _coerce_task_takeover_protocol(execution_result.get("takeoverProtocol"))
    evidence_refs = [
        {"kind": "node", "id": execution_result.get("createdNode", {}).get("id")},
        {"kind": "pull-request", "id": pr_result.get("pullRequest", {}).get("id")},
    ]

    wake_request: dict[str, Any] = {}
    merged = False
    latest_parent_run_id: str | None = None
    with get_persistence_runtime().session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        parent_task = task_repository.get_task(parent_task_id)
        if parent_task is None:
            raise KeyError(parent_task_id)

        latest_parent_run = task_repository.get_agent_run(parent_run_id) if parent_run_id is not None else None
        if latest_parent_run is None:
            latest_parent_run = task_repository.get_latest_agent_run(parent_task_id)
        latest_parent_run_id = latest_parent_run.id if latest_parent_run is not None else None

        parent_protocol = (
            load_persisted_task_takeover_protocol(parent_task_id, latest_parent_run.id)
            if latest_parent_run is not None
            else None
        )
        parent_stack = (
            load_persisted_work_context_stack(parent_task_id, latest_parent_run.id)
            if latest_parent_run is not None
            else None
        )

        synthetic_run_id = latest_parent_run_id or new_id("run", parent_task_id, parent_node_id or "mailbox-parent", stable=True)
        if parent_protocol is None and parent_node_id is not None:
            parent_protocol, parent_stack = bootstrap_takeover_state_for_work_node(
                task_id=parent_task_id,
                agent_run_id=synthetic_run_id,
                objective=parent_task.current_objective or parent_task.goal or child_summary,
                work_tree_node_id=parent_node_id,
                current_focus=parent_task.current_focus or child_summary,
            )
        elif parent_protocol is not None and parent_stack is None:
            parent_protocol, parent_stack = normalize_takeover_runtime_state(
                parent_protocol,
                task_id=parent_task_id,
                agent_run_id=synthetic_run_id,
            )

        parent_protocol, parent_stack = merge_child_takeover_completion_into_parent(
            parent_protocol,
            parent_node_id=parent_node_id,
            child_protocol=child_protocol,
            child_task_id=child_task_id,
            child_run_id=child_run_id,
            child_summary=child_summary,
            evidence_refs=evidence_refs,
            work_context_stack=parent_stack,
        )
        merged = parent_protocol is not None and parent_stack is not None and parent_node_id is not None
        if parent_protocol is not None and parent_stack is not None:
            if latest_parent_run is not None:
                persist_task_takeover_protocol(parent_protocol, task_id=parent_task_id, run_id=latest_parent_run.id)
                persist_stack_snapshot(parent_stack, task_id=parent_task_id, run_id=latest_parent_run.id)
            wake_request = build_takeover_continuation_request(
                {
                    "appId": parent_task.app_id,
                    "projectId": parent_task.project_id,
                    "spaceId": parent_task.space_id,
                    "branchId": parent_task.branch_id,
                    "currentObjective": parent_task.current_objective or parent_task.goal or child_summary,
                    "taskObjective": parent_task.current_objective or parent_task.goal or child_summary,
                    "currentFocus": normalize_excerpt(f"Summarize child result: {child_summary}", 96),
                    "budgetState": parent_task.budget.model_dump(by_alias=True, mode="json"),
                },
                protocol=parent_protocol,
                work_context_stack=parent_stack,
                parent_run_id=latest_parent_run_id,
                current_focus=normalize_excerpt(f"Summarize child result: {child_summary}", 96),
            )

    mailbox_result = post_task_mailbox_message(
        parent_task_id,
        {
            "sender": request.get("createdBy") or {"type": "agent", "id": "subagent"},
            "agentRunId": latest_parent_run_id,
            "messageKind": "subagent-completion",
            "subject": f"Sub-agent completed for {parent_node_id or 'parent task'}",
            "body": child_summary,
            "workTreeNodeId": parent_node_id,
            "wakeOnMessage": True,
            "wakeRequest": wake_request,
        },
    )
    return {
        "parentTaskId": parent_task_id,
        "parentRunId": latest_parent_run_id,
        "summary": child_summary,
        "takeoverMerged": merged,
        "mailboxMessage": mailbox_result.get("mailboxMessage"),
        "sideChannelEvent": mailbox_result.get("sideChannelEvent"),
        "wakeResult": mailbox_result.get("wakeResult"),
    }


def execute_subagent_work_item(work_item: dict[str, Any]) -> dict[str, Any]:
    request = work_item.get("payload") if isinstance(work_item.get("payload"), dict) else {}
    readonly_context_ref = request.get("readonlyContextRef") if isinstance(request.get("readonlyContextRef"), dict) else None
    current_context = request.get("currentContext") if isinstance(request.get("currentContext"), list) else None
    if current_context is None and isinstance(readonly_context_ref, dict) and readonly_context_ref.get("locator"):
        readonly_payload = load_package_entry(str(readonly_context_ref["locator"]))
        if isinstance(readonly_payload, dict) and isinstance(readonly_payload.get("contextItems"), list):
            current_context = [item for item in readonly_payload["contextItems"] if isinstance(item, dict)]

    execution_result = execute_main_agent_work_item(
        {
            "activity": "core.agent.main.execute",
            "taskId": work_item.get("taskId"),
            "command": work_item.get("command") or request.get("command") or "start",
            "payload": {
                **request,
                "runType": "subagent",
                "currentContext": current_context or [],
                "executionActorId": str(request.get("executionActorId") or "subagent"),
            },
        }
    )
    execution_status = str(execution_result.get("status") or "failed")
    if execution_status not in {"completed", "awaiting-approval"}:
        return {
            "status": execution_status,
            "taskId": work_item.get("taskId"),
            "execution": execution_result,
        }

    pr_result = create_pull_request(
        {
            **request,
            "sourceBranchId": work_item.get("sourceBranchId") or work_item.get("taskBranchId"),
            "targetBranchId": work_item.get("targetBranchId"),
            "sourceTaskId": work_item.get("taskId"),
            "sourceRunId": execution_result.get("run", {}).get("id"),
            "readonlyContextRef": readonly_context_ref,
            "createdBy": request.get("createdBy") or {"type": "agent", "id": "subagent"},
            "title": request.get("prTitle") or request.get("title") or execution_result.get("task", {}).get("title"),
            "summary": request.get("prSummary") or execution_result.get("createdNode", {}).get("content"),
        }
    )
    parent_followup = _publish_subagent_completion_to_parent(work_item, request, execution_result, pr_result)
    return {
        "status": execution_status,
        "taskId": work_item.get("taskId"),
        "execution": execution_result,
        "pullRequest": pr_result["pullRequest"],
        "reviewComments": pr_result["reviewComments"],
        "manifestPath": pr_result["manifestPath"],
        "git": pr_result.get("git"),
        "github": pr_result.get("github"),
        "outboxRecord": pr_result.get("outboxRecord"),
        "workTreeNodeId": pr_result.get("workTreeNodeId"),
        "subagentBudgetDecision": pr_result.get("subagentBudgetDecision"),
        "parentFollowup": parent_followup,
    }

__all__ = [name for name in globals() if not name.startswith("__")]
