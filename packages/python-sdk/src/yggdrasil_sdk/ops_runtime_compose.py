from __future__ import annotations

import socket
import subprocess
from pathlib import Path
from typing import Any

from .ops_runtime_shared import _port_from_env, _run_command
from .support import resolve_workspace_root, utc_now


def _docker_compose_command(workspace_root: Path | None = None) -> list[str]:
    compose_path = resolve_workspace_root(workspace_root) / "infra" / "docker-compose.yml"
    return ["docker", "compose", "-f", str(compose_path)]


def _tcp_check(port: int, *, host: str = "127.0.0.1", timeout: float = 1.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def run_compose_smoke(*, workspace_root: Path | None = None, ensure_up: bool = False) -> dict[str, Any]:
    command = _docker_compose_command(workspace_root)
    if ensure_up:
        _run_command([*command, "up", "-d"])

    services_output = subprocess.run([*command, "config", "--services"], capture_output=True, text=True, check=False)
    if services_output.returncode != 0:
        detail = services_output.stderr.strip() or services_output.stdout.strip() or "docker compose config failed"
        raise RuntimeError(detail)
    declared_services = [line.strip() for line in services_output.stdout.splitlines() if line.strip()]

    running_output = subprocess.run([*command, "ps", "--services", "--status", "running"], capture_output=True, text=True, check=False)
    if running_output.returncode != 0:
        detail = running_output.stderr.strip() or running_output.stdout.strip() or "docker compose ps failed"
        raise RuntimeError(detail)
    running_services = {line.strip() for line in running_output.stdout.splitlines() if line.strip()}

    port_checks = {
        "postgres": _port_from_env("YGGDRASIL_POSTGRES_PORT", 5432),
        "redis": _port_from_env("YGGDRASIL_REDIS_PORT", 6379),
        "nats": _port_from_env("YGGDRASIL_NATS_PORT", 4222),
        "minio": _port_from_env("YGGDRASIL_MINIO_API_PORT", 9000),
        "temporal": _port_from_env("YGGDRASIL_TEMPORAL_PORT", 7233),
        "temporal-ui": _port_from_env("YGGDRASIL_TEMPORAL_UI_PORT", 8088),
        "otel-collector": _port_from_env("YGGDRASIL_OTEL_COLLECTOR_HTTP_PORT", 4318),
        "jaeger": _port_from_env("YGGDRASIL_JAEGER_UI_PORT", 16686),
    }
    checks = [
        {
            "service": service,
            "declared": service in declared_services,
            "running": service in running_services,
            "port": port,
            "reachable": _tcp_check(port),
        }
        for service, port in port_checks.items()
    ]
    status = "ok" if all(item["declared"] and item["running"] and item["reachable"] for item in checks) else "degraded"
    return {
        "generatedAt": utc_now().isoformat(),
        "status": status,
        "declaredServices": declared_services,
        "runningServices": sorted(running_services),
        "checks": checks,
    }