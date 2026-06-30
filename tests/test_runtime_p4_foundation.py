from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from yggdrasil_agent_runtime.app import app as runtime_app
from yggdrasil_agent_runtime.runtime import build_root_mount_package
import yggdrasil_sdk.runtime_kernel.takeover as runtime_takeover
import yggdrasil_sdk.runtime_kernel.execution_loop as runtime_execution_loop
from yggdrasil_sdk.contracts import TaskTakeoverProtocol
from yggdrasil_sdk import TaskRepository, get_persistence_runtime
from yggdrasil_sdk.persistence.constants import DEFAULT_PROJECT_ID
from yggdrasil_sdk.persistence.repositories import CollaborationRepository, WorkspaceBootstrapRepository
from yggdrasil_task_takeover.plugin import TaskTakeoverModule
from yggdrasil_worker.registry import run_worker_once


client = TestClient(runtime_app)


def _nested_takeover_protocol(task_id: str) -> dict[str, object]:
    return {
        "id": f"takeover_{task_id}",
        "version": "0.1.0",
        "taskId": task_id,
        "taskType": "coding",
        "runType": "main",
        "currentPhase": "execute",
        "status": "executing",
        "objective": "交付多节点最终结果。",
        "objectiveSummary": "先完成两个子节点，再汇总为根节点交付。",
        "ambiguities": [],
        "constraints": [],
        "plan": [
            {
                "id": "step_child_1",
                "title": "完成子节点一",
                "instructions": "完成第一部分交付，并留下可复用摘要。",
                "phase": "execute",
                "status": "completed",
                "dependsOn": [],
                "expectedEvidence": ["child-1"],
            },
            {
                "id": "step_child_2",
                "title": "完成子节点二",
                "instructions": "完成第二部分交付，并留下可复用摘要。",
                "phase": "execute",
                "status": "in-progress",
                "dependsOn": [],
                "expectedEvidence": ["child-2"],
            },
            {
                "id": "step_root",
                "title": "汇总根节点交付",
                "instructions": "整合两个子节点的输出并形成最终答案。",
                "phase": "deliver",
                "status": "pending",
                "dependsOn": ["step_child_1", "step_child_2"],
                "expectedEvidence": ["root-result"],
            },
        ],
        "workTree": {
            "version": "0.2.0",
            "id": f"work_tree_{task_id}",
            "taskId": task_id,
            "rootNodeId": "root",
            "rootObjective": "交付多节点最终结果。",
            "status": "active",
            "currentNodeId": "child-1",
            "loadedNodeIds": ["root", "child-1", "child-2"],
            "activePathNodeIds": ["root", "child-1"],
            "pcMemo": "continue:child-1",
            "entropyBudgetRemaining": 8,
            "versionCounter": 1,
            "nodes": [
                {
                    "id": "root",
                    "title": "汇总根节点交付",
                    "parentNodeId": None,
                    "questionsItAnswers": ["最终交付是什么"],
                    "nodeText": "综合两个子节点的执行结果并生成最终答案。",
                    "localGoal": "综合两个子节点的执行结果并生成最终答案。",
                    "workingNodeAnnotation": "<Working_Node: root>",
                    "phase": "delivery",
                    "status": "in-progress",
                    "childNodeIds": ["child-1", "child-2"],
                    "expectedEvidence": ["root-result"],
                    "detailLevel": 0,
                    "recoveryAnchor": "resume:root",
                },
                {
                    "id": "child-1",
                    "title": "完成子节点一",
                    "parentNodeId": "root",
                    "questionsItAnswers": ["子节点一完成了吗"],
                    "nodeText": "完成第一部分交付。",
                    "localGoal": "完成第一部分交付。",
                    "workingNodeAnnotation": "<Working_Node: child-1>",
                    "phase": "executing",
                    "status": "in-progress",
                    "childNodeIds": [],
                    "planStepIds": ["step_child_1"],
                    "expectedEvidence": ["child-1"],
                    "detailLevel": 1,
                    "recoveryAnchor": "resume:child-1",
                },
                {
                    "id": "child-2",
                    "title": "完成子节点二",
                    "parentNodeId": "root",
                    "questionsItAnswers": ["子节点二完成了吗"],
                    "nodeText": "完成第二部分交付。",
                    "localGoal": "完成第二部分交付。",
                    "workingNodeAnnotation": "<Working_Node: child-2>",
                    "phase": "executing",
                    "status": "pending",
                    "childNodeIds": [],
                    "planStepIds": ["step_child_2"],
                    "expectedEvidence": ["child-2"],
                    "detailLevel": 1,
                    "recoveryAnchor": "resume:child-2",
                },
            ],
        },
        "deliverySections": [],
        "verificationItems": [],
        "metrics": {
            "planQualityScore0_100": 92.0,
            "reworkCount": 0,
            "reworkRate": 0.0,
            "clarificationNeeded": False,
            "deliveryCompletenessScore0_100": 0.0,
            "verificationPassRate": 0.0,
        },
        "appliedModules": ["task-takeover"],
        "hookTrace": [],
    }


