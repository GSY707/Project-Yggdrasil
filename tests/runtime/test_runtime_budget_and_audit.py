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
import yggdrasil_sdk.llm_runtime_part_b as llm_runtime_part_b
from yggdrasil_sdk.persistence.constants import DEFAULT_APP_ID
from yggdrasil_sdk.persistence.orm import RetrievalRequestORM
from yggdrasil_sdk.persistence.repositories import NodeRepository, RuntimeRepository, WorkspaceBootstrapRepository
import yggdrasil_sdk.runtime_kernel.execution_loop as runtime_execution_loop
from yggdrasil_worker.registry import run_worker_once


client = TestClient(runtime_app)
pytestmark = pytest.mark.slow

def test_main_agent_runtime_fails_when_budget_is_exhausted() -> None:
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        TaskRepository(session).create_task(
            {
                "id": "task_budget_fail",
                "title": "预算约束校验",
                "goal": "验证主 Agent 会在预算不足时显式失败。",
                "status": "draft",
                "budgetState": {
                    "tokenBudgetTotal": 10,
                    "costBudgetTotal": 0.01,
                },
            }
        )

    started = client.post(
        "/runtime/tasks/task_budget_fail/start",
        json={
            "currentContext": [
                {
                    "id": "ctx_budget",
                    "title": "大上下文",
                    "content": "这是一段为了触发预算超限而故意拉长的上下文。" * 40,
                    "importance": 0.8,
                }
            ]
        },
    )
    assert started.status_code == 202

    processed = run_worker_once("agent-runtime")
    assert processed["status"] == "processed"
    assert processed["result"]["status"] == "failed"

    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        runtime_repository = RuntimeRepository(session)
        task = task_repository.get_task("task_budget_fail")
        assert task is not None
        assert task.status == "failed"
        assert task_repository.list_agent_runs("task_budget_fail") == []
        assert runtime_repository.list_model_route_decisions(task_id="task_budget_fail") == []


def test_main_agent_runtime_fails_when_actual_usage_exceeds_budget(monkeypatch) -> None:
    monkeypatch.setattr(
        runtime_execution_loop,
        "load_runtime_candidate_models",
        lambda: [
            {
                "model": "budget-model",
                "provider": "budget-provider",
                "quality": 0.8,
                "costPer1k": 0.001,
                "latencyMs": 50,
                "contextWindow": 8192,
                "freeTier": True,
            }
        ],
    )

    def _fake_invoke_model(**_kwargs):
        return {
            "mode": "live",
            "provider": "budget-provider",
            "model": "budget-model",
            "outputText": "已输出一份超预算结果。",
            "finishReason": "stop",
            "usage": {
                "inputTokens": 260,
                "outputTokens": 120,
                "totalTokens": 380,
            },
            "costUsed": 0.05,
            "error": None,
            "toolCalls": [],
            "rawResponse": {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "已输出一份超预算结果。"},
                    }
                ],
                "usage": {
                    "prompt_tokens": 260,
                    "completion_tokens": 120,
                    "total_tokens": 380,
                },
            },
            "requestPayload": {
                "model": "budget-model",
                "messages": [],
                "stream": True,
            },
            "firstTokenLatencyMs": 120.0,
        }

    monkeypatch.setattr(yggdrasil_model_providers, "invoke_model", _fake_invoke_model)

    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        TaskRepository(session).create_task(
            {
                "id": "task_budget_actual_fail",
                "title": "预算后置校验",
                "goal": "验证实际 token/cost 超支后任务会失败。",
                "status": "draft",
                "budgetState": {
                    "tokenBudgetTotal": 500,
                    "costBudgetTotal": 0.03,
                },
            }
        )

    started = client.post(
        "/runtime/tasks/task_budget_actual_fail/start",
        json={
            "currentContext": [
                {
                    "id": "ctx_budget_actual",
                    "title": "小上下文",
                    "content": "让预估通过，但让实际用量超支。",
                    "importance": 0.5,
                }
            ]
        },
    )
    assert started.status_code == 202

    processed = run_worker_once("agent-runtime")
    assert processed["status"] == "processed"
    assert processed["result"]["status"] == "failed"
    assert "budget exceeded after model invocation" in processed["result"]["detail"].lower()

    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        runtime_repository = RuntimeRepository(session)
        task = task_repository.get_task("task_budget_actual_fail")
        assert task is not None
        assert task.status == "failed"
        runs = task_repository.list_agent_runs("task_budget_actual_fail")
        assert len(runs) == 1
        assert runs[0].status == "failed"
        assert len(runtime_repository.list_model_route_decisions(task_id="task_budget_actual_fail")) == 1
        assert len(runtime_repository.list_model_invocations(task_id="task_budget_actual_fail")) == 1


