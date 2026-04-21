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
    assert "Readonly context ref" in compiled.messages[1]["content"]
    assert "Run type: subagent" in compiled.messages[1]["content"]


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
    assert "narrative" in compiled.messages[1]["content"]


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