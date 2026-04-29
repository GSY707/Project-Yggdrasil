from __future__ import annotations

import atexit
from collections import deque
from datetime import datetime
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time
from typing import Any

from .support import ensure_state_subdir, normalize_excerpt, read_json, resolve_workspace_root, utc_now, write_json


BRIDGE_VERSION = "0.1.0"
BRIDGE_CLIENT_PROTOCOL_VERSION = "2025-03-26"
BRIDGE_MODULE_ID = "mcp-bridge"
BRIDGE_CONFIG_FILE = "config.json"
BRIDGE_SNAPSHOT_FILE = "snapshot.json"
BRIDGE_KNOWN_IMPORTS = {
    "io.github.ChromeDevTools/chrome-devtools-mcp": {
        "id": "chrome-devtools",
        "displayName": "Chrome DevTools MCP",
        "description": "Copy of the locally configured Chrome DevTools MCP server definition.",
        "toolPrefix": "web",
        "enabled": False,
        "keepAlive": True,
    },
    "microsoft/markitdown": {
        "id": "markitdown",
        "displayName": "MarkItDown MCP",
        "description": "Copy of the locally configured MarkItDown MCP server definition.",
        "toolPrefix": "markitdown",
        "enabled": False,
        "keepAlive": False,
    },
}
DEFAULT_SERVER_TIMEOUT_MS = 20000
COMMON_IGNORED_DIRS = {
    ".git",
    ".next",
    ".venv",
    ".yggdrasil",
    "node_modules",
    "dist",
    "build",
    "coverage",
    "__pycache__",
}


def _bridge_state_dir(workspace_root: Path | None = None) -> Path:
    return ensure_state_subdir("mcp-bridge", workspace_root)


def _bridge_config_path(workspace_root: Path | None = None) -> Path:
    return _bridge_state_dir(workspace_root) / BRIDGE_CONFIG_FILE


def _bridge_snapshot_path(workspace_root: Path | None = None) -> Path:
    return _bridge_state_dir(workspace_root) / BRIDGE_SNAPSHOT_FILE


def _project_workspace_default(workspace_root: Path | None = None) -> str:
    return str(resolve_workspace_root(workspace_root))


def _normalize_server_definition(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(payload.get("id") or "").strip(),
        "displayName": str(payload.get("displayName") or payload.get("id") or "Unnamed MCP Server").strip(),
        "description": str(payload.get("description") or "").strip() or None,
        "transport": str(payload.get("transport") or "stdio"),
        "command": str(payload.get("command") or "").strip(),
        "args": [str(item) for item in payload.get("args") or [] if str(item).strip()],
        "env": {
            str(key): str(value)
            for key, value in (payload.get("env") or {}).items()
            if str(key).strip()
        },
        "cwd": str(payload.get("cwd")).strip() if payload.get("cwd") is not None and str(payload.get("cwd")).strip() else None,
        "enabled": bool(payload.get("enabled", True)),
        "keepAlive": bool(payload.get("keepAlive", False)),
        "toolPrefix": str(payload.get("toolPrefix") or payload.get("id") or "mcp").strip(),
        "origin": str(payload.get("origin") or "custom"),
        "sourcePath": str(payload.get("sourcePath")).strip() if payload.get("sourcePath") is not None and str(payload.get("sourcePath")).strip() else None,
        "timeoutMs": int(payload.get("timeoutMs") or DEFAULT_SERVER_TIMEOUT_MS),
    }


