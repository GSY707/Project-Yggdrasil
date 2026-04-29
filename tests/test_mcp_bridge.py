from __future__ import annotations

import json
from pathlib import Path

from yggdrasil_agent_runtime.runtime import build_root_mount_package
from yggdrasil_sdk import (
    TaskRepository,
    ensure_mcp_bridge_config,
    execute_registered_tool,
    get_persistence_runtime,
    sync_mcp_bridge_servers,
    update_mcp_bridge_workspace,
)
from yggdrasil_sdk.persistence.repositories import WorkspaceBootstrapRepository

import yggdrasil_sdk.mcp_bridge as mcp_bridge_module


def _seed_task(task_id: str, *, app_id: str = "yggdrasil.app.software-factory"):
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        task = task_repository.create_task(
            {
                "id": task_id,
                "appId": app_id,
                "title": "MCP bridge 测试任务",
                "goal": "验证 bridge 可以把 MCP 工具接入正式运行时。",
                "status": "running",
            }
        )
        run = task_repository.create_agent_run(
            task.id,
            {
                "id": f"run_{task_id}",
                "status": "running",
                "selectedModel": "gpt-5.4",
                "selectedProvider": "copilot",
            },
        )
        return task, run


def test_mcp_bridge_copies_user_mcp_server_definitions(tmp_path, monkeypatch) -> None:
    appdata_root = tmp_path / "AppData"
    user_dir = appdata_root / "Code" / "User"
    user_dir.mkdir(parents=True, exist_ok=True)
    (user_dir / "mcp.json").write_text(
        json.dumps(
            {
                "servers": {
                    "io.github.ChromeDevTools/chrome-devtools-mcp": {
                        "type": "stdio",
                        "command": "npx",
                        "args": ["chrome-devtools-mcp@0.18.1"],
                    },
                    "microsoft/markitdown": {
                        "type": "stdio",
                        "command": "uvx",
                        "args": ["markitdown-mcp@0.0.1a4"],
                    },
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("APPDATA", str(appdata_root))

    config = ensure_mcp_bridge_config()
    servers_by_id = {server["id"]: server for server in config["servers"]}

    assert {"workspace-read", "workspace-edit", "workspace-search", "workspace-execute", "workspace-python"} <= set(servers_by_id)
    assert servers_by_id["chrome-devtools"]["origin"] == "copied-from-user-mcp"
    assert servers_by_id["markitdown"]["origin"] == "copied-from-user-mcp"


def test_mcp_bridge_syncs_builtin_servers_and_executes_tools(tmp_path) -> None:
    project_workspace = tmp_path / "project"
    project_workspace.mkdir(parents=True, exist_ok=True)
    sample_file = project_workspace / "notes.txt"
    sample_file.write_text("alpha\nbeta\n", encoding="utf-8")

    update_mcp_bridge_workspace(str(project_workspace))
    snapshot = sync_mcp_bridge_servers()
    exposed_tools = {
        tool["exposedName"]
        for server in snapshot["servers"]
        if server.get("status") == "ready"
        for tool in server.get("tools") or []
    }

    assert "mcp.read.read_file" in exposed_tools
    assert "mcp.python.inspect_environment" in exposed_tools

    task, run = _seed_task("task_mcp_bridge")
    root_mount = build_root_mount_package(task.id)
    execution = execute_registered_tool(
        "mcp.read.read_file",
        {"path": "notes.txt"},
        task=task,
        run=run,
        root_mount=root_mount,
        current_context=[],
    )

    assert "mcp-bridge" in root_mount["activeCapabilities"]
    assert execution["result"]["serverId"] == "workspace-read"
    assert execution["result"]["result"]["content"] == "alpha\nbeta"
    assert execution["result"]["result"]["path"] == str(sample_file.resolve())


def test_mcp_bridge_builtin_servers_default_to_keepalive() -> None:
    config = ensure_mcp_bridge_config()
    builtin_servers = {
        server["id"]: server
        for server in config["servers"]
        if server["id"].startswith("workspace-")
    }

    assert builtin_servers
    assert all(server["keepAlive"] is True for server in builtin_servers.values())


def test_mcp_bridge_missing_binding_does_not_force_sync(monkeypatch) -> None:
    sync_calls = {"count": 0}

    def never_sync(*args, **kwargs):
        sync_calls["count"] += 1
        raise AssertionError("sync_mcp_bridge_servers should not be called from tool lookup hot path")

    monkeypatch.setattr(mcp_bridge_module, "sync_mcp_bridge_servers", never_sync)

    try:
        mcp_bridge_module._tool_binding_by_name("mcp.read.missing_tool")
    except KeyError:
        pass
    else:
        raise AssertionError("Expected KeyError for a missing MCP tool binding")

    assert sync_calls["count"] == 0