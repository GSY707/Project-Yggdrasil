from __future__ import annotations

from pathlib import Path

from yggdrasil_sdk.catalog import default_modules_root as sdk_default_modules_root
from yggdrasil_sdk.catalog import discover_module_manifests
from yggdrasil_sdk.contracts import ModuleManifestSummary


def default_modules_root() -> Path:
    return sdk_default_modules_root(Path(__file__).resolve())


def discover_manifests(base_dir: Path | None = None) -> list[ModuleManifestSummary]:
    return discover_module_manifests(base_dir or default_modules_root())