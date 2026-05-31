from __future__ import annotations

from .prompting__part01 import *  # noqa: F403,F401

def _format_world_roots(root_mount: dict[str, Any]) -> str:
    semantic_roots = root_mount.get("semanticRoots") if isinstance(root_mount.get("semanticRoots"), dict) else {}
    system_root_protocol = (
        root_mount.get("systemRootProtocol") if isinstance(root_mount.get("systemRootProtocol"), dict) else {}
    )
    startup_load_order = [str(item) for item in root_mount.get("startupLoadOrder") or [] if str(item).strip()]
    if semantic_roots:
        lines = ["启动根指针:"]
        for key, fallback_count in (("identity", len(root_mount.get("identityRefs") or [])), ("context", len(root_mount.get("contextRefs") or [])), ("execution", len(root_mount.get("executionRefs") or []))):
            root_entry = semantic_roots.get(key) if isinstance(semantic_roots.get(key), dict) else {}
            label = str(root_entry.get("label") or "").strip() or key
            summary = str(root_entry.get("summary") or "").strip()
            primary_ref = str(root_entry.get("primaryRefId") or "").strip()
            line = f"- {label}"
            if summary:
                line += f" {summary}"
            if primary_ref:
                line += f" rootRef={primary_ref}"
            else:
                line += f" 引用数={fallback_count}"
            if key == "execution" and root_entry.get("currentNodeId") is not None:
                line += f" currentNode={root_entry['currentNodeId']}"
            lines.append(line)
        protocol_label = str(system_root_protocol.get("label") or "[NODE_ID: SYS_ROOT_PROTOCOL]").strip()
        protocol_summary = str(system_root_protocol.get("summary") or "系统宪法与能力索引入口").strip()
        lines.append(f"- {protocol_label} {protocol_summary}")
        if startup_load_order:
            lines.append("启动加载顺序: " + " -> ".join(startup_load_order))
        lines.extend(
            [
                f"系统导语: {root_mount.get('systemIntro') or ''}",
                f"根摘要: {root_mount.get('rootSummary') or ''}",
                f"任务说明: {root_mount.get('taskObjective') or ''}",
            ]
        )
        return "\n".join(lines)

    identity_refs = root_mount.get("identityRefs") or []
    context_refs = root_mount.get("contextRefs") or []
    execution_refs = root_mount.get("executionRefs") or []
    return "\n".join(
        [
            "启动根指针:",
            f"- [ID: 001 我是谁] 身份引用数={len(identity_refs)}",
            f"- [ID: 002 我在哪] 上下文引用数={len(context_refs)}",
            f"- [ID: 003 我要干什么] 执行引用数={len(execution_refs)}",
            "- [NODE_ID: SYS_ROOT_PROTOCOL] 系统宪法与能力索引入口",
            f"系统导语: {root_mount.get('systemIntro') or ''}",
            f"根摘要: {root_mount.get('rootSummary') or ''}",
            f"任务说明: {root_mount.get('taskObjective') or ''}",
        ]
    )
def _format_behavior_constitution(profile: PromptProfile) -> str:
    constitution_lines = [
        "行为宪法:",
        "1. 通过结构化工具和消息通道触达外界，不跨边界越权执行。",
        "2. 工作树节点命名优先体现 questions_it_answers，避免无语义标题。",
        "3. 关键新知、失败原因、约束与关联优先写入记忆，再推进下一步。",
        "4. 面对大量未知文件或长文本重活，优先委派 Sub-Agent 预读和摘要。",
    ]
    return "\n".join(constitution_lines)
def _format_scene_preferences(profile: PromptProfile) -> str:
    return "\n\n".join(
        section
        for section in [
            "场景偏好与执行倾向:",
            profile.kernel_truth,
            profile.behavior_guidelines,
            profile.memory_policy,
            profile.evidence_policy,
        ]
        if section
    )
