from __future__ import annotations

from yggdrasil_sdk.contracts import TaskTakeoverProtocol, WorkTreeProtocol
from yggdrasil_sdk.runtime_kernel.execution_loop.worker import _inject_work_tree_resolution
from yggdrasil_sdk.runtime_kernel.takeover import advance_takeover_after_delivery
from yggdrasil_sdk.runtime_kernel.work_tree_graph import (
    assess_node_resolution,
    build_long_run_core_frontiers,
    compute_delivery_readiness,
    compute_parent_ready_set,
    plan_fork_batch,
)


def _work_tree(nodes: list[dict[str, object]]) -> WorkTreeProtocol:
    return WorkTreeProtocol.model_validate(
        {
            "id": "wt-fork-test",
            "rootNodeId": "root",
            "rootObjective": "验证工作树图 fork 调度。",
            "status": "active",
            "currentNodeId": "root",
            "nodes": nodes,
        }
    )


def _takeover_protocol(work_tree: WorkTreeProtocol) -> TaskTakeoverProtocol:
    return TaskTakeoverProtocol.model_validate(
        {
            "id": "takeover-resolution-test",
            "taskId": "task-resolution-test",
            "taskType": "coding",
            "runType": "main",
            "currentPhase": "execute",
            "status": "executing",
            "objective": "验证滚动前沿交付控制。",
            "objectiveSummary": "验证滚动前沿交付控制。",
            "workTree": work_tree.model_dump(by_alias=True, mode="json"),
            "metrics": {
                "planQualityScore0_100": 90,
                "reworkCount": 0,
                "reworkRate": 0,
                "clarificationNeeded": False,
                "deliveryCompletenessScore0_100": 0,
                "verificationPassRate": 0,
            },
        }
    )


def _node(
    node_id: str,
    *,
    parent: str | None = "root",
    children: list[str] | None = None,
    depends_on: list[str] | None = None,
    relation_ids: list[str] | None = None,
    priority: int = 100,
    status: str = "pending",
    detail_level: int = 1,
    expected_evidence: list[str] | None = None,
    produced_evidence_refs: list[dict[str, str]] | None = None,
    failure_summary: str | None = None,
    assigned_agent_run_id: str | None = None,
) -> dict[str, object]:
    return {
        "id": node_id,
        "title": node_id,
        "parentNodeId": parent,
        "questionsItAnswers": [node_id],
        "nodeText": node_id,
        "localGoal": node_id,
        "phase": "executing",
        "status": status,
        "childNodeIds": children or [],
        "dependsOn": depends_on or [],
        "relationIds": relation_ids or [],
        "expectedEvidence": expected_evidence or [],
        "producedEvidenceRefs": produced_evidence_refs or [],
        "failureSummary": failure_summary,
        "priority": priority,
        "detailLevel": detail_level,
        "assignedAgentRunId": assigned_agent_run_id,
    }


def test_ready_set_diamond_uses_depends_on_as_hard_block_and_priority_order() -> None:
    work_tree = _work_tree(
        [
            _node("root", parent=None, children=["left", "right", "join"]),
            _node("left", priority=20),
            _node("right", priority=10),
            _node("join", depends_on=["left", "right"], priority=0),
        ]
    )

    result = compute_parent_ready_set(work_tree, "root")

    assert [child.node_id for child in result.ready_children] == ["right", "left"]
    assert [(child.node_id, child.reason, child.blocking_node_ids) for child in result.blocked_children] == [
        ("join", "dependency-not-completed", ["left", "right"])
    ]


def test_ready_set_releases_diamond_join_after_dependencies_complete() -> None:
    work_tree = _work_tree(
        [
            _node("root", parent=None, children=["left", "right", "join"]),
            _node("left", priority=20, status="completed"),
            _node("right", priority=10, status="completed"),
            _node("join", depends_on=["left", "right"], priority=0),
        ]
    )

    result = compute_parent_ready_set(work_tree, "root")

    assert [child.node_id for child in result.ready_children] == ["join"]
    assert {child.node_id: child.reason for child in result.blocked_children} == {
        "left": "terminal",
        "right": "terminal",
    }


