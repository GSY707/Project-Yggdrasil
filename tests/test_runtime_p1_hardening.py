from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import yggdrasil_sdk.prompting as runtime_prompting
import yggdrasil_sdk.runtime_kernel.execution_loop as runtime_execution_loop
import yggdrasil_sdk.runtime_kernel.execution_loop_part_a as runtime_execution_loop_part_a
import yggdrasil_sdk.runtime_kernel.root_mount as runtime_root_mount
import yggdrasil_sdk.runtime_kernel.snapshot as runtime_snapshot
import yggdrasil_sdk.runtime_kernel.takeover as runtime_takeover
from yggdrasil_sdk.contracts import TaskSnapshotSummary, TaskTakeoverProtocol, WorkTreeProtocol
from yggdrasil_pause_resume.plugin import PauseResumeModule
from yggdrasil_context_pruning.plugin import ContextPruningModule


def test_build_restart_request_state_uses_deep_copy_and_keeps_contract_keys() -> None:
    request = {
        "responseRequirements": "必须包含四段交付。",
        "restartMessage": "继续下一窗口。",
        "takeoverProtocol": {
            "workTree": {
                "status": "active",
                "currentNodeId": "node-a",
                "nodes": [],
            }
        },
        "memoryRetrievalState": {
            "requestId": "retr-1",
            "matchedNodeRefs": [{"kind": "node", "id": "n-1"}],
        },
    }
    runtime_metrics = {"windowIndex": 2, "restartCount": 1}

    request_state = runtime_snapshot._build_restart_request_state(request, runtime_metrics)

    request["takeoverProtocol"]["workTree"]["currentNodeId"] = "mutated"
    request["memoryRetrievalState"]["matchedNodeRefs"].append({"kind": "node", "id": "n-2"})

    assert request_state["responseRequirements"] == "必须包含四段交付。"
    assert request_state["restartMessage"] == "继续下一窗口。"
    assert request_state["takeoverProtocol"]["workTree"]["currentNodeId"] == "node-a"
    assert request_state["memoryRetrievalState"]["matchedNodeRefs"] == [{"kind": "node", "id": "n-1"}]


def test_work_tree_node_id_from_request_reads_current_node_memory_state_and_stack() -> None:
    assert runtime_execution_loop_part_a._work_tree_node_id_from_request({"currentNodeId": "node-request"}) == "node-request"
    assert runtime_execution_loop_part_a._work_tree_node_id_from_request(
        {"memoryRetrievalState": {"workTreeNodeId": "node-memory"}}
    ) == "node-memory"
    assert runtime_execution_loop_part_a._work_tree_node_id_from_request(
        {
            "workContextStack": {
                "topFrameId": "frame-1",
                "frames": [
                    {
                        "id": "frame-1",
                        "nodeId": "node-stack",
                        "status": "active",
                    }
                ],
            }
        }
    ) == "node-stack"


def test_resolve_startup_state_prefers_resume_node_before_bootstrap() -> None:
    startup_state = runtime_root_mount._resolve_startup_state(
        {
            "currentNodeId": "node-run",
            "workingNodeAnnotation": "<Working_Node: node-run>",
            "pcMemo": "continue:node-run",
            "currentObjective": "完成当前节点交付",
        },
        task_objective="完成当前节点交付",
        current_focus="deliver",
    )

    assert startup_state["startupMode"] == "resume-node"
    assert startup_state["currentNodeId"] == "node-run"
    assert startup_state["workingNodeAnnotation"] == "<Working_Node: node-run>"
    assert startup_state["pcMemo"] == "continue:node-run"