def _merge_server_definitions(existing: list[dict[str, Any]], defaults: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def _is_empty_value(value: Any) -> bool:
        return value is None or value == "" or value == [] or value == {}

    merged = {
        item["id"]: _normalize_server_definition(item)
        for item in existing
        if str(item.get("id") or "").strip()
    }
    for item in defaults:
        normalized = _normalize_server_definition(item)
        server_id = normalized["id"]
        if not server_id:
            continue
        if server_id not in merged:
            merged[server_id] = normalized
            continue
        current = merged[server_id]
        for key, value in normalized.items():
            if key in {"enabled", "command", "args", "env", "cwd", "keepAlive", "timeoutMs"}:
                continue
            if _is_empty_value(current.get(key)):
                current[key] = value
        if current.get("sourcePath") is None and normalized.get("sourcePath"):
            current["sourcePath"] = normalized["sourcePath"]
    return [merged[key] for key in sorted(merged)]


def _builtin_server_definitions(workspace_root: Path | None = None) -> list[dict[str, Any]]:
    python_executable = sys.executable
    return [
        {
            "id": "workspace-read",
            "displayName": "Workspace Read MCP",
            "description": "Builtin MCP server for reading files and listing directories in the configured project workspace.",
            "transport": "stdio",
            "command": python_executable,
            "args": ["-m", "yggdrasil_sdk.mcp_servers.read_server"],
            "enabled": True,
            "keepAlive": True,
            "toolPrefix": "read",
            "origin": "builtin",
            "sourcePath": "yggdrasil_sdk.mcp_servers.read_server",
            "timeoutMs": 10000,
        },
        {
            "id": "workspace-edit",
            "displayName": "Workspace Edit MCP",
            "description": "Builtin MCP server for creating files and replacing text in the configured project workspace.",
            "transport": "stdio",
            "command": python_executable,
            "args": ["-m", "yggdrasil_sdk.mcp_servers.edit_server"],
            "enabled": True,
            "keepAlive": True,
            "toolPrefix": "edit",
            "origin": "builtin",
            "sourcePath": "yggdrasil_sdk.mcp_servers.edit_server",
            "timeoutMs": 10000,
        },
        {
            "id": "workspace-search",
            "displayName": "Workspace Search MCP",
            "description": "Builtin MCP server for globbing files and searching text inside the configured project workspace.",
            "transport": "stdio",
            "command": python_executable,
            "args": ["-m", "yggdrasil_sdk.mcp_servers.search_server"],
            "enabled": True,
            "keepAlive": True,
            "toolPrefix": "search",
            "origin": "builtin",
            "sourcePath": "yggdrasil_sdk.mcp_servers.search_server",
            "timeoutMs": 15000,
        },
        {
            "id": "workspace-execute",
            "displayName": "Workspace Execute MCP",
            "description": "Builtin MCP server for running shell commands inside the configured project workspace.",
            "transport": "stdio",
            "command": python_executable,
            "args": ["-m", "yggdrasil_sdk.mcp_servers.execute_server"],
            "enabled": True,
            "keepAlive": True,
            "toolPrefix": "execute",
            "origin": "builtin",
            "sourcePath": "yggdrasil_sdk.mcp_servers.execute_server",
            "timeoutMs": 20000,
        },
        {
            "id": "workspace-python",
            "displayName": "Workspace Python MCP",
            "description": "Builtin MCP server for running Python snippets inside the configured project workspace.",
            "transport": "stdio",
            "command": python_executable,
            "args": ["-m", "yggdrasil_sdk.mcp_servers.python_server"],
            "enabled": True,
            "keepAlive": True,
            "toolPrefix": "python",
            "origin": "builtin",
            "sourcePath": "yggdrasil_sdk.mcp_servers.python_server",
            "timeoutMs": 20000,
        },
    ]


def _user_mcp_config_path() -> Path:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return Path("mcp.json")
    return Path(appdata) / "Code" / "User" / "mcp.json"


def discover_copyable_mcp_servers() -> list[dict[str, Any]]:
    config_path = _user_mcp_config_path()
    payload = read_json(config_path, {"servers": {}})
    servers = payload.get("servers") if isinstance(payload, dict) else {}
    if not isinstance(servers, dict):
        return []

    discovered: list[dict[str, Any]] = []
    for external_name, defaults in BRIDGE_KNOWN_IMPORTS.items():
        raw = servers.get(external_name)
        if not isinstance(raw, dict):
            continue
        command = str(raw.get("command") or "").strip()
        if not command:
            continue
        discovered.append(
            {
                **defaults,
                "transport": str(raw.get("type") or "stdio"),
                "command": command,
                "args": [str(item) for item in raw.get("args") or [] if str(item).strip()],
                "env": {
                    str(key): str(value)
                    for key, value in (raw.get("env") or {}).items()
                    if str(key).strip()
                },
                "cwd": str(raw.get("cwd")).strip() if raw.get("cwd") is not None and str(raw.get("cwd")).strip() else None,
                "origin": "copied-from-user-mcp",
                "sourcePath": str(config_path),
                "timeoutMs": DEFAULT_SERVER_TIMEOUT_MS,
            }
        )
    return [_normalize_server_definition(item) for item in discovered]


def ensure_mcp_bridge_config(workspace_root: Path | None = None) -> dict[str, Any]:
    config_path = _bridge_config_path(workspace_root)
    payload = read_json(config_path, {})
    project_workspace = str(payload.get("projectWorkspace") or _project_workspace_default(workspace_root))
    merged_servers = _merge_server_definitions(
        payload.get("servers") if isinstance(payload.get("servers"), list) else [],
        [*_builtin_server_definitions(workspace_root), *discover_copyable_mcp_servers()],
    )
    config = {
        "projectWorkspace": project_workspace,
        "servers": merged_servers,
        "updatedAt": str(payload.get("updatedAt") or utc_now().isoformat()),
    }
    write_json(config_path, config)
    return config


def _workspace_options(project_workspace: str, workspace_root: Path | None = None) -> list[dict[str, str]]:
    options = [
        {
            "label": "当前仓库根目录",
            "value": _project_workspace_default(workspace_root),
            "source": "workspace-root",
        }
    ]
    if project_workspace and project_workspace != options[0]["value"]:
        options.append(
            {
                "label": "当前 MCP 项目工作区",
                "value": project_workspace,
                "source": "mcp-bridge-config",
            }
        )
    return options


def update_mcp_bridge_workspace(project_workspace: str, workspace_root: Path | None = None) -> dict[str, Any]:
    config = ensure_mcp_bridge_config(workspace_root)
    config["projectWorkspace"] = str(Path(project_workspace).expanduser().resolve())
    config["updatedAt"] = utc_now().isoformat()
    write_json(_bridge_config_path(workspace_root), config)
    close_mcp_bridge_sessions()
    sync_mcp_bridge_servers(workspace_root)
    return config


def upsert_mcp_bridge_server(server_payload: dict[str, Any], workspace_root: Path | None = None) -> dict[str, Any]:
    config = ensure_mcp_bridge_config(workspace_root)
    server = _normalize_server_definition(server_payload)
    if not server["id"]:
        raise ValueError("MCP server id is required.")
    servers = [item for item in config["servers"] if item["id"] != server["id"]]
    servers.append(server)
    config["servers"] = [item for item in sorted(servers, key=lambda item: item["id"])]
    config["updatedAt"] = utc_now().isoformat()
    write_json(_bridge_config_path(workspace_root), config)
    close_mcp_bridge_sessions(server["id"])
    sync_mcp_bridge_servers(workspace_root, server_ids=[server["id"]])
    return config


def set_mcp_bridge_server_enabled(server_id: str, enabled: bool, workspace_root: Path | None = None) -> dict[str, Any]:
    config = ensure_mcp_bridge_config(workspace_root)
    updated = False
    for server in config["servers"]:
        if server["id"] != server_id:
            continue
        server["enabled"] = enabled
        updated = True
        break
    if not updated:
        raise KeyError(server_id)
    config["updatedAt"] = utc_now().isoformat()
    write_json(_bridge_config_path(workspace_root), config)
    if not enabled:
        close_mcp_bridge_sessions(server_id)
    sync_mcp_bridge_servers(workspace_root, server_ids=[server_id])
    return config


def refresh_copyable_mcp_servers(workspace_root: Path | None = None) -> dict[str, Any]:
    config = ensure_mcp_bridge_config(workspace_root)
    config["servers"] = _merge_server_definitions(config["servers"], discover_copyable_mcp_servers())
    config["updatedAt"] = utc_now().isoformat()
    write_json(_bridge_config_path(workspace_root), config)
    sync_mcp_bridge_servers(workspace_root)
    return config


def _substitute_placeholder(value: str, project_workspace: str) -> str:
    return value.replace("${projectWorkspace}", project_workspace)


def _server_process_payload(server: dict[str, Any], project_workspace: str) -> tuple[list[str], dict[str, str], str | None]:
    if server.get("transport") != "stdio":
        raise RuntimeError(f"Unsupported MCP transport: {server.get('transport')}")
    command = _substitute_placeholder(str(server.get("command") or ""), project_workspace)
    if not command:
        raise RuntimeError(f"MCP server {server['id']} does not declare a command.")
    args = [_substitute_placeholder(str(item), project_workspace) for item in server.get("args") or []]
    cwd = server.get("cwd")
    resolved_cwd = _substitute_placeholder(str(cwd), project_workspace) if cwd else project_workspace
    env = dict(os.environ)
    env.update({
        "PYTHONUTF8": "1",
        "YGGDRASIL_MCP_WORKSPACE": project_workspace,
    })
    for key, value in (server.get("env") or {}).items():
        env[str(key)] = _substitute_placeholder(str(value), project_workspace)
    return [command, *args], env, resolved_cwd


class _StdioMCPClient:
    def __init__(self, server: dict[str, Any], project_workspace: str) -> None:
        self.server = server
        self.project_workspace = project_workspace
        command, env, cwd = _server_process_payload(server, project_workspace)
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            env=env,
        )
        self._lock = threading.RLock()
        self._queue: queue.Queue[dict[str, Any]] = queue.Queue()
        self._stderr: deque[str] = deque(maxlen=80)
        self._next_id = 0
        self._initialized = False
        self._reader = threading.Thread(target=self._reader_loop, daemon=True)
        self._stderr_reader = threading.Thread(target=self._stderr_loop, daemon=True)
        self._reader.start()
        self._stderr_reader.start()

    def _stderr_loop(self) -> None:
        if self.process.stderr is None:
            return
        try:
            while True:
                line = self.process.stderr.readline()
                if not line:
                    return
                self._stderr.append(line.decode("utf-8", errors="replace").rstrip())
        except Exception:
            return

    def _reader_loop(self) -> None:
        if self.process.stdout is None:
            return
        try:
            while True:
                headers: dict[str, str] = {}
                while True:
                    line = self.process.stdout.readline()
                    if not line:
                        return
                    if line in {b"\r\n", b"\n"}:
                        break
                    decoded = line.decode("utf-8", errors="replace")
                    name, _, value = decoded.partition(":")
                    if _:
                        headers[name.lower().strip()] = value.strip()
                content_length = int(headers.get("content-length", "0") or "0")
                if content_length <= 0:
                    continue
                payload = self.process.stdout.read(content_length)
                if not payload:
                    return
                self._queue.put(json.loads(payload.decode("utf-8")))
        except Exception as exc:
            self._queue.put({"_bridgeReaderError": str(exc)})

    def _write_message(self, payload: dict[str, Any]) -> None:
        if self.process.stdin is None:
            raise RuntimeError("MCP stdin is not available.")
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
        self.process.stdin.write(header)
        self.process.stdin.write(body)
        self.process.stdin.flush()

    def _request(self, method: str, params: dict[str, Any] | None = None, *, timeout_ms: int | None = None) -> dict[str, Any]:
        timeout = (timeout_ms or int(self.server.get("timeoutMs") or DEFAULT_SERVER_TIMEOUT_MS)) / 1000.0
        with self._lock:
            self._next_id += 1
            request_id = self._next_id
            self._write_message(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "method": method,
                    "params": params or {},
                }
            )
            deadline = time.monotonic() + timeout
            while True:
                remaining = max(deadline - time.monotonic(), 0.0)
                if remaining <= 0:
                    break
                try:
                    message = self._queue.get(timeout=remaining)
                except queue.Empty:
                    break
                if message.get("_bridgeReaderError"):
                    raise RuntimeError(str(message["_bridgeReaderError"]))
                if message.get("id") != request_id:
                    continue
                if message.get("error"):
                    error = message["error"]
                    detail = error.get("message") if isinstance(error, dict) else str(error)
                    raise RuntimeError(detail)
                result = message.get("result")
                return result if isinstance(result, dict) else {"value": result}
            stderr_tail = "\n".join(self._stderr)
            raise TimeoutError(
                f"Timed out waiting for MCP response from {self.server['id']}. {stderr_tail}".strip()
            )

    def _notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        with self._lock:
            self._write_message(
                {
                    "jsonrpc": "2.0",
                    "method": method,
                    "params": params or {},
                }
            )

    def initialize(self) -> dict[str, Any]:
        if self._initialized:
            return {}
        result = self._request(
            "initialize",
            {
                "protocolVersion": BRIDGE_CLIENT_PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "clientInfo": {"name": "project-yggdrasil-mcp-bridge", "version": BRIDGE_VERSION},
            },
        )
        self._notify("notifications/initialized", {})
        self._initialized = True
        return result

    def list_tools(self) -> dict[str, Any]:
        self.initialize()
        return self._request("tools/list", {})

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self.initialize()
        return self._request("tools/call", {"name": tool_name, "arguments": arguments})

    def close(self) -> None:
        if self.process.poll() is not None:
            return
        try:
            self.process.terminate()
            self.process.wait(timeout=2)
        except Exception:
            self.process.kill()
        finally:
            if self.process.stdin is not None:
                self.process.stdin.close()
            if self.process.stdout is not None:
                self.process.stdout.close()
            if self.process.stderr is not None:
                self.process.stderr.close()


