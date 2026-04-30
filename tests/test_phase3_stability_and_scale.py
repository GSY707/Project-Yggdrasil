"""
Phase 3 tests: Stability and Boundary Testing.

Tests cover:
- Scale: 1000-node tree retrieval latency benchmark
- Scale: 100k-word fragment import memory and time upper bound
- Concurrency: two workers simultaneously pausing the same task produce no double snapshot
- Concurrency: sub-agents concurrently writing to the same space produce no data race
- Hook fault isolation: one module hook exception does not affect other modules or the main flow
"""

from __future__ import annotations

import threading
import time
import tracemalloc
from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from yggdrasil_agent_runtime.runtime import prepare_pause_snapshot
from yggdrasil_sdk import TaskRepository, get_persistence_runtime
from yggdrasil_sdk.contracts import ExternalRef, ModuleCatalogSnapshot, ModuleInstallRecord, ModuleManifestSummary
from yggdrasil_sdk.hook_runtime import collect_hook_results
from yggdrasil_sdk.hooks import HookNames
from yggdrasil_sdk.module import BaseModulePlugin, HookRegistration
from yggdrasil_sdk.persistence.constants import DEFAULT_APP_ID, DEFAULT_BRANCH_ID, DEFAULT_PROJECT_ID, DEFAULT_SPACE_ID
from yggdrasil_sdk.persistence.repositories import MemoryRepository, NodeRepository, WorkspaceBootstrapRepository
from yggdrasil_sdk.support import utc_now


pytestmark = pytest.mark.slow


# ---------------------------------------------------------------------------
# Scale test helpers
# ---------------------------------------------------------------------------

def _bulk_create_nodes(
    node_repo: NodeRepository,
    *,
    branch_id: str = DEFAULT_BRANCH_ID,
    space_id: str = DEFAULT_SPACE_ID,
    count: int = 100,
    prefix: str = "node",
) -> list[str]:
    """Create `count` nodes and return their IDs."""
    ids: list[str] = []
    for i in range(count):
        node = node_repo.create_node(
            {
                "projectId": DEFAULT_PROJECT_ID,
                "spaceId": space_id,
                "branchId": branch_id,
                "nodeType": "detail",
                "title": f"{prefix}-{i}",
                "content": f"Content for node {i}. " * 10,
                "importance": 0.5,
            }
        )
        ids.append(node.id)
    return ids


# ---------------------------------------------------------------------------
# 1. Scale: 1000-node tree retrieval latency benchmark
# ---------------------------------------------------------------------------

RETRIEVAL_LATENCY_THRESHOLD_S = 5.0  # generous threshold for test environments


def test_scale_1000_node_tree_retrieval_latency() -> None:
    """
    Phase 3 scale test: 1000 nodes in a branch must be retrievable within
    RETRIEVAL_LATENCY_THRESHOLD_S seconds.

    Inserts 1000 nodes into the default branch, then measures the wall-clock
    time of a full list_nodes scan and a sample of get_node lookups.
    """
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        node_repo = NodeRepository(session)
        node_ids = _bulk_create_nodes(node_repo, count=1000, prefix="scale-node")

    # Measure list_nodes latency (full scan of 1000 records)
    with runtime.session_scope() as session:
        node_repo = NodeRepository(session)
        t_start = time.perf_counter()
        nodes = node_repo.list_nodes(branch_id=DEFAULT_BRANCH_ID, limit=1000)
        list_latency = time.perf_counter() - t_start

    assert len(nodes) >= 1000, "Expected at least 1000 nodes in branch"
    assert list_latency < RETRIEVAL_LATENCY_THRESHOLD_S, (
        f"list_nodes over 1000 nodes took {list_latency:.3f}s, "
        f"exceeds threshold of {RETRIEVAL_LATENCY_THRESHOLD_S}s"
    )

    # Measure get_node latency over a 50-node sample
    sample_ids = node_ids[::20]  # every 20th node → 50 samples
    with runtime.session_scope() as session:
        node_repo = NodeRepository(session)
        t_start = time.perf_counter()
        for node_id in sample_ids:
            result = node_repo.get_node(node_id)
            assert result is not None, f"Node {node_id} should be retrievable"
        sample_latency = time.perf_counter() - t_start

    assert sample_latency < RETRIEVAL_LATENCY_THRESHOLD_S, (
        f"50 get_node lookups took {sample_latency:.3f}s, "
        f"exceeds threshold of {RETRIEVAL_LATENCY_THRESHOLD_S}s"
    )


# ---------------------------------------------------------------------------
# 2. Scale: 100k-word fragment import memory and time upper bound
# ---------------------------------------------------------------------------