def test_build_carry_forward_context_dedupes_excerpts_and_preserves_pointer_header() -> None:
    payload = {
        "currentContextState": [
            {
                "id": "ctx-1",
                "title": "重复摘要",
                "summary": "same content",
                "content": "same content",
                "note": "same content",
                "excerpt": "same content",
            }
        ],
        "effectiveContextWindow": 64,
        "windowRestartThreshold": 64,
        "windowIndex": 1,
        "currentObjective": "继续实现",
        "currentFocus": "恢复执行",
        "restartMessage": "按原节点继续",
        "takeoverProtocol": {
            "workTree": {
                "status": "active",
                "currentNodeId": "wt-node-1",
                "recoveryAnchor": "resume:step-1",
            }
        },
        "memoryRetrievalState": {
            "summary": "retrieval summary",
            "reverseTraceMode": True,
            "workTreeNodeId": "wt-node-1",
        },
    }

    carry_forward = runtime_snapshot._build_carry_forward_context("task-cf", payload)

    assert len(carry_forward) == 1
    package = carry_forward[0]["pointerPackage"]
    content = str(carry_forward[0]["content"])
    assert carry_forward[0]["title"] == "Carry-forward execution pointer W1 -> W2"
    assert package["handoffMode"] == "execution-pointer"
    assert package["workTreeCurrentNodeId"] == "wt-node-1"
    assert package["workTreeRecoveryAnchor"] == "resume:step-1"
    assert package["retrievalWorkTreeNodeId"] == "wt-node-1"
    assert package["retrievalFingerprint"] is not None
    assert package["evidenceAnchors"] == [{"title": "重复摘要", "id": "ctx-1", "excerptDigest": package["evidenceAnchors"][0]["excerptDigest"]}]
    assert "Carry-forward execution pointer W1 -> W2" in content
    assert "Execution rule: continue from the same work tree node and delivery contract; do not restart broad planning." in content
    assert "recoveryAnchor=resume:step-1" in content
    assert content.count("same content") == 1


def test_restore_takeover_work_tree_pointer_falls_back_to_nearest_executable_node() -> None:
    protocol = {
        "id": "takeover-1",
        "version": "0.1.0",
        "taskId": "task-1",
        "taskType": "coding",
        "runType": "main",
        "currentPhase": "deliver",
        "status": "verified",
        "objective": "obj",
        "objectiveSummary": "obj",
        "ambiguities": [],
        "constraints": [],
        "plan": [],
        "workTree": {
            "version": "0.1.0",
            "rootObjective": "obj",
            "status": "planned",
            "currentNodeId": "missing-node",
            "nodes": [
                {
                    "id": "node-done",
                    "title": "done",
                    "phase": "planning",
                    "status": "completed",
                    "planStepIds": [],
                    "constraintIds": [],
                    "dependsOn": [],
                    "expectedEvidence": [],
                    "recoveryAnchor": None,
                },
                {
                    "id": "node-run",
                    "title": "run",
                    "phase": "executing",
                    "status": "in-progress",
                    "planStepIds": [],
                    "constraintIds": [],
                    "dependsOn": [],
                    "expectedEvidence": [],
                    "recoveryAnchor": "resume:run",
                },
            ],
            "recoveryAnchor": None,
            "entropyBudgetRemaining": 8,
        },
        "deliverySections": [],
        "verificationItems": [],
        "metrics": {
            "planQualityScore0_100": 90.0,
            "reworkCount": 0,
            "reworkRate": 0.0,
            "clarificationNeeded": False,
            "deliveryCompletenessScore0_100": 0.0,
            "verificationPassRate": 0.0,
        },
        "appliedModules": [],
        "hookTrace": [],
    }

    repaired = runtime_takeover.restore_takeover_work_tree_pointer(protocol)

    assert repaired["workTree"]["currentNodeId"] == "node-run"
    assert repaired["workTree"]["recoveryAnchor"] == "resume:run"
    assert repaired["workTree"]["status"] == "active"


def test_work_tree_protocol_v0_1_payload_upgrades_to_v0_2_with_bootstrap_root() -> None:
    raw_work_tree = {
        "version": "0.1.0",
        "rootObjective": "完成根任务",
        "status": "planned",
        "currentNodeId": "node-run",
        "nodes": [
            {
                "id": "node-run",
                "title": "run",
                "phase": "executing",
                "status": "in-progress",
                "planStepIds": ["step-1"],
                "constraintIds": ["constraint-1"],
                "dependsOn": [],
                "expectedEvidence": ["evidence-1"],
                "recoveryAnchor": "resume:run",
            }
        ],
        "recoveryAnchor": "resume:run",
        "entropyBudgetRemaining": 8,
    }

    protocol = WorkTreeProtocol.model_validate(raw_work_tree)

    assert protocol.version == "0.2.0"
    assert protocol.root_node_id is not None
    assert protocol.current_node_id == "node-run"
    assert protocol.active_path_node_ids == [protocol.root_node_id, "node-run"]
    root_node = next(node for node in protocol.nodes if node.id == protocol.root_node_id)
    run_node = next(node for node in protocol.nodes if node.id == "node-run")
    assert run_node.parent_node_id == protocol.root_node_id
    assert run_node.working_node_annotation == "<Working_Node: node-run>"
    assert run_node.local_goal == "run"
    assert "node-run" in root_node.child_node_ids


