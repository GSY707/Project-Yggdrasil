from __future__ import annotations

from yggdrasil_sdk import TaskRepository, get_persistence_runtime, utc_now
from yggdrasil_sdk.llm_work_analysis import (
    analyze_llm_work_run,
    get_latest_llm_work_analysis_ref,
    load_persisted_llm_work_analysis,
)
from yggdrasil_sdk.persistence.repositories import RuntimeRepository, WorkspaceBootstrapRepository
from yggdrasil_sdk.support import ensure_state_subdir, write_json


def _seed_llm_work_case(*, task_id: str, run_id: str, invocation_id: str) -> None:
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        runtime_repository = RuntimeRepository(session)
        task_repository.create_task(
            {
                "id": task_id,
                "title": "LLM 工作分析测试任务",
                "goal": "验证运行过程分析器能输出多粒度视图。",
                "status": "running",
                "currentObjective": "输出分析报告",
                "currentFocus": "验证窗口与工具记录",
            }
        )
        run = task_repository.create_agent_run(
            task_id,
            {
                "id": run_id,
                "status": "completed",
                "selectedModel": "LongCat-2.0",
                "selectedProvider": "longcat",
                "windowIndex": 1,
                "restartCount": 0,
                "cumulativeWindowSpanTokens": 1200,
                "inputTokensUsed": 128,
                "outputTokensUsed": 64,
                "costUsed": 0.12,
            },
        )
        runtime_repository.create_model_invocation(
            {
                "id": invocation_id,
                "projectId": "project_default",
                "taskId": task_id,
                "agentRunId": run.id,
                "requestedModel": "LongCat-2.0",
                "requestedProvider": "longcat",
                "resolvedModel": "LongCat-2.0",
                "resolvedProvider": "longcat",
                "status": "completed",
                "assistantTextSummary": "已完成一次完整的工作分析。",
                "inputTokensUsed": 128,
                "outputTokensUsed": 64,
                "costUsed": 0.12,
                "latencyMs": 180.0,
                "startedAt": utc_now(),
                "endedAt": utc_now(),
                "createdAt": utc_now(),
            }
        )

    request_path = ensure_state_subdir("llm/requests") / f"{invocation_id}.json"
    response_path = ensure_state_subdir("llm/responses") / f"{invocation_id}.json"
    prompt_path = ensure_state_subdir("prompt/compiled") / f"{invocation_id}.json"
    metrics_path = ensure_state_subdir("runtime/metrics") / f"{invocation_id}.json"
    takeover_path = ensure_state_subdir("runtime/takeover") / f"{task_id}-{run_id}.json"
    work_context_path = ensure_state_subdir("runtime/work-context-stack") / f"{task_id}-{run_id}.json"
    window_path = ensure_state_subdir("runtime/window-executions") / f"{task_id}-{run_id}.json"
    window_history_path = ensure_state_subdir("runtime/window-executions/by-invocation") / f"{invocation_id}.json"

    write_json(
        request_path,
        {
            "invocationId": invocation_id,
            "taskId": task_id,
            "agentRunId": run_id,
            "auditLevel": "strict",
            "messages": [
                {"role": "system", "content": "系统提示"},
                {"role": "user", "content": "请分析当前运行过程。"},
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "read_file",
                        "description": "Read a file",
                        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}},
                    },
                }
            ],
        },
    )
    write_json(
        response_path,
        {
            "invocationId": invocation_id,
            "taskId": task_id,
            "agentRunId": run_id,
            "auditLevel": "strict",
            "mode": "live",
            "provider": "longcat",
            "model": "LongCat-2.0",
            "finishReason": "stop",
            "assistantText": "已完成一次完整的工作分析，并给出多粒度记录。",
            "usage": {
                "inputTokens": 128,
                "outputTokens": 64,
                "totalTokens": 192,
                "cacheHitInputTokens": 96,
                "cacheWriteInputTokens": 8,
                "nonCacheInputTokens": 32,
            },
            "costUsed": 0.12,
            "toolExecutions": [
                {
                    "tool": {"name": "read_file"},
                    "arguments": {"path": "README.md"},
                    "result": {
                        "status": "ok",
                        "sourceWorkTreeNodeId": "wt-node-1",
                        "content": "Project Yggdrasil"
                    },
                    "success": True,
                    "toolCallId": "toolcall_1",
                    "durationMs": 23,
                }
            ],
            "rounds": [
                {
                    "index": 0,
                    "mode": "live",
                    "finishReason": "tool-calls",
                    "latencyMs": 100.0,
                    "reasoningContentPresent": True,
                    "toolCalls": ["read_file"],
                    "toolFailures": [],
                },
                {
                    "index": 1,
                    "mode": "live",
                    "finishReason": "stop",
                    "latencyMs": 80.0,
                    "reasoningContentPresent": False,
                    "toolCalls": [],
                    "toolFailures": [],
                },
            ],
            "runtimeMetrics": {
                "windowIndex": 1,
                "restartCount": 0,
                "effectiveContextWindow": 64000,
                "windowRestartThreshold": 60000,
                "windowSpanTokens": 1200,
                "cumulativeWindowSpanTokens": 1200,
            },
        },
    )
    write_json(
        prompt_path,
        {
            "appId": "yggdrasil.app.base",
            "modelInvocationId": invocation_id,
            "auditLevel": "strict",
            "prompt": {
                "runType": "main",
                "taskType": "generic",
                "scenario": "analysis",
            },
            "messages": [
                {"role": "system", "content": "系统提示"},
                {"role": "user", "content": "请分析当前运行过程。"},
            ],
        },
    )
    write_json(
        metrics_path,
        {
            "taskId": task_id,
            "invocationId": invocation_id,
            "snapshot": {
                "windowIndex": 1,
                "restartCount": 0,
                "cacheHitInputTokens": 96,
                "cacheWriteInputTokens": 8,
                "nonCacheInputTokens": 32,
                "cumulativeWindowSpanTokens": 1200,
            },
        },
    )
    write_json(
        takeover_path,
        {
            "workTree": {
                "currentNodeId": "wt-node-1",
                "status": "active",
                "recoveryAnchor": "resume:wt-node-1",
            }
        },
    )
    write_json(
        work_context_path,
        {
            "frames": [
                {
                    "id": "frame-root",
                    "nodeId": "wt-node-1",
                    "frameHeader": "当前工作节点",
                    "cursorState": "resume-parent-summary",
                    "childCompletionSummaries": [
                        {"childNodeId": "child-1", "status": "failed", "summary": "子节点一失败并已上浮。"},
                        {"childNodeId": "child-2", "status": "completed", "summary": "子节点二已完成。"},
                    ],
                }
            ]
        },
    )
    window_record = {
        "taskId": task_id,
        "runId": run_id,
        "agentRunId": run_id,
        "invocationId": invocation_id,
        "windowIndex": 1,
        "restartCount": 0,
        "transitionStage": "task-complete",
        "transitionOutcome": "awaiting-approval",
        "currentObjective": "输出分析报告",
        "currentFocus": "验证窗口与工具记录",
        "sourceSnapshotId": None,
        "targetSnapshotId": None,
        "resumePath": None,
        "restartTrigger": None,
        "workTreeCurrentNodeId": "wt-node-1",
        "workTreeStatus": "awaiting-approval",
        "workTreeRecoveryAnchor": "resume:wt-node-1",
        "topFrameId": "frame-root",
        "topFramePrefixCacheKey": "prefix-root-001",
        "memoryRetrievalState": {
            "matchedNodeCount": 3,
            "materializedNodeCount": 1,
            "retrievalFingerprint": "fingerprint-1",
        },
        "cacheSummary": {
            "inputTokens": 128,
            "cacheHitInputTokens": 96,
            "cacheWriteInputTokens": 8,
            "nonCacheInputTokens": 32,
            "trackedInputTokens": 136,
            "cacheHitRatio0_1": 0.7059,
            "cacheWriteRatio0_1": 0.0588,
        },
        "workTreeDebug": {
            "topFrameId": "frame-root",
            "topFrameNodeId": "wt-node-1",
            "topFramePrefixCacheKey": "prefix-root-001",
            "continuationReason": "resume-parent-summary",
            "reworkReason": "resume-parent-summary",
            "approvalStop0_1": 1,
            "childBubble0_1": 0,
            "mixedOutcome0_1": 1,
            "childStatusCounts": {"failed": 1, "completed": 1},
            "framePath": [
                {
                    "frameId": "frame-root",
                    "nodeId": "wt-node-1",
                    "parentFrameId": None,
                    "stackDepth": 0,
                    "status": "active",
                    "cursorState": "resume-parent-summary",
                    "frameHeader": "当前工作节点",
                    "prefixCacheKey": "prefix-root-001",
                    "childCompletionCount": 2,
                    "childCompletionStatuses": ["failed", "completed"],
                }
            ],
            "recentChildCompletionSummaries": [
                {"frameId": "frame-root", "nodeId": "wt-node-1", "childNodeId": "child-1", "status": "failed", "summary": "子节点一失败并已上浮。"},
                {"frameId": "frame-root", "nodeId": "wt-node-1", "childNodeId": "child-2", "status": "completed", "summary": "子节点二已完成。"},
            ],
        },
        "llm": {"planningStub0_1": 0},
    }
    write_json(window_path, window_record)
    write_json(window_history_path, window_record)