def test_delayed_information_flow_attaches_pending_summaries_without_blocking_relation_edges() -> None:
    work_tree = _work_tree(
        [
            _node("root", parent=None, children=["research", "write"]),
            _node("research", status="completed", relation_ids=["rel-source"], priority=10),
            _node("write", relation_ids=["rel-source"], priority=20),
        ]
    )
    graph_state = {
        "pendingInformationItems": [
            {
                "id": "info-1",
                "sourceNodeId": "research",
                "targetNodeId": "write",
                "relationId": "rel-source",
                "relationType": "evidence",
                "category": "summary",
                "summary": "研究节点产出可被写作节点引用。",
                "evidenceRefs": ["artifact://research#summary"],
            }
        ]
    }

    result = compute_parent_ready_set(work_tree, "root", graph_state=graph_state)

    assert [child.node_id for child in result.ready_children] == ["write"]
    assert result.ready_children[0].pending_information_items[0].summary == "研究节点产出可被写作节点引用。"
    assert result.blocked_children[0].node_id == "research"
    assert result.blocked_children[0].reason == "terminal"


def test_auto_batch_pipeline_returns_candidates_limited_by_available_slots() -> None:
    work_tree = _work_tree(
        [
            _node("root", parent=None, children=["a", "b", "c", "d"]),
            _node("a", priority=1),
            _node("b", priority=2),
            _node("c", priority=3),
            _node("d", priority=4),
        ]
    )

    result = compute_parent_ready_set(
        work_tree,
        "root",
        active_runs=[{"id": "fork-existing", "runType": "fork", "status": "running"}],
        policy={"maxForks": 3},
    )

    assert result.active_fork_count == 1
    assert result.available_fork_slots == 2
    assert result.can_auto_launch is True
    assert [candidate.assigned_work_tree_node_id for candidate in result.fork_launch_candidates] == ["a", "b"]

    batch = plan_fork_batch(result, {"maxForks": 3})
    assert [candidate.assigned_work_tree_node_id for candidate in batch.launch_candidates] == ["a", "b"]
    assert [candidate.assigned_work_tree_node_id for candidate in batch.waiting_candidates] == ["c", "d"]


def test_budget_limited_fork_batch_reserves_parent_merge_capacity() -> None:
    child_ids = [f"child-{index}" for index in range(1, 9)]
    work_tree = _work_tree(
        [
            _node("root", parent=None, children=child_ids),
            *[_node(child_id, priority=index) for index, child_id in enumerate(child_ids, start=1)],
        ]
    )

    result = compute_parent_ready_set(
        work_tree,
        "root",
        policy={"maxForks": 4, "reserveParentMergeSlots": 1},
    )
    batch = plan_fork_batch(result, {"maxForks": 4, "reserveParentMergeSlots": 1})

    assert result.active_fork_count == 0
    assert result.available_fork_slots == 3
    assert [candidate.assigned_work_tree_node_id for candidate in result.fork_launch_candidates] == [
        "child-1",
        "child-2",
        "child-3",
    ]
    assert [candidate.assigned_work_tree_node_id for candidate in batch.launch_candidates] == [
        "child-1",
        "child-2",
        "child-3",
    ]
    assert [candidate.assigned_work_tree_node_id for candidate in batch.waiting_candidates] == [
        "child-4",
        "child-5",
        "child-6",
        "child-7",
        "child-8",
    ]
    assert batch.reason == "max-forks"


def test_budget_limited_fork_batch_degrades_to_parent_strategy_when_merge_budget_consumes_slots() -> None:
    work_tree = _work_tree(
        [
            _node("root", parent=None, children=["a", "b", "c"]),
            _node("a", priority=1),
            _node("b", priority=2),
            _node("c", priority=3),
        ]
    )

    result = compute_parent_ready_set(
        work_tree,
        "root",
        active_runs=[{"id": "fork-active", "runType": "fork", "status": "running", "assignedWorkTreeNodeId": "outside"}],
        policy={"maxForks": 3, "reserveParentMergeSlots": 2},
    )

    assert result.ready_children
    assert result.available_fork_slots == 0
    assert result.fork_launch_candidates == []
    assert result.can_auto_launch is False


def test_parent_replan_gate_blocks_auto_launch_when_pending_info_changes_graph_shape() -> None:
    work_tree = _work_tree(
        [
            _node("root", parent=None, children=["next"]),
            _node("next", priority=1),
        ]
    )
    graph_state = {
        "pendingInformationItems": [
            {
                "id": "impact-1",
                "sourceNodeId": "root",
                "targetNodeId": "next",
                "relationType": "proposed-dependency-change",
                "category": "dependency-change",
                "summary": "需要父节点重排依赖。",
            }
        ]
    }

    result = compute_parent_ready_set(work_tree, "root", graph_state=graph_state)

    assert [child.node_id for child in result.ready_children] == ["next"]
    assert result.parent_replan_required is True
    assert result.can_auto_launch is False


