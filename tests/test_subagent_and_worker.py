from __future__ import annotations

import json
import subprocess
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from yggdrasil_core_api.app import app
from yggdrasil_sdk import PromptAssetRepository, get_persistence_runtime, resolve_workspace_root
from yggdrasil_sdk.collaboration_runtime import GitCollaborationAdapter, launch_subagent_task
from yggdrasil_sdk.contracts import WorkerActivityDescriptor
from yggdrasil_sdk.persistence.constants import DEFAULT_APP_ID, DEFAULT_BRANCH_ID
from yggdrasil_sdk.persistence.repositories import CollaborationRepository, NodeRepository, RuntimeRepository, TaskRepository, WorkspaceBootstrapRepository
import yggdrasil_sdk.runtime_kernel.execution_loop as runtime_execution_loop
import yggdrasil_sdk.runtime_kernel.execution_loop_worker_entry as runtime_execution_loop_worker_entry
import yggdrasil_worker.registry as worker_registry
import yggdrasil_worker.main as worker_main
from yggdrasil_worker.registry import build_worker_report, enqueue_work_item, pop_work_item, run_worker_once


pytestmark = pytest.mark.slow


def _run_git(repo_path: Path, *args: str) -> str:
    completed = subprocess.run(["git", "-C", str(repo_path), *args], capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "unknown git error"
        raise RuntimeError(detail)
    return completed.stdout.strip()


def _init_git_repo(tmp_path: Path, monkeypatch) -> Path:
    repo_path = tmp_path / "collaboration-repo"
    repo_path.mkdir(parents=True, exist_ok=True)
    _run_git(repo_path, "init", "-b", "main")
    _run_git(repo_path, "config", "user.name", "Test User")
    _run_git(repo_path, "config", "user.email", "test@example.com")
    (repo_path / "README.md").write_text("# Test Repo\n", encoding="utf-8")
    _run_git(repo_path, "add", "README.md")
    _run_git(repo_path, "commit", "-m", "init")
    monkeypatch.setenv("YGGDRASIL_GIT_REPO_PATH", str(repo_path))
    return repo_path


def _seed_parent_task() -> tuple[dict[str, object], int]:
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        bootstrap = WorkspaceBootstrapRepository(session)
        bootstrap.ensure_default_workspace()
        task_repository = TaskRepository(session)
        node_repository = NodeRepository(session)
        existing_non_root_count = len(
            [node for node in node_repository.list_nodes(branch_id=DEFAULT_BRANCH_ID, limit=200) if node.node_type != "root"]
        )
        task = task_repository.create_task(
            {
                "title": "Main Task",
                "goal": "Coordinate a child implementation through PR review.",
                "currentFocus": "parent-planning",
                "currentObjective": "Prepare a sub-agent proposal.",
                "budget": {
                    "tokenBudgetTotal": 2400,
                    "tokenBudgetUsed": 0,
                    "costBudgetTotal": 5.0,
                    "costBudgetUsed": 0.0,
                    "selfThinkTokenLimit": 400,
                    "childBudgetMode": "capped",
                    "maxSubAgents": 2,
                },
            }
        )
        node_repository.create_node(
            {
                "projectId": task.project_id,
                "spaceId": task.space_id,
                "branchId": task.branch_id,
                "parentId": task.execution_root_node_id,
                "rootBranch": "execution",
                "nodeType": "task",
                "title": "Parent Context",
                "content": "This context must be passed as readonly material to the sub-agent.",
                "createdBy": {"type": "agent", "id": "main-agent"},
                "updatedBy": {"type": "agent", "id": "main-agent"},
            }
        )
    return task.model_dump(by_alias=True, mode="json"), existing_non_root_count


def _run_worker_until_result(predicate, *, max_steps: int = 16) -> dict[str, object]:
    last: dict[str, object] | None = None
    last_processed: dict[str, object] | None = None
    for _ in range(max_steps):
        candidate = run_worker_once()
        if candidate.get("status") != "processed":
            last = candidate
            continue
        last_processed = candidate
        result = candidate.get("result") if isinstance(candidate.get("result"), dict) else {}
        if predicate(result):
            return candidate
        last = candidate
    raise AssertionError(
        f"worker did not reach expected state within {max_steps} steps: last={last}; last_processed={last_processed}"
    )


def test_worker_report_collects_core_and_module_activities() -> None:
    report = build_worker_report()

    work_kinds = set(report["workKinds"])
    assert "core.agent.main.execute" in work_kinds
    assert "core.agent.subagent.execute" in work_kinds
    assert "core.memory.import.materialize" in work_kinds
    assert "subagent.pr.create" in work_kinds
    assert report["totalActivities"] >= 5


def test_worker_queue_operations_return_structured_status() -> None:
    enqueued = enqueue_work_item("activity", {"activity": "core.memory.import.materialize", "taskId": "task_alpha"})
    assert enqueued["status"] in {"enqueued", "error"}

    popped = pop_work_item("activity")
    assert popped["status"] in {"received", "empty", "error"}


def test_worker_main_defaults_to_continuous_agent_runtime_consumption(monkeypatch) -> None:
    calls: list[str] = []
    shutdown_checks = iter([False, True])

    monkeypatch.setattr(worker_main, "load_workspace_dotenv", lambda: None)
    monkeypatch.setattr(worker_main, "time", type("_TimeModule", (), {"sleep": staticmethod(lambda _: None)})())
    monkeypatch.setattr(worker_main, "is_shutdown_requested", lambda: next(shutdown_checks))
    monkeypatch.setattr(worker_main, "run_worker_once", lambda queue, timeout_seconds=1: calls.append(queue) or {"status": "empty", "queue": queue, "payload": None})
    monkeypatch.setattr("sys.argv", ["yggdrasil-worker"])

    worker_main.main()

    assert calls == ["agent-runtime"]


def test_run_worker_once_requeues_retryable_failed_activity(monkeypatch) -> None:
    monkeypatch.setattr(
        worker_registry,
        "pop_work_item",
        lambda queue, timeout_seconds=0: {
            "status": "received",
            "queue": queue,
            "payload": {"activity": "core.agent.main.execute", "taskId": "task_retry", "attempt": 1},
        },
    )
    monkeypatch.setattr(
        worker_registry,
        "discover_worker_activities",
        lambda: [
            WorkerActivityDescriptor(
                name="core.agent.main.execute",
                moduleId="kernel",
                description="retryable test",
                implementationRef="tests",
                timeoutMs=1,
                retryable=True,
            )
        ],
    )
    monkeypatch.setattr(
        worker_registry,
        "dispatch_work_item",
        lambda payload: {"status": "failed", "detail": "transient", "retryable": True},
    )

    captured: dict[str, object] = {}

    def _fake_enqueue(queue: str, payload: dict[str, object]) -> dict[str, object]:
        captured["queue"] = queue
        captured["payload"] = payload
        return {"status": "enqueued", "queue": queue, "queueDepth": 1, "payload": payload}

    monkeypatch.setattr(worker_registry, "enqueue_work_item", _fake_enqueue)

    result = run_worker_once()

    assert result["status"] == "requeued"
    assert captured["queue"] == "agent-runtime"
    assert captured["payload"]["attempt"] == 2
    assert result["result"]["status"] == "failed"


def test_subagent_closed_loop_creates_branch_and_pull_request(monkeypatch, tmp_path: Path) -> None:
    repo_path = _init_git_repo(tmp_path, monkeypatch)
    parent_task, existing_non_root_count = _seed_parent_task()

    launched = launch_subagent_task(
        str(parent_task["id"]),
        {
            "title": "Implement child path",
            "goal": "Produce the first branch proposal.",
            "createdBy": {"type": "agent", "id": "main-agent"},
        },
    )

    assert launched["status"] == "queued"
    assert launched["readonlyContext"]["mode"] == "readonly"
    assert launched["branch"]["name"].startswith("yggdrasil/subagent/")
    assert parent_task["appId"] == DEFAULT_APP_ID

    processed = _run_worker_until_result(lambda result: bool(result.get("pullRequest")))
    assert processed["status"] == "processed"
    result = processed["result"]
    assert result["status"] in {"completed", "awaiting-approval"}
    assert result["pullRequest"]["status"] == "open"

    manifest_json = _run_git(repo_path, "show", f"{launched['branch']['name']}:{result['manifestPath']}")
    manifest = json.loads(manifest_json)
    assert manifest["pullRequest"]["id"] == result["pullRequest"]["id"]
    assert manifest["readonlyContextRef"]["locator"].endswith("/readonly-context/current")

    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        task_repository = TaskRepository(session)
        prompt_repository = PromptAssetRepository(session)
        collaboration_repository = CollaborationRepository(session)
        runtime_repository = RuntimeRepository(session)
        child_task = task_repository.get_task(str(launched["task"]["id"]))
        assert child_task is not None
        assert child_task.app_id == str(parent_task["appId"])
        assert child_task.status in {"completed", "awaiting-approval"}
        runs = task_repository.list_agent_runs(child_task.id)
        assert runs[0].app_id == child_task.app_id
        assert runs[0].run_type == "subagent"
        invocations = runtime_repository.list_model_invocations(task_id=child_task.id)
        assert len(invocations) == 1
        assert invocations[0].app_id == child_task.app_id
        assert invocations[0].request_ref is not None
        assert invocations[0].prompt_compile_artifact_id is not None
        prompt_artifact = prompt_repository.get_prompt_compile_artifact(str(invocations[0].prompt_compile_artifact_id))
        assert prompt_artifact is not None
        assert prompt_artifact.app_id == child_task.app_id
        request_path = Path(resolve_workspace_root()) / invocations[0].request_ref.locator
        request_payload = json.loads(request_path.read_text(encoding="utf-8"))
        assert request_payload["appId"] == child_task.app_id
        assert request_payload["promptMetadata"]["promptProfileId"] == "yggdrasil.subagent"
        assert request_payload["promptMetadata"]["runType"] == "subagent"
        assert request_payload["promptCompileArtifactId"] == invocations[0].prompt_compile_artifact_id
        pull_request = collaboration_repository.get_pull_request(str(result["pullRequest"]["id"]))
        assert pull_request is not None
        assert pull_request.status == "open"
        review_comments = collaboration_repository.list_review_comments(pull_request.id)
        assert len(review_comments) == 1
        target_nodes = [node for node in NodeRepository(session).list_nodes(branch_id=DEFAULT_BRANCH_ID, limit=200) if node.node_type != "root"]
        assert len(target_nodes) == existing_non_root_count + 1


def test_subagent_launch_binds_work_tree_and_emits_budget_artifact(monkeypatch, tmp_path: Path) -> None:
    repo_path = _init_git_repo(tmp_path, monkeypatch)
    parent_task, _ = _seed_parent_task()

    launched = launch_subagent_task(
        str(parent_task["id"]),
        {
            "title": "Bind child to work tree",
            "goal": "Produce a scoped child proposal for one work tree node.",
            "workTreeNodeId": "wt-node-subagent-child",
            "subAgentBudget": {
                "tokenBudgetTotal": 2400,
                "costBudgetTotal": 1.25,
                "maxSubAgents": 1,
            },
            "createdBy": {"type": "agent", "id": "main-agent"},
        },
    )

    assert launched["status"] == "queued"
    assert launched["workTreeNodeId"] == "wt-node-subagent-child"
    assert launched["readonlyContext"]["workTreeNodeId"] == "wt-node-subagent-child"
    assert launched["readonlyContext"]["rootMount"]["currentNodeId"] == "wt-node-subagent-child"
    assert launched["subagentBudgetDecision"]["workTreeNodeId"] == "wt-node-subagent-child"
    assert launched["subagentBudgetDecision"]["allocatedBudget"]["tokenBudgetTotal"] == 2400
    assert launched["subagentBudgetDecision"]["allocatedBudget"]["costBudgetTotal"] == 1.25
    assert launched["workItem"]["payload"]["workTreeNodeId"] == "wt-node-subagent-child"
    assert launched["workItem"]["payload"]["currentNodeId"] == "wt-node-subagent-child"
    assert launched["workItem"]["payload"]["memoryRetrievalState"]["workTreeNodeId"] == "wt-node-subagent-child"

    processed = _run_worker_until_result(
        lambda result: bool(result.get("pullRequest")) or str(result.get("status") or "") in {"awaiting-approval", "continuing"}
    )
    assert processed["status"] == "processed"
    result = processed["result"]
    assert result["status"] in {"completed", "awaiting-approval", "continuing"}
    if result.get("workTreeNodeId") is not None:
        assert result["workTreeNodeId"] == "wt-node-subagent-child"
    budget_decision = result.get("subagentBudgetDecision") if isinstance(result.get("subagentBudgetDecision"), dict) else None
    if budget_decision is not None:
        assert (budget_decision.get("allocatedBudget") or {}).get("tokenBudgetTotal") == 2400

    if isinstance(result.get("pullRequest"), dict) and result.get("manifestPath"):
        manifest_json = _run_git(repo_path, "show", f"{launched['branch']['name']}:{result['manifestPath']}")
        manifest = json.loads(manifest_json)
        assert manifest["workTreeNodeId"] == "wt-node-subagent-child"
        assert manifest["subagentBudgetDecision"]["allocatedBudget"]["tokenBudgetTotal"] == 2400
        assert manifest["subagentBudgetDecision"]["allocatedBudget"]["costBudgetTotal"] == 1.25

    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        task_repository = TaskRepository(session)
        runtime_repository = RuntimeRepository(session)
        child_task = task_repository.get_task(str(launched["task"]["id"]))
        assert child_task is not None
        invocations = runtime_repository.list_model_invocations(task_id=child_task.id)
        assert len(invocations) == 1
        assert any(str(label).startswith("work-tree:") for label in (invocations[0].output_labels or []))


def test_subagent_completion_merges_into_parent_work_tree_and_wakes_parent(monkeypatch, tmp_path: Path) -> None:
    _init_git_repo(tmp_path, monkeypatch)
    parent_task, _ = _seed_parent_task()

    invoke_calls: list[dict[str, object]] = []

    def _fake_invoke_runtime_completion(*args, **kwargs):  # type: ignore[no-untyped-def]
        request_payload = kwargs.get("request") if isinstance(kwargs.get("request"), dict) else {}
        invoke_calls.append(request_payload)
        return {
            "assistantText": (
                "# result\nChild completed implementation and parent can summarize the result.\n"
                "# evidence\n通过验证。\n"
                "# pending\n无。\n"
                "# incomplete\n无。"
            ),
            "invocation": {
                "id": f"inv_subagent_parent_{len(invoke_calls)}",
                "resolvedModel": "LongCat-Flash-Lite",
                "resolvedProvider": "longcat",
                "status": "completed",
                "promptCompileArtifactId": f"artifact_subagent_parent_{len(invoke_calls)}",
                "traceId": f"trace_subagent_parent_{len(invoke_calls)}",
            },
            "usage": {
                "inputTokens": 64,
                "outputTokens": 24,
                "totalTokens": 88,
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
    monkeypatch.setattr(runtime_execution_loop_worker_entry, "invoke_runtime_completion", _fake_invoke_runtime_completion)

    launched = launch_subagent_task(
        str(parent_task["id"]),
        {
            "title": "Bind child to parent merge path",
            "goal": "Produce a child result that must be merged back into the parent work tree.",
            "workTreeNodeId": "wt-parent-child-summary",
            "createdBy": {"type": "agent", "id": "main-agent"},
        },
    )

    processed_records: list[dict[str, object]] = []
    for _ in range(6):
        candidate = run_worker_once()
        if candidate.get("status") != "processed":
            continue
        processed_records.append(candidate)

    child_record = next(
        (record for record in processed_records if (record.get("payload") or {}).get("activity") == "core.agent.subagent.execute"),
        None,
    )
    parent_record = next(
        (record for record in processed_records if (record.get("payload") or {}).get("activity") == "core.agent.main.execute"),
        None,
    )
    assert child_record is not None
    assert parent_record is not None

    child_result = child_record["result"] if isinstance(child_record.get("result"), dict) else {}
    assert child_result.get("status") in {"completed", "awaiting-approval", "continuing"}
    parent_followup = child_result.get("parentFollowup") if isinstance(child_result.get("parentFollowup"), dict) else None
    if parent_followup is not None:
        assert parent_followup.get("takeoverMerged") is True
        assert (parent_followup.get("mailboxMessage") or {}).get("workTreeNodeId") == "wt-parent-child-summary"

    parent_result = parent_record["result"] if isinstance(parent_record.get("result"), dict) else {}
    assert parent_result["status"] in {"completed", "awaiting-approval", "continuing"}
    assert len(invoke_calls) >= 2
    assert str(invoke_calls[1]["currentNodeId"]).startswith("work-tree-node_") or invoke_calls[1]["currentNodeId"] == "wt-parent-child-summary"
    assert invoke_calls[1]["workContextStack"]["frames"][0]["childCompletionSummaries"]

    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        task_repository = TaskRepository(session)
        runtime_repository = RuntimeRepository(session)
        parent = task_repository.get_task(str(parent_task["id"]))
        messages = runtime_repository.list_mailbox_messages(task_id=str(parent_task["id"]), limit=10)
        assert parent is not None
        assert parent.status in {"draft", "completed", "awaiting-approval"}
        assert messages


def test_collaboration_api_review_merges_pull_request(monkeypatch, tmp_path: Path) -> None:
    repo_path = _init_git_repo(tmp_path, monkeypatch)
    parent_task, _ = _seed_parent_task()
    launched = launch_subagent_task(
        str(parent_task["id"]),
        {
            "title": "Prepare reviewable branch",
            "goal": "Produce a proposal that will be merged by the parent.",
            "createdBy": {"type": "agent", "id": "main-agent"},
        },
    )
    processed = _run_worker_until_result(lambda result: bool(result.get("pullRequest")))
    pr_id = str(processed["result"]["pullRequest"]["id"])
    manifest_path = processed["result"]["manifestPath"]

    client = TestClient(app)
    list_response = client.get("/collaboration/pull-requests")
    assert list_response.status_code == 200
    assert any(record["id"] == pr_id for record in list_response.json()["pullRequests"])

    detail_response = client.get(f"/collaboration/pull-requests/{pr_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["pullRequest"]["status"] == "open"

    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        source_branch_nodes = [
            node for node in NodeRepository(session).list_nodes(branch_id=str(launched["branch"]["id"]), limit=200) if node.node_type != "root"
        ]
        target_before = [node for node in NodeRepository(session).list_nodes(branch_id=DEFAULT_BRANCH_ID, limit=200) if node.node_type != "root"]
    assert source_branch_nodes

    review_response = client.post(
        f"/collaboration/pull-requests/{pr_id}/review",
        json={
            "decision": "approved",
            "mergeImmediately": True,
            "reviewedBy": {"type": "agent", "id": "main-agent"},
        },
    )
    assert review_response.status_code == 200
    review_payload = review_response.json()
    assert review_payload["pullRequest"]["status"] == "merged"
    assert review_payload["git"]["mergeCommitRef"]
    assert review_payload["mergeSummary"]["counts"]["nodes"] >= len(source_branch_nodes)

    manifest_on_main = _run_git(repo_path, "show", f"main:{manifest_path}")
    assert json.loads(manifest_on_main)["pullRequest"]["id"] == pr_id

    with runtime.session_scope() as session:
        collaboration_repository = CollaborationRepository(session)
        merged_pr = collaboration_repository.get_pull_request(pr_id)
        assert merged_pr is not None
        assert merged_pr.status == "merged"
        merged_branch = collaboration_repository.get_branch(str(launched["branch"]["id"]))
        assert merged_branch is not None
        assert merged_branch.status == "merged"
        target_after = [node for node in NodeRepository(session).list_nodes(branch_id=DEFAULT_BRANCH_ID, limit=400) if node.node_type != "root"]
        assert len(target_after) >= len(target_before) + len(source_branch_nodes)


def test_pull_request_persists_remote_metadata_when_github_adapter_is_available(monkeypatch, tmp_path: Path) -> None:
    _init_git_repo(tmp_path, monkeypatch)
    parent_task, _ = _seed_parent_task()

    monkeypatch.setattr(
        GitCollaborationAdapter,
        "create_remote_pull_request",
        lambda self, **kwargs: {"number": 23, "html_url": "https://example.test/pr/23"},
    )

    launched = launch_subagent_task(
        str(parent_task["id"]),
        {
            "title": "Prepare remote metadata",
            "goal": "Persist GitHub metadata on PR creation.",
            "createdBy": {"type": "agent", "id": "main-agent"},
        },
    )
    processed = _run_worker_until_result(lambda result: bool(result.get("pullRequest")))
    pull_request = processed["result"]["pullRequest"]

    assert pull_request["externalId"] == "23"
    assert pull_request["externalUrl"] == "https://example.test/pr/23"

    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        persisted = CollaborationRepository(session).get_pull_request(str(pull_request["id"]))
        assert persisted is not None
        assert persisted.external_id == "23"
        assert persisted.external_url == "https://example.test/pr/23"
        branch = CollaborationRepository(session).get_branch(str(launched["branch"]["id"]))
        assert branch is not None
        assert branch.head_ref