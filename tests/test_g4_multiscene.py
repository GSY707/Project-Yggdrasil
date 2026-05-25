from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

from yggdrasil_sdk.evaluation_runtime.bootstrap import _seed_runtime_task, isolated_runtime_environment, local_evaluation_runtime_environment
import yggdrasil_sdk.evaluation_runtime.scorer as evaluation_scorer
import yggdrasil_sdk.evaluation_runtime.suite_cases_g4 as suite_cases_g4
from yggdrasil_sdk import list_evaluation_suite_definitions, run_evaluation_suite


def test_seed_runtime_task_can_skip_token_cap_for_live_provider_matrix() -> None:
    task = _seed_runtime_task(
        "eval_task_g4_unbounded_token_budget",
        token_budget_total=None,
        cost_budget_total=5.0,
    )

    assert task["budget"]["tokenBudgetTotal"] is None
    assert task["budget"]["costBudgetTotal"] == 5.0


def test_g4_multiscene_suite_passes_official_scene_contracts() -> None:
    suites = {definition["id"]: definition for definition in list_evaluation_suite_definitions()}

    assert "evalsuite_g4_multiscene" in suites
    assert "evalsuite_g4_provider_matrix" in suites

    result = run_evaluation_suite("evalsuite_g4_multiscene")

    metrics = result["metrics"]
    assert isinstance(metrics.get("cases"), list)
    recovery_rows = [case for case in metrics["cases"] if case["scenario"] == "g4.scene_runtime_recovery"]
    assert len(recovery_rows) == 3
    assert {case["id"] for case in recovery_rows} == {
        "evalcase_g4_coding_recovery",
        "evalcase_g4_research_recovery",
        "evalcase_g4_writing_recovery",
    }


def test_g4_multiscene_suite_encodes_single_path_recovery_contracts() -> None:
    suites = {definition["id"]: definition for definition in list_evaluation_suite_definitions()}

    suite = suites["evalsuite_g4_multiscene"]
    recovery_cases = {
        case["appId"]: case
        for case in suite["cases"]
        if case["scenario"] == "g4.scene_runtime_recovery"
    }

    assert recovery_cases["yggdrasil.app.coding-greenfield"]["expectedResultStatus"] == "awaiting-approval"
    assert recovery_cases["yggdrasil.app.coding-greenfield"]["expectedTaskStatus"] == "awaiting-approval"
    assert recovery_cases["yggdrasil.app.coding-greenfield"]["expectedWorkTreeStatus"] == "awaiting-approval"
    assert recovery_cases["yggdrasil.app.deep-research"]["expectedResultStatus"] == "awaiting-approval"
    assert recovery_cases["yggdrasil.app.deep-research"]["expectedTaskStatus"] == "awaiting-approval"
    assert recovery_cases["yggdrasil.app.deep-research"]["expectedWorkTreeStatus"] == "awaiting-approval"
    assert recovery_cases["yggdrasil.app.epic-writing"]["expectedResultStatus"] == "awaiting-approval"
    assert recovery_cases["yggdrasil.app.epic-writing"]["expectedTaskStatus"] == "awaiting-approval"
    assert recovery_cases["yggdrasil.app.epic-writing"]["expectedWorkTreeStatus"] == "awaiting-approval"


def test_g4_longform_provider_matrix_suite_focuses_on_one_task() -> None:
    suites = {definition["id"]: definition for definition in list_evaluation_suite_definitions()}

    suite = suites["evalsuite_g4_provider_matrix_longform"]
    cases = suite["cases"]

    assert len(cases) == 2
    assert {case["matrixKey"] for case in cases} == {"g4-coding-longform"}
    assert {case["requestedProvider"] for case in cases} == {"deepseek_direct", "longcat"}
    assert {case["appId"] for case in cases} == {"yggdrasil.app.coding-greenfield"}
    assert {case["expectedSeedTemplateId"] for case in cases} == {"yggdrasil.seed.coding.new-project"}
    for case in cases:
        assert case["maxTokens"] >= 1200
        assert len(case["taskGoal"]) >= 600
        assert len(case["currentContext"]) >= 4
        assert case["workspaceProfile"] == "g4-longform-single-task"


