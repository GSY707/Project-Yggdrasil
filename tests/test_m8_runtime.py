from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import subprocess

import pytest
import yggdrasil_sdk.observability_exporters as observability_exporters
import yggdrasil_sdk.llm_runtime as sdk_llm_runtime
import yggdrasil_sdk.ops_runtime_scorecard as ops_runtime_scorecard

from yggdrasil_sdk import TaskRepository, create_runtime_backup, get_persistence_runtime, restore_runtime_backup, run_evaluation_suite, summarize_observability
from yggdrasil_sdk.evaluation_runtime import isolated_runtime_environment
from yggdrasil_sdk.evaluation_runtime.suite_cases_part_a import _run_live_llm_task_case, _run_live_llm_tool_case
from yggdrasil_sdk.mcp_bridge import ensure_mcp_bridge_config
from yggdrasil_sdk.ops_runtime import prepare_real_user_validation_sandbox, summarize_real_user_scorecard
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


def test_live_llm_cases_fail_on_missing_candidate_not_bad_import(monkeypatch) -> None:
    monkeypatch.setattr(sdk_llm_runtime, "load_runtime_candidate_models", lambda: [])

    with pytest.raises(RuntimeError, match="requested live candidate is unavailable: longcat/LongCat-2.0-Preview"):
        _run_live_llm_task_case({"requireLive": True})

    with pytest.raises(RuntimeError, match="requested live candidate is unavailable: longcat/LongCat-2.0-Preview"):
        _run_live_llm_tool_case({"requireLive": True})


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


def test_isolated_evaluation_environment_can_copy_explicit_workspace_root(tmp_path: Path) -> None:
    workspace_root = _create_fake_validation_workspace(tmp_path / "source-workspace")

    with isolated_runtime_environment(workspace_root=workspace_root):
        project_workspace = Path(os.environ["YGGDRASIL_GIT_REPO_PATH"])

        assert project_workspace.is_dir()
        assert project_workspace != workspace_root
        assert (project_workspace / "README.md").read_text(encoding="utf-8") == "# Fake Workspace\n"
        assert (project_workspace / "evaluation" / "fixtures" / "real-user-validation" / "task-pack-2026-04-30.md").exists()


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
    assert result["activationCommands"]["powershell"].startswith("pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File")
    assert "activate.ps1" in result["activationCommands"]["powershell"]


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


def test_real_user_validation_sandbox_activation_command_uses_file_mode(tmp_path: Path) -> None:
    workspace_root = _create_fake_validation_workspace(tmp_path / "source-workspace-activation")
    sandbox_root = tmp_path / "pilot-output-activation"

    result = prepare_real_user_validation_sandbox(
        workspace_root=workspace_root,
        output_dir=sandbox_root,
        disable_live_llm=False,
    )

    assert result["activationCommands"]["powershell"].endswith('activate.ps1"')
    assert result["activationCommands"]["shell"].startswith("bash ")
    assert "activate.sh" in result["activationCommands"]["shell"]


