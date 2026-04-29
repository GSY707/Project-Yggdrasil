from __future__ import annotations

from importlib import import_module
from pathlib import Path
import time
from threading import RLock
from typing import Any

import yaml

from .contracts import (
    EventSubscriptionRecord,
    ExternalRef,
    HealthReport,
    HookContributionRecord,
    ModuleCatalogSnapshot,
    ModuleInstallRecord,
    ModuleManifestSummary,
)
from .support import ensure_state_dir, new_id, read_json, relative_workspace_path, resolve_workspace_root, utc_now, write_json


KERNEL_VERSION = "0.1.0"

_CATALOG_CACHE: dict[str, tuple[ModuleCatalogSnapshot, float]] = {}
_CATALOG_CACHE_TTL = 2.0
_CATALOG_CACHE_LOCK = RLock()


def invalidate_catalog_cache() -> None:
    with _CATALOG_CACHE_LOCK:
        _CATALOG_CACHE.clear()


def default_modules_root(workspace_root: Path | None = None) -> Path:
    return resolve_workspace_root(workspace_root) / "modules"


def _load_manifest_payload(manifest_path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Manifest at {manifest_path} is not a mapping.")
    return payload


def discover_module_manifests(modules_root: Path | None = None) -> list[ModuleManifestSummary]:
    root = modules_root or default_modules_root()
    workspace_root = resolve_workspace_root(root)
    manifests: list[ModuleManifestSummary] = []

    for manifest_path in sorted(root.glob("*/yggdrasil.module.yaml")):
        raw = _load_manifest_payload(manifest_path)
        metadata = raw.get("metadata", {})
        spec = raw.get("spec", {})
        runtime = spec.get("runtime", {})
        capabilities = spec.get("capabilities", {})
        permissions = spec.get("permissions", {})
        compatibility = spec.get("compatibility", {})

        manifests.append(
            ModuleManifestSummary(
                moduleId=metadata.get("id", manifest_path.parent.name),
                displayName=metadata.get("displayName", manifest_path.parent.name),
                version=str(metadata.get("version", "0.0.0")),
                runtimeMode=runtime.get("mode", "in-process"),
                manifestPath=relative_workspace_path(manifest_path, workspace_root),
                category=metadata.get("category"),
                owner=metadata.get("owner"),
                description=metadata.get("description"),
                entryPoint=runtime.get("entryPoint"),
                protocol=runtime.get("protocol"),
                kernelCompatibility=compatibility.get("kernel"),
                hooks=list(capabilities.get("hooks", [])),
                publishes=list(capabilities.get("publishes", [])),
                subscribes=list(capabilities.get("subscribes", [])),
                requestedPermissions=list(permissions.get("requested", [])),
            )
        )

    return manifests


def _is_kernel_compatible(kernel_range: str | None) -> bool:
    if not kernel_range:
        return True
    if ">=0.1.0" in kernel_range and "<0.2.0" in kernel_range:
        return True
    return KERNEL_VERSION in kernel_range


def _load_module_profile(state_dir: Path) -> dict[str, Any]:
    return read_json(state_dir / "module-profile.json", {"_defaults": {"desiredState": "enabled"}})


def _load_existing_installs(state_dir: Path) -> dict[str, ModuleInstallRecord]:
    records = read_json(state_dir / "module-install-records.json", [])
    installs: dict[str, ModuleInstallRecord] = {}
    for record in records:
        model = ModuleInstallRecord.model_validate(record)
        installs[model.module_id] = model
    return installs


def _desired_state_for(module_id: str, profile: dict[str, Any], existing: ModuleInstallRecord | None) -> str:
    default_state = existing.desired_state if existing is not None else profile.get("_defaults", {}).get("desiredState", "enabled")
    module_entry = profile.get(module_id)
    if isinstance(module_entry, bool):
        return "enabled" if module_entry else "disabled"
    if isinstance(module_entry, dict):
        return module_entry.get("desiredState", default_state)
    return default_state


def build_module_catalog_snapshot(workspace_root: Path | None = None) -> ModuleCatalogSnapshot:
    root = resolve_workspace_root(workspace_root)
    cache_key = str(root)
    now = time.monotonic()
    with _CATALOG_CACHE_LOCK:
        cached = _CATALOG_CACHE.get(cache_key)
        if cached is not None and now - cached[1] < _CATALOG_CACHE_TTL:
            return cached[0]

    state_dir = ensure_state_dir(root)
    profile = _load_module_profile(state_dir)
    existing_installs = _load_existing_installs(state_dir)
    manifests = discover_module_manifests(default_modules_root(root))
    generated_at = utc_now()

    installs: list[ModuleInstallRecord] = []
    hooks: list[HookContributionRecord] = []
    subscriptions: list[EventSubscriptionRecord] = []
    health: list[HealthReport] = []

    for manifest in manifests:
        existing = existing_installs.get(manifest.module_id)
        desired_state = _desired_state_for(manifest.module_id, profile, existing)
        compatible = _is_kernel_compatible(manifest.kernel_compatibility)
        lifecycle_state = "incompatible" if not compatible else "discovered"
        if existing is not None and compatible:
            lifecycle_state = existing.lifecycle_state
        installed_at = existing.installed_at if existing else generated_at
        enabled_at = existing.enabled_at if existing else None
        disabled_at = existing.disabled_at if existing else None

        install_record = ModuleInstallRecord(
            id=existing.id if existing else new_id("modins", manifest.module_id, manifest.version, stable=True),
            moduleId=manifest.module_id,
            moduleVersion=manifest.version,
            desiredState=desired_state,
            lifecycleState=lifecycle_state,
            runtimeMode=manifest.runtime_mode,
            manifestRef=ExternalRef(type="file", locator=manifest.manifest_path),
            configBindingId=None,
            installedAt=installed_at,
            enabledAt=enabled_at,
            disabledAt=disabled_at,
            lastError=None if compatible else "Kernel compatibility check failed.",
        )
        installs.append(install_record)

        for index, hook_name in enumerate(manifest.hooks):
            hooks.append(
                HookContributionRecord(
                    id=new_id("hookreg", install_record.id, hook_name, stable=True),
                    moduleInstallId=install_record.id,
                    hookName=hook_name,
                    implementationRef=f"{manifest.entry_point or manifest.module_id}#{hook_name}",
                    executionOrder=100 + index,
                    timeoutMs=3000,
                    sideEffects="read-only",
                    enabled=desired_state == "enabled" and compatible,
                    createdAt=generated_at,
                )
            )

        for event_type in manifest.subscribes:
            subscriptions.append(
                EventSubscriptionRecord(
                    id=new_id("evtreg", install_record.id, event_type, stable=True),
                    moduleInstallId=install_record.id,
                    eventType=event_type,
                    consumerGroup=f"{manifest.module_id}.{event_type.replace('.', '-')}",
                    deliveryMode="at-least-once",
                    status="active" if desired_state == "enabled" and compatible else "paused",
                    createdAt=generated_at,
                    updatedAt=generated_at,
                )
            )

        health_status = "healthy"
        health_summary = "Module is discovered and awaiting lifecycle reconciliation."
        if existing is not None and compatible:
            health_status = "quarantined" if existing.lifecycle_state == "quarantined" else "healthy"
            health_summary = f"Module lifecycle state is {existing.lifecycle_state}."
        if not compatible:
            health_status = "unhealthy"
            health_summary = "Module failed compatibility validation."

        health.append(
            HealthReport(
                id=new_id("health", install_record.id, stable=True),
                moduleInstallId=install_record.id,
                status=health_status,
                summary=health_summary,
                detailsRef=None,
                observedAt=generated_at,
            )
        )

    snapshot = ModuleCatalogSnapshot(
        generatedAt=generated_at,
        manifests=manifests,
        installs=installs,
        hooks=hooks,
        subscriptions=subscriptions,
        health=health,
    )
    write_json(
        state_dir / "module-install-records.json",
        [record.model_dump(by_alias=True, mode="json") for record in installs],
    )
    write_json(
        state_dir / "module-catalog-snapshot.json",
        snapshot.model_dump(by_alias=True, mode="json"),
    )
    with _CATALOG_CACHE_LOCK:
        _CATALOG_CACHE[cache_key] = (snapshot, time.monotonic())
    return snapshot


def load_in_process_plugin(entry_point: str) -> Any:
    module_name, _, attribute_name = entry_point.partition(":")
    if not module_name or not attribute_name:
        raise ValueError(f"Unsupported entry point: {entry_point}")
    module = import_module(module_name)
    return getattr(module, attribute_name)