def test_recursive_fork_active_limit_counts_only_active_statuses() -> None:
    work_tree = _work_tree(
        [
            _node("root", parent=None, children=["child-a", "child-b"]),
            _node("child-a", priority=1),
            _node("child-b", priority=2),
        ]
    )
    active_runs = [
        {"id": "fork-active-1", "runType": "fork", "status": "running", "assignedWorkTreeNodeId": "other-a"},
        {"id": "fork-active-2", "runType": "fork", "status": "mounting", "assignedWorkTreeNodeId": "other-b"},
        {"id": "fork-active-3", "runType": "fork", "status": "waiting-tool", "assignedWorkTreeNodeId": "other-c"},
        {"id": "fork-done", "runType": "fork", "status": "completed", "assignedWorkTreeNodeId": "other-d"},
        {"id": "main", "runType": "main", "status": "running"},
    ]

    result = compute_parent_ready_set(work_tree, "root", active_runs=active_runs, policy={"maxForks": 3})

    assert result.active_fork_count == 3
    assert result.available_fork_slots == 0
    assert result.ready_children[0].node_id == "child-a"
    assert result.fork_launch_candidates == []
    assert result.can_auto_launch is False


def test_recursive_fork_active_limit_allows_nested_batch_until_global_max_forks() -> None:
    work_tree = _work_tree(
        [
            _node("root", parent=None, children=["a", "b"]),
            _node("a", children=["a1", "a2"], priority=1, status="in-progress"),
            _node("b", children=["b1", "b2"], priority=2, status="in-progress"),
            _node("a1", parent="a", priority=1),
            _node("a2", parent="a", priority=2),
            _node("b1", parent="b", priority=1),
            _node("b2", parent="b", priority=2),
        ]
    )
    active_runs = [
        {"id": "fork-a", "runType": "fork", "status": "running", "forkRootRunId": "run-parent", "forkDepth": 1, "assignedWorkTreeNodeId": "a"},
        {"id": "fork-b", "runType": "fork", "status": "running", "forkRootRunId": "run-parent", "forkDepth": 1, "assignedWorkTreeNodeId": "b"},
    ]

    a_result = compute_parent_ready_set(work_tree, "a", active_runs=active_runs, policy={"maxForks": 5, "allowRecursiveFork": True})
    a_batch = plan_fork_batch(a_result, {"maxForks": 5, "allowRecursiveFork": True})

    assert a_result.active_fork_count == 2
    assert a_result.available_fork_slots == 3
    assert [candidate.assigned_work_tree_node_id for candidate in a_batch.launch_candidates] == ["a1", "a2"]
    assert a_batch.waiting_candidates == []

    active_after_a = [
        *active_runs,
        {"id": "fork-a1", "runType": "fork", "status": "running", "forkRootRunId": "run-parent", "forkDepth": 2, "assignedWorkTreeNodeId": "a1"},
        {"id": "fork-a2", "runType": "fork", "status": "running", "forkRootRunId": "run-parent", "forkDepth": 2, "assignedWorkTreeNodeId": "a2"},
    ]
    b_result = compute_parent_ready_set(work_tree, "b", active_runs=active_after_a, policy={"maxForks": 5, "allowRecursiveFork": True})
    b_batch = plan_fork_batch(b_result, {"maxForks": 5, "allowRecursiveFork": True})

    assert b_result.active_fork_count == 4
    assert b_result.available_fork_slots == 1
    assert [candidate.assigned_work_tree_node_id for candidate in b_batch.launch_candidates] == ["b1"]
    assert [candidate.assigned_work_tree_node_id for candidate in b_batch.waiting_candidates] == ["b2"]


def test_recursive_fork_disabled_keeps_child_ready_set_but_blocks_fork_launch() -> None:
    work_tree = _work_tree(
        [
            _node("root", parent=None, children=["a"]),
            _node("a", children=["a1", "a2"], status="in-progress"),
            _node("a1", parent="a", priority=1),
            _node("a2", parent="a", priority=2),
        ]
    )

    result = compute_parent_ready_set(work_tree, "a", policy={"maxForks": 5, "allowRecursiveFork": False})

    assert [child.node_id for child in result.ready_children] == ["a1", "a2"]
    assert result.available_fork_slots == 0
    assert result.fork_launch_candidates == []
    assert result.can_auto_launch is False


