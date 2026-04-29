from __future__ import annotations

from pathlib import Path

from .contracts import EventEnvelope, EventHandlingResult, ToolDescriptor
from .mcp_bridge import BRIDGE_MODULE_ID, ensure_mcp_bridge_config, execute_mcp_bridge_tool, load_mcp_bridge_snapshot, mcp_bridge_tool_descriptors, sync_mcp_bridge_servers
from .module import BaseModulePlugin, HookRegistration
from .hooks import HookNames
from .support import resolve_workspace_root


class MCPBridgeModule(BaseModulePlugin):
    module_id = BRIDGE_MODULE_ID

    def manifest_path(self) -> Path:
        return resolve_workspace_root() / "modules" / BRIDGE_MODULE_ID / "yggdrasil.module.yaml"

    def register_hooks(self) -> tuple[HookRegistration, ...]:
        return (
            HookRegistration(name=HookNames.MODULE_ENABLE_PREFLIGHT, handler=self.enable_preflight),
            HookRegistration(name=HookNames.MODULE_HEALTH_REPORT, handler=self.report_health),
            HookRegistration(name=HookNames.AGENT_TOOLS_REGISTER, handler=self.register_tools_hook),
        )

    def register_tools(self) -> tuple[dict[str, object], ...]:
        return tuple(mcp_bridge_tool_descriptors(refresh_if_missing=True))

    def register_tools_hook(self, payload: dict[str, object]) -> dict[str, object]:
        return {
            "tools": list(self.register_tools()),
            "toolCount": len(self.register_tools()),
            "moduleId": self.module_id,
        }

    def enable_preflight(self, payload: dict[str, object]) -> dict[str, object]:
        ensure_mcp_bridge_config()
        snapshot = sync_mcp_bridge_servers()
        ready_servers = [server for server in snapshot.get("servers") or [] if server.get("status") == "ready"]
        return {
            "status": "ok",
            "summary": f"MCP Bridge is ready with {len(ready_servers)} synced server(s).",
        }

    def report_health(self, payload: dict[str, object]) -> dict[str, object]:
        ensure_mcp_bridge_config()
        snapshot = load_mcp_bridge_snapshot(refresh_if_missing=False)
        healthy_servers = [server for server in snapshot.get("servers") or [] if server.get("status") == "ready"]
        failing_servers = [server for server in snapshot.get("servers") or [] if server.get("status") == "error"]
        summary = f"MCP Bridge exposes {sum(int(server.get('toolCount') or 0) for server in healthy_servers)} tool(s) from {len(healthy_servers)} ready server(s)."
        if failing_servers:
            summary += f" {len(failing_servers)} server(s) currently report errors."
        return {
            "status": "degraded" if failing_servers else "healthy",
            "summary": summary,
            "details": {
                "readyServers": [server.get("id") for server in healthy_servers],
                "failingServers": [server.get("id") for server in failing_servers],
            },
        }

    def handle_event(self, event: EventEnvelope) -> EventHandlingResult:
        return EventHandlingResult(status="ignored", handled=False, summary=f"{self.module_id} ignored {event.event_type}.")


def invoke_mcp_tool(payload: dict[str, object]) -> dict[str, object]:
    execution_context = payload.get("executionContext") if isinstance(payload.get("executionContext"), dict) else {}
    invoked_tool_name = str(execution_context.get("invokedToolName") or "").strip()
    if not invoked_tool_name:
        raise KeyError("executionContext.invokedToolName")
    arguments = {key: value for key, value in payload.items() if key != "executionContext"}
    return execute_mcp_bridge_tool(invoked_tool_name, arguments)


plugin = MCPBridgeModule()