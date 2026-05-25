"""Suite Contract Verifier — validates suite/case definitions against real-task conventions v0.1.

This module checks suite JSON definitions at load time to ensure they conform to the
established conventions for real-task testing. It distinguishes between:
- ``real-task``: Must satisfy all four default conventions (single goal, no embedded
  planning, project-business weak relation, no planning injection).
- ``runtime-debug-harness``: Exempt from most checks; intentionally pre-configures
  work trees and step sequences.
- ``legacy-repo-specific``: Historical suites that predate the conventions; produce
  warnings but do not block.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Issue severity
# ---------------------------------------------------------------------------

REJECT = "reject"
WARN = "warn"
PASS = "pass"


@dataclass
class Issue:
    """A single verification issue found in a suite or case definition."""

    severity: str  # "reject" | "warn"
    check: str
    message: str
    case_id: str | None = None


@dataclass
class VerificationResult:
    """Aggregated result of verifying one suite."""

    suite_id: str
    suite_role: str | None
    issues: list[Issue] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not any(issue.severity == REJECT for issue in self.issues)

    @property
    def warnings(self) -> list[Issue]:
        return [issue for issue in self.issues if issue.severity == WARN]

    @property
    def rejections(self) -> list[Issue]:
        return [issue for issue in self.issues if issue.severity == REJECT]


# ---------------------------------------------------------------------------
# Pattern constants
# ---------------------------------------------------------------------------

_REPO_SELF_REFERENCE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"Project\s+Yggdrasil",
        r"世界树",
        r"世界树计划",
        r"本仓库",
        r"当前仓库",
        r"this\s+repository",
        r"current\s+repo",
        r"this\s+repo\b",
        r"yggdrasil[_-]sdk",
    ]
]

_MULTI_GOAL_SEMICOLON_RE = re.compile(r";\s*(?:and\s+|then\s+|also\s+)?[A-Z\u4e00-\u9fff]")
_MULTI_GOAL_NUMBERED_RE = re.compile(
    r"(?:^|\.\s+)(?:\d+\)|[①②③④⑤⑥⑦]|\(\d+\))\s*\S", re.MULTILINE
)

_EMBEDDED_PLANNING_SECTION_ORDER_RE = re.compile(
    r"(?:结构必须是|structure\s+must\s+be|final\s+structure\s+must\s+be)\s*[:：]?\s*\d+\)", re.IGNORECASE
)
_EMBEDDED_PLANNING_SECTION_HEADING_LIST_RE = re.compile(
    r"(?:##\s+\d+\.\s+.+\n){3,}", re.MULTILINE
)
_EMBEDDED_PLANNING_STEP_SEQUENCE_RE = re.compile(
    r"(?:先做|先完成|先读取|Start\s+with|First\s*,?\s+.+(?:Then|Next|Finally))", re.IGNORECASE
)

_RESPONSE_REQ_STEP_PATH_RE = re.compile(
    r"(?:Start\s+(?:immediately\s+)?with|先做|先完成).+(?:Then|再|然后|Next|Finally)", re.IGNORECASE | re.DOTALL
)


def _count_required_section_headings(text: str) -> int:
    """Count how many '## N. Title' style headings are prescribed in text."""
    return len(re.findall(r"['\"']##\s+\d+\.\s+[^'\"']+['\"']", text))


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def check_single_goal(case: dict[str, Any]) -> list[Issue]:
    """Reject if taskGoal contains multiple semicolon-separated or numbered objectives."""
    task_goal = str(case.get("taskGoal") or "")
    case_id = str(case.get("id") or "unknown")
    issues: list[Issue] = []

    if _MULTI_GOAL_SEMICOLON_RE.search(task_goal):
        issues.append(Issue(
            severity=REJECT,
            check="single-goal",
            message="taskGoal contains multiple semicolon-separated objectives",
            case_id=case_id,
        ))

    if _MULTI_GOAL_NUMBERED_RE.search(task_goal):
        issues.append(Issue(
            severity=REJECT,
            check="single-goal",
            message="taskGoal contains numbered multi-objective list",
            case_id=case_id,
        ))

    return issues


def check_no_embedded_planning(case: dict[str, Any]) -> list[Issue]:
    """Reject if currentContext or responseRequirements prescribes section order/step sequence."""
    case_id = str(case.get("id") or "unknown")
    issues: list[Issue] = []

    # Check currentContext entries
    for ctx_item in case.get("currentContext") or []:
        if not isinstance(ctx_item, dict):
            continue
        content = str(ctx_item.get("content") or "")

        if _EMBEDDED_PLANNING_SECTION_ORDER_RE.search(content):
            issues.append(Issue(
                severity=REJECT,
                check="no-embedded-planning",
                message=f"currentContext item '{ctx_item.get('id', '?')}' prescribes section order with numbered structure",
                case_id=case_id,
            ))

        if _EMBEDDED_PLANNING_STEP_SEQUENCE_RE.search(content):
            issues.append(Issue(
                severity=REJECT,
                check="no-embedded-planning",
                message=f"currentContext item '{ctx_item.get('id', '?')}' prescribes execution step sequence",
                case_id=case_id,
            ))

    # Check responseRequirements
    response_req = str(case.get("responseRequirements") or "")
    if response_req:
        heading_count = _count_required_section_headings(response_req)
        if heading_count > 3:
            issues.append(Issue(
                severity=REJECT,
                check="no-embedded-planning",
                message=f"responseRequirements prescribes {heading_count} section headings (max 3 for real-task)",
                case_id=case_id,
            ))

        if _RESPONSE_REQ_STEP_PATH_RE.search(response_req):
            issues.append(Issue(
                severity=REJECT,
                check="no-embedded-planning",
                message="responseRequirements prescribes step-by-step execution path",
                case_id=case_id,
            ))

    # Check restartMessage
    restart_msg = str(case.get("restartMessage") or "")
    if restart_msg:
        heading_count = _count_required_section_headings(restart_msg)
        if heading_count > 3:
            issues.append(Issue(
                severity=REJECT,
                check="no-embedded-planning",
                message=f"restartMessage prescribes {heading_count} section headings (max 3 for real-task)",
                case_id=case_id,
            ))

    return issues


def check_repo_self_reference(case: dict[str, Any]) -> list[Issue]:
    """Reject if taskGoal references the project name or repo path."""
    task_goal = str(case.get("taskGoal") or "")
    case_id = str(case.get("id") or "unknown")
    issues: list[Issue] = []

    for pattern in _REPO_SELF_REFERENCE_PATTERNS:
        match = pattern.search(task_goal)
        if match:
            issues.append(Issue(
                severity=REJECT,
                check="repo-self-reference",
                message=f"taskGoal references project/repo: matched '{match.group()}'",
                case_id=case_id,
            ))
            break  # One match is enough

    return issues


def check_suite_role(suite: dict[str, Any]) -> list[Issue]:
    """Warn if suiteRole is missing."""
    issues: list[Issue] = []
    if "suiteRole" not in suite:
        issues.append(Issue(
            severity=WARN,
            check="suite-role-missing",
            message="Suite definition is missing 'suiteRole' field",
        ))
    return issues


# ---------------------------------------------------------------------------
# Main verifier
# ---------------------------------------------------------------------------

class SuiteContractVerifier:
    """Validates suite JSON definitions against real-task conventions v0.1.

    The verifier adapts its behavior based on the ``suiteRole`` of the suite:

    - ``real-task``: All checks produce REJECT on violation.
    - ``runtime-debug-harness``: Embedded planning and repo self-reference are
      allowed (PASS); multi-goal produces WARN.
    - ``legacy-repo-specific``: All violations produce WARN instead of REJECT.
    - Other roles (``provider-matrix``, ``regression``, ``benchmark``): Not checked
      against real-task conventions.
    """

    # Roles that are exempt from real-task convention checks
    EXEMPT_ROLES = frozenset({"provider-matrix", "regression", "benchmark"})

    def verify_suite(self, suite: dict[str, Any]) -> VerificationResult:
        """Run all convention checks on a suite definition.

        Args:
            suite: Parsed suite JSON as a dict.

        Returns:
            A :class:`VerificationResult` with all issues found.
        """
        suite_id = str(suite.get("id") or "unknown")
        suite_role = str(suite.get("suiteRole") or "").strip() or None
        result = VerificationResult(suite_id=suite_id, suite_role=suite_role)

        # Always check suite-level metadata
        result.issues.extend(check_suite_role(suite))

        # Skip case-level checks for exempt roles
        if suite_role in self.EXEMPT_ROLES:
            return result

        cases = suite.get("cases") or []
        for case in cases:
            if not isinstance(case, dict):
                continue
            self._verify_case(case, suite_role, result)

        return result

    def _verify_case(
        self,
        case: dict[str, Any],
        suite_role: str | None,
        result: VerificationResult,
    ) -> None:
        """Verify a single case within a suite."""
        is_real_task = suite_role == "real-task"
        is_harness = suite_role == "runtime-debug-harness"
        is_legacy = suite_role == "legacy-repo-specific"

        # --- single goal ---
        goal_issues = check_single_goal(case)
        for issue in goal_issues:
            if is_harness:
                issue.severity = WARN
            elif is_legacy:
                issue.severity = WARN
            # real-task keeps REJECT
            result.issues.append(issue)

        # --- no embedded planning ---
        planning_issues = check_no_embedded_planning(case)
        for issue in planning_issues:
            if is_harness:
                continue  # skip entirely for harness
            elif is_legacy:
                issue.severity = WARN
            # real-task keeps REJECT
            result.issues.append(issue)

        # --- repo self-reference ---
        repo_issues = check_repo_self_reference(case)
        for issue in repo_issues:
            if is_harness:
                continue  # skip entirely for harness
            elif is_legacy:
                issue.severity = WARN
            # real-task keeps REJECT
            result.issues.append(issue)


__all__ = [
    "REJECT",
    "WARN",
    "PASS",
    "Issue",
    "VerificationResult",
    "SuiteContractVerifier",
    "check_single_goal",
    "check_no_embedded_planning",
    "check_repo_self_reference",
    "check_suite_role",
]