FRAGMENT_IMPORT_TIME_THRESHOLD_S = 30.0  # seconds
FRAGMENT_IMPORT_MEMORY_THRESHOLD_MB = 200.0  # megabytes


def test_scale_100k_word_fragment_import_memory_and_time() -> None:
    """
    Phase 3 scale test: importing ~100k words worth of fragments must complete
    within FRAGMENT_IMPORT_TIME_THRESHOLD_S and stay under
    FRAGMENT_IMPORT_MEMORY_THRESHOLD_MB of peak memory.

    Uses 1000 fragments × ~100 words each = ~100k words total.
    """
    WORDS_PER_FRAGMENT = 100
    FRAGMENT_COUNT = 1000

    word_base = "语义记忆内容 "  # 7 chars; approx 1 word
    fragment_text = word_base * WORDS_PER_FRAGMENT  # ~700 chars per fragment

    fragments = [
        {
            "ordinal": i + 1,
            "normalizedText": fragment_text,
            "approxTokens": len(fragment_text) // 4,
        }
        for i in range(FRAGMENT_COUNT)
    ]

    runtime = get_persistence_runtime()

    # Create import job
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        job = MemoryRepository(session).create_import_job(
            {
                "projectId": DEFAULT_PROJECT_ID,
                "branchId": DEFAULT_BRANCH_ID,
                "sourceKind": "stream",
                "status": "accepted",
            }
        )
        job_id = job.id

    # Measure import latency and peak memory
    tracemalloc.start()
    t_start = time.perf_counter()

    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        created_fragments = MemoryRepository(session).replace_import_fragments(job_id, fragments)

    elapsed = time.perf_counter() - t_start
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    peak_mb = peak_bytes / (1024 * 1024)

    assert len(created_fragments) == FRAGMENT_COUNT, (
        f"Expected {FRAGMENT_COUNT} fragments, got {len(created_fragments)}"
    )
    assert elapsed < FRAGMENT_IMPORT_TIME_THRESHOLD_S, (
        f"Fragment import took {elapsed:.2f}s, exceeds {FRAGMENT_IMPORT_TIME_THRESHOLD_S}s threshold"
    )
    assert peak_mb < FRAGMENT_IMPORT_MEMORY_THRESHOLD_MB, (
        f"Peak memory {peak_mb:.1f}MB exceeds {FRAGMENT_IMPORT_MEMORY_THRESHOLD_MB}MB threshold"
    )


# ---------------------------------------------------------------------------
# 3. Concurrency: two workers simultaneously pause same task → no double snapshot
# ---------------------------------------------------------------------------

def _seed_concurrent_task(task_id: str, run_ids: list[str]) -> None:
    """Seed a running task with multiple agent runs for the concurrent pause test."""
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repo = TaskRepository(session)
        task_repo.create_task(
            {
                "id": task_id,
                "appId": DEFAULT_APP_ID,
                "title": "并发暂停测试任务",
                "goal": "验证两个 worker 同时 pause 不产生双重快照。",
                "status": "running",
                "currentObjective": "验证并发安全",
                "currentFocus": "concurrent-pause",
                "budgetState": {"tokenBudgetTotal": 2000, "costBudgetTotal": 10.0},
            }
        )
        for run_id in run_ids:
            task_repo.create_agent_run(
                task_id,
                {
                    "id": run_id,
                    "status": "running",
                    "selectedModel": "gpt-5.4",
                    "selectedProvider": "copilot",
                },
            )


def test_concurrent_pause_same_task_no_double_snapshot() -> None:
    """
    Phase 3 concurrency test: two workers simultaneously calling prepare_pause_snapshot
    on the same task must not produce two active (non-superseded) snapshots.

    After both threads finish, the DB must be consistent:
      - task.active_snapshot_id points to a valid snapshot
      - at most one snapshot has a non-superseded status
    """
    task_id = "task_concurrent_pause"
    run_id_a = "run_concurrent_a"
    run_id_b = "run_concurrent_b"

    _seed_concurrent_task(task_id, [run_id_a, run_id_b])

    results: list[dict[str, Any]] = []
    errors: list[Exception] = []

    def pause_worker(run_id: str) -> None:
        try:
            result = prepare_pause_snapshot(
                task_id,
                {
                    "agentRunId": run_id,
                    "currentResponseState": "completed",
                    "pendingWrites": [],
                },
            )
            results.append(result)
        except Exception as exc:
            errors.append(exc)

    thread_a = threading.Thread(target=pause_worker, args=(run_id_a,))
    thread_b = threading.Thread(target=pause_worker, args=(run_id_b,))

    thread_a.start()
    thread_b.start()
    thread_a.join(timeout=10)
    thread_b.join(timeout=10)

    assert not errors, f"Unexpected exceptions during concurrent pause: {errors}"
    assert len(results) == 2, "Both workers should have completed (even if one failed to persist)"

    # Verify DB consistency: at most one non-superseded snapshot
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repo = TaskRepository(session)
        task = task_repo.get_task(task_id)
        assert task is not None

        snapshots = task_repo.list_snapshots(task_id)
        # Both threads attempted to create a snapshot; verify no double "active" state
        non_superseded = [s for s in snapshots if s.status not in {"superseded", "consumed"}]
        assert len(non_superseded) <= 1, (
            f"Expected at most 1 active snapshot, got {len(non_superseded)}: "
            f"{[s.id for s in non_superseded]}"
        )

        # If any snapshot was persisted, active_snapshot_id must be valid
        if non_superseded:
            active_id = task.active_snapshot_id
            assert active_id is not None
            active_snapshot = task_repo.get_snapshot(active_id)
            assert active_snapshot is not None, (
                f"active_snapshot_id {active_id} must point to an existing snapshot"
            )