def test_ci01_baseline_and_runtime_context_follow_current_directory_reference_mapping(tmp_path: Path, monkeypatch) -> None:
    import yggdrasil_sdk.ops_runtime_live as ops_runtime_live

    source_workspace = tmp_path / "source-workspace-ci01"
    target_workspace = tmp_path / "target-workspace-ci01"
    (source_workspace / "docs").mkdir(parents=True, exist_ok=True)
    (target_workspace / "docs").mkdir(parents=True, exist_ok=True)

    package_text = (
        "{\n"
        '  "scripts": {\n'
        '    "eval:m9:control-plane": "uv run python -m yggdrasil_sdk.evaluation_cli run --suite evalsuite_regression_m9_control_plane",\n'
        '    "eval:m9:acceptance": "uv run python -m yggdrasil_sdk.evaluation_cli run --suite evalsuite_acceptance_m9_capabilities"\n'
        "  }\n"
        "}\n"
    )
    readme_text = (
        "corepack pnpm eval:m9:control-plane\n"
        "corepack pnpm eval:m9:acceptance\n"
    )
    directory_text = (
        "| `eval:m9:control-plane` | `suites/m9-control-plane.json` |\n"
        "| `eval:m9:acceptance` | `suites/m9-acceptance.json` |\n"
    )

    (source_workspace / "package.json").write_text(package_text, encoding="utf-8")
    (source_workspace / "README.md").write_text(readme_text, encoding="utf-8")
    (source_workspace / "docs" / "DIRECTORY_REFERENCE.md").write_text(directory_text, encoding="utf-8")

    import yggdrasil_sdk.ops_runtime_live_part_a as ops_runtime_live_part_a
    monkeypatch.setattr(ops_runtime_live, "resolve_workspace_root", lambda: source_workspace)
    monkeypatch.setattr(ops_runtime_live, "_run_git_command", lambda *args: "")
    monkeypatch.setattr(ops_runtime_live_part_a, "_run_git_command", lambda *args: "")

    ops_runtime_live._prepare_ci01_baseline(target_workspace)

    prepared_package = (target_workspace / "package.json").read_text(encoding="utf-8")
    prepared_readme = (target_workspace / "README.md").read_text(encoding="utf-8")
    prepared_directory = (target_workspace / "docs" / "DIRECTORY_REFERENCE.md").read_text(encoding="utf-8")
    runtime_context = ops_runtime_live._build_ci01_runtime_context(target_workspace)
    direct_replacements = runtime_context[0]["content"]

    assert '"eval:m9:acceptance"' not in prepared_package
    assert "corepack pnpm eval:m9:acceptance" not in prepared_readme
    assert "| `eval:m9:acceptance` | `suites/m9-acceptance.json` |" not in prepared_directory
    assert "| `eval:m9:control-plane` | `suites/m9-control-plane.json` |" in direct_replacements
    assert "| `eval:m9:acceptance` | `suites/m9-acceptance.json` |" in direct_replacements


def test_live_task_token_budget_defaults_to_unbounded_without_override() -> None:
    import yggdrasil_sdk.ops_runtime_live as ops_runtime_live

    assert ops_runtime_live._live_task_token_budget({"maxTokens": 900, "maxToolRounds": 12}) is None
    assert ops_runtime_live._live_task_token_budget({"maxTokens": 2200, "maxToolRounds": 36}) is None
    assert ops_runtime_live._live_task_token_budget({"budgetTokenTotal": 24000, "maxTokens": 900}) == 24000


def test_drain_worker_attempts_consumes_requeued_results_before_returning() -> None:
    import yggdrasil_sdk.ops_runtime_live as ops_runtime_live

    attempts = iter(
        [
            {"status": "requeued", "result": {"status": "failed"}},
            {"status": "processed", "result": {"status": "completed"}},
        ]
    )

    results = ops_runtime_live._drain_worker_attempts(lambda _queue: next(attempts))

    assert [item["status"] for item in results] == ["requeued", "processed"]