def test_stale_assigned_run_id_does_not_block_without_active_run_view() -> None:
    work_tree = _work_tree(
        [
            _node("root", parent=None, children=["child"]),
            _node("child", assigned_agent_run_id="fork-completed-earlier"),
        ]
    )

    result = compute_parent_ready_set(
        work_tree,
        "root",
        active_runs=[{"id": "fork-completed-earlier", "runType": "fork", "status": "completed"}],
    )

    assert [child.node_id for child in result.ready_children] == ["child"]
    assert result.blocked_children == []


def test_resolution_controller_keeps_broad_root_flexible_instead_of_delivering() -> None:
    work_tree = _work_tree(
        [
            _node(
                "root",
                parent=None,
                children=[],
                detail_level=0,
                expected_evidence=["queue", "snapshot", "merge", "evaluation"],
                status="in-progress",
            ),
        ]
    )

    assessment = assess_node_resolution(work_tree, "root")

    assert assessment.recommended_action == "refine"
    assert assessment.frontier_pressure >= 0.65
    assert any(frontier.axis == "deliverable" for frontier in assessment.frontiers)
    assert assessment.delivery_readiness.ready is False


def test_candidate_delivery_is_summary_only_when_children_and_frontiers_are_open() -> None:
    work_tree = _work_tree(
        [
            _node("root", parent=None, children=["plan", "runtime"], status="in-progress"),
            _node("plan", priority=1, status="completed", produced_evidence_refs=[{"kind": "artifact", "id": "plan-summary"}]),
            _node("runtime", priority=2, status="pending"),
        ]
    )

    assessment = assess_node_resolution(
        work_tree,
        "root",
        graph_state={"candidateDeliveryText": "I am done."},
    )
    readiness = compute_delivery_readiness(
        work_tree,
        node_id="root",
        graph_state={
            "frontierItems": [
                frontier.model_dump(by_alias=True, mode="json") for frontier in assessment.frontiers
            ]
        },
    )

    assert assessment.recommended_action in {"refine", "merge"}
    assert readiness.ready is False
    assert "unresolved-children" in readiness.blockers
    assert "open-frontier-pressure" in readiness.blockers
    assert any(frontier.id.endswith("premature-candidate-delivery") for frontier in assessment.frontiers)


def test_failure_budget_pushes_same_resolution_retry_into_refine() -> None:
    work_tree = _work_tree(
        [
            _node("root", parent=None, children=["migration"]),
            _node("migration", priority=1, status="in-progress", detail_level=2),
        ]
    )

    assessment = assess_node_resolution(
        work_tree,
        "migration",
        graph_state={"failureAttempts": {"migration": 2}},
        policy={"failureRetryBudget": 1},
    )

    assert assessment.recommended_action == "refine"
    assert any(frontier.axis == "failure" for frontier in assessment.frontiers)
    assert "frontier-pressure-above-refine-threshold" in assessment.reasons


def test_completed_root_with_low_frontier_pressure_can_deliver() -> None:
    work_tree = _work_tree(
        [
            _node(
                "root",
                parent=None,
                status="completed",
                expected_evidence=["summary"],
                produced_evidence_refs=[{"kind": "artifact", "id": "root-summary"}],
            ),
        ]
    )

    assessment = assess_node_resolution(work_tree, "root")

    assert assessment.recommended_action == "deliver"
    assert assessment.delivery_readiness.ready is True


def test_in_progress_delivery_readiness_blocks_missing_expected_evidence() -> None:
    work_tree = _work_tree(
        [
            _node(
                "root",
                parent=None,
                status="in-progress",
                expected_evidence=["implementation proof"],
            ),
        ]
    )

    readiness = compute_delivery_readiness(work_tree, node_id="root")

    assert readiness.ready is False
    assert "missing-target-evidence" in readiness.blockers


def test_long_run_core_frontiers_cover_all_eight_required_gaps() -> None:
    frontiers = build_long_run_core_frontiers("root")

    assert len(frontiers) == 8
    assert {frontier.id for frontier in frontiers} == {
        "queue-reliability",
        "durable-snapshot",
        "transactional-node",
        "plan-lifecycle",
        "typed-merge",
        "semantic-gc",
        "long-run-eval",
        "observability-replay",
    }
    assert all(frontier.node_id == "root" for frontier in frontiers)
    assert all(frontier.status == "open" for frontier in frontiers)


