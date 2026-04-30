from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SLOW_TEST_FILES = {
    "tests/test_m9_acceptance.py",
    "tests/test_m8_runtime.py",
    "tests/test_subagent_and_worker.py",
    "tests/test_phase1_permissions_and_errors.py",
    "tests/test_memory_pipeline_api.py",
    "tests/test_mcp_bridge.py",
    "tests/test_module_host_eventing.py",
    "tests/test_phase3_stability_and_scale.py",
    "tests/test_runtime_and_pruning.py",
    "tests/test_persistence_api.py",
}


def _read_repo_file(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_slow_suite_marks_all_nightly_regression_files() -> None:
    missing = []

    for relative_path in sorted(SLOW_TEST_FILES):
        if "pytestmark = pytest.mark.slow" not in _read_repo_file(relative_path):
            missing.append(relative_path)

    assert not missing, "Expected slow marker on: " + ", ".join(missing)


def test_fast_ci_workflows_keep_excluding_slow_tests() -> None:
    for workflow_path in (".github/workflows/pr.yml", ".github/workflows/ci.yml"):
        assert 'uv run pytest -m "not slow"' in _read_repo_file(workflow_path)


def test_nightly_slow_job_runs_in_parallel() -> None:
    nightly = _read_repo_file(".github/workflows/nightly.yml")

    assert "uv run pytest -m slow -n auto --dist loadfile" in nightly