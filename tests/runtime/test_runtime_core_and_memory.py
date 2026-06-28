import json
from pathlib import Path
import threading

from fastapi.testclient import TestClient
import pytest

from yggdrasil_agent_runtime.app import app as runtime_app
from yggdrasil_agent_runtime.runtime import build_root_mount_package, prepare_pause_snapshot
from yggdrasil_context_pruning.plugin import ContextPruningModule
from yggdrasil_sdk import (
    PromptAssetRepository,
    TaskRepository,
    execute_registered_tool,
    get_persistence_runtime,
    resolve_registered_tool_descriptors,
    resolve_workspace_root,
)
from yggdrasil_sdk.persistence.constants import DEFAULT_APP_ID
from yggdrasil_sdk.persistence.repositories import NodeRepository, RuntimeRepository, WorkspaceBootstrapRepository
import yggdrasil_sdk.runtime_kernel.execution_loop as runtime_execution_loop
from yggdrasil_worker.registry import run_worker_once


client = TestClient(runtime_app)
pytestmark = pytest.mark.slow

def _seed_task(
    task_id: str = "task_alpha",
    agent_run_id: str = "run_alpha",
    *,
    app_id: str = DEFAULT_APP_ID,
) -> None:
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        task_repository.create_task(
            {
                "id": task_id,
                "appId": app_id,
                "title": "实现正式持久化底座",
                "goal": "把运行时、模块注册和快照链路落到正式存储。",
                "status": "running",
                "currentObjective": "完成 runtime 持久化",
                "currentFocus": "pause snapshot",
                "resumeMessage": "继续写入任务快照。",
            }
        )
        task_repository.create_agent_run(
            task_id,
            {
                "id": agent_run_id,
                "status": "running",
                "selectedModel": "gpt-5.4",
                "selectedProvider": "copilot",
            },
        )


def test_root_mount_package_uses_formal_runtime_fields() -> None:
    _seed_task()
    mount_package = build_root_mount_package(
        "task_alpha",
        {
            "taskObjective": "整理项目的模块注册和运行时入口",
            "currentFocus": "runtime bootstrap",
            "resumeMessage": "继续完成 M1。",
        },
    )

    assert mount_package["taskId"] == "task_alpha"
    assert mount_package["identityRefs"]
    assert mount_package["contextRefs"]
    assert mount_package["executionRefs"]
    assert "text-memory" in mount_package["activeCapabilities"]
    assert "training-lab" not in mount_package["activeCapabilities"]
    assert mount_package["mountedNodeRefs"]
    assert mount_package["source"] == "database"


def test_root_mount_package_respects_application_default_capabilities() -> None:
    _seed_task(
        task_id="task_learning",
        agent_run_id="run_learning",
        app_id="yggdrasil.app.learning-coach",
    )

    mount_package = build_root_mount_package("task_learning")

    assert set(mount_package["activeCapabilities"]) == {
        "text-memory",
        "context-pruning",
        "mcp-bridge",
        "pause-resume",
        "task-takeover",
        "subagent-runtime",
        "scene-learning-coach",
    }


def test_pause_snapshot_reports_blockers_and_safe_stop() -> None:
    _seed_task()
    blocked_snapshot = prepare_pause_snapshot(
        "task_alpha",
        {
            "agentRunId": "run_alpha",
            "activeToolCalls": ["subagent.pr.create"],
            "currentResponseState": "streaming",
        },
    )
    assert blocked_snapshot["safeToPause"] is False
    assert blocked_snapshot["appId"] == DEFAULT_APP_ID
    assert "active-tool-calls" in blocked_snapshot["blockers"]
    assert blocked_snapshot["persisted"] is True
    assert any("Prepared safe-stop" in summary for summary in blocked_snapshot["moduleSummaries"])

    safe_snapshot = prepare_pause_snapshot(
        "task_alpha",
        {
            "agentRunId": "run_alpha",
            "pendingWrites": [{"kind": "node", "id": "node_123"}],
            "currentResponseState": "completed",
        },
    )
    assert safe_snapshot["safeToPause"] is True
    assert safe_snapshot["appId"] == DEFAULT_APP_ID
    assert safe_snapshot["flushedWrites"] == 1
    assert safe_snapshot["persisted"] is True
    assert any(action["kind"] == "resume-digest" for action in safe_snapshot["pendingActions"])


