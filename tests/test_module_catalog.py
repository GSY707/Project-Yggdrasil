from yggdrasil_sdk import sync_module_catalog_snapshot
from yggdrasil_sdk.spec_catalog import list_spec_documents


def test_module_catalog_snapshot_contains_core_modules() -> None:
    snapshot = sync_module_catalog_snapshot()

    module_ids = {manifest.module_id for manifest in snapshot.manifests}
    assert {"text-memory", "context-pruning", "subagent-pr"}.issubset(module_ids)

    installs_by_module_id = {record.module_id: record for record in snapshot.installs}
    assert installs_by_module_id["text-memory"].desired_state == "enabled"
    assert installs_by_module_id["context-pruning"].lifecycle_state == "active"

    hook_names = {hook.hook_name for hook in snapshot.hooks}
    assert "memory.ingest.plan-tree" in hook_names
    assert "worker.activities.register" in hook_names


def test_spec_catalog_discovers_protocol_and_data_specs() -> None:
    documents = list_spec_documents()

    paths = {document.path for document in documents}
    assert "docs/PRD-v0.1.md" in paths
    assert "docs/protocols/hook-contracts-v0.1.md" in paths
    assert "docs/specs/runtime-domain-data-spec-v0.1.md" in paths

    categories = {document.category for document in documents}
    assert {"Product", "Protocol", "Data Spec"} <= categories