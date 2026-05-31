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
    assert result["status"] == "continuing"
    assert result["runtimeMetrics"]["restartCount"] == 0
    assert result["queuedWorkItem"]["command"] == "start"
    assert result["windowExecutionArtifact"]["record"]["transitionOutcome"] == "bubble-parent-after-failure"
    assert "failure bubbling semantics" in str(result.get("detail") or "")
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
                        "matrixKey": "g4-web-research-default-grid-storage-short64k",
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
                        "matrixKey": "g4-web-research-default-grid-storage-long128k",
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
                        "matrixKey": "g4-web-research-default-grid-storage-short64k",
                        "parityPairKey": "g4-web-research-default-grid-storage",
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
                        "matrixKey": "g4-web-research-default-grid-storage-long128k",
                        "parityPairKey": "g4-web-research-default-grid-storage",
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
                        "matrixKey": "g4-web-research-default-grid-storage-short64k-deepseek",
                        "parityPairKey": "g4-web-research-default-grid-storage-deepseek",
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
                        "matrixKey": "g4-web-research-default-grid-storage-long128k-deepseek",
                        "parityPairKey": "g4-web-research-default-grid-storage-deepseek",
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
def test_g4_manual_review_report_single_reviewer_pending_after_auto_pass() -> None:
    report = suite_cases_g4._g4_manual_review_report(
        {
            "acceptanceRequireHumanReview": True,
            "humanReviewMode": "single-reviewer",
            "humanReviewersRequired": 1,
        },
        {"passed": True},
    )

    assert report["required"] is True
    assert report["mode"] == "single-reviewer"
    assert report["reviewersRequired"] == 1
    assert report["status"] == "pending-user-review"
    assert report["decision"] == "pending"
    assert report["blocking"] is False
def test_g4_manual_review_report_blocked_when_auto_gate_fails() -> None:
    report = suite_cases_g4._g4_manual_review_report(
        {
            "acceptanceRequireHumanReview": True,
            "humanReviewMode": "single-reviewer",
            "humanReviewersRequired": 1,
        },
        {"passed": False},
    )

    assert report["required"] is True
    assert report["status"] == "blocked-by-auto-gate"
    assert report["decision"] == "rejected-by-auto-gate"
def test_g4_contract_verification_rejects_missing_thesis_rubric_artifacts() -> None:
    response_text = """
## 摘要
这是一个初步结果。

## 方法
我们尝试了一个基础方法。

## 结果
得到初步结论。
"""

    result = suite_cases_g4._g4_contract_verification_results(
        {
            "acceptanceRequiredDeliverables": ["论文", "文献综述", "外文翻译"],
            "acceptanceMinEvidenceLinks": 3,
            "acceptanceRequireInnovationStatement": True,
            "acceptanceRequireProblemSolutionTrace": True,
            "acceptanceRequireLimitationsAndFutureWork": True,
            "acceptanceRequireTaskBookProgress": True,
            "acceptanceRequireForeignTranslation": True,
            "acceptanceRequireDefenseQAReady": True,
        },
        response_text,
        {
            "restartCount": 1,
            "windowIndex": 2,
            "cumulativeWindowSpanTokens": 120000,
        },
    )

    assert result["enabled"] is True
    assert result["passed"] is False
    assert any("缺少关键交付物" in issue for issue in result["issues"])
    assert any("证据链接数量不足" in issue for issue in result["issues"])
    assert any("缺少创新性或贡献说明" in issue for issue in result["issues"])
    assert any("缺少问题分析与解决路径闭环" in issue for issue in result["issues"])
    assert any("缺少局限性与未来工作说明" in issue for issue in result["issues"])
    assert any("缺少任务书与进度执行说明" in issue for issue in result["issues"])
    assert any("缺少外文翻译任务与结果说明" in issue for issue in result["issues"])
    assert any("缺少答辩问答准备说明" in issue for issue in result["issues"])
def test_g4_contract_verification_accepts_thesis_rubric_artifacts() -> None:
    response_text = """
## 摘要
本文围绕机器学习训练稳定性给出创新点与贡献。

## 相关工作
文献综述：系统比较主流路线并给出差异。

## 方法
问题：泛化不稳定与训练震荡。
解决：提出分阶段优化与正则化组合，并给出改进路径。

## 实验
任务书与进度：里程碑 M1/M2/M3 全部完成。
外文翻译：完成英文论文原文-译文对照。

## 结论
局限：对小样本任务仍有波动。
未来工作：扩展到多模态任务与更大规模数据。

## 答辩准备
答辩问答 Q&A：覆盖方法选择、失败案例与有效性边界。

交付物：论文、文献综述、外文翻译。

证据链接：
https://arxiv.org/abs/2401.00001
https://arxiv.org/abs/2402.00002
https://api.semanticscholar.org/graph/v1/paper/search
"""

    result = suite_cases_g4._g4_contract_verification_results(
        {
            "acceptanceRequiredDeliverables": ["论文", "文献综述", "外文翻译"],
            "acceptanceMinEvidenceLinks": 3,
            "acceptanceRequireInnovationStatement": True,
            "acceptanceRequireProblemSolutionTrace": True,
            "acceptanceRequireLimitationsAndFutureWork": True,
            "acceptanceRequireTaskBookProgress": True,
            "acceptanceRequireForeignTranslation": True,
            "acceptanceRequireDefenseQAReady": True,
        },
        response_text,
        {
            "restartCount": 1,
            "windowIndex": 2,
            "cumulativeWindowSpanTokens": 120000,
        },
    )

    assert result["enabled"] is True
    assert result["passed"] is True
    assert result["issues"] == []