def test_g4_window_restart_stress_suite_targets_longcat_and_deepseek() -> None:
    suites = {definition["id"]: definition for definition in list_evaluation_suite_definitions()}

    suite = suites["evalsuite_g4_window_restart_stress"]
    cases = suite["cases"]

    assert len(cases) == 2
    assert {case["requestedProvider"] for case in cases} == {"deepseek_direct", "longcat"}
    assert {case["forcedWindowRestartBudget"] for case in cases} == {100}
    assert {case["effectiveContextWindow"] for case in cases} == {120}
    assert {case["maxWindowCycles"] for case in cases} == {120}


def test_g4_real_task_window_parity_suite_uses_free_default_and_small_paid_approval() -> None:
    suites = {definition["id"]: definition for definition in list_evaluation_suite_definitions()}

    suite = suites["evalsuite_g4_real_task_window_parity"]
    cases = suite["cases"]

    assert len(cases) == 4
    assert {case["requestedProvider"] for case in cases} == {"longcat", "deepseek_direct"}
    assert len([case for case in cases if bool(case.get("allowPaidModels"))]) == 2
    assert {case["costBudgetTotal"] for case in cases if case["requestedProvider"] == "deepseek_direct"} == {2.0}
    assert {case["parityPairKey"] for case in cases} == {"g4-real-task-window-parity", "g4-real-task-window-parity-deepseek"}
    assert {case.get("auditLevel") for case in cases} == {"strict"}


def test_g4_real_task_minimal_workset_suite_uses_strict_audit_and_no_repo_wide_globs() -> None:
    suites = {definition["id"]: definition for definition in list_evaluation_suite_definitions()}

    suite = suites["evalsuite_g4_real_task_minimal_workset"]
    cases = suite["cases"]

    assert len(cases) == 4
    assert {case["requestedProvider"] for case in cases} == {"deepseek_direct", "longcat"}
    assert {case.get("auditLevel") for case in cases} == {"strict"}
    assert all(not case.get("currentContextGlobs") for case in cases)
    assert {case["parityPairKey"] for case in cases} == {
        "g4-real-task-minimal-workset",
        "g4-real-task-minimal-workset-deepseek",
    }


def test_g4_live_provider_matrix_start_payload_preserves_explicit_takeover_protocol() -> None:
    explicit_protocol = {
        "id": "takeover_debug_case",
        "version": "0.1.0",
        "taskId": "placeholder-task",
        "taskType": "coding",
        "runType": "main",
        "currentPhase": "execute",
        "status": "executing",
        "objective": "调试工作树。",
        "workTree": {
            "version": "0.2.0",
            "id": "work_tree_debug_case",
            "taskId": "placeholder-task",
            "rootNodeId": "root",
            "rootObjective": "调试工作树。",
            "status": "active",
            "currentNodeId": "child-1",
            "loadedNodeIds": ["root", "child-1"],
            "activePathNodeIds": ["root", "child-1"],
            "pcMemo": "continue:child-1",
            "entropyBudgetRemaining": 8,
            "versionCounter": 1,
            "nodes": [
                {
                    "id": "root",
                    "title": "根节点",
                    "parentNodeId": None,
                    "questionsItAnswers": ["最终工作树调试结论是什么"],
                    "nodeText": "汇总工作树调试结果。",
                    "localGoal": "汇总工作树调试结果。",
                    "workingNodeAnnotation": "<Working_Node: root>",
                    "phase": "delivery",
                    "status": "in-progress",
                    "childNodeIds": ["child-1"],
                    "detailLevel": 0,
                    "recoveryAnchor": "resume:root",
                },
                {
                    "id": "child-1",
                    "title": "子节点一",
                    "parentNodeId": "root",
                    "questionsItAnswers": ["当前子节点完成了吗"],
                    "nodeText": "重建目标工作树。",
                    "localGoal": "重建目标工作树。",
                    "workingNodeAnnotation": "<Working_Node: child-1>",
                    "phase": "executing",
                    "status": "in-progress",
                    "childNodeIds": [],
                    "detailLevel": 1,
                    "recoveryAnchor": "resume:child-1",
                },
            ],
        },
    }

    start_payload = suite_cases_g4._g4_live_provider_matrix_start_payload(
        {
            "currentFocus": "g4-real-task-work-tree-debug",
            "currentObjective": "验证显式工作树会被 live case 透传。",
            "currentContext": [
                {
                    "id": "ctx_work_tree_debug",
                    "title": "work tree debug",
                    "content": "调试显式嵌套工作树。",
                    "importance": 1.0,
                }
            ],
            "takeoverProtocol": explicit_protocol,
            "effectiveContextWindow": 64000,
            "forcedWindowRestartBudget": 6,
            "responseRequirements": "输出正式工作树调试报告。",
        },
        {"id": "task_live_debug", "currentFocus": "fallback-focus", "currentObjective": "fallback-objective"},
        app_id="yggdrasil.app.coding-greenfield",
        task_type="coding",
        candidate_models=[{"provider": "longcat", "model": "LongCat-2.0-Preview"}],
    )

    assert start_payload["takeoverProtocol"]["taskId"] == "task_live_debug"
    assert start_payload["takeoverProtocol"]["workTree"]["taskId"] == "task_live_debug"
    assert start_payload["takeoverProtocol"]["workTree"]["currentNodeId"] == "child-1"
    assert explicit_protocol["taskId"] == "placeholder-task"
    assert explicit_protocol["workTree"]["taskId"] == "placeholder-task"
    assert start_payload["candidateModels"][0]["provider"] == "longcat"