def test_task_snapshot_summary_backfills_runtime_pointer_fields_from_legacy_request_state() -> None:
    summary = TaskSnapshotSummary.model_validate(
        {
            "id": "snap-1",
            "appId": "app-1",
            "taskId": "task-1",
            "agentRunId": "run-1",
            "projectId": "project-1",
            "branchId": "branch-1",
            "snapshotType": "pause",
            "status": "restorable",
            "resumeToken": "resume-1",
            "contextRef": {"type": "package-entry", "locator": "runtime/context"},
            "rootMountRef": {"type": "package-entry", "locator": "runtime/root-mount"},
            "pendingWrites": [],
            "pendingActions": [
                {
                    "kind": "runtime-request-state",
                    "requestState": {
                        "takeoverProtocol": {
                            "taskId": "task-1",
                            "workTree": {
                                "version": "0.1.0",
                                "rootObjective": "完成根任务",
                                "status": "active",
                                "currentNodeId": "node-run",
                                "nodes": [
                                    {
                                        "id": "node-run",
                                        "title": "run",
                                        "phase": "executing",
                                        "status": "in-progress",
                                        "planStepIds": ["step-1"],
                                        "constraintIds": [],
                                        "dependsOn": [],
                                        "expectedEvidence": [],
                                        "recoveryAnchor": "resume:run",
                                    }
                                ],
                            },
                        }
                    },
                }
            ],
            "resumeMessage": "继续执行",
            "safeStopReason": "manual-pause",
            "createdAt": datetime.now(timezone.utc),
            "safeToPause": True,
            "blockers": [],
        }
    )

    assert summary.current_node_id == "node-run"
    assert summary.working_node_annotation == "<Working_Node: node-run>"
    assert summary.top_frame_id == "frame-node-run"
    assert summary.stack_digest is not None


def test_build_restart_request_state_bootstraps_work_context_stack_from_legacy_work_tree() -> None:
    request_state = runtime_snapshot._build_restart_request_state(
        {
            "taskId": "task-1",
            "agentRunId": "run-1",
            "takeoverProtocol": {
                "taskId": "task-1",
                "workTree": {
                    "version": "0.1.0",
                    "rootObjective": "完成根任务",
                    "status": "active",
                    "currentNodeId": "node-run",
                    "nodes": [
                        {
                            "id": "node-run",
                            "title": "run",
                            "phase": "executing",
                            "status": "in-progress",
                            "planStepIds": ["step-1"],
                            "constraintIds": [],
                            "dependsOn": [],
                            "expectedEvidence": [],
                            "recoveryAnchor": "resume:run",
                        }
                    ],
                },
            },
            "memoryRetrievalState": {"workTreeNodeId": "node-run"},
        },
        {"windowIndex": 2, "restartCount": 1},
    )

    assert request_state["currentNodeId"] == "node-run"
    assert request_state["workingNodeAnnotation"] == "<Working_Node: node-run>"
    assert request_state["topFrameId"] == "frame-node-run"
    assert request_state["stackDigest"] is not None
    assert request_state["workContextStack"]["topFrameId"] == "frame-node-run"


