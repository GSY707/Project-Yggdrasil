from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
import json
import statistics
from pathlib import Path
from typing import Any

from .support import utc_now, write_json


def _parse_int(row: dict[str, str], key: str) -> int:
    raw = str(row.get(key) or "0").strip()
    try:
        return int(float(raw))
    except ValueError:
        return 0


def _parse_optional_float(row: dict[str, str], key: str) -> float | None:
    raw = str(row.get(key) or "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _parse_optional_int(row: dict[str, str], key: str) -> int | None:
    value = _parse_optional_float(row, key)
    return int(value) if value is not None else None


def summarize_real_user_scorecard(csv_path: Path) -> dict[str, Any]:
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    if not rows:
        return {
            "generatedAt": utc_now().isoformat(),
            "csvPath": str(csv_path.resolve()),
            "rowCount": 0,
            "status": "empty",
            "overall": {},
            "tasks": {},
        }

    def _median(values: list[int]) -> float:
        return float(statistics.median(values)) if values else 0.0

    tasks: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        tasks.setdefault(str(row.get("task_id") or "unknown"), []).append(row)

    def _summarize(group: list[dict[str, str]]) -> dict[str, Any]:
        row_count = len(group)
        acceptance_passes = [_parse_int(row, "acceptance_pass_0_1") for row in group]
        takeovers = [_parse_int(row, "human_takeover_count") for row in group]
        clarifications = [_parse_int(row, "user_clarification_rounds") for row in group]
        recovery_attempts = [_parse_int(row, "recovery_attempted_0_1") for row in group]
        recovery_successes = [_parse_int(row, "recovery_success_0_1") for row in group]
        weighted_scores = [_parse_int(row, "weighted_total_score_0_100") for row in group]
        plan_quality_scores = [
            value
            for row in group
            if (value := _parse_optional_float(row, "plan_quality_score_0_100")) is not None
        ]
        rework_counts = [value for row in group if (value := _parse_optional_int(row, "rework_count")) is not None]
        rework_rates = [value for row in group if (value := _parse_optional_float(row, "rework_rate")) is not None]
        attempted_recovery_count = sum(recovery_attempts)
        return {
            "rowCount": row_count,
            "acceptancePassRate": sum(acceptance_passes) / row_count,
            "medianHumanTakeoverCount": _median(takeovers),
            "medianUserClarificationRounds": _median(clarifications),
            "averageWeightedScore": (sum(weighted_scores) / row_count) if weighted_scores else 0.0,
            "averagePlanQualityScore": (sum(plan_quality_scores) / len(plan_quality_scores)) if plan_quality_scores else None,
            "planQualitySampleCount": len(plan_quality_scores),
            "medianReworkCount": float(statistics.median(rework_counts)) if rework_counts else None,
            "reworkCountSampleCount": len(rework_counts),
            "averageReworkRate": (sum(rework_rates) / len(rework_rates)) if rework_rates else None,
            "reworkRateSampleCount": len(rework_rates),
            "recoverySuccessRate": (sum(recovery_successes) / attempted_recovery_count) if attempted_recovery_count else None,
        }

    return {
        "generatedAt": utc_now().isoformat(),
        "csvPath": str(csv_path.resolve()),
        "rowCount": len(rows),
        "status": "ok",
        "overall": _summarize(rows),
        "tasks": {task_id: _summarize(group) for task_id, group in sorted(tasks.items())},
    }


def _format_timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    normalized = value.astimezone(timezone.utc) if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    return normalized.isoformat().replace("+00:00", "Z")


def _seconds_between(started_at: datetime | None, ended_at: datetime | None) -> float | None:
    if started_at is None or ended_at is None:
        return None
    delta = ended_at - started_at
    return round(delta.total_seconds(), 2)


def _read_json_ref(ref: Any, workspace_root: Path) -> dict[str, Any] | None:
    if ref is None:
        return None
    locator = getattr(ref, "locator", None)
    if locator is None and isinstance(ref, dict):
        locator = ref.get("locator")
    if not locator:
        return None
    path = (workspace_root / str(locator)).resolve()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _scorecard_fieldnames(csv_path: Path) -> list[str]:
    if csv_path.exists():
        with csv_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            header = next(reader, None)
        if header:
            return [str(item) for item in header]
    raise FileNotFoundError(f"Scorecard header missing: {csv_path}")


def _append_scorecard_rows(csv_path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    fieldnames = _scorecard_fieldnames(csv_path)
    needs_newline = False
    if csv_path.exists() and csv_path.stat().st_size > 0:
        with csv_path.open("rb") as probe:
            probe.seek(-1, 2)
            needs_newline = probe.read(1) not in {b"\n", b"\r"}
    with csv_path.open("a", encoding="utf-8", newline="") as handle:
        if needs_newline:
            handle.write("\n")
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        for row in rows:
            payload = {name: row.get(name, "") for name in fieldnames}
            writer.writerow(payload)


def _write_json_output(path: Path | None, payload: dict[str, Any]) -> str | None:
    if path is None:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, payload)
    return str(path.resolve())


def _task_pack_output_path(output_path: Path | None, workspace_root: Path) -> Path | None:
    if output_path is not None:
        return output_path.resolve()
    date_slug = utc_now().strftime("%Y-%m-%d")
    return (workspace_root / "evaluation" / "fixtures" / "real-user-validation" / f"live-task-pack-{date_slug}.json").resolve()


def _first_useful_output_seconds(invocations: list[dict[str, Any]]) -> float | None:
    for item in invocations:
        response_payload = item.get("responsePayload") or {}
        rounds = response_payload.get("rounds") if isinstance(response_payload, dict) else None
        if isinstance(rounds, list) and rounds:
            first_round = rounds[0] if isinstance(rounds[0], dict) else {}
            if first_round.get("latencyMs") is not None:
                return round(float(first_round["latencyMs"]) / 1000.0, 2)
    return None


def _first_useful_output_at(invocations: list[dict[str, Any]], seconds: float | None) -> str | None:
    if seconds is None:
        return None
    for item in invocations:
        record = item.get("record") or {}
        started_at_raw = record.get("startedAt")
        if not started_at_raw:
            continue
        started_at = datetime.fromisoformat(str(started_at_raw).replace("Z", "+00:00"))
        return _format_timestamp(started_at + timedelta(seconds=seconds))
    return None


def _takeover_metrics(invocations: list[dict[str, Any]]) -> dict[str, Any]:
    for item in invocations:
        request_payload = item.get("requestPayload") or {}
        takeover = request_payload.get("takeoverProtocol") if isinstance(request_payload, dict) else None
        if isinstance(takeover, dict):
            metrics = takeover.get("metrics")
            if isinstance(metrics, dict):
                return metrics
    return {}


def _tool_execution_names(invocations: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    for item in invocations:
        response_payload = item.get("responsePayload") or {}
        summaries = response_payload.get("toolExecutionSummaries") if isinstance(response_payload, dict) else None
        if not isinstance(summaries, list):
            continue
        for summary in summaries:
            if not isinstance(summary, dict):
                continue
            name = str(summary.get("tool") or "").strip()
            if name and name not in names:
                names.append(name)
    return names


def _response_speed_score(first_useful_seconds: float | None, fastest_seconds: float | None) -> int:
    if first_useful_seconds is None or fastest_seconds is None or fastest_seconds <= 0:
        return 0
    if first_useful_seconds <= fastest_seconds:
        return 100
    ratio = first_useful_seconds / fastest_seconds
    if ratio <= 1.15:
        return 85
    if ratio <= 1.30:
        return 70
    if ratio <= 1.50:
        return 50
    return 0


def _task_outcome_score(task_completed: int, acceptance_pass: int) -> int:
    if acceptance_pass:
        return 100
    if task_completed:
        return 70
    return 0


def _weighted_total_score(
    response_speed: int,
    config_quality: int,
    human_effort: int,
    continuity: int,
    outcome: int,
) -> int:
    total = 0.4 * outcome + 0.2 * human_effort + 0.2 * continuity + 0.1 * response_speed + 0.1 * config_quality
    return int(round(total))


def _aggregate_pause_resume(execution: dict[str, Any]) -> tuple[bool, bool]:
    attempts = [execution, *[item for item in execution.get("repairAttempts") or [] if isinstance(item, dict)]]
    attempted = any(bool(item.get("pauseResumeAttempted")) for item in attempts)
    success = any(bool(item.get("pauseResumeSuccess")) for item in attempts)
    return attempted, success


def _build_scorecard_row(
    *,
    task_key: str,
    task_def: dict[str, Any],
    execution: dict[str, Any],
    fastest_first_useful: float | None,
    provider: str,
    model: str,
    batch_id: str,
    environment_id: str,
    coordination_backend: str,
) -> dict[str, Any]:
    verification_results = execution.get("verification") or []
    task_payload = execution.get("taskRuntime") or {}
    invocations = task_payload.get("invocations") or []
    task_record = task_payload.get("task") or {}
    takeover_metrics = _takeover_metrics(invocations)
    first_useful_seconds = execution.get("firstUsefulOutputSeconds")
    response_speed = _response_speed_score(first_useful_seconds, fastest_first_useful)
    config_quality = 100 if not execution.get("issues") else 80
    human_effort = 100
    pause_resume_attempted, pause_resume_success = _aggregate_pause_resume(execution)
    continuity = 100 if task_key != "YGG-CG-03" else 100 if pause_resume_success else 0
    task_completed = 1 if str(task_record.get("status") or execution.get("finalStatus") or "") == "completed" else 0
    acceptance_pass = 1 if verification_results and all(int(item.get("returncode") or 0) == 0 for item in verification_results) else 0
    outcome_score = _task_outcome_score(task_completed, acceptance_pass)
    weighted_total = _weighted_total_score(response_speed, config_quality, human_effort, continuity, outcome_score)
    notes = [
        f"traceIds={','.join(str(trace_id) for trace_id in execution.get('traceIds') or [])}",
        f"workspace={execution.get('taskWorkspace')}",
    ]
    if execution.get("toolExecutionNames"):
        notes.append("tools=" + ",".join(str(name) for name in execution["toolExecutionNames"]))
    if execution.get("diffSummary", {}).get("changedFiles"):
        notes.append("changes=" + "; ".join(str(item) for item in execution["diffSummary"]["changedFiles"]))
    return {
        "run_id": f"RV-LIVE-{utc_now().strftime('%Y-%m-%d')}-{task_key}",
        "batch_id": batch_id,
        "participant_id": "internal-reviewer",
        "participant_segment": "developer",
        "reviewer_id": "internal-reviewer",
        "agent_system": "yggdrasil-longcat-live",
        "baseline_system": "none",
        "app_id": task_def["appLabel"],
        "task_id": task_key,
        "task_type": task_def["taskType"],
        "environment_id": environment_id,
        "workspace_profile": task_def["workspaceProfile"],
        "provider": provider,
        "model": model,
        "audit_level": execution.get("auditLevel") or "default",
        "coordination_backend": coordination_backend,
        "used_full_infra_0_1": 0,
        "session_count": 1,
        "start_at": execution.get("startAt") or "",
        "first_useful_output_at": execution.get("firstUsefulOutputAt") or "",
        "end_at": execution.get("endAt") or "",
        "first_useful_output_seconds": first_useful_seconds if first_useful_seconds is not None else "",
        "total_duration_seconds": execution.get("totalDurationSeconds") if execution.get("totalDurationSeconds") is not None else "",
        "task_completed_0_1": task_completed,
        "acceptance_pass_0_1": acceptance_pass,
        "completion_quality_0_5": 5 if acceptance_pass else 3 if task_completed else 0,
        "process_stability_0_5": 5 if acceptance_pass else 3 if task_completed else 0,
        "diagnosability_0_5": 5 if acceptance_pass else 3 if task_completed else 0,
        "human_takeover_count": 0,
        "user_clarification_rounds": 0,
        "human_edit_minutes": 0,
        "pause_resume_attempted_0_1": 1 if pause_resume_attempted else 0,
        "pause_resume_success_0_1": 1 if pause_resume_success else 0,
        "recovery_attempted_0_1": 1 if pause_resume_attempted else 0,
        "recovery_success_0_1": 1 if pause_resume_success else 0,
        "configuration_issues_count": len(execution.get("issues") or []),
        "major_issues_count": 0 if acceptance_pass else 1,
        "blocking_issues_count": 0 if acceptance_pass else 1,
        "response_speed_score_0_100": response_speed,
        "config_quality_score_0_100": config_quality,
        "human_effort_score_0_100": human_effort,
        "continuity_recovery_score_0_100": continuity,
        "task_outcome_score_0_100": outcome_score,
        "weighted_total_score_0_100": weighted_total,
        "user_would_reuse_0_5": 5 if acceptance_pass else 3,
        "plan_quality_score_0_100": takeover_metrics.get("planQualityScore0_100", ""),
        "rework_count": takeover_metrics.get("reworkCount", 0),
        "rework_rate": takeover_metrics.get("reworkRate", 0.0),
        "reviewer_notes": " | ".join(notes),
    }