def test_runtime_audit_level_lean_writes_compact_artifacts() -> None:
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        TaskRepository(session).create_task(
            {
                "id": "task_audit_lean",
                "title": "lean audit runtime test",
                "goal": "验证 lean 审计模式会写入紧凑工件。",
                "status": "draft",
                "currentObjective": "完成一次最小运行。",
                "currentFocus": "lean-audit",
                "budgetState": {
                    "tokenBudgetTotal": 1000,
                    "costBudgetTotal": 5.0,
                },
            }
        )

    started = client.post(
        "/runtime/tasks/task_audit_lean/start",
        json={
            "auditLevel": "lean",
            "currentFocus": "lean-audit",
            "currentContext": [
                {
                    "id": "ctx_audit",
                    "title": "lean audit context",
                    "content": "验证 runtime 的 request/response/compiled prompt 工件可以被裁剪。",
                    "importance": 0.8,
                }
            ],
        },
    )
    assert started.status_code == 202

    processed = run_worker_once("agent-runtime")
    assert processed["status"] == "processed"
    assert processed["result"]["status"] == "completed"

    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        prompt_repository = PromptAssetRepository(session)
        runtime_repository = RuntimeRepository(session)
        invocations = runtime_repository.list_model_invocations(task_id="task_audit_lean")
        assert len(invocations) == 1
        invocation = invocations[0]
        artifact = prompt_repository.get_prompt_compile_artifact(str(invocation.prompt_compile_artifact_id))
        assert artifact is not None
        assert artifact.compiled_messages_ref is not None
        assert invocation.request_ref is not None
        assert invocation.response_ref is not None

        compiled_path = Path(resolve_workspace_root()) / artifact.compiled_messages_ref.locator
        compiled_payload = json.loads(compiled_path.read_text(encoding="utf-8"))
        assert compiled_payload["auditLevel"] == "lean"
        assert "messageDigests" in compiled_payload
        assert "messages" not in compiled_payload

        request_path = Path(resolve_workspace_root()) / invocation.request_ref.locator
        request_payload = json.loads(request_path.read_text(encoding="utf-8"))
        assert request_payload["auditLevel"] == "lean"
        assert "messages" not in request_payload
        assert "initialMessageDigests" in request_payload
        assert "finalMessageDigests" in request_payload
        assert "toolExecutionCount" in request_payload

        response_path = Path(resolve_workspace_root()) / invocation.response_ref.locator
        response_payload = json.loads(response_path.read_text(encoding="utf-8"))
        assert response_payload["auditLevel"] == "lean"
        assert response_payload["localRuntimeTimings"]["compilePromptMs"] >= 0
        assert "rawResponse" not in response_payload
        assert "toolExecutions" not in response_payload
        assert "toolExecutionCount" in response_payload


