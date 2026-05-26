from __future__ import annotations

from pathlib import Path
import time
from threading import RLock
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from .app_catalog import active_application_id, build_application_catalog_snapshot, get_application_manifest
from .contracts import TaskTakeoverProtocol, WorkContextStack
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
    boot_sections: dict[str, str] = Field(default_factory=dict, alias="bootSections")
    system_sections: dict[str, str] = Field(default_factory=dict, alias="systemSections")
    user_sections: dict[str, str] = Field(default_factory=dict, alias="userSections")
    few_shot_refs: list[str] = Field(default_factory=list, alias="fewShotRefs")
    takeover_protocol: TaskTakeoverProtocol | None = Field(default=None, alias="takeoverProtocol")
    messages: list[dict[str, str]]


def _format_memory_retrieval_state(state: dict[str, Any]) -> str:
    lines = [
        f"摘要: {state.get('summary') or '未记录检索摘要。'}",
        f"请求 ID: {state.get('requestId') or 'unknown'}",
        f"窗口索引: {state.get('windowIndex') or 'unknown'}",
        f"命中引用数: {len(state.get('matchedNodeRefs') or [])}",
        f"物化引用数: {len(state.get('materializedNodeIds') or [])}",
    ]
    if state.get("workTreeNodeId") is not None:
        lines.append(f"工作树节点: {state['workTreeNodeId']}")
    if state.get("reverseTraceMode") is not None:
        lines.append(f"反向追踪模式: {'是' if bool(state.get('reverseTraceMode')) else '否'}")
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


def _normalize_prompt_text(value: str | None) -> str:
    return " ".join((value or "").split())


def _dedupe_section_contents(sections: dict[str, str]) -> dict[str, str]:
    deduped: dict[str, str] = {}
    seen_signatures: set[str] = set()
    for tag, content in sections.items():
        text = (content or "").strip()
        if not text:
            continue
        signature = _normalize_prompt_text(text)
        if signature in seen_signatures:
            continue
        deduped[tag] = text
        seen_signatures.add(signature)
    return deduped


def _localized_output_style(style: str | None) -> str:
    normalized = str(style or "concise").strip().lower()
    return {
        "concise": "简洁",
        "detailed": "详细",
        "structured": "结构化",
        "narrative": "叙事化",
    }.get(normalized, str(style or "concise"))


def _example_role_label(role: str) -> str:
    if role == "user":
        return "用户示例"
    if role == "assistant":
        return "助手示例"
    return "系统示例"


def _format_few_shot_examples(few_shot_assets: list[FewShotAsset]) -> str:
    if not few_shot_assets:
        return ""
    blocks: list[str] = ["以下示例仅用于对齐执行风格，不代表当前用户真实发言："]
    seen_signatures: set[tuple[tuple[str, str], ...]] = set()
    example_index = 1
    for asset in few_shot_assets:
        signature = tuple((message.role, _normalize_prompt_text(message.content)) for message in asset.messages)
        if not signature or signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        title = f"示例 {example_index}（{asset.name}）"
        if asset.description:
            title += f"：{asset.description}"
        block_lines = [title]
        for message in asset.messages:
            block_lines.append(f"{_example_role_label(message.role)}:\n{message.content.strip()}")
        blocks.append("\n".join(block_lines))
        example_index += 1
    return "\n\n".join(block for block in blocks if block.strip())


def _format_active_capabilities(active_capabilities: list[str]) -> str:
    if not active_capabilities:
        return "当前未显式挂载模块能力清单。"
    return "\n".join(f"- {module_id}" for module_id in active_capabilities)


