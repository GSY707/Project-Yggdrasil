from __future__ import annotations

from types import SimpleNamespace

from yggdrasil_sdk.evaluation_runtime.bootstrap import _seed_runtime_task
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

    assert result["run"]["status"] == "completed"
    metrics = result["metrics"]
    assert metrics["status"] == "completed"
    assert metrics["passRate"] == 1.0

    switch_case = next(case for case in metrics["cases"] if case["scenario"] == "g4.scene_switch_isolation")
    assert switch_case["status"] == "passed"
    assert switch_case["detail"]["sequence"] == [
        "yggdrasil.app.coding-greenfield",
        "yggdrasil.app.deep-research",
        "yggdrasil.app.epic-writing",
    ]


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
    assert all(item["returncode"] == 0 for item in result["checks"])


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


def test_g4_live_provider_matrix_case_handles_window_restart_chain() -> None:
    detail = suite_cases_g4._run_g4_live_provider_matrix_case(
        {
            "id": "evalcase_g4_window_restart_local",
            "matrixKey": "g4-window-restart-local",
            "appId": "yggdrasil.app.coding-greenfield",
            "taskType": "coding",
            "taskTitle": "Local G4 Window Restart",
            "taskGoal": "Validate that the provider-matrix runtime can survive multiple restart handoffs before the final model invocation.",
            "currentFocus": "g4-window-restart-local",
            "currentObjective": "Finish after two forced restart handoffs without losing the final delivery contract.",
            "currentContext": [
                {
                    "id": "ctx_g4_window_restart_local",
                    "title": "window restart local context",
                    "content": "This local provider-matrix regression deliberately uses a tiny effective window and two forced restart handoffs before the final fallback invocation. " * 6,
                    "importance": 0.99,
                }
            ],
            "requestedProvider": "longcat",
            "requestedModel": "LongCat-Flash-Lite",
            "allowFallback": True,
            "allowToolExecution": False,
            "requireLive": False,
            "temperature": 0.1,
            "maxTokens": 220,
            "effectiveContextWindow": 120,
            "windowRestartRatio": 0.75,
            "forcedWindowRestartBudget": 2,
            "maxWindowCycles": 6,
            "expectedPromptProfileId": "yggdrasil.coding-greenfield.main-agent",
            "expectedSeedTemplateId": "yggdrasil.seed.coding.new-project",
            "expectedCompiledFewShotRefs": [
                "yggdrasil.fewshot.coding-greenfield.spec-to-module-plan.v1",
                "yggdrasil.fewshot.coding-greenfield.incremental-delivery.v1",
                "yggdrasil.fewshot.scene-coding-new-project.scope-first-architecture.v1",
                "yggdrasil.fewshot.scene-coding-new-project.contract-driven-bootstrap.v1"
            ],
        }
    )

    assert detail["restartCount"] == 2
    assert detail["effectiveContextWindow"] == 120
    assert detail["windowTransitionCount"] == 2
    assert detail["restartSuccessRate0_1"] == 1.0
    assert detail["liveScenario"]["runtimeMetrics"]["restartCount"] == 2


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
    assert parity["qualityDeltaToLongWindow0_100"] == 2.0
    assert parity["parityPassed0_1"] == 1