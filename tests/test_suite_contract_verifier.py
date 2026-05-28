"""Tests for suite_contract_verifier — validates real-task conventions v0.1 enforcement."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from yggdrasil_sdk.evaluation_runtime.suite_contract_verifier import (
    REJECT,
    WARN,
    Issue,
    SuiteContractVerifier,
    VerificationResult,
    check_no_embedded_planning,
    check_repo_self_reference,
    check_single_goal,
    check_suite_role,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
SUITES_DIR = REPO_ROOT / "evaluation" / "suites"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_suite(
    suite_id: str = "test_suite",
    suite_role: str | None = "real-task",
    cases: list[dict] | None = None,
) -> dict:
    suite: dict = {"id": suite_id}
    if suite_role is not None:
        suite["suiteRole"] = suite_role
    suite["cases"] = cases or []
    return suite


def _make_case(
    case_id: str = "test_case",
    task_goal: str = "Produce a technical report.",
    current_context: list[dict] | None = None,
    response_requirements: str = "",
    restart_message: str = "",
) -> dict:
    case: dict = {
        "id": case_id,
        "taskGoal": task_goal,
    }
    if current_context is not None:
        case["currentContext"] = current_context
    if response_requirements:
        case["responseRequirements"] = response_requirements
    if restart_message:
        case["restartMessage"] = restart_message
    return case


# ---------------------------------------------------------------------------
# check_single_goal
# ---------------------------------------------------------------------------

class TestSingleGoal:
    def test_accepts_clean_single_goal(self) -> None:
        case = _make_case(task_goal="Produce a technical review of the public REST API surface.")
        issues = check_single_goal(case)
        assert not issues

    def test_rejects_semicolon_multi_objective(self) -> None:
        case = _make_case(
            task_goal="Review the API surface; Produce a migration guide; Write a changelog."
        )
        issues = check_single_goal(case)
        assert any(i.severity == REJECT and i.check == "single-goal" for i in issues)

    def test_rejects_numbered_multi_objective(self) -> None:
        case = _make_case(
            task_goal="1) Review the codebase. 2) Identify tech debt. 3) Propose fixes."
        )
        issues = check_single_goal(case)
        assert any(i.severity == REJECT and i.check == "single-goal" for i in issues)

    def test_accepts_semicolon_within_single_sentence(self) -> None:
        case = _make_case(
            task_goal="Produce a report covering throughput; this should be a single deliverable."
        )
        # lowercase after semicolon = not a new objective
        issues = check_single_goal(case)
        assert not any(i.severity == REJECT for i in issues)


# ---------------------------------------------------------------------------
# check_no_embedded_planning
# ---------------------------------------------------------------------------

class TestNoEmbeddedPlanning:
    def test_accepts_clean_context(self) -> None:
        case = _make_case(
            current_context=[
                {"id": "ctx_1", "content": "You are reviewing an API. Focus on backward compatibility."}
            ]
        )
        issues = check_no_embedded_planning(case)
        assert not issues

    def test_rejects_numbered_section_structure_in_context(self) -> None:
        case = _make_case(
            current_context=[
                {
                    "id": "ctx_output",
                    "content": "The final structure must be: 1) 任务价值判断, 2) 联调覆盖范围, 3) 关键集成链路.",
                }
            ]
        )
        issues = check_no_embedded_planning(case)
        assert any(i.severity == REJECT and i.check == "no-embedded-planning" for i in issues)

    def test_rejects_step_sequence_in_context(self) -> None:
        case = _make_case(
            current_context=[
                {
                    "id": "ctx_steps",
                    "content": "先完成仓库现状的快速扫描, Then produce the report.",
                }
            ]
        )
        issues = check_no_embedded_planning(case)
        assert any(i.severity == REJECT and i.check == "no-embedded-planning" for i in issues)

    def test_rejects_too_many_section_headings_in_response_requirements(self) -> None:
        case = _make_case(
            response_requirements=(
                "Required sections: '## 1. 任务价值判断', '## 2. 联调覆盖范围', "
                "'## 3. 关键集成链路', '## 4. short-window 配置', "
                "'## 5. long-window 配置', '## 6. acceptance 对照结论', '## 7. 风险与下一步'."
            )
        )
        issues = check_no_embedded_planning(case)
        assert any(i.severity == REJECT and i.check == "no-embedded-planning" for i in issues)

    def test_accepts_few_section_headings(self) -> None:
        case = _make_case(
            response_requirements="The report must contain a conclusion with a clear recommendation."
        )
        issues = check_no_embedded_planning(case)
        assert not any(i.severity == REJECT for i in issues)

    def test_rejects_too_many_headings_in_restart_message(self) -> None:
        case = _make_case(
            restart_message=(
                "Produce brief with: '## 1. A', '## 2. B', '## 3. C', '## 4. D'."
            )
        )
        issues = check_no_embedded_planning(case)
        assert any(i.severity == REJECT and i.check == "no-embedded-planning" for i in issues)


# ---------------------------------------------------------------------------
# check_repo_self_reference
# ---------------------------------------------------------------------------

class TestRepoSelfReference:
    def test_rejects_project_yggdrasil(self) -> None:
        case = _make_case(task_goal="Review the current Project Yggdrasil repository.")
        issues = check_repo_self_reference(case)
        assert any(i.severity == REJECT and i.check == "repo-self-reference" for i in issues)

    def test_rejects_chinese_project_name(self) -> None:
        case = _make_case(task_goal="总结世界树计划的当前实现状态。")
        issues = check_repo_self_reference(case)
        assert any(i.severity == REJECT and i.check == "repo-self-reference" for i in issues)

    def test_rejects_this_repository(self) -> None:
        case = _make_case(task_goal="Analyze this repository and produce a brief.")
        issues = check_repo_self_reference(case)
        assert any(i.severity == REJECT and i.check == "repo-self-reference" for i in issues)

    def test_rejects_current_repo(self) -> None:
        case = _make_case(task_goal="Review the current repo state.")
        issues = check_repo_self_reference(case)
        assert any(i.severity == REJECT and i.check == "repo-self-reference" for i in issues)

    def test_accepts_external_task(self) -> None:
        case = _make_case(task_goal="Produce a technical review of a CI/CD pipeline API surface.")
        issues = check_repo_self_reference(case)
        assert not issues


# ---------------------------------------------------------------------------
# check_suite_role
# ---------------------------------------------------------------------------

class TestSuiteRole:
    def test_warns_when_missing(self) -> None:
        suite = {"id": "test_suite"}
        issues = check_suite_role(suite)
        assert any(i.severity == WARN and i.check == "suite-role-missing" for i in issues)

    def test_passes_when_present(self) -> None:
        suite = {"id": "test_suite", "suiteRole": "real-task"}
        issues = check_suite_role(suite)
        assert not issues


# ---------------------------------------------------------------------------
# SuiteContractVerifier — integration
# ---------------------------------------------------------------------------

class TestSuiteContractVerifier:
    def test_externalized_suite_passes_all_checks(self) -> None:
        path = SUITES_DIR / "g4-real-task-externalized.json"
        if not path.exists():
            pytest.skip("externalized suite not found")
        suite = json.loads(path.read_text(encoding="utf-8"))
        verifier = SuiteContractVerifier()
        result = verifier.verify_suite(suite)
        assert result.passed, f"Externalized suite failed: {[str(i.message) for i in result.rejections]}"

    def test_work_tree_debug_harness_loads_without_reject(self) -> None:
        path = SUITES_DIR / "g4-real-task-work-tree-debug.json"
        if not path.exists():
            pytest.skip("work-tree-debug suite not found")
        suite = json.loads(path.read_text(encoding="utf-8"))
        verifier = SuiteContractVerifier()
        result = verifier.verify_suite(suite)
        assert result.passed, f"Harness suite should pass: {[str(i.message) for i in result.rejections]}"

    def test_harness_suite_allows_embedded_planning(self) -> None:
        suite = _make_suite(
            suite_role="runtime-debug-harness",
            cases=[
                _make_case(
                    task_goal="Validate work tree child continuation.",
                    current_context=[
                        {
                            "id": "ctx_steps",
                            "content": "The final structure must be: 1) child-1 completion, 2) child-2 transition, 3) root convergence.",
                        }
                    ],
                )
            ],
        )
        verifier = SuiteContractVerifier()
        result = verifier.verify_suite(suite)
        assert result.passed, f"Harness suite should allow embedded planning: {[str(i.message) for i in result.rejections]}"

    def test_harness_suite_allows_repo_self_reference(self) -> None:
        suite = _make_suite(
            suite_role="runtime-debug-harness",
            cases=[
                _make_case(task_goal="Validate Project Yggdrasil work tree runtime.")
            ],
        )
        verifier = SuiteContractVerifier()
        result = verifier.verify_suite(suite)
        assert result.passed

    def test_real_task_suite_rejects_repo_self_reference(self) -> None:
        suite = _make_suite(
            suite_role="real-task",
            cases=[
                _make_case(task_goal="Review the current Project Yggdrasil repository.")
            ],
        )
        verifier = SuiteContractVerifier()
        result = verifier.verify_suite(suite)
        assert not result.passed
        assert any(i.check == "repo-self-reference" for i in result.rejections)

    def test_real_task_suite_rejects_embedded_planning(self) -> None:
        suite = _make_suite(
            suite_role="real-task",
            cases=[
                _make_case(
                    current_context=[
                        {
                            "id": "ctx_output",
                            "content": "The final structure must be: 1) Analysis, 2) Comparison, 3) Conclusion, 4) Risks.",
                        }
                    ],
                )
            ],
        )
        verifier = SuiteContractVerifier()
        result = verifier.verify_suite(suite)
        assert not result.passed
        assert any(i.check == "no-embedded-planning" for i in result.rejections)

    def test_exempt_role_skips_case_checks(self) -> None:
        suite = _make_suite(
            suite_role="provider-matrix",
            cases=[
                _make_case(task_goal="Review the current Project Yggdrasil repository.")
            ],
        )
        verifier = SuiteContractVerifier()
        result = verifier.verify_suite(suite)
        assert result.passed
        assert not result.rejections

    def test_missing_suite_role_produces_warning(self) -> None:
        suite = _make_suite(suite_role=None)
        verifier = SuiteContractVerifier()
        result = verifier.verify_suite(suite)
        assert result.passed  # warnings don't block
        assert any(i.check == "suite-role-missing" for i in result.warnings)


# ---------------------------------------------------------------------------
# All existing suites must have suiteRole
# ---------------------------------------------------------------------------

class TestAllSuitesHaveRole:
    def test_all_suite_files_have_suite_role(self) -> None:
        if not SUITES_DIR.exists():
            pytest.skip("suites directory not found")
        missing: list[str] = []
        for path in sorted(SUITES_DIR.glob("*.json")):
            suite = json.loads(path.read_text(encoding="utf-8"))
            if "suiteRole" not in suite:
                missing.append(path.name)
        assert not missing, f"Suites missing suiteRole: {', '.join(missing)}"

    def test_all_existing_suites_pass_verifier(self) -> None:
        """All suites should pass the verifier (legacy=warn, real-task=pass, harness=pass)."""
        if not SUITES_DIR.exists():
            pytest.skip("suites directory not found")
        verifier = SuiteContractVerifier()
        failed: list[str] = []
        for path in sorted(SUITES_DIR.glob("*.json")):
            suite = json.loads(path.read_text(encoding="utf-8"))
            result = verifier.verify_suite(suite)
            if not result.passed:
                failed.append(f"{path.name}: {[i.message for i in result.rejections]}")
        assert not failed, f"Suites failed verification:\n" + "\n".join(failed)