def test_llm_work_analysis_builds_multigranularity_payload() -> None:
    task_id = "task_llm_work_analysis"
    run_id = "run_llm_work_analysis"
    invocation_id = "llm_llm_work_analysis"
    _seed_llm_work_case(task_id=task_id, run_id=run_id, invocation_id=invocation_id)

    payload = analyze_llm_work_run(task_id=task_id, persist=True)

    assert payload["summary"]["windowCount"] == 1
    assert payload["coverage"]["requestArtifactsAvailable"] == 1
    assert payload["windows"][0]["workTreeCurrentNodeId"] == "wt-node-1"
    assert payload["windows"][0]["memoryRetrievalState"]["retrievalFingerprint"] == "fingerprint-1"
    assert payload["windows"][0]["topFramePrefixCacheKey"] == "prefix-root-001"
    assert payload["windows"][0]["cacheSummary"]["cacheHitInputTokens"] == 96
    assert payload["windows"][0]["workTreeDebug"]["mixedOutcome0_1"] == 1
    assert payload["turns"][0]["toolCallCount"] == 1
    assert payload["tools"][0]["toolName"] == "read_file"
    assert payload["summary"]["cacheSummary"]["cacheHitInputTokens"] == 96
    assert payload["summary"]["workTreeDebug"]["approvalStopCount"] == 1
    assert payload["summary"]["workTreeDebug"]["timeline"][0]["topFramePrefixCacheKey"] == "prefix-root-001"
    assert payload["analysis"]["analysisRef"]["locator"]

    latest = get_latest_llm_work_analysis_ref(task_id)
    assert latest is not None
    assert latest["analysisId"] == payload["analysis"]["analysisId"]

    filtered = load_persisted_llm_work_analysis(payload["analysis"]["analysisId"], granularities="tool")
    assert "tools" in filtered
    assert "windows" not in filtered