def test_context_pruning_retains_protected_refs() -> None:
    plugin = ContextPruningModule()
    plan = plugin.plan(
        {
            "taskId": "task_alpha",
            "sourceRunId": "run_alpha",
            "nextObjective": "只保留和模块注册相关的内容",
            "budget": {"maxRetainedTokens": 30},
            "protectedItems": [{"kind": "node", "id": "node_keep"}],
            "currentContext": [
                {
                    "id": "node_keep",
                    "title": "模块注册表",
                    "content": "模块注册需要稳定的 install record 和 hook catalog。",
                    "importance": 0.9,
                },
                {
                    "id": "node_drop",
                    "title": "无关资料",
                    "content": "这段内容和当前目标没有直接关系。",
                    "importance": 0.1,
                },
                {
                    "id": "ctx_response_requirements",
                    "kind": "responseRequirements",
                    "title": "responseRequirements",
                    "content": "按任务需要说明结果和证据。",
                    "importance": 0.0,
                },
            ],
        }
    )

    retained_ids = {reference["id"] for reference in plan["retainedRefs"]}
    assert "node_keep" in retained_ids
    assert "ctx_response_requirements" in retained_ids
    assert plan["pruningReport"]["kept"]

    executed = plugin.execute(
        {
            "plan": plan,
            "currentContext": [
                {
                    "id": "node_keep",
                    "title": "模块注册表",
                    "content": "模块注册需要稳定的 install record 和 hook catalog。",
                }
            ],
        }
    )
    assert executed["status"] == "executed"
    assert executed["plan"]["status"] == "executed"


def test_main_agent_materializes_runtime_context_into_memory_tree_before_prompt() -> None:
    runtime = get_persistence_runtime()
    task_id = "task_memory_tree_runtime"
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        TaskRepository(session).create_task(
            {
                "id": task_id,
                "title": "记忆树主导上下文装配",
                "goal": "让运行时在模型调用前先把外来上下文写入记忆树，再从记忆树检索工作集。",
                "status": "draft",
                "currentObjective": "验证当前 prompt 使用的是记忆树检索结果。",
                "currentFocus": "memory-tree-runtime",
                "budgetState": {
                    "tokenBudgetTotal": 2000,
                    "costBudgetTotal": 5.0,
                },
            }
        )

    started = client.post(
        f"/runtime/tasks/{task_id}/start",
        json={
            "auditLevel": "strict",
            "currentFocus": "memory-tree-runtime",
            "currentObjective": "验证当前 prompt 使用的是记忆树检索结果。",
            "currentContext": [
                {
                    "id": "ctx_memory_tree_1",
                    "title": "持久记忆检索入口",
                    "content": "运行时必须先把上下文写成记忆节点，再从记忆树读取节点与关联关系。",
                    "importance": 0.95,
                },
                {
                    "id": "ctx_memory_tree_2",
                    "title": "共享挂载检索",
                    "content": "共享空间节点应和本地节点一起进入统一 retrieval，再由 text-memory 输出自然语言摘要。",
                    "importance": 0.85,
                },
            ],
        },
    )
    assert started.status_code == 202

    processed = run_worker_once("agent-runtime")
    assert processed["status"] == "processed"
    assert processed["result"]["status"] == "continuing"

    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        node_repository = NodeRepository(session)
        runtime_repository = RuntimeRepository(session)
        prompt_repository = PromptAssetRepository(session)
        temporary_nodes = [
            node
            for node in node_repository.list_nodes(branch_id="branch_main", limit=500)
            if node.status == "temporary"
            and node.title in {"持久记忆检索入口", "共享挂载检索"}
        ]
        assert len(temporary_nodes) >= 2

        invocations = runtime_repository.list_model_invocations(task_id=task_id)
        assert len(invocations) == 1
        invocation = invocations[0]
        artifact = prompt_repository.get_prompt_compile_artifact(str(invocation.prompt_compile_artifact_id))
        assert artifact is not None
        assert artifact.compiled_messages_ref is not None
        assert invocation.request_ref is not None

        compiled_path = Path(resolve_workspace_root()) / artifact.compiled_messages_ref.locator
        compiled_payload = json.loads(compiled_path.read_text(encoding="utf-8"))
        messages = compiled_payload.get("messages") or []
        assert messages
        user_message = str(messages[-1].get("content") or "")
        assert "Memory retrieval summary" in user_message
        assert "持久记忆检索入口" in user_message