def _format_registered_tools(registered_tools: list[dict[str, Any]]) -> str:
    if not registered_tools:
        return "当前没有通过模块 hook 暴露的结构化工具描述。"
    lines: list[str] = []
    for tool in registered_tools:
        permissions = ", ".join(tool.get("permissionRequired") or []) or "无"
        schema_ref = str(tool.get("schemaRef") or "未提供")
        module_id = str(tool.get("moduleId") or "unknown")
        lines.append(
            f"- {tool['name']} | 模块={module_id} | 执行模式={tool.get('executionMode') or 'sync'} | 权限={permissions} | schema={schema_ref}"
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


def _format_runtime_state(root_mount: dict[str, Any], *, include_resume_message: bool = True) -> str:
    mounted_refs = root_mount.get("mountedNodeRefs") or []
    lines = [
        f"系统导语: {root_mount.get('systemIntro') or ''}",
        f"根摘要: {root_mount.get('rootSummary') or ''}",
        f"任务说明: {root_mount.get('taskObjective') or ''}",
    ]
    if include_resume_message:
        lines.append(f"恢复提示: {root_mount.get('resumeMessage') or ''}")
    lines.extend(
        [
            f"挂载节点引用数: {len(mounted_refs)}",
            "当前可见能力:",
            _format_active_capabilities([str(item) for item in root_mount.get("activeCapabilities") or []]),
        ]
    )
    return "\n".join(lines).strip()


def _normalized_optional_text(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _working_node_tag(node_id: str | None) -> str:
    normalized = _normalized_optional_text(node_id) or "standby"
    return f"<Working_Node: {normalized}>"


def _resolved_current_node_id(
    request: dict[str, Any],
    root_mount: dict[str, Any],
    memory_retrieval_state: dict[str, Any] | None,
    takeover_protocol: TaskTakeoverProtocol | None,
) -> str | None:
    takeover_current_node_id = None
    if takeover_protocol is not None and takeover_protocol.work_tree is not None:
        takeover_current_node_id = _normalized_optional_text(takeover_protocol.work_tree.current_node_id)
    return (
        _normalized_optional_text(request.get("currentNodeId"))
        or _normalized_optional_text(root_mount.get("currentNodeId"))
        or takeover_current_node_id
        or _normalized_optional_text((memory_retrieval_state or {}).get("workTreeNodeId"))
    )


def _resolve_runtime_pointer_fields(
    request: dict[str, Any],
    root_mount: dict[str, Any],
    memory_retrieval_state: dict[str, Any] | None,
    takeover_protocol: TaskTakeoverProtocol | None,
) -> dict[str, str]:
    takeover_pc_memo: str | None = None
    if takeover_protocol is not None and takeover_protocol.work_tree is not None:
        takeover_pc_memo = _normalized_optional_text(takeover_protocol.work_tree.pc_memo)

    current_node_id = _resolved_current_node_id(request, root_mount, memory_retrieval_state, takeover_protocol)
    canonical_annotation = _working_node_tag(current_node_id)
    working_node_annotation = next(
        (
            normalized
            for normalized in (
                _normalized_optional_text(request.get("workingNodeAnnotation")),
                _normalized_optional_text(root_mount.get("workingNodeAnnotation")),
            )
            if normalized == canonical_annotation
        ),
        canonical_annotation,
    )
    pc_memo = (
        _normalized_optional_text(request.get("pcMemo"))
        or _normalized_optional_text(root_mount.get("pcMemo"))
        or takeover_pc_memo
    )
    top_frame_id = _normalized_optional_text(request.get("topFrameId")) or _normalized_optional_text(root_mount.get("topFrameId"))
    stack_digest = _normalized_optional_text(request.get("stackDigest")) or _normalized_optional_text(root_mount.get("stackDigest"))
    return {
        "currentNodeId": current_node_id or "standby",
        "workingNodeAnnotation": working_node_annotation,
        "pcMemo": pc_memo or "",
        "topFrameId": top_frame_id or "",
        "stackDigest": stack_digest or "",
    }


def _canonicalize_memory_retrieval_state(
    memory_retrieval_state: dict[str, Any] | None,
    *,
    current_node_id: str | None,
) -> dict[str, Any] | None:
    if memory_retrieval_state is None:
        return None
    normalized = dict(memory_retrieval_state)
    if current_node_id is not None:
        normalized["workTreeNodeId"] = current_node_id
    return normalized


def _canonicalize_takeover_protocol(
    takeover_protocol: TaskTakeoverProtocol | None,
    *,
    current_node_id: str | None,
    pc_memo: str | None,
) -> TaskTakeoverProtocol | None:
    if takeover_protocol is None or takeover_protocol.work_tree is None:
        return takeover_protocol

    work_tree_updates: dict[str, Any] = {}
    if current_node_id is not None and _normalized_optional_text(takeover_protocol.work_tree.current_node_id) != current_node_id:
        work_tree_updates["current_node_id"] = current_node_id
    normalized_pc_memo = _normalized_optional_text(pc_memo)
    if normalized_pc_memo is not None and _normalized_optional_text(takeover_protocol.work_tree.pc_memo) != normalized_pc_memo:
        work_tree_updates["pc_memo"] = normalized_pc_memo
    if not work_tree_updates:
        return takeover_protocol
    return takeover_protocol.model_copy(
        update={
            "work_tree": takeover_protocol.work_tree.model_copy(update=work_tree_updates),
        }
    )


def _work_context_stack_from_request(request: dict[str, Any]) -> WorkContextStack | None:
    candidate = request.get("workContextStack") if isinstance(request.get("workContextStack"), dict) else None
    if candidate is None:
        return None
    try:
        return WorkContextStack.model_validate(candidate)
    except Exception:
        return None


def _format_work_context_stack(work_context_stack: WorkContextStack) -> str:
    frames = work_context_stack.frames
    if not frames:
        return "工作上下文栈为空。"
    lines = [
        f"topFrameId: {work_context_stack.top_frame_id}",
        f"stackDigest: {work_context_stack.stack_digest}",
        "activePath: " + " -> ".join(frame.node_id for frame in frames),
    ]
    top_frame = next((frame for frame in frames if frame.id == work_context_stack.top_frame_id), frames[-1])
    if top_frame.frame_header:
        lines.append(f"topFrameHeader: {top_frame.frame_header}")
    if top_frame.cursor_state:
        lines.append(f"cursorState: {top_frame.cursor_state}")
    summary_frames = [frame for frame in frames[-3:] if frame.child_completion_summaries]
    if summary_frames:
        lines.append("childCompletionSummaries:")
        for frame in summary_frames:
            frame_label = frame.frame_header or frame.working_node_annotation or frame.node_id
            lines.append(f"- {frame_label}")
            for item in frame.child_completion_summaries[-4:]:
                status_label = f"[{item.status}] " if item.status != "completed" else ""
                lines.append(f"  - {status_label}{item.child_node_id}: {normalize_excerpt(item.summary, 120)}")
    return "\n".join(lines)


def _format_tool_usage_preferences(
    profile: PromptProfile,
    seed_template: SeedTemplate | None,
    active_capabilities: list[str] | None = None,
) -> str:
    sections = [
        section
        for section in [
            "工具使用偏好:",
            profile.tool_policy,
            seed_template.tool_policy_overlay if seed_template is not None else None,
        ]
        if section
    ]
    capability_set = {str(item) for item in active_capabilities or []}
    if {"text-memory", "shared-memory"} & capability_set:
        sections.append(
            "\n".join(
                [
                    "记忆修改优先级:",
                    "1. 默认优先使用正式记忆工具（例如 text_memory.* / shared_memory.*）完成读取、版本保护更新、追加日志、提案与遗忘。",
                    "2. 只有在需要不中断当前回答、且修改足够轻量时，才使用 <memory-write> 作为旁路写入。",
                    "3. 节点过宽、存在多个独立主题或冲突风险高时，优先创建细分子节点做空间隔离，再通过 relate 或 proposal 关联回父节点。",
                    "4. 遇到 latestVersionId 冲突时，不要静默覆盖；改用 append_memory_log 或 submit_memory_proposal 把冲突转成可继续处理的合并任务。",
                ]
            )
        )
    return "\n\n".join(sections)


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


def _format_task_contract(task: Any, run_type: str, task_type: str, request: dict[str, Any], resume_path: str | None) -> str:
    objective = str(request.get("taskObjective") or request.get("currentObjective") or task.current_objective or task.goal)
    focus = str(request.get("currentFocus") or task.current_focus or "runtime execution")
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
    additional = request.get("responseRequirements")
    has_delivery_contract = isinstance(additional, str) and additional.strip()
    is_resume = bool(resume_path)
    lines = [
        "1. 基于完整的工作树状态和记忆内容自主判断下一步行动。需要交付则直接交付，需要规划则进行规划，不要被强制指令干扰。",
        '2. 若需要操作工作树，必须通过动作标签显式声明：创建新子节点使用 <work-node-create ...></work-node-create>，进入已有子节点使用 <work-node-enter nodeId="..."></work-node-enter>。',
        "3. 父节点强编排：child 完成或失败返回父节点后，由父节点决定下一步（进入已有 child、创建新 child、或直接汇总交付），不要默认自动跳 sibling。",
        "4. 若证据不足，明确说明缺失信息，不要补空白。",
        "5. 保持输出 grounded 在当前挂载上下文、工具结果和正式状态上。",
        f"6. 默认采用 {localized_style} 风格，除非任务另有明确要求。",
    ]
    if is_resume:
        lines.append(f"{len(lines) + 1}. 恢复态下，把 resume_message 视为接续上下文的提示（context hint），结合记忆树继续执行，无需退回初始规划状态。")
        lines.append(f"{len(lines) + 1}. 恢复态优先按 结果/证据/待确认项/未完成项（result/evidence/pending/incomplete）组织交付，不要回退成纯规划。")
        lines.append(f"{len(lines) + 1}. 恢复态必须包含 judgment 字段并给出当前完成度判断。")
    if bool(request.get("memoryWriteTagsEnabled", True)):
        lines.append(
            f'{len(lines) + 1}. 记忆修改默认优先使用正式记忆工具；仅当需要不中断回答且改动足够轻量时，才插入 <memory-write title="..." rootBranch="context">记忆内容</memory-write>；更新已有节点时使用 nodeId="..." action="append|replace"。'
        )
    if has_delivery_contract:
        lines.append(f"{len(lines) + 1}. 附加要求: {additional.strip()}")
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
    takeover_protocol = _takeover_protocol_from_request(request)
    work_context_stack = _work_context_stack_from_request(request)
    memory_retrieval_state = request.get("memoryRetrievalState") if isinstance(request.get("memoryRetrievalState"), dict) else None
    current_node_id = _resolved_current_node_id(request, root_mount, memory_retrieval_state, takeover_protocol)
    pointer_fields = _resolve_runtime_pointer_fields(request, root_mount, memory_retrieval_state, takeover_protocol)
    memory_retrieval_state = _canonicalize_memory_retrieval_state(
        memory_retrieval_state,
        current_node_id=current_node_id,
    )
    takeover_protocol = _canonicalize_takeover_protocol(
        takeover_protocol,
        current_node_id=current_node_id,
        pc_memo=pointer_fields["pcMemo"],
    )
    pointer_fields = _resolve_runtime_pointer_fields(request, root_mount, memory_retrieval_state, takeover_protocol)
    resume_message = (
        _normalized_optional_text(request.get("restartMessage"))
        or _normalized_optional_text(request.get("resumeMessage"))
        or _normalized_optional_text(getattr(task, "restart_message", None))
        or _normalized_optional_text(getattr(task, "resume_message", None))
        or _normalized_optional_text(root_mount.get("resumeMessage"))
        or ""
    )
    few_shot_assets = _resolve_few_shot_assets(profile, seed_template, resolved_registry)
    few_shot_refs = [asset.id for asset in few_shot_assets]
    few_shot_examples = "" if resume_path else _format_few_shot_examples(few_shot_assets)

    boot_sections = {
        "physical_interface": "\n\n".join(
            section
            for section in [
                "你只能通过结构化工具、MCP 泛型工具与消息通道触达外部世界，不得假设隐藏接口。",
                "当前可见模块能力:\n" + _format_active_capabilities(active_capabilities),
                "当前可见结构化工具描述:\n" + _format_registered_tools(resolved_registered_tools),
            ]
            if section
        ),
        "world_roots": _format_world_roots(root_mount),
        "behavior_constitution": _format_behavior_constitution(profile),
        "scene_recovery": _format_scene_recovery(
            resume_path=resume_path,
            resume_message=resume_message,
            pointer_fields=pointer_fields,
            memory_retrieval_state=memory_retrieval_state,
        ),
    }
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
    if profile.self_evolution:
        system_sections["self_evolution"] = profile.self_evolution

    user_sections = {
        "runtime_state": _format_runtime_state(root_mount, include_resume_message=not bool(resume_path)),
        "task_contract": _format_task_contract(task, run_type, task_type, request, resume_path),
        "scene_recovery": boot_sections.get("scene_recovery", ""),
        "capability_protocol_index": _format_capability_protocol_index(active_capabilities, resolved_registered_tools),
        "mounted_context_items": _format_context_lines(current_context),
        "response_requirements": _format_response_requirements(request, seed_template, resume_path),
    }
    if takeover_protocol is not None:
        user_sections["takeover_protocol"] = _format_takeover_protocol(takeover_protocol)
    if work_context_stack is not None:
        user_sections["work_context_stack"] = _format_work_context_stack(work_context_stack)
    if memory_retrieval_state is not None:
        user_sections["memory_retrieval_state"] = _format_memory_retrieval_state(memory_retrieval_state)
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