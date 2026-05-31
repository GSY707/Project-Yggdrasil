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


def _single_root_protocol(task_id: str) -> dict[str, object]:
    return {
        "id": f"takeover_{task_id}",
        "version": "0.1.0",
        "taskId": task_id,
        "taskType": "coding",
        "runType": "main",
        "currentPhase": "execute",
        "status": "executing",
        "objective": "完成一次最小运行。",
        "objectiveSummary": "直接在根节点收尾并进入审批。",
        "ambiguities": [],
        "constraints": [],
        "plan": [],
        "workTree": {
            "version": "0.2.0",
            "id": f"work_tree_{task_id}",
            "taskId": task_id,
            "rootNodeId": "root",
            "rootObjective": "完成一次最小运行。",
            "status": "active",
            "currentNodeId": "root",
            "loadedNodeIds": ["root"],
            "activePathNodeIds": ["root"],
            "pcMemo": "continue:root",
            "entropyBudgetRemaining": 9,
            "versionCounter": 1,
            "nodes": [
                {
                    "id": "root",
                    "title": "根节点",
                    "parentNodeId": None,
                    "questionsItAnswers": ["最小运行是否完成"],
                    "nodeText": "完成最小运行并输出交付。",
                    "localGoal": "完成最小运行并输出交付。",
                    "workingNodeAnnotation": "<Working_Node: root>",
                    "phase": "delivery",
                    "status": "in-progress",
                    "childNodeIds": [],
                    "detailLevel": 0,
                    "recoveryAnchor": "resume:root",
                }
            ],
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
        "appliedModules": ["task-takeover"],
        "hookTrace": [],
    }

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
    assert processed["result"]["status"] == "paused"
    assert "budget exceeded after model invocation" in processed["result"]["detail"].lower()
    assert processed["result"]["snapshot"]["status"] == "restorable"

    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        runtime_repository = RuntimeRepository(session)
        task = task_repository.get_task("task_budget_actual_fail")
        assert task is not None
        assert task.status == "paused"
        assert task.active_snapshot_id is not None
        runs = task_repository.list_agent_runs("task_budget_actual_fail")
        assert len(runs) == 1
        assert runs[0].status == "paused"
        snapshots = task_repository.list_snapshots("task_budget_actual_fail")
        assert len(snapshots) == 1
        assert snapshots[0].status == "restorable"
        assert len(runtime_repository.list_model_route_decisions(task_id="task_budget_actual_fail")) == 1
        assert len(runtime_repository.list_model_invocations(task_id="task_budget_actual_fail")) == 1


def test_runtime_effective_context_window_does_not_hard_filter_candidates(monkeypatch) -> None:
    monkeypatch.setattr(
        runtime_execution_loop,
        "load_runtime_candidate_models",
        lambda: [
            {
                "model": "LongCat-2.0-Preview",
                "provider": "longcat",
                "quality": 0.9,
                "costPer1k": 0.001,
                "latencyMs": 120,
                "contextWindow": 128000,
                "freeTier": True,
            }
        ],
    )

    def _fake_invoke_model(**_kwargs):
        return {
            "mode": "live",
            "provider": "longcat",
            "model": "LongCat-2.0-Preview",
            "outputText": "## 结果\n完成\n## 证据\nhttp://example.com\n## 风险\n暂无\n## 已知问题\n暂无",
            "finishReason": "stop",
            "usage": {
                "inputTokens": 200,
                "outputTokens": 100,
                "totalTokens": 300,
            },
            "costUsed": 0.0,
            "error": None,
            "toolCalls": [],
            "rawResponse": {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": "## 结果\n完成\n## 证据\nhttp://example.com\n## 风险\n暂无\n## 已知问题\n暂无",
                        },
                    }
                ],
                "usage": {
                    "prompt_tokens": 200,
                    "completion_tokens": 100,
                    "total_tokens": 300,
                },
            },
            "requestPayload": {
                "model": "LongCat-2.0-Preview",
                "messages": [],
                "stream": True,
            },
            "firstTokenLatencyMs": 80.0,
        }

    monkeypatch.setattr(yggdrasil_model_providers, "invoke_model", _fake_invoke_model)

    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        TaskRepository(session).create_task(
            {
                "id": "task_effective_ctx_not_hard_filter",
                "title": "effective context soft routing",
                "goal": "验证 effectiveContextWindow 不会作为模型候选硬过滤条件。",
                "status": "draft",
                "budgetState": {
                    "tokenBudgetTotal": 5000,
                    "costBudgetTotal": 5.0,
                },
            }
        )

    started = client.post(
        "/runtime/tasks/task_effective_ctx_not_hard_filter/start",
        json={
            "effectiveContextWindow": 200000,
            "requestedProvider": "longcat",
            "requestedModel": "LongCat-2.0-Preview",
            "currentContext": [
                {
                    "id": "ctx_effective_ctx",
                    "title": "ctx",
                    "content": "保证能够进入模型调用，不在候选筛选阶段失败。",
                    "importance": 0.9,
                }
            ],
        },
    )
    assert started.status_code == 202

    processed = run_worker_once("agent-runtime")
    assert processed["status"] == "processed"
    assert processed["result"]["status"] != "failed"

    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        runtime_repository = RuntimeRepository(session)
        task = task_repository.get_task("task_effective_ctx_not_hard_filter")
        assert task is not None
        assert task.current_focus is None or "No viable candidate model" not in (task.current_focus or "")
        routes = runtime_repository.list_model_route_decisions(task_id="task_effective_ctx_not_hard_filter")
        assert len(routes) == 1
        assert routes[0].selected_model == "LongCat-2.0-Preview"


