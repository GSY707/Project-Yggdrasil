from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ..support import resolve_workspace_root


def module_manifest_path(module_id: str) -> Path:
    return resolve_workspace_root() / "modules" / module_id / "yggdrasil.module.yaml"


def load_module_prompt_asset(module_id: str, relative_path: str) -> dict[str, Any]:
    asset_path = resolve_workspace_root() / "modules" / module_id / relative_path
    payload = yaml.safe_load(asset_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Prompt asset at {asset_path} is not a mapping.")
    return payload