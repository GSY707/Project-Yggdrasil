from __future__ import annotations

from pathlib import Path
import time
from threading import RLock
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from .app_catalog import active_application_id, build_application_catalog_snapshot, get_application_manifest
from .contracts import TaskTakeoverProtocol
from .catalog import build_module_catalog_snapshot
from .hook_runtime import collect_hook_results
from .hooks import HookNames
from .persistence.constants import DEFAULT_APP_ID
from .support import normalize_excerpt, read_json, resolve_workspace_root
from .tool_runtime import resolve_registered_tool_descriptors


_PROMPT_REGISTRY_CACHE: dict[tuple[Any, ...], tuple[dict[str, Any], float]] = {}
_PROMPT_REGISTRY_CACHE_TTL = 2.0
_PROMPT_REGISTRY_CACHE_LOCK = RLock()


def invalidate_prompt_registry_cache() -> None:
    with _PROMPT_REGISTRY_CACHE_LOCK:
        _PROMPT_REGISTRY_CACHE.clear()


def _prompt_registry_cache_key(app_id: str, active_capabilities: list[str] | None) -> tuple[Any, ...]:
    application_snapshot = build_application_catalog_snapshot()
    module_snapshot = build_module_catalog_snapshot()
    normalized_capabilities = tuple(sorted({str(item) for item in active_capabilities or []}))
    return (
        str(resolve_workspace_root()),
        app_id,
        normalized_capabilities,
        application_snapshot.generated_at.isoformat(),
        module_snapshot.generated_at.isoformat(),
    )


