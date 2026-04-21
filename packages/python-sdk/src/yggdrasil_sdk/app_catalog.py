from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from .contracts import ApplicationCatalogSnapshot, ApplicationConfigBinding, ApplicationManifestSummary, ExternalRef
from .persistence.constants import DEFAULT_APP_ID
from .support import ensure_state_dir, read_json, relative_workspace_path, resolve_workspace_root, utc_now, write_json


APP_MANIFEST_NAME = "yggdrasil.app.yaml"


def default_applications_root(workspace_root: Path | None = None) -> Path:
    return resolve_workspace_root(workspace_root) / "applications"


def _load_yaml_payload(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Manifest at {path} is not a mapping.")
    return payload


def _relative_file_list(base_dir: Path, values: list[Any], workspace_root: Path) -> list[str]:
    files: list[str] = []
    for value in values:
        if not isinstance(value, str) or not value.strip():
            continue
        files.append(relative_workspace_path(base_dir / value, workspace_root))
    return files


def _external_ref(base_dir: Path, value: Any, workspace_root: Path) -> ExternalRef | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return ExternalRef(type="file", locator=relative_workspace_path(base_dir / value, workspace_root))


def discover_application_manifests(applications_root: Path | None = None) -> list[ApplicationManifestSummary]:
    root = applications_root or default_applications_root()
    workspace_root = resolve_workspace_root(root)
    manifests: list[ApplicationManifestSummary] = []

    for manifest_path in sorted(root.glob(f"*/{APP_MANIFEST_NAME}")):
        raw = _load_yaml_payload(manifest_path)
        metadata = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
        spec = raw.get("spec") if isinstance(raw.get("spec"), dict) else {}
        prompting = spec.get("prompting") if isinstance(spec.get("prompting"), dict) else {}
        dependencies = spec.get("dependencies") if isinstance(spec.get("dependencies"), dict) else {}
        config = spec.get("config") if isinstance(spec.get("config"), dict) else {}
        frontend = spec.get("frontend") if isinstance(spec.get("frontend"), dict) else {}
        module_dependencies = [
            str(item.get("id"))
            for item in dependencies.get("modules") or []
            if isinstance(item, dict) and str(item.get("id") or "").strip()
        ]

        manifests.append(
            ApplicationManifestSummary(
                appId=str(metadata.get("id") or manifest_path.parent.name),
                displayName=str(metadata.get("displayName") or manifest_path.parent.name),
                version=str(metadata.get("version") or "0.0.0"),
                manifestPath=relative_workspace_path(manifest_path, workspace_root),
                owner=str(metadata.get("owner")) if metadata.get("owner") is not None else None,
                description=str(metadata.get("description")) if metadata.get("description") is not None else None,
                defaultLoad=bool(metadata.get("defaultLoad", False)),
                moduleDependencies=module_dependencies,
                capabilityModuleIds=[str(item) for item in prompting.get("capabilityModules") or [] if str(item).strip()],
                sceneModuleIds=[str(item) for item in prompting.get("sceneModules") or [] if str(item).strip()],
                defaultPromptProfileId=(
                    str(prompting.get("defaultPromptProfileId"))
                    if prompting.get("defaultPromptProfileId") is not None
                    else None
                ),
                subagentPromptProfileId=(
                    str(prompting.get("subagentPromptProfileId"))
                    if prompting.get("subagentPromptProfileId") is not None
                    else None
                ),
                defaultSeedTemplateId=(
                    str(prompting.get("defaultSeedTemplateId"))
                    if prompting.get("defaultSeedTemplateId") is not None
                    else None
                ),
                promptProfileFiles=_relative_file_list(manifest_path.parent, prompting.get("profileFiles") or [], workspace_root),
                seedTemplateFiles=_relative_file_list(manifest_path.parent, prompting.get("seedTemplateFiles") or [], workspace_root),
                configDefaultsRef=_external_ref(manifest_path.parent, config.get("defaultsRef"), workspace_root),
                frontendEntryRoute=(
                    str(frontend.get("entryRoute"))
                    if frontend.get("entryRoute") is not None
                    else None
                ),
                dashboardRef=_external_ref(manifest_path.parent, frontend.get("dashboardRef"), workspace_root),
            )
        )

    return manifests


def build_application_catalog_snapshot(workspace_root: Path | None = None) -> ApplicationCatalogSnapshot:
    root = resolve_workspace_root(workspace_root)
    snapshot = ApplicationCatalogSnapshot(
        generatedAt=utc_now(),
        manifests=discover_application_manifests(default_applications_root(root)),
    )
    write_json(
        ensure_state_dir(root) / "application-catalog-snapshot.json",
        snapshot.model_dump(by_alias=True, mode="json"),
    )
    return snapshot


def get_application_manifest(app_id: str, workspace_root: Path | None = None) -> ApplicationManifestSummary:
    snapshot = build_application_catalog_snapshot(workspace_root)
    for manifest in snapshot.manifests:
        if manifest.app_id == app_id:
            return manifest
    raise KeyError(app_id)


def _application_profile_path(workspace_root: Path | None = None) -> Path:
    return ensure_state_dir(resolve_workspace_root(workspace_root)) / "application-profile.json"


def _default_application_profile() -> dict[str, Any]:
    return {
        "_defaults": {"activeAppId": DEFAULT_APP_ID},
        "bindings": {},
    }


def _load_application_profile(workspace_root: Path | None = None) -> dict[str, Any]:
    return read_json(_application_profile_path(workspace_root), _default_application_profile())


def _write_application_profile(payload: dict[str, Any], workspace_root: Path | None = None) -> None:
    write_json(_application_profile_path(workspace_root), payload)


def active_application_id(workspace_root: Path | None = None) -> str:
    profile = _load_application_profile(workspace_root)
    defaults = profile.get("_defaults") if isinstance(profile.get("_defaults"), dict) else {}
    return str(defaults.get("activeAppId") or DEFAULT_APP_ID)


def set_active_application(app_id: str, workspace_root: Path | None = None) -> ApplicationConfigBinding:
    get_application_manifest(app_id, workspace_root)
    now = utc_now()
    profile = _load_application_profile(workspace_root)
    defaults = profile.setdefault("_defaults", {})
    defaults["activeAppId"] = app_id
    bindings = profile.setdefault("bindings", {})
    binding = bindings.setdefault(app_id, {})
    binding["updatedAt"] = now.isoformat()
    _write_application_profile(profile, workspace_root)
    return ApplicationConfigBinding(
        appId=app_id,
        active=True,
        importantConfig=dict(binding.get("importantConfig") or {}),
        updatedAt=now,
    )


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(dict(merged[key]), value)
            continue
        merged[key] = value
    return merged


def upsert_application_config_binding(
    app_id: str,
    important_config: dict[str, Any],
    workspace_root: Path | None = None,
) -> ApplicationConfigBinding:
    get_application_manifest(app_id, workspace_root)
    now = utc_now()
    profile = _load_application_profile(workspace_root)
    bindings = profile.setdefault("bindings", {})
    binding = bindings.setdefault(app_id, {})
    binding["importantConfig"] = dict(important_config or {})
    binding["updatedAt"] = now.isoformat()
    _write_application_profile(profile, workspace_root)
    return ApplicationConfigBinding(
        appId=app_id,
        active=active_application_id(workspace_root) == app_id,
        importantConfig=dict(binding.get("importantConfig") or {}),
        updatedAt=now,
    )


def get_application_config_binding(app_id: str, workspace_root: Path | None = None) -> ApplicationConfigBinding:
    get_application_manifest(app_id, workspace_root)
    profile = _load_application_profile(workspace_root)
    bindings = profile.get("bindings") if isinstance(profile.get("bindings"), dict) else {}
    binding = bindings.get(app_id) if isinstance(bindings.get(app_id), dict) else {}
    updated_at = binding.get("updatedAt")
    return ApplicationConfigBinding(
        appId=app_id,
        active=active_application_id(workspace_root) == app_id,
        importantConfig=dict(binding.get("importantConfig") or {}),
        updatedAt=utc_now() if not updated_at else datetime.fromisoformat(str(updated_at)),
    )


def load_effective_application_config(app_id: str, workspace_root: Path | None = None) -> dict[str, Any]:
    manifest = get_application_manifest(app_id, workspace_root)
    defaults_payload: dict[str, Any] = {}
    if manifest.config_defaults_ref is not None:
        defaults_path = resolve_workspace_root(workspace_root) / manifest.config_defaults_ref.locator
        loaded = read_json(defaults_path, {})
        if isinstance(loaded, dict):
            defaults_payload = loaded

    profile = _load_application_profile(workspace_root)
    bindings = profile.get("bindings") if isinstance(profile.get("bindings"), dict) else {}
    binding = bindings.get(app_id) if isinstance(bindings.get(app_id), dict) else {}
    important_config = dict(binding.get("importantConfig") or {})
    return _deep_merge(defaults_payload, important_config)