def _root_only_takeover_protocol(task_id: str) -> dict[str, object]:
    payload = _nested_takeover_protocol(task_id)
    payload["objective"] = "交付根节点结果。"
    payload["objectiveSummary"] = "当前直接在根节点上生成最终结果。"
    payload["plan"] = []
    payload["workTree"] = {
        "version": "0.2.0",
        "id": f"work_tree_{task_id}",
        "taskId": task_id,
        "rootNodeId": "root",
        "rootObjective": "交付根节点结果。",
        "status": "active",
        "currentNodeId": "root",
        "loadedNodeIds": ["root"],
        "activePathNodeIds": ["root"],
        "pcMemo": "continue:root",
        "entropyBudgetRemaining": 9,
        "versionCounter": 1,
        "nodes": [
            {
                "id": "root",
                "title": "根节点",
                "parentNodeId": None,
                "questionsItAnswers": ["下一步应该做什么"],
                "nodeText": "为根节点创建可执行子任务。",
                "localGoal": "为根节点创建可执行子任务。",
                "workingNodeAnnotation": "<Working_Node: root>",
                "phase": "delivery",
                "status": "in-progress",
                "childNodeIds": [],
                "detailLevel": 0,
                "recoveryAnchor": "resume:root",
            }
        ],
    }
    return payload


def test_create_task_bootstraps_missing_branch_workspace_for_existing_space() -> None:
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        collaboration = CollaborationRepository(session)
        task_repository = TaskRepository(session)
        mounted_space = collaboration.create_space(
            {
                "projectId": DEFAULT_PROJECT_ID,
                "spaceType": "shared",
                "ownerSubject": "profile:p4",
            }
        )
        task = task_repository.create_task(
            {
                "id": "task_p4_bootstrap",
                "projectId": DEFAULT_PROJECT_ID,
                "spaceId": mounted_space.id,
                "branchId": "branch_p4_bootstrap",
                "branchName": "p4-bootstrap",
                "title": "bootstrap task",
                "goal": "ensure workspace is initialized",
            }
        )

    mount_package = build_root_mount_package(task.id)

    assert task.branch_id == "branch_p4_bootstrap"
    assert mount_package["branchId"] == "branch_p4_bootstrap"
    assert mount_package["source"] == "database"
    assert mount_package["executionRefs"][0]["id"] == task.execution_root_node_id


def test_create_task_rejects_branch_space_mismatch() -> None:
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        collaboration = CollaborationRepository(session)
        task_repository = TaskRepository(session)
        first_space = collaboration.create_space(
            {
                "projectId": DEFAULT_PROJECT_ID,
                "spaceType": "shared",
                "ownerSubject": "profile:p4-a",
            }
        )
        second_space = collaboration.create_space(
            {
                "projectId": DEFAULT_PROJECT_ID,
                "spaceType": "shared",
                "ownerSubject": "profile:p4-b",
            }
        )
        branch = collaboration.create_branch(
            {
                "projectId": DEFAULT_PROJECT_ID,
                "spaceId": first_space.id,
                "name": "branch-p4-mismatch",
            }
        )

        with pytest.raises(ValueError, match="does not belong to space"):
            task_repository.create_task(
                {
                    "id": "task_p4_mismatch",
                    "projectId": DEFAULT_PROJECT_ID,
                    "spaceId": second_space.id,
                    "branchId": branch.id,
                    "title": "invalid task",
                    "goal": "should fail",
                }
            )


def test_root_mount_exposes_root_branches_and_startup_contract() -> None:
    mount_package = build_root_mount_package(
        "task_p4_contract",
        {
            "projectId": DEFAULT_PROJECT_ID,
            "spaceId": "space_p4_preview",
            "branchId": "branch_p4_preview",
            "taskObjective": "stabilize startup contract",
            "responseRequirements": "按任务需要说明结果和证据。",
            "restartMessage": "窗口切换后沿当前节点继续。",
        },
    )

    assert mount_package["rootBranches"] == {
        "identity": mount_package["identityRefs"][0]["id"],
        "context": mount_package["contextRefs"][0]["id"],
        "execution": mount_package["executionRefs"][0]["id"],
    }
    assert mount_package["semanticRoots"]["identity"]["label"] == "[ID: 001 我是谁]"
    assert mount_package["systemRootProtocol"]["nodeId"] == "SYS_ROOT_PROTOCOL"
    assert mount_package["startupLoadOrder"] == ["你的能力", "你的工具", "你的工作", "你的知识"]
    assert mount_package["startupMode"] == "bootstrap"
    assert mount_package["startupContract"]["responseRequirements"] == "按任务需要说明结果和证据。"
    assert mount_package["startupContract"]["restartMessage"] == "窗口切换后沿当前节点继续。"


def test_root_mount_preview_without_active_work_enters_standby() -> None:
    mount_package = build_root_mount_package(
        "task_p4_standby_preview",
        {
            "projectId": DEFAULT_PROJECT_ID,
            "spaceId": "space_p4_standby",
            "branchId": "branch_p4_standby",
        },
    )

    assert mount_package["startupMode"] == "standby"
    assert mount_package["standbyState"]["isStandby"] is True
    assert mount_package["mailboxState"]["status"] == "idle"
    assert "currentNodeId" not in mount_package["semanticRoots"]["execution"]
    assert "workingNodeAnnotation" not in mount_package["semanticRoots"]["execution"]


def test_task_takeover_extracts_root_mount_and_startup_contract_constraints() -> None:
    result = TaskTakeoverModule().extract_constraints(
        {
            "request": {},
            "rootMount": {
                "budgetState": {},
                "activeCapabilities": ["task-takeover"],
                "rootBranches": {
                    "identity": "node_identity",
                    "context": "node_context",
                    "execution": "node_execution",
                },
                "startupContract": {
                    "responseRequirements": "必须先给正式交付。",
                    "restartMessage": "按当前 work tree 节点恢复。",
                },
            },
        }
    )

    labels = {item["label"]: item for item in result["constraints"]}
    assert labels["根挂载"]["source"] == "root-mount"
    assert labels["启动合同"]["value"] == "必须先给正式交付。"
    assert labels["重启交接"]["value"] == "按当前 work tree 节点恢复。"


