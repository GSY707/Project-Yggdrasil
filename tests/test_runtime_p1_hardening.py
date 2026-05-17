from __future__ import annotations

from types import SimpleNamespace

import yggdrasil_sdk.prompting as runtime_prompting
import yggdrasil_sdk.runtime_kernel.execution_loop as runtime_execution_loop
import yggdrasil_sdk.runtime_kernel.snapshot as runtime_snapshot
import yggdrasil_sdk.runtime_kernel.takeover as runtime_takeover
from yggdrasil_pause_resume.plugin import PauseResumeModule


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
    content = str(carry_forward[0]["content"])
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
