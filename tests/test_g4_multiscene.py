from __future__ import annotations
import os
from pathlib import Path
from types import SimpleNamespace
import pytest
from yggdrasil_sdk.evaluation_runtime.bootstrap import _seed_runtime_task, isolated_runtime_environment, local_evaluation_runtime_environment
import yggdrasil_sdk.evaluation_runtime.scorer as evaluation_scorer
import yggdrasil_sdk.evaluation_runtime.suite_cases_g4 as suite_cases_g4
from yggdrasil_sdk import list_evaluation_suite_definitions, run_evaluation_suite
from yggdrasil_sdk.contracts import BudgetState
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
def test_g4_real_task_web_research_default_suite_enforces_live_web_contract() -> None:
    suites = {definition["id"]: definition for definition in list_evaluation_suite_definitions()}

    suite = suites["evalsuite_g4_real_task_web_research_default"]
    cases = suite["cases"]

    assert len(cases) == 1
    assert {case["requestedProvider"] for case in cases} == {"longcat"}
    assert all(case.get("allowToolExecution") is True for case in cases)
    assert {case["parityPairKey"] for case in cases} == {"g4-web-research-default-grid-storage"}
    assert {case.get("auditLevel") for case in cases} == {"strict"}
def test_g4_real_task_web_research_default_suite_does_not_seed_takeover_path() -> None:
    suites = {definition["id"]: definition for definition in list_evaluation_suite_definitions()}

    suite = suites["evalsuite_g4_real_task_web_research_default"]
    cases = suite["cases"]

    assert len(cases) == 1
    case = cases[0]
    assert "takeoverProtocol" not in case
def test_g4_live_provider_matrix_start_payload_keeps_web_research_unorchestrated() -> None:
    start_payload = suite_cases_g4._g4_live_provider_matrix_start_payload(
        {
            "currentFocus": "g4-web-research-default-grid-storage",
            "currentObjective": "Deliver a web-grounded comparison report.",
            "currentContext": [
                {
                    "id": "ctx_contract",
                    "title": "contract",
                    "content": "Use web evidence and resolve contradictions.",
                    "importance": 1.0,
                }
            ],
            "allowToolExecution": True,
            "auditLevel": "strict",
            "responseRequirements": "Output Markdown only.",
        },
        {"id": "task_web_default", "currentFocus": "fallback-focus", "currentObjective": "fallback-objective"},
        app_id="yggdrasil.app.deep-research",
        task_type="research",
        candidate_models=[{"provider": "longcat", "model": "LongCat-2.0-Preview"}],
    )

    assert "takeoverProtocol" not in start_payload
    assert start_payload["allowToolExecution"] is True
    assert start_payload["takeoverPlanConfirmed"] is True
def test_g4_live_provider_matrix_start_payload_pins_expected_prompt_contract() -> None:
    start_payload = suite_cases_g4._g4_live_provider_matrix_start_payload(
        {
            "currentFocus": "g4-graduate-ml-longcat2",
            "currentObjective": "Keep the graduate researcher prompt contract pinned.",
            "currentContext": [
                {
                    "id": "ctx_grad_contract",
                    "title": "graduate contract",
                    "content": "Use the graduate researcher prompt profile and seed template.",
                    "importance": 1.0,
                }
            ],
            "expectedPromptProfileId": "yggdrasil.graduate-researcher.main-agent",
            "expectedSeedTemplateId": "yggdrasil.seed.graduate-researcher.default",
        },
        {"id": "task_grad_contract", "currentFocus": "fallback-focus", "currentObjective": "fallback-objective"},
        app_id="yggdrasil.app.graduate-researcher",
        task_type="research",
        candidate_models=[{"provider": "longcat", "model": "LongCat-2.0-Preview"}],
    )

    assert start_payload["promptProfileId"] == "yggdrasil.graduate-researcher.main-agent"
    assert start_payload["seedTemplateId"] == "yggdrasil.seed.graduate-researcher.default"
