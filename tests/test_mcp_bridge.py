from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
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


pytestmark = pytest.mark.slow


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


def test_workspace_python_run_python_uses_temp_script_for_unicode_workspace(tmp_path) -> None:
    workspace = tmp_path / "世界树-workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    original_cwd = os.environ.get("YGGDRASIL_MCP_WORKSPACE")
    os.environ["YGGDRASIL_MCP_WORKSPACE"] = str(workspace)
    try:
        from yggdrasil_sdk.mcp_servers.python_server import _run_python

        result = _run_python(
            {
                "code": "print('你好，世界树')",
                "workingDirectory": ".",
                "timeoutMs": 5000,
            }
        )
    finally:
        if original_cwd is None:
            os.environ.pop("YGGDRASIL_MCP_WORKSPACE", None)
        else:
            os.environ["YGGDRASIL_MCP_WORKSPACE"] = original_cwd

    assert result["isError"] is False
    assert "你好，世界树" in result["structuredContent"]["stdout"]
    assert not any(path.name.startswith("yggdrasil-python-") for path in workspace.iterdir())


def test_workspace_edit_coerces_raw_windows_style_path_arguments() -> None:
    from yggdrasil_sdk.mcp_servers.edit_server import _coerce_arguments

    raw_arguments = {
        "_raw": r'{"path": "C:\skzy\sandbox\note_index.py", "content": "token_re = re.compile(r\"[A-Za-z0-9]+(?:\.\d+)*\")\n", "encoding": "utf-8"}'
    }

    parsed = _coerce_arguments(raw_arguments)

    assert parsed["path"] == r"C:\skzy\sandbox\note_index.py"
    assert parsed["content"] == 'token_re = re.compile(r"[A-Za-z0-9]+(?:\\.\\d+)*")\n'
    assert parsed["encoding"] == "utf-8"


def test_workspace_edit_write_file_accepts_raw_json_with_invalid_backslashes(tmp_path, monkeypatch) -> None:
    from yggdrasil_sdk.mcp_servers.edit_server import _write_file

    workspace = tmp_path / "project"
    workspace.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("YGGDRASIL_MCP_WORKSPACE", str(workspace))
    monkeypatch.setenv("YGGDRASIL_MCP_EDIT_ALLOWED_PATHS", json.dumps(["note_index.py"]))

    result = _write_file(
        {
            "_raw": r'{"path": "note_index.py", "content": "token_re = re.compile(r\"[A-Za-z0-9]+(?:\.\d+)*\")\n", "encoding": "utf-8"}'
        }
    )

    written = (workspace / "note_index.py").read_text(encoding="utf-8")
    assert written == 'token_re = re.compile(r"[A-Za-z0-9]+(?:\\.\\d+)*")\n'
    assert result["structuredContent"]["path"].endswith("note_index.py")


def test_workspace_edit_write_file_accepts_live_style_multiline_raw_payload(tmp_path, monkeypatch) -> None:
    from yggdrasil_sdk.mcp_servers.edit_server import _write_file

    workspace = tmp_path / "project-live"
    workspace.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("YGGDRASIL_MCP_WORKSPACE", str(workspace))
    monkeypatch.setenv("YGGDRASIL_MCP_EDIT_ALLOWED_PATHS", json.dumps(["note_index.py"]))

    live_style_raw = '''{"path": "note_index.py", "content": "#!/usr/bin/env python3
\"\"\"Note Index CLI\"\"\"
token_re = re.compile(r\"[A-Za-z0-9]+(?:\\.\\d+)*\")
", "encoding": "utf-8"}'''

    result = _write_file({"_raw": live_style_raw})

    written = (workspace / "note_index.py").read_text(encoding="utf-8")
    assert written == '#!/usr/bin/env python3\n\"\"\"Note Index CLI\"\"\"\ntoken_re = re.compile(r\"[A-Za-z0-9]+(?:\\.\\d+)*\")\n'
    assert result["structuredContent"]["path"].endswith("note_index.py")


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