def test_pause_resume_rehydrate_repairs_takeover_pointer_in_request_updates() -> None:
    snapshot = {
        "id": "snap-1",
        "taskId": "task-1",
        "resumeToken": "resume-1",
        "safeStopReason": "checkpoint",
        "pendingActions": [
            {
                "kind": "runtime-request-state",
                "requestState": {
                    "takeoverProtocol": {
                        "id": "takeover-1",
                        "version": "0.1.0",
                        "taskId": "task-1",
                        "taskType": "coding",
                        "runType": "main",
                        "currentPhase": "deliver",
                        "status": "verified",
                        "objective": "obj",
                        "objectiveSummary": "obj",
                        "ambiguities": [],
                        "constraints": [],
                        "plan": [],
                        "workTree": {
                            "version": "0.1.0",
                            "rootObjective": "obj",
                            "status": "planned",
                            "currentNodeId": "missing",
                            "nodes": [
                                {
                                    "id": "node-run",
                                    "title": "run",
                                    "phase": "executing",
                                    "status": "in-progress",
                                    "planStepIds": [],
                                    "constraintIds": [],
                                    "dependsOn": [],
                                    "expectedEvidence": [],
                                    "recoveryAnchor": "resume:run",
                                }
                            ],
                            "recoveryAnchor": None,
                            "entropyBudgetRemaining": 9,
                        },
                        "deliverySections": [],
                        "verificationItems": [],
                        "metrics": {
                            "planQualityScore0_100": 90.0,
                            "reworkCount": 0,
                            "reworkRate": 0.0,
                            "clarificationNeeded": False,
                            "deliveryCompletenessScore0_100": 0.0,
                            "verificationPassRate": 0.0,
                        },
                        "appliedModules": [],
                        "hookTrace": [],
                    }
                },
            }
        ],
    }

    rehydrated = PauseResumeModule().rehydrate_resume({"taskSnapshot": snapshot, "rootMounts": {}})
    restored_protocol = rehydrated["restoredState"]["requestUpdates"]["takeoverProtocol"]

    assert restored_protocol["workTree"]["currentNodeId"] == "node-run"
    assert restored_protocol["workTree"]["recoveryAnchor"] == "resume:run"


def test_format_response_requirements_resume_path_enforces_delivery_first() -> None:
    seed_template = SimpleNamespace(output_style="concise")

    formatted = runtime_prompting._format_response_requirements(
        request={"memoryWriteTagsEnabled": True},
        seed_template=seed_template,
        resume_path="restart-snapshot",
    )

    assert "result/evidence/pending/incomplete" in formatted
    assert "judgment" in formatted
    assert "默认采用" in formatted
    assert "简洁" in formatted


def test_window_restart_trigger_threshold_boundary_and_forced_budget() -> None:
    trigger_below, span_below = runtime_execution_loop._window_restart_trigger(
        request={},
        runtime_metrics={"effectiveContextWindow": 120, "windowRestartThreshold": 90, "forcedWindowRestartBudget": 0},
        effective_context=[{"id": "x", "content": "a" * 300}],
    )
    assert span_below < 90
    assert trigger_below is None

    trigger_equal, span_equal = runtime_execution_loop._window_restart_trigger(
        request={},
        runtime_metrics={"effectiveContextWindow": 120, "windowRestartThreshold": 90, "forcedWindowRestartBudget": 0},
        effective_context=[{"id": "x", "content": "a" * 360}],
    )
    assert span_equal >= 90
    assert trigger_equal == "effectiveContextWindow"

    trigger_forced, _ = runtime_execution_loop._window_restart_trigger(
        request={},
        runtime_metrics={"effectiveContextWindow": 120, "windowRestartThreshold": 90, "forcedWindowRestartBudget": 1},
        effective_context=[{"id": "x", "content": "tiny"}],
    )
    assert trigger_forced == "forcedWindowRestartBudget"


def test_should_trim_retrieved_context_auto_decompress_default_n_1() -> None:
    # B-only: keep trim to avoid premature re-expansion loops.
    should_trim_b_only = runtime_execution_loop._should_trim_retrieved_context(
        [{"kind": "carry-forward-package", "id": "ctx_b"}],
        request={},
    )
    assert should_trim_b_only is True

    # ...<1>B<3>A<4>A<5> keeps trim because tail=2 > 1
    should_trim_long_tail = runtime_execution_loop._should_trim_retrieved_context(
        [
            {"kind": "carry-forward-package", "id": "ctx_b"},
            {"kind": "retrieval-node", "id": "ctx_a4"},
            {"kind": "retrieval-node", "id": "ctx_a5"},
        ],
        request={},
    )
    assert should_trim_long_tail is True


