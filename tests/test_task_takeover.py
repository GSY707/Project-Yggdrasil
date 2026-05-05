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

    assert protocol["status"] == "prepared"
    assert protocol["taskType"] == "coding"
    assert protocol["plan"]
    assert any(step["phase"] == "verify" for step in protocol["plan"])
    assert any(constraint["category"] == "delivery" for constraint in protocol["constraints"])
    assert protocol["metrics"]["planQualityScore0_100"] > 0


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