def test_g4_real_task_work_tree_debug_suite_uses_nested_work_tree_and_strict_audit() -> None:
    suites = {definition["id"]: definition for definition in list_evaluation_suite_definitions()}

    suite = suites["evalsuite_g4_real_task_work_tree_debug"]
    cases = suite["cases"]

    assert len(cases) == 2
    assert {case["requestedProvider"] for case in cases} == {"longcat"}
    assert {case.get("auditLevel") for case in cases} == {"strict"}
    assert all(not case.get("currentContextGlobs") for case in cases)
    assert {case["parityPairKey"] for case in cases} == {"g4-real-task-work-tree-debug"}
    assert {case["takeoverProtocol"]["workTree"]["currentNodeId"] for case in cases} == {"child-1"}
    assert {
        tuple(case["acceptanceRequiredSections"])
        for case in cases
    } == {
        (
            "目标工作树模型",
            "实际执行路径",
            "节点与窗口一致性",
            "失败与上浮语义",
            "approval 与完成语义",
            "差距判断",
            "下一步",
        )
    }
    for case in cases:
        paths = {item["path"] for item in case["currentContextFiles"]}
        assert "docs/specs/work-tree-protocol-v0.2.md" in paths
        assert "docs/specs/agent-runtime-protocol-v0.2.md" in paths
        assert "packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/takeover.py" in paths
        assert "packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop_part_b.py" in paths
        assert "tests/test_runtime_p4_foundation.py" in paths
        assert case["acceptanceMinRestartCount"] == 0
        assert case["acceptanceMinWindowIndex"] == 1
        assert case["acceptanceMinCumulativeWindowSpanTokens"] == 0