_SESSION_LOCK = threading.RLock()
_SESSION_POOL: dict[str, _StdioMCPClient] = {}


def close_mcp_bridge_sessions(server_id: str | None = None) -> None:
    with _SESSION_LOCK:
        if server_id is not None:
            session = _SESSION_POOL.pop(server_id, None)
            if session is not None:
                session.close()
            return
        sessions = list(_SESSION_POOL.values())
        _SESSION_POOL.clear()
    for session in sessions:
        session.close()


atexit.register(close_mcp_bridge_sessions)


def _server_lookup(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        server["id"]: server
        for server in config.get("servers") or []
        if str(server.get("id") or "").strip()
    }


def _client_for_server(server: dict[str, Any], project_workspace: str) -> _StdioMCPClient:
    if not server.get("keepAlive"):
        return _StdioMCPClient(server, project_workspace)
    with _SESSION_LOCK:
        existing = _SESSION_POOL.get(server["id"])
        if existing is not None and existing.process.poll() is None:
            return existing
        if existing is not None:
            existing.close()
        client = _StdioMCPClient(server, project_workspace)
        _SESSION_POOL[server["id"]] = client
        return client


def _with_server_client(server: dict[str, Any], project_workspace: str, callback):
    client = _client_for_server(server, project_workspace)
    keep_alive = bool(server.get("keepAlive"))
    try:
        return callback(client)
    finally:
        if not keep_alive:
            client.close()


