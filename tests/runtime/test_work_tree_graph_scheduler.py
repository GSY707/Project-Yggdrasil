from __future__ import annotations

from yggdrasil_sdk.contracts import WorkTreeProtocol
from yggdrasil_sdk.runtime_kernel.work_tree_graph import compute_parent_ready_set, plan_fork_batch


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


def _node(
    node_id: str,
    *,
    parent: str | None = "root",
    children: list[str] | None = None,
    depends_on: list[str] | None = None,
    relation_ids: list[str] | None = None,
    priority: int = 100,
    status: str = "pending",
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
        "priority": priority,
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
