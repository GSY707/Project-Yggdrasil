from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any

from .base import SimpleMCPServer, structured_tool_result


_configured_python_executable: Path | None = None


def _workspace_root() -> Path:
    return Path(os.environ.get("YGGDRASIL_MCP_WORKSPACE") or Path.cwd()).resolve()


def _resolve_cwd(raw_path: str | None) -> Path:
    workspace_root = _workspace_root()
    if not raw_path:
        return workspace_root
    candidate = Path(raw_path).expanduser()
    resolved = candidate.resolve() if candidate.is_absolute() else (workspace_root / candidate).resolve()
    try:
        resolved.relative_to(workspace_root)
    except ValueError as exc:
        raise ValueError("workingDirectory escapes the configured project workspace.") from exc
    return resolved


def _resource_workspace(raw_path: str | None) -> Path:
    if not raw_path:
        return _workspace_root()
    return _resolve_cwd(raw_path)


def _discover_workspace_python(workspace: Path) -> Path:
    candidates = [
        workspace / ".venv" / "Scripts" / "python.exe",
        workspace / "venv" / "Scripts" / "python.exe",
        workspace / ".venv" / "bin" / "python",
        workspace / "venv" / "bin" / "python",
    ]
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate.resolve()
    return Path(sys.executable).resolve()


def _selected_python_executable(resource_path: str | None = None) -> Path:
    global _configured_python_executable
    if _configured_python_executable is not None and _configured_python_executable.exists():
        return _configured_python_executable
    workspace = _resource_workspace(resource_path)
    return _discover_workspace_python(workspace)


def _run_python_command(
    python_executable: Path,
    args: list[str],
    *,
    cwd: Path,
    timeout_ms: int = 20000,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(python_executable), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=max(int(timeout_ms), 1) / 1000.0,
        check=False,
    )


def _configure_python_environment(arguments: dict[str, Any]) -> dict[str, Any]:
    global _configured_python_executable
    resource_path = str(arguments.get("resourcePath") or "").strip() or None
    workspace = _resource_workspace(resource_path)
    requested_python = str(arguments.get("pythonExecutable") or "").strip()

    if requested_python:
        candidate = Path(requested_python).expanduser()
        resolved = candidate.resolve() if candidate.is_absolute() else (workspace / candidate).resolve()
        if not resolved.exists() or not resolved.is_file():
            raise FileNotFoundError(f"pythonExecutable not found: {resolved}")
        selected = resolved
        source = "explicit"
    else:
        selected = _discover_workspace_python(workspace)
        source = "workspace-auto"

    _configured_python_executable = selected
    return structured_tool_result(
        {
            "status": "ok",
            "resourcePath": str(workspace),
            "pythonExecutable": str(selected),
            "selectionSource": source,
        },
        text=f"Configured Python environment: {selected}",
    )


def _get_python_executable_details(arguments: dict[str, Any]) -> dict[str, Any]:
    resource_path = str(arguments.get("resourcePath") or "").strip() or None
    workspace = _resource_workspace(resource_path)
    python_executable = _selected_python_executable(resource_path)
    return structured_tool_result(
        {
            "pythonExecutable": str(python_executable),
            "command": [str(python_executable)],
            "resourcePath": str(workspace),
            "configured": _configured_python_executable is not None,
        },
        text=f"Python executable: {python_executable}",
    )


def _get_python_environment_details(arguments: dict[str, Any]) -> dict[str, Any]:
    resource_path = str(arguments.get("resourcePath") or "").strip() or None
    workspace = _resource_workspace(resource_path)
    python_executable = _selected_python_executable(resource_path)

    version_run = _run_python_command(python_executable, ["--version"], cwd=workspace, timeout_ms=int(arguments.get("timeoutMs") or 10000))
    pip_list_run = _run_python_command(
        python_executable,
        ["-m", "pip", "list", "--format", "json"],
        cwd=workspace,
        timeout_ms=int(arguments.get("timeoutMs") or 20000),
    )

    packages: list[dict[str, str]] = []
    pip_error = None
    if pip_list_run.returncode == 0:
        try:
            parsed = json.loads(pip_list_run.stdout or "[]")
            if isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict):
                        packages.append(
                            {
                                "name": str(item.get("name") or ""),
                                "version": str(item.get("version") or ""),
                            }
                        )
        except Exception as exc:  # noqa: BLE001
            pip_error = str(exc)
    else:
        pip_error = (pip_list_run.stderr or pip_list_run.stdout or "pip list failed").strip()

    env_type = "global"
    executable_str = str(python_executable).replace("\\", "/").lower()
    if "/.venv/" in executable_str or "/venv/" in executable_str:
        env_type = "venv"

    return structured_tool_result(
        {
            "environmentType": env_type,
            "pythonExecutable": str(python_executable),
            "pythonVersion": (version_run.stdout or version_run.stderr).strip(),
            "resourcePath": str(workspace),
            "packages": packages,
            "packageCount": len(packages),
            "packageListError": pip_error,
        },
        text=f"Python environment details collected for {python_executable}",
        is_error=version_run.returncode != 0,
    )