def test_work_tree_bootstraps_pointer_when_plan_is_empty() -> None:
    protocol = runtime_takeover._work_tree_from_protocol_parts(
        task_id="task_p4_work_tree",
        objective="stabilize takeover bootstrap",
        constraints=[],
        plan=[],
        protocol_status="prepared",
    )

    assert protocol.current_node_id is not None
    root_node = next(node for node in protocol.nodes if node.parent_node_id is None)
    bootstrap_node = next(node for node in protocol.nodes if node.id == protocol.current_node_id)
    assert root_node.title == "Establish executable plan"
    assert bootstrap_node.title == "Establish executable plan"
    assert bootstrap_node.parent_node_id is None
    assert bootstrap_node.recovery_anchor == "resume:bootstrap"


def test_takeover_confirmation_gate_is_advisory_unless_explicitly_required() -> None:
    protocol = TaskTakeoverProtocol.model_validate(_root_only_takeover_protocol("task_p4_confirm_gate"))
    advisory = runtime_takeover.enforce_takeover_confirmation_gate(
        protocol,
        request={},
    )
    assert advisory is not None
    assert advisory.status == "executing"
    assert advisory.current_phase == "execute"
    assert advisory.metrics.plan_confirmation_needed is False
    assert advisory.metrics.plan_confirmed is False

    gated = runtime_takeover.enforce_takeover_confirmation_gate(
        protocol,
        request={"requireTakeoverPlanConfirmation": True},
    )
    assert gated is not None
    assert gated.status == "needs-clarification"
    assert gated.current_phase == "confirm"
    assert gated.metrics.plan_confirmation_needed is True

    prepared = runtime_takeover.enforce_takeover_confirmation_gate(
        gated,
        request={"takeoverPlanConfirmed": True},
    )
    assert prepared is not None
    assert prepared.status == "prepared"
    assert prepared.current_phase == "execute"
    assert prepared.metrics.plan_confirmation_needed is False
    assert prepared.metrics.plan_confirmed is True


def test_work_tree_reducer_can_create_child_and_sync_stack() -> None:
    protocol = TaskTakeoverProtocol.model_validate(_root_only_takeover_protocol("task_p4_create_child"))
    protocol, stack = runtime_takeover.normalize_takeover_runtime_state(
        protocol,
        task_id="task_p4_create_child",
        agent_run_id="run_p4_create_child",
    )

    assert protocol is not None
    assert stack is not None
    assert [frame.node_id for frame in stack.frames] == ["root"]
    assert stack.frames[0].prefix_cache_key is not None

    protocol, stack, child_node = runtime_takeover.create_child_work_node(
        protocol,
        task_id="task_p4_create_child",
        agent_run_id="run_p4_create_child",
        title="检查执行证据",
        local_goal="检查执行证据并整理为子节点输入。",
        expected_evidence=["evidence-check"],
        work_context_stack=stack,
    )

    assert child_node.parent_node_id == "root"
    assert protocol.work_tree is not None
    assert protocol.work_tree.current_node_id == child_node.id
    assert [frame.node_id for frame in stack.frames] == ["root", child_node.id]
    assert all(frame.prefix_cache_key for frame in stack.frames)
    assert stack.frames[0].prefix_cache_key != stack.frames[-1].prefix_cache_key
    root_node = next(node for node in protocol.work_tree.nodes if node.id == "root")
    assert child_node.id in root_node.child_node_ids


def test_work_tree_reducer_returns_parent_for_reorchestration_and_waits_for_approval() -> None:
    protocol = TaskTakeoverProtocol.model_validate(_nested_takeover_protocol("task_p4_reducer"))
    protocol, stack = runtime_takeover.normalize_takeover_runtime_state(
        protocol,
        task_id="task_p4_reducer",
        agent_run_id="run_p4_reducer",
    )

    assert protocol is not None
    assert stack is not None
    assert [frame.node_id for frame in stack.frames] == ["root", "child-1"]

    protocol, stack, child_one_transition = runtime_takeover.complete_current_work_node(
        protocol,
        task_id="task_p4_reducer",
        agent_run_id="run_p4_reducer",
        execution_summary="子节点一已经生成可复用摘要。",
        work_context_stack=stack,
    )

    assert child_one_transition["transition"] == "bubble-parent"
    assert protocol.work_tree is not None
    assert protocol.work_tree.current_node_id == "root"
    root_frame = next(frame for frame in stack.frames if frame.node_id == "root")
    assert [item.child_node_id for item in root_frame.child_completion_summaries] == ["child-1"]

    protocol, stack = runtime_takeover.switch_current_work_node(
        protocol,
        task_id="task_p4_reducer",
        agent_run_id="run_p4_reducer",
        node_id="child-2",
        work_context_stack=stack,
        cursor_state="parent-selected-existing-child",
    )

    protocol, stack, child_two_transition = runtime_takeover.complete_current_work_node(
        protocol,
        task_id="task_p4_reducer",
        agent_run_id="run_p4_reducer",
        execution_summary="子节点二也已经完成。",
        work_context_stack=stack,
    )

    assert child_two_transition["transition"] == "bubble-parent"
    assert protocol.work_tree is not None
    assert protocol.work_tree.current_node_id == "root"
    root_frame = next(frame for frame in stack.frames if frame.node_id == "root")
    assert [item.child_node_id for item in root_frame.child_completion_summaries] == ["child-1", "child-2"]

    protocol, stack, root_transition = runtime_takeover.complete_current_work_node(
        protocol,
        task_id="task_p4_reducer",
        agent_run_id="run_p4_reducer",
        execution_summary="根节点已经汇总子节点交付并等待批准。",
        work_context_stack=stack,
    )

    assert root_transition["transition"] == "awaiting-approval"
    assert protocol.work_tree is not None
    assert protocol.work_tree.status == "awaiting-approval"
    assert protocol.status == "verified"
    assert stack.top_frame_id == "frame-root"


