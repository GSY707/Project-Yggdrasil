from __future__ import annotations

from yggdrasil_task_takeover.plugin import TaskTakeoverModule


def test_task_takeover_module_builds_coding_protocol() -> None:
    plugin = TaskTakeoverModule()
    protocol = plugin.build_protocol(
        {
            "taskId": "task_coding_g2",
            "taskType": "coding",
            "runType": "main",
            "request": {
                "taskObjective": "把 Gate 2 接管协议正式接入运行时，并补回归测试。",
            },
            "rootMount": {
                "budgetState": {"tokenBudgetTotal": 4000, "tokenBudgetUsed": 0},
                "activeCapabilities": ["context-pruning", "task-takeover", "subagent-runtime"],
            },
        }
    )

    assert protocol["status"] == "needs-clarification"
    assert protocol["taskType"] == "coding"
    assert protocol["plan"]
    assert any(step["phase"] == "verify" for step in protocol["plan"])
    assert any(constraint["category"] == "delivery" for constraint in protocol["constraints"])
    assert protocol["metrics"]["planConfirmationNeeded"] is True
    assert protocol["metrics"]["planConfirmed"] is False
    assert protocol["metrics"]["planQualityScore0_100"] > 0


def test_task_takeover_module_switches_to_prepared_after_plan_confirmation() -> None:
    plugin = TaskTakeoverModule()
    protocol = plugin.build_protocol(
        {
            "taskId": "task_coding_confirmed",
            "taskType": "coding",
            "runType": "main",
            "request": {
                "taskObjective": "先核对后执行。",
                "takeoverPlanConfirmed": True,
            },
            "rootMount": {
                "activeCapabilities": ["task-takeover"],
            },
        }
    )

    assert protocol["status"] == "prepared"
    assert protocol["metrics"]["planConfirmationNeeded"] is False
    assert protocol["metrics"]["planConfirmed"] is True


def test_task_takeover_module_formats_and_verifies_structured_delivery() -> None:
    plugin = TaskTakeoverModule()
    protocol = plugin.build_protocol(
        {
            "taskId": "task_delivery_g2",
            "taskType": "coding",
            "runType": "main",
            "request": {"taskObjective": "完成 Gate 2 交付结构化验证。"},
            "rootMount": {"activeCapabilities": ["task-takeover"]},
        }
    )

    verification = plugin.verify_delivery(
        {
            "modelOutput": "# 结果\n已完成任务接管协议接线。\n\n# 证据\n- 补了运行时测试\n\n# 待确认\n- 需要扩展到更多场景\n\n# 未完成\n- 首 token 指标还未接入 scorecard",
            "plan": protocol["plan"],
            "planQualityScore0_100": protocol["metrics"]["planQualityScore0_100"],
        }
    )

    assert all(section["status"] == "present" for section in verification["deliverySections"])
    assert all(item["status"] == "passed" for item in verification["verificationItems"])
    assert verification["metrics"]["deliveryCompletenessScore0_100"] == 100.0
    assert verification["metrics"]["verificationPassRate"] == 1.0


def test_task_takeover_module_hard_fails_when_required_delivery_section_missing() -> None:
    plugin = TaskTakeoverModule()

    verification = plugin.verify_delivery(
        {
            "modelOutput": "# 结果\n已完成核心改动。\n\n# 证据\n- 补了测试\n\n# 待确认\n- 需要 live 复跑",
            "plan": [],
            "planQualityScore0_100": 80.0,
        }
    )

    incomplete_item = next(item for item in verification["verificationItems"] if item["label"] == "delivery.incomplete")
    pending_item = next(item for item in verification["verificationItems"] if item["label"] == "delivery.pending")
    assert pending_item["gateMode"] == "hard"
    assert incomplete_item["gateMode"] == "hard"
    assert incomplete_item["status"] == "failed"
    assert verification["metrics"]["deliveryCompletenessScore0_100"] == 85.0
    assert verification["metrics"]["verificationPassRate"] == 0.75


def test_parse_delivery_sections_handles_english_headers() -> None:
    plugin = TaskTakeoverModule()
    verification = plugin.verify_delivery(
        {
            "modelOutput": "# Results\nTask completed.\n\n# Evidence\n- All tests pass.\n\n# Pending\n- Needs review.\n\n# Incomplete\n- None.",
            "plan": [],
            "planQualityScore0_100": 80.0,
        }
    )
    assert all(section["status"] == "present" for section in verification["deliverySections"])
    assert verification["metrics"]["deliveryCompletenessScore0_100"] == 100.0


def test_parse_delivery_sections_handles_mixed_language() -> None:
    plugin = TaskTakeoverModule()
    verification = plugin.verify_delivery(
        {
            "modelOutput": "# 结果 Summary\n完成了核心改动。\n\n# Evidence 验证\n- 补了测试\n\n# 待确认\n- 需要 live 复跑\n\n# Incomplete\n- 无",
            "plan": [],
            "planQualityScore0_100": 80.0,
        }
    )
    assert all(section["status"] == "present" for section in verification["deliverySections"])


def test_parse_delivery_sections_infers_evidence_from_result() -> None:
    plugin = TaskTakeoverModule()
    verification = plugin.verify_delivery(
        {
            "modelOutput": "# 结果\n已完成核心改动。\n通过了所有 test 验证。\n\n# 待确认\n- 需要 live 复跑\n\n# 未完成\n- 无",
            "plan": [],
            "planQualityScore0_100": 80.0,
        }
    )
    evidence_section = next(s for s in verification["deliverySections"] if s["section"] == "evidence")
    assert evidence_section["status"] == "present"