def _sanitize_tool_segment(value: str) -> str:
    sanitized = []
    for char in value.lower():
        if char.isalnum():
            sanitized.append(char)
            continue
        sanitized.append("_")
    compact = "".join(sanitized).strip("_")
    return compact or "tool"


def _normalize_tool_schema(schema: Any) -> dict[str, Any]:
    if isinstance(schema, dict):
        normalized = dict(schema)
    else:
        normalized = {}
    normalized.setdefault("type", "object")
    normalized.setdefault("properties", {})
    normalized.setdefault("additionalProperties", False)
    return normalized


def _normalize_discovered_tool(server: dict[str, Any], tool: dict[str, Any]) -> dict[str, Any]:
    name = str(tool.get("name") or "").strip()
    if not name:
        raise ValueError(f"MCP server {server['id']} returned a tool without a name.")
    exposed_name = f"mcp.{_sanitize_tool_segment(str(server.get('toolPrefix') or server['id']))}.{_sanitize_tool_segment(name)}"
    return {
        "serverId": server["id"],
        "serverDisplayName": server.get("displayName") or server["id"],
        "remoteToolName": name,
        "exposedName": exposed_name,
        "description": str(tool.get("description") or "").strip() or None,
        "inputSchema": _normalize_tool_schema(tool.get("inputSchema") or tool.get("parameters")),
    }