def test_work_tree_reducer_continues_next_sibling_after_failed_leaf() -> None:
    protocol = TaskTakeoverProtocol.model_validate(_nested_takeover_protocol("task_p4_failed_leaf_reducer"))
    protocol, stack = runtime_takeover.normalize_takeover_runtime_state(
        protocol,
        task_id="task_p4_failed_leaf_reducer",
        agent_run_id="run_p4_failed_leaf_reducer",
    )

    assert protocol is not None
    assert stack is not None

    protocol, stack, failure_transition = runtime_takeover.fail_current_work_node(
        protocol,
        task_id="task_p4_failed_leaf_reducer",
        agent_run_id="run_p4_failed_leaf_reducer",
        failure_summary="子节点一在窗口阶段失败，需要回到父节点重排。",
        work_context_stack=stack,
    )

    assert failure_transition["transition"] == "bubble-parent-after-failure"
    assert failure_transition["requiresContinuation"] is True
    assert protocol.work_tree is not None
    assert protocol.work_tree.current_node_id == "root"
    assert failure_transition["nextNodeId"] == "root"
    failed_child = next(node for node in protocol.work_tree.nodes if node.id == "child-1")
    assert failed_child.status == "failed"
    assert failed_child.failure_summary is not None
    assert "窗口阶段失败" in failed_child.failure_summary
    root_frame = next(frame for frame in stack.frames if frame.node_id == "root")
    assert [item.child_node_id for item in root_frame.child_completion_summaries] == ["child-1"]
    assert root_frame.child_completion_summaries[0].status == "failed"
    assert stack.top_frame_id == "frame-root"


def test_work_tree_reducer_allows_root_delivery_after_failed_child_summary() -> None:
    protocol = TaskTakeoverProtocol.model_validate(_nested_takeover_protocol("task_p4_failed_leaf_root_delivery"))
    protocol, stack = runtime_takeover.normalize_takeover_runtime_state(
        protocol,
        task_id="task_p4_failed_leaf_root_delivery",
        agent_run_id="run_p4_failed_leaf_root_delivery",
    )

    assert protocol is not None
    assert stack is not None

    protocol, stack, failure_transition = runtime_takeover.fail_current_work_node(
        protocol,
        task_id="task_p4_failed_leaf_root_delivery",
        agent_run_id="run_p4_failed_leaf_root_delivery",
        failure_summary="子节点一失败，但父节点应继续汇总其失败摘要。",
        work_context_stack=stack,
    )

    assert failure_transition["currentNodeId"] == "root"

    protocol, stack = runtime_takeover.switch_current_work_node(
        protocol,
        task_id="task_p4_failed_leaf_root_delivery",
        agent_run_id="run_p4_failed_leaf_root_delivery",
        node_id="child-2",
        work_context_stack=stack,
        cursor_state="parent-selected-existing-child",
    )

    protocol, stack, child_two_transition = runtime_takeover.complete_current_work_node(
        protocol,
        task_id="task_p4_failed_leaf_root_delivery",
        agent_run_id="run_p4_failed_leaf_root_delivery",
        execution_summary="子节点二已经完成真实路径比对。",
        work_context_stack=stack,
    )

    assert child_two_transition["transition"] == "bubble-parent"
    assert protocol.work_tree is not None
    assert protocol.work_tree.current_node_id == "root"

    protocol, stack, root_transition = runtime_takeover.complete_current_work_node(
        protocol,
        task_id="task_p4_failed_leaf_root_delivery",
        agent_run_id="run_p4_failed_leaf_root_delivery",
        execution_summary="根节点已经综合失败子节点与完成子节点的摘要，并等待批准。",
        work_context_stack=stack,
    )

    assert root_transition["transition"] == "awaiting-approval"
    assert protocol.work_tree is not None
    assert protocol.work_tree.status == "awaiting-approval"
    root_frame = next(frame for frame in stack.frames if frame.node_id == "root")
    assert [item.status for item in root_frame.child_completion_summaries] == ["failed", "completed"]


