from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from yggdrasil_sdk.persistence import ModulePlatformService
from yggdrasil_sdk.persistence.coordination import RedisCoordinator


@dataclass(slots=True)
class ModuleHostService:
    workspace_root: Path | None = None
    platform: ModulePlatformService = field(init=False)
    coordinator: RedisCoordinator = field(init=False)

    def __post_init__(self) -> None:
        self.platform = ModulePlatformService(workspace_root=self.workspace_root)
        self.coordinator = RedisCoordinator()

    def health(self) -> dict[str, object]:
        return {
            "status": "ok",
            "service": "module-host",
            **self.platform.health_report(),
            "redis": self.coordinator.ping(),
        }

    def sync_modules(self) -> dict[str, object]:
        snapshot = self.platform.sync_catalog()
        return {
            "status": "synced",
            "generatedAt": snapshot.generated_at,
            "moduleCount": len(snapshot.manifests),
            "installCount": len(snapshot.installs),
            "activeCount": len([record for record in snapshot.installs if record.lifecycle_state == "active"]),
        }

    def list_modules(self) -> dict[str, object]:
        snapshot = self.platform.sync_catalog()
        return snapshot.model_dump(by_alias=True, mode="json")

    def discovered_modules(self) -> dict[str, object]:
        snapshot = self.platform.sync_catalog()
        return {
            "generatedAt": snapshot.generated_at,
            "manifests": [manifest.model_dump(by_alias=True) for manifest in snapshot.manifests],
            "installs": [record.model_dump(by_alias=True, mode="json") for record in snapshot.installs],
            "health": [report.model_dump(by_alias=True, mode="json") for report in snapshot.health],
        }

    def module_details(self, module_id: str) -> dict[str, object]:
        return self.platform.get_module_details(module_id)

    def enable_module(self, module_id: str) -> dict[str, object]:
        return self.platform.set_module_enabled(module_id, enabled=True)

    def disable_module(self, module_id: str) -> dict[str, object]:
        return self.platform.set_module_enabled(module_id, enabled=False)

    def quarantine_module(self, module_id: str, *, reason: str) -> dict[str, object]:
        return self.platform.quarantine_module(module_id, reason=reason)

    def unquarantine_module(self, module_id: str) -> dict[str, object]:
        return self.platform.unquarantine_module(module_id)

    def list_hooks(self) -> dict[str, object]:
        return self.platform.list_hook_registry()

    def list_subscriptions(self) -> dict[str, object]:
        return self.platform.list_event_subscriptions()

    def list_health_reports(self) -> dict[str, object]:
        return self.platform.list_health_reports()

    def list_config_bindings(self) -> dict[str, object]:
        return self.platform.list_config_bindings()

    def publish_pending_events(self, *, limit: int = 100) -> dict[str, object]:
        return self.platform.publish_pending_events(limit=limit)

    def consume_events(
        self,
        *,
        module_id: str | None = None,
        limit: int = 10,
        timeout_seconds: int = 1,
    ) -> dict[str, object]:
        return self.platform.consume_events(
            module_id=module_id,
            limit=limit,
            timeout_seconds=timeout_seconds,
        )