def test_g4_contract_verification_accepts_work_tree_debug_report() -> None:
    response_text = "\n".join(
        [
            "## 1. 目标工作树模型",
            "工作树应当是执行栈和工作记忆，根节点只负责最终汇总，当前工作由子节点推进。",
            "## 2. 实际执行路径",
            "本次真实任务按 child-1 -> child-2 -> root 的路径推进，并在窗口切换后继续沿当前节点恢复。",
            "## 3. 节点与窗口一致性",
            "currentNodeId、WorkContextStack top frame、Working_Node 与 retrieval 节点指针保持一致。",
            "## 4. 失败与上浮语义",
            "叶子失败时应写 failureSummary 并把失败摘要上浮到父节点，而不是直接把整棵树打死。",
            "## 5. approval 与完成语义",
            "根节点完成后应进入 awaiting-approval，而不是直接 completed。",
            "## 6. 差距判断",
            "当前真实任务 harness 与目标模型不一致，因为 live case 过去默认 root-only，直到显式 takeoverProtocol 被透传后才具备调试基础。",
            "## 7. 下一步",
            "继续用真实任务工件验证窗口级 currentNodeId、stack 与 approval 链路。",
        ]
    )

    result = suite_cases_g4._g4_contract_verification_results(
        {
            "acceptanceRequiredSections": [
                "目标工作树模型",
                "实际执行路径",
                "节点与窗口一致性",
                "失败与上浮语义",
                "approval 与完成语义",
                "差距判断",
                "下一步",
            ],
            "acceptanceRequiredPhrases": ["工作树"],
            "acceptanceRequiredAnyPhrases": ["一致", "不一致"],
            "acceptanceRejectPhrases": ["我会先总结当前局势，再给出最稳妥的下一步"],
            "acceptanceMinRestartCount": 1,
            "acceptanceMinWindowIndex": 2,
            "acceptanceMinCumulativeWindowSpanTokens": 150000,
            "acceptanceMinWorkTreeContinuity0_1": 1.0,
            "acceptanceMinMinimalWorksetRatio0_1": 0.25,
            "acceptanceMaxRetrievalDriftRate0_1": 0.0,
            "acceptanceRequirePrefixCacheKey": True,
            "acceptanceMinCacheEvidence0_1": 1.0,
        },
        response_text,
        {
            "restartCount": 1,
            "windowIndex": 2,
            "cumulativeWindowSpanTokens": 180000,
        },
        {
            "workTreeContinuity0_1": 1.0,
            "minimalWorksetRatio0_1": 0.41,
            "retrievalDriftRate0_1": 0.0,
            "prefixCacheReady0_1": 1.0,
            "cacheEvidence0_1": 1.0,
        },
    )

    assert result["enabled"] is True
    assert result["passed"] is True
    assert result["issues"] == []


def test_isolated_runtime_environment_resets_paid_gate_unless_case_explicitly_allows_it() -> None:
    previous = os.environ.get("YGGDRASIL_ALLOW_PAID_MODELS")
    os.environ["YGGDRASIL_ALLOW_PAID_MODELS"] = "1"
    try:
        with isolated_runtime_environment(disable_live_llm=True):
            assert os.environ.get("YGGDRASIL_ALLOW_PAID_MODELS") is None
        with isolated_runtime_environment(disable_live_llm=True, allow_paid_models=True):
            assert os.environ.get("YGGDRASIL_ALLOW_PAID_MODELS") == "1"
    finally:
        if previous is None:
            os.environ.pop("YGGDRASIL_ALLOW_PAID_MODELS", None)
        else:
            os.environ["YGGDRASIL_ALLOW_PAID_MODELS"] = previous


def test_local_evaluation_runtime_environment_keeps_preserved_case_sandboxes_under_persistent_state_root(
    tmp_path,
    monkeypatch,
) -> None:
    state_root = tmp_path / "persistent-eval-root"
    monkeypatch.setenv("YGGDRASIL_STATE_ROOT", state_root.as_posix())
    monkeypatch.setenv("YGGDRASIL_EVAL_PRESERVE_SANDBOX", "1")

    with local_evaluation_runtime_environment(disable_live_llm=True):
        assert Path(os.environ["YGGDRASIL_STATE_ROOT"]).resolve() == state_root.resolve()
        assert Path(os.environ["YGGDRASIL_STATE_DIR"]).resolve() == (state_root / "state").resolve()
        with isolated_runtime_environment(disable_live_llm=True):
            sandbox_root = Path(os.environ["YGGDRASIL_EVAL_ACTIVE_SANDBOX_ROOT"]).resolve()

        assert str(sandbox_root).startswith(str((state_root / "state" / "evaluation-sandboxes").resolve()))