def _install_python_packages(arguments: dict[str, Any]) -> dict[str, Any]:
    resource_path = str(arguments.get("resourcePath") or "").strip() or None
    workspace = _resource_workspace(resource_path)
    python_executable = _selected_python_executable(resource_path)

    package_list_raw = arguments.get("packageList")
    if isinstance(package_list_raw, list):
        packages = [str(item).strip() for item in package_list_raw if str(item).strip()]
    elif isinstance(package_list_raw, str):
        packages = [segment.strip() for segment in package_list_raw.split(",") if segment.strip()]
    else:
        packages = []
    if not packages:
        raise ValueError("packageList is required")

    install_run = _run_python_command(
        python_executable,
        ["-m", "pip", "install", *packages],
        cwd=workspace,
        timeout_ms=int(arguments.get("timeoutMs") or 600000),
    )

    return structured_tool_result(
        {
            "pythonExecutable": str(python_executable),
            "resourcePath": str(workspace),
            "packageList": packages,
            "exitCode": install_run.returncode,
            "stdout": install_run.stdout,
            "stderr": install_run.stderr,
        },
        text=f"pip install finished with exit code {install_run.returncode}",
        is_error=install_run.returncode != 0,
    )


def _inspect_environment(arguments: dict[str, Any]) -> dict[str, Any]:
    cwd = _resolve_cwd(arguments.get("workingDirectory"))
    return structured_tool_result(
        {
            "pythonExecutable": sys.executable,
            "version": sys.version,
            "workingDirectory": str(cwd),
        },
        text=f"Python executable: {sys.executable}",
    )


def _run_python(arguments: dict[str, Any]) -> dict[str, Any]:
    code = str(arguments.get("code") or "")
    if not code.strip():
        raise ValueError("code is required")
    cwd = _resolve_cwd(arguments.get("workingDirectory"))
    script_fd, script_path_raw = tempfile.mkstemp(prefix="yggdrasil-python-", suffix=".py", dir=str(cwd))
    script_path = Path(script_path_raw)
    try:
        # Use a temporary script instead of `-c` to avoid Windows/Unicode quoting issues.
        with os.fdopen(script_fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(code)
        completed = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=max(int(arguments.get("timeoutMs") or 10000), 1) / 1000.0,
            check=False,
        )
    finally:
        try:
            script_path.unlink(missing_ok=True)
        except TypeError:
            if script_path.exists():
                script_path.unlink()
    return structured_tool_result(
        {
            "exitCode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        },
        text=f"Python finished with exit code {completed.returncode}.",
        is_error=completed.returncode != 0,
    )


def main() -> None:
    server = SimpleMCPServer("workspace-python-mcp", "0.1.0")
    server.register_tool(
        name="configure_python_environment",
        description="Configure and pin the Python executable used by the MCP Python server.",
        input_schema={
            "type": "object",
            "properties": {
                "resourcePath": {"type": "string"},
                "pythonExecutable": {"type": "string"},
            },
            "additionalProperties": False,
        },
        handler=_configure_python_environment,
    )
    server.register_tool(
        name="get_python_executable_details",
        description="Return the selected Python executable and terminal command details.",
        input_schema={
            "type": "object",
            "properties": {
                "resourcePath": {"type": "string"},
            },
            "additionalProperties": False,
        },
        handler=_get_python_executable_details,
    )
    server.register_tool(
        name="get_python_environment_details",
        description="Return Python environment type, version, and installed package list.",
        input_schema={
            "type": "object",
            "properties": {
                "resourcePath": {"type": "string"},
                "timeoutMs": {"type": "integer", "minimum": 1},
            },
            "additionalProperties": False,
        },
        handler=_get_python_environment_details,
    )
    server.register_tool(
        name="install_python_packages",
        description="Install Python packages with pip into the configured Python environment.",
        input_schema={
            "type": "object",
            "properties": {
                "resourcePath": {"type": "string"},
                "packageList": {
                    "oneOf": [
                        {"type": "array", "items": {"type": "string"}},
                        {"type": "string"},
                    ]
                },
                "timeoutMs": {"type": "integer", "minimum": 1},
            },
            "required": ["packageList"],
            "additionalProperties": False,
        },
        handler=_install_python_packages,
    )
    server.register_tool(
        name="inspect_environment",
        description="Report the active Python interpreter and working directory used by the MCP bridge.",
        input_schema={
            "type": "object",
            "properties": {"workingDirectory": {"type": "string"}},
            "additionalProperties": False,
        },
        handler=_inspect_environment,
    )
    server.register_tool(
        name="run_python",
        description="Run a Python snippet inside the configured project workspace.",
        input_schema={
            "type": "object",
            "properties": {
                "code": {"type": "string"},
                "workingDirectory": {"type": "string"},
                "timeoutMs": {"type": "integer", "minimum": 1},
            },
            "required": ["code"],
            "additionalProperties": False,
        },
        handler=_run_python,
    )
    server.serve_stdio()


if __name__ == "__main__":
    main()