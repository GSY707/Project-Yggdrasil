from __future__ import annotations

import shlex
import shutil
from pathlib import Path
from typing import Any

from .ops_runtime_shared import (
    _REAL_USER_VALIDATION_MATERIALS,
    _default_real_user_validation_sandbox_dir,
    _powershell_file_command,
    _powershell_quote,
    _run_git_command,
    _shell_file_command,
    resolve_workspace_root,
)
from .support import prepare_runtime_workspace_sandbox, utc_now, write_json


def _copy_real_user_validation_materials(materials_root: Path, workspace_root: Path) -> list[dict[str, str]]:
    copied: list[dict[str, str]] = []
    for relative_path in _REAL_USER_VALIDATION_MATERIALS:
        source_path = (workspace_root / relative_path).resolve()
        if not source_path.exists():
            raise FileNotFoundError(f"Real-user validation material missing: {source_path}")
        target_path = (materials_root / relative_path).resolve()
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)
        copied.append(
            {
                "relativePath": relative_path.as_posix(),
                "source": str(source_path),
                "copiedTo": str(target_path),
            }
        )
    return copied


def _initialize_sandbox_git_repo(repo_path: Path) -> dict[str, str]:
    _run_git_command(repo_path, "init", "-b", "main")
    _run_git_command(repo_path, "config", "user.name", "Yggdrasil Pilot")
    _run_git_command(repo_path, "config", "user.email", "pilot@yggdrasil.local")
    _run_git_command(repo_path, "add", ".")
    _run_git_command(repo_path, "commit", "-m", "sandbox snapshot")
    return {
        "branch": _run_git_command(repo_path, "branch", "--show-current"),
        "head": _run_git_command(repo_path, "rev-parse", "HEAD"),
    }


def _write_real_user_activation_scripts(
    sandbox_root: Path,
    workspace_path: Path,
    env_vars: dict[str, str],
    *,
    disable_live_llm: bool,
) -> dict[str, str]:
    powershell_path = sandbox_root / "activate.ps1"
    powershell_lines = [
        "$ErrorActionPreference = \"Stop\"",
        "Remove-Item Env:YGGDRASIL_STATE_DIR -ErrorAction SilentlyContinue",
    ]
    for key, value in env_vars.items():
        powershell_lines.append(f'$env:{key} = "{_powershell_quote(value)}"')
    if disable_live_llm:
        powershell_lines.append('$env:YGGDRASIL_DISABLE_LIVE_LLM = "1"')
    else:
        powershell_lines.append("Remove-Item Env:YGGDRASIL_DISABLE_LIVE_LLM -ErrorAction SilentlyContinue")
    powershell_lines.append(f'Set-Location "{_powershell_quote(str(workspace_path))}"')
    powershell_lines.append('Write-Host "Real-user validation sandbox ready."')
    powershell_path.write_text("\n".join(powershell_lines) + "\n", encoding="utf-8")

    shell_path = sandbox_root / "activate.sh"
    shell_lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "unset YGGDRASIL_STATE_DIR || true",
    ]
    for key, value in env_vars.items():
        shell_lines.append(f"export {key}={shlex.quote(value)}")
    if disable_live_llm:
        shell_lines.append("export YGGDRASIL_DISABLE_LIVE_LLM=1")
    else:
        shell_lines.append("unset YGGDRASIL_DISABLE_LIVE_LLM || true")
    shell_lines.append(f"cd {shlex.quote(str(workspace_path))}")
    shell_lines.append("printf 'Real-user validation sandbox ready.\\n'")
    shell_path.write_text("\n".join(shell_lines) + "\n", encoding="utf-8")

    return {
        "powershell": str(powershell_path),
        "shell": str(shell_path),
    }


def _write_real_user_validation_readme(sandbox_root: Path, manifest_path: Path) -> Path:
    readme_path = sandbox_root / "README.md"
    readme_path.write_text(
        "# Real User Validation Sandbox\n\n"
        "This directory is an isolated runtime sandbox for internal pilot runs.\n\n"
        "## Contents\n\n"
        "- workspace/: copied Project Yggdrasil workspace snapshot\n"
        "- .yggdrasil/: isolated runtime state root and sqlite database target\n"
        "- materials/: frozen task pack, scorecard, and validation research notes\n"
        "- activate.ps1 / activate.sh: environment activation scripts\n"
        "- prefer running the generated script files directly (`pwsh -File activate.ps1` / `bash activate.sh`)\n"
        f"- sandbox-manifest.json: generated manifest ({manifest_path.name})\n",
        encoding="utf-8",
    )
    return readme_path


def prepare_real_user_validation_sandbox(
    *,
    workspace_root: Path | None = None,
    output_dir: Path | None = None,
    disable_live_llm: bool = False,
) -> dict[str, Any]:
    workspace = resolve_workspace_root(workspace_root)
    sandbox_root = (output_dir or _default_real_user_validation_sandbox_dir(workspace_root)).expanduser().resolve()
    try:
        sandbox_root.relative_to(workspace)
    except ValueError:
        pass
    else:
        raise ValueError(f"Sandbox output must be outside the workspace root: {sandbox_root}")

    if sandbox_root.exists() and any(sandbox_root.iterdir()):
        raise FileExistsError(f"Sandbox output directory already exists and is not empty: {sandbox_root}")

    sandbox_root.mkdir(parents=True, exist_ok=True)
    state_root = sandbox_root / ".yggdrasil"
    state_root.mkdir(parents=True, exist_ok=True)
    sandbox_workspace = prepare_runtime_workspace_sandbox(sandbox_root, workspace)
    materials = _copy_real_user_validation_materials(sandbox_root / "materials", workspace)
    git_summary = _initialize_sandbox_git_repo(sandbox_workspace)
    env_vars = {
        "YGGDRASIL_DATABASE_URL": f"sqlite+pysqlite:///{(state_root / 'runtime.db').resolve().as_posix()}",
        "YGGDRASIL_AUTO_CREATE_SCHEMA": "1",
        "YGGDRASIL_COORDINATION_BACKEND": "memory",
        "YGGDRASIL_REDIS_URL": "redis://127.0.0.1:6390/15",
        "YGGDRASIL_STATE_ROOT": str(state_root.resolve()),
        "YGGDRASIL_GIT_REPO_PATH": str(sandbox_workspace.resolve()),
        "YGGDRASIL_MCP_PROJECT_WORKSPACE": str(sandbox_workspace.resolve()),
    }
    activation_scripts = _write_real_user_activation_scripts(
        sandbox_root,
        sandbox_workspace,
        env_vars,
        disable_live_llm=disable_live_llm,
    )
    activation_commands = {
        "powershell": _powershell_file_command(Path(activation_scripts["powershell"])),
        "shell": _shell_file_command(Path(activation_scripts["shell"])),
    }
    manifest_path = sandbox_root / "sandbox-manifest.json"
    readme_path = _write_real_user_validation_readme(sandbox_root, manifest_path)
    manifest = {
        "createdAt": utc_now().isoformat(),
        "status": "ready",
        "sandboxRoot": str(sandbox_root),
        "sourceWorkspace": str(workspace),
        "workspaceRoot": str(sandbox_workspace.resolve()),
        "stateRoot": str(state_root.resolve()),
        "materialsRoot": str((sandbox_root / "materials").resolve()),
        "workspaceIsolationConfirmed": True,
        "env": env_vars,
        "disableLiveLlm": disable_live_llm,
        "activationScripts": activation_scripts,
        "activationCommands": activation_commands,
        "git": git_summary,
        "materials": materials,
        "readme": str(readme_path),
    }
    write_json(manifest_path, manifest)
    return manifest
