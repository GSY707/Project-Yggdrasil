from __future__ import annotations

import os
from pathlib import Path
import subprocess

import pytest
import yggdrasil_sdk.observability_exporters as observability_exporters

from yggdrasil_sdk import TaskRepository, create_runtime_backup, get_persistence_runtime, restore_runtime_backup, run_evaluation_suite, summarize_observability
from yggdrasil_sdk.evaluation_runtime import isolated_runtime_environment
from yggdrasil_sdk.mcp_bridge import ensure_mcp_bridge_config
from yggdrasil_sdk.ops_runtime import prepare_real_user_validation_sandbox
from yggdrasil_sdk.persistence.repositories import WorkspaceBootstrapRepository
from yggdrasil_sdk.support import resolve_state_root


pytestmark = pytest.mark.slow


def _create_fake_validation_workspace(root: Path) -> Path:
    (root / "services").mkdir(parents=True, exist_ok=True)
    (root / "modules").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "research").mkdir(parents=True, exist_ok=True)
    (root / "evaluation" / "fixtures" / "real-user-validation").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text("# Fake Workspace\n", encoding="utf-8")
    (root / "package.json").write_text('{"name":"fake-workspace"}\n', encoding="utf-8")
    (root / "docs" / "research" / "real-user-validation-plan-2026-04-30.md").write_text("# Plan\n", encoding="utf-8")
    (root / "docs" / "research" / "real-user-validation-baseline-freeze-2026-04-30.md").write_text("# Baseline\n", encoding="utf-8")
    (root / "docs" / "research" / "real-user-validation-internal-pilot-deepseek-2026-04-30.md").write_text("# Pilot\n", encoding="utf-8")
    (root / "evaluation" / "fixtures" / "real-user-validation" / "task-pack-2026-04-30.md").write_text("# Task Pack\n", encoding="utf-8")
    (root / "evaluation" / "fixtures" / "real-user-validation" / "scorecard-template-2026-04-30.csv").write_text("score\n", encoding="utf-8")
    return root


def test_m8_benchmark_suite_produces_strategy_metrics() -> None:
    result = run_evaluation_suite("evalsuite_benchmark_m8_memory_strategies")

    assert result["run"]["status"] == "completed"
    metrics = result["metrics"]
    assert metrics["status"] == "completed"
    assert metrics["baselineComparisons"]
    leaderboard = metrics["strategyLeaderboard"]
    strategy_names = {row["name"] for row in leaderboard}
    assert {"no-memory", "vector-flat", "memory-tree"}.issubset(strategy_names)


def test_isolated_evaluation_environment_disables_live_llm_by_default(monkeypatch) -> None:
    monkeypatch.setenv("YGGDRASIL_DISABLE_LIVE_LLM", "0")

    with isolated_runtime_environment():
        assert os.environ["YGGDRASIL_DISABLE_LIVE_LLM"] == "1"

    assert os.environ["YGGDRASIL_DISABLE_LIVE_LLM"] == "0"


def test_isolated_evaluation_environment_can_allow_live_llm(monkeypatch) -> None:
    monkeypatch.delenv("YGGDRASIL_DISABLE_LIVE_LLM", raising=False)

    with isolated_runtime_environment(disable_live_llm=False):
        assert os.environ.get("YGGDRASIL_DISABLE_LIVE_LLM") is None


def test_isolated_evaluation_environment_redirects_workspace_writes() -> None:
    repo_root = Path(__file__).resolve().parents[1]

    with isolated_runtime_environment():
        config = ensure_mcp_bridge_config()
        project_workspace = Path(config["projectWorkspace"])
        git_repo_path = Path(os.environ["YGGDRASIL_GIT_REPO_PATH"])
        state_root = Path(os.environ["YGGDRASIL_STATE_ROOT"])

        assert project_workspace == git_repo_path
        assert project_workspace.is_dir()
        assert (project_workspace / "README.md").exists()

        for path in (project_workspace, git_repo_path, state_root):
            try:
                path.relative_to(repo_root)
            except ValueError:
                continue
            raise AssertionError(f"sandbox path leaked into repo root: {path}")