def test_g4_live_provider_matrix_start_payload_passes_tool_name_policy() -> None:
    start_payload = suite_cases_g4._g4_live_provider_matrix_start_payload(
        {
            "currentFocus": "g4-graduate-ml-longcat2",
            "currentObjective": "Keep tool visibility constrained.",
            "toolNameDenylist": ["mcp.read.*", "mcp.search.*"],
        },
        {"id": "task_grad_policy", "currentFocus": "fallback-focus", "currentObjective": "fallback-objective"},
        app_id="yggdrasil.app.graduate-researcher",
        task_type="research",
        candidate_models=[{"provider": "longcat", "model": "LongCat-2.0-Preview"}],
    )

    assert start_payload["toolNameDenylist"] == ["mcp.read.*", "mcp.search.*"]
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
def test_g4_preview_request_pins_expected_prompt_contract() -> None:
    preview_request = suite_cases_g4._g4_preview_request(
        {
            "appId": "yggdrasil.app.graduate-researcher",
            "taskType": "research",
            "currentFocus": "g4-graduate-ml-longcat2",
            "currentObjective": "Keep the graduate researcher preview contract pinned.",
            "expectedPromptProfileId": "yggdrasil.graduate-researcher.main-agent",
            "expectedSeedTemplateId": "yggdrasil.seed.graduate-researcher.default",
        }
    )

    assert preview_request["request"]["promptProfileId"] == "yggdrasil.graduate-researcher.main-agent"
    assert preview_request["request"]["seedTemplateId"] == "yggdrasil.seed.graduate-researcher.default"
def test_g4_wait_for_target_worker_result_ignores_foreign_payloads() -> None:
    events = iter(
        [
            {
                "status": "processed",
                "payload": {"taskId": "task_foreign", "payload": {}},
                "result": {"status": "continuing"},
            },
            {
                "status": "processed",
                "payload": {"taskId": "task_target", "payload": {}},
                "result": {"status": "continuing"},
            },
            {
                "status": "processed",
                "payload": {"taskId": "task_target", "payload": {}},
                "result": {"status": "awaiting-approval"},
            },
        ]
    )

    def _run_worker_once(_queue_name: str, timeout_seconds: int = 1) -> dict[str, object]:
        assert timeout_seconds == 1
        return next(events)

    processed_runs, processed, result_payload = suite_cases_g4._g4_wait_for_target_worker_result(
        task_id="task_target",
        expected_result_status="awaiting-approval",
        max_window_cycles=8,
        max_worker_wait_seconds=30,
        run_worker_once_fn=_run_worker_once,
    )

    assert len(processed_runs) == 2
    assert all(str((item.get("payload") or {}).get("taskId") or "") == "task_target" for item in processed_runs)
    assert str((processed.get("payload") or {}).get("taskId") or "") == "task_target"
    assert result_payload["status"] == "awaiting-approval"
def test_g4_wait_for_target_worker_result_fails_fast_on_worker_poll_timeout() -> None:
    def _run_worker_once(_queue_name: str, timeout_seconds: int = 1) -> dict[str, object]:
        del timeout_seconds
        import time

        time.sleep(0.2)
        return {"status": "empty"}

    with pytest.raises(RuntimeError, match="worker call timed out while polling queue"):
        suite_cases_g4._g4_wait_for_target_worker_result(
            task_id="task_target",
            expected_result_status="awaiting-approval",
            max_window_cycles=8,
            max_worker_wait_seconds=30,
            run_worker_once_fn=_run_worker_once,
            worker_poll_timeout_seconds=0.05,
        )
def test_g4_budget_state_with_top_up_preserves_used_budget_fields() -> None:
    updated = suite_cases_g4._g4_budget_state_with_top_up(
        BudgetState.model_validate(
            {
                "tokenBudgetTotal": 1000,
                "tokenBudgetUsed": 900,
                "costBudgetTotal": 5.0,
                "costBudgetUsed": 5.4,
                "childBudgetMode": "inherit",
            }
        ),
        {},
    )

    assert updated["tokenBudgetUsed"] == 900
    assert updated["costBudgetUsed"] == 5.4
    assert updated["tokenBudgetTotal"] > 1000
    assert updated["costBudgetTotal"] > 5.4
    assert updated["childBudgetMode"] == "inherit"