def test_runtime_audit_level_lean_writes_compact_artifacts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        runtime_execution_loop,
        "load_runtime_candidate_models",
        lambda: [
            {
                "model": "lean-audit-model",
                "provider": "lean-audit-provider",
                "quality": 0.8,
                "costPer1k": 0.001,
                "latencyMs": 50,
                "contextWindow": 1_000_000,
                "freeTier": True,
            }
        ],
    )

    def _fake_invoke_model(**_kwargs):
        formal_output = "## 结果\n完成\n\n## 证据\n已写入 lean 审计工件。\n\n## 风险\n无。\n\n## 已知问题\n无。"
        return {
            "mode": "live",
            "provider": "lean-audit-provider",
            "model": "lean-audit-model",
            "outputText": formal_output,
            "finishReason": "stop",
            "usage": {
                "inputTokens": 160,
                "outputTokens": 80,
                "totalTokens": 240,
            },
            "costUsed": 0.0,
            "error": None,
            "toolCalls": [],
            "rawResponse": {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": formal_output},
                    }
                ],
                "usage": {
                    "prompt_tokens": 160,
                    "completion_tokens": 80,
                    "total_tokens": 240,
                },
            },
            "requestPayload": {
                "model": "lean-audit-model",
                "messages": [],
                "stream": True,
            },
            "firstTokenLatencyMs": 50.0,
        }

    monkeypatch.setattr(yggdrasil_model_providers, "invoke_model", _fake_invoke_model)

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
            "takeoverProtocol": _single_root_protocol("task_audit_lean"),
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
    assert processed["result"]["status"] == "awaiting-approval"

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


def test_runtime_no_tool_prompt_does_not_expose_registered_tools(monkeypatch) -> None:
    monkeypatch.setattr(
        runtime_execution_loop,
        "load_runtime_candidate_models",
        lambda: [
            {
                "model": "no-tool-model",
                "provider": "no-tool-provider",
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
            "provider": "no-tool-provider",
            "model": "no-tool-model",
            "outputText": "# Result\n直接输出最终报告，不调用任何工具。\n# Evidence\n无需工具进行校验。",
            "finishReason": "stop",
            "usage": {
                "inputTokens": 120,
                "outputTokens": 60,
                "totalTokens": 180,
            },
            "costUsed": 0.0,
            "error": None,
            "toolCalls": [],
            "rawResponse": {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "# Result\n直接输出最终报告，不调用任何工具。\n# Evidence\n无需工具进行校验。"},
                    }
                ],
                "usage": {
                    "prompt_tokens": 120,
                    "completion_tokens": 60,
                    "total_tokens": 180,
                },
            },
            "requestPayload": {
                "model": "no-tool-model",
                "messages": [],
                "stream": True,
            },
            "firstTokenLatencyMs": 50.0,
        }

    monkeypatch.setattr(yggdrasil_model_providers, "invoke_model", _fake_invoke_model)

    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        TaskRepository(session).create_task(
            {
                "id": "task_no_tool_prompt",
                "title": "no tool prompt",
                "goal": "验证 allowToolExecution=false 时 prompt 不再暴露结构化工具。",
                "status": "draft",
                "currentObjective": "输出一份无需工具的最终说明。",
                "currentFocus": "no-tool-prompt",
                "budgetState": {
                    "tokenBudgetTotal": 1000,
                    "costBudgetTotal": 5.0,
                },
            }
        )

    started = client.post(
        "/runtime/tasks/task_no_tool_prompt/start",
        json={
            "auditLevel": "strict",
            "allowToolExecution": False,
            "currentFocus": "no-tool-prompt",
            "currentContext": [
                {
                    "id": "ctx_no_tool",
                    "title": "no tool context",
                    "content": "这个任务必须直接基于挂载上下文回答，不允许读取仓库文件或调用任何工具。",
                    "importance": 0.9,
                }
            ],
        },
    )
    assert started.status_code == 202

    processed = run_worker_once("agent-runtime")
    assert processed["status"] == "processed"
    assert processed["result"]["status"] == "awaiting-approval"

    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        prompt_repository = PromptAssetRepository(session)
        runtime_repository = RuntimeRepository(session)
        invocations = runtime_repository.list_model_invocations(task_id="task_no_tool_prompt")
        assert len(invocations) == 1
        artifact = prompt_repository.get_prompt_compile_artifact(str(invocations[0].prompt_compile_artifact_id))
        assert artifact is not None
        assert artifact.compiled_messages_ref is not None

        compiled_path = Path(resolve_workspace_root()) / artifact.compiled_messages_ref.locator
        compiled_payload = json.loads(compiled_path.read_text(encoding="utf-8"))

    compiled_text = "\n".join(str(message.get("content") or "") for message in compiled_payload["messages"])
    assert "当前没有通过模块 hook 暴露的结构化工具描述。" in compiled_text
    assert "mcp.read.read_file" not in compiled_text
    assert "mcp.execute.run_command" not in compiled_text


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
            "outputText": "已生成一份长任务实现计划。\n\n# Result\n已生成一份长任务实现计划。\n# Evidence\n经过本地运行测试确认指标落盘。",
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
                        "message": {"role": "assistant", "content": "已生成一份长任务实现计划。\n\n# Result\n已生成一份长任务实现计划。\n# Evidence\n经过本地运行测试确认指标落盘。"},
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
    assert processed["result"]["status"] == "awaiting-approval"

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


