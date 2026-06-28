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


def test_task_takeover_research_plan_starts_with_explore_phase() -> None:
    plugin = TaskTakeoverModule()
    protocol = plugin.build_protocol(
        {
            "taskId": "task_research_explore_01",
            "taskType": "research",
            "runType": "main",
            "request": {
                "taskObjective": "研究表示学习中的泛化边界，并形成可复验结论。",
                "currentFocus": "g4-graduate-ml-deepseek-v4",
            },
            "rootMount": {
                "budgetState": {"tokenBudgetTotal": 4000, "tokenBudgetUsed": 0},
                "activeCapabilities": ["task-takeover", "mcp-bridge", "text-memory"],
            },
        }
    )

    assert protocol["taskType"] == "research"
    assert protocol["plan"]
    assert protocol["plan"][0]["phase"] == "objective"
    assert "探索" in str(protocol["plan"][0]["title"])


def test_task_takeover_research_exploration_variant_is_stable_for_same_task() -> None:
    plugin = TaskTakeoverModule()
    payload = {
        "taskId": "task_research_explore_stable",
        "taskType": "research",
        "runType": "main",
        "request": {
            "taskObjective": "研究优化方法在小样本学习中的鲁棒性。",
            "currentFocus": "g4-graduate-ml-longcat2",
        },
        "rootMount": {"activeCapabilities": ["task-takeover"]},
    }
    protocol_a = plugin.build_protocol(payload)
    protocol_b = plugin.build_protocol(payload)

    assert protocol_a["plan"][0]["title"] == protocol_b["plan"][0]["title"]
    assert protocol_a["plan"][0]["instructions"] == protocol_b["plan"][0]["instructions"]


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


def test_task_takeover_module_ignores_optional_delivery_sections_when_missing() -> None:
    plugin = TaskTakeoverModule()

    verification = plugin.verify_delivery(
        {
            "modelOutput": "# 结果\n已完成核心改动。\n\n# 证据\n- 补了测试\n\n# 待确认\n- 需要 live 复跑",
            "plan": [],
            "planQualityScore0_100": 80.0,
        }
    )

    labels = {item["label"] for item in verification["verificationItems"]}
    assert labels == {"delivery.result", "delivery.evidence"}
    assert verification["metrics"]["deliveryCompletenessScore0_100"] == 100.0
    assert verification["metrics"]["verificationPassRate"] == 1.0


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


def test_verify_delivery_web_grounded_requires_successful_tool_execution() -> None:
    plugin = TaskTakeoverModule()
    verification = plugin.verify_delivery(
        {
            "modelOutput": "# result\n完成。\n\n# evidence\n基于已有知识给出结论。\n\n# pending\n无。\n\n# incomplete\n无。",
            "plan": [],
            "planQualityScore0_100": 80.0,
            "request": {"responseRequirements": "Use web search and provide source URLs."},
            "toolExecutions": [],
        }
    )

    web_item = next(item for item in verification["verificationItems"] if item["label"] == "delivery.web-grounded-evidence")
    assert web_item["gateMode"] == "hard"
    assert web_item["status"] == "failed"


def test_verify_delivery_web_grounded_passes_with_successful_tool_execution() -> None:
    plugin = TaskTakeoverModule()
    verification = plugin.verify_delivery(
        {
            "modelOutput": "# result\n完成。\n\n# evidence\n- 引用来源: https://example.com/source\n\n# pending\n无。\n\n# incomplete\n无。",
            "plan": [],
            "planQualityScore0_100": 80.0,
            "request": {"responseRequirements": "Need web-grounded answer with source URL citations."},
            "toolExecutions": [
                {"name": "fetch_webpage", "status": "completed", "result": {"isError": False}}
            ],
        }
    )

    web_item = next(item for item in verification["verificationItems"] if item["label"] == "delivery.web-grounded-evidence")
    assert web_item["status"] == "passed"


def test_verify_delivery_web_grounded_passes_with_url_citations_without_tool_execution() -> None:
    plugin = TaskTakeoverModule()
    verification = plugin.verify_delivery(
        {
            "modelOutput": "# result\n完成。\n\n# evidence\n- 来源 A: https://example.com/a\n- 来源 B: https://example.com/b\n\n# pending\n无。\n\n# incomplete\n无。",
            "plan": [],
            "planQualityScore0_100": 80.0,
            "request": {"responseRequirements": "Need web-grounded answer with source URL citations."},
            "toolExecutions": [],
        }
    )

    web_item = next(item for item in verification["verificationItems"] if item["label"] == "delivery.web-grounded-evidence")
    assert web_item["status"] == "passed"


def test_verify_delivery_web_grounded_passes_on_continuation_without_new_tool_execution() -> None:
    plugin = TaskTakeoverModule()
    verification = plugin.verify_delivery(
        {
            "modelOutput": "# result\n完成。\n\n# evidence\n已沿用上一窗口检索证据完成综合。\n\n# pending\n无。\n\n# incomplete\n无。",
            "plan": [],
            "planQualityScore0_100": 80.0,
            "request": {
                "responseRequirements": "Need web-grounded answer with source URL citations.",
                "currentNodeId": "work-tree-node_xxx",
                "windowIndex": 3,
            },
            "toolExecutions": [],
        }
    )

    web_item = next(item for item in verification["verificationItems"] if item["label"] == "delivery.web-grounded-evidence")
    assert web_item["status"] == "passed"


def test_verify_delivery_web_grounded_passes_when_continuation_fields_are_top_level() -> None:
    plugin = TaskTakeoverModule()
    verification = plugin.verify_delivery(
        {
            "modelOutput": "# result\n完成。\n\n# evidence\n已沿用上一窗口检索证据完成综合。\n\n# pending\n无。\n\n# incomplete\n无。",
            "plan": [],
            "planQualityScore0_100": 80.0,
            "request": {
                "responseRequirements": "Need web-grounded answer with source URL citations.",
            },
            "parentRunId": "run_parent_001",
            "windowIndex": 4,
            "toolExecutions": [],
        }
    )

    web_item = next(item for item in verification["verificationItems"] if item["label"] == "delivery.web-grounded-evidence")
    assert web_item["status"] == "passed"


def test_verify_delivery_web_grounded_passes_when_work_context_stack_is_top_level() -> None:
    plugin = TaskTakeoverModule()
    verification = plugin.verify_delivery(
        {
            "modelOutput": "# result\n完成。\n\n# evidence\n已沿用上一窗口检索证据完成综合。\n\n# pending\n无。\n\n# incomplete\n无。",
            "plan": [],
            "planQualityScore0_100": 80.0,
            "request": {
                "responseRequirements": "Need web-grounded answer with source URL citations.",
            },
            "workContextStack": {"currentNodeId": "work-tree-node_xxx", "frames": [{"nodeId": "root"}]},
            "toolExecutions": [],
        }
    )

    web_item = next(item for item in verification["verificationItems"] if item["label"] == "delivery.web-grounded-evidence")
    assert web_item["status"] == "passed"
