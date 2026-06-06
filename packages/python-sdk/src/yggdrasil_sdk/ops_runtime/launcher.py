from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time
from typing import Sequence
from urllib.error import URLError
from urllib.request import urlopen

from yggdrasil_sdk.provider_config import has_provider_key
from yggdrasil_sdk.support import resolve_state_root, resolve_workspace_root


PRODUCT_URL = "http://localhost:3000"
CORE_HEALTH_URL = "http://127.0.0.1:5000/health"
DOCKER_DESKTOP_PATH = r"C:\Program Files\Docker\Docker\Docker Desktop.exe"


@dataclass(slots=True)
class ManagedProcess:
    name: str
    command: list[str]
    process: subprocess.Popen
    log_path: Path


def _which(command: str) -> str:
    candidates = [command]
    if os.name == "nt" and not command.lower().endswith((".cmd", ".exe", ".bat")):
        candidates = [f"{command}.cmd", f"{command}.exe", command]
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    raise RuntimeError(f"Required command not found on PATH: {command}")


def _run_checked(command: Sequence[str], *, cwd: Path, label: str) -> None:
    result = subprocess.run(list(command), cwd=str(cwd), text=True, capture_output=True, check=False)
    if result.returncode != 0:
        detail = "\n".join(part for part in (result.stdout.strip(), result.stderr.strip()) if part)
        raise RuntimeError(f"{label} failed with exit code {result.returncode}.\n{detail}")


def _port_is_open(port: int, *, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex((host, port)) == 0


def _ensure_ports_available(ports: dict[int, str], *, allow_existing: bool) -> None:
    if allow_existing:
        return
    busy = [f"{port} ({name})" for port, name in ports.items() if _port_is_open(port)]
    if busy:
        raise RuntimeError(
            "Product ports are already in use: "
            + ", ".join(busy)
            + ". Stop the existing process or rerun with --allow-existing-services."
        )


def _has_provider_key() -> bool:
    return has_provider_key()


def _preflight(*, workspace_root: Path, allow_missing_provider: bool, allow_existing_services: bool) -> None:
    docker = _which("docker")
    _which("uv")
    _which("corepack")
    _ensure_ports_available(
        {
            3000: "Web",
            5000: "Core API",
            5001: "Agent Runtime",
            5002: "Module Host",
        },
        allow_existing=allow_existing_services,
    )
    if not allow_missing_provider and not _has_provider_key():
        raise RuntimeError(
            "No model provider key is configured. Set YGGDRASIL_LLM_API_KEY_LONGCAT or LONGCAT_API_KEY in .env, "
            "or pass --allow-missing-provider for fallback-only local testing."
        )
    result = subprocess.run([docker, "info"], cwd=str(workspace_root), text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(
            "Docker is not available. Start Docker Desktop first. "
            f"Expected Windows path: {DOCKER_DESKTOP_PATH}\n{result.stderr.strip() or result.stdout.strip()}"
        )


def _wait_for_http(url: str, *, label: str, timeout_seconds: int) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error = ""
    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=2) as response:
                if 200 <= response.status < 500:
                    return
        except URLError as exc:
            last_error = str(exc)
        except Exception as exc:
            last_error = str(exc)
        time.sleep(1)
    raise RuntimeError(f"{label} did not become reachable at {url}. {last_error}")


def _start_process(name: str, command: Sequence[str], *, cwd: Path, log_dir: Path) -> ManagedProcess:
    log_path = log_dir / f"{name}.log"
    handle = log_path.open("a", encoding="utf-8")
    env = dict(os.environ)
    env.setdefault("PYTHONUNBUFFERED", "1")
    env.setdefault("YGGDRASIL_CORE_API_BASE_URL", "http://127.0.0.1:5000")
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    process = subprocess.Popen(
        list(command),
        cwd=str(cwd),
        env=env,
        stdout=handle,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        creationflags=creationflags,
    )
    return ManagedProcess(name=name, command=list(command), process=process, log_path=log_path)


def _stop_processes(processes: list[ManagedProcess]) -> None:
    for managed in reversed(processes):
        if managed.process.poll() is None:
            managed.process.terminate()
    deadline = time.monotonic() + 8
    for managed in reversed(processes):
        while managed.process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.2)
        if managed.process.poll() is None:
            managed.process.kill()


def launch_local_product(
    *,
    workspace_root: Path | None = None,
    allow_missing_provider: bool = False,
    allow_existing_services: bool = False,
    skip_infra: bool = False,
    detach: bool = False,
    wait_timeout_seconds: int = 90,
) -> dict[str, object]:
    root = resolve_workspace_root(workspace_root)
    state_root = resolve_state_root(root)
    log_dir = state_root / "product-logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    _preflight(
        workspace_root=root,
        allow_missing_provider=allow_missing_provider,
        allow_existing_services=allow_existing_services,
    )

    docker = _which("docker")
    uv = _which("uv")
    corepack = _which("corepack")

    if not skip_infra:
        _run_checked([docker, "compose", "-f", "infra/docker-compose.yml", "up", "-d"], cwd=root, label="docker compose up")
    _run_checked([uv, "run", "alembic", "upgrade", "head"], cwd=root, label="alembic upgrade")

    processes = [
        _start_process("core-api", [uv, "run", "yggdrasil-core-api"], cwd=root, log_dir=log_dir),
        _start_process("agent-runtime", [uv, "run", "yggdrasil-agent-runtime"], cwd=root, log_dir=log_dir),
        _start_process("module-host", [uv, "run", "yggdrasil-module-host"], cwd=root, log_dir=log_dir),
        _start_process("worker", [uv, "run", "yggdrasil-worker", "--serve"], cwd=root, log_dir=log_dir),
        _start_process("web", [corepack, "pnpm", "web:dev"], cwd=root, log_dir=log_dir),
    ]

    try:
        _wait_for_http(CORE_HEALTH_URL, label="Core API", timeout_seconds=wait_timeout_seconds)
        _wait_for_http(PRODUCT_URL, label="Web", timeout_seconds=wait_timeout_seconds)
        summary = {
            "status": "running",
            "url": PRODUCT_URL,
            "logs": str(log_dir),
            "processes": [
                {
                    "name": managed.name,
                    "pid": managed.process.pid,
                    "log": str(managed.log_path),
                }
                for managed in processes
            ],
        }
        print(PRODUCT_URL, flush=True)
        if detach:
            return summary
        while True:
            stopped = [managed for managed in processes if managed.process.poll() is not None]
            if stopped:
                names = ", ".join(f"{managed.name}={managed.process.returncode}" for managed in stopped)
                raise RuntimeError(f"Product service exited: {names}. Logs: {log_dir}")
            time.sleep(1)
    except KeyboardInterrupt:
        return {
            "status": "stopped",
            "url": PRODUCT_URL,
            "logs": str(log_dir),
        }
    finally:
        if not detach:
            _stop_processes(processes)
