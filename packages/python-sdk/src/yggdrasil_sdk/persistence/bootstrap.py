from __future__ import annotations

from pathlib import Path

from ..catalog import build_module_catalog_snapshot
from ..contracts import ModuleCatalogSnapshot
from ..support import ensure_state_dir, resolve_workspace_root, write_json
from .database import get_persistence_runtime, initialize_schema
from .module_platform import ModulePlatformService
from .repositories import ModuleStateRepository, WorkspaceBootstrapRepository


def ensure_workspace_bootstrap() -> dict[str, str]:
    runtime = get_persistence_runtime()
    if runtime.settings.auto_create_schema:
        initialize_schema()
    with runtime.session_scope() as session:
        return WorkspaceBootstrapRepository(session).ensure_default_workspace()


def sync_module_catalog_snapshot(workspace_root: Path | None = None) -> ModuleCatalogSnapshot:
    root = resolve_workspace_root(workspace_root)
    return ModulePlatformService(workspace_root=root).sync_catalog()