def sync_mcp_bridge_servers(
    workspace_root: Path | None = None,
    *,
    server_ids: list[str] | None = None,
) -> dict[str, Any]:
    config = ensure_mcp_bridge_config(workspace_root)
    project_workspace = str(config["projectWorkspace"])
    target_ids = set(server_ids or [])
    snapshot_servers: list[dict[str, Any]] = []
    previous_snapshot = read_json(_bridge_snapshot_path(workspace_root), {"servers": []})
    previous_by_id = {
        item["id"]: item
        for item in previous_snapshot.get("servers") or []
        if isinstance(item, dict) and str(item.get("id") or "").strip()
    }

    for server in config["servers"]:
        if target_ids and server["id"] not in target_ids:
            preserved = previous_by_id.get(server["id"])
            if preserved is not None:
                snapshot_servers.append(preserved)
            continue
        if not server.get("enabled"):
            snapshot_servers.append(
                {
                    "id": server["id"],
                    "displayName": server.get("displayName") or server["id"],
                    "status": "disabled",
                    "error": None,
                    "tools": [],
                    "toolCount": 0,
                    "lastSyncedAt": utc_now().isoformat(),
                    "sourcePath": server.get("sourcePath"),
                    "origin": server.get("origin"),
                }
            )
            continue

        try:
            result = _with_server_client(server, project_workspace, lambda client: client.list_tools())
            raw_tools = result.get("tools") if isinstance(result.get("tools"), list) else []
            normalized_tools = [_normalize_discovered_tool(server, tool) for tool in raw_tools if isinstance(tool, dict)]
            snapshot_servers.append(
                {
                    "id": server["id"],
                    "displayName": server.get("displayName") or server["id"],
                    "status": "ready",
                    "error": None,
                    "tools": normalized_tools,
                    "toolCount": len(normalized_tools),
                    "serverInfo": result.get("serverInfo") if isinstance(result.get("serverInfo"), dict) else None,
                    "lastSyncedAt": utc_now().isoformat(),
                    "sourcePath": server.get("sourcePath"),
                    "origin": server.get("origin"),
                }
            )
        except Exception as exc:
            snapshot_servers.append(
                {
                    "id": server["id"],
                    "displayName": server.get("displayName") or server["id"],
                    "status": "error",
                    "error": normalize_excerpt(str(exc), 400),
                    "tools": [],
                    "toolCount": 0,
                    "lastSyncedAt": utc_now().isoformat(),
                    "sourcePath": server.get("sourcePath"),
                    "origin": server.get("origin"),
                }
            )

    snapshot = {
        "generatedAt": utc_now().isoformat(),
        "servers": snapshot_servers,
        "toolCount": sum(int(item.get("toolCount") or 0) for item in snapshot_servers),
    }
    write_json(_bridge_snapshot_path(workspace_root), snapshot)
    return snapshot


