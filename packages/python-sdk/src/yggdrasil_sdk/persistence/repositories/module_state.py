from ._common import *  # noqa: F403,F401

class ModuleStateRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_module_installs(self) -> list[ModuleInstallRecord]:
        statement = sa.select(ModuleInstallORM).order_by(ModuleInstallORM.module_id.asc())
        return [_module_install_record(model) for model in self.session.execute(statement).scalars().all()]

    def get_module_install(self, module_id: str) -> ModuleInstallRecord | None:
        statement = sa.select(ModuleInstallORM).where(ModuleInstallORM.module_id == module_id)
        model = self.session.execute(statement).scalar_one_or_none()
        return _module_install_record(model) if model is not None else None

    def upsert_module_install(self, record: ModuleInstallRecord) -> ModuleInstallRecord:
        statement = sa.select(ModuleInstallORM).where(ModuleInstallORM.module_id == record.module_id)
        model = self.session.execute(statement).scalar_one_or_none()
        if model is None:
            model = ModuleInstallORM(id=record.id, module_id=record.module_id)
            self.session.add(model)
        model.module_version = record.module_version
        model.desired_state = record.desired_state
        model.lifecycle_state = record.lifecycle_state
        model.runtime_mode = record.runtime_mode
        model.manifest_ref = record.manifest_ref.model_dump(mode="json")
        model.config_binding_id = record.config_binding_id
        model.installed_at = record.installed_at
        model.enabled_at = record.enabled_at
        model.disabled_at = record.disabled_at
        model.last_error = record.last_error
        self.session.flush()
        return _module_install_record(model)

    def set_desired_state(self, module_id: str, desired_state: str) -> ModuleInstallRecord:
        statement = sa.select(ModuleInstallORM).where(ModuleInstallORM.module_id == module_id)
        model = self.session.execute(statement).scalar_one()
        model.desired_state = desired_state
        self.session.flush()
        return _module_install_record(model)

    def transition_lifecycle(
        self,
        module_id: str,
        lifecycle_state: str,
        *,
        last_error: str | None = None,
    ) -> ModuleInstallRecord:
        statement = sa.select(ModuleInstallORM).where(ModuleInstallORM.module_id == module_id)
        model = self.session.execute(statement).scalar_one()
        model.lifecycle_state = lifecycle_state
        model.last_error = last_error
        if lifecycle_state == "active":
            model.enabled_at = model.enabled_at or utc_now()
        if lifecycle_state in {"disabled", "removed"}:
            model.disabled_at = utc_now()
        self.session.flush()
        return _module_install_record(model)

    def list_config_bindings(self) -> list[ModuleConfigBinding]:
        statement = sa.select(ModuleConfigBindingORM).order_by(ModuleConfigBindingORM.module_install_id.asc())
        return [_module_config_binding_record(model) for model in self.session.execute(statement).scalars().all()]

    def get_config_binding(
        self,
        *,
        module_install_id: str | None = None,
        binding_id: str | None = None,
    ) -> ModuleConfigBinding | None:
        statement = sa.select(ModuleConfigBindingORM)
        if module_install_id is not None:
            statement = statement.where(ModuleConfigBindingORM.module_install_id == module_install_id)
        if binding_id is not None:
            statement = statement.where(ModuleConfigBindingORM.id == binding_id)
        model = self.session.execute(statement).scalar_one_or_none()
        return _module_config_binding_record(model) if model is not None else None

    def upsert_config_binding(self, record: ModuleConfigBinding) -> ModuleConfigBinding:
        statement = sa.select(ModuleConfigBindingORM).where(ModuleConfigBindingORM.module_install_id == record.module_install_id)
        model = self.session.execute(statement).scalar_one_or_none()
        if model is None:
            model = ModuleConfigBindingORM(id=record.id, module_install_id=record.module_install_id)
            self.session.add(model)
        model.config_schema_version = record.config_schema_version
        model.effective_config_ref = record.effective_config_ref.model_dump(mode="json")
        model.source_mode = record.source_mode
        model.updated_at = record.updated_at
        model.updated_by = record.updated_by.model_dump(mode="json")
        self.session.execute(
            sa.update(ModuleInstallORM)
            .where(ModuleInstallORM.id == record.module_install_id)
            .values(config_binding_id=record.id)
        )
        self.session.flush()
        return _module_config_binding_record(model)

    def list_hooks(self, *, module_install_id: str | None = None) -> list[HookContributionRecord]:
        statement = sa.select(HookContributionORM).order_by(HookContributionORM.execution_order.asc(), HookContributionORM.hook_name.asc())
        if module_install_id is not None:
            statement = statement.where(HookContributionORM.module_install_id == module_install_id)
        return [_hook_record(model) for model in self.session.execute(statement).scalars().all()]

    def replace_hook_contributions(self, module_install_id: str, records: list[HookContributionRecord]) -> list[HookContributionRecord]:
        self.session.execute(sa.delete(HookContributionORM).where(HookContributionORM.module_install_id == module_install_id))
        for record in records:
            self.session.add(
                HookContributionORM(
                    id=record.id,
                    module_install_id=record.module_install_id,
                    hook_name=record.hook_name,
                    implementation_ref=record.implementation_ref,
                    execution_order=record.execution_order,
                    timeout_ms=record.timeout_ms,
                    side_effects=record.side_effects,
                    enabled=record.enabled,
                    created_at=record.created_at,
                )
            )
        self.session.flush()
        return self.list_hooks(module_install_id=module_install_id)

    def list_subscriptions(
        self,
        *,
        module_install_id: str | None = None,
        status: str | None = None,
    ) -> list[EventSubscriptionRecord]:
        statement = sa.select(EventSubscriptionORM).order_by(EventSubscriptionORM.event_type.asc())
        if module_install_id is not None:
            statement = statement.where(EventSubscriptionORM.module_install_id == module_install_id)
        if status is not None:
            statement = statement.where(EventSubscriptionORM.status == status)
        return [_subscription_record(model) for model in self.session.execute(statement).scalars().all()]

    def replace_event_subscriptions(self, module_install_id: str, records: list[EventSubscriptionRecord]) -> list[EventSubscriptionRecord]:
        self.session.execute(sa.delete(EventSubscriptionORM).where(EventSubscriptionORM.module_install_id == module_install_id))
        for record in records:
            self.session.add(
                EventSubscriptionORM(
                    id=record.id,
                    module_install_id=record.module_install_id,
                    event_type=record.event_type,
                    consumer_group=record.consumer_group,
                    delivery_mode=record.delivery_mode,
                    status=record.status,
                    created_at=record.created_at,
                    updated_at=record.updated_at,
                )
            )
        self.session.flush()
        return self.list_subscriptions(module_install_id=module_install_id)

    def set_runtime_contributions_active(self, module_install_id: str, *, enabled: bool) -> None:
        self.session.execute(
            sa.update(HookContributionORM)
            .where(HookContributionORM.module_install_id == module_install_id)
            .values(enabled=enabled)
        )
        self.session.execute(
            sa.update(EventSubscriptionORM)
            .where(EventSubscriptionORM.module_install_id == module_install_id)
            .values(status="active" if enabled else "paused", updated_at=utc_now())
        )
        self.session.flush()

    def get_health_report(self, module_install_id: str) -> HealthReport | None:
        statement = sa.select(HealthReportORM).where(HealthReportORM.module_install_id == module_install_id)
        model = self.session.execute(statement).scalar_one_or_none()
        return _health_record(model) if model is not None else None

    def list_health_reports(self) -> list[HealthReport]:
        statement = sa.select(HealthReportORM).order_by(HealthReportORM.module_install_id.asc())
        return [_health_record(model) for model in self.session.execute(statement).scalars().all()]

    def upsert_health_report(self, record: HealthReport) -> HealthReport:
        statement = sa.select(HealthReportORM).where(HealthReportORM.module_install_id == record.module_install_id)
        model = self.session.execute(statement).scalar_one_or_none()
        if model is None:
            model = HealthReportORM(id=record.id, module_install_id=record.module_install_id)
            self.session.add(model)
        model.status = record.status
        model.summary = record.summary
        model.details_ref = record.details_ref.model_dump(mode="json") if record.details_ref else None
        model.observed_at = record.observed_at
        self.session.flush()
        return _health_record(model)

    def sync_snapshot(self, snapshot: ModuleCatalogSnapshot) -> None:
        generated_at = snapshot.generated_at
        current_module_ids = {record.module_id for record in snapshot.installs}
        existing_installs = {
            model.module_id: model
            for model in self.session.execute(sa.select(ModuleInstallORM)).scalars().all()
        }

        for record in snapshot.installs:
            model = existing_installs.get(record.module_id)
            if model is None:
                model = ModuleInstallORM(id=record.id, module_id=record.module_id)
                self.session.add(model)
            model.module_version = record.module_version
            model.desired_state = record.desired_state
            model.lifecycle_state = record.lifecycle_state
            model.runtime_mode = record.runtime_mode
            model.manifest_ref = record.manifest_ref.model_dump(mode="json")
            model.config_binding_id = record.config_binding_id
            model.installed_at = record.installed_at
            model.enabled_at = record.enabled_at
            model.disabled_at = record.disabled_at
            model.last_error = record.last_error

        for module_id, model in existing_installs.items():
            if module_id in current_module_ids:
                continue
            model.desired_state = "disabled"
            model.lifecycle_state = "removed"
            model.disabled_at = generated_at
            model.last_error = "Manifest no longer discovered."

        self.session.flush()
        install_ids = [record.id for record in snapshot.installs]
        if install_ids:
            for orm_model in (HookContributionORM, EventSubscriptionORM, HealthReportORM):
                self.session.execute(sa.delete(orm_model).where(orm_model.module_install_id.in_(install_ids)))

        for record in snapshot.hooks:
            self.session.add(
                HookContributionORM(
                    id=record.id,
                    module_install_id=record.module_install_id,
                    hook_name=record.hook_name,
                    implementation_ref=record.implementation_ref,
                    execution_order=record.execution_order,
                    timeout_ms=record.timeout_ms,
                    side_effects=record.side_effects,
                    enabled=record.enabled,
                    created_at=record.created_at,
                )
            )
        for record in snapshot.subscriptions:
            self.session.add(
                EventSubscriptionORM(
                    id=record.id,
                    module_install_id=record.module_install_id,
                    event_type=record.event_type,
                    consumer_group=record.consumer_group,
                    delivery_mode=record.delivery_mode,
                    status=record.status,
                    created_at=record.created_at,
                    updated_at=record.updated_at,
                )
            )
        for record in snapshot.health:
            self.session.add(
                HealthReportORM(
                    id=record.id,
                    module_install_id=record.module_install_id,
                    status=record.status,
                    summary=record.summary,
                    details_ref=record.details_ref.model_dump(mode="json") if record.details_ref else None,
                    observed_at=record.observed_at,
                )
            )
        self.session.flush()

    def build_snapshot(self, manifests: list[ModuleManifestSummary], generated_at: datetime) -> ModuleCatalogSnapshot:
        module_ids = [manifest.module_id for manifest in manifests]
        installs = self.session.execute(
            sa.select(ModuleInstallORM).where(ModuleInstallORM.module_id.in_(module_ids)).order_by(ModuleInstallORM.module_id.asc())
        ).scalars().all()
        install_ids = [record.id for record in installs]
        hooks = []
        subscriptions = []
        health = []
        if install_ids:
            hooks = self.session.execute(
                sa.select(HookContributionORM).where(HookContributionORM.module_install_id.in_(install_ids)).order_by(HookContributionORM.hook_name.asc())
            ).scalars().all()
            subscriptions = self.session.execute(
                sa.select(EventSubscriptionORM).where(EventSubscriptionORM.module_install_id.in_(install_ids)).order_by(EventSubscriptionORM.event_type.asc())
            ).scalars().all()
            health = self.session.execute(
                sa.select(HealthReportORM).where(HealthReportORM.module_install_id.in_(install_ids)).order_by(HealthReportORM.module_install_id.asc())
            ).scalars().all()
        return ModuleCatalogSnapshot(
            generatedAt=generated_at,
            manifests=manifests,
            installs=[_module_install_record(model) for model in installs],
            hooks=[_hook_record(model) for model in hooks],
            subscriptions=[_subscription_record(model) for model in subscriptions],
            health=[_health_record(model) for model in health],
        )


__all__ = [name for name in globals() if not name.startswith("__")]
