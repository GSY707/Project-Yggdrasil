from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..catalog import build_module_catalog_snapshot, invalidate_catalog_cache, load_in_process_plugin
from ..contracts import (
    ActorRef,
    EventEnvelope,
    EventHandlingResult,
    EventSubscriptionRecord,
    ExternalRef,
    HealthReport,
    HookContributionRecord,
    ModuleCatalogSnapshot,
    ModuleConfigBinding,
    ModuleEventEmission,
    ModuleInstallRecord,
    ModuleManifestSummary,
)
from ..hooks import HookNames
from ..module import HookRegistration
from ..support import ensure_state_dir, ensure_state_subdir, new_id, read_json, relative_workspace_path, resolve_workspace_root, utc_now, write_json
from ..tool_runtime import invalidate_tool_descriptor_cache
from .constants import DEFAULT_BRANCH_ID, DEFAULT_PROJECT_ID, DEFAULT_SPACE_ID
from .database import PersistenceRuntime, get_persistence_runtime, initialize_schema
from .eventing import EventBusClient, NatsJetStreamBus, OutboxPublisher, event_payload_ref
from .repositories import ModuleStateRepository, OutboxRepository, WorkspaceBootstrapRepository


MODULE_HOST_ACTOR = ActorRef(type="system", id="module-host")


