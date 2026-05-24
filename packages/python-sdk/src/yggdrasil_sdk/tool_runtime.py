from __future__ import annotations

from importlib import import_module
import json
import time
from threading import RLock
from typing import Any

from .catalog import build_module_catalog_snapshot, load_in_process_plugin
from .contracts import ToolDescriptor
from .hooks import HookNames
from .mcp_bridge import load_mcp_bridge_snapshot
from .support import resolve_workspace_root


_TOOL_DESCRIPTOR_CACHE: dict[tuple[Any, ...], tuple[list[ToolDescriptor], float]] = {}
_TOOL_DESCRIPTOR_CACHE_TTL = 2.0
_TOOL_DESCRIPTOR_CACHE_LOCK = RLock()


def invalidate_tool_descriptor_cache() -> None:
    with _TOOL_DESCRIPTOR_CACHE_LOCK:
        _TOOL_DESCRIPTOR_CACHE.clear()


def _tool_descriptor_cache_key(active_capabilities: list[str] | None) -> tuple[Any, ...]:
    module_snapshot = build_module_catalog_snapshot()
    bridge_snapshot = load_mcp_bridge_snapshot(refresh_if_missing=False)
    normalized_capabilities = tuple(sorted({str(item) for item in active_capabilities or []}))
    return (
        str(resolve_workspace_root()),
        normalized_capabilities if active_capabilities is not None else None,
        module_snapshot.generated_at.isoformat(),
        str(bridge_snapshot.get("generatedAt") or ""),
    )


def _normalize_tool_descriptor(tool: dict[str, Any], module_id: str) -> ToolDescriptor:
    payload = dict(tool)
    payload.setdefault("moduleId", module_id)
    payload.setdefault("version", "0.1.0")
    payload.setdefault("displayName", payload.get("name") or module_id)
    payload.setdefault("schemaRef", "docs/specs/agent-runtime-protocol-v0.1.md")
    payload.setdefault("executionMode", "sync")
    payload.setdefault("timeoutMs", 5000)
    payload.setdefault("permissionRequired", [])
    payload.setdefault("inputSchema", {"type": "object", "properties": {}, "additionalProperties": False})
    return ToolDescriptor.model_validate(payload)


def resolve_registered_tool_descriptors(active_capabilities: list[str] | None = None) -> list[ToolDescriptor]:
    cache_key = _tool_descriptor_cache_key(active_capabilities)
    now = time.monotonic()
    with _TOOL_DESCRIPTOR_CACHE_LOCK:
        cached = _TOOL_DESCRIPTOR_CACHE.get(cache_key)
        if cached is not None and now - cached[1] < _TOOL_DESCRIPTOR_CACHE_TTL:
            return cached[0]

    snapshot = build_module_catalog_snapshot()
    installs_by_module_id = {record.module_id: record for record in snapshot.installs}
    descriptors: dict[str, ToolDescriptor] = {}

    for manifest in snapshot.manifests:
        install = installs_by_module_id.get(manifest.module_id)
        if install is None:
            continue
        if active_capabilities is not None and manifest.module_id not in active_capabilities:
            continue
        if install.desired_state != "enabled" or install.lifecycle_state not in {"active", "degraded", "discovered"}:
            continue
        if not manifest.entry_point:
            continue
        try:
            plugin = load_in_process_plugin(manifest.entry_point)
            registered_tools: list[dict[str, Any]] = []
            if HookNames.AGENT_TOOLS_REGISTER in manifest.hooks:
                for registration in plugin.register_hooks():
                    if registration.name != HookNames.AGENT_TOOLS_REGISTER:
                        continue
                    result = registration.handler(
                        {
                            "moduleId": manifest.module_id,
                            "manifest": manifest.model_dump(by_alias=True, mode="json"),
                        }
                    )
                    if isinstance(result, dict) and isinstance(result.get("tools"), list):
                        registered_tools.extend(tool for tool in result["tools"] if isinstance(tool, dict))
            if not registered_tools:
                registered_tools.extend(tool for tool in plugin.register_tools() if isinstance(tool, dict))
        except Exception:
            continue

        for tool in registered_tools:
            descriptor = _normalize_tool_descriptor(tool, manifest.module_id)
            descriptors[descriptor.name] = descriptor

    resolved = [descriptors[name] for name in sorted(descriptors)]
    with _TOOL_DESCRIPTOR_CACHE_LOCK:
        _TOOL_DESCRIPTOR_CACHE[cache_key] = (resolved, time.monotonic())
    return resolved