def test_g4_provider_matrix_metrics_capture_token_and_context_usage() -> None:
    invocation = SimpleNamespace(input_tokens_used=3200, output_tokens_used=400)
    response_payload = {
        "usage": {
            "inputTokens": 3200,
            "outputTokens": 400,
            "totalTokens": 3600,
            "cacheHitInputTokens": 2400,
            "cacheWriteInputTokens": 300,
            "nonCacheInputTokens": 800,
            "reasoningTokens": 120,
        },
        "contextLengthObservations": [
            {"phase": "beforeContextPruning", "source": "currentContext", "estimatedTokens": 1800, "itemCount": 2},
            {"phase": "taskEnd", "source": "conversationMessages", "estimatedTokens": 1400, "messageCount": 3},
        ],
        "runtimeMetrics": {
            "windowIndex": 3,
            "restartCount": 2,
            "compressionCount": 2,
            "cumulativeWindowSpanTokens": 6400,
            "carryForwardLossCount": 0,
            "effectiveContextWindow": 120,
            "windowRestartThreshold": 90,
        },
    }

    token_usage = suite_cases_g4._g4_token_usage(invocation, response_payload)
    observations = suite_cases_g4._g4_context_length_observations(response_payload)
    runtime_metrics = suite_cases_g4._g4_runtime_metrics(response_payload)

    assert token_usage["totalTokens"] == 3600
    assert token_usage["cacheHitInputTokens"] == 2400
    assert token_usage["nonCacheInputTokens"] == 800
    assert suite_cases_g4._g4_max_context_length_tokens(observations) == 1800
    assert runtime_metrics["restartCount"] == 2
    assert runtime_metrics["effectiveContextWindow"] == 120


def test_g4_contract_verification_detects_planning_stub_and_missing_restart_evidence() -> None:
    result = suite_cases_g4._g4_contract_verification_results(
        {
            "acceptanceRequiredSections": ["任务价值判断", "acceptance 对照结论"],
            "acceptanceRequiredPhrases": ["高价值"],
            "acceptanceRequiredAnyPhrases": ["等价", "不等价"],
            "acceptanceRejectPhrases": ["我会先总结当前局势，再给出最稳妥的下一步"],
            "acceptanceMinRestartCount": 1,
            "acceptanceMinWindowIndex": 2,
            "acceptanceMinCumulativeWindowSpanTokens": 1000000,
        },
        "我会先总结当前局势，再给出最稳妥的下一步。\n下一步：定位实现面。",
        {
            "restartCount": 0,
            "windowIndex": 1,
            "cumulativeWindowSpanTokens": 0,
        },
    )

    assert result["enabled"] is True
    assert result["passed"] is False
    assert any("缺少必需小节" in issue for issue in result["issues"])
    assert any("缺少必需短语" in issue for issue in result["issues"])
    assert any("命中拒绝短语" in issue for issue in result["issues"])
    assert any("restartCount 不足" in issue for issue in result["issues"])
    assert any("windowIndex 不足" in issue for issue in result["issues"])
    assert any("cumulativeWindowSpanTokens 不足" in issue for issue in result["issues"])


def test_g4_contract_verification_accepts_release_brief_with_restart_evidence() -> None:
    response_text = "\n".join(
        [
            "1) 任务价值判断",
            "这是当前仓库的高价值真实任务，因为它直接检验跨 runtime、evaluation、protocol、provider 和文档证据面的 release readiness。",
            "2) 联调覆盖范围",
            "覆盖 runtime、evaluation、protocol、provider、documentation 和 evidence。",
            "3) 关键集成链路",
            "记忆树检索、work tree 恢复、snapshot carry-forward、评分与文档证据串联。",
            "4) short-window 配置",
            "64k，允许更高时延但不能降低最终交付质量。",
            "5) long-window 配置",
            "128k，作为更宽工作集参考路径。",
            "6) acceptance 对照结论",
            "当前两条路径不等价，因为 short-window 在恢复态仍可能漂移到 planning stub。",
            "7) 风险与下一步",
            "继续冻结 restart contract 与正式验收器。",
        ]
    )

    result = suite_cases_g4._g4_contract_verification_results(
        {
            "acceptanceRequiredSections": [
                "任务价值判断",
                "联调覆盖范围",
                "关键集成链路",
                "short-window 配置",
                "long-window 配置",
                "acceptance 对照结论",
                "风险与下一步",
            ],
            "acceptanceRequiredPhrases": ["高价值"],
            "acceptanceRequiredAnyPhrases": ["等价", "不等价"],
            "acceptanceRejectPhrases": ["我会先总结当前局势，再给出最稳妥的下一步"],
            "acceptanceMinRestartCount": 1,
            "acceptanceMinWindowIndex": 2,
            "acceptanceMinCumulativeWindowSpanTokens": 1000000,
        },
        response_text,
        {
            "restartCount": 1,
            "windowIndex": 2,
            "cumulativeWindowSpanTokens": 1500000,
        },
    )

    assert result["enabled"] is True
    assert result["passed"] is True
    assert result["issues"] == []