def test_runtime_single_path_moves_root_delivery_to_awaiting_approval(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        TaskRepository(session).create_task(
            {
                "id": "task_p4_awaiting_approval",
                "title": "P4 根节点完成待批准",
                "goal": "验证重做路径下根节点完成进入 awaiting-approval。",
                "status": "draft",
                "currentObjective": "交付最终结果。",
                "currentFocus": "deliver-root-result",
            }
        )

    def _fake_invoke_runtime_completion(*args, **kwargs):  # type: ignore[no-untyped-def]
        return {
            "assistantText": "# result\n已完成最终交付。\n# evidence\n已生成正式答案与验证线索。\n# pending\n无。\n# incomplete\n无。",
            "invocation": {
                "id": "inv_p4_awaiting_approval_1",
                "resolvedModel": "LongCat-2.0",
                "resolvedProvider": "longcat",
                "status": "completed",
                "promptCompileArtifactId": "artifact_p4_awaiting_approval",
                "traceId": "trace_p4_awaiting_approval",
            },
            "usage": {
                "inputTokens": 64,
                "outputTokens": 32,
                "totalTokens": 96,
            },
            "costUsed": 0.0,
            "toolExecutions": [],
            "timings": {
                "compilePromptMs": 0.0,
                "modelToolLoopMs": 0.0,
            },
            "contextLengthObservations": [],
        }

    monkeypatch.setattr(runtime_execution_loop, "invoke_runtime_completion", _fake_invoke_runtime_completion)
    
    started = client.post(
        "/runtime/tasks/task_p4_awaiting_approval/start",
        json={
            "currentObjective": "交付最终结果。",
            "currentFocus": "deliver-root-result",
            "takeoverProtocol": _root_only_takeover_protocol("task_p4_awaiting_approval"),
        },
    )
    assert started.status_code == 202

    processed = run_worker_once("agent-runtime")
    assert processed["status"] == "processed"
    assert processed["result"]["status"] == "awaiting-approval"
    assert processed["result"]["task"]["status"] == "awaiting-approval"
    assert processed["result"]["run"]["status"] == "completed"
    assert processed["result"]["windowExecutionArtifact"]["record"]["transitionOutcome"] == "awaiting-approval"

    takeover_protocol = processed["result"]["takeoverProtocol"]
    assert takeover_protocol is not None
    assert takeover_protocol["workTree"]["status"] == "awaiting-approval"
    assert any(node.get("executionSummary") for node in takeover_protocol["workTree"]["nodes"])

    with runtime.session_scope() as session:
        task = TaskRepository(session).get_task("task_p4_awaiting_approval")
        assert task is not None
        assert task.status == "awaiting-approval"


def test_runtime_default_mode_moves_root_delivery_to_awaiting_approval(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        TaskRepository(session).create_task(
            {
                "id": "task_p4_default_mode_awaiting_approval",
                "title": "P7 默认单路径",
                "goal": "验证默认请求也进入 awaiting-approval。",
                "status": "draft",
                "currentObjective": "交付最终结果。",
                "currentFocus": "deliver-root-result",
            }
        )

    def _fake_invoke_runtime_completion(*args, **kwargs):  # type: ignore[no-untyped-def]
        return {
            "assistantText": "# result\n已完成最终交付。\n# evidence\n已生成正式答案与验证线索。\n# pending\n无。\n# incomplete\n无。",
            "invocation": {
                "id": "inv_p4_default_mode_awaiting_approval_1",
                "resolvedModel": "LongCat-2.0",
                "resolvedProvider": "longcat",
                "status": "completed",
                "promptCompileArtifactId": "artifact_p4_default_mode_awaiting_approval",
                "traceId": "trace_p4_default_mode_awaiting_approval",
            },
            "usage": {
                "inputTokens": 64,
                "outputTokens": 32,
                "totalTokens": 96,
            },
            "costUsed": 0.0,
            "toolExecutions": [],
            "timings": {
                "compilePromptMs": 0.0,
                "modelToolLoopMs": 0.0,
            },
            "contextLengthObservations": [],
        }

    monkeypatch.setattr(runtime_execution_loop, "invoke_runtime_completion", _fake_invoke_runtime_completion)
    
    started = client.post(
        "/runtime/tasks/task_p4_default_mode_awaiting_approval/start",
        json={
            "currentObjective": "交付最终结果。",
            "currentFocus": "deliver-root-result",
            "takeoverProtocol": _root_only_takeover_protocol("task_p4_default_mode_awaiting_approval"),
        },
    )
    assert started.status_code == 202

    processed = run_worker_once("agent-runtime")
    assert processed["status"] == "processed"
    assert processed["result"]["status"] == "awaiting-approval"
    assert processed["result"]["task"]["status"] == "awaiting-approval"
    assert processed["result"]["windowExecutionArtifact"]["record"]["transitionOutcome"] == "awaiting-approval"
    assert processed["result"]["takeoverProtocol"]["workTree"]["status"] == "awaiting-approval"


def test_runtime_parent_reorchestrates_existing_children_then_waits_for_approval(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        TaskRepository(session).create_task(
            {
                "id": "task_p4_multi_node_loop",
                "title": "P4 多节点闭环",
                "goal": "验证 child -> sibling -> parent -> awaiting-approval 闭环。",
                "status": "draft",
                "currentObjective": "完成两个子节点并汇总根节点。",
                "currentFocus": "child-1",
            }
        )

    def _fake_invoke_runtime_completion(*args, **kwargs):  # type: ignore[no-untyped-def]
        request = kwargs["request"]
        current_node_id = str(request.get("currentNodeId") or "")
        root_frame = next(
            (frame for frame in (request.get("workContextStack") or {}).get("frames") or [] if frame.get("nodeId") == "root"),
            None,
        )
        completed_children = [
            str(item.get("childNodeId") or "")
            for item in (root_frame or {}).get("childCompletionSummaries") or []
            if str(item.get("status") or "") == "completed"
        ]
        text_by_node = {
            "child-1": "# result\n子节点一完成。\n# evidence\n子节点一证据齐全。\n# pending\nchild-2。\n# incomplete\n无。",
            "child-2": "# result\n子节点二完成。\n# evidence\n子节点二证据齐全。\n# pending\n汇总 root。\n# incomplete\n无。",
        }
        if current_node_id == "root":
            if completed_children == ["child-1"]:
                assistant_text = "继续由 root 编排并进入 child-2。\n<work-node-enter nodeId=\"child-2\"></work-node-enter>"
            else:
                assistant_text = "# result\n根节点已汇总两个子节点。\n# evidence\n已形成最终答案。\n# pending\n等待批准。\n# incomplete\n无。"
        else:
            assistant_text = text_by_node[current_node_id]
        return {
            "assistantText": assistant_text,
            "invocation": {
                "id": f"inv_{current_node_id}",
                "resolvedModel": "LongCat-2.0",
                "resolvedProvider": "longcat",
                "status": "completed",
                "promptCompileArtifactId": f"artifact_{current_node_id}",
                "traceId": f"trace_{current_node_id}",
            },
            "usage": {
                "inputTokens": 64,
                "outputTokens": 32,
                "totalTokens": 96,
            },
            "costUsed": 0.0,
            "toolExecutions": [],
            "timings": {
                "compilePromptMs": 0.0,
                "modelToolLoopMs": 0.0,
            },
            "contextLengthObservations": [],
        }

    monkeypatch.setattr(runtime_execution_loop, "invoke_runtime_completion", _fake_invoke_runtime_completion)
    
    started = client.post(
        "/runtime/tasks/task_p4_multi_node_loop/start",
        json={
            "currentObjective": "完成两个子节点并汇总根节点。",
            "currentFocus": "child-1",
            "takeoverProtocol": _nested_takeover_protocol("task_p4_multi_node_loop"),
        },
    )
    assert started.status_code == 202

    first = run_worker_once("agent-runtime")
    assert first["status"] == "processed"
    assert first["result"]["status"] == "continuing"
    assert first["result"]["task"]["status"] == "queued"
    assert first["result"]["windowExecutionArtifact"]["record"]["transitionOutcome"] == "bubble-parent"
    assert first["result"]["windowExecutionArtifact"]["record"]["topFramePrefixCacheKey"]
    assert first["result"]["windowExecutionArtifact"]["record"]["workTreeDebug"]["childBubble0_1"] == 1
    assert first["result"]["queuedWorkItem"]["payload"]["payload"]["currentNodeId"] == "root"
    assert first["result"]["queuedWorkItem"]["payload"]["payload"]["workContextStack"]["topFrameId"] == "frame-root"
    assert first["result"]["workContextStackRef"] is not None

    second = run_worker_once("agent-runtime")
    assert second["status"] == "processed"
    assert second["result"]["status"] == "continuing"
    assert second["result"]["task"]["status"] == "queued"
    assert second["result"]["windowExecutionArtifact"]["record"]["transitionOutcome"] == "enter-existing-child"
    assert second["result"]["queuedWorkItem"]["payload"]["payload"]["currentNodeId"] == "child-2"
    assert second["result"]["queuedWorkItem"]["payload"]["payload"]["workContextStack"]["topFrameId"] == "frame-child-2"

    third = run_worker_once("agent-runtime")
    assert third["status"] == "processed"
    assert third["result"]["status"] == "continuing"
    assert third["result"]["task"]["status"] == "queued"
    assert third["result"]["windowExecutionArtifact"]["record"]["transitionOutcome"] == "bubble-parent"
    assert third["result"]["windowExecutionArtifact"]["record"]["workTreeDebug"]["childBubble0_1"] == 1
    assert third["result"]["queuedWorkItem"]["payload"]["payload"]["currentNodeId"] == "root"
    assert third["result"]["queuedWorkItem"]["payload"]["payload"]["workContextStack"]["topFrameId"] == "frame-root"
    root_frame = next(
        frame
        for frame in third["result"]["queuedWorkItem"]["payload"]["payload"]["workContextStack"]["frames"]
        if frame["nodeId"] == "root"
    )
    assert [item["childNodeId"] for item in root_frame["childCompletionSummaries"]] == ["child-1", "child-2"]

    fourth = run_worker_once("agent-runtime")
    assert fourth["status"] == "processed"
    assert fourth["result"]["status"] == "awaiting-approval"
    assert fourth["result"]["task"]["status"] == "awaiting-approval"
    assert fourth["result"]["windowExecutionArtifact"]["record"]["transitionOutcome"] == "awaiting-approval"
    assert fourth["result"]["windowExecutionArtifact"]["record"]["workTreeDebug"]["approvalStop0_1"] == 1
    assert fourth["result"]["takeoverProtocol"]["workTree"]["status"] == "awaiting-approval"

    with runtime.session_scope() as session:
        task = TaskRepository(session).get_task("task_p4_multi_node_loop")
        assert task is not None
        assert task.status == "awaiting-approval"


def test_runtime_single_path_can_expand_work_tree_via_assistant_tag(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        TaskRepository(session).create_task(
            {
                "id": "task_p4_dynamic_child",
                "title": "P4 动态扩树",
                "goal": "验证模型可在正式主循环里创建子节点并继续执行。",
                "status": "draft",
                "currentObjective": "先创建子节点，再完成子节点并回到根节点交付。",
                "currentFocus": "过时 UI 焦点，不应主导工作树指针。",
            }
        )

    def _fake_invoke_runtime_completion(*args, **kwargs):  # type: ignore[no-untyped-def]
        request = kwargs["request"]
        current_node_id = str(request.get("currentNodeId") or "")
        work_tree_nodes = (request.get("takeoverProtocol") or {}).get("workTree", {}).get("nodes") or []
        if current_node_id == "root" and len(work_tree_nodes) == 1:
            return {
                "assistantText": (
                    "先下潜处理细节。\n"
                    '<work-node-create title="收集执行证据" questions="需要哪些关键证据">'
                    "收集关键执行证据并整理可复用输入。"
                    "</work-node-create>"
                ),
                "invocation": {
                    "id": "inv_p4_dynamic_child_root_expand",
                    "resolvedModel": "LongCat-2.0",
                    "resolvedProvider": "longcat",
                    "status": "completed",
                    "promptCompileArtifactId": "artifact_p4_dynamic_child_root_expand",
                    "traceId": "trace_p4_dynamic_child_root_expand",
                },
                "usage": {"inputTokens": 64, "outputTokens": 32, "totalTokens": 96},
                "costUsed": 0.0,
                "toolExecutions": [],
                "timings": {"compilePromptMs": 0.0, "modelToolLoopMs": 0.0},
                "contextLengthObservations": [],
            }
        if current_node_id != "root":
            return {
                "assistantText": "# result\n子节点证据已整理完成。\n# evidence\n已形成证据摘要。\n# pending\n汇总 root。\n# incomplete\n无。",
                "invocation": {
                    "id": "inv_p4_dynamic_child_leaf",
                    "resolvedModel": "LongCat-2.0",
                    "resolvedProvider": "longcat",
                    "status": "completed",
                    "promptCompileArtifactId": "artifact_p4_dynamic_child_leaf",
                    "traceId": "trace_p4_dynamic_child_leaf",
                },
                "usage": {"inputTokens": 64, "outputTokens": 32, "totalTokens": 96},
                "costUsed": 0.0,
                "toolExecutions": [],
                "timings": {"compilePromptMs": 0.0, "modelToolLoopMs": 0.0},
                "contextLengthObservations": [],
            }
        return {
            "assistantText": "# result\n根节点已整合子节点摘要并等待批准。\n# evidence\n已形成最终答案。\n# pending\n等待批准。\n# incomplete\n无。",
            "invocation": {
                "id": "inv_p4_dynamic_child_root_finalize",
                "resolvedModel": "LongCat-2.0",
                "resolvedProvider": "longcat",
                "status": "completed",
                "promptCompileArtifactId": "artifact_p4_dynamic_child_root_finalize",
                "traceId": "trace_p4_dynamic_child_root_finalize",
            },
            "usage": {"inputTokens": 64, "outputTokens": 32, "totalTokens": 96},
            "costUsed": 0.0,
            "toolExecutions": [],
            "timings": {"compilePromptMs": 0.0, "modelToolLoopMs": 0.0},
            "contextLengthObservations": [],
        }

    monkeypatch.setattr(runtime_execution_loop, "invoke_runtime_completion", _fake_invoke_runtime_completion)
    
    started = client.post(
        "/runtime/tasks/task_p4_dynamic_child/start",
        json={
            "currentObjective": "先创建子节点，再完成子节点并回到根节点交付。",
            "currentFocus": "过时 UI 焦点，不应主导工作树指针。",
            "takeoverProtocol": _root_only_takeover_protocol("task_p4_dynamic_child"),
        },
    )
    assert started.status_code == 202

    first = run_worker_once("agent-runtime")
    assert first["status"] == "processed"
    assert first["result"]["status"] == "continuing"
    assert first["result"]["windowExecutionArtifact"]["record"]["transitionOutcome"] == "enter-child"
    assert first["result"]["assistantText"] == "先下潜处理细节。"
    assert first["result"]["workContextStackRef"] is not None
    child_node_id = first["result"]["queuedWorkItem"]["payload"]["payload"]["currentNodeId"]
    assert child_node_id != "root"
    root_node = next(node for node in first["result"]["takeoverProtocol"]["workTree"]["nodes"] if node["id"] == "root")
    assert child_node_id in root_node["childNodeIds"]

    second = run_worker_once("agent-runtime")
    assert second["status"] == "processed"
    assert second["result"]["status"] == "continuing"
    assert second["result"]["windowExecutionArtifact"]["record"]["transitionOutcome"] == "bubble-parent"
    assert second["result"]["queuedWorkItem"]["payload"]["payload"]["currentNodeId"] == "root"

    third = run_worker_once("agent-runtime")
    assert third["status"] == "processed"
    assert third["result"]["status"] == "awaiting-approval"
    assert third["result"]["takeoverProtocol"]["workTree"]["status"] == "awaiting-approval"


def test_runtime_single_path_marks_failed_node_summary_on_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        TaskRepository(session).create_task(
            {
                "id": "task_p4_failed_node",
                "title": "P4 失败节点摘要",
                "goal": "验证异常路径会写回 failed 节点与避坑摘要。",
                "status": "draft",
                "currentObjective": "在根节点上执行并触发异常。",
                "currentFocus": "root",
            }
        )

    def _boom(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("模拟模型调用异常")

    monkeypatch.setattr(runtime_execution_loop, "invoke_runtime_completion", _boom)
    
    started = client.post(
        "/runtime/tasks/task_p4_failed_node/start",
        json={
            "currentObjective": "在根节点上执行并触发异常。",
            "takeoverProtocol": _root_only_takeover_protocol("task_p4_failed_node"),
        },
    )
    assert started.status_code == 202

    processed = run_worker_once("agent-runtime")
    assert processed["status"] == "processed"
    assert processed["result"]["status"] == "failed"

    with runtime.session_scope() as session:
        task_repository = TaskRepository(session)
        task = task_repository.get_task("task_p4_failed_node")
        assert task is not None
        assert task.status == "failed"
        latest_run = task_repository.get_latest_agent_run("task_p4_failed_node")
        assert latest_run is not None
        failed_protocol = runtime_takeover.load_persisted_task_takeover_protocol("task_p4_failed_node", latest_run.id)
        assert failed_protocol is not None
        failed_root = next(node for node in failed_protocol.work_tree.nodes if node.id == "root")
        assert failed_root.status == "failed"
        assert failed_root.failure_summary is not None
        assert "模拟模型调用异常" in failed_root.failure_summary


def test_runtime_window_overflow_bubbles_failed_leaf_to_parent_and_preserves_continuation_policy() -> None:
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        TaskRepository(session).create_task(
            {
                "id": "task_p4_window_overflow_leaf_failure",
                "title": "P4 窗口溢出叶子失败上浮",
                "goal": "验证窗口超限会把当前叶子节点标记为失败并回到父节点，同时保留 continuation 的 provider 约束。",
                "status": "draft",
                "currentObjective": "在 child-1 上触发窗口超限并回到 root。",
                "currentFocus": "child-1",
            }
        )

    started = client.post(
        "/runtime/tasks/task_p4_window_overflow_leaf_failure/start",
        json={
            "currentObjective": "在 child-1 上触发窗口超限并回到 root。",
            "currentFocus": "child-1",
            "currentContext": [
                {
                    "id": "ctx_overflow_leaf",
                    "title": "overflow leaf",
                    "content": "窗口超限叶子失败后要回到父节点。" * 80,
                    "importance": 0.9,
                }
            ],
            "effectiveContextWindow": 120,
            "forcedWindowRestartBudget": 1,
            "allowToolExecution": False,
            "temperature": 0.1,
            "maxTokens": 256,
            "candidateModels": [
                {
                    "model": "LongCat-2.0",
                    "provider": "longcat",
                    "quality": 0.82,
                    "costPer1k": 0.0,
                    "latencyMs": 760,
                    "contextWindow": 128000,
                }
            ],
            "takeoverProtocol": _nested_takeover_protocol("task_p4_window_overflow_leaf_failure"),
        },
    )
    assert started.status_code == 202

    processed = run_worker_once("agent-runtime")
    assert processed["status"] == "processed"
    assert processed["result"]["status"] == "continuing"
    assert processed["result"]["windowExecutionArtifact"]["record"]["transitionOutcome"] == "bubble-parent-after-failure"

    queued_payload = processed["result"]["queuedWorkItem"]["payload"]["payload"]
    assert queued_payload["currentNodeId"] == "root"
    assert queued_payload["allowToolExecution"] is False
    assert queued_payload["temperature"] == 0.1
    assert queued_payload["maxTokens"] == 256
    assert queued_payload["candidateModels"][0]["provider"] == "longcat"
    assert queued_payload["candidateModels"][0]["model"] == "LongCat-2.0"

    queued_protocol = queued_payload["takeoverProtocol"]
    failed_child = next(node for node in queued_protocol["workTree"]["nodes"] if node["id"] == "child-1")
    assert failed_child["status"] == "failed"
    assert "forcedWindowRestartBudget" in str(failed_child["failureSummary"])

    root_frame = next(frame for frame in queued_payload["workContextStack"]["frames"] if frame["nodeId"] == "root")
    assert root_frame["childCompletionSummaries"][0]["childNodeId"] == "child-1"
    assert root_frame["childCompletionSummaries"][0]["status"] == "failed"
    assert queued_payload["workContextStack"]["topFrameId"] == "frame-root"


def test_runtime_provider_exception_leaf_failure_returns_parent_for_reorchestration(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        TaskRepository(session).create_task(
            {
                "id": "task_p4_provider_exception_leaf_failure",
                "title": "P4 provider 异常叶子失败返回父节点",
                "goal": "验证 provider 异常会把当前叶子节点标记 failed 并回到父节点等待重新编排。",
                "status": "draft",
                "currentObjective": "在 child-1 上触发 provider 异常并回到 root。",
                "currentFocus": "child-1",
            }
        )

    def _boom(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("Model provider failed after 4 attempts: transient EOF")

    monkeypatch.setattr(runtime_execution_loop, "invoke_runtime_completion", _boom)
    
    started = client.post(
        "/runtime/tasks/task_p4_provider_exception_leaf_failure/start",
        json={
            "currentObjective": "在 child-1 上触发 provider 异常并回到 root。",
            "currentFocus": "child-1",
            "takeoverProtocol": _nested_takeover_protocol("task_p4_provider_exception_leaf_failure"),
        },
    )
    assert started.status_code == 202

    processed = run_worker_once("agent-runtime")
    assert processed["status"] == "processed"
    assert processed["result"]["status"] == "continuing"
    assert processed["result"]["task"]["status"] == "queued"
    assert processed["result"]["windowExecutionArtifact"]["record"]["transitionOutcome"] == "bubble-parent-after-failure"
    assert processed["result"]["queuedWorkItem"]["payload"]["payload"]["currentNodeId"] == "root"
    assert processed["result"]["queuedWorkItem"]["payload"]["payload"]["workContextStack"]["topFrameId"] == "frame-root"
    failed_child = next(
        node
        for node in processed["result"]["takeoverProtocol"]["workTree"]["nodes"]
        if node["id"] == "child-1"
    )
    assert failed_child["status"] == "failed"
    assert "Model provider failed after 4 attempts" in str(failed_child["failureSummary"])
    root_frame = next(
        frame
        for frame in processed["result"]["queuedWorkItem"]["payload"]["payload"]["workContextStack"]["frames"]
        if frame["nodeId"] == "root"
    )
    assert root_frame["childCompletionSummaries"][0]["childNodeId"] == "child-1"
    assert root_frame["childCompletionSummaries"][0]["status"] == "failed"