def test_real_user_validation_sandbox_prepares_isolated_git_workspace(tmp_path: Path) -> None:
    workspace_root = _create_fake_validation_workspace(tmp_path / "source-workspace")
    sandbox_root = tmp_path / "pilot-output"

    result = prepare_real_user_validation_sandbox(
        workspace_root=workspace_root,
        output_dir=sandbox_root,
        disable_live_llm=True,
    )

    workspace_path = Path(result["workspaceRoot"])
    state_root = Path(result["stateRoot"])
    powershell_script = Path(result["activationScripts"]["powershell"])
    manifest_path = sandbox_root / "sandbox-manifest.json"
    task_pack_path = sandbox_root / "materials" / "evaluation" / "fixtures" / "real-user-validation" / "task-pack-2026-04-30.md"

    assert result["status"] == "ready"
    assert result["workspaceIsolationConfirmed"] is True
    assert workspace_path == sandbox_root / "workspace"
    assert state_root == sandbox_root / ".yggdrasil"
    assert powershell_script.exists()
    assert manifest_path.exists()
    assert task_pack_path.exists()
    assert (workspace_path / "README.md").exists()
    assert (workspace_path / ".git").exists()

    git_head = subprocess.run(["git", "-C", str(workspace_path), "rev-parse", "HEAD"], capture_output=True, text=True, check=False)
    assert git_head.returncode == 0
    assert git_head.stdout.strip() == result["git"]["head"]

    activation_contents = powershell_script.read_text(encoding="utf-8")
    assert "YGGDRASIL_GIT_REPO_PATH" in activation_contents
    assert "YGGDRASIL_DISABLE_LIVE_LLM" in activation_contents
    assert str(state_root.resolve()) in activation_contents


def test_runtime_backup_restore_round_trip(tmp_path) -> None:
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        repository = TaskRepository(session)
        repository.create_task(
            {
                "id": "task_backup_before",
                "title": "backup before",
                "goal": "create baseline state",
            }
        )

    state_file = resolve_state_root() / "state" / "ops" / "marker.txt"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text("before-restore", encoding="utf-8")

    backup = create_runtime_backup(snapshot_dir=tmp_path / "backup")

    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        repository = TaskRepository(session)
        repository.create_task(
            {
                "id": "task_backup_after",
                "title": "backup after",
                "goal": "mutate state after snapshot",
            }
        )

    state_file.write_text("after-restore", encoding="utf-8")
    restore_runtime_backup(snapshot_dir=Path(backup["snapshotDir"]))

    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        repository = TaskRepository(session)
        assert repository.get_task("task_backup_before") is not None
        assert repository.get_task("task_backup_after") is None

    assert state_file.read_text(encoding="utf-8") == "before-restore"


def test_observability_summary_reports_exporters(monkeypatch) -> None:
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.delenv("YGGDRASIL_LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("YGGDRASIL_LANGFUSE_SECRET_KEY", raising=False)
    summary = summarize_observability(limit=5)
    assert summary["exporters"]["otel"]["configured"] is False
    assert summary["exporters"]["langfuse"]["configured"] is False
    assert summary["exporters"]["langfuse"]["host"] == "http://127.0.0.1:3100"


def test_langfuse_client_uses_local_base_url_and_project_keys(monkeypatch) -> None:
    captured: dict[str, str | None] = {}

    class FakeLangfuseClient:
        def __init__(self, *, public_key=None, secret_key=None, base_url=None, **_kwargs):
            captured["public_key"] = public_key
            captured["secret_key"] = secret_key
            captured["base_url"] = base_url

        def flush(self) -> None:
            return None

    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-test")
    monkeypatch.delenv("LANGFUSE_BASE_URL", raising=False)
    monkeypatch.setattr(observability_exporters, "LangfuseClient", FakeLangfuseClient)
    observability_exporters._STATE._langfuse_client = None
    observability_exporters._STATE._langfuse_identity = None

    client = observability_exporters._STATE.langfuse_client()

    assert client is not None
    assert captured["public_key"] == "pk-lf-test"
    assert captured["secret_key"] == "sk-lf-test"
    assert captured["base_url"] == "http://127.0.0.1:3100"