def test_g4_window_execution_metrics_detects_continuity_and_minimal_workset() -> None:
    metrics = suite_cases_g4._g4_window_execution_metrics(
        [
            {
                "workTreeCurrentNodeId": "wt-node-1",
                "responseRequirementsDigest": "resp-1",
                "restartMessageDigest": "restart-1",
                "stateFingerprint": "fp-1",
                "topFramePrefixCacheKey": "prefix-1",
                "effectiveContextWindow": 100,
                "currentContextTokenEstimate": 70,
                "cacheSummary": {"cacheHitInputTokens": 24, "cacheWriteInputTokens": 0},
                "memoryRetrievalState": {
                    "reverseTraceMode": True,
                    "workTreeNodeId": "wt-node-1",
                },
                "llm": {"planningStub0_1": 0},
            },
            {
                "workTreeCurrentNodeId": "wt-node-2",
                "responseRequirementsDigest": "resp-2",
                "restartMessageDigest": "restart-2",
                "stateFingerprint": "fp-2",
                "topFramePrefixCacheKey": "prefix-2",
                "effectiveContextWindow": 100,
                "currentContextTokenEstimate": 20,
                "cacheSummary": {"cacheHitInputTokens": 0, "cacheWriteInputTokens": 12},
                "memoryRetrievalState": {
                    "reverseTraceMode": True,
                    "workTreeNodeId": "wt-node-2",
                },
                "llm": {"planningStub0_1": 1},
            },
        ]
    )

    assert metrics["windowExecutionCount"] == 2
    assert metrics["workTreeContinuity0_1"] == 1
    assert metrics["minimalWorksetRatio0_1"] == 0.55
    assert metrics["planningStubRate0_1"] == 0.5
    assert metrics["retrievalDriftRate0_1"] == 0.0
    assert metrics["prefixCacheReady0_1"] == 1.0
    assert metrics["cacheEvidence0_1"] == 1.0


def test_g4_provider_matrix_summary_aggregates_new_metrics() -> None:
    summary = evaluation_scorer._provider_matrix_summary(
        [
            {
                "provider": "deepseek_direct",
                "model": "deepseek-v4-pro",
                "pass": True,
                "firstTokenSeconds": 1.5,
                "firstUsefulOutputSeconds": 10.0,
                "planQualityScore0_100": 96.0,
                "reworkRate": 0.0,
                "totalTokens": 3600,
                "outputTokens": 400,
                "cacheHitInputTokens": 2400,
                "nonCacheInputTokens": 800,
                "cacheWriteInputTokens": 300,
                "reasoningTokens": 120,
                "maxContextLengthTokens": 1800,
                "restartCount": 2,
                "compressionCount": 2,
                "cumulativeWindowSpanTokens": 6400,
                "carryForwardLossCount": 0,
                "effectiveContextWindow": 120,
            },
            {
                "provider": "deepseek_direct",
                "model": "deepseek-v4-pro",
                "pass": True,
                "firstTokenSeconds": 2.5,
                "firstUsefulOutputSeconds": 20.0,
                "planQualityScore0_100": 94.0,
                "reworkRate": 0.0,
                "totalTokens": 2400,
                "outputTokens": 300,
                "cacheHitInputTokens": 1200,
                "nonCacheInputTokens": 900,
                "cacheWriteInputTokens": 100,
                "reasoningTokens": 60,
                "maxContextLengthTokens": 1500,
                "restartCount": 4,
                "compressionCount": 4,
                "cumulativeWindowSpanTokens": 12800,
                "carryForwardLossCount": 0,
                "effectiveContextWindow": 120,
            },
        ]
    )

    provider_summary = summary["providerSummary"][0]
    assert provider_summary["avgTotalTokens"] == 3000.0
    assert provider_summary["avgOutputTokens"] == 350.0
    assert provider_summary["avgCacheHitInputTokens"] == 1800.0
    assert provider_summary["avgNonCacheInputTokens"] == 850.0
    assert provider_summary["avgCacheWriteInputTokens"] == 200.0
    assert provider_summary["avgReasoningTokens"] == 90.0
    assert provider_summary["avgMaxContextLengthTokens"] == 1650.0
    assert provider_summary["avgRestartCount"] == 3.0
    assert provider_summary["avgCompressionCount"] == 3.0
    assert provider_summary["avgCumulativeWindowSpanTokens"] == 9600.0
    assert provider_summary["avgCarryForwardLossCount"] == 0.0
    assert provider_summary["avgEffectiveContextWindow"] == 120.0