def load_mcp_bridge_snapshot(workspace_root: Path | None = None, *, refresh_if_missing: bool = True) -> dict[str, Any]:
    snapshot = read_json(_bridge_snapshot_path(workspace_root), {})
    if snapshot:
        return snapshot
    if not refresh_if_missing:
        return {"generatedAt": utc_now().isoformat(), "servers": [], "toolCount": 0}
    return sync_mcp_bridge_servers(workspace_root)


def list_mcp_bridge_tool_bindings(workspace_root: Path | None = None, *, refresh_if_missing: bool = False) -> list[dict[str, Any]]:
    snapshot = load_mcp_bridge_snapshot(workspace_root, refresh_if_missing=refresh_if_missing)
    bindings: list[dict[str, Any]] = []
    for server in snapshot.get("servers") or []:
        if str(server.get("status") or "") != "ready":
            continue
        bindings.extend(tool for tool in server.get("tools") or [] if isinstance(tool, dict))
    return bindings


def mcp_bridge_tool_descriptors(workspace_root: Path | None = None, *, refresh_if_missing: bool = False) -> list[dict[str, Any]]:
    bindings = list_mcp_bridge_tool_bindings(workspace_root, refresh_if_missing=refresh_if_missing)
    descriptors: list[dict[str, Any]] = []
    for binding in bindings:
        descriptors.append(
            {
                "name": binding["exposedName"],
                "moduleId": BRIDGE_MODULE_ID,
                "version": BRIDGE_VERSION,
                "displayName": f"{binding['serverDisplayName']} / {binding['remoteToolName']}",
                "description": binding.get("description") or f"MCP bridge tool from {binding['serverDisplayName']}",
                "schemaRef": "docs/specs/agent-runtime-protocol-v0.1.md",
                "executionMode": "sync",
                "timeoutMs": DEFAULT_SERVER_TIMEOUT_MS,
                "permissionRequired": ["tool.mcp.invoke"],
                "inputSchema": _normalize_tool_schema(binding.get("inputSchema")),
                "implementationRef": "yggdrasil_sdk.mcp_bridge_module:invoke_mcp_tool",
            }
        )
    return descriptors