@dataclass(slots=True)
class ModulePlatformService:
    workspace_root: Path | None = None
    runtime: PersistenceRuntime | None = None
    event_bus: EventBusClient | None = None

    def __post_init__(self) -> None:
        self.workspace_root = resolve_workspace_root(self.workspace_root)
        self.runtime = self.runtime or get_persistence_runtime()
        self.event_bus = self.event_bus or NatsJetStreamBus(self.runtime.settings)

    def sync_catalog(self) -> ModuleCatalogSnapshot:
        file_snapshot = build_module_catalog_snapshot(self.workspace_root)
        if self.runtime.settings.auto_create_schema:
            initialize_schema()

        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            repository = ModuleStateRepository(session)
            outbox = OutboxRepository(session)
            existing_by_module_id = {
                record.module_id: record
                for record in repository.list_module_installs()
            }
            inventory_by_module_id = {
                record.module_id: record
                for record in file_snapshot.installs
            }
            manifests_by_module_id = {
                manifest.module_id: manifest
                for manifest in file_snapshot.manifests
            }
            processed_module_ids: set[str] = set()

            for manifest in file_snapshot.manifests:
                source_record = inventory_by_module_id[manifest.module_id]
                install = self._sync_manifest_record(
                    repository,
                    outbox,
                    existing_by_module_id.get(manifest.module_id),
                    manifest,
                    source_record.desired_state,
                    source_record.last_error,
                )
                processed_module_ids.add(manifest.module_id)
                if source_record.last_error:
                    self._apply_incompatible_state(repository, install, source_record.last_error)
                    continue
                install = self._validate_module(repository, outbox, install, manifest)
                if install.lifecycle_state in {"failed", "quarantined"}:
                    continue
                install = self._install_module(repository, install, manifest)
                if install.desired_state == "enabled":
                    self._enable_module(repository, outbox, install, manifest)
                else:
                    self._disable_module(repository, outbox, install, manifest)

            removed_module_ids = set(existing_by_module_id).difference(processed_module_ids)
            for module_id in removed_module_ids:
                self._remove_module(repository, outbox, existing_by_module_id[module_id])

            snapshot = repository.build_snapshot(file_snapshot.manifests, file_snapshot.generated_at)

        state_dir = ensure_state_dir(self.workspace_root)
        write_json(
            state_dir / "module-install-records.json",
            [record.model_dump(by_alias=True, mode="json") for record in snapshot.installs],
        )
        write_json(
            state_dir / "module-catalog-snapshot.json",
            snapshot.model_dump(by_alias=True, mode="json"),
        )
        return snapshot

    def get_module_details(self, module_id: str) -> dict[str, object]:
        snapshot = self.sync_catalog()
        manifests_by_module_id = {manifest.module_id: manifest for manifest in snapshot.manifests}
        installs_by_module_id = {record.module_id: record for record in snapshot.installs}
        install = installs_by_module_id.get(module_id)
        if install is None:
            raise KeyError(module_id)
        with self.runtime.session_scope() as session:
            repository = ModuleStateRepository(session)
            config_binding = repository.get_config_binding(module_install_id=install.id)
            hooks = repository.list_hooks(module_install_id=install.id)
            subscriptions = repository.list_subscriptions(module_install_id=install.id)
            health = repository.get_health_report(install.id)
        return {
            "manifest": manifests_by_module_id[module_id].model_dump(by_alias=True),
            "install": install.model_dump(by_alias=True, mode="json"),
            "configBinding": config_binding.model_dump(by_alias=True, mode="json") if config_binding else None,
            "hooks": [record.model_dump(by_alias=True, mode="json") for record in hooks],
            "subscriptions": [record.model_dump(by_alias=True, mode="json") for record in subscriptions],
            "health": health.model_dump(by_alias=True, mode="json") if health else None,
        }

    def set_module_enabled(self, module_id: str, *, enabled: bool) -> dict[str, object]:
        manifests = build_module_catalog_snapshot(self.workspace_root).manifests
        manifests_by_module_id = {manifest.module_id: manifest for manifest in manifests}
        manifest = manifests_by_module_id.get(module_id)
        if manifest is None:
            raise KeyError(module_id)
        self._persist_desired_state(module_id, "enabled" if enabled else "disabled")
        invalidate_catalog_cache()
        invalidate_tool_descriptor_cache()
        with self.runtime.session_scope() as session:
            repository = ModuleStateRepository(session)
            outbox = OutboxRepository(session)
            install = repository.get_module_install(module_id)
            if install is None:
                raise KeyError(module_id)
            install = repository.set_desired_state(module_id, "enabled" if enabled else "disabled")
            if enabled:
                install = self._validate_module(repository, outbox, install, manifest)
                if install.lifecycle_state not in {"failed", "quarantined", "incompatible"}:
                    install = self._install_module(repository, install, manifest)
                    self._enable_module(repository, outbox, install, manifest)
            else:
                self._disable_module(repository, outbox, install, manifest)
        details = self.get_module_details(module_id)
        return {
            "status": "enabled" if enabled else "disabled",
            "module": details,
        }

    def quarantine_module(self, module_id: str, *, reason: str) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            repository = ModuleStateRepository(session)
            outbox = OutboxRepository(session)
            install = repository.get_module_install(module_id)
            if install is None:
                raise KeyError(module_id)
            self._record_failure(repository, outbox, install, reason)
        return {"status": "quarantined", "module": self.get_module_details(module_id)}

    def unquarantine_module(self, module_id: str) -> dict[str, object]:
        manifests = build_module_catalog_snapshot(self.workspace_root).manifests
        manifests_by_module_id = {manifest.module_id: manifest for manifest in manifests}
        manifest = manifests_by_module_id.get(module_id)
        if manifest is None:
            raise KeyError(module_id)
        with self.runtime.session_scope() as session:
            repository = ModuleStateRepository(session)
            outbox = OutboxRepository(session)
            install = repository.get_module_install(module_id)
            if install is None:
                raise KeyError(module_id)
            self._write_health_details(module_id, {"failureCount": 0, "status": "healthy", "summary": "Failure counter reset."})
            install = repository.transition_lifecycle(module_id, "disabled", last_error=None)
            repository.upsert_health_report(
                HealthReport(
                    id=new_id("health", install.id, stable=True),
                    moduleInstallId=install.id,
                    status="healthy",
                    summary="Module quarantine cleared and module is disabled.",
                    detailsRef=self._health_details_ref(module_id),
                    observedAt=utc_now(),
                )
            )
            if install.desired_state == "enabled":
                self._enable_module(repository, outbox, install, manifest)
        return {"status": "unquarantined", "module": self.get_module_details(module_id)}

    def list_hook_registry(self) -> dict[str, object]:
        snapshot = self.sync_catalog()
        installs_by_id = {record.id: record for record in snapshot.installs}
        with self.runtime.session_scope() as session:
            hooks = ModuleStateRepository(session).list_hooks()
        return {
            "hooks": [
                {
                    **record.model_dump(by_alias=True, mode="json"),
                    "moduleId": installs_by_id[record.module_install_id].module_id,
                }
                for record in hooks
            ]
        }

    def list_event_subscriptions(self) -> dict[str, object]:
        snapshot = self.sync_catalog()
        installs_by_id = {record.id: record for record in snapshot.installs}
        with self.runtime.session_scope() as session:
            subscriptions = ModuleStateRepository(session).list_subscriptions()
        return {
            "subscriptions": [
                {
                    **record.model_dump(by_alias=True, mode="json"),
                    "moduleId": installs_by_id[record.module_install_id].module_id,
                }
                for record in subscriptions
            ]
        }

    def list_health_reports(self) -> dict[str, object]:
        snapshot = self.sync_catalog()
        installs_by_id = {record.id: record for record in snapshot.installs}
        with self.runtime.session_scope() as session:
            health_reports = ModuleStateRepository(session).list_health_reports()
        return {
            "health": [
                {
                    **record.model_dump(by_alias=True, mode="json"),
                    "moduleId": installs_by_id[record.module_install_id].module_id,
                }
                for record in health_reports
            ]
        }

    def list_config_bindings(self) -> dict[str, object]:
        snapshot = self.sync_catalog()
        installs_by_id = {record.id: record for record in snapshot.installs}
        with self.runtime.session_scope() as session:
            bindings = ModuleStateRepository(session).list_config_bindings()
        return {
            "configBindings": [
                {
                    **record.model_dump(by_alias=True, mode="json"),
                    "moduleId": installs_by_id[record.module_install_id].module_id,
                }
                for record in bindings
            ]
        }

    def publish_pending_events(self, *, limit: int = 100) -> dict[str, object]:
        return OutboxPublisher(
            workspace_root=self.workspace_root,
            runtime=self.runtime,
            event_bus=self.event_bus,
        ).publish_pending(limit=limit)

    def consume_events(
        self,
        *,
        module_id: str | None = None,
        limit: int = 10,
        timeout_seconds: int = 1,
    ) -> dict[str, object]:
        snapshot = self.sync_catalog()
        manifests_by_module_id = {manifest.module_id: manifest for manifest in snapshot.manifests}
        installs_by_id = {record.id: record for record in snapshot.installs}
        subscriptions = [record for record in snapshot.subscriptions if record.status == "active"]
        if module_id is not None:
            subscriptions = [
                record
                for record in subscriptions
                if installs_by_id[record.module_install_id].module_id == module_id
            ]

        results: list[dict[str, object]] = []
        emitted = 0
        handled = 0
        ignored = 0
        failed = 0
        for subscription in subscriptions:
            install = installs_by_id[subscription.module_install_id]
            manifest = manifests_by_module_id[install.module_id]
            plugin = self._load_plugin(manifest)
            local_result = {"handled": 0, "ignored": 0, "failed": 0, "emitted": 0}

            def _handler(envelope: EventEnvelope) -> bool:
                nonlocal handled, ignored, failed, emitted
                outcome = self._dispatch_event(plugin, manifest, install, envelope)
                if outcome["status"] == "handled":
                    local_result["handled"] += 1
                    handled += 1
                elif outcome["status"] == "ignored":
                    local_result["ignored"] += 1
                    ignored += 1
                else:
                    local_result["failed"] += 1
                    failed += 1
                local_result["emitted"] += int(outcome.get("emitted", 0))
                emitted += int(outcome.get("emitted", 0))
                return bool(outcome["ack"])

            consume_result = self.event_bus.consume(
                event_type=subscription.event_type,
                consumer_group=subscription.consumer_group,
                batch=limit,
                timeout_seconds=timeout_seconds,
                handler=_handler,
            )
            results.append(
                {
                    "moduleId": install.module_id,
                    "eventType": subscription.event_type,
                    "consumerGroup": subscription.consumer_group,
                    "consumeResult": consume_result,
                    **local_result,
                }
            )

        return {
            "status": "ok",
            "handled": handled,
            "ignored": ignored,
            "failed": failed,
            "emitted": emitted,
            "subscriptions": results,
        }

    def health_report(self) -> dict[str, object]:
        snapshot = self.sync_catalog()
        return {
            "status": "ok",
            "database": self.runtime.ping_database(),
            "nats": self.event_bus.ping(),
            "modules": len(snapshot.installs),
            "active": len([record for record in snapshot.installs if record.lifecycle_state == "active"]),
            "degraded": len([record for record in snapshot.installs if record.lifecycle_state == "degraded"]),
            "quarantined": len([record for record in snapshot.installs if record.lifecycle_state == "quarantined"]),
        }

    def _sync_manifest_record(
        self,
        repository: ModuleStateRepository,
        outbox: OutboxRepository,
        existing: ModuleInstallRecord | None,
        manifest: ModuleManifestSummary,
        desired_state: str,
        compatibility_error: str | None,
    ) -> ModuleInstallRecord:
        manifest_ref = ExternalRef(type="file", locator=manifest.manifest_path)
        if existing is None:
            install = repository.upsert_module_install(
                ModuleInstallRecord(
                    id=new_id("modins", manifest.module_id, manifest.version, stable=True),
                    moduleId=manifest.module_id,
                    moduleVersion=manifest.version,
                    desiredState=desired_state,
                    lifecycleState="incompatible" if compatibility_error else "discovered",
                    runtimeMode=manifest.runtime_mode,
                    manifestRef=manifest_ref,
                    configBindingId=None,
                    installedAt=None,
                    enabledAt=None,
                    disabledAt=None,
                    lastError=compatibility_error,
                )
            )
            self._record_event(
                outbox,
                aggregate_type="module",
                aggregate_id=manifest.module_id,
                event_type="module.discovered",
                payload={
                    "moduleId": manifest.module_id,
                    "moduleVersion": manifest.version,
                    "desiredState": desired_state,
                    "runtimeMode": manifest.runtime_mode,
                },
            )
            return install

        lifecycle_state = existing.lifecycle_state
        if existing.module_version != manifest.version and lifecycle_state not in {"removed", "quarantined"}:
            lifecycle_state = "discovered"
        return repository.upsert_module_install(
            existing.model_copy(
                update={
                    "module_version": manifest.version,
                    "desired_state": desired_state,
                    "runtime_mode": manifest.runtime_mode,
                    "manifest_ref": manifest_ref,
                    "lifecycle_state": "incompatible" if compatibility_error else lifecycle_state,
                    "last_error": compatibility_error,
                }
            )
        )

    def _apply_incompatible_state(self, repository: ModuleStateRepository, install: ModuleInstallRecord, detail: str) -> None:
        repository.transition_lifecycle(install.module_id, "incompatible", last_error=detail)
        repository.set_runtime_contributions_active(install.id, enabled=False)
        repository.upsert_health_report(
            HealthReport(
                id=new_id("health", install.id, stable=True),
                moduleInstallId=install.id,
                status="unhealthy",
                summary="Module failed compatibility validation.",
                detailsRef=self._write_health_details(
                    install.module_id,
                    {"failureCount": 0, "status": "unhealthy", "detail": detail},
                ),
                observedAt=utc_now(),
            )
        )

    def _validate_module(
        self,
        repository: ModuleStateRepository,
        outbox: OutboxRepository,
        install: ModuleInstallRecord,
        manifest: ModuleManifestSummary,
    ) -> ModuleInstallRecord:
        if install.lifecycle_state not in {"discovered", "failed", "removed", "incompatible"} and install.installed_at is not None:
            return install
        try:
            plugin = self._load_plugin(manifest)
            registrations = {registration.name: registration for registration in plugin.register_hooks()}
            validation_hook = registrations.get(HookNames.MODULE_INSTALL_VALIDATE)
            if validation_hook is not None:
                result = validation_hook.handler(
                    {
                        "moduleId": install.module_id,
                        "manifest": manifest.model_dump(by_alias=True),
                        "desiredState": install.desired_state,
                    }
                ) or {}
                if isinstance(result, dict) and str(result.get("status", "ok")).lower() in {"error", "failed"}:
                    raise RuntimeError(str(result.get("summary") or result.get("detail") or "Module validation failed."))
            updated = repository.transition_lifecycle(install.module_id, "validated", last_error=None)
            return updated
        except Exception as exc:
            return self._record_failure(repository, outbox, install, f"Validation failed: {exc}")

    def _install_module(
        self,
        repository: ModuleStateRepository,
        install: ModuleInstallRecord,
        manifest: ModuleManifestSummary,
    ) -> ModuleInstallRecord:
        self._ensure_config_binding(repository, install, manifest)
        current = repository.get_module_install(install.module_id) or install
        if current.installed_at is None or current.lifecycle_state in {"validated", "discovered"}:
            current = repository.upsert_module_install(
                current.model_copy(update={"installed_at": utc_now()})
            )
        if current.lifecycle_state not in {"installed", "disabled", "active", "degraded", "quarantined"}:
            current = repository.transition_lifecycle(current.module_id, "installed", last_error=None)
        if current.desired_state == "disabled" and current.lifecycle_state in {"installed", "validated"}:
            current = repository.transition_lifecycle(current.module_id, "disabled", last_error=None)
        return current

    def _enable_module(
        self,
        repository: ModuleStateRepository,
        outbox: OutboxRepository,
        install: ModuleInstallRecord,
        manifest: ModuleManifestSummary,
    ) -> ModuleInstallRecord:
        current = repository.get_module_install(install.module_id) or install
        if current.lifecycle_state == "quarantined":
            return current
        reloading = current.lifecycle_state not in {"active", "degraded"}
        try:
            plugin = self._load_plugin(manifest)
            registrations = tuple(plugin.register_hooks())
            if reloading:
                current = repository.transition_lifecycle(current.module_id, "enabling", last_error=None)
            preflight = self._find_hook(registrations, HookNames.MODULE_ENABLE_PREFLIGHT)
            if preflight is not None:
                result = preflight.handler(self._lifecycle_payload(manifest, current)) or {}
                if isinstance(result, dict) and str(result.get("status", "ok")).lower() in {"error", "failed"}:
                    raise RuntimeError(str(result.get("summary") or result.get("detail") or "Module preflight failed."))

            repository.replace_hook_contributions(current.id, self._build_hook_records(current, manifest, registrations, enabled=True))
            repository.replace_event_subscriptions(current.id, self._build_subscription_records(current, manifest, enabled=True))
            repository.set_runtime_contributions_active(current.id, enabled=True)
            health_report = self._build_health_report(current, manifest, registrations)
            repository.upsert_health_report(health_report)

            if health_report.status == "degraded":
                current = repository.transition_lifecycle(current.module_id, "degraded", last_error=None)
                self._record_event(
                    outbox,
                    aggregate_type="module",
                    aggregate_id=current.module_id,
                    event_type="module.degraded",
                    payload={"moduleId": current.module_id, "summary": health_report.summary},
                )
            elif health_report.status in {"unhealthy", "quarantined"}:
                return self._record_failure(repository, outbox, current, health_report.summary)
            else:
                previous_state = current.lifecycle_state
                current = repository.transition_lifecycle(current.module_id, "active", last_error=None)
                if previous_state != "active":
                    self._record_event(
                        outbox,
                        aggregate_type="module",
                        aggregate_id=current.module_id,
                        event_type="module.enabled",
                        payload={"moduleId": current.module_id, "summary": health_report.summary},
                    )
            self._write_health_details(current.module_id, {"failureCount": 0, "status": health_report.status, "summary": health_report.summary})
            post_activate = self._find_hook(registrations, HookNames.MODULE_ENABLE_POST_ACTIVATE)
            if post_activate is not None:
                post_activate.handler(self._lifecycle_payload(manifest, current))
            return current
        except Exception as exc:
            return self._record_failure(repository, outbox, current, f"Enable failed: {exc}")

    def _disable_module(
        self,
        repository: ModuleStateRepository,
        outbox: OutboxRepository,
        install: ModuleInstallRecord,
        manifest: ModuleManifestSummary,
    ) -> ModuleInstallRecord:
        current = repository.get_module_install(install.module_id) or install
        if current.lifecycle_state == "disabled":
            repository.set_runtime_contributions_active(current.id, enabled=False)
            return current
        registrations: tuple[HookRegistration, ...] = ()
        try:
            plugin = self._load_plugin(manifest)
            registrations = tuple(plugin.register_hooks())
        except Exception:
            registrations = ()
        pre_drain = self._find_hook(registrations, HookNames.MODULE_DISABLE_PRE_DRAIN)
        if pre_drain is not None:
            pre_drain.handler(self._lifecycle_payload(manifest, current))
        if current.lifecycle_state in {"active", "degraded", "enabling", "failed"}:
            current = repository.transition_lifecycle(current.module_id, "draining", last_error=None)
        repository.set_runtime_contributions_active(current.id, enabled=False)
        repository.replace_event_subscriptions(current.id, self._build_subscription_records(current, manifest, enabled=False))
        repository.upsert_health_report(
            HealthReport(
                id=new_id("health", current.id, stable=True),
                moduleInstallId=current.id,
                status="healthy",
                summary="Module is installed and disabled.",
                detailsRef=self._health_details_ref(current.module_id),
                observedAt=utc_now(),
            )
        )
        post_stop = self._find_hook(registrations, HookNames.MODULE_DISABLE_POST_STOP)
        if post_stop is not None:
            post_stop.handler(self._lifecycle_payload(manifest, current))
        previous_state = current.lifecycle_state
        current = repository.transition_lifecycle(current.module_id, "disabled", last_error=None)
        if previous_state != "disabled":
            self._record_event(
                outbox,
                aggregate_type="module",
                aggregate_id=current.module_id,
                event_type="module.disabled",
                payload={"moduleId": current.module_id, "summary": "Module disabled."},
            )
        return current

    def _remove_module(
        self,
        repository: ModuleStateRepository,
        outbox: OutboxRepository,
        install: ModuleInstallRecord,
    ) -> None:
        current = repository.get_module_install(install.module_id) or install
        if current.lifecycle_state in {"active", "degraded", "enabling"}:
            current = repository.transition_lifecycle(current.module_id, "draining", last_error=None)
        repository.set_runtime_contributions_active(current.id, enabled=False)
        current = repository.transition_lifecycle(current.module_id, "uninstalling", last_error=None)
        current = repository.transition_lifecycle(current.module_id, "removed", last_error="Manifest no longer discovered.")
        self._record_event(
            outbox,
            aggregate_type="module",
            aggregate_id=current.module_id,
            event_type="module.removed",
            payload={"moduleId": current.module_id, "summary": "Manifest removed from catalog."},
        )

    def _dispatch_event(
        self,
        plugin,
        manifest: ModuleManifestSummary,
        install: ModuleInstallRecord,
        envelope: EventEnvelope,
    ) -> dict[str, object]:
        try:
            result = EventHandlingResult.model_validate(plugin.handle_event(envelope))
        except Exception as exc:
            with self.runtime.session_scope() as session:
                repository = ModuleStateRepository(session)
                outbox = OutboxRepository(session)
                self._record_failure(repository, outbox, install, f"Event handling failed: {exc}")
            return {"status": "failed", "ack": False, "emitted": 0}

        emitted = 0
        with self.runtime.session_scope() as session:
            repository = ModuleStateRepository(session)
            outbox = OutboxRepository(session)
            current = repository.get_module_install(install.module_id) or install
            if result.health_status is not None:
                repository.upsert_health_report(
                    HealthReport(
                        id=new_id("health", current.id, stable=True),
                        moduleInstallId=current.id,
                        status=result.health_status,
                        summary=result.summary or f"Module handled {envelope.event_type}.",
                        detailsRef=self._health_details_ref(current.module_id),
                        observedAt=utc_now(),
                    )
                )
                if result.health_status == "degraded":
                    repository.transition_lifecycle(current.module_id, "degraded", last_error=None)
                if result.health_status in {"unhealthy", "quarantined"}:
                    self._record_failure(repository, outbox, current, result.summary or f"{envelope.event_type} failed.")
                    return {"status": "failed", "ack": False, "emitted": 0}
            for emission in result.emitted_events:
                self._record_emission(outbox, current, envelope, emission)
                emitted += 1
        return {
            "status": result.status,
            "ack": result.status in {"handled", "ignored"},
            "emitted": emitted,
        }

    def _record_failure(
        self,
        repository: ModuleStateRepository,
        outbox: OutboxRepository,
        install: ModuleInstallRecord,
        reason: str,
    ) -> ModuleInstallRecord:
        details = self._read_health_details(install.module_id)
        failure_count = int(details.get("failureCount", 0)) + 1
        status = "quarantined" if failure_count >= self.runtime.settings.module_failure_threshold else "unhealthy"
        details_ref = self._write_health_details(
            install.module_id,
            {
                "failureCount": failure_count,
                "status": status,
                "summary": reason,
            },
        )
        repository.upsert_health_report(
            HealthReport(
                id=new_id("health", install.id, stable=True),
                moduleInstallId=install.id,
                status=status,
                summary=reason,
                detailsRef=details_ref,
                observedAt=utc_now(),
            )
        )
        repository.set_runtime_contributions_active(install.id, enabled=False)
        if status == "quarantined":
            updated = repository.transition_lifecycle(install.module_id, "quarantined", last_error=reason)
            self._record_event(
                outbox,
                aggregate_type="module",
                aggregate_id=install.module_id,
                event_type="module.quarantined",
                payload={
                    "moduleId": install.module_id,
                    "failureCount": failure_count,
                    "summary": reason,
                },
            )
            return updated
        return repository.transition_lifecycle(install.module_id, "failed", last_error=reason)

    def _ensure_config_binding(
        self,
        repository: ModuleStateRepository,
        install: ModuleInstallRecord,
        manifest: ModuleManifestSummary,
    ) -> ModuleConfigBinding:
        existing = repository.get_config_binding(module_install_id=install.id)
        config_dir = ensure_state_subdir("module-config", self.workspace_root)
        config_path = config_dir / f"{install.module_id}.json"
        if not config_path.exists():
            write_json(config_path, {})
        record = ModuleConfigBinding(
            id=existing.id if existing is not None else new_id("modcfg", install.module_id, stable=True),
            moduleInstallId=install.id,
            configSchemaVersion=manifest.version,
            effectiveConfigRef=ExternalRef(type="file", locator=relative_workspace_path(config_path, self.workspace_root)),
            sourceMode="database-primary-file-overlay",
            updatedAt=utc_now(),
            updatedBy=MODULE_HOST_ACTOR,
        )
        return repository.upsert_config_binding(record)

    def _build_hook_records(
        self,
        install: ModuleInstallRecord,
        manifest: ModuleManifestSummary,
        registrations: tuple[HookRegistration, ...],
        *,
        enabled: bool,
    ) -> list[HookContributionRecord]:
        return [
            HookContributionRecord(
                id=new_id("hookreg", install.id, registration.name, stable=True),
                moduleInstallId=install.id,
                hookName=registration.name,
                implementationRef=f"{manifest.entry_point or manifest.module_id}#{registration.name}",
                executionOrder=registration.order,
                timeoutMs=registration.timeout_ms,
                sideEffects=registration.side_effects,
                enabled=enabled,
                createdAt=utc_now(),
            )
            for registration in registrations
        ]

    def _build_subscription_records(
        self,
        install: ModuleInstallRecord,
        manifest: ModuleManifestSummary,
        *,
        enabled: bool,
    ) -> list[EventSubscriptionRecord]:
        return [
            EventSubscriptionRecord(
                id=new_id("evtreg", install.id, event_type, stable=True),
                moduleInstallId=install.id,
                eventType=event_type,
                consumerGroup=f"{install.module_id}.{event_type.replace('.', '-')}",
                deliveryMode="at-least-once",
                status="active" if enabled else "paused",
                createdAt=utc_now(),
                updatedAt=utc_now(),
            )
            for event_type in manifest.subscribes
        ]

    def _build_health_report(
        self,
        install: ModuleInstallRecord,
        manifest: ModuleManifestSummary,
        registrations: tuple[HookRegistration, ...],
    ) -> HealthReport:
        health_hook = self._find_hook(registrations, HookNames.MODULE_HEALTH_REPORT)
        status = "healthy"
        summary = f"{manifest.display_name} is active."
        details_ref = self._health_details_ref(install.module_id)
        if health_hook is not None:
            result = health_hook.handler(self._lifecycle_payload(manifest, install)) or {}
            if isinstance(result, dict):
                status = str(result.get("status") or status)
                summary = str(result.get("summary") or summary)
                if isinstance(result.get("details"), dict):
                    details_ref = self._write_health_details(install.module_id, result["details"])
        return HealthReport(
            id=new_id("health", install.id, stable=True),
            moduleInstallId=install.id,
            status=status,
            summary=summary,
            detailsRef=details_ref,
            observedAt=utc_now(),
        )

    def _record_emission(
        self,
        outbox: OutboxRepository,
        install: ModuleInstallRecord,
        envelope: EventEnvelope,
        emission: ModuleEventEmission,
    ) -> None:
        self._record_event(
            outbox,
            aggregate_type=emission.aggregate_type,
            aggregate_id=emission.aggregate_id,
            event_type=emission.event_type,
            payload=emission.payload,
            source=emission.source or install.module_id,
            project_id=emission.project_id or envelope.project_id,
            space_id=emission.space_id or envelope.space_id,
            branch_id=emission.branch_id or envelope.branch_id,
            task_id=emission.task_id or envelope.task_id,
            agent_run_id=emission.agent_run_id or envelope.agent_run_id,
            correlation_id=emission.correlation_id or envelope.correlation_id,
            causation_id=emission.causation_id or envelope.event_id,
            schema_ref=emission.schema_ref,
            event_version=emission.event_version,
        )

    def _record_event(
        self,
        outbox: OutboxRepository,
        *,
        aggregate_type: str,
        aggregate_id: str,
        event_type: str,
        payload: dict[str, Any],
        source: str = "module-host",
        project_id: str = DEFAULT_PROJECT_ID,
        space_id: str | None = DEFAULT_SPACE_ID,
        branch_id: str | None = DEFAULT_BRANCH_ID,
        task_id: str | None = None,
        agent_run_id: str | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        schema_ref: str | None = None,
        event_version: int = 1,
    ) -> None:
        event_id = new_id("evt", event_type, aggregate_id, utc_now().isoformat())
        envelope = EventEnvelope(
            eventType=event_type,
            eventVersion=event_version,
            eventId=event_id,
            occurredAt=utc_now(),
            source=source,
            actor=MODULE_HOST_ACTOR,
            projectId=project_id,
            spaceId=space_id,
            branchId=branch_id,
            taskId=task_id,
            agentRunId=agent_run_id,
            correlationId=correlation_id or event_id,
            causationId=causation_id,
            schemaRef=schema_ref or f"yggdrasil://events/{event_type}/v{event_version}",
            payload=payload,
        )
        payload_ref = event_payload_ref(envelope, self.workspace_root)
        outbox.record_event(
            {
                "id": event_id,
                "projectId": project_id,
                "aggregateType": aggregate_type,
                "aggregateId": aggregate_id,
                "eventType": event_type,
                "eventVersion": event_version,
                "payloadRef": payload_ref.model_dump(by_alias=True, mode="json"),
                "publishStatus": "pending",
                "createdAt": envelope.occurred_at,
                "availableAt": envelope.occurred_at,
            }
        )

    def _load_plugin(self, manifest: ModuleManifestSummary):
        if manifest.runtime_mode != "in-process" or not manifest.entry_point:
            raise RuntimeError(f"Unsupported runtime mode for {manifest.module_id}: {manifest.runtime_mode}")
        return load_in_process_plugin(manifest.entry_point)

    def _find_hook(self, registrations: tuple[HookRegistration, ...], name: str) -> HookRegistration | None:
        for registration in registrations:
            if registration.name == name:
                return registration
        return None

    def _lifecycle_payload(self, manifest: ModuleManifestSummary, install: ModuleInstallRecord) -> dict[str, object]:
        return {
            "moduleId": install.module_id,
            "install": install.model_dump(by_alias=True, mode="json"),
            "manifest": manifest.model_dump(by_alias=True),
            "workspaceRoot": str(self.workspace_root),
        }

    def _health_details_ref(self, module_id: str) -> ExternalRef:
        details_dir = ensure_state_subdir("module-health", self.workspace_root)
        details_path = details_dir / f"{module_id}.json"
        if not details_path.exists():
            write_json(details_path, {"failureCount": 0, "status": "healthy"})
        return ExternalRef(type="file", locator=relative_workspace_path(details_path, self.workspace_root))

    def _persist_desired_state(self, module_id: str, desired_state: str) -> None:
        state_dir = ensure_state_dir(self.workspace_root)
        profile_path = state_dir / "module-profile.json"
        profile = read_json(profile_path, {"_defaults": {"desiredState": "enabled"}})
        if not isinstance(profile, dict):
            profile = {"_defaults": {"desiredState": "enabled"}}
        profile[module_id] = {"desiredState": desired_state}
        write_json(profile_path, profile)

    def _read_health_details(self, module_id: str) -> dict[str, Any]:
        details_dir = ensure_state_subdir("module-health", self.workspace_root)
        details_path = details_dir / f"{module_id}.json"
        payload = read_json(details_path, {"failureCount": 0, "status": "healthy"})
        return payload if isinstance(payload, dict) else {"failureCount": 0, "status": "healthy"}

    def _write_health_details(self, module_id: str, payload: dict[str, Any]) -> ExternalRef:
        details_dir = ensure_state_subdir("module-health", self.workspace_root)
        details_path = details_dir / f"{module_id}.json"
        write_json(details_path, payload)
        return ExternalRef(type="file", locator=relative_workspace_path(details_path, self.workspace_root))