def _format_capability_protocol_index(
    active_capabilities: list[str],
    registered_tools: list[dict[str, Any]],
) -> str:
    return "\n".join(
        [
            "能力与协议索引:",
            f"- 挂载能力数: {len(active_capabilities)}",
            f"- 可见工具数: {len(registered_tools)}",
            "- 协议入口: SYS_ROOT_PROTOCOL / WorkTreeProtocol v0.2 / Agent Runtime v0.2",
        ]
    )
def _format_scene_recovery(
    *,
    resume_path: str | None,
    resume_message: str,
    pointer_fields: dict[str, str],
    memory_retrieval_state: dict[str, Any] | None,
) -> str:
    lines = [
        f"运行模式: {'恢复态' if resume_path else '常态'}",
        f"工作节点标签: {pointer_fields['workingNodeAnnotation']}",
        f"currentNodeId: {pointer_fields['currentNodeId']}",
    ]
    if pointer_fields["pcMemo"]:
        lines.append(f"pcMemo: {pointer_fields['pcMemo']}")
    if pointer_fields["topFrameId"]:
        lines.append(f"topFrameId: {pointer_fields['topFrameId']}")
    if pointer_fields["stackDigest"]:
        lines.append(f"stackDigest: {pointer_fields['stackDigest']}")
    if resume_path:
        lines.append(f"恢复路径: {resume_path}")
    lines.append(f"恢复/重启提示: {resume_message or '未提供恢复提示。'}")
    if memory_retrieval_state is not None:
        lines.append("记忆检索状态:")
        lines.append(_format_memory_retrieval_state(memory_retrieval_state))
    return "\n".join(lines)
def _format_task_contract(
    task: Any,
    run_type: str,
    task_type: str,
    request: dict[str, Any],
    resume_path: str | None,
    *,
    objective_override: str | None = None,
    focus_override: str | None = None,
) -> str:
    objective = str(
        objective_override
        or request.get("taskObjective")
        or request.get("currentObjective")
        or task.current_objective
        or task.goal
    )
    focus = str(focus_override or request.get("currentFocus") or task.current_focus or "runtime execution")
    lines = [
        f"任务标题: {task.title}",
        f"任务目标: {task.goal}",
        f"当前目标: {objective}",
        f"当前焦点: {focus}",
        f"运行类型: {run_type}",
        f"任务类型: {task_type}",
    ]
    if resume_path:
        lines.append(f"恢复路径: {resume_path}")
    return "\n".join(lines)