def test_g4_wait_for_target_worker_result_allows_budget_recovery_callback() -> None:
    events = iter(
        [
            {
                "status": "processed",
                "payload": {"taskId": "task_target", "payload": {}},
                "result": {"status": "paused", "snapshot": {"retentionClass": "active-paused"}},
            },
            {
                "status": "processed",
                "payload": {"taskId": "task_target", "payload": {}},
                "result": {"status": "awaiting-approval"},
            },
        ]
    )
    recovery_calls: list[str] = []

    def _run_worker_once(_queue_name: str, timeout_seconds: int = 1) -> dict[str, object]:
        assert timeout_seconds == 1
        return next(events)

    def _recover(**kwargs) -> bool:
        result_payload = dict(kwargs.get("result_payload") or {})
        recovery_calls.append(str(result_payload.get("status") or ""))
        return str(result_payload.get("status") or "") == "paused"

    processed_runs, processed, result_payload = suite_cases_g4._g4_wait_for_target_worker_result(
        task_id="task_target",
        expected_result_status="awaiting-approval",
        max_window_cycles=8,
        max_worker_wait_seconds=30,
        run_worker_once_fn=_run_worker_once,
        recovery_handler_fn=_recover,
    )

    assert recovery_calls == ["paused", "awaiting-approval"]
    assert len(processed_runs) == 2
    assert str((processed.get("payload") or {}).get("taskId") or "") == "task_target"
    assert result_payload["status"] == "awaiting-approval"
def test_g4_recover_live_budget_pause_resumes_with_topped_up_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_task = SimpleNamespace(
        status="paused",
        current_focus="budget-exhausted: Cost budget exceeded after model invocation.",
        active_snapshot_id="snap_1",
        budget=BudgetState.model_validate(
            {
                "tokenBudgetTotal": 1000,
                "tokenBudgetUsed": 950,
                "costBudgetTotal": 5.0,
                "costBudgetUsed": 5.4,
                "childBudgetMode": "inherit",
            }
        ),
        resume_message="continue evaluation",
        current_objective="finish the live evaluation",
        goal="finish the live evaluation",
    )

    class _FakeTaskRepository:
        def __init__(self, _session: object) -> None:
            pass

        def get_task(self, task_id: str):
            assert task_id == "task_target"
            return fake_task

        def get_snapshot(self, snapshot_id: str):
            assert snapshot_id == "snap_1"
            return SimpleNamespace(status="restorable")

    class _FakeScope:
        def __enter__(self) -> object:
            return object()

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    class _FakeRuntime:
        def session_scope(self) -> _FakeScope:
            return _FakeScope()

    posted: list[tuple[str, dict[str, object]]] = []

    class _FakeClient:
        def post(self, path: str, json: dict[str, object]):
            posted.append((path, json))
            return SimpleNamespace(status_code=202, text="")

    monkeypatch.setattr(suite_cases_g4, "TaskRepository", _FakeTaskRepository)
    monkeypatch.setattr(suite_cases_g4, "get_persistence_runtime", lambda: _FakeRuntime())

    recovered = suite_cases_g4._g4_recover_live_budget_pause_or_failure(
        client=_FakeClient(),
        task_id="task_target",
        case_payload={},
        result_payload={"status": "paused"},
        recovery_state={},
    )

    assert recovered is True
    assert len(posted) == 1
    assert posted[0][0] == "/runtime/tasks/task_target/resume"
    payload = posted[0][1]
    assert "resumeToken" not in payload
    assert payload["budgetState"]["tokenBudgetUsed"] == 950
    assert payload["budgetState"]["costBudgetUsed"] == 5.4
    assert payload["budgetState"]["tokenBudgetTotal"] > 1000
    assert payload["budgetState"]["costBudgetTotal"] > 5.4
