from __future__ import annotations

from types import SimpleNamespace

from yggdrasil_sdk import compile_runtime_prompt


def _task(**overrides):
    payload = {
        "title": "接手现有仓库并修复运行时问题",
        "goal": "在既有架构下完成安全迭代。",
        "current_focus": "runtime-prompting",
        "current_objective": "把提示词编译器接入正式执行链。",
        "resume_message": "继续完成 PromptCompiler 接线。",
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def _root_mount(**overrides):
    payload = {
        "systemIntro": "Project Yggdrasil mounts identity, context, and execution roots before each run.",
        "rootSummary": "Identity, context, and execution roots are mounted.",
        "taskObjective": "完成正式 prompt 编译链",
        "resumeMessage": "继续编译 runtime prompt。",
        "activeCapabilities": ["text-memory", "context-pruning", "subagent-pr"],
        "mountedNodeRefs": [{"kind": "node", "id": "node_1"}],
    }
    payload.update(overrides)
    return payload


def test_compile_runtime_prompt_for_main_coding_uses_existing_project_seed() -> None:
    compiled = compile_runtime_prompt(
        task=_task(),
        run_type="main",
        task_type="coding",
        root_mount=_root_mount(),
        current_context=[
            {
                "id": "ctx_1",
                "title": "已有仓库结构",
                "content": "当前仓库已经有 runtime、worker 和 subagent PR 闭环。",
                "rootBranch": "context",
            }
        ],
        request={"appId": "yggdrasil.app.software-factory", "codingMode": "existing-project"},
        resume_path=None,
    )

    assert compiled.app_id == "yggdrasil.app.software-factory"
    assert compiled.prompt_profile_id == "yggdrasil.software-factory.main-agent"
    assert compiled.seed_template_id == "yggdrasil.seed.coding.inherit-project"
    assert compiled.scenario == "coding.inherit-project"
    assert set(compiled.boot_sections.keys()) == {
        "physical_interface",
        "world_roots",
        "behavior_constitution",
        "scene_recovery",
    }
    assert "深潜研究员与继承开发者" in compiled.messages[0]["content"]
    assert "subagent_pr.create" in compiled.messages[0]["content"]
    assert "当前可见模块能力" in compiled.messages[0]["content"]


def test_compile_runtime_prompt_for_subagent_includes_scope_constraints() -> None:
    compiled = compile_runtime_prompt(
        task=_task(title="子任务：审查 PR 结果"),
        run_type="subagent",
        task_type="research",
        root_mount=_root_mount(),
        current_context=[
            {
                "id": "ctx_readonly",
                "title": "只读上下文",
                "content": "Sub-Agent 只能在当前切片里工作。",
                "rootBranch": "context",
            }
        ],
        request={"readonlyContextRef": {"type": "package-entry", "locator": "runtime/tasks/task_sub/readonly-context/current"}},
        resume_path="snapshot",
    )

    assert compiled.prompt_profile_id == "yggdrasil.subagent"
    assert compiled.messages[0]["content"]
    assert "通用 Sub-Agent" in compiled.messages[0]["content"]
    assert "只读上下文引用" in compiled.messages[1]["content"]
    assert "任务说明: 完成正式 prompt 编译链" in compiled.messages[1]["content"]
    assert "运行类型: subagent" in compiled.messages[1]["content"]


def test_compile_runtime_prompt_includes_takeover_protocol_when_present() -> None:
    compiled = compile_runtime_prompt(
        task=_task(),
        run_type="main",
        task_type="coding",
        root_mount=_root_mount(activeCapabilities=["text-memory", "task-takeover", "context-pruning"]),
        current_context=[],
        request={
            "takeoverProtocol": {
                "id": "takeover_test",
                "version": "0.1.0",
                "taskId": "task_takeover_prompt",
                "taskType": "coding",
                "runType": "main",
                "currentPhase": "plan",
                "status": "prepared",
                "objective": "把 Gate 2 接管协议注入 Prompt。",
                "objectiveSummary": "把 Gate 2 接管协议注入 Prompt。",
                "ambiguities": [],
                "constraints": [
                    {
                        "id": "constraint_delivery",
                        "category": "delivery",
                        "label": "交付结构",
                        "value": "结果 / 证据 / 待确认项 / 未完成项",
                        "required": True,
                        "source": "gate-2",
                    }
                ],
                "plan": [
                    {
                        "id": "step_plan",
                        "title": "形成计划",
                        "instructions": "生成可执行且可验证的步骤。",
                        "phase": "plan",
                        "status": "pending",
                        "expectedEvidence": ["plan steps"],
                        "dependsOn": [],
                    }
                ],
                "workTree": {
                    "version": "0.1.0",
                    "rootObjective": "把 Gate 2 接管协议注入 Prompt。",
                    "status": "planned",
                    "currentNodeId": "worktree-node-1",
                    "nodes": [
                        {
                            "id": "worktree-node-1",
                            "title": "形成计划",
                            "phase": "planning",
                            "status": "in-progress",
                            "planStepIds": ["step_plan"],
                            "constraintIds": ["constraint_delivery"],
                            "dependsOn": [],
                            "expectedEvidence": ["plan steps"],
                            "recoveryAnchor": None
                        }
                    ],
                    "recoveryAnchor": None,
                    "entropyBudgetRemaining": 9
                },
                "deliverySections": [],
                "verificationItems": [],
                "metrics": {
                    "planQualityScore0_100": 92.0,
                    "reworkCount": 0,
                    "reworkRate": 0.0,
                    "clarificationNeeded": False,
                    "deliveryCompletenessScore0_100": 0.0,
                    "verificationPassRate": 0.0,
                },
                "appliedModules": ["task-takeover"],
                "hookTrace": [],
            }
        },
        resume_path=None,
    )

    assert compiled.takeover_protocol is not None
    assert compiled.takeover_protocol.objective == "把 Gate 2 接管协议注入 Prompt。"
    assert "目标摘要: 把 Gate 2 接管协议注入 Prompt。" in compiled.messages[-1]["content"]
    assert "工作树:" in compiled.messages[-1]["content"]
    assert "计划步骤数: 1" in compiled.messages[-1]["content"]
    assert "1. [plan] 形成计划" not in compiled.messages[-1]["content"]
    assert "计划质量: 92.0" in compiled.messages[-1]["content"]


def test_compile_runtime_prompt_for_writing_selects_writing_seed() -> None:
    compiled = compile_runtime_prompt(
        task=_task(title="写作长篇章节", goal="推进剧情并维护角色一致性。", app_id="yggdrasil.app.knowledge-studio"),
        run_type="main",
        task_type="writing",
        root_mount=_root_mount(),
        current_context=[],
        request={"appId": "yggdrasil.app.knowledge-studio"},
        resume_path=None,
    )

    assert compiled.app_id == "yggdrasil.app.knowledge-studio"
    assert compiled.prompt_profile_id == "yggdrasil.knowledge-studio.main-agent"
    assert compiled.seed_template_id == "yggdrasil.seed.writing.epic"
    assert "史诗叙事架构师" in compiled.messages[0]["content"]
    assert "叙事化" in compiled.messages[-1]["content"]


def test_compile_runtime_prompt_for_dedicated_apps_selects_expected_scene() -> None:
    cases = [
        {
            "app_id": "yggdrasil.app.coding-greenfield",
            "task_type": "coding",
            "request": {"codingMode": "new-project"},
            "prompt_profile_id": "yggdrasil.coding-greenfield.main-agent",
            "seed_template_id": "yggdrasil.seed.coding.new-project",
            "content_marker": "全生命周期架构师",
        },
        {
            "app_id": "yggdrasil.app.coding-inherit",
            "task_type": "coding",
            "request": {},
            "prompt_profile_id": "yggdrasil.coding-inherit.main-agent",
            "seed_template_id": "yggdrasil.seed.coding.inherit-project",
            "content_marker": "深潜研究员与继承开发者",
        },
        {
            "app_id": "yggdrasil.app.deep-research",
            "task_type": "research",
            "request": {},
            "prompt_profile_id": "yggdrasil.deep-research.main-agent",
            "seed_template_id": "yggdrasil.seed.research.deep",
            "content_marker": "研究方向",
        },
        {
            "app_id": "yggdrasil.app.epic-writing",
            "task_type": "writing",
            "request": {},
            "prompt_profile_id": "yggdrasil.epic-writing.main-agent",
            "seed_template_id": "yggdrasil.seed.writing.epic",
            "content_marker": "叙事连续性",
        },
        {
            "app_id": "yggdrasil.app.maintenance-ops",
            "task_type": "maintenance",
            "request": {},
            "prompt_profile_id": "yggdrasil.maintenance-ops.main-agent",
            "seed_template_id": "yggdrasil.seed.maintenance.default",
            "content_marker": "最小修复范围",
        },
        {
            "app_id": "yggdrasil.app.learning-coach",
            "task_type": "learning",
            "request": {},
            "prompt_profile_id": "yggdrasil.learning-coach.main-agent",
            "seed_template_id": "yggdrasil.seed.learning.coach",
            "content_marker": "学习目标",
        },
        {
            "app_id": "yggdrasil.app.scenic-guide",
            "task_type": "service",
            "request": {},
            "prompt_profile_id": "yggdrasil.scenic-guide.main-agent",
            "seed_template_id": "yggdrasil.seed.scenic.guide",
            "content_marker": "景区导览",
        },
    ]

    for case in cases:
        compiled = compile_runtime_prompt(
            task=_task(title=f"{case['app_id']} 场景验证", goal="验证独立应用的 prompt 装配结果。", app_id=case["app_id"]),
            run_type="main",
            task_type=case["task_type"],
            root_mount=_root_mount(),
            current_context=[],
            request={"appId": case["app_id"], **case["request"]},
            resume_path=None,
        )

        assert compiled.app_id == case["app_id"]
        assert compiled.prompt_profile_id == case["prompt_profile_id"]
        assert compiled.seed_template_id == case["seed_template_id"]
        assert case["content_marker"] in compiled.messages[0]["content"]


def test_compile_runtime_prompt_injects_declared_few_shots_into_messages() -> None:
    cases = [
        {
            "app_id": "yggdrasil.app.coding-greenfield",
            "task_type": "coding",
            "request": {"codingMode": "new-project"},
            "expected_refs": [
                "yggdrasil.fewshot.coding-greenfield.spec-to-module-plan.v1",
                "yggdrasil.fewshot.coding-greenfield.incremental-delivery.v1",
                "yggdrasil.fewshot.scene-coding-new-project.scope-first-architecture.v1",
                "yggdrasil.fewshot.scene-coding-new-project.contract-driven-bootstrap.v1",
            ],
            "expected_markers": ["模块化实施计划", "先骨架、后能力、再扩展", "范围、模块边界和主链路", "同一套 contract"],
        },
        {
            "app_id": "yggdrasil.app.deep-research",
            "task_type": "research",
            "request": {},
            "expected_refs": [
                "yggdrasil.fewshot.deep-research.claim-evidence-matrix.v1",
                "yggdrasil.fewshot.deep-research.hypothesis-pivot.v1",
                "yggdrasil.fewshot.scene-research-deep.source-triangulation.v1",
                "yggdrasil.fewshot.scene-research-deep.direction-recalibration.v1",
            ],
            "expected_markers": ["结论 / 证据 / 冲突 / 待验证空白", "新的研究方向", "多源交叉验证", "重新给出可执行的校准路径"],
        },
        {
            "app_id": "yggdrasil.app.epic-writing",
            "task_type": "writing",
            "request": {},
            "expected_refs": [
                "yggdrasil.fewshot.epic-writing.chapter-outline-to-draft.v1",
                "yggdrasil.fewshot.epic-writing.continuity-conflict-resolution.v1",
                "yggdrasil.fewshot.scene-writing-epic.canon-before-draft.v1",
                "yggdrasil.fewshot.scene-writing-epic.chapter-continuity-audit.v1",
            ],
            "expected_markers": ["章节目标、角色状态和时间线锚点", "最小破坏方案", "回收 canon", "章节连续性审查风险"],
        },
    ]

    for case in cases:
        compiled = compile_runtime_prompt(
            task=_task(title=f"{case['app_id']} few-shot", goal="验证 few-shot 已进入运行时消息。", app_id=case["app_id"]),
            run_type="main",
            task_type=case["task_type"],
            root_mount=_root_mount(),
            current_context=[],
            request={"appId": case["app_id"], **case["request"]},
            resume_path=None,
        )

        assert compiled.few_shot_refs == case["expected_refs"]
        assert [message["role"] for message in compiled.messages] == ["system", "user"]
        assert "以下示例仅用于对齐执行风格，不代表当前用户真实发言：" in compiled.system_sections["few_shot_examples"]
        few_shot_payload = compiled.system_sections["few_shot_examples"]
        for marker in case["expected_markers"]:
            assert marker in few_shot_payload


def test_compile_runtime_prompt_resume_path_omits_few_shot_examples() -> None:
    compiled = compile_runtime_prompt(
        task=_task(title="恢复态 prompt 编译", goal="确认恢复态不会重复注入 few-shot。", app_id="yggdrasil.app.coding-greenfield"),
        run_type="main",
        task_type="coding",
        root_mount=_root_mount(resumeMessage="继续执行同一任务。"),
        current_context=[],
        request={"appId": "yggdrasil.app.coding-greenfield", "codingMode": "new-project", "resumeMessage": "继续执行同一任务。"},
        resume_path="restart-snapshot",
    )

    assert compiled.few_shot_refs == [
        "yggdrasil.fewshot.coding-greenfield.spec-to-module-plan.v1",
        "yggdrasil.fewshot.coding-greenfield.incremental-delivery.v1",
        "yggdrasil.fewshot.scene-coding-new-project.scope-first-architecture.v1",
        "yggdrasil.fewshot.scene-coding-new-project.contract-driven-bootstrap.v1",
    ]
    assert "few_shot_examples" not in compiled.system_sections
    assert "范围、模块边界和主链路" not in compiled.messages[0]["content"]
    assert "resume_message" not in compiled.user_sections
    assert "<Working_Node: " in compiled.user_sections["scene_recovery"]
    assert "恢复路径: restart-snapshot" in compiled.user_sections["scene_recovery"]
    assert compiled.messages[1]["content"].count("继续执行同一任务。") == 1


def test_boot_behavior_constitution_is_stable_and_scene_specific_text_stays_outside_boot() -> None:
    compiled = compile_runtime_prompt(
        task=_task(),
        run_type="main",
        task_type="coding",
        root_mount=_root_mount(),
        current_context=[],
        request={"appId": "yggdrasil.app.software-factory", "codingMode": "existing-project"},
        resume_path=None,
    )

    assert "场景偏好与执行倾向" not in compiled.boot_sections["behavior_constitution"]
    assert "行为宪法" in compiled.boot_sections["behavior_constitution"]
    assert "场景偏好与执行倾向" in compiled.system_sections["scene_preferences"]
    assert "高风险或不可逆操作必须显式请求确认。" not in compiled.boot_sections["physical_interface"]
    assert "工具使用偏好:" in compiled.system_sections["tool_usage_preferences"]
    assert "高风险或不可逆操作必须显式请求确认。" in compiled.system_sections["tool_usage_preferences"]


def test_compile_runtime_prompt_prefers_formal_memory_tools_over_memory_write_tags() -> None:
    compiled = compile_runtime_prompt(
        task=_task(),
        run_type="main",
        task_type="coding",
        root_mount=_root_mount(activeCapabilities=["text-memory", "shared-memory", "task-takeover"]),
        current_context=[],
        request={"appId": "yggdrasil.app.software-factory", "codingMode": "existing-project"},
        resume_path=None,
    )

    tool_policy = compiled.system_sections["tool_usage_preferences"]
    response_requirements = compiled.user_sections["response_requirements"]

    assert "记忆修改优先级:" in tool_policy
    assert "默认优先使用正式记忆工具" in tool_policy
    assert "只有在需要不中断当前回答、且修改足够轻量时，才使用 <memory-write>" in tool_policy
    assert "节点过宽、存在多个独立主题或冲突风险高时，优先创建细分子节点做空间隔离" in tool_policy
    assert "latestVersionId 冲突时，不要静默覆盖" in tool_policy
    assert "记忆修改默认优先使用正式记忆工具" in response_requirements
    assert "<memory-write title=\"...\" rootBranch=\"context\">" in response_requirements
    assert "<work-node-create ...></work-node-create>" in response_requirements
    assert "<work-node-enter nodeId=\"...\"></work-node-enter>" in response_requirements
    assert "child 完成或失败返回父节点后，由父节点决定下一步" in response_requirements
    assert "root 节点默认负责编排和最终汇总" in response_requirements
    assert "child 节点只处理单一局部目标" in response_requirements
    assert "已经在同一节点连续恢复/重启，优先把当前工作拆成更小的 child 或 leaf" in response_requirements
    assert "先判断是否已经完成必要的子工作并拿到对应摘要" in response_requirements


def test_resume_prompt_prefers_restart_message_and_keeps_single_recovery_memo() -> None:
    compiled = compile_runtime_prompt(
        task=_task(
            title="窗口重启恢复",
            goal="验证恢复态提示唯一性。",
            resume_message="来自任务的旧恢复提示。",
        ),
        run_type="main",
        task_type="coding",
        root_mount=_root_mount(resumeMessage="来自 root mount 的恢复提示。"),
        current_context=[],
        request={
            "appId": "yggdrasil.app.coding-greenfield",
            "codingMode": "new-project",
            "resumeMessage": "来自请求的恢复提示。",
            "restartMessage": "来自请求的重启提示。",
        },
        resume_path="restart-window-2",
    )

    assert "来自请求的重启提示。" in compiled.user_sections["scene_recovery"]
    assert "来自请求的恢复提示。" not in compiled.user_sections["scene_recovery"]
    assert "来自 root mount 的恢复提示。" not in compiled.user_sections["scene_recovery"]
    assert compiled.messages[1]["content"].count("来自请求的重启提示。") == 1


def test_resume_prompt_canonicalizes_working_node_and_memory_pointer() -> None:
    compiled = compile_runtime_prompt(
        task=_task(title="恢复态指针一致性", goal="验证恢复态 prompt 的节点指针一致。"),
        run_type="main",
        task_type="coding",
        root_mount=_root_mount(
            currentNodeId="node-root",
            workingNodeAnnotation="<Working_Node: node-root>",
            pcMemo="pc:node-root",
        ),
        current_context=[],
        request={
            "appId": "yggdrasil.app.software-factory",
            "workingNodeAnnotation": "<Working_Node: node-wrong>",
            "memoryRetrievalState": {
                "summary": "retrieval summary",
                "requestId": "retr-1",
                "workTreeNodeId": "node-memory",
                "matchedNodeRefs": [],
                "materializedNodeIds": [],
            },
            "takeoverProtocol": {
                "id": "takeover_pointer_test",
                "version": "0.1.0",
                "taskId": "task_takeover_pointer_test",
                "taskType": "coding",
                "runType": "main",
                "currentPhase": "execute",
                "status": "prepared",
                "objective": "继续执行当前节点。",
                "objectiveSummary": "继续执行当前节点。",
                "ambiguities": [],
                "constraints": [],
                "plan": [],
                "workTree": {
                    "version": "0.1.0",
                    "rootObjective": "继续执行当前节点。",
                    "status": "active",
                    "currentNodeId": "node-takeover",
                    "nodes": [
                        {
                            "id": "node-takeover",
                            "title": "执行当前节点",
                            "phase": "executing",
                            "status": "in-progress",
                            "planStepIds": [],
                            "constraintIds": [],
                            "dependsOn": [],
                            "expectedEvidence": [],
                            "recoveryAnchor": "resume:node-takeover",
                        }
                    ],
                    "recoveryAnchor": "resume:node-takeover",
                    "entropyBudgetRemaining": 8,
                    "pcMemo": "pc:node-takeover",
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
            },
        },
        resume_path="snapshot",
    )

    assert "工作节点标签: <Working_Node: node-root>" in compiled.user_sections["scene_recovery"]
    assert "currentNodeId: node-root" in compiled.user_sections["scene_recovery"]
    assert "pcMemo: pc:node-root" in compiled.user_sections["scene_recovery"]
    assert "工作树节点: node-root" in compiled.user_sections["memory_retrieval_state"]
    assert "当前节点=node-root" in compiled.user_sections["takeover_protocol"]
    assert compiled.takeover_protocol is not None
    assert compiled.takeover_protocol.work_tree is not None
    assert compiled.takeover_protocol.work_tree.current_node_id == "node-root"
    assert compiled.takeover_protocol.work_tree.pc_memo == "pc:node-root"