def list_registered_tool_payloads(active_capabilities: list[str] | None = None) -> list[dict[str, Any]]:
    return [tool.model_dump(by_alias=True, mode="json") for tool in resolve_registered_tool_descriptors(active_capabilities)]


def build_llm_tool_specs(registered_tools: list[dict[str, Any]] | list[ToolDescriptor]) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for tool in registered_tools:
        descriptor = tool if isinstance(tool, ToolDescriptor) else ToolDescriptor.model_validate(tool)
        if descriptor.execution_mode != "sync" or not descriptor.implementation_ref:
            continue
        parameters = dict(descriptor.input_schema or {})
        parameters.setdefault("type", "object")
        parameters.setdefault("properties", {})
        parameters.setdefault("additionalProperties", False)
        specs.append(
            {
                "type": "function",
                "function": {
                    "name": descriptor.name,
                    "description": descriptor.description or descriptor.display_name,
                    "parameters": parameters,
                },
            }
        )
    return specs


def _load_tool_callable(implementation_ref: str) -> Any:
    module_name, _, attribute_name = implementation_ref.partition(":")
    if not module_name or not attribute_name:
        raise ValueError(f"Unsupported tool implementation ref: {implementation_ref}")
    module = import_module(module_name)
    return getattr(module, attribute_name)


def _source_work_tree_node_id(root_mount: dict[str, Any]) -> str | None:
    direct_value = str(root_mount.get("currentNodeId") or "").strip()
    if direct_value:
        return direct_value
    takeover_protocol = root_mount.get("takeoverProtocol") if isinstance(root_mount.get("takeoverProtocol"), dict) else {}
    work_tree = takeover_protocol.get("workTree") if isinstance(takeover_protocol.get("workTree"), dict) else {}
    work_tree_current_node_id = str(work_tree.get("currentNodeId") or "").strip()
    if work_tree_current_node_id:
        return work_tree_current_node_id
    return None


def execute_registered_tool(
    tool_name: str,
    arguments: dict[str, Any],
    *,
    task: Any,
    run: Any,
    root_mount: dict[str, Any],
    current_context: list[dict[str, Any]],
) -> dict[str, Any]:
    descriptors = {tool.name: tool for tool in resolve_registered_tool_descriptors([str(item) for item in root_mount.get("activeCapabilities") or []])}
    descriptor = descriptors.get(tool_name)
    if descriptor is None:
        raise KeyError(f"Tool {tool_name} is not registered.")
    if descriptor.implementation_ref is None:
        raise RuntimeError(f"Tool {tool_name} does not declare an implementationRef.")
    payload = dict(arguments)
    payload["executionContext"] = {
        "invokedToolName": tool_name,
        "toolDescriptor": descriptor.model_dump(by_alias=True, mode="json"),
        "taskId": getattr(task, "id", None),
        "projectId": getattr(task, "project_id", None),
        "branchId": getattr(task, "branch_id", None),
        "runId": getattr(run, "id", None),
        "runType": getattr(run, "run_type", None),
        "taskTitle": getattr(task, "title", None),
        "taskGoal": getattr(task, "goal", None),
        "currentFocus": getattr(task, "current_focus", None),
        "currentObjective": getattr(task, "current_objective", None),
        "sourceWorkTreeNodeId": _source_work_tree_node_id(root_mount),
        "rootMount": root_mount,
        "currentContext": current_context,
        "activeCapabilities": list(root_mount.get("activeCapabilities") or []),
    }
    handler = _load_tool_callable(descriptor.implementation_ref)
    result = handler(payload)
    return {
        "tool": descriptor.model_dump(by_alias=True, mode="json"),
        "arguments": arguments,
        "result": result if isinstance(result, dict) else {"value": result},
    }


def tool_result_to_message_content(execution: dict[str, Any]) -> str:
    return json.dumps(execution.get("result") or {}, ensure_ascii=False)