def test_g4_real_task_work_tree_debug_suite_uses_nested_work_tree_and_strict_audit() -> None:
    suites = {definition["id"]: definition for definition in list_evaluation_suite_definitions()}

    suite = suites["evalsuite_g4_real_task_work_tree_debug"]
    cases = suite["cases"]

    assert len(cases) == 2
    assert {case["requestedProvider"] for case in cases} == {"deepseek_direct"}
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
        assert "treat the seeded currentNodeId / Working_Node / WorkContextStack as authoritative" in case["responseRequirements"]
        assert "If the current node is child-1, first complete and bubble child-1 semantics" in case["responseRequirements"]
        assert "Tool execution is disabled for this case." in case["currentContext"][3]["content"]
        assert "## 1. 目标工作树模型" in case["currentContext"][3]["content"]
    for case in cases:
        paths = {item["path"] for item in case["currentContextFiles"]}
        assert "docs/specs/work-tree-protocol-v0.2.md" in paths
        assert "docs/specs/agent-runtime-protocol-v0.2.md" in paths
        assert "packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/takeover.py" in paths
        assert "packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop/worker.py" in paths
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
def test_g4_contract_verification_rejects_graduate_standard_without_tool_and_asset_evidence() -> None:
    response_text = """
## 摘要
这是一个快速总结。

## 结果
给出一个结论。

## 证据
仅基于已有上下文。
"""

    result = suite_cases_g4._g4_contract_verification_results(
        {
            "acceptanceMinIndependentSteps": 10,
            "acceptanceMinToolBackedStepRatio0_1": 0.6,
            "acceptanceMinMemoryNodeCount": 30,
            "acceptanceRequireExperimentRecord": True,
            "acceptanceRequireDisputeList": True,
            "acceptanceRequireToolCategories": ["web", "compute", "memory"],
            "acceptanceMinSuccessfulToolExecutions": 6,
            "acceptanceRequiredAcademicSections": ["摘要", "引言", "相关工作", "方法", "实验", "结论", "参考文献"],
            "acceptanceMinCitationMarkers": 8,
        },
        response_text,
        {
            "restartCount": 1,
            "windowIndex": 2,
            "cumulativeWindowSpanTokens": 120000,
        },
        {},
        [
            {
                "responsePayload": {
                    "toolExecutions": [
                        {
                            "tool": {"name": "text_memory.read_index"},
                            "success": True,
                            "result": {"result": {"count": 8}},
                        }
                    ]
                }
            }
        ],
    )

    assert result["enabled"] is True
    assert result["passed"] is False
    assert any("独立步骤数不足" in issue for issue in result["issues"])
    assert any("工具支撑步骤占比不足" in issue for issue in result["issues"])
    assert any("记忆节点数不足" in issue for issue in result["issues"])
    assert any("缺少实验记录集合" in issue for issue in result["issues"])
    assert any("缺少争议与未决问题清单" in issue for issue in result["issues"])
    assert any("工具类别覆盖不足" in issue for issue in result["issues"])
    assert any("成功工具动作不足" in issue for issue in result["issues"])
    assert any("缺少本科论文关键小节" in issue for issue in result["issues"])
    assert any("引用标记不足" in issue for issue in result["issues"])
def test_g4_contract_verification_accepts_graduate_standard_with_undergrad_thesis_evidence() -> None:
    response_text = """
## 摘要
研究目标与主要贡献概述。[1]

## 引言
问题背景与研究意义。[2]

## 相关工作
比较现有路线并说明差距。[3]

## 方法
给出流程与假设。[4]

## 实验
实验记录：A/B 对照、消融与复现实验。[5]

## 结论
总结发现与边界。[6]

## 参考文献
[1] ...
[2] ...
[3] ...
[4] ...
[5] ...
[6] ...
[7] ...
[8] ...

步骤 1：工具证据 mcp.search.search_text
步骤 2：工具证据 mcp.python.run_python
步骤 3：工具证据 text_memory.read_index
步骤 4：工具证据 mcp.search.fetch_webpage
步骤 5：工具证据 mcp.execute.run_command
步骤 6：工具证据 text_memory.update_memory_with_version
步骤 7：工具证据 mcp.search.search_text
步骤 8：工具证据 mcp.python.run_python
步骤 9：工具证据 text_memory.read_node
步骤 10：工具证据 mcp.search.fetch_webpage

争议与未决问题：记录了评估口径与外推风险。
"""

    result = suite_cases_g4._g4_contract_verification_results(
        {
            "acceptanceMinIndependentSteps": 10,
            "acceptanceMinToolBackedStepRatio0_1": 0.6,
            "acceptanceMinMemoryNodeCount": 30,
            "acceptanceRequireExperimentRecord": True,
            "acceptanceRequireDisputeList": True,
            "acceptanceRequireToolCategories": ["web", "compute", "memory"],
            "acceptanceMinSuccessfulToolExecutions": 6,
            "acceptanceRequiredAcademicSections": ["摘要", "引言", "相关工作", "方法", "实验", "结论", "参考文献"],
            "acceptanceMinCitationMarkers": 8,
        },
        response_text,
        {
            "restartCount": 2,
            "windowIndex": 3,
            "cumulativeWindowSpanTokens": 220000,
        },
        {},
        [
            {
                "responsePayload": {
                    "toolExecutions": [
                        {"tool": {"name": "mcp.search.search_text"}, "success": True},
                        {"tool": {"name": "mcp.python.run_python"}, "success": True},
                        {"tool": {"name": "text_memory.read_index"}, "success": True, "result": {"result": {"count": 36}}},
                        {"tool": {"name": "mcp.search.fetch_webpage"}, "success": True},
                        {"tool": {"name": "mcp.execute.run_command"}, "success": True},
                        {"tool": {"name": "text_memory.update_memory_with_version"}, "success": True},
                    ]
                }
            }
        ],
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
