from __future__ import annotations

from pathlib import Path

from ..hooks import HookNames
from ..module import BaseModulePlugin, HookRegistration
from .common import load_module_prompt_asset, module_manifest_path


class ResearchDeepSceneModule(BaseModulePlugin):
    module_id = "scene-research-deep"

    def manifest_path(self) -> Path:
        return module_manifest_path(self.module_id)

    def register_hooks(self) -> tuple[HookRegistration, ...]:
        return (
            HookRegistration(name=HookNames.MODULE_ENABLE_PREFLIGHT, handler=self.enable_preflight),
            HookRegistration(name=HookNames.MODULE_HEALTH_REPORT, handler=self.report_health),
            HookRegistration(name=HookNames.PROMPT_SEED_TEMPLATES_REGISTER, handler=self.register_seed_templates),
        )

    def enable_preflight(self, payload: dict[str, object]) -> dict[str, object]:
        return {"status": "ok", "summary": "Research deep scene module preflight passed."}

    def report_health(self, payload: dict[str, object]) -> dict[str, object]:
        return {"status": "healthy", "summary": "Research deep scene module is ready."}

    def register_seed_templates(self, payload: dict[str, object]) -> dict[str, object]:
        return {
            "seedTemplates": [load_module_prompt_asset(self.module_id, "scenes/research-deep.yaml")],
            "moduleId": self.module_id,
        }


plugin = ResearchDeepSceneModule()