def test_g4_live_provider_matrix_case_overflow_fails_without_restart_handoff() -> None:
    from fastapi.testclient import TestClient

    from yggdrasil_agent_runtime.app import app as runtime_app
    from yggdrasil_worker.registry import run_worker_once

    task = _seed_runtime_task(
        "eval_task_g4_window_overflow_single_path",
        app_id="yggdrasil.app.coding-greenfield",
        title="Local G4 Window Overflow",
        goal="Validate overflow handling uses fail-in-place instead of restart handoff.",
        current_focus="g4-window-overflow-single-path",
        current_objective="Force overflow and verify runtime fails the current branch.",
    )
    client = TestClient(runtime_app)
    started = client.post(
        f"/runtime/tasks/{task['id']}/start",
        json={
            "appId": "yggdrasil.app.coding-greenfield",
            "taskType": "coding",
            "currentFocus": "g4-window-overflow-single-path",
            "currentObjective": "Force overflow and verify runtime fails the current branch.",
            "currentContext": [
                {
                    "id": "ctx_g4_window_overflow_single_path",
                    "title": "window overflow context",
                    "content": "This context intentionally exceeds the tiny window threshold to trigger overflow handling without restart. " * 8,
                    "importance": 0.99,
                }
            ],
            "allowModelFallback": True,
            "allowToolExecution": False,
            "temperature": 0.1,
            "maxTokens": 220,
            "effectiveContextWindow": 120,
            "windowRestartRatio": 0.75,
            "forcedWindowRestartBudget": 2,
        },
    )
    assert started.status_code == 202

    processed = run_worker_once("agent-runtime")
    assert processed["status"] == "processed"
    result = processed["result"]
    assert result["status"] == "failed"
    assert result["runtimeMetrics"]["restartCount"] == 0
    assert result["windowExecutionArtifact"]["record"]["transitionOutcome"] == "failed-window-overflow"
    assert "restart is deprecated" in str(result.get("detail") or "")


def test_g4_restart_stability_report_supports_tiered_thresholds() -> None:
    report = suite_cases_g4._g4_restart_stability_report(
        {"restartStabilityTiers": [30, 60, 100]},
        {"restartCount": 100},
        acceptance_pass=1,
    )

    assert report["enabled"] is True
    assert report["passed"] is True
    assert report["restartSuccessRate0_1"] == 1.0
    assert [item["targetRestarts"] for item in report["tiers"]] == [30, 60, 100]


def test_g4_aggregate_case_metrics_emits_real_task_window_parity_summary() -> None:
    payload = evaluation_scorer._aggregate_case_metrics(
        [
            {
                "id": "short",
                "title": "short",
                "detail": {
                    "providerMatrixEntry": {
                        "matrixKey": "g4-real-task-window-parity-short64k",
                        "parityRole": "short",
                        "goalCompletion0_1": 1,
                        "deliveryCompletion0_1": 1,
                        "workTreeContinuity0_1": 1,
                        "minimalWorksetRatio0_1": 0.62,
                        "minimalWorksetThreshold0_1": 0.35,
                        "planQualityScore0_100": 94.0,
                        "qualityDeltaThreshold0_100": 8.0,
                    }
                },
            },
            {
                "id": "long",
                "title": "long",
                "detail": {
                    "providerMatrixEntry": {
                        "matrixKey": "g4-real-task-window-parity-long128k",
                        "parityRole": "long",
                        "goalCompletion0_1": 1,
                        "deliveryCompletion0_1": 1,
                        "workTreeContinuity0_1": 1,
                        "minimalWorksetRatio0_1": 0.73,
                        "minimalWorksetThreshold0_1": 0.35,
                        "planQualityScore0_100": 96.0,
                        "qualityDeltaThreshold0_100": 8.0,
                    }
                },
            },
        ]
    )

    parity = payload["realTaskWindowParity"]
    assert parity["goalCompletionParity0_1"] == 1
    assert parity["deliveryEquivalence0_1"] == 1
    assert parity["workTreeContinuity0_1"] == 1
    assert parity["minimalWorksetRatio0_1"] == 0.62
    assert parity["qualityDeltaToLongWindow0_100"] == 2.0
    assert parity["parityPassed0_1"] == 1