def test_main_agent_applies_memory_write_tags_without_interrupting_completion(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = get_persistence_runtime()
    task_id = "task_memory_tag_write"
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        TaskRepository(session).create_task(
            {
                "id": task_id,
                "title": "标签写入记忆树",
                "goal": "让主 Agent 可以在回答中用标签写入记忆树而不触发额外工具回合。",
                "status": "draft",
                "currentObjective": "验证 assistant 输出标签会在停止点落入记忆树。",
                "currentFocus": "memory-tag-write",
                "budgetState": {
                    "tokenBudgetTotal": 2000,
                    "costBudgetTotal": 5.0,
                },
            }
        )

    def _fake_invoke_runtime_completion(*args, **kwargs):  # type: ignore[no-untyped-def]
        return {
            "assistantText": (
                "# result\n已记录本轮运行记忆。\n"
                "# evidence\n通过验证。\n"
                "# pending\n无。\n"
                "# incomplete\n无。\n"
                '<memory-write title="运行时记忆策略" rootBranch="context" importance="0.93">'
                "模型必须始终先从记忆树检索，再决定当前工作集。"
                "</memory-write>"
            ),
            "invocation": {
                "id": "inv_memory_tag_write",
                "resolvedModel": "LongCat-Flash-Lite",
                "resolvedProvider": "longcat",
                "status": "completed",
                "promptCompileArtifactId": "artifact_memory_tag_write",
                "traceId": "trace_memory_tag_write",
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
    
    started = client.post(
        f"/runtime/tasks/{task_id}/start",
        json={
            "currentFocus": "memory-tag-write",
            "currentObjective": "验证 assistant 输出标签会在停止点落入记忆树。",
        },
    )
    assert started.status_code == 202

    processed = run_worker_once("agent-runtime")
    assert processed["status"] == "processed"
    assert processed["result"]["status"] == "continuing"
    assert processed["result"]["memoryTagWrites"]["detectedCount"] == 1
    assert len(processed["result"]["memoryTagWrites"]["applied"]) == 1
    assert processed["result"]["memoryTagWrites"]["blocked"] == []

    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        node_repository = NodeRepository(session)
        task = task_repository.get_task(task_id)
        assert task is not None

        memory_nodes = [
            node
            for node in node_repository.list_nodes(branch_id=task.branch_id, limit=200)
            if node.title == "运行时记忆策略" and node.node_type == "detail"
        ]
        assert len(memory_nodes) == 1
        assert "模型必须始终先从记忆树检索，再决定当前工作集。" in memory_nodes[0].content

        execution_notes = [
            node
            for node in node_repository.list_nodes(branch_id=task.branch_id, limit=200)
            if node.node_type == "task" and node.parent_id == task.execution_root_node_id
        ]
        assert len(execution_notes) == 1
        assert "已记录本轮运行记忆。" in execution_notes[0].content
        assert "<memory-write" not in execution_notes[0].content


def test_memory_write_tag_parser_blocks_invalid_action_and_supports_disable_switch() -> None:
    parsed_enabled = runtime_execution_loop._extract_assistant_memory_write_tags(
        (
            "开始输出。"
            '<memory-write title="非法动作" action="merge">不应写入</memory-write>'
            '<memory-write title="合法动作" action="append">可写入</memory-write>'
        ),
        enabled=True,
    )
    assert parsed_enabled["detectedCount"] == 2
    assert len(parsed_enabled["writes"]) == 1
    assert parsed_enabled["writes"][0]["title"] == "合法动作"
    assert len(parsed_enabled["blocked"]) == 1
    assert parsed_enabled["blocked"][0]["reason"] == "invalid-action"
    assert "memory-write" not in parsed_enabled["cleanAssistantText"]

    parsed_disabled = runtime_execution_loop._extract_assistant_memory_write_tags(
        '<memory-write title="不解析">保持原文</memory-write>',
        enabled=False,
    )
    assert parsed_disabled["detectedCount"] == 0
    assert parsed_disabled["writes"] == []
    assert parsed_disabled["blocked"] == []
    assert parsed_disabled["cleanAssistantText"] == '<memory-write title="不解析">保持原文</memory-write>'


def test_execute_registered_tool_passes_source_work_tree_node_id_to_multimodal_memory() -> None:
    task_id = "task_p5_tool_context"
    run_id = "run_p5_tool_context"
    _seed_task(task_id=task_id, agent_run_id=run_id)

    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        node_repository = NodeRepository(session)
        task = task_repository.get_task(task_id)
        run = task_repository.get_agent_run(run_id)
        assert task is not None
        assert run is not None
        _, context_refs, _ = node_repository.root_mount_refs(task.project_id, task.branch_id)
        owner_node_id = context_refs[0].id

    root_mount = build_root_mount_package(task_id)
    root_mount["activeCapabilities"] = sorted(set(root_mount.get("activeCapabilities") or []) | {"multimodal-memory"})
    root_mount["takeoverProtocol"] = {"workTree": {"currentNodeId": "wt-node-p5-tools"}}

    execution = execute_registered_tool(
        "multimodal_memory.ingest_asset",
        {
            "mediaType": "document",
            "sourceText": "P5 需要让正式记忆工具和工作树节点来源绑定。",
            "ownerNodeId": owner_node_id,
        },
        task=task,
        run=run,
        root_mount=root_mount,
        current_context=[],
    )

    assert execution["result"]["summaryNode"]["sourceWorkTreeNodeId"] == "wt-node-p5-tools"

    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        node_repository = NodeRepository(session)
        summary_node = node_repository.get_node(execution["result"]["summaryNode"]["id"])
        assert summary_node is not None
        assert summary_node.source_work_tree_node_id == "wt-node-p5-tools"


def test_text_memory_tools_support_read_conflict_proposal_and_forget_paths() -> None:
    task_id = "task_p5_memory_tools"
    run_id = "run_p5_memory_tools"
    _seed_task(task_id=task_id, agent_run_id=run_id)

    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        node_repository = NodeRepository(session)
        task = task_repository.get_task(task_id)
        run = task_repository.get_agent_run(run_id)
        assert task is not None
        assert run is not None
        _, context_refs, _ = node_repository.root_mount_refs(task.project_id, task.branch_id)
        memory_node = node_repository.create_node(
            {
                "projectId": task.project_id,
                "spaceId": task.space_id,
                "branchId": task.branch_id,
                "parentId": context_refs[0].id,
                "rootBranch": "context",
                "nodeType": "detail",
                "title": "Runtime Memory Draft",
                "content": "旧版记忆内容。",
                "createdBy": {"type": "user", "id": "pytest"},
                "updatedBy": {"type": "user", "id": "pytest"},
                "changeReason": "seed-memory-node",
            }
        )

    root_mount = build_root_mount_package(task_id)
    root_mount["activeCapabilities"] = sorted(set(root_mount.get("activeCapabilities") or []) | {"text-memory"})
    root_mount["takeoverProtocol"] = {"workTree": {"currentNodeId": "wt-node-memory-tools"}}

    tool_names = {tool.name for tool in resolve_registered_tool_descriptors(["text-memory"])}
    assert {
        "text_memory.read_node",
        "text_memory.read_index",
        "text_memory.update_memory_with_version",
        "text_memory.append_memory_log",
        "text_memory.submit_memory_proposal",
        "text_memory.forget_node",
    } <= tool_names

    with runtime.session_scope() as session:
        task_repository = TaskRepository(session)
        task = task_repository.get_task(task_id)
        run = task_repository.get_agent_run(run_id)
        assert task is not None
        assert run is not None

    read_index = execute_registered_tool(
        "text_memory.read_index",
        {"queryText": "Runtime Memory", "limit": 10},
        task=task,
        run=run,
        root_mount=root_mount,
        current_context=[],
    )
    assert any(item["id"] == memory_node.id for item in read_index["result"]["nodes"])

    read_node = execute_registered_tool(
        "text_memory.read_node",
        {"nodeId": memory_node.id, "includeVersions": True},
        task=task,
        run=run,
        root_mount=root_mount,
        current_context=[],
    )
    assert read_node["result"]["node"]["id"] == memory_node.id
    stale_version_id = read_node["result"]["latestVersionId"]

    updated = execute_registered_tool(
        "text_memory.update_memory_with_version",
        {
            "nodeId": memory_node.id,
            "expectedLatestVersionId": stale_version_id,
            "mode": "revise",
            "content": "新版记忆内容。",
        },
        task=task,
        run=run,
        root_mount=root_mount,
        current_context=[],
    )
    assert updated["result"]["status"] == "updated"
    latest_version_id = updated["result"]["node"]["latestVersionId"]

    conflict = execute_registered_tool(
        "text_memory.update_memory_with_version",
        {
            "nodeId": memory_node.id,
            "expectedLatestVersionId": stale_version_id,
            "mode": "revise",
            "content": "不会覆盖的新内容。",
        },
        task=task,
        run=run,
        root_mount=root_mount,
        current_context=[],
    )
    assert conflict["result"]["status"] == "conflict"
    assert conflict["result"]["currentLatestVersionId"] == latest_version_id

    appended = execute_registered_tool(
        "text_memory.append_memory_log",
        {"nodeId": memory_node.id, "logEntry": "并发补充日志。"},
        task=task,
        run=run,
        root_mount=root_mount,
        current_context=[],
    )
    assert appended["result"]["status"] == "appended"

    proposal = execute_registered_tool(
        "text_memory.submit_memory_proposal",
        {
            "nodeId": memory_node.id,
            "title": "拆分 Runtime Memory Draft",
            "proposal": "将宽节点拆成两个子节点分别记录运行时策略与冲突处理。",
            "rationale": "宽节点过宽，直接改写冲突风险高。",
        },
        task=task,
        run=run,
        root_mount=root_mount,
        current_context=[],
    )
    assert proposal["result"]["status"] == "proposed"
    proposal_node_id = proposal["result"]["proposalNode"]["id"]

    forgotten = execute_registered_tool(
        "text_memory.forget_node",
        {
            "nodeId": proposal_node_id,
            "reason": "提案已合并回主节点。",
            "status": "archived",
            "mergedIntoNodeId": memory_node.id,
        },
        task=task,
        run=run,
        root_mount=root_mount,
        current_context=[],
    )
    assert forgotten["result"]["status"] == "forgotten"

    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        node_repository = NodeRepository(session)
        updated_memory_node = node_repository.get_node(memory_node.id)
        proposal_node = node_repository.get_node(proposal_node_id)
        memory_versions = node_repository.list_versions(memory_node.id, limit=20)
        assert updated_memory_node is not None
        assert updated_memory_node.content.endswith("并发补充日志。")
        assert updated_memory_node.source_work_tree_node_id == "wt-node-memory-tools"
        assert len(memory_versions) >= 3
        assert proposal_node is not None
        assert proposal_node.status == "archived"
        assert proposal_node.merged_into_node_id == memory_node.id
        assert proposal_node.source_work_tree_node_id == "wt-node-memory-tools"


def test_append_memory_log_keeps_all_entries_under_race(monkeypatch: pytest.MonkeyPatch) -> None:
    task_id = "task_p5_memory_log_race"
    run_id = "run_p5_memory_log_race"
    _seed_task(task_id=task_id, agent_run_id=run_id)

    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        node_repository = NodeRepository(session)
        task = task_repository.get_task(task_id)
        run = task_repository.get_agent_run(run_id)
        assert task is not None
        assert run is not None
        _, context_refs, _ = node_repository.root_mount_refs(task.project_id, task.branch_id)
        memory_node = node_repository.create_node(
            {
                "projectId": task.project_id,
                "spaceId": task.space_id,
                "branchId": task.branch_id,
                "parentId": context_refs[0].id,
                "rootBranch": "context",
                "nodeType": "detail",
                "title": "Concurrent Memory Log Node",
                "content": "初始记忆内容。",
                "createdBy": {"type": "user", "id": "pytest"},
                "updatedBy": {"type": "user", "id": "pytest"},
                "changeReason": "seed-memory-log-race",
            }
        )

    root_mount = build_root_mount_package(task_id)
    root_mount["activeCapabilities"] = sorted(set(root_mount.get("activeCapabilities") or []) | {"text-memory"})
    root_mount["takeoverProtocol"] = {"workTree": {"currentNodeId": "wt-node-memory-race"}}

    with runtime.session_scope() as session:
        task_repository = TaskRepository(session)
        task = task_repository.get_task(task_id)
        run = task_repository.get_agent_run(run_id)
        assert task is not None
        assert run is not None

    barrier = threading.Barrier(2)
    original_append_version = NodeRepository.append_version

    def _coordinated_append_version(self: NodeRepository, node_id: str, payload: dict[str, object]):
        if node_id == memory_node.id:
            try:
                barrier.wait(timeout=5)
            except threading.BrokenBarrierError as exc:
                raise AssertionError("append_version barrier was broken during concurrent append test") from exc
        return original_append_version(self, node_id, payload)

    monkeypatch.setattr(NodeRepository, "append_version", _coordinated_append_version)

    errors: list[Exception] = []

    def _append_log(entry: str) -> None:
        try:
            execute_registered_tool(
                "text_memory.append_memory_log",
                {"nodeId": memory_node.id, "logEntry": entry},
                task=task,
                run=run,
                root_mount=root_mount,
                current_context=[],
            )
        except Exception as exc:
            errors.append(exc)

    threads = [
        threading.Thread(target=_append_log, args=("并发日志 A",)),
        threading.Thread(target=_append_log, args=("并发日志 B",)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert not errors, f"Unexpected errors during concurrent append test: {errors}"

    with runtime.session_scope() as session:
        node_repository = NodeRepository(session)
        updated_node = node_repository.get_node(memory_node.id)
        versions = node_repository.list_versions(memory_node.id, limit=10)

    assert updated_node is not None
    assert updated_node.source_work_tree_node_id == "wt-node-memory-race"
    assert updated_node.content is not None
    assert "并发日志 A" in updated_node.content
    assert "并发日志 B" in updated_node.content
    assert len(versions) == 3