def test_runtime_response_payload_tracks_token_usage_and_context_lengths(monkeypatch) -> None:
    langfuse_start_calls: list[dict[str, object]] = []
    langfuse_finish_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        llm_runtime_part_b,
        "start_langfuse_generation",
        lambda **kwargs: langfuse_start_calls.append(kwargs) or object(),
    )
    monkeypatch.setattr(
        llm_runtime_part_b,
        "finish_langfuse_generation",
        lambda _generation, **kwargs: langfuse_finish_calls.append(kwargs),
    )
    monkeypatch.setattr(
        runtime_execution_loop,
        "load_runtime_candidate_models",
        lambda: [
            {
                "model": "metrics-model",
                "provider": "metrics-provider",
                "quality": 0.8,
                "costPer1k": 0.001,
                "latencyMs": 50,
                "contextWindow": 1_000_000,
                "freeTier": True,
            }
        ],
    )

    def _fake_invoke_model(**_kwargs):
        return {
            "mode": "live",
            "provider": "metrics-provider",
            "model": "metrics-model",
            "outputText": "已生成一份长任务实现计划。",
            "finishReason": "stop",
            "usage": {
                "inputTokens": 3200,
                "outputTokens": 400,
                "totalTokens": 3600,
                "cacheHitInputTokens": 2400,
                "cacheWriteInputTokens": 300,
                "nonCacheInputTokens": 800,
                "reasoningTokens": 120,
            },
            "costUsed": 0.05,
            "error": None,
            "toolCalls": [],
            "rawResponse": {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "已生成一份长任务实现计划。"},
                    }
                ],
                "usage": {
                    "prompt_tokens": 3200,
                    "completion_tokens": 400,
                    "total_tokens": 3600,
                },
            },
            "requestPayload": {
                "model": "metrics-model",
                "messages": [],
                "stream": True,
            },
            "firstTokenLatencyMs": 250.0,
        }

    monkeypatch.setattr(yggdrasil_model_providers, "invoke_model", _fake_invoke_model)

    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        TaskRepository(session).create_task(
            {
                "id": "task_metrics_trace",
                "title": "runtime metrics trace",
                "goal": "验证 token 用量和上下文长度会写入 response artifact。",
                "status": "draft",
                "currentObjective": "完成一轮 metrics 落盘。",
                "currentFocus": "metrics-trace",
                "budgetState": {
                    "tokenBudgetTotal": 10000,
                    "costBudgetTotal": 5.0,
                },
            }
        )

    started = client.post(
        "/runtime/tasks/task_metrics_trace/start",
        json={
            "currentFocus": "metrics-trace",
            "maxRetainedTokens": 24,
            "currentContext": [
                {
                    "id": "ctx_keep_metrics",
                    "title": "核心约束",
                    "content": "必须把 token 开销拆成缓存命中、非缓存命中、输出数，并记录长任务上下文长度。" * 4,
                    "importance": 0.95,
                },
                {
                    "id": "ctx_drop_metrics",
                    "title": "次要细节",
                    "content": "这段上下文用于触发 pruning，让 before/after 长度都能被记录。" * 4,
                    "importance": 0.1,
                },
            ],
            "protectedItems": [{"kind": "node", "id": "ctx_keep_metrics"}],
        },
    )
    assert started.status_code == 202

    processed = run_worker_once("agent-runtime")
    assert processed["status"] == "processed"
    assert processed["result"]["status"] == "completed"

    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        runtime_repository = RuntimeRepository(session)
        invocations = runtime_repository.list_model_invocations(task_id="task_metrics_trace")
        assert len(invocations) == 1
        response_path = Path(resolve_workspace_root()) / str(invocations[0].response_ref.locator)
        response_payload = json.loads(response_path.read_text(encoding="utf-8"))

    assert response_payload["usage"] == {
        "inputTokens": 3200,
        "outputTokens": 400,
        "totalTokens": 3600,
        "cacheHitInputTokens": 2400,
        "cacheWriteInputTokens": 300,
        "nonCacheInputTokens": 800,
        "reasoningTokens": 120,
    }
    observations = response_payload["contextLengthObservations"]
    phases = {item["phase"] for item in observations}
    assert {"beforeContextPruning", "afterContextPruning", "beforeModelInvocation", "taskEnd"}.issubset(phases)
    before_pruning = next(item for item in observations if item["phase"] == "beforeContextPruning")
    after_pruning = next(item for item in observations if item["phase"] == "afterContextPruning")
    assert before_pruning["estimatedTokens"] >= after_pruning["estimatedTokens"]
    assert langfuse_start_calls
    assert langfuse_finish_calls
    start_metadata = langfuse_start_calls[0]["metadata"]
    finish_metadata = langfuse_finish_calls[0]["metadata"]
    assert start_metadata["windowExecution"]["windowIndex"] == 1
    assert start_metadata["windowExecution"]["currentContextCount"] >= 1
    assert start_metadata["windowExecution"]["memoryRetrievalRequestId"] is not None
    assert finish_metadata["windowExecution"]["assistantTextSummary"].startswith("已生成一份长任务实现计划")
    assert finish_metadata["windowExecution"]["planningStub0_1"] == 0


