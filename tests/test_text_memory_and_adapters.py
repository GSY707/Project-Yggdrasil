from sqlalchemy.exc import OperationalError

from yggdrasil_model_providers.router import route_model
from yggdrasil_media_providers.pipeline import plan_asset_processing
from yggdrasil_sdk import get_persistence_runtime
from yggdrasil_sdk.persistence.repositories import NodeRepository, WorkspaceBootstrapRepository
from yggdrasil_text_memory.plugin import TextMemoryModule
from yggdrasil_text_memory.plugin import _run_with_sqlite_lock_retry
from yggdrasil_text_memory.plugin import read_memory_node_tool


def test_text_memory_plan_tree_and_expand_retrieval() -> None:
    plugin = TextMemoryModule()
    preprocess = plugin.preprocess_import(
        {
            "importJob": {
                "id": "import_alpha",
                "projectId": "project_default",
                "spaceId": "space_default",
                "branchId": "branch_main",
            },
            "sourceTexts": [
                "任务目标是实现模块注册表、hook 目录和 worker 活动注册。",
                "运行时需要在启动时挂载根节点，并在暂停时生成可恢复快照。",
            ],
        }
    )
    assert preprocess["orderedFragments"]

    tree_plan = plugin.plan_tree(
        {
            "importJob": {
                "id": "import_alpha",
                "projectId": "project_default",
                "spaceId": "space_default",
                "branchId": "branch_main",
            },
            "orderedFragments": preprocess["orderedFragments"],
        }
    )

    assert len(tree_plan["candidateNodes"]) == 2
    assert tree_plan["candidateSourceAnnotations"]
    validation = plugin.validate_memory_write(
        {
            "candidateNodes": tree_plan["candidateNodes"],
            "candidateEdges": tree_plan["candidateEdges"],
        }
    )
    assert validation["status"] == "ok"

    retrieval = plugin.expand_retrieval(
        {
            "retrievalRequest": {
                "id": "retr_1",
                "queryText": "模块注册 worker 运行时",
                "maxLeafNodes": 2,
                "maxRelatedNodes": 2,
            },
            "candidateNodes": tree_plan["candidateNodes"],
            "candidateEdges": tree_plan["candidateEdges"],
            "candidateSourceAnnotations": tree_plan["candidateSourceAnnotations"],
        }
    )

    assert retrieval["matchedNodeRefs"]
    assert retrieval["nodePayloads"]
    assert retrieval["naturalLanguageSummary"]
    assert len(retrieval["matchedNodeRefs"]) <= 4


def test_text_memory_plan_tree_is_stable_for_same_input() -> None:
    plugin = TextMemoryModule()
    payload = {
        "importJob": {
            "id": "import_stable",
            "projectId": "project_default",
            "spaceId": "space_default",
            "branchId": "branch_main",
        },
        "sourceTexts": [
            "任务目标是让记忆树成为主记忆，并确保跨窗口恢复时保持同一执行指针。",
            "检索扩展必须有界，且优先与当前 work tree 节点关联的线索。",
        ],
    }
    fragments = plugin.preprocess_import(payload)["orderedFragments"]
    first = plugin.plan_tree({"importJob": payload["importJob"], "orderedFragments": fragments})
    second = plugin.plan_tree({"importJob": payload["importJob"], "orderedFragments": fragments})

    first_nodes = [node["id"] for node in first["candidateNodes"]]
    second_nodes = [node["id"] for node in second["candidateNodes"]]
    first_edges = [edge["id"] for edge in first["candidateEdges"]]
    second_edges = [edge["id"] for edge in second["candidateEdges"]]
    assert first_nodes == second_nodes
    assert first_edges == second_edges
    assert first["depth"] == 2
    assert second["depth"] == 2


def test_text_memory_expand_retrieval_is_bounded_by_caps() -> None:
    plugin = TextMemoryModule()
    preprocess = plugin.preprocess_import(
        {
            "importJob": {
                "id": "import_bounds",
                "projectId": "project_default",
                "spaceId": "space_default",
                "branchId": "branch_main",
            },
            "sourceTexts": [
                "A B C D E F G H I J K L M N O P Q R S T U V W X Y Z。" * 4,
            ],
        }
    )
    tree_plan = plugin.plan_tree(
        {
            "importJob": {
                "id": "import_bounds",
                "projectId": "project_default",
                "spaceId": "space_default",
                "branchId": "branch_main",
            },
            "orderedFragments": preprocess["orderedFragments"],
        }
    )
    retrieval = plugin.expand_retrieval(
        {
            "retrievalRequest": {
                "id": "retr_bounded",
                "queryText": "A B C",
                "maxLeafNodes": 99,
                "maxRelatedNodes": 99,
                "tokenBudget": 1,
            },
            "candidateNodes": tree_plan["candidateNodes"],
            "candidateEdges": tree_plan["candidateEdges"],
            "candidateSourceAnnotations": tree_plan["candidateSourceAnnotations"],
        }
    )
    assert len(retrieval["matchedNodeRefs"]) <= 4
    assert retrieval["truncated"] is True


def test_model_router_returns_weighted_route_decision() -> None:
    route = route_model("coding")

    assert route["taskType"] == "coding"
    assert route["selectedModel"]
    assert route["candidateModels"]
    assert route["routePolicyVersion"] == "v0.1-task-weighted"


def test_media_pipeline_returns_planned_pipeline() -> None:
    plan = plan_asset_processing("video")

    assert plan["assetKind"] == "video"
    assert plan["status"] == "planned"
    assert any(stage["stage"] == "segment-scenes" for stage in plan["pipeline"])


def test_read_memory_node_tool_falls_back_to_first_index_node_when_node_id_missing() -> None:
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        nodes = NodeRepository(session)
        created = nodes.create_node(
            {
                "projectId": "project_default",
                "spaceId": "space_default",
                "branchId": "branch_main",
                "rootBranch": "context",
                "nodeType": "temporary",
                "title": "fallback candidate",
                "content": "fallback node content",
                "importance": 0.9,
            }
        )

    result = read_memory_node_tool({"executionContext": {"branchId": "branch_main"}, "nodeId": {}})

    assert result["fallbackNodeSelected"] is True
    assert result["node"]["id"] == created.id


def test_sqlite_lock_retry_recovers_after_transient_lock(monkeypatch) -> None:
    attempts = {"count": 0}

    monkeypatch.setattr("yggdrasil_text_memory.plugin.time.sleep", lambda _seconds: None)

    def _action() -> dict[str, object]:
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise OperationalError("UPDATE nodes", {}, Exception("database is locked"))
        return {"status": "ok"}

    result = _run_with_sqlite_lock_retry(_action)

    assert result["status"] == "ok"
    assert attempts["count"] == 3


def test_sqlite_lock_retry_does_not_retry_non_lock_operational_error(monkeypatch) -> None:
    attempts = {"count": 0}

    monkeypatch.setattr("yggdrasil_text_memory.plugin.time.sleep", lambda _seconds: None)

    def _action() -> dict[str, object]:
        attempts["count"] += 1
        raise OperationalError("UPDATE nodes", {}, Exception("syntax error near UPDATE"))

    try:
        _run_with_sqlite_lock_retry(_action)
    except OperationalError:
        pass
    else:
        raise AssertionError("Expected OperationalError to be raised")

    assert attempts["count"] == 1