def test_takeover_delivery_treats_open_resolution_frontier_as_advisory() -> None:
    work_tree = _work_tree(
        [
            _node("root", parent=None, children=["analysis"], status="in-progress"),
            _node(
                "analysis",
                priority=1,
                status="completed",
                produced_evidence_refs=[{"kind": "artifact", "id": "analysis-summary"}],
            ),
        ]
    )

    protocol, stack, transition = advance_takeover_after_delivery(
        _takeover_protocol(work_tree),
        task_id="task-resolution-test",
        agent_run_id="run-resolution-test",
        assistant_text="## 结果\n已完成。",
        work_tree_resolution={
            "nodeId": "root",
            "recommendedAction": "work",
            "frontierPressure": 0.9,
            "saturation": 0.1,
            "frontiers": [
                {
                    "id": "root:verification-gap",
                    "nodeId": "root",
                    "axis": "verification",
                    "description": "final delivery still lacks independent verification",
                    "severity": 0.9,
                    "status": "open",
                }
            ],
            "deliveryReadiness": {"ready": False, "blockers": ["open-frontier-pressure"]},
            "reasons": ["delivery-blocked:open-frontier-pressure"],
        },
    )

    assert protocol is not None
    assert protocol.status == "verified"
    assert protocol.work_tree is not None
    assert protocol.work_tree.status == "awaiting-approval"
    assert stack is not None
    assert transition["transition"] == "awaiting-approval"


def test_takeover_delivery_blocks_missing_expected_evidence_before_completion() -> None:
    work_tree = _work_tree(
        [
            _node(
                "root",
                parent=None,
                status="in-progress",
                expected_evidence=["implementation proof"],
            ),
        ]
    )
    assessment = assess_node_resolution(work_tree, "root")

    protocol, _, transition = advance_takeover_after_delivery(
        _takeover_protocol(work_tree),
        task_id="task-resolution-test",
        agent_run_id="run-resolution-test",
        assistant_text="## 结果\n已完成。",
        evidence_refs=[],
        work_tree_resolution=assessment.model_dump(by_alias=True, mode="json"),
    )

    assert protocol is not None
    assert protocol.work_tree is not None
    assert protocol.work_tree.status == "active"
    assert transition["transition"] == "work-tree-resolution-blocked"
    assert "missing-target-evidence" in transition["deliveryReadiness"]["blockers"]


def test_takeover_delivery_treats_upstream_not_ready_without_hard_blocker_as_advisory() -> None:
    work_tree = _work_tree(
        [
            _node("root", parent=None, status="in-progress"),
        ]
    )

    _, _, transition = advance_takeover_after_delivery(
        _takeover_protocol(work_tree),
        task_id="task-resolution-test",
        agent_run_id="run-resolution-test",
        assistant_text="## 结果\n已完成。",
        work_tree_resolution={
            "nodeId": "root",
            "recommendedAction": "work",
            "frontierPressure": 0,
            "saturation": 1,
            "frontiers": [],
            "deliveryReadiness": {
                "ready": False,
                "blockers": ["policy-not-ready"],
            },
            "reasons": ["delivery-blocked:policy-not-ready"],
        },
    )

    assert transition["transition"] == "awaiting-approval"


def test_turn_evidence_satisfies_missing_evidence_frontier_and_is_persisted_on_completion() -> None:
    work_tree = _work_tree(
        [
            _node(
                "root",
                parent=None,
                status="in-progress",
                expected_evidence=["implementation proof"],
            ),
        ]
    )
    assessment = assess_node_resolution(work_tree, "root")

    protocol, _, transition = advance_takeover_after_delivery(
        _takeover_protocol(work_tree),
        task_id="task-resolution-test",
        agent_run_id="run-resolution-test",
        assistant_text="## 结果\n已完成。",
        evidence_refs=[{"kind": "node", "id": "evidence-node"}],
        work_tree_resolution=assessment.model_dump(by_alias=True, mode="json"),
    )

    assert protocol is not None
    assert protocol.work_tree is not None
    assert transition["transition"] == "awaiting-approval"
    root_node = next(node for node in protocol.work_tree.nodes if node.id == "root")
    assert [ref.model_dump() for ref in root_node.produced_evidence_refs] == [
        {"kind": "node", "id": "evidence-node"}
    ]


def test_worker_resolution_injection_clears_stale_payload_on_assessment_failure() -> None:
    request = {
        "currentNodeId": "missing-node",
        "workTreeResolution": {"nodeId": "stale"},
    }
    root_mount = {"workTreeResolution": {"nodeId": "stale"}}
    work_tree = _work_tree([_node("root", parent=None, status="in-progress")])

    result = _inject_work_tree_resolution(request, root_mount, _takeover_protocol(work_tree))

    assert result is None
    assert "workTreeResolution" not in request
    assert "workTreeResolution" not in root_mount