def test_observability_summary_reports_exporters(monkeypatch) -> None:
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.delenv("YGGDRASIL_LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("YGGDRASIL_LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT", raising=False)
    monkeypatch.delenv("YGGDRASIL_OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.delenv("YGGDRASIL_OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
    monkeypatch.delenv("YGGDRASIL_OTEL_EXPORTER_OTLP_METRICS_ENDPOINT", raising=False)
    summary = summarize_observability(limit=5)
    assert summary["exporters"]["otel"]["configured"] is False
    assert summary["exporters"]["langfuse"]["configured"] is False
    assert summary["exporters"]["langfuse"]["host"] == "http://127.0.0.1:3100"


def test_summarize_real_user_scorecard_reports_g2_metrics(tmp_path: Path) -> None:
    csv_path = tmp_path / "scorecard.csv"
    csv_path.write_text(
        "run_id,task_id,acceptance_pass_0_1,human_takeover_count,user_clarification_rounds,recovery_attempted_0_1,recovery_success_0_1,weighted_total_score_0_100,first_token_seconds,plan_quality_score_0_100,rework_count,rework_rate\n"
        "run-1,YGG-CG-01,1,0,1,0,0,98,1.25,94,1,0.25\n"
        "run-2,YGG-CG-01,1,1,0,0,0,96,1.75,90,2,0.50\n"
        "run-3,YGG-CG-03,1,0,0,1,1,99,,,,\n",
        encoding="utf-8",
    )

    summary = summarize_real_user_scorecard(csv_path)

    assert summary["status"] == "ok"
    assert summary["overall"]["acceptancePassRate"] == 1.0
    assert summary["overall"]["medianHumanTakeoverCount"] == 0.0
    assert summary["overall"]["medianUserClarificationRounds"] == 0.0
    assert summary["overall"]["averageFirstTokenSeconds"] == 1.5
    assert summary["overall"]["firstTokenSampleCount"] == 2
    assert summary["overall"]["averagePlanQualityScore"] == 92.0
    assert summary["overall"]["planQualitySampleCount"] == 2
    assert summary["overall"]["medianReworkCount"] == 1.5
    assert summary["overall"]["reworkCountSampleCount"] == 2
    assert summary["overall"]["averageReworkRate"] == 0.375
    assert summary["overall"]["reworkRateSampleCount"] == 2
    assert summary["tasks"]["YGG-CG-01"]["averageFirstTokenSeconds"] == 1.5
    assert summary["tasks"]["YGG-CG-01"]["averagePlanQualityScore"] == 92.0
    assert summary["tasks"]["YGG-CG-03"]["averageFirstTokenSeconds"] is None
    assert summary["tasks"]["YGG-CG-03"]["averagePlanQualityScore"] is None
    assert summary["tasks"]["YGG-CG-03"]["recoverySuccessRate"] == 1.0


def test_first_token_helpers_read_response_payload() -> None:
    invocations = [
        {
            "record": {"startedAt": "2026-05-15T08:31:06Z"},
            "responsePayload": {
                "firstTokenLatencyMs": 1250.0,
                "rounds": [{"latencyMs": 3750.0}],
            },
        }
    ]

    first_token_seconds = ops_runtime_scorecard._first_token_seconds(invocations)

    assert first_token_seconds == 1.25
    assert ops_runtime_scorecard._first_token_at(invocations, first_token_seconds) == "2026-05-15T08:31:07.250000Z"
    assert ops_runtime_scorecard._first_useful_output_seconds(invocations) == 3.75


def test_build_scorecard_row_keeps_pause_resume_metrics_from_repair_attempts() -> None:
    row = ops_runtime_scorecard._build_scorecard_row(
        task_key="YGG-CG-03",
        task_def={"appLabel": "coding-inherit", "taskType": "coding-resume", "workspaceProfile": "pack-a-live-sandbox"},
        execution={
            "verification": [{"returncode": 0}],
            "taskRuntime": {"task": {"status": "completed"}, "invocations": []},
            "firstTokenSeconds": 1.5,
            "firstUsefulOutputSeconds": 10.0,
            "issues": [],
            "traceIds": [],
            "toolExecutionNames": [],
            "diffSummary": {},
            "taskWorkspace": "C:/tmp/pack-a",
            "auditLevel": "strict",
            "startAt": "2026-05-15T08:31:06Z",
            "firstTokenAt": "2026-05-15T08:31:07.500000Z",
            "firstUsefulOutputAt": "2026-05-15T08:31:17Z",
            "endAt": "2026-05-15T08:33:04Z",
            "totalDurationSeconds": 118.0,
            "pauseResumeAttempted": False,
            "pauseResumeSuccess": False,
            "repairAttempts": [
                {
                    "pauseResumeAttempted": True,
                    "pauseResumeSuccess": True,
                }
            ],
        },
        fastest_first_useful=10.0,
        provider="deepseek_direct",
        model="deepseek-v4-pro",
        batch_id="G2-LIVE-TEST",
        environment_id="sandbox-live-test",
        coordination_backend="memory",
    )

    assert row["pause_resume_attempted_0_1"] == 1
    assert row["pause_resume_success_0_1"] == 1
    assert row["recovery_attempted_0_1"] == 1
    assert row["recovery_success_0_1"] == 1
    assert row["continuity_recovery_score_0_100"] == 100
    assert row["first_token_at"] == "2026-05-15T08:31:07.500000Z"
    assert row["first_token_seconds"] == 1.5
    assert row["agent_system"] == "yggdrasil-deepseek-direct-live"


def test_build_scorecard_row_records_token_usage_and_context_lengths() -> None:
    row = ops_runtime_scorecard._build_scorecard_row(
        task_key="G4-CONTEXT-LONGFORM",
        task_def={"appLabel": "coding-greenfield", "taskType": "coding", "workspaceProfile": "g4-longform-single-task"},
        execution={
            "verification": [{"returncode": 0}],
            "taskRuntime": {
                "task": {"status": "completed"},
                "invocations": [
                    {
                        "record": {"inputTokensUsed": 3200, "outputTokensUsed": 400},
                        "responsePayload": {
                            "usage": {
                                "inputTokens": 3200,
                                "outputTokens": 400,
                                "totalTokens": 3600,
                                "cacheHitInputTokens": 2400,
                                "cacheWriteInputTokens": 300,
                                "nonCacheInputTokens": 800,
                                "reasoningTokens": 120,
                            },
                            "contextLengthObservations": [
                                {"phase": "beforeContextPruning", "estimatedTokens": 1800},
                                {"phase": "taskEnd", "estimatedTokens": 1400},
                            ],
                        },
                    }
                ],
            },
            "firstTokenSeconds": 2.5,
            "firstUsefulOutputSeconds": 18.0,
            "issues": [],
            "traceIds": [],
            "toolExecutionNames": [],
            "diffSummary": {},
            "taskWorkspace": "C:/tmp/g4-longform",
            "auditLevel": "default",
            "startAt": "2026-05-15T15:16:06Z",
            "firstTokenAt": "2026-05-15T15:16:08.500000Z",
            "firstUsefulOutputAt": "2026-05-15T15:16:24Z",
            "endAt": "2026-05-15T15:16:52Z",
            "totalDurationSeconds": 46.0,
            "pauseResumeAttempted": False,
            "pauseResumeSuccess": False,
        },
        fastest_first_useful=18.0,
        provider="deepseek_direct",
        model="deepseek-v4-pro",
        batch_id="G4-PROVIDER-MATRIX",
        environment_id="g4-provider-matrix",
        coordination_backend="memory",
    )

    assert row["input_tokens_used"] == 3200
    assert row["output_tokens_used"] == 400
    assert row["total_tokens_used"] == 3600
    assert row["cache_hit_input_tokens"] == 2400
    assert row["non_cache_input_tokens"] == 800
    assert row["cache_write_input_tokens"] == 300
    assert row["reasoning_tokens"] == 120
    assert row["max_context_length_tokens"] == 1800
    observations = json.loads(row["context_length_observations_json"])
    assert observations[0]["phase"] == "beforeContextPruning"


def test_append_scorecard_rows_inserts_newline_after_header(tmp_path: Path) -> None:
    csv_path = tmp_path / "scorecard.csv"
    csv_path.write_text("run_id,task_id,acceptance_pass_0_1", encoding="utf-8")

    ops_runtime_scorecard._append_scorecard_rows(
        csv_path,
        [{"run_id": "run-1", "task_id": "YGG-CG-03", "acceptance_pass_0_1": 1}],
    )

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert rows == [{"run_id": "run-1", "task_id": "YGG-CG-03", "acceptance_pass_0_1": "1"}]


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
    monkeypatch.setenv("LANGFUSE_TRACING_ENABLED", "1")
    monkeypatch.delenv("LANGFUSE_BASE_URL", raising=False)
    monkeypatch.setattr(observability_exporters, "LangfuseClient", FakeLangfuseClient)
    observability_exporters._STATE._langfuse_client = None
    observability_exporters._STATE._langfuse_identity = None

    client = observability_exporters._STATE.langfuse_client()

    assert client is not None
    assert captured["public_key"] == "pk-lf-test"
    assert captured["secret_key"] == "sk-lf-test"
    assert captured["base_url"] == "http://127.0.0.1:3100"