def test_g4_aggregate_case_metrics_splits_real_task_parity_by_provider_group() -> None:
    payload = evaluation_scorer._aggregate_case_metrics(
        [
            {
                "id": "short-longcat",
                "title": "short-longcat",
                "detail": {
                    "providerMatrixEntry": {
                        "matrixKey": "g4-real-task-window-parity-short64k",
                        "parityPairKey": "g4-real-task-window-parity",
                        "parityRole": "short",
                        "provider": "longcat",
                        "model": "LongCat-2.0-Preview",
                        "goalCompletion0_1": 1,
                        "deliveryCompletion0_1": 1,
                        "workTreeContinuity0_1": 1,
                        "minimalWorksetRatio0_1": 0.61,
                        "minimalWorksetThreshold0_1": 0.35,
                        "planQualityScore0_100": 94.0,
                        "qualityDeltaThreshold0_100": 8.0,
                    }
                },
            },
            {
                "id": "long-longcat",
                "title": "long-longcat",
                "detail": {
                    "providerMatrixEntry": {
                        "matrixKey": "g4-real-task-window-parity-long128k",
                        "parityPairKey": "g4-real-task-window-parity",
                        "parityRole": "long",
                        "provider": "longcat",
                        "model": "LongCat-2.0-Preview",
                        "goalCompletion0_1": 1,
                        "deliveryCompletion0_1": 1,
                        "workTreeContinuity0_1": 1,
                        "minimalWorksetRatio0_1": 0.74,
                        "minimalWorksetThreshold0_1": 0.35,
                        "planQualityScore0_100": 96.0,
                        "qualityDeltaThreshold0_100": 8.0,
                    }
                },
            },
            {
                "id": "short-deepseek",
                "title": "short-deepseek",
                "detail": {
                    "providerMatrixEntry": {
                        "matrixKey": "g4-real-task-window-parity-short64k-deepseek",
                        "parityPairKey": "g4-real-task-window-parity-deepseek",
                        "parityRole": "short",
                        "provider": "deepseek_direct",
                        "model": "deepseek-v4-pro",
                        "goalCompletion0_1": 1,
                        "deliveryCompletion0_1": 1,
                        "workTreeContinuity0_1": 1,
                        "minimalWorksetRatio0_1": 0.58,
                        "minimalWorksetThreshold0_1": 0.35,
                        "planQualityScore0_100": 93.0,
                        "qualityDeltaThreshold0_100": 8.0,
                    }
                },
            },
            {
                "id": "long-deepseek",
                "title": "long-deepseek",
                "detail": {
                    "providerMatrixEntry": {
                        "matrixKey": "g4-real-task-window-parity-long128k-deepseek",
                        "parityPairKey": "g4-real-task-window-parity-deepseek",
                        "parityRole": "long",
                        "provider": "deepseek_direct",
                        "model": "deepseek-v4-pro",
                        "goalCompletion0_1": 1,
                        "deliveryCompletion0_1": 1,
                        "workTreeContinuity0_1": 1,
                        "minimalWorksetRatio0_1": 0.7,
                        "minimalWorksetThreshold0_1": 0.35,
                        "planQualityScore0_100": 95.0,
                        "qualityDeltaThreshold0_100": 8.0,
                    }
                },
            },
        ]
    )

    parity = payload["realTaskWindowParity"]
    groups = payload["realTaskWindowParityGroups"]

    assert parity["groupCount"] == 2
    assert parity["passedGroupCount"] == 2
    assert parity["parityPassed0_1"] == 1
    assert len(groups) == 2
    assert {item["provider"] for item in groups} == {"longcat", "deepseek_direct"}
    assert all(item["parityPassed0_1"] == 1 for item in groups)