import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest
import sqlalchemy as sa
import yggdrasil_model_providers

from yggdrasil_agent_runtime.app import app as runtime_app
from yggdrasil_agent_runtime.runtime import build_root_mount_package, prepare_pause_snapshot
from yggdrasil_context_pruning.plugin import ContextPruningModule
from yggdrasil_sdk import PromptAssetRepository, TaskRepository, get_persistence_runtime, resolve_workspace_root
from yggdrasil_sdk.persistence.constants import DEFAULT_APP_ID
from yggdrasil_sdk.persistence.orm import RetrievalRequestORM
from yggdrasil_sdk.persistence.repositories import NodeRepository, RuntimeRepository, WorkspaceBootstrapRepository
import yggdrasil_sdk.runtime_kernel.execution_loop as runtime_execution_loop
import yggdrasil_sdk.runtime_kernel.execution_loop_part_b as runtime_execution_loop_part_b
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
                    "content": "result/evidence/pending/incomplete 必须齐全。",
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
    assert processed["result"]["status"] == "completed"

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
        assert "Materialized 2 runtime context items into the memory tree before retrieval." in user_message
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
                "已记录本轮运行记忆。\n"
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
    monkeypatch.setattr(runtime_execution_loop_part_b, "invoke_runtime_completion", _fake_invoke_runtime_completion)

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
    assert processed["result"]["status"] == "completed"
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


