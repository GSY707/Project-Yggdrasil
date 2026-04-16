from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from yggdrasil_sdk import get_persistence_runtime
from yggdrasil_sdk.contracts import ModuleCatalogSnapshot, ModuleInstallRecord

from .services import ModuleHostService


@dataclass(slots=True)
class DatabaseBackedModuleRegistry:
    workspace_root: Path | None = None
    service: ModuleHostService = field(init=False)

    def __post_init__(self) -> None:
        self.service = ModuleHostService(workspace_root=self.workspace_root)

    def snapshot(self) -> ModuleCatalogSnapshot:
        return ModuleCatalogSnapshot.model_validate(self.service.list_modules())

    def install_records(self) -> list[ModuleInstallRecord]:
        return self.snapshot().installs

    def health(self) -> dict[str, object]:
        return get_persistence_runtime().ping_database()