def _tool_binding_by_name(exposed_name: str, workspace_root: Path | None = None, *, refresh_on_miss: bool = False) -> dict[str, Any]:
    for binding in list_mcp_bridge_tool_bindings(workspace_root, refresh_if_missing=False):
        if binding.get("exposedName") == exposed_name:
            return binding
    if not refresh_on_miss:
        raise KeyError(exposed_name)
    snapshot = sync_mcp_bridge_servers(workspace_root)
    for server in snapshot.get("servers") or []:
        for binding in server.get("tools") or []:
            if binding.get("exposedName") == exposed_name:
                return binding
    raise KeyError(exposed_name)


def _normalize_mcp_tool_call_result(result: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {"value": result}
    if isinstance(result.get("structuredContent"), dict):
        normalized = dict(result["structuredContent"])
    else:
        normalized = {}
    content_items = result.get("content") if isinstance(result.get("content"), list) else []
    text_parts = [
        str(item.get("text"))
        for item in content_items
        if isinstance(item, dict) and item.get("type") == "text" and item.get("text") is not None
    ]
    if text_parts:
        normalized.setdefault("text", "\n".join(text_parts))
    if content_items:
        normalized.setdefault("contentItems", content_items)
    if result.get("isError") is not None:
        normalized.setdefault("isError", bool(result.get("isError")))
    return normalized or {"raw": result}


def execute_mcp_bridge_tool(
    exposed_name: str,
    arguments: dict[str, Any],
    workspace_root: Path | None = None,
    *,
    refresh_on_miss: bool = False,
) -> dict[str, Any]:
    binding = _tool_binding_by_name(exposed_name, workspace_root, refresh_on_miss=refresh_on_miss)
    config = ensure_mcp_bridge_config(workspace_root)
    servers = _server_lookup(config)
    server = servers.get(binding["serverId"])
    if server is None:
        raise KeyError(binding["serverId"])
    if not server.get("enabled"):
        raise RuntimeError(f"MCP server {binding['serverId']} is disabled.")
    project_workspace = str(config["projectWorkspace"])
    raw_result = _with_server_client(
        server,
        project_workspace,
        lambda client: client.call_tool(binding["remoteToolName"], dict(arguments or {})),
    )
    return {
        "status": "ok",
        "serverId": binding["serverId"],
        "serverDisplayName": binding["serverDisplayName"],
        "remoteToolName": binding["remoteToolName"],
        "exposedName": binding["exposedName"],
        "result": _normalize_mcp_tool_call_result(raw_result),
    }


def mcp_bridge_overview(workspace_root: Path | None = None) -> dict[str, Any]:
    config = ensure_mcp_bridge_config(workspace_root)
    snapshot = load_mcp_bridge_snapshot(workspace_root, refresh_if_missing=False)
    tools: list[dict[str, Any]] = []
    for server in snapshot.get("servers") or []:
        tools.extend(tool for tool in server.get("tools") or [] if isinstance(tool, dict))
    return {
        "generatedAt": snapshot.get("generatedAt") or utc_now().isoformat(),
        "projectWorkspace": config["projectWorkspace"],
        "workspaceOptions": _workspace_options(config["projectWorkspace"], workspace_root),
        "servers": config["servers"],
        "syncedServers": snapshot.get("servers") or [],
        "tools": tools,
        "availableImports": discover_copyable_mcp_servers(),
    }