from __future__ import annotations

from pathlib import Path

from ..hooks import HookNames
from ..module import BaseModulePlugin, HookRegistration
from .common import load_module_prompt_asset, module_manifest_path


class CodingNewProjectSceneModule(BaseModulePlugin):
    module_id = "scene-coding-new-project"

    def manifest_path(self) -> Path:
        return module_manifest_path(self.module_id)

    def register_hooks(self) -> tuple[HookRegistration, ...]:
        return (
            HookRegistration(name=HookNames.MODULE_ENABLE_PREFLIGHT, handler=self.enable_preflight),
            HookRegistration(name=HookNames.MODULE_HEALTH_REPORT, handler=self.report_health),
            HookRegistration(name=HookNames.PROMPT_SEED_TEMPLATES_REGISTER, handler=self.register_seed_templates),
        )

    def enable_preflight(self, payload: dict[str, object]) -> dict[str, object]:
        return {"status": "ok", "summary": "Coding new-project scene module preflight passed."}

    def report_health(self, payload: dict[str, object]) -> dict[str, object]:
        return {"status": "healthy", "summary": "Coding new-project scene module is ready."}

    def register_seed_templates(self, payload: dict[str, object]) -> dict[str, object]:
        return {
            "seedTemplates": [load_module_prompt_asset(self.module_id, "scenes/coding-new-project.yaml")],
            "moduleId": self.module_id,
        }


plugin = CodingNewProjectSceneModule()