def test_build_task_takeover_protocol_non_explicit_preserves_plan_work_tree(monkeypatch) -> None:
    def _fake_collect_hook_results(hook_name, payload, module_ids=None):
        if hook_name == runtime_takeover.HookNames.TASK_TAKEOVER_PARSE_OBJECTIVE:
            return [{"moduleId": "task-takeover", "result": {"objective": "执行搜索研究任务", "objectiveSummary": "执行搜索研究任务", "ambiguities": []}}]
        if hook_name == runtime_takeover.HookNames.TASK_TAKEOVER_EXTRACT_CONSTRAINTS:
            return [{"moduleId": "task-takeover", "result": {"constraints": []}}]
        if hook_name == runtime_takeover.HookNames.TASK_TAKEOVER_GENERATE_PLAN:
            return [
                {
                    "moduleId": "task-takeover",
                    "result": {
                        "plan": [
                            {
                                "id": "step-search",
                                "title": "执行检索",
                                "instructions": "收集与目标相关的资料",
                                "phase": "execute",
                                "status": "in-progress",
                                "expectedEvidence": ["检索证据"],
                                "dependsOn": [],
                            },
                            {
                                "id": "step-summarize",
                                "title": "整理结果",
                                "instructions": "形成可交付结论",
                                "phase": "deliver",
                                "status": "pending",
                                "expectedEvidence": ["总结结论"],
                                "dependsOn": ["step-search"],
                            },
                        ],
                        "metrics": {
                            "planQualityScore0_100": 90.0,
                            "reworkCount": 0,
                            "reworkRate": 0.0,
                            "clarificationNeeded": False,
                            "deliveryCompletenessScore0_100": 0.0,
                            "verificationPassRate": 0.0,
                        },
                    },
                }
            ]
        return []

    monkeypatch.setattr(runtime_takeover, "collect_hook_results", _fake_collect_hook_results)

    protocol = runtime_takeover.build_task_takeover_protocol(
        task=SimpleNamespace(id="task-1", task_type="deep-research", run_type="main", goal="执行搜索研究任务"),
        task_type="deep-research",
        run_type="main",
        request={"takeoverPlanConfirmed": True},
        root_mount={"activeCapabilities": ["task-takeover"]},
        current_context=[],
    )

    assert protocol is not None
    assert len(protocol.plan) == 2
    assert protocol.work_tree is not None
    assert len(protocol.work_tree.nodes) >= 2
    assert not (
        len(protocol.work_tree.nodes) == 1
        and protocol.work_tree.root_node_id is not None
        and protocol.work_tree.nodes[0].id == protocol.work_tree.root_node_id
    )


def test_advance_takeover_after_delivery_requires_parent_orchestration_when_children_pending() -> None:
    protocol = TaskTakeoverProtocol.model_validate(
        {
            "id": "takeover-task-1",
            "version": "0.2.0",
            "taskId": "task-1",
            "taskType": "deep-research",
            "runType": "main",
            "currentPhase": "execute",
            "status": "executing",
            "objective": "执行搜索研究任务",
            "objectiveSummary": "执行搜索研究任务",
            "ambiguities": [],
            "constraints": [],
            "plan": [],
            "workTree": {
                "version": "0.2.0",
                "id": "work-tree-task-1",
                "taskId": "task-1",
                "rootNodeId": "root",
                "rootObjective": "执行搜索研究任务",
                "status": "active",
                "currentNodeId": "root",
                "nodes": [
                    {
                        "id": "root",
                        "title": "任务根",
                        "phase": "coordination",
                        "status": "in-progress",
                        "childNodeIds": ["child-a", "child-b"],
                        "planStepIds": [],
                        "constraintIds": [],
                        "dependsOn": [],
                        "expectedEvidence": [],
                    },
                    {
                        "id": "child-a",
                        "title": "子任务A",
                        "parentNodeId": "root",
                        "phase": "executing",
                        "status": "completed",
                        "planStepIds": [],
                        "constraintIds": [],
                        "dependsOn": [],
                        "expectedEvidence": [],
                    },
                    {
                        "id": "child-b",
                        "title": "子任务B",
                        "parentNodeId": "root",
                        "phase": "executing",
                        "status": "in-progress",
                        "planStepIds": [],
                        "constraintIds": [],
                        "dependsOn": [],
                        "expectedEvidence": [],
                    },
                ],
                "loadedNodeIds": ["root", "child-a", "child-b"],
                "activePathNodeIds": ["root"],
                "entropyBudgetRemaining": 8,
                "versionCounter": 1,
            },
            "deliverySections": [],
            "verificationItems": [],
            "metrics": {
                "planQualityScore0_100": 90.0,
                "reworkCount": 0,
                "reworkRate": 0.0,
                "clarificationNeeded": False,
                "deliveryCompletenessScore0_100": 0.0,
                "verificationPassRate": 0.0,
            },
            "appliedModules": [],
            "hookTrace": [],
        }
    )

    next_protocol, _, transition = runtime_takeover.advance_takeover_after_delivery(
        protocol,
        task_id="task-1",
        agent_run_id="run-1",
        assistant_text="完成根节点总结",
    )

    assert next_protocol is not None
    assert next_protocol.work_tree is not None
    assert next_protocol.work_tree.current_node_id == "root"
    assert transition["transition"] == "parent-orchestration-required"
    assert transition["requiresContinuation"] is True
    assert transition["nextNodeId"] == "child-b"
    assert transition["preferredChildNodeId"] == "child-b"
    assert "child-b" in transition["currentFocus"]
    assert transition["pendingChildNodeIds"] == ["child-b"]

    # ...<1>B<3>A<4> auto-decompresses because tail=1 <= 1
    should_trim_short_tail = runtime_execution_loop._should_trim_retrieved_context(
        [
            {"kind": "carry-forward-package", "id": "ctx_b"},
            {"kind": "retrieval-node", "id": "ctx_a4"},
        ],
        request={},
    )
    assert should_trim_short_tail is False


