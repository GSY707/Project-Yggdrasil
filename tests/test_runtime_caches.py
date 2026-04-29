from yggdrasil_sdk.app_catalog import build_application_catalog_snapshot, invalidate_application_catalog_cache
from yggdrasil_sdk.catalog import invalidate_catalog_cache
from yggdrasil_sdk.prompting import assemble_prompt_registry, invalidate_prompt_registry_cache
from yggdrasil_sdk.tool_runtime import invalidate_tool_descriptor_cache, resolve_registered_tool_descriptors

import yggdrasil_sdk.app_catalog as app_catalog_module
import yggdrasil_sdk.prompting as prompting_module
import yggdrasil_sdk.tool_runtime as tool_runtime_module


def test_application_catalog_uses_process_cache(monkeypatch) -> None:
    invalidate_application_catalog_cache()
    calls = {"count": 0}
    original = app_catalog_module.discover_application_manifests

    def counting_discover(*args, **kwargs):
        calls["count"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(app_catalog_module, "discover_application_manifests", counting_discover)

    first = build_application_catalog_snapshot()
    second = build_application_catalog_snapshot()

    assert first.manifests
    assert second.manifests
    assert calls["count"] == 1


def test_assemble_prompt_registry_uses_process_cache(monkeypatch) -> None:
    invalidate_catalog_cache()
    invalidate_application_catalog_cache()
    invalidate_prompt_registry_cache()
    calls = {"count": 0}
    original = prompting_module.collect_hook_results

    def counting_collect(*args, **kwargs):
        calls["count"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(prompting_module, "collect_hook_results", counting_collect)

    first = assemble_prompt_registry(
        app_id="yggdrasil.app.software-factory",
        active_capabilities=["text-memory", "context-pruning", "mcp-bridge"],
    )
    second = assemble_prompt_registry(
        app_id="yggdrasil.app.software-factory",
        active_capabilities=["text-memory", "context-pruning", "mcp-bridge"],
    )

    assert first["promptProfiles"]
    assert second["seedTemplates"]
    assert calls["count"] == 2


def test_resolve_registered_tool_descriptors_uses_process_cache(monkeypatch) -> None:
    invalidate_catalog_cache()
    invalidate_tool_descriptor_cache()
    calls = {"count": 0}
    original = tool_runtime_module.load_in_process_plugin

    def counting_load(entry_point: str):
        calls["count"] += 1
        return original(entry_point)

    monkeypatch.setattr(tool_runtime_module, "load_in_process_plugin", counting_load)

    first = resolve_registered_tool_descriptors(["text-memory"])
    second = resolve_registered_tool_descriptors(["text-memory"])

    assert first == second
    assert calls["count"] == 1