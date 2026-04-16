from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from yggdrasil_core_api.app import app


client = TestClient(app)
SAMPLE_TEXT = (Path(__file__).parent / "fixtures" / "memory_import_sample.txt").read_text(encoding="utf-8")


def test_core_api_materializes_memory_import_and_retrieval() -> None:
    created = client.post(
        "/memory/import-jobs",
        json={
            "sourceKind": "file",
            "sourceText": SAMPLE_TEXT,
            "rawRef": {"type": "file", "locator": "tests/fixtures/memory_import_sample.txt"},
            "processImmediately": True,
            "requestedBy": {"type": "user", "id": "test-user"},
            "importPolicy": {
                "segmentTargetChars": 180,
                "allowDiscardLowValue": False,
                "linkStrategy": ["keyword"],
                "mergePolicy": "balanced",
            },
        },
    )
    assert created.status_code == 201
    body = created.json()

    assert body["status"] == "completed"
    assert body["importJob"]["status"] == "completed"
    assert len(body["fragments"]) >= 2
    assert body["treePlans"]
    assert len(body["materializedNodes"]) >= 2
    assert body["materializedEdges"]
    assert body["materializedSourceAnnotations"]

    import_job_id = body["importJob"]["id"]
    fetched_job = client.get(f"/memory/import-jobs/{import_job_id}")
    assert fetched_job.status_code == 200
    assert fetched_job.json()["materializedNodes"]

    first_node_id = body["materializedNodes"][0]["id"]
    node_detail = client.get(f"/nodes/{first_node_id}")
    assert node_detail.status_code == 200
    node_body = node_detail.json()
    assert node_body["node"]["content"]
    assert node_body["versions"]
    assert node_body["annotations"]
    assert node_body["incomingEdges"] or node_body["outgoingEdges"]

    retrieval = client.post(
        "/memory/retrievals",
        json={
            "queryText": "模块生命周期 事件总线 导入链路 检索",
            "branchId": "branch_main",
            "maxLeafNodes": 4,
            "maxRelatedNodes": 4,
            "includeNaturalLanguageSummary": True,
        },
    )
    assert retrieval.status_code == 201
    retrieval_body = retrieval.json()
    assert retrieval_body["retrievalRequest"]["id"]
    assert retrieval_body["retrievalBundle"]["matchedNodeRefs"]
    assert retrieval_body["retrievalBundle"]["nodePayloads"]
    assert retrieval_body["retrievalBundle"]["sourceAnnotationRefs"]
    assert retrieval_body["retrievalBundle"]["naturalLanguageSummary"]

    outbox = client.get("/outbox")
    assert outbox.status_code == 200
    event_types = {event["eventType"] for event in outbox.json()["events"]}
    assert {"import.accepted", "import.segmented", "memory.tree.plan.proposed", "memory.tree.materialized"} <= event_types