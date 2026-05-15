from __future__ import annotations

from types import SimpleNamespace

import pytest

from yggdrasil_sdk.mcp_servers.execute_server import _run_command
from yggdrasil_sdk.mcp_servers.permission_layer import assert_command_allowed, command_requests_network


def test_command_requests_network_matches_explicit_network_commands() -> None:
    assert command_requests_network("curl https://example.com") is True
    assert command_requests_network("Invoke-WebRequest https://example.com") is True
    assert command_requests_network("python -c \"print(1)\"") is False


def test_assert_command_allowed_blocks_network_commands_by_default(monkeypatch) -> None:
    monkeypatch.delenv("YGGDRASIL_MCP_ALLOW_NETWORK", raising=False)

    with pytest.raises(PermissionError, match="Network commands are disabled"):
        assert_command_allowed("curl https://example.com")


def test_run_command_allows_explicit_network_access_when_enabled(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("YGGDRASIL_MCP_WORKSPACE", str(tmp_path))
    monkeypatch.setenv("YGGDRASIL_MCP_ALLOW_NETWORK", "1")

    captured: dict[str, object] = {}

    def _fake_run(command, **kwargs):
        captured["command"] = command
        captured["cwd"] = kwargs.get("cwd")
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("yggdrasil_sdk.mcp_servers.execute_server.subprocess.run", _fake_run)

    result = _run_command({"command": "curl https://example.com", "timeoutMs": 1000})

    assert captured["command"] == "curl https://example.com"
    assert str(captured["cwd"]) == str(tmp_path.resolve())
    assert result["content"][0]["text"] == "Command finished with exit code 0."