class PromptProfile(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    name: str
    version: str
    run_scope: Literal["main", "subagent", "any"] = Field(alias="runScope")
    system_role: str = Field(alias="systemRole")
    kernel_truth: str = Field(alias="kernelTruth")
    behavior_guidelines: str = Field(alias="behaviorGuidelines")
    tool_policy: str = Field(alias="toolPolicy")
    memory_policy: str = Field(alias="memoryPolicy")
    evidence_policy: str = Field(alias="evidencePolicy")
    output_contract: str = Field(alias="outputContract")
    self_evolution: str | None = Field(default=None, alias="selfEvolution")
    few_shot_refs: list[str] = Field(default_factory=list, alias="fewShotRefs")
    source_app_id: str | None = Field(default=None, alias="sourceAppId")
    source_module_id: str | None = Field(default=None, alias="sourceModuleId")


class SeedTemplate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    name: str
    version: str
    domain: Literal["coding", "writing", "research", "maintenance", "generic"]
    scenario: str
    identity_overlay: str = Field(alias="identityOverlay")
    context_overlay: str = Field(alias="contextOverlay")
    execution_bias: str = Field(alias="executionBias")
    tool_policy_overlay: str | None = Field(default=None, alias="toolPolicyOverlay")
    output_style: str | None = Field(default=None, alias="outputStyle")
    retrieval_hints: dict[str, Any] = Field(default_factory=dict, alias="retrievalHints")
    selection_rules: dict[str, Any] = Field(default_factory=dict, alias="selectionRules")
    few_shot_refs: list[str] = Field(default_factory=list, alias="fewShotRefs")
    source_app_id: str | None = Field(default=None, alias="sourceAppId")
    source_module_id: str | None = Field(default=None, alias="sourceModuleId")


class FewShotMessage(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    role: Literal["user", "assistant", "system"]
    content: str


class FewShotAsset(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    name: str
    version: str
    description: str | None = None
    messages: list[FewShotMessage] = Field(default_factory=list)
    source_app_id: str | None = Field(default=None, alias="sourceAppId")
    source_module_id: str | None = Field(default=None, alias="sourceModuleId")


class CompiledPrompt(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    app_id: str = Field(alias="appId")
    prompt_profile_id: str = Field(alias="promptProfileId")
    prompt_profile_version: str = Field(alias="promptProfileVersion")
    seed_template_id: str | None = Field(default=None, alias="seedTemplateId")
    seed_template_version: str | None = Field(default=None, alias="seedTemplateVersion")
    run_type: str = Field(alias="runType")
    task_type: str = Field(alias="taskType")
    scenario: str | None = None
    registered_tools: list[dict[str, Any]] = Field(default_factory=list, alias="registeredTools")
    system_sections: dict[str, str] = Field(default_factory=dict, alias="systemSections")
    user_sections: dict[str, str] = Field(default_factory=dict, alias="userSections")
    few_shot_refs: list[str] = Field(default_factory=list, alias="fewShotRefs")
    takeover_protocol: TaskTakeoverProtocol | None = Field(default=None, alias="takeoverProtocol")
    messages: list[dict[str, str]]


def _format_memory_retrieval_state(state: dict[str, Any]) -> str:
    lines = [
        f"Summary: {state.get('summary') or 'No retrieval summary was recorded.'}",
        f"Request id: {state.get('requestId') or 'unknown'}",
        f"Window index: {state.get('windowIndex') or 'unknown'}",
        f"Matched refs: {len(state.get('matchedNodeRefs') or [])}",
        f"Materialized refs: {len(state.get('materializedNodeIds') or [])}",
    ]
    if state.get("workTreeNodeId") is not None:
        lines.append(f"Work tree node: {state['workTreeNodeId']}")
    if state.get("reverseTraceMode") is not None:
        lines.append(f"Reverse trace mode: {bool(state.get('reverseTraceMode'))}")
    return "\n".join(lines)


def _load_structured_payload(path: Path) -> dict[str, Any]:
    if path.suffix.lower() == ".json":
        payload = read_json(path, {})
        if isinstance(payload, dict):
            return payload
        raise ValueError(f"Prompt asset at {path} is not a mapping.")

    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Prompt asset at {path} is not a mapping.")
    return payload


def _load_profiles_from_application(app_manifest: Any) -> list[PromptProfile]:
    workspace_root = resolve_workspace_root()
    profiles: list[PromptProfile] = []
    for relative_path in app_manifest.prompt_profile_files:
        payload = _load_structured_payload(workspace_root / relative_path)
        payload.setdefault("sourceAppId", app_manifest.app_id)
        profiles.append(PromptProfile.model_validate(payload))
    return profiles


def _load_seed_templates_from_application(app_manifest: Any) -> list[SeedTemplate]:
    workspace_root = resolve_workspace_root()
    templates: list[SeedTemplate] = []
    for relative_path in app_manifest.seed_template_files:
        payload = _load_structured_payload(workspace_root / relative_path)
        payload.setdefault("sourceAppId", app_manifest.app_id)
        templates.append(SeedTemplate.model_validate(payload))
    return templates


def _load_few_shot_assets_from_directory(
    directory: Path,
    *,
    source_app_id: str | None = None,
    source_module_id: str | None = None,
) -> list[FewShotAsset]:
    assets_dir = directory / "few-shots"
    if not assets_dir.exists():
        return []
    assets: list[FewShotAsset] = []
    for asset_path in sorted(assets_dir.rglob("*")):
        if not asset_path.is_file() or asset_path.suffix.lower() not in {".yaml", ".yml", ".json"}:
            continue
        payload = _load_structured_payload(asset_path)
        payload.setdefault("sourceAppId", source_app_id)
        payload.setdefault("sourceModuleId", source_module_id)
        assets.append(FewShotAsset.model_validate(payload))
    return assets


def _load_few_shot_assets_from_application(app_manifest: Any) -> list[FewShotAsset]:
    workspace_root = resolve_workspace_root()
    manifest_dir = (workspace_root / app_manifest.manifest_path).parent
    return _load_few_shot_assets_from_directory(manifest_dir, source_app_id=app_manifest.app_id)


def _allowed_module_ids(app_manifest: Any, active_capabilities: list[str] | None) -> list[str]:
    allowlist: list[str] = []
    for module_id in [
        *app_manifest.module_dependencies,
        *app_manifest.capability_module_ids,
        *app_manifest.scene_module_ids,
    ]:
        if module_id not in allowlist:
            allowlist.append(module_id)
    return allowlist


def _collect_module_prompt_profiles(app_id: str, module_ids: list[str]) -> list[PromptProfile]:
    profiles: list[PromptProfile] = []
    if not module_ids:
        return profiles
    for item in collect_hook_results(
        HookNames.PROMPT_PROFILES_REGISTER,
        {"appId": app_id},
        module_ids=module_ids,
    ):
        if item.get("error"):
            continue
        result = item.get("result") if isinstance(item.get("result"), dict) else {}
        module_id = str(item.get("moduleId") or "")
        for payload in result.get("promptProfiles") or result.get("profiles") or []:
            if not isinstance(payload, dict):
                continue
            normalized = dict(payload)
            normalized.setdefault("sourceAppId", app_id)
            normalized.setdefault("sourceModuleId", module_id)
            profiles.append(PromptProfile.model_validate(normalized))
    return profiles


def _collect_module_seed_templates(app_id: str, module_ids: list[str]) -> list[SeedTemplate]:
    templates: list[SeedTemplate] = []
    if not module_ids:
        return templates
    for item in collect_hook_results(
        HookNames.PROMPT_SEED_TEMPLATES_REGISTER,
        {"appId": app_id},
        module_ids=module_ids,
    ):
        if item.get("error"):
            continue
        result = item.get("result") if isinstance(item.get("result"), dict) else {}
        module_id = str(item.get("moduleId") or "")
        for payload in result.get("seedTemplates") or result.get("templates") or []:
            if not isinstance(payload, dict):
                continue
            normalized = dict(payload)
            normalized.setdefault("sourceAppId", app_id)
            normalized.setdefault("sourceModuleId", module_id)
            templates.append(SeedTemplate.model_validate(normalized))
    return templates


def _collect_module_few_shot_assets(app_id: str, module_ids: list[str]) -> list[FewShotAsset]:
    if not module_ids:
        return []
    workspace_root = resolve_workspace_root()
    snapshot = build_module_catalog_snapshot(workspace_root)
    manifests_by_id = {manifest.module_id: manifest for manifest in snapshot.manifests}
    assets: list[FewShotAsset] = []
    seen_module_dirs: set[str] = set()
    for module_id in module_ids:
        manifest = manifests_by_id.get(module_id)
        if manifest is None:
            continue
        module_dir = (workspace_root / manifest.manifest_path).parent
        module_dir_key = str(module_dir)
        if module_dir_key in seen_module_dirs:
            continue
        seen_module_dirs.add(module_dir_key)
        assets.extend(
            _load_few_shot_assets_from_directory(
                module_dir,
                source_app_id=app_id,
                source_module_id=module_id,
            )
        )
    return assets


def assemble_prompt_registry(
    app_id: str | None = None,
    active_capabilities: list[str] | None = None,
) -> dict[str, Any]:
    resolved_app_id = str(app_id or active_application_id() or DEFAULT_APP_ID)
    cache_key = _prompt_registry_cache_key(resolved_app_id, active_capabilities)
    now = time.monotonic()
    with _PROMPT_REGISTRY_CACHE_LOCK:
        cached = _PROMPT_REGISTRY_CACHE.get(cache_key)
        if cached is not None and now - cached[1] < _PROMPT_REGISTRY_CACHE_TTL:
            return cached[0]

    app_manifest = get_application_manifest(resolved_app_id)
    selected_module_ids = _allowed_module_ids(app_manifest, active_capabilities)

    profiles_by_id: dict[str, PromptProfile] = {}
    for profile in [
        *_load_profiles_from_application(app_manifest),
        *_collect_module_prompt_profiles(resolved_app_id, selected_module_ids),
    ]:
        profiles_by_id[profile.id] = profile

    templates_by_id: dict[str, SeedTemplate] = {}
    for template in [
        *_load_seed_templates_from_application(app_manifest),
        *_collect_module_seed_templates(resolved_app_id, selected_module_ids),
    ]:
        templates_by_id[template.id] = template

    few_shot_assets_by_id: dict[str, FewShotAsset] = {}
    for asset in [
        *_load_few_shot_assets_from_application(app_manifest),
        *_collect_module_few_shot_assets(resolved_app_id, selected_module_ids),
    ]:
        few_shot_assets_by_id[asset.id] = asset

    registry = {
        "application": app_manifest,
        "selectedModuleIds": selected_module_ids,
        "promptProfiles": [profiles_by_id[key] for key in sorted(profiles_by_id)],
        "seedTemplates": [templates_by_id[key] for key in sorted(templates_by_id)],
        "fewShotAssets": [few_shot_assets_by_id[key] for key in sorted(few_shot_assets_by_id)],
    }
    with _PROMPT_REGISTRY_CACHE_LOCK:
        _PROMPT_REGISTRY_CACHE[cache_key] = (registry, time.monotonic())
    return registry


def list_registered_agent_tools(active_capabilities: list[str] | None = None) -> list[dict[str, Any]]:
    return [tool.model_dump(by_alias=True, mode="json") for tool in resolve_registered_tool_descriptors(active_capabilities)]


def get_prompt_profile_definition(
    prompt_profile_id: str,
    app_id: str | None = None,
    active_capabilities: list[str] | None = None,
    registry: dict[str, Any] | None = None,
) -> PromptProfile | None:
    resolved_registry = registry or assemble_prompt_registry(app_id=app_id, active_capabilities=active_capabilities)
    return next(
        (profile for profile in resolved_registry["promptProfiles"] if profile.id == prompt_profile_id),
        None,
    )


def list_prompt_profile_definitions(
    app_id: str | None = None,
    active_capabilities: list[str] | None = None,
    registry: dict[str, Any] | None = None,
) -> list[PromptProfile]:
    resolved_registry = registry or assemble_prompt_registry(app_id=app_id, active_capabilities=active_capabilities)
    return list(resolved_registry["promptProfiles"])


def get_seed_template_definition(
    seed_template_id: str | None,
    app_id: str | None = None,
    active_capabilities: list[str] | None = None,
    registry: dict[str, Any] | None = None,
) -> SeedTemplate | None:
    if seed_template_id is None:
        return None
    resolved_registry = registry or assemble_prompt_registry(app_id=app_id, active_capabilities=active_capabilities)
    return next(
        (template for template in resolved_registry["seedTemplates"] if template.id == seed_template_id),
        None,
    )


def list_seed_template_definitions(
    app_id: str | None = None,
    active_capabilities: list[str] | None = None,
    registry: dict[str, Any] | None = None,
) -> list[SeedTemplate]:
    resolved_registry = registry or assemble_prompt_registry(app_id=app_id, active_capabilities=active_capabilities)
    return list(resolved_registry["seedTemplates"])


def _select_prompt_profile(run_type: str, request: dict[str, Any], app_manifest: Any, profiles: list[PromptProfile]) -> PromptProfile:
    explicit = str(request.get("promptProfileId") or "").strip()
    profiles_by_id = {profile.id: profile for profile in profiles}
    if explicit and explicit in profiles_by_id:
        return profiles_by_id[explicit]

    configured_default = (
        app_manifest.subagent_prompt_profile_id
        if run_type == "subagent"
        else app_manifest.default_prompt_profile_id
    )
    if configured_default and configured_default in profiles_by_id:
        return profiles_by_id[configured_default]

    ranked_candidates = [profile for profile in profiles if profile.run_scope in {run_type, "any"}]
    ranked_candidates.sort(
        key=lambda profile: (
            0 if profile.run_scope == run_type else 1,
            profile.id,
        )
    )
    if ranked_candidates:
        return ranked_candidates[0]
    raise KeyError(f"No prompt profile available for run type {run_type} in app {app_manifest.app_id}.")


def _normalized_markers(request: dict[str, Any], keys: list[str]) -> set[str]:
    markers: set[str] = set()
    for key in keys:
        value = request.get(key)
        if value is None:
            continue
        markers.add(str(value).strip().lower())
    return markers


def _selection_score(
    template: SeedTemplate,
    *,
    task_type: str,
    run_type: str,
    request: dict[str, Any],
    default_seed_template_id: str | None,
) -> int | None:
    rules = dict(template.selection_rules or {})
    score = int(rules.get("priority", 0) or 0)

    task_types = {str(item).strip().lower() for item in rules.get("taskTypes") or [] if str(item).strip()}
    if task_types:
        if task_type.lower() not in task_types:
            return None
        score += 100

    run_types = {str(item).strip().lower() for item in rules.get("runTypes") or [] if str(item).strip()}
    if run_types:
        if run_type.lower() not in run_types:
            return None
        score += 50

    coding_modes = {str(item).strip().lower() for item in rules.get("codingModes") or [] if str(item).strip()}
    request_coding_modes = _normalized_markers(request, ["codingMode", "projectMode"])
    if coding_modes:
        if not request_coding_modes.intersection(coding_modes):
            return None
        score += 25

    project_states = {str(item).strip().lower() for item in rules.get("projectStates") or [] if str(item).strip()}
    request_project_states = _normalized_markers(request, ["projectState"])
    if project_states:
        if not request_project_states.intersection(project_states):
            return None
        score += 20

    if template.domain == task_type:
        score += 10
    if default_seed_template_id and template.id == default_seed_template_id:
        score += 1
    return score


def _select_seed_template(
    task_type: str,
    run_type: str,
    request: dict[str, Any],
    app_manifest: Any,
    templates: list[SeedTemplate],
) -> SeedTemplate:
    explicit = str(request.get("seedTemplateId") or "").strip()
    explicit_scenario = str(request.get("promptScenario") or "").strip()
    if explicit or explicit_scenario:
        for template in templates:
            if template.id == explicit or template.id == explicit_scenario or template.scenario == explicit_scenario:
                return template

    scored: list[tuple[int, SeedTemplate]] = []
    for template in templates:
        score = _selection_score(
            template,
            task_type=task_type,
            run_type=run_type,
            request=request,
            default_seed_template_id=app_manifest.default_seed_template_id,
        )
        if score is not None:
            scored.append((score, template))

    if scored:
        scored.sort(key=lambda item: (-item[0], item[1].id))
        return scored[0][1]

    if app_manifest.default_seed_template_id:
        fallback = next(
            (template for template in templates if template.id == app_manifest.default_seed_template_id),
            None,
        )
        if fallback is not None:
            return fallback

    generic = next((template for template in templates if template.domain == "generic"), None)
    if generic is not None:
        return generic
    raise KeyError(f"No seed template available for task type {task_type} in app {app_manifest.app_id}.")


def _format_section(tag: str, content: str | None) -> str:
    text = (content or "").strip()
    if not text:
        return ""
    return f"<{tag}>\n{text}\n</{tag}>"


def _format_active_capabilities(active_capabilities: list[str]) -> str:
    if not active_capabilities:
        return "当前未显式挂载模块能力清单。"
    return "\n".join(f"- {module_id}" for module_id in active_capabilities)


def _format_registered_tools(registered_tools: list[dict[str, Any]]) -> str:
    if not registered_tools:
        return "当前没有通过模块 hook 暴露的结构化工具描述。"
    lines: list[str] = []
    for tool in registered_tools:
        permissions = ", ".join(tool.get("permissionRequired") or []) or "none"
        schema_ref = str(tool.get("schemaRef") or "n/a")
        description = str(tool.get("description") or tool.get("displayName") or tool["name"])
        lines.append(
            f"- {tool['name']} | {description} | mode={tool.get('executionMode') or 'sync'} | permissions={permissions} | schema={schema_ref}"
        )
    return "\n".join(lines)


def _format_context_lines(current_context: list[dict[str, Any]], *, limit: int = 10) -> str:
    lines: list[str] = []
    for index, item in enumerate(current_context[:limit], start=1):
        title = str(item.get("title") or item.get("kind") or f"context-{index}")
        raw_content = str(item.get("content") or item)
        content = raw_content if bool(item.get("verbatim")) else normalize_excerpt(raw_content, 240)
        root_branch = str(item.get("rootBranch") or item.get("mode") or "context")
        lines.append(f"{index}. [{root_branch}] {title}: {content}")
    return "\n".join(lines) if lines else "当前没有额外挂载的上下文切片。"


def _format_runtime_state(root_mount: dict[str, Any]) -> str:
    mounted_refs = root_mount.get("mountedNodeRefs") or []
    return "\n".join(
        [
            f"System intro: {root_mount.get('systemIntro') or ''}",
            f"Root summary: {root_mount.get('rootSummary') or ''}",
            f"Task objective: {root_mount.get('taskObjective') or ''}",
            f"Resume message: {root_mount.get('resumeMessage') or ''}",
            f"Mounted node refs: {len(mounted_refs)}",
            "Active capabilities:",
            _format_active_capabilities([str(item) for item in root_mount.get("activeCapabilities") or []]),
        ]
    ).strip()


def _format_task_contract(task: Any, run_type: str, task_type: str, request: dict[str, Any], resume_path: str | None) -> str:
    objective = str(request.get("taskObjective") or request.get("currentObjective") or task.current_objective or task.goal)
    focus = str(request.get("currentFocus") or task.current_focus or "runtime execution")
    lines = [
        f"Task title: {task.title}",
        f"Task goal: {task.goal}",
        f"Current objective: {objective}",
        f"Current focus: {focus}",
        f"Run type: {run_type}",
        f"Task type: {task_type}",
    ]
    if resume_path:
        lines.append(f"Resume path: {resume_path}")
    return "\n".join(lines)


def _format_response_requirements(request: dict[str, Any], seed_template: SeedTemplate | None) -> str:
    style = seed_template.output_style if seed_template is not None else "concise"
    additional = request.get("responseRequirements")
    has_delivery_contract = isinstance(additional, str) and additional.strip()
    lines = [
        "1. 直接产出以下要求指定的最终交付物，不要停在计划或下一步总结。" if has_delivery_contract else "1. 先总结当前局势，再给出最稳妥的下一步。",
        "2. 若证据不足，明确说明缺失信息，不要补空白。",
        "3. 保持输出 grounded 在当前挂载上下文、工具结果和正式状态上。",
        f"4. 默认采用 {style} 风格，除非任务另有明确要求。",
    ]
    if bool(request.get("memoryWriteTagsEnabled", True)):
        lines.append(
            '5. 如需在不中断回答的情况下修改记忆树，可插入 <memory-write title="..." rootBranch="context">记忆内容</memory-write>；更新已有节点时使用 nodeId="..." action="append|replace"。'
        )
    if has_delivery_contract:
        lines.append(f"{len(lines) + 1}. Additional requirement: {additional.strip()}")
    return "\n".join(lines)


def _takeover_protocol_from_request(request: dict[str, Any]) -> TaskTakeoverProtocol | None:
    candidate = request.get("takeoverProtocol") if isinstance(request.get("takeoverProtocol"), dict) else None
    if candidate is None:
        return None
    try:
        return TaskTakeoverProtocol.model_validate(candidate)
    except Exception:
        return None


def _format_takeover_protocol(protocol: TaskTakeoverProtocol) -> str:
    lines = [
        f"Objective summary: {protocol.objective_summary}",
        f"Current phase: {protocol.current_phase}",
        f"Status: {protocol.status}",
        "Constraints:",
    ]
    if protocol.constraints:
        lines.extend(f"- [{item.category}] {item.label}: {item.value}" for item in protocol.constraints)
    else:
        lines.append("- none")
    lines.append("Plan:")
    if protocol.plan:
        lines.extend(
            f"{index}. [{step.phase}] {step.title}: {step.instructions}"
            for index, step in enumerate(protocol.plan, start=1)
        )
    else:
        lines.append("1. No formal plan was generated.")
    if protocol.work_tree is not None:
        lines.append("Work tree:")
        lines.append(
            f"- status={protocol.work_tree.status}; currentNode={protocol.work_tree.current_node_id or 'none'}; entropyBudgetRemaining={protocol.work_tree.entropy_budget_remaining}"
        )
        if protocol.work_tree.nodes:
            lines.extend(
                f"- [{node.phase}/{node.status}] {node.title}"
                for node in protocol.work_tree.nodes[:6]
            )
    if protocol.delivery_sections:
        lines.append("Delivery checkpoints:")
        lines.extend(
            f"- {section.section}: {normalize_excerpt(section.content or section.status, 120)}"
            for section in protocol.delivery_sections
        )
    lines.extend(
        [
            f"Plan quality: {protocol.metrics.plan_quality_score_0_100}",
            f"Rework rate: {protocol.metrics.rework_rate}",
            f"Delivery completeness: {protocol.metrics.delivery_completeness_score_0_100}",
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
    takeover_protocol = _takeover_protocol_from_request(request)
    few_shot_assets = _resolve_few_shot_assets(profile, seed_template, resolved_registry)
    few_shot_refs = [asset.id for asset in few_shot_assets]
    few_shot_messages = [
        message.model_dump(mode="json")
        for asset in few_shot_assets
        for message in asset.messages
    ]

    system_sections = {
        "system_role": profile.system_role,
        "kernel_truth": profile.kernel_truth,
        "behavior_guidelines": profile.behavior_guidelines,
        "identity": seed_template.identity_overlay,
        "world": seed_template.context_overlay,
        "execution_bias": seed_template.execution_bias,
        "tool_policy": "\n\n".join(
            section
            for section in [
                profile.tool_policy,
                seed_template.tool_policy_overlay,
                "当前可见模块能力:\n" + _format_active_capabilities(active_capabilities),
                "当前可见结构化工具描述:\n" + _format_registered_tools(resolved_registered_tools),
            ]
            if section
        ),
        "memory_policy": profile.memory_policy,
        "evidence_policy": profile.evidence_policy,
        "output_contract": profile.output_contract,
    }
    if profile.self_evolution:
        system_sections["self_evolution"] = profile.self_evolution

    user_sections = {
        "runtime_state": _format_runtime_state(root_mount),
        "task_contract": _format_task_contract(task, run_type, task_type, request, resume_path),
        "mounted_context_items": _format_context_lines(current_context),
        "response_requirements": _format_response_requirements(request, seed_template),
    }
    if takeover_protocol is not None:
        user_sections["takeover_protocol"] = _format_takeover_protocol(takeover_protocol)
    memory_retrieval_state = request.get("memoryRetrievalState") if isinstance(request.get("memoryRetrievalState"), dict) else None
    if memory_retrieval_state is not None:
        user_sections["memory_retrieval_state"] = _format_memory_retrieval_state(memory_retrieval_state)
    resume_message = str(request.get("resumeMessage") or task.resume_message or "").strip()
    if resume_message:
        user_sections["resume_message"] = resume_message
    readonly_context_ref = request.get("readonlyContextRef") if isinstance(request.get("readonlyContextRef"), dict) else None
    if run_type == "subagent":
        subagent_scope_lines = [
            "你正在以 Sub-Agent 运行。当前挂载上下文就是你被授权使用的工作切片。",
            "如果关键前提超出这份切片，请明确报告缺失，而不是推测完整全局状态。",
        ]
        if readonly_context_ref and readonly_context_ref.get("locator"):
            subagent_scope_lines.append(f"Readonly context ref: {readonly_context_ref['locator']}")
        user_sections["subagent_scope"] = "\n".join(subagent_scope_lines)

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
        systemSections=system_sections,
        userSections=user_sections,
        fewShotRefs=few_shot_refs,
        takeoverProtocol=takeover_protocol,
        messages=[
            {"role": "system", "content": system_message},
            *few_shot_messages,
            {"role": "user", "content": user_message},
        ],
    )