def test_should_trim_retrieved_context_auto_decompress_custom_n() -> None:
    current_context = [
        {"kind": "carry-forward-package", "id": "ctx_b"},
        {"kind": "retrieval-node", "id": "ctx_a4"},
        {"kind": "retrieval-node", "id": "ctx_a5"},
    ]

    # n=2: tail=2 should auto-decompress
    should_trim_n2 = runtime_execution_loop._should_trim_retrieved_context(
        current_context,
        request={"maxUncompressedTailBeforeDecompress": 2},
    )
    assert should_trim_n2 is False

    # n=0: tail=2 should stay compressed/trimmed
    should_trim_n0 = runtime_execution_loop._should_trim_retrieved_context(
        current_context,
        request={"maxUncompressedTailBeforeDecompress": 0},
    )
    assert should_trim_n0 is True


def test_context_pruning_plan_respects_compression_range_guards() -> None:
    module = ContextPruningModule()
    current_context = [
        {
            "id": "ctx_foundation_1",
            "kind": "retrieval-summary",
            "title": "Memory retrieval summary",
            "content": "foundation",
            "importance": 0.9,
        },
        {
            "id": "ctx_foundation_2",
            "kind": "context-item",
            "title": "takeoverProtocol anchor",
            "content": "foundation",
            "importance": 0.9,
        },
        {
            "id": "ctx_mid_1",
            "kind": "context-item",
            "title": "middle 1",
            "content": "x" * 200,
            "importance": 0.1,
        },
        {
            "id": "ctx_mid_2",
            "kind": "context-item",
            "title": "middle 2",
            "content": "y" * 200,
            "importance": 0.1,
        },
        {
            "id": "ctx_tail_1",
            "kind": "context-item",
            "title": "tail 1",
            "content": "z" * 200,
            "importance": 0.1,
        },
        {
            "id": "ctx_tail_2",
            "kind": "context-item",
            "title": "tail 2",
            "content": "w" * 200,
            "importance": 0.1,
        },
    ]

    plan = module.plan(
        {
            "taskId": "task_pruning_range",
            "sourceRunId": "run_pruning_range",
            "nextObjective": "focus middle",
            "budget": {"maxRetainedTokens": 10},
            "maxUncompressedTailBeforeDecompress": 1,
            "currentContext": current_context,
            "protectedItems": [],
        }
    )

    compressed_ids = {ref["id"] for ref in plan.get("compressedRefs", []) if isinstance(ref, dict)}
    dropped_ids = {ref["id"] for ref in plan.get("droppedRefs", []) if isinstance(ref, dict)}
    touched_ids = compressed_ids | dropped_ids

    assert "ctx_foundation_1" not in touched_ids
    assert "ctx_foundation_2" not in touched_ids
    assert "ctx_tail_1" not in touched_ids
    assert "ctx_tail_2" not in touched_ids
    assert plan["compressionRange"]["startIndex"] == 2
    assert plan["compressionRange"]["endIndex"] == 3
