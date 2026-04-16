from yggdrasil_model_providers.router import route_model
from yggdrasil_media_providers.pipeline import plan_asset_processing
from yggdrasil_text_memory.plugin import TextMemoryModule


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