def _format_response_requirements(
    request: dict[str, Any],
    seed_template: SeedTemplate | None,
    resume_path: str | None = None,
) -> str:
    style = seed_template.output_style if seed_template is not None else "concise"
    localized_style = _localized_output_style(style)
    additional = sanitize_prompt_contract_text(request.get("responseRequirements"))
    takeover_protocol = request.get("takeoverProtocol") if isinstance(request.get("takeoverProtocol"), dict) else {}
    takeover_status = str(takeover_protocol.get("status") or "").strip().lower()
    has_delivery_contract = isinstance(additional, str) and additional.strip()
    is_resume = bool(resume_path)
    lines = [
        "1. 先依据 currentNodeId、Working_Node 和 WorkContextStack 判断当前所在节点，再决定行动；默认沿当前节点推进，不要跳过节点语义直接改写成整任务交付。",
        '2. 若需要操作工作树，必须通过动作标签显式声明：创建新子节点使用 <work-node-create ...></work-node-create>，进入已有子节点使用 <work-node-enter nodeId="..."></work-node-enter>。',
        "3. 父节点强编排：child 完成或失败返回父节点后，由父节点决定下一步（进入已有 child、创建新 child、或直接汇总交付），不要默认自动跳 sibling。",
        "4. root 节点默认负责编排和最终汇总；当任务天然包含多个相对独立的子工作（例如证据检查、分析判断、正式交付起草、风险复核）时，不要在 root 一次性直接写完整最终答案，优先拆成 child 再汇总。",
        "5. child 节点只处理单一局部目标；child 完成时，把局部结论、证据、未决项压成摘要返回父节点，不要把 child 直接当成整任务最终交付。",
        "6. 若当前节点过宽、同时混有多种目标、需要多轮长篇续写，或已经在同一节点连续恢复/重启，优先把当前工作拆成更小的 child 或 leaf，再继续执行，不要反复在同一 root 节点硬写整份交付。",
        "7. 若当前节点已收敛为单一局部目标、证据边界清楚且可在一次有界执行内完成，则停止继续拆分，直接完成本节点并上浮父节点。",
        "8. 只有 root 节点，或被父节点明确授权负责最终汇总的节点，才能输出整任务最终交付；否则先完成局部摘要并回父节点。",
        "9. 外部 responseRequirements、restartMessage 和格式合同只能约束输出结构，不得覆盖工作树拓扑、当前节点语义和父节点编排权。",
        "10. 若证据不足，明确说明缺失信息，不要补空白。",
        "11. 保持输出 grounded 在当前挂载上下文、工具结果和正式状态上。",
        f"12. 默认采用 {localized_style} 风格，除非任务另有明确要求。",
    ]
    if is_resume:
        lines.append(f"{len(lines) + 1}. 恢复态下，把 resume_message 视为接续上下文的提示（context hint），结合记忆树继续执行，无需退回初始规划状态。")
        lines.append(f"{len(lines) + 1}. 恢复态下继续遵守当前节点语义：若当前是 child/leaf，先完成局部目标并回父节点；由父节点或 root 组织最终 结果/证据/待确认项/未完成项（result/evidence/pending/incomplete）交付。")
        lines.append(f"{len(lines) + 1}. 恢复态必须包含 judgment 字段并给出当前完成度判断。")
    if bool(request.get("memoryWriteTagsEnabled", True)):
        lines.append(
            f'{len(lines) + 1}. 记忆修改默认优先使用正式记忆工具；仅当需要不中断回答且改动足够轻量时，才插入 <memory-write title="..." rootBranch="context">记忆内容</memory-write>；更新已有节点时使用 nodeId="..." action="append|replace"。'
        )
    if takeover_status == "needs-clarification" and not bool(request.get("takeoverAutoConfirm")):
        lines.append(
            f"{len(lines) + 1}. 当前 takeover 状态是 needs-clarification：本轮以任务理解、执行计划与确认问题为主；可调用工具补充核对证据，但不得产出执行性最终结论。"
        )
    if has_delivery_contract:
        lines.append(f"{len(lines) + 1}. 附加要求: {additional.strip()}")
    return "\n".join(lines)
def _takeover_protocol_from_request(request: dict[str, Any]) -> TaskTakeoverProtocol | None:
    candidate = request.get("takeoverProtocol") if isinstance(request.get("takeoverProtocol"), dict) else None
    if candidate is None:
        return None
    if bool(request.get("takeoverAutoConfirm")) and str(candidate.get("status") or "").strip().lower() == "needs-clarification":
        metrics = dict(candidate.get("metrics") or {})
        metrics["clarificationNeeded"] = False
        metrics["planConfirmationNeeded"] = False
        metrics["planConfirmed"] = True
        candidate = {
            **candidate,
            "status": "prepared",
            "currentPhase": "execute",
            "metrics": metrics,
        }
    try:
        return TaskTakeoverProtocol.model_validate(candidate)
    except Exception:
        return None
def _format_takeover_protocol(protocol: TaskTakeoverProtocol) -> str:
    lines = [
        f"目标摘要: {protocol.objective_summary}",
        f"当前阶段: {protocol.current_phase}",
        f"状态: {protocol.status}",
        "约束:",
    ]
    if protocol.constraints:
        lines.extend(f"- [{item.category}] {item.label}: {item.value}" for item in protocol.constraints)
    else:
        lines.append("- 无")
    lines.append(f"计划步骤数: {len(protocol.plan)}")
    if protocol.work_tree is not None:
        lines.append("工作树:")
        lines.append(
            f"- 状态={protocol.work_tree.status}; 当前节点={protocol.work_tree.current_node_id or 'none'}; 剩余熵预算={protocol.work_tree.entropy_budget_remaining}"
        )
        if protocol.work_tree.nodes:
            lines.extend(
                f"- [{node.phase}/{node.status}] {node.title}"
                for node in protocol.work_tree.nodes[:6]
            )
    if protocol.delivery_sections:
        lines.append("交付检查点:")
        lines.extend(
            f"- {section.section}: {normalize_excerpt(section.content or section.status, 120)}"
            for section in protocol.delivery_sections
        )
    lines.extend(
        [
            f"计划质量: {protocol.metrics.plan_quality_score_0_100}",
            f"返工率: {protocol.metrics.rework_rate}",
            f"交付完整度: {protocol.metrics.delivery_completeness_score_0_100}",
        ]
    )
    return "\n".join(lines)
