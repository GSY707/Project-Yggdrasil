from __future__ import annotations

from pathlib import Path
from typing import Any

from yggdrasil_sdk.contracts import ToolDescriptor
from yggdrasil_sdk.hooks import HookNames
from yggdrasil_sdk.module import BaseModulePlugin, HookRegistration
from yggdrasil_sdk.persistence import get_persistence_runtime
from yggdrasil_sdk.persistence.constants import DEFAULT_BRANCH_ID
from yggdrasil_sdk.persistence.repositories import NodeRepository, WorkspaceBootstrapRepository
from yggdrasil_sdk.support import normalize_excerpt


def _organizer_score(node: dict[str, Any]) -> float:
    return (
        float(node.get("importance", 0.5)) * 0.45
        + float(node.get("stability", 0.5)) * 0.2
        + float(node.get("accessScore", 0.0)) * 0.15
        + float(node.get("feedforwardScore", 0.0)) * 0.1
        + min(float(node.get("edgeCount", 0)) / 10.0, 0.1)
    )


class MemoryOrganizerModule(BaseModulePlugin):
    module_id = "memory-organizer"

    def manifest_path(self) -> Path:
        return Path(__file__).resolve().parents[2] / "yggdrasil.module.yaml"

    def register_hooks(self) -> tuple[HookRegistration, ...]:
        return (
            HookRegistration(name=HookNames.MODULE_ENABLE_PREFLIGHT, handler=self.enable_preflight),
            HookRegistration(name=HookNames.MODULE_HEALTH_REPORT, handler=self.report_health),
            HookRegistration(name=HookNames.AGENT_TOOLS_REGISTER, handler=self.register_tools_hook),
        )

    def register_tools(self) -> tuple[dict[str, object], ...]:
        tools = (
            ToolDescriptor(
                name="memory_organizer.apply_soft_forgetting",
                moduleId=self.module_id,
                version="0.1.0",
                displayName="Apply Soft Forgetting",
                description="Compress and down-rank low-value memory nodes without deleting them.",
                schemaRef="docs/specs/memory-domain-data-spec-v0.1.md",
                executionMode="sync",
                timeoutMs=5000,
                permissionRequired=["node.read", "node.write"],
                inputSchema={
                    "type": "object",
                    "properties": {
                        "branchId": {"type": "string"},
                        "targetCount": {"type": "integer", "minimum": 1, "maximum": 20},
                        "dryRun": {"type": "boolean"},
                    },
                    "additionalProperties": False,
                },
                implementationRef="yggdrasil_memory_organizer.plugin:apply_soft_forgetting_tool",
            ),
        )
        return tuple(tool.model_dump(by_alias=True) for tool in tools)

    def register_tools_hook(self, payload: dict[str, object]) -> dict[str, object]:
        return {
            "tools": list(self.register_tools()),
            "toolCount": len(self.register_tools()),
            "moduleId": self.module_id,
        }

    def enable_preflight(self, payload: dict[str, object]) -> dict[str, object]:
        return {"status": "ok", "summary": "Memory Organizer preflight passed."}

    def report_health(self, payload: dict[str, object]) -> dict[str, object]:
        return {
            "status": "healthy",
            "summary": "Memory Organizer is ready to govern low-value nodes with soft forgetting.",
        }

    def apply_soft_forgetting(self, payload: dict[str, object]) -> dict[str, object]:
        execution_context = payload.get("executionContext") if isinstance(payload.get("executionContext"), dict) else {}
        branch_id = str(payload.get("branchId") or execution_context.get("branchId") or DEFAULT_BRANCH_ID)
        dry_run = bool(payload.get("dryRun", False))
        target_count = int(payload.get("targetCount") or 4)

        runtime = get_persistence_runtime()
        with runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            repository = NodeRepository(session)
            candidates = [
                node.model_dump(by_alias=True, mode="json")
                for node in repository.list_nodes(branch_id=branch_id, limit=300)
                if node.node_type != "root"
            ]
            ranked = sorted(candidates, key=_organizer_score)
            selected = ranked[:target_count]
            if dry_run:
                return {
                    "status": "preview",
                    "branchId": branch_id,
                    "candidates": [
                        {
                            "nodeId": node["id"],
                            "score": round(_organizer_score(node), 4),
                            "title": node["title"],
                        }
                        for node in selected
                    ],
                }

            adjusted_nodes: list[dict[str, Any]] = []
            for node in selected:
                compressed_content = normalize_excerpt(str(node.get("content") or ""), 140)
                version = repository.append_version(
                    node["id"],
                    {
                        "content": compressed_content,
                        "stability": round(max(0.1, float(node.get("stability", 0.5)) * 0.9), 3),
                        "forgetRate": round(min(1.0, float(node.get("forgetRate", 0.2)) + 0.15), 3),
                        "accessScore": round(max(0.0, float(node.get("accessScore", 0.0)) * 0.6), 3),
                        "floatScore": round(min(1.0, float(node.get("floatScore", 0.3)) + 0.2), 3),
                        "changeReason": "soft-forgetting-pass",
                        "updatedBy": {"type": "module", "id": self.module_id},
                    },
                )
                adjusted_nodes.append(
                    {
                        "nodeId": node["id"],
                        "title": node["title"],
                        "newVersionId": version.id,
                        "compressedContent": compressed_content,
                    }
                )
        return {
            "status": "organized",
            "branchId": branch_id,
            "adjustedNodes": adjusted_nodes,
            "summary": f"Applied soft forgetting to {len(adjusted_nodes)} nodes in branch {branch_id}.",
        }


plugin = MemoryOrganizerModule()


def apply_soft_forgetting_tool(payload: dict[str, object]) -> dict[str, object]:
    return plugin.apply_soft_forgetting(payload)