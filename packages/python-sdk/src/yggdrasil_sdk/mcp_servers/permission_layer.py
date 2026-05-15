from __future__ import annotations

import os
import re


_NETWORK_COMMAND_PATTERN = re.compile(
    r"(^|[\s;&|])(?:curl|wget|scp|ssh|ftp|sftp|nc|ncat|telnet|ping|tracert|nslookup|invoke-webrequest|invoke-restmethod|iwr|irm|start-bitstransfer)\b"
)


def _network_access_allowed() -> bool:
    value = str(os.environ.get("YGGDRASIL_MCP_ALLOW_NETWORK") or "").strip().lower()
    return value in {"1", "true", "yes", "on", "enable", "enabled"}


def command_requests_network(command: str) -> bool:
    normalized = str(command or "").strip().lower()
    return bool(_NETWORK_COMMAND_PATTERN.search(normalized) or "http://" in normalized or "https://" in normalized)


def assert_command_allowed(command: str) -> None:
    if command_requests_network(command) and not _network_access_allowed():
        raise PermissionError(
            "Network commands are disabled for workspace execute server. Set YGGDRASIL_MCP_ALLOW_NETWORK=1 to allow them explicitly."
        )


__all__ = ["assert_command_allowed", "command_requests_network"]