def _merged_few_shot_refs(profile: PromptProfile, seed_template: SeedTemplate) -> list[str]:
    refs: list[str] = []
    for candidate in [*profile.few_shot_refs, *seed_template.few_shot_refs]:
        normalized = str(candidate).strip()
        if normalized and normalized not in refs:
            refs.append(normalized)
    return refs
def _resolve_few_shot_assets(
    profile: PromptProfile,
    seed_template: SeedTemplate,
    registry: dict[str, Any],
) -> list[FewShotAsset]:
    refs = _merged_few_shot_refs(profile, seed_template)
    if not refs:
        return []
    assets_by_id = {
        asset.id: asset
        for asset in registry.get("fewShotAssets") or []
        if isinstance(asset, FewShotAsset)
    }
    missing_refs = [ref for ref in refs if ref not in assets_by_id]
    if missing_refs:
        raise KeyError(
            "Missing few-shot assets for refs: " + ", ".join(missing_refs)
        )
    return [assets_by_id[ref] for ref in refs]
def compile_runtime_prompt(
    *,
    task: Any,
    run_type: str,
    task_type: str,
    root_mount: dict[str, Any],
    current_context: list[dict[str, Any]],
    request: dict[str, Any],
    resume_path: str | None,
    registry: dict[str, Any] | None = None,
    registered_tools: list[dict[str, Any]] | None = None,
) -> CompiledPrompt:
    app_id = str(request.get("appId") or getattr(task, "app_id", None) or DEFAULT_APP_ID)
    active_capabilities = [str(item) for item in root_mount.get("activeCapabilities") or []]
    resolved_registry = registry or assemble_prompt_registry(app_id=app_id, active_capabilities=active_capabilities)
    app_manifest = resolved_registry["application"]
    profile = _select_prompt_profile(run_type, request, app_manifest, resolved_registry["promptProfiles"])
    seed_template = _select_seed_template(task_type, run_type, request, app_manifest, resolved_registry["seedTemplates"])
    resolved_registered_tools = registered_tools if registered_tools is not None else list_registered_agent_tools(active_capabilities)

    task_runtime_state = request.get("taskRuntimeState")
    if isinstance(task_runtime_state, dict):
        from .contracts import TaskRuntimeState
        try:
            task_runtime_state = TaskRuntimeState.model_validate(task_runtime_state)
        except Exception:
            task_runtime_state = None

    is_initial_awakening = (task_runtime_state is None or task_runtime_state.phase == "start-state")

    if is_initial_awakening:
        task_objective = None
        current_focus = None
        current_node_id = None
        working_node_annotation = None
        pc_memo = None
        top_frame_id = None
        stack_digest = None
        resume_message = ""
        restart_message = ""
        takeover_protocol = None
        work_context_stack = None
        memory_retrieval_state = None
        pointer_fields = {
            "currentNodeId": "standby",
            "workingNodeAnnotation": "<Working_Node: standby>",
            "pcMemo": "",
            "topFrameId": "",
            "stackDigest": "",
        }
    else:
        task_objective = (
            task_runtime_state.task_objective
            or _normalized_optional_text(request.get("taskObjective"))
            or _normalized_optional_text(request.get("currentObjective"))
            or _normalized_optional_text(getattr(task, "current_objective", None))
            or _normalized_optional_text(getattr(task, "goal", None))
        )
        current_focus = (
            task_runtime_state.current_focus
            or _normalized_optional_text(request.get("currentFocus"))
            or _normalized_optional_text(getattr(task, "current_focus", None))
            or "runtime execution"
        )
        current_node_id = (
            task_runtime_state.current_node_id
            or _normalized_optional_text(request.get("currentNodeId"))
        )
        working_node_annotation = (
            task_runtime_state.working_node_annotation
            or _normalized_optional_text(request.get("workingNodeAnnotation"))
            or _working_node_tag(current_node_id)
        )
        pc_memo = (
            task_runtime_state.pc_memo
            or _normalized_optional_text(request.get("pcMemo"))
        )
        resume_message = (
            task_runtime_state.resume_message
            or _normalized_optional_text(request.get("resumeMessage"))
            or _normalized_optional_text(getattr(task, "resume_message", None))
            or ""
        )
        restart_message = (
            task_runtime_state.restart_message
            or _normalized_optional_text(request.get("restartMessage"))
            or _normalized_optional_text(getattr(task, "restart_message", None))
            or ""
        )
        resume_message = sanitize_prompt_contract_text(resume_message) or ""
        restart_message = sanitize_prompt_contract_text(restart_message) or ""
        takeover_protocol = task_runtime_state.takeover_protocol
        if takeover_protocol is None:
            takeover_protocol = _takeover_protocol_from_request(request)

        work_context_stack = task_runtime_state.work_context_stack
        if work_context_stack is None:
            work_context_stack = _work_context_stack_from_request(request)

        memory_retrieval_state = task_runtime_state.memory_retrieval_state
        if memory_retrieval_state is None:
            memory_retrieval_state = request.get("memoryRetrievalState") if isinstance(request.get("memoryRetrievalState"), dict) else None

        if current_node_id is None:
            current_node_id = _resolved_current_node_id(request, {}, memory_retrieval_state, takeover_protocol)

        pointer_fields = _resolve_runtime_pointer_fields(request, {}, memory_retrieval_state, takeover_protocol)
        if task_runtime_state.current_node_id is not None:
            pointer_fields["currentNodeId"] = task_runtime_state.current_node_id
        if task_runtime_state.working_node_annotation is not None:
            pointer_fields["workingNodeAnnotation"] = task_runtime_state.working_node_annotation
        if task_runtime_state.pc_memo is not None:
            pointer_fields["pcMemo"] = task_runtime_state.pc_memo
        if work_context_stack is not None:
            pointer_fields["topFrameId"] = work_context_stack.top_frame_id
            pointer_fields["stackDigest"] = work_context_stack.stack_digest

        memory_retrieval_state = _canonicalize_memory_retrieval_state(
            memory_retrieval_state,
            current_node_id=current_node_id,
        )
        takeover_protocol = _canonicalize_takeover_protocol(
            takeover_protocol,
            current_node_id=current_node_id,
            pc_memo=pointer_fields["pcMemo"],
        )

    few_shot_assets = _resolve_few_shot_assets(profile, seed_template, resolved_registry)
    few_shot_refs = [asset.id for asset in few_shot_assets]
    few_shot_examples = "" if resume_path else _format_few_shot_examples(few_shot_assets)
    application_memory_assets = list(resolved_registry.get("applicationMemoryAssets") or [])
    application_memory_examples = _format_application_memory_assets(application_memory_assets)

    boot_sections = {
        "physical_interface": "\n\n".join(
            section
            for section in [
                "你只能通过结构化工具、MCP 泛型工具与消息通道触达外部世界，不得假设隐藏接口。",
                "当前可见模块能力:\n" + _format_active_capabilities(active_capabilities),
                "当前可见结构化工具描述:\n" + _format_registered_tools(resolved_registered_tools, strip_body=is_initial_awakening),
            ]
            if section
        ),
        "world_roots": _format_world_roots(root_mount),
        "behavior_constitution": _format_behavior_constitution(profile),
    }
    if not is_initial_awakening:
        boot_sections["scene_recovery"] = _format_scene_recovery(
            resume_path=resume_path,
            resume_message=restart_message or resume_message,
            pointer_fields=pointer_fields,
            memory_retrieval_state=memory_retrieval_state,
        )
    boot_sections = _dedupe_section_contents(boot_sections)

    system_sections = {
        "system_role": profile.system_role,
        "physical_interface": boot_sections.get("physical_interface", ""),
        "world_roots": boot_sections.get("world_roots", ""),
        "behavior_constitution": boot_sections.get("behavior_constitution", ""),
        "scene_preferences": _format_scene_preferences(profile),
        "tool_usage_preferences": _format_tool_usage_preferences(profile, seed_template, active_capabilities),
        "identity": seed_template.identity_overlay,
        "world": seed_template.context_overlay,
        "execution_bias": seed_template.execution_bias,
        "output_contract": profile.output_contract,
    }
    if few_shot_examples:
        system_sections["few_shot_examples"] = few_shot_examples
    if application_memory_examples:
        system_sections["application_memory"] = application_memory_examples
    if profile.self_evolution:
        system_sections["self_evolution"] = profile.self_evolution

    user_sections = {
        "runtime_state": _format_runtime_state(root_mount, include_resume_message=not bool(resume_path) and not is_initial_awakening),
    }
    if not is_initial_awakening:
        user_sections["task_contract"] = _format_task_contract(
            task,
            run_type,
            task_type,
            request,
            resume_path,
            objective_override=task_objective,
            focus_override=current_focus,
        )
        if "scene_recovery" in boot_sections:
            user_sections["scene_recovery"] = boot_sections["scene_recovery"]
        if takeover_protocol is not None:
            user_sections["takeover_protocol"] = _format_takeover_protocol(takeover_protocol)
        if work_context_stack is not None:
            user_sections["work_context_stack"] = _format_work_context_stack(work_context_stack)
        if memory_retrieval_state is not None:
            user_sections["memory_retrieval_state"] = _format_memory_retrieval_state(memory_retrieval_state)
    user_sections["capability_protocol_index"] = _format_capability_protocol_index(active_capabilities, resolved_registered_tools)
    user_sections["mounted_context_items"] = _format_context_lines(current_context, strip_body=is_initial_awakening)
    user_sections["runtime_glossary"] = _format_runtime_glossary()
    user_sections["response_requirements"] = _format_response_requirements(request, seed_template, resume_path)
    readonly_context_ref = request.get("readonlyContextRef") if isinstance(request.get("readonlyContextRef"), dict) else None
    if run_type == "subagent":
        subagent_scope_lines = [
            "你正在以 Sub-Agent 运行。当前挂载上下文就是你被授权使用的工作切片。",
            "如果关键前提超出这份切片，请明确报告缺失，而不是推测完整全局状态。",
        ]
        if readonly_context_ref and readonly_context_ref.get("locator"):
            subagent_scope_lines.append(f"只读上下文引用: {readonly_context_ref['locator']}")
        user_sections["subagent_scope"] = "\n".join(subagent_scope_lines)

    system_sections = _dedupe_section_contents(system_sections)
    user_sections = _dedupe_section_contents(user_sections)

    system_message = "\n\n".join(
        block for block in [_format_section(tag, content) for tag, content in system_sections.items()] if block
    )
    user_message = "\n\n".join(
        block for block in [_format_section(tag, content) for tag, content in user_sections.items()] if block
    )

    return CompiledPrompt(
        appId=app_id,
        promptProfileId=profile.id,
        promptProfileVersion=profile.version,
        seedTemplateId=seed_template.id,
        seedTemplateVersion=seed_template.version,
        runType=run_type,
        taskType=task_type,
        scenario=seed_template.scenario,
        registeredTools=resolved_registered_tools,
        bootSections=boot_sections,
        systemSections=system_sections,
        userSections=user_sections,
        fewShotRefs=few_shot_refs,
        takeoverProtocol=takeover_protocol,
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message},
        ],
    )