# ---------------------------------------------------------------------------
# 4. Concurrency: sub-agents concurrently writing same space → no data race
# ---------------------------------------------------------------------------

CONCURRENT_WRITERS = 4
NODES_PER_WRITER = 25


def test_concurrent_subagent_space_writes_no_data_race() -> None:
    """
    Phase 3 concurrency test: CONCURRENT_WRITERS sub-agents simultaneously writing
    NODES_PER_WRITER nodes each to the same space/branch must produce all
    CONCURRENT_WRITERS × NODES_PER_WRITER nodes without data races or lost writes.
    """
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()

    created_ids: list[list[str]] = [[] for _ in range(CONCURRENT_WRITERS)]
    errors: list[Exception] = []

    def writer_thread(writer_idx: int) -> None:
        try:
            with runtime.session_scope() as session:
                node_repo = NodeRepository(session)
                ids = _bulk_create_nodes(
                    node_repo,
                    count=NODES_PER_WRITER,
                    prefix=f"concurrent-w{writer_idx}",
                )
                created_ids[writer_idx] = ids
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=writer_thread, args=(i,)) for i in range(CONCURRENT_WRITERS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert not errors, f"Unexpected exceptions during concurrent writes: {errors}"

    # Verify each writer's nodes are retrievable
    all_expected_ids = [node_id for ids in created_ids for node_id in ids]
    assert len(all_expected_ids) == CONCURRENT_WRITERS * NODES_PER_WRITER, (
        f"Expected {CONCURRENT_WRITERS * NODES_PER_WRITER} total nodes, "
        f"got {len(all_expected_ids)}"
    )

    with runtime.session_scope() as session:
        node_repo = NodeRepository(session)
        # Sample: verify every node created by each writer is individually retrievable
        missing = []
        for node_id in all_expected_ids:
            if node_repo.get_node(node_id) is None:
                missing.append(node_id)

    assert not missing, (
        f"{len(missing)} nodes were lost during concurrent writes: {missing[:5]}..."
    )

    # Verify total count in branch matches expectations (existing + new)
    with runtime.session_scope() as session:
        node_repo = NodeRepository(session)
        all_branch_nodes = node_repo.list_nodes(branch_id=DEFAULT_BRANCH_ID, limit=2000)
    new_node_titles = {n.title for n in all_branch_nodes if n.title.startswith("concurrent-w")}
    assert len(new_node_titles) == CONCURRENT_WRITERS * NODES_PER_WRITER, (
        f"Expected {CONCURRENT_WRITERS * NODES_PER_WRITER} new nodes by title, "
        f"found {len(new_node_titles)}"
    )


# ---------------------------------------------------------------------------
# 5. Hook fault isolation: one module hook exception does not propagate
# ---------------------------------------------------------------------------

class _FaultPlugin(BaseModulePlugin):
    """A fake plugin whose MEMORY_WRITE_VALIDATE hook always raises."""

    module_id = "test-fault-module"

    def manifest_path(self):  # type: ignore[override]
        from pathlib import Path
        return Path("test/fault")

    def register_hooks(self):
        def _raising_handler(payload: dict[str, Any]) -> None:
            raise RuntimeError("simulated-hook-failure-from-faulty-module")

        return (
            HookRegistration(
                name=HookNames.MEMORY_WRITE_VALIDATE,
                handler=_raising_handler,
                order=50,
            ),
        )


class _GoodPlugin(BaseModulePlugin):
    """A fake plugin whose MEMORY_WRITE_VALIDATE hook returns a valid result."""

    module_id = "test-good-module"

    def manifest_path(self):  # type: ignore[override]
        from pathlib import Path
        return Path("test/good")

    def register_hooks(self):
        def _ok_handler(payload: dict[str, Any]) -> dict[str, Any]:
            return {"status": "ok", "summary": "good-module-hook-executed", "allowed": True}

        return (
            HookRegistration(
                name=HookNames.MEMORY_WRITE_VALIDATE,
                handler=_ok_handler,
                order=100,
            ),
        )


def _build_fake_catalog_snapshot() -> ModuleCatalogSnapshot:
    now = utc_now()
    manifest_ref = ExternalRef(type="file", locator="test/manifest")

    manifest_fault = ModuleManifestSummary.model_validate(
        {
            "moduleId": "test-fault-module",
            "displayName": "Fault Module",
            "version": "0.1.0",
            "runtimeMode": "in-process",
            "manifestPath": "test/fault",
            "hooks": [HookNames.MEMORY_WRITE_VALIDATE],
            "entryPoint": "test_fault:FaultPlugin",
        }
    )
    manifest_good = ModuleManifestSummary.model_validate(
        {
            "moduleId": "test-good-module",
            "displayName": "Good Module",
            "version": "0.1.0",
            "runtimeMode": "in-process",
            "manifestPath": "test/good",
            "hooks": [HookNames.MEMORY_WRITE_VALIDATE],
            "entryPoint": "test_good:GoodPlugin",
        }
    )

    install_fault = ModuleInstallRecord.model_validate(
        {
            "id": "install-fault",
            "moduleId": "test-fault-module",
            "moduleVersion": "0.1.0",
            "desiredState": "enabled",
            "lifecycleState": "active",
            "runtimeMode": "in-process",
            "manifestRef": manifest_ref.model_dump(),
            "installedAt": now.isoformat(),
        }
    )
    install_good = ModuleInstallRecord.model_validate(
        {
            "id": "install-good",
            "moduleId": "test-good-module",
            "moduleVersion": "0.1.0",
            "desiredState": "enabled",
            "lifecycleState": "active",
            "runtimeMode": "in-process",
            "manifestRef": manifest_ref.model_dump(),
            "installedAt": now.isoformat(),
        }
    )

    return ModuleCatalogSnapshot.model_validate(
        {
            "generatedAt": now.isoformat(),
            "manifests": [
                manifest_fault.model_dump(by_alias=True),
                manifest_good.model_dump(by_alias=True),
            ],
            "installs": [
                install_fault.model_dump(by_alias=True),
                install_good.model_dump(by_alias=True),
            ],
            "hooks": [],
            "subscriptions": [],
            "health": [],
        }
    )


def test_hook_fault_isolation_one_module_exception() -> None:
    """
    Phase 3 hook fault isolation test: when one module's hook handler raises an
    exception, the error must be captured in the results, other modules' hooks must
    still execute, and the main flow must not propagate the exception.
    """
    fake_snapshot = _build_fake_catalog_snapshot()

    fault_plugin = _FaultPlugin()
    good_plugin = _GoodPlugin()

    def fake_loader(entry_point: str):
        if entry_point == "test_fault:FaultPlugin":
            return fault_plugin
        if entry_point == "test_good:GoodPlugin":
            return good_plugin
        raise ImportError(f"Unknown entry point in test: {entry_point}")

    with (
        patch("yggdrasil_sdk.hook_runtime.build_module_catalog_snapshot", return_value=fake_snapshot),
        patch("yggdrasil_sdk.hook_runtime.load_in_process_plugin", side_effect=fake_loader),
    ):
        # Must not raise despite the faulty module
        results = collect_hook_results(
            HookNames.MEMORY_WRITE_VALIDATE,
            {"targetSpaceId": DEFAULT_SPACE_ID, "targetBranchId": DEFAULT_BRANCH_ID},
        )

    # Two modules should have been invoked (one per manifest with this hook)
    assert len(results) == 2, f"Expected 2 results (one per module), got {len(results)}: {results}"

    error_entries = [r for r in results if r.get("error")]
    ok_entries = [r for r in results if not r.get("error")]

    # The faulty module's exception must be captured, not propagated
    assert len(error_entries) == 1, (
        f"Expected exactly 1 error entry, got {len(error_entries)}: {error_entries}"
    )
    assert "simulated-hook-failure-from-faulty-module" in error_entries[0]["error"]
    assert error_entries[0]["moduleId"] == "test-fault-module"

    # The good module must still have executed successfully
    assert len(ok_entries) == 1, (
        f"Expected exactly 1 successful entry, got {len(ok_entries)}: {ok_entries}"
    )
    assert ok_entries[0]["moduleId"] == "test-good-module"
    assert ok_entries[0]["result"].get("summary") == "good-module-hook-executed"
