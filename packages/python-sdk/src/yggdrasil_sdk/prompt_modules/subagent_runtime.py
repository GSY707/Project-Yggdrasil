from __future__ import annotations

from pathlib import Path

from ..hooks import HookNames
from ..module import BaseModulePlugin, HookRegistration
from .common import load_module_prompt_asset, module_manifest_path


class SubagentRuntimePromptModule(BaseModulePlugin):
    module_id = "subagent-runtime"

    def manifest_path(self) -> Path:
        return module_manifest_path(self.module_id)

    def register_hooks(self) -> tuple[HookRegistration, ...]:
        return (
            HookRegistration(name=HookNames.MODULE_ENABLE_PREFLIGHT, handler=self.enable_preflight),
            HookRegistration(name=HookNames.MODULE_HEALTH_REPORT, handler=self.report_health),
            HookRegistration(name=HookNames.PROMPT_PROFILES_REGISTER, handler=self.register_prompt_profiles),
        )

    def enable_preflight(self, payload: dict[str, object]) -> dict[str, object]:
        return {"status": "ok", "summary": "Subagent runtime prompt module preflight passed."}

    def report_health(self, payload: dict[str, object]) -> dict[str, object]:
        return {"status": "healthy", "summary": "Subagent runtime prompt module is ready."}

    def register_prompt_profiles(self, payload: dict[str, object]) -> dict[str, object]:
        return {
            "promptProfiles": [load_module_prompt_asset(self.module_id, "prompt-profiles/subagent.yaml")],
            "moduleId": self.module_id,
        }


plugin = SubagentRuntimePromptModule()