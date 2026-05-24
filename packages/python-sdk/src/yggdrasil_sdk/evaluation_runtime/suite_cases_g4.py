from ._common import *  # noqa: F403,F401
from .bootstrap import *  # noqa: F403,F401
from .scorer import *  # noqa: F403,F401

from ..ops_runtime_scorecard import (  # noqa: F401
    _build_scorecard_row,
    _first_token_seconds,
    _first_useful_output_seconds,
    _format_timestamp,
    _seconds_between,
    _takeover_metrics,
    _tool_execution_names,
)


def _g4_int_metric(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _g4_token_usage(invocation, response_payload: dict[str, Any]) -> dict[str, int]:
    usage = response_payload.get("usage") if isinstance(response_payload.get("usage"), dict) else {}
    input_tokens = _g4_int_metric(usage.get("inputTokens"), int(invocation.input_tokens_used or 0))
    output_tokens = _g4_int_metric(usage.get("outputTokens"), int(invocation.output_tokens_used or 0))
    total_tokens = _g4_int_metric(usage.get("totalTokens"), input_tokens + output_tokens)
    cache_hit_input_tokens = _g4_int_metric(usage.get("cacheHitInputTokens"), 0)
    cache_write_input_tokens = _g4_int_metric(usage.get("cacheWriteInputTokens"), 0)
    non_cache_input_tokens = _g4_int_metric(usage.get("nonCacheInputTokens"), max(input_tokens - cache_hit_input_tokens, 0))
    reasoning_tokens = _g4_int_metric(usage.get("reasoningTokens"), 0)
    return {
        "inputTokens": input_tokens,
        "outputTokens": output_tokens,
        "totalTokens": total_tokens,
        "cacheHitInputTokens": max(cache_hit_input_tokens, 0),
        "cacheWriteInputTokens": max(cache_write_input_tokens, 0),
        "nonCacheInputTokens": max(non_cache_input_tokens, 0),
        "reasoningTokens": max(reasoning_tokens, 0),
    }


def _g4_context_length_observations(response_payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw = response_payload.get("contextLengthObservations") if isinstance(response_payload.get("contextLengthObservations"), list) else []
    observations: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict) or item.get("estimatedTokens") is None:
            continue
        observation: dict[str, Any] = {
            "phase": str(item.get("phase") or "unknown"),
            "source": str(item.get("source") or "unknown"),
            "estimatedTokens": _g4_int_metric(item.get("estimatedTokens")),
        }
        for key in ("messageCount", "itemCount", "roundIndex"):
            if item.get(key) is not None:
                observation[key] = _g4_int_metric(item.get(key))
        if item.get("trigger") is not None:
            observation["trigger"] = str(item.get("trigger") or "")
        observations.append(observation)
    return observations


def _g4_max_context_length_tokens(observations: list[dict[str, Any]]) -> int | None:
    estimated_tokens = [
        _g4_int_metric(item.get("estimatedTokens"))
        for item in observations
        if isinstance(item, dict) and item.get("estimatedTokens") is not None
    ]
    return max(estimated_tokens) if estimated_tokens else None


def _g4_runtime_metrics(response_payload: dict[str, Any]) -> dict[str, Any]:
    raw = response_payload.get("runtimeMetrics") if isinstance(response_payload.get("runtimeMetrics"), dict) else {}
    return {
        "windowIndex": _g4_int_metric(raw.get("windowIndex"), 1),
        "restartCount": _g4_int_metric(raw.get("restartCount"), 0),
        "compressionCount": _g4_int_metric(raw.get("compressionCount"), 0),
        "cumulativeWindowSpanTokens": _g4_int_metric(raw.get("cumulativeWindowSpanTokens"), 0),
        "carryForwardLossCount": _g4_int_metric(raw.get("carryForwardLossCount"), 0),
        "effectiveContextWindow": _g4_int_metric(raw.get("effectiveContextWindow"), 0),
        "windowRestartThreshold": _g4_int_metric(raw.get("windowRestartThreshold"), 0),
        "forcedWindowRestartBudget": _g4_int_metric(raw.get("forcedWindowRestartBudget"), 0),
        "windowSpanTokens": _g4_int_metric(raw.get("windowSpanTokens"), 0),
    }


def _g4_restart_stability_report(case_payload: dict[str, Any], runtime_metrics: dict[str, Any], *, acceptance_pass: int) -> dict[str, Any]:
    raw_tiers = case_payload.get("restartStabilityTiers")
    tiers = [max(_g4_int_metric(item), 0) for item in raw_tiers] if isinstance(raw_tiers, list) else []
    tiers = [item for item in tiers if item > 0]
    restart_count = max(_g4_int_metric(runtime_metrics.get("restartCount")), 0)
    if not tiers:
        return {
            "enabled": False,
            "restartCount": restart_count,
            "tiers": [],
            "restartSuccessRate0_1": 1.0 if acceptance_pass == 1 else 0.0,
            "passed": True,
        }

    tier_results: list[dict[str, Any]] = []
    for tier in sorted(set(tiers)):
        tier_results.append(
            {
                "targetRestarts": tier,
                "observedRestartCount": restart_count,
                "passed": restart_count >= tier and acceptance_pass == 1,
            }
        )
    restart_success_rate = (
        round(sum(1.0 for item in tier_results if item.get("passed")) / len(tier_results), 4)
        if tier_results
        else (1.0 if acceptance_pass == 1 else 0.0)
    )
    return {
        "enabled": True,
        "restartCount": restart_count,
        "tiers": tier_results,
        "restartSuccessRate0_1": restart_success_rate,
        "passed": bool(tier_results) and all(bool(item.get("passed")) for item in tier_results),
    }


def _g4_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text:
            items.append(text)
    return items


def _g4_normalize_match_text(value: str) -> str:
    return " ".join(str(value or "").lower().split())


def _g4_response_text(result_payload: dict[str, Any], response_payload: dict[str, Any]) -> str:
    for candidate in (result_payload.get("assistantText"), response_payload.get("assistantText")):
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()

    raw_response = response_payload.get("rawResponse") if isinstance(response_payload.get("rawResponse"), dict) else {}
    for choice in raw_response.get("choices") or []:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
        if isinstance(content, list):
            parts = [
                str(item.get("text") or "")
                for item in content
                if isinstance(item, dict) and (item.get("type") in {None, "text"})
            ]
            joined = "".join(part for part in parts if part)
            if joined.strip():
                return joined.strip()
    return ""


def _g4_window_execution_records(
    processed_runs: list[dict[str, Any]],
    *,
    workspace_root: Path | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    artifact_refs: list[dict[str, Any]] = []
    for item in processed_runs:
        result_payload = item.get("result") if isinstance(item, dict) else None
        if not isinstance(result_payload, dict):
            continue
        artifact = result_payload.get("windowExecutionArtifact")
        if not isinstance(artifact, dict):
            continue
        artifact_ref = artifact.get("artifactRef") if isinstance(artifact.get("artifactRef"), dict) else None
        if artifact_ref is not None:
            artifact_refs.append(dict(artifact_ref))
        record = artifact.get("record") if isinstance(artifact.get("record"), dict) else None
        if record is None and artifact_ref is not None:
            loaded = _read_external_ref_json(artifact_ref, workspace_root)
            if isinstance(loaded, dict):
                record = loaded
        if isinstance(record, dict):
            records.append(dict(record))
    return records, artifact_refs


def _g4_window_execution_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    if not records:
        return {
            "windowExecutionCount": 0,
            "workTreeContinuity0_1": 0,
            "minimalWorksetRatio0_1": 0.0,
            "planningStubRate0_1": 0.0,
            "retrievalDriftRate0_1": 0.0,
        }

    minimal_workset_ratios: list[float] = []
    continuity_flags: list[bool] = []
    planning_stub_count = 0
    drift_checks = 0
    drift_hits = 0

    for record in records:
        llm = record.get("llm") if isinstance(record.get("llm"), dict) else {}
        if _g4_int_metric(llm.get("planningStub0_1"), 0) == 1:
            planning_stub_count += 1

        work_tree_node_id = str(record.get("workTreeCurrentNodeId") or "").strip()
        response_digest = str(record.get("responseRequirementsDigest") or "").strip()
        restart_digest = str(record.get("restartMessageDigest") or "").strip()
        state_fingerprint = str(record.get("stateFingerprint") or "").strip()
        memory_state = record.get("memoryRetrievalState") if isinstance(record.get("memoryRetrievalState"), dict) else {}
        retrieval_node_id = str(memory_state.get("workTreeNodeId") or "").strip()
        reverse_trace_mode = bool(memory_state.get("reverseTraceMode"))

        continuity_ok = bool(work_tree_node_id and response_digest and restart_digest and state_fingerprint)
        if reverse_trace_mode:
            continuity_ok = continuity_ok and bool(retrieval_node_id)
        continuity_flags.append(continuity_ok)

        if work_tree_node_id and retrieval_node_id:
            drift_checks += 1
            if work_tree_node_id != retrieval_node_id:
                drift_hits += 1

        effective_context_window = max(_g4_int_metric(record.get("effectiveContextWindow"), 0), 0)
        current_context_tokens = max(_g4_int_metric(record.get("currentContextTokenEstimate"), 0), 0)
        if effective_context_window > 0:
            minimal_workset_ratios.append(
                round(max(0.0, 1.0 - min(current_context_tokens / effective_context_window, 1.0)), 4)
            )

    planning_stub_rate = round(planning_stub_count / len(records), 4)
    retrieval_drift_rate = round(drift_hits / drift_checks, 4) if drift_checks else 0.0
    minimal_workset_ratio = (
        round(sum(minimal_workset_ratios) / len(minimal_workset_ratios), 4)
        if minimal_workset_ratios
        else 0.0
    )
    work_tree_continuity = 1 if continuity_flags and all(continuity_flags) and drift_hits == 0 else 0

    return {
        "windowExecutionCount": len(records),
        "workTreeContinuity0_1": work_tree_continuity,
        "minimalWorksetRatio0_1": minimal_workset_ratio,
        "planningStubRate0_1": planning_stub_rate,
        "retrievalDriftRate0_1": retrieval_drift_rate,
    }


def _g4_contract_verification_results(
    case_payload: dict[str, Any],
    response_text: str,
    runtime_metrics: dict[str, Any],
    window_execution_metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_response = _g4_normalize_match_text(response_text)
    required_sections = _g4_string_list(case_payload.get("acceptanceRequiredSections"))
    required_phrases = _g4_string_list(case_payload.get("acceptanceRequiredPhrases"))
    required_any_phrases = _g4_string_list(case_payload.get("acceptanceRequiredAnyPhrases"))
    reject_phrases = _g4_string_list(case_payload.get("acceptanceRejectPhrases"))
    min_restart_count = case_payload.get("acceptanceMinRestartCount")
    min_window_index = case_payload.get("acceptanceMinWindowIndex")
    min_cumulative_window_span_tokens = case_payload.get("acceptanceMinCumulativeWindowSpanTokens")
    min_work_tree_continuity = case_payload.get("acceptanceMinWorkTreeContinuity0_1")
    min_minimal_workset_ratio = case_payload.get("acceptanceMinMinimalWorksetRatio0_1")
    max_planning_stub_rate = case_payload.get("acceptanceMaxPlanningStubRate0_1")
    max_retrieval_drift_rate = case_payload.get("acceptanceMaxRetrievalDriftRate0_1")
    window_execution_metrics = window_execution_metrics or {}

    enabled = any(
        (
            required_sections,
            required_phrases,
            required_any_phrases,
            reject_phrases,
            min_restart_count is not None,
            min_window_index is not None,
            min_cumulative_window_span_tokens is not None,
            min_work_tree_continuity is not None,
            min_minimal_workset_ratio is not None,
            max_planning_stub_rate is not None,
            max_retrieval_drift_rate is not None,
        )
    )
    checks: list[dict[str, Any]] = []
    issues: list[str] = []

    if required_sections:
        missing_sections = [
            section for section in required_sections
            if _g4_normalize_match_text(section) not in normalized_response
        ]
        checks.append(
            {
                "command": "g4-required-sections",
                "returncode": 1 if missing_sections else 0,
                "detail": "missing sections: " + ", ".join(missing_sections) if missing_sections else "all required sections present",
            }
        )
        if missing_sections:
            issues.append("缺少必需小节: " + ", ".join(missing_sections))

    if required_phrases:
        missing_phrases = [
            phrase for phrase in required_phrases
            if _g4_normalize_match_text(phrase) not in normalized_response
        ]
        checks.append(
            {
                "command": "g4-required-phrases",
                "returncode": 1 if missing_phrases else 0,
                "detail": "missing phrases: " + ", ".join(missing_phrases) if missing_phrases else "all required phrases present",
            }
        )
        if missing_phrases:
            issues.append("缺少必需短语: " + ", ".join(missing_phrases))

    if required_any_phrases:
        matched_any_phrase = any(
            _g4_normalize_match_text(phrase) in normalized_response
            for phrase in required_any_phrases
        )
        checks.append(
            {
                "command": "g4-required-any-phrases",
                "returncode": 0 if matched_any_phrase else 1,
                "detail": "matched one required alternative phrase" if matched_any_phrase else "missing any accepted alternative phrase",
            }
        )
        if not matched_any_phrase:
            issues.append("缺少至少一个必需判断短语: " + ", ".join(required_any_phrases))

    if reject_phrases:
        matched_reject_phrases = [
            phrase for phrase in reject_phrases
            if _g4_normalize_match_text(phrase) in normalized_response
        ]
        checks.append(
            {
                "command": "g4-reject-phrases",
                "returncode": 1 if matched_reject_phrases else 0,
                "detail": "matched reject phrases: " + ", ".join(matched_reject_phrases) if matched_reject_phrases else "no reject phrases matched",
            }
        )
        if matched_reject_phrases:
            issues.append("命中拒绝短语: " + ", ".join(matched_reject_phrases))

    if min_restart_count is not None:
        expected = max(_g4_int_metric(min_restart_count), 0)
        actual = max(_g4_int_metric(runtime_metrics.get("restartCount")), 0)
        checks.append(
            {
                "command": "g4-min-restart-count",
                "returncode": 0 if actual >= expected else 1,
                "detail": f"restartCount={actual}, expected>={expected}",
            }
        )
        if actual < expected:
            issues.append(f"restartCount 不足: actual={actual}, expected>={expected}")

    if min_window_index is not None:
        expected = max(_g4_int_metric(min_window_index), 1)
        actual = max(_g4_int_metric(runtime_metrics.get("windowIndex")), 1)
        checks.append(
            {
                "command": "g4-min-window-index",
                "returncode": 0 if actual >= expected else 1,
                "detail": f"windowIndex={actual}, expected>={expected}",
            }
        )
        if actual < expected:
            issues.append(f"windowIndex 不足: actual={actual}, expected>={expected}")

    if min_cumulative_window_span_tokens is not None:
        expected = max(_g4_int_metric(min_cumulative_window_span_tokens), 0)
        actual = max(_g4_int_metric(runtime_metrics.get("cumulativeWindowSpanTokens")), 0)
        checks.append(
            {
                "command": "g4-min-cumulative-window-span-tokens",
                "returncode": 0 if actual >= expected else 1,
                "detail": f"cumulativeWindowSpanTokens={actual}, expected>={expected}",
            }
        )
        if actual < expected:
            issues.append(f"cumulativeWindowSpanTokens 不足: actual={actual}, expected>={expected}")

    if min_work_tree_continuity is not None:
        expected = max(float(min_work_tree_continuity), 0.0)
        actual = float(window_execution_metrics.get("workTreeContinuity0_1") or 0.0)
        checks.append(
            {
                "command": "g4-min-work-tree-continuity",
                "returncode": 0 if actual >= expected else 1,
                "detail": f"workTreeContinuity0_1={actual}, expected>={expected}",
            }
        )
        if actual < expected:
            issues.append(f"workTreeContinuity0_1 不足: actual={actual}, expected>={expected}")

    if min_minimal_workset_ratio is not None:
        expected = max(float(min_minimal_workset_ratio), 0.0)
        actual = float(window_execution_metrics.get("minimalWorksetRatio0_1") or 0.0)
        checks.append(
            {
                "command": "g4-min-minimal-workset-ratio",
                "returncode": 0 if actual >= expected else 1,
                "detail": f"minimalWorksetRatio0_1={actual}, expected>={expected}",
            }
        )
        if actual < expected:
            issues.append(f"minimalWorksetRatio0_1 不足: actual={actual}, expected>={expected}")

    if max_planning_stub_rate is not None:
        expected = max(float(max_planning_stub_rate), 0.0)
        actual = float(window_execution_metrics.get("planningStubRate0_1") or 0.0)
        checks.append(
            {
                "command": "g4-max-planning-stub-rate",
                "returncode": 0 if actual <= expected else 1,
                "detail": f"planningStubRate0_1={actual}, expected<={expected}",
            }
        )
        if actual > expected:
            issues.append(f"planningStubRate0_1 超限: actual={actual}, expected<={expected}")

    if max_retrieval_drift_rate is not None:
        expected = max(float(max_retrieval_drift_rate), 0.0)
        actual = float(window_execution_metrics.get("retrievalDriftRate0_1") or 0.0)
        checks.append(
            {
                "command": "g4-max-retrieval-drift-rate",
                "returncode": 0 if actual <= expected else 1,
                "detail": f"retrievalDriftRate0_1={actual}, expected<={expected}",
            }
        )
        if actual > expected:
            issues.append(f"retrievalDriftRate0_1 超限: actual={actual}, expected<={expected}")

    return {
        "enabled": enabled,
        "passed": not issues,
        "issues": issues,
        "checks": checks,
    }


def _g4_current_context(case_payload: dict[str, Any]) -> list[dict[str, Any]]:
    context_items = [dict(item) for item in case_payload.get("currentContext") or [] if isinstance(item, dict)]
    workspace_root = resolve_workspace_root()
    seen_paths: set[str] = set()

    def _append_file(relative_path: str, item: dict[str, Any], default_id: str) -> None:
        normalized_path = relative_path.strip().replace("\\", "/")
        if not normalized_path or normalized_path in seen_paths:
            return
        file_path = (workspace_root / normalized_path).resolve()
        if not file_path.exists() or not file_path.is_file():
            raise RuntimeError(f"g4 currentContextFiles entry is missing: {normalized_path}")

        encoding = str(item.get("encoding") or "utf-8")
        try:
            content = file_path.read_text(encoding=encoding)
        except UnicodeDecodeError as exc:
            raise RuntimeError(f"g4 currentContextFiles failed to read {normalized_path} with encoding {encoding}: {exc}") from exc

        line_start_raw = item.get("lineStart")
        line_end_raw = item.get("lineEnd")
        if line_start_raw is not None or line_end_raw is not None:
            lines = content.splitlines()
            start_line = max(_g4_int_metric(line_start_raw, 1), 1)
            end_line = min(_g4_int_metric(line_end_raw, len(lines)), len(lines))
            if end_line < start_line:
                raise RuntimeError(f"g4 currentContextFiles has invalid line range for {normalized_path}: {start_line}-{end_line}")
            content = "\n".join(lines[start_line - 1 : end_line])

        max_chars = _g4_int_metric(item.get("maxChars"), 0)
        if max_chars > 0 and len(content) > max_chars:
            content = content[:max_chars]

        prepend_path = bool(item.get("prependPath", True))
        if prepend_path:
            content = f"File: {normalized_path}\n\n{content}"

        context_items.append(
            {
                "id": str(item.get("id") or default_id),
                "title": str(item.get("title") or normalized_path),
                "content": content,
                "importance": float(item.get("importance") or 0.98),
                "rootBranch": str(item.get("rootBranch") or "context"),
            }
        )
        seen_paths.add(normalized_path)

    for index, item in enumerate(case_payload.get("currentContextFiles") or []):
        if not isinstance(item, dict):
            continue
        _append_file(str(item.get("path") or ""), item, f"ctx_file_{index}")

    glob_offset = len(context_items)
    for glob_index, item in enumerate(case_payload.get("currentContextGlobs") or []):
        if not isinstance(item, dict):
            continue
        pattern = str(item.get("pattern") or "").strip().replace("\\", "/")
        if not pattern:
            continue
        max_files = _g4_int_metric(item.get("maxFiles"), 0)
        matched_paths = [
            path for path in sorted(workspace_root.glob(pattern))
            if path.is_file()
        ]
        if max_files > 0:
            matched_paths = matched_paths[:max_files]
        for file_index, file_path in enumerate(matched_paths):
            relative_path = file_path.relative_to(workspace_root).as_posix()
            _append_file(relative_path, item, f"ctx_glob_{glob_offset + glob_index}_{file_index}")
    return context_items


def _g4_preview_request(case_payload: dict[str, Any]) -> dict[str, Any]:
    app_id = str(case_payload.get("appId") or DEFAULT_APP_ID)
    task_type = str(case_payload.get("taskType") or "generic")
    run_type = str(case_payload.get("runType") or "main")
    current_focus = str(case_payload.get("currentFocus") or f"g4-{task_type}-preview")
    current_objective = str(case_payload.get("currentObjective") or "Validate the official G4 prompt contract.")
    resume_message = str(case_payload.get("resumeMessage") or "continue the G4 evaluation flow")
    request_payload = dict(case_payload.get("request") or {})
    request_payload.setdefault("appId", app_id)
    request_payload.setdefault("currentFocus", current_focus)
    request_payload.setdefault("currentObjective", current_objective)
    if case_payload.get("resumeMessage") is not None:
        request_payload["resumeMessage"] = resume_message

    return {
        "appId": app_id,
        "runType": run_type,
        "taskType": task_type,
        "activeCapabilities": list(case_payload.get("activeCapabilities") or []),
        "task": {
            "title": str(case_payload.get("taskTitle") or f"G4 {app_id} Preview"),
            "goal": str(case_payload.get("taskGoal") or "Validate the official Gate 4 prompt contract."),
            "currentFocus": current_focus,
            "currentObjective": current_objective,
            "resumeMessage": resume_message,
        },
        "request": request_payload,
        "resumePath": str(case_payload.get("resumePath")) if case_payload.get("resumePath") is not None else None,
        "currentContext": list(
            case_payload.get("currentContext")
            or [
                {
                    "id": f"ctx_{task_type}_g4",
                    "title": f"G4 {task_type} context",
                    "content": str(
                        case_payload.get("context")
                        or "This evaluation checks official G4 scene assembly, few-shot execution, and scene isolation."
                    ),
                    "rootBranch": "context",
                }
            ]
        ),
    }


def _g4_fetch_preview(case_payload: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    from fastapi.testclient import TestClient
    from yggdrasil_core_api.app import app

    client = TestClient(app)
    app_id = str(case_payload.get("appId") or DEFAULT_APP_ID)
    profiles = client.get("/prompting/prompt-profiles", params={"appId": app_id})
    templates = client.get("/prompting/seed-templates", params={"appId": app_id})
    preview = client.post("/prompting/compile-preview", json=_g4_preview_request(case_payload))
    responses = [profiles, templates, preview]
    if any(response.status_code not in {200, 201} for response in responses):
        raise RuntimeError("g4 prompt preview surface returned non-200 responses")
    return (
        list(profiles.json().get("promptProfiles") or []),
        list(templates.json().get("seedTemplates") or []),
        dict(preview.json().get("compiledPrompt") or {}),
    )


def _g4_validate_prompt_contract(case_payload: dict[str, Any], preview_payload: dict[str, Any], profile_list: list[dict[str, Any]], template_list: list[dict[str, Any]]) -> dict[str, Any]:
    expected_profile_id = str(case_payload.get("expectedPromptProfileId") or "")
    expected_seed_id = str(case_payload.get("expectedSeedTemplateId") or "")
    expected_profile_refs = [str(item) for item in case_payload.get("expectedProfileFewShotRefs") or []]
    expected_seed_refs = [str(item) for item in case_payload.get("expectedSeedFewShotRefs") or []]
    expected_compiled_refs = [str(item) for item in case_payload.get("expectedCompiledFewShotRefs") or []]
    expected_markers = [str(item) for item in case_payload.get("expectedMarkers") or []]
    expected_source_module_id = str(case_payload.get("expectedSourceModuleId") or "").strip()
    expected_message_count = int(case_payload.get("expectedMessageCount") or 0)

    profile = next((item for item in profile_list if str(item.get("id") or "") == expected_profile_id), None)
    template = next((item for item in template_list if str(item.get("id") or "") == expected_seed_id), None)
    if profile is None:
        raise RuntimeError(f"missing expected prompt profile: {expected_profile_id}")
    if template is None:
        raise RuntimeError(f"missing expected seed template: {expected_seed_id}")
    if str(preview_payload.get("promptProfileId") or "") != expected_profile_id:
        raise RuntimeError("g4 preview selected the wrong prompt profile")
    if str(preview_payload.get("seedTemplateId") or "") != expected_seed_id:
        raise RuntimeError("g4 preview selected the wrong seed template")
    if list(profile.get("fewShotRefs") or []) != expected_profile_refs:
        raise RuntimeError("g4 prompt profile few-shot refs do not match the official contract")
    if list(template.get("fewShotRefs") or []) != expected_seed_refs:
        raise RuntimeError("g4 seed template few-shot refs do not match the official contract")
    if list(preview_payload.get("fewShotRefs") or []) != expected_compiled_refs:
        raise RuntimeError("g4 compiled prompt few-shot refs do not match the effective contract")
    if expected_source_module_id and str(template.get("sourceModuleId") or "") != expected_source_module_id:
        raise RuntimeError("g4 seed template is not sourced from the expected scene module")

    messages = [dict(item) for item in preview_payload.get("messages") or [] if isinstance(item, dict)]
    if expected_message_count and len(messages) != expected_message_count:
        raise RuntimeError(f"g4 preview message count mismatch: expected {expected_message_count}, got {len(messages)}")
    few_shot_text = "\n\n".join(str(item.get("content") or "") for item in messages[1:-1])
    for marker in expected_markers:
        if marker not in few_shot_text:
            raise RuntimeError(f"g4 preview few-shot marker missing: {marker}")

    return {
        "appId": preview_payload.get("appId"),
        "promptProfileId": preview_payload.get("promptProfileId"),
        "seedTemplateId": preview_payload.get("seedTemplateId"),
        "scenario": preview_payload.get("scenario"),
        "fewShotRefs": list(preview_payload.get("fewShotRefs") or []),
        "messageCount": len(messages),
    }


def _run_g4_scene_prompt_contract_case(case: dict[str, Any] | None = None) -> dict[str, Any]:
    case_payload = dict(case or {})
    profile_list, template_list, preview_payload = _g4_fetch_preview(case_payload)
    return _g4_validate_prompt_contract(case_payload, preview_payload, profile_list, template_list)


def _run_g4_scene_resume_contract_case(case: dict[str, Any] | None = None) -> dict[str, Any]:
    case_payload = dict(case or {})
    profile_list, template_list, preview_payload = _g4_fetch_preview(case_payload)
    detail = _g4_validate_prompt_contract(case_payload, preview_payload, profile_list, template_list)
    user_sections = dict(preview_payload.get("userSections") or {})
    expected_resume_message = str(case_payload.get("resumeMessage") or "")
    expected_resume_path = str(case_payload.get("resumePath") or "")
    if expected_resume_message and str(user_sections.get("resume_message") or "") != expected_resume_message:
        raise RuntimeError("g4 resume contract did not preserve the expected resume message")
    if expected_resume_path and f"Resume path: {expected_resume_path}" not in str(user_sections.get("task_contract") or ""):
        raise RuntimeError("g4 resume contract did not preserve the expected resume path")
    detail["resumeMessage"] = user_sections.get("resume_message")
    detail["resumePath"] = expected_resume_path
    return detail


def _run_g4_scene_runtime_recovery_case(case: dict[str, Any] | None = None) -> dict[str, Any]:
    from fastapi.testclient import TestClient
    from yggdrasil_agent_runtime.app import app as runtime_app
    from yggdrasil_worker.registry import run_worker_once

    case_payload = dict(case or {})
    app_id = str(case_payload.get("appId") or DEFAULT_APP_ID)
    task_type = str(case_payload.get("taskType") or "generic")
    expected_few_shot_refs = [str(item) for item in case_payload.get("expectedCompiledFewShotRefs") or []]
    expected_scenario = str(case_payload.get("expectedScenario") or "").strip()
    expected_result_status = str(case_payload.get("expectedResultStatus") or "awaiting-approval")
    expected_task_status = str(case_payload.get("expectedTaskStatus") or expected_result_status)
    expected_work_tree_status = str(case_payload.get("expectedWorkTreeStatus") or expected_task_status)
    task = _seed_runtime_task(
        str(case_payload.get("taskId") or new_id("task", app_id, task_type, "g4-recovery", stable=False)),
        app_id=app_id,
        title=str(case_payload.get("taskTitle") or f"G4 {app_id} Recovery Task"),
        goal=str(case_payload.get("taskGoal") or "Validate the official Gate 4 recovery flow."),
        current_focus=str(case_payload.get("currentFocus") or f"g4-{task_type}-recovery"),
        current_objective=str(case_payload.get("currentObjective") or "Pause, resume, and preserve the official scene contract."),
        resume_message=str(case_payload.get("resumeMessage") or "continue the recovery validation"),
    )
    client = TestClient(runtime_app)

    def _root_only_takeover_protocol(task_id: str) -> dict[str, Any]:
        objective = str(case_payload.get("currentObjective") or "Pause, resume, and preserve the official scene contract.")
        return {
            "id": f"takeover_{task_id}",
            "version": "0.1.0",
            "taskId": task_id,
            "taskType": task_type,
            "runType": "main",
            "currentPhase": "execute",
            "status": "executing",
            "objective": objective,
            "objectiveSummary": objective,
            "ambiguities": [],
            "constraints": [],
            "plan": [],
            "workTree": {
                "version": "0.2.0",
                "id": f"work_tree_{task_id}",
                "taskId": task_id,
                "rootNodeId": "root",
                "rootObjective": objective,
                "status": "active",
                "currentNodeId": "root",
                "loadedNodeIds": ["root"],
                "activePathNodeIds": ["root"],
                "pcMemo": "continue:root",
                "entropyBudgetRemaining": 8,
                "versionCounter": 1,
                "nodes": [
                    {
                        "id": "root",
                        "title": "root",
                        "parentNodeId": None,
                        "questionsItAnswers": ["next step"],
                        "nodeText": "Deliver the final result on the root node.",
                        "localGoal": "Deliver the final result on the root node.",
                        "workingNodeAnnotation": "<Working_Node: root>",
                        "phase": "delivery",
                        "status": "in-progress",
                        "childNodeIds": [],
                        "detailLevel": 0,
                        "recoveryAnchor": "resume:root",
                    }
                ],
            },
        }

    start_payload = {
        "appId": app_id,
        "taskType": task_type,
        "currentFocus": str(case_payload.get("currentFocus") or task.get("currentFocus") or "g4-recovery"),
        "currentObjective": str(case_payload.get("currentObjective") or task.get("currentObjective") or "g4 recovery"),
        "currentContext": list(
            case_payload.get("currentContext")
            or [
                {
                    "id": "ctx_g4_recovery",
                    "title": "G4 recovery contract",
                    "content": str(
                        case_payload.get("context")
                        or "The resumed run must preserve the official app scene, few-shot refs, and recovery instructions."
                    ),
                    "importance": 0.99,
                }
            ]
        ),
        "protectedItems": case_payload.get("protectedItems") or [{"kind": "node", "id": "ctx_g4_recovery"}],
        "allowModelFallback": bool(case_payload.get("allowFallback", True)),
        "temperature": float(case_payload.get("temperature") or 0.1),
        "maxTokens": int(case_payload.get("maxTokens") or 240),
    }
    if not case_payload.get("takeoverProtocol"):
        start_payload["takeoverProtocol"] = _root_only_takeover_protocol(task["id"])
    started = client.post(f"/runtime/tasks/{task['id']}/start", json=start_payload)
    if started.status_code != 202:
        raise RuntimeError(f"g4 runtime recovery start failed: {started.text}")
    pause_request = client.post(
        f"/runtime/tasks/{task['id']}/pause-request",
        json={
            "reason": "g4-evaluation-pause",
            "resumeMessage": str(case_payload.get("resumeMessage") or "continue the recovery validation"),
        },
    )
    if pause_request.status_code != 202:
        raise RuntimeError(f"g4 runtime recovery pause request failed: {pause_request.text}")
    first = run_worker_once("agent-runtime")
    if (first.get("result") or {}).get("status") != "paused":
        raise RuntimeError(f"g4 runtime recovery pause step failed: {json.dumps(first, ensure_ascii=False)}")
    resume_token = ((first.get("result") or {}).get("snapshot") or {}).get("resumeToken")
    resumed = client.post(
        f"/runtime/tasks/{task['id']}/resume",
        json={
            "resumeToken": resume_token,
            "nextObjective": str(case_payload.get("resumeObjective") or "finish the G4 recovery flow"),
        },
    )
    if resumed.status_code != 202:
        raise RuntimeError(f"g4 runtime recovery resume failed: {resumed.text}")
    second = run_worker_once("agent-runtime")
    if (second.get("result") or {}).get("status") != expected_result_status:
        raise RuntimeError(f"g4 runtime recovery completion failed: {json.dumps(second, ensure_ascii=False)}")

    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        task_repository = TaskRepository(session)
        prompt_repository = PromptAssetRepository(session)
        runtime_repository = RuntimeRepository(session)
        persisted_task = task_repository.get_task(task["id"])
        invocations = runtime_repository.list_model_invocations(task_id=task["id"], limit=5)
        if not invocations:
            raise RuntimeError("g4 runtime recovery did not persist any model invocation")
        invocation = invocations[0]
        prompt_artifact = prompt_repository.get_prompt_compile_artifact(invocation.prompt_compile_artifact_id or "")
        if prompt_artifact is None:
            raise RuntimeError("g4 runtime recovery prompt artifact is missing")

    request_payload = _read_external_ref_json(invocation.request_ref, resolve_workspace_root()) or {}
    prompt_metadata = dict(request_payload.get("promptMetadata") or {})
    if list(prompt_metadata.get("fewShotRefs") or []) != expected_few_shot_refs:
        raise RuntimeError("g4 runtime recovery prompt metadata few-shot refs do not match the official contract")
    if expected_scenario and str(prompt_artifact.scenario or "") != expected_scenario:
        raise RuntimeError("g4 runtime recovery scenario drifted during pause/resume")
    if prompt_artifact.app_id != app_id:
        raise RuntimeError("g4 runtime recovery persisted prompt artifact under the wrong app scope")
    if persisted_task is None or str(persisted_task.status or "") != expected_task_status:
        raise RuntimeError(
            f"g4 runtime recovery task status drifted: expected {expected_task_status}, got {persisted_task.status if persisted_task is not None else 'missing'}"
        )

    takeover_protocol = dict((second.get("result") or {}).get("takeoverProtocol") or {})
    work_tree_status = str((takeover_protocol.get("workTree") or {}).get("status") or "") if takeover_protocol else ""
    if expected_work_tree_status and work_tree_status != expected_work_tree_status:
        raise RuntimeError(
            f"g4 runtime recovery work tree drifted: expected {expected_work_tree_status}, got {work_tree_status or 'missing'}"
        )

    return {
        "appId": app_id,
        "taskId": task["id"],
        "pauseStatus": (first.get("result") or {}).get("status"),
        "resumeStatus": (second.get("result") or {}).get("status"),
        "expectedResultStatus": expected_result_status,
        "expectedTaskStatus": expected_task_status,
        "promptCompileArtifactId": invocation.prompt_compile_artifact_id,
        "fewShotRefs": list(prompt_metadata.get("fewShotRefs") or []),
        "scenario": prompt_artifact.scenario,
        "taskStatus": persisted_task.status if persisted_task is not None else None,
        "workTreeStatus": work_tree_status,
    }


def _run_g4_scene_switch_isolation_case(case: dict[str, Any] | None = None) -> dict[str, Any]:
    case_payload = dict(case or {})
    sequence = [dict(item) for item in case_payload.get("sequence") or [] if isinstance(item, dict)]
    if not sequence:
        raise RuntimeError("g4 scene switch isolation case requires a non-empty sequence")
    steps: list[dict[str, Any]] = []
    for entry in sequence:
        profile_list, template_list, preview_payload = _g4_fetch_preview(entry)
        detail = _g4_validate_prompt_contract(entry, preview_payload, profile_list, template_list)
        compiled_text = "\n\n".join(str(item.get("content") or "") for item in preview_payload.get("messages") or [] if isinstance(item, dict))
        forbidden_markers = [str(item) for item in entry.get("forbiddenMarkers") or []]
        for marker in forbidden_markers:
            if marker and marker in compiled_text:
                raise RuntimeError(f"g4 scene switch leak detected for {entry.get('appId')}: {marker}")
        steps.append(
            {
                "appId": detail["appId"],
                "scenario": detail["scenario"],
                "fewShotRefs": detail["fewShotRefs"],
            }
        )
    return {
        "sequence": [str(item.get("appId") or "") for item in sequence],
        "steps": steps,
    }


def _run_g4_live_provider_matrix_case(case: dict[str, Any] | None = None) -> dict[str, Any]:
    from datetime import datetime, timedelta
    import os

    from fastapi.testclient import TestClient
    from yggdrasil_agent_runtime.app import app as runtime_app
    from yggdrasil_sdk.llm_runtime import load_runtime_candidate_models
    from yggdrasil_worker.registry import run_worker_once

    case_payload = dict(case or {})
    app_id = str(case_payload.get("appId") or DEFAULT_APP_ID)
    task_type = str(case_payload.get("taskType") or "generic")
    requested_provider = str(case_payload.get("requestedProvider") or "longcat")
    requested_model = str(case_payload.get("requestedModel") or "LongCat-2.0-Preview")
    expected_prompt_profile_id = str(case_payload.get("expectedPromptProfileId") or "")
    expected_seed_template_id = str(case_payload.get("expectedSeedTemplateId") or "")
    expected_few_shot_refs = [str(item) for item in case_payload.get("expectedCompiledFewShotRefs") or []]
    expected_result_status = str(case_payload.get("expectedResultStatus") or "awaiting-approval")
    expected_task_status = str(case_payload.get("expectedTaskStatus") or expected_result_status)
    task_id = str(case_payload.get("taskId") or new_id("task", app_id, task_type, requested_provider, stable=False))
    candidate_models = [
        dict(candidate)
        for candidate in load_runtime_candidate_models() or []
        if str(candidate.get("provider") or "") == requested_provider and str(candidate.get("model") or "") == requested_model
    ]
    require_live = bool(case_payload.get("requireLive", False))
    if require_live and not candidate_models:
        raise RuntimeError(f"requested live candidate is unavailable: {requested_provider}/{requested_model}")

    task = _seed_runtime_task(
        task_id,
        app_id=app_id,
        title=str(case_payload.get("taskTitle") or f"G4 {app_id} Live Matrix"),
        goal=str(case_payload.get("taskGoal") or "Validate the official G4 provider matrix task."),
        current_focus=str(case_payload.get("currentFocus") or f"g4-{task_type}-live"),
        current_objective=str(case_payload.get("currentObjective") or "Execute the official G4 provider matrix task."),
        resume_message=str(case_payload.get("resumeMessage") or "continue the live G4 evaluation"),
        token_budget_total=int(case_payload["budgetTokenTotal"]) if case_payload.get("budgetTokenTotal") is not None else None,
        cost_budget_total=float(case_payload.get("costBudgetTotal") or 5.0),
    )
    client = TestClient(runtime_app)
    start_payload = {
        "appId": app_id,
        "taskType": task_type,
        "currentFocus": str(case_payload.get("currentFocus") or task.get("currentFocus") or "g4-live"),
        "currentObjective": str(case_payload.get("currentObjective") or task.get("currentObjective") or "g4 live task"),
        "currentContext": _g4_current_context(case_payload),
        "protectedItems": case_payload.get("protectedItems") or [],
        "allowModelFallback": bool(case_payload.get("allowFallback", False)),
        "allowToolExecution": bool(case_payload.get("allowToolExecution", False)),
        "temperature": float(case_payload.get("temperature") or 0.1),
        "maxTokens": int(case_payload.get("maxTokens") or 320),
    }
    if case_payload.get("auditLevel") is not None:
        start_payload["auditLevel"] = str(case_payload.get("auditLevel") or "default")
    if case_payload.get("effectiveContextWindow") is not None:
        start_payload["effectiveContextWindow"] = int(case_payload["effectiveContextWindow"])
    if case_payload.get("windowRestartRatio") is not None:
        start_payload["windowRestartRatio"] = float(case_payload["windowRestartRatio"])
    if case_payload.get("windowRestartThreshold") is not None:
        start_payload["windowRestartThreshold"] = int(case_payload["windowRestartThreshold"])
    if case_payload.get("forcedWindowRestartBudget") is not None:
        start_payload["forcedWindowRestartBudget"] = int(case_payload["forcedWindowRestartBudget"])
    if case_payload.get("maxToolRounds") is not None:
        start_payload["maxToolRounds"] = int(case_payload["maxToolRounds"])
    if case_payload.get("responseRequirements") is not None:
        start_payload["responseRequirements"] = str(case_payload["responseRequirements"])
    if case_payload.get("restartMessage") is not None:
        start_payload["restartMessage"] = str(case_payload["restartMessage"])
    if candidate_models:
        start_payload["candidateModels"] = candidate_models
    started = client.post(f"/runtime/tasks/{task['id']}/start", json=start_payload)
    if started.status_code != 202:
        raise RuntimeError(f"g4 provider matrix start failed: {started.text}")

    processed_runs: list[dict[str, Any]] = []
    max_window_cycles = max(int(case_payload.get("maxWindowCycles") or 12), int(case_payload.get("forcedWindowRestartBudget") or 0) + 4)
    while True:
        processed = run_worker_once("agent-runtime")
        result_payload = dict(processed.get("result") or {})
        processed_runs.append(processed)
        if result_payload.get("status") in {"restarting", "continuing"}:
            if len(processed_runs) >= max_window_cycles:
                raise RuntimeError(
                    f"g4 provider matrix exceeded maxWindowCycles={max_window_cycles}: {json.dumps(processed_runs[-1], ensure_ascii=False)}"
                )
            continue
        if result_payload.get("status") != expected_result_status:
            raise RuntimeError(f"g4 provider matrix worker failed: {json.dumps(processed, ensure_ascii=False)}")
        break

    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        task_repository = TaskRepository(session)
        prompt_repository = PromptAssetRepository(session)
        runtime_repository = RuntimeRepository(session)
        persisted_task = task_repository.get_task(task["id"])
        invocations = runtime_repository.list_model_invocations(task_id=task["id"], limit=5)
        if not invocations:
            raise RuntimeError("g4 provider matrix did not persist any model invocation")
        invocation = invocations[0]
        prompt_artifact = prompt_repository.get_prompt_compile_artifact(invocation.prompt_compile_artifact_id or "")
        if prompt_artifact is None:
            raise RuntimeError("g4 provider matrix prompt artifact is missing")

    if require_live and invocation.status != "completed":
        raise RuntimeError(f"g4 provider matrix live invocation did not complete: {invocation.status}")
    if require_live and invocation.resolved_provider not in {requested_provider, str(case_payload.get('providerAlias') or '')}:
        raise RuntimeError(
            f"g4 provider matrix provider mismatch: expected {requested_provider}, got {invocation.resolved_provider or 'unknown'}"
        )

    request_payload = _read_external_ref_json(invocation.request_ref, resolve_workspace_root()) or {}
    response_payload = _read_external_ref_json(invocation.response_ref, resolve_workspace_root()) or {}
    processed_request = dict((processed.get("payload") or {}).get("payload") or {})
    takeover_protocol = processed_request.get("takeoverProtocol")
    if isinstance(takeover_protocol, dict):
        request_payload = dict(request_payload)
        request_payload.setdefault("takeoverProtocol", takeover_protocol)
    prompt_metadata = dict(request_payload.get("promptMetadata") or {})
    if expected_prompt_profile_id and str(prompt_metadata.get("promptProfileId") or "") != expected_prompt_profile_id:
        raise RuntimeError("g4 provider matrix prompt profile drifted from the official scene contract")
    if expected_seed_template_id and str(prompt_metadata.get("seedTemplateId") or "") != expected_seed_template_id:
        raise RuntimeError("g4 provider matrix seed template drifted from the official scene contract")
    if expected_few_shot_refs and list(prompt_metadata.get("fewShotRefs") or []) != expected_few_shot_refs:
        raise RuntimeError("g4 provider matrix few-shot refs drifted from the official scene contract")
    final_task_status = str((persisted_task.status if persisted_task is not None else None) or result_payload.get("status") or "")
    if final_task_status != expected_task_status:
        raise RuntimeError(
            f"g4 provider matrix final task status drifted: expected {expected_task_status}, got {final_task_status or 'missing'}"
        )

    invocation_rows = [
        {
            "record": invocation.model_dump(by_alias=True, mode="json"),
            "requestPayload": request_payload,
            "responsePayload": response_payload,
        }
    ]
    task_record = persisted_task.model_dump(by_alias=True, mode="json") if persisted_task is not None else {}
    start_at_raw = task_record.get("startedAt")
    end_at_raw = task_record.get("endedAt")
    started_at = datetime.fromisoformat(str(start_at_raw).replace("Z", "+00:00")) if start_at_raw else None
    ended_at = datetime.fromisoformat(str(end_at_raw).replace("Z", "+00:00")) if end_at_raw else None
    first_token_seconds = _first_token_seconds(invocation_rows)
    first_useful_output_seconds = _first_useful_output_seconds(invocation_rows)
    runtime_metrics = _g4_runtime_metrics(response_payload)
    response_text = _g4_response_text(result_payload, response_payload)
    window_execution_records, window_execution_refs = _g4_window_execution_records(
        processed_runs,
        workspace_root=resolve_workspace_root(),
    )
    window_execution_metrics = _g4_window_execution_metrics(window_execution_records)
    contract_verification = _g4_contract_verification_results(
        case_payload,
        response_text,
        runtime_metrics,
        window_execution_metrics,
    )
    verification_results = [{"command": "g4-live-guard", "returncode": 0}]
    verification_results.extend(contract_verification["checks"])
    execution = {
        "taskRuntime": {
            "task": task_record,
            "invocations": invocation_rows,
        },
        "verification": verification_results,
        "issues": [{"type": "acceptance", "detail": issue} for issue in contract_verification["issues"]],
        "traceIds": [str(invocation.trace_id)] if invocation.trace_id else [],
        "taskWorkspace": str(resolve_workspace_root()),
        "toolExecutionNames": _tool_execution_names(invocation_rows),
        "firstTokenSeconds": first_token_seconds,
        "firstTokenAt": _format_timestamp(started_at + timedelta(seconds=first_token_seconds)) if started_at and first_token_seconds is not None else None,
        "firstUsefulOutputSeconds": first_useful_output_seconds,
        "firstUsefulOutputAt": _format_timestamp(started_at + timedelta(seconds=first_useful_output_seconds)) if started_at and first_useful_output_seconds is not None else None,
        "startAt": _format_timestamp(started_at),
        "endAt": _format_timestamp(ended_at),
        "totalDurationSeconds": _seconds_between(started_at, ended_at),
        "finalStatus": task_record.get("status") or result_payload.get("status"),
        "pauseResumeAttempted": False,
        "pauseResumeSuccess": False,
    }
    scorecard_row = _build_scorecard_row(
        task_key=str(case_payload.get("matrixKey") or case_payload.get("id") or task_id),
        task_def={
            "appLabel": app_id,
            "taskType": task_type,
            "workspaceProfile": str(case_payload.get("workspaceProfile") or "g4-official"),
        },
        execution=execution,
        fastest_first_useful=first_useful_output_seconds,
        provider=str(invocation.resolved_provider or requested_provider),
        model=str(invocation.resolved_model or requested_model),
        batch_id=str(case_payload.get("batchId") or "G4-PROVIDER-MATRIX"),
        environment_id=str(case_payload.get("environmentId") or "g4-provider-matrix"),
        coordination_backend="memory",
    )
    takeover_metrics = _takeover_metrics(invocation_rows)
    token_usage = _g4_token_usage(invocation, response_payload)
    context_length_observations = _g4_context_length_observations(response_payload)
    max_context_length_tokens = _g4_max_context_length_tokens(context_length_observations)
    restart_success_rate = 1.0 if final_task_status == expected_task_status else 0.0
    acceptance_pass = int(scorecard_row.get("acceptance_pass_0_1") or 0)
    restart_stability_report = _g4_restart_stability_report(
        case_payload,
        runtime_metrics,
        acceptance_pass=acceptance_pass,
    )
    prompt_artifact_record = prompt_artifact.model_dump(by_alias=True, mode="json")
    evaluation_sandbox = os.environ.get("YGGDRASIL_EVAL_ACTIVE_SANDBOX_ROOT")
    sandbox_state_root = os.environ.get("YGGDRASIL_STATE_ROOT")
    audit_level = str(case_payload.get("auditLevel") or request_payload.get("auditLevel") or response_payload.get("auditLevel") or "default")
    provider_matrix_entry = {
        "matrixKey": str(case_payload.get("matrixKey") or case_payload.get("id") or task_id),
        "appId": app_id,
        "taskType": task_type,
        "provider": str(invocation.resolved_provider or requested_provider),
        "model": str(invocation.resolved_model or requested_model),
        "scenario": str(prompt_artifact.scenario or prompt_metadata.get("scenario") or ""),
        "promptProfileId": str(prompt_metadata.get("promptProfileId") or ""),
        "seedTemplateId": str(prompt_metadata.get("seedTemplateId") or ""),
        "fewShotRefs": list(prompt_metadata.get("fewShotRefs") or []),
        "firstTokenSeconds": first_token_seconds,
        "firstUsefulOutputSeconds": first_useful_output_seconds,
        "humanTakeoverCount": 0,
        "userClarificationRounds": 0,
        "planQualityScore0_100": takeover_metrics.get("planQualityScore0_100"),
        "reworkCount": takeover_metrics.get("reworkCount"),
        "reworkRate": takeover_metrics.get("reworkRate"),
        "inputTokens": token_usage["inputTokens"],
        "outputTokens": token_usage["outputTokens"],
        "totalTokens": token_usage["totalTokens"],
        "cacheHitInputTokens": token_usage["cacheHitInputTokens"],
        "cacheWriteInputTokens": token_usage["cacheWriteInputTokens"],
        "nonCacheInputTokens": token_usage["nonCacheInputTokens"],
        "reasoningTokens": token_usage["reasoningTokens"],
        "tokenUsage": token_usage,
        "contextLengthObservations": context_length_observations,
        "maxContextLengthTokens": max_context_length_tokens,
        "windowIndex": runtime_metrics["windowIndex"],
        "restartCount": runtime_metrics["restartCount"],
        "compressionCount": runtime_metrics["compressionCount"],
        "cumulativeWindowSpanTokens": runtime_metrics["cumulativeWindowSpanTokens"],
        "carryForwardLossCount": runtime_metrics["carryForwardLossCount"],
        "effectiveContextWindow": runtime_metrics["effectiveContextWindow"],
        "windowRestartThreshold": runtime_metrics["windowRestartThreshold"],
        "restartSuccessRate0_1": restart_stability_report.get("restartSuccessRate0_1", restart_success_rate),
        "windowTransitionCount": max(len(processed_runs) - 1, 0),
        "windowExecutionCount": window_execution_metrics["windowExecutionCount"],
        "workTreeContinuity0_1": window_execution_metrics["workTreeContinuity0_1"],
        "minimalWorksetRatio0_1": window_execution_metrics["minimalWorksetRatio0_1"],
        "planningStubRate0_1": window_execution_metrics["planningStubRate0_1"],
        "retrievalDriftRate0_1": window_execution_metrics["retrievalDriftRate0_1"],
        "workTreeContinuityThreshold0_1": float(case_payload.get("acceptanceMinWorkTreeContinuity0_1") or 0.0),
        "minimalWorksetThreshold0_1": float(case_payload.get("acceptanceMinMinimalWorksetRatio0_1") or 0.0),
        "acceptancePass0_1": acceptance_pass,
        "officialAcceptancePassed0_1": 1 if contract_verification["passed"] else 0,
        "goalCompletion0_1": 1 if final_task_status == expected_task_status else 0,
        "deliveryCompletion0_1": 1 if final_task_status == expected_task_status and acceptance_pass == 1 and contract_verification["passed"] else 0,
        "parityPairKey": str(case_payload.get("parityPairKey") or ""),
        "parityRole": str(case_payload.get("parityRole") or ""),
        "qualityDeltaThreshold0_100": float(case_payload.get("qualityDeltaThreshold0_100") or 8.0),
        "pass": final_task_status == expected_task_status and acceptance_pass == 1,
        "promptCompileArtifactId": invocation.prompt_compile_artifact_id,
        "auditLevel": audit_level,
    }
    assistant_preview = normalize_excerpt(response_text or str(result_payload.get("assistantText") or ""), 240)
    if bool(case_payload.get("failOnAcceptanceViolation")) and not contract_verification["passed"]:
        issues_text = "; ".join(contract_verification["issues"]) or "unknown acceptance failure"
        sandbox_text = evaluation_sandbox or "unknown"
        raise RuntimeError(
            f"g4 provider matrix acceptance failed for {provider_matrix_entry['matrixKey']}: {issues_text} | sandbox={sandbox_text} | response={assistant_preview}"
        )
    if bool(case_payload.get("failOnRestartStabilityViolation")) and restart_stability_report.get("enabled") and not restart_stability_report.get("passed"):
        failed_tiers = [
            str(item.get("targetRestarts"))
            for item in restart_stability_report.get("tiers") or []
            if isinstance(item, dict) and not bool(item.get("passed"))
        ]
        sandbox_text = evaluation_sandbox or "unknown"
        raise RuntimeError(
            "g4 provider matrix restart stability failed "
            f"for {provider_matrix_entry['matrixKey']}: failed tiers={','.join(failed_tiers) or 'unknown'} "
            f"| sandbox={sandbox_text} | response={assistant_preview}"
        )
    return {
        **provider_matrix_entry,
        "liveScenario": {
            "taskId": task["id"],
            "invocationId": invocation.id,
            "invocationStatus": invocation.status,
            "provider": provider_matrix_entry["provider"],
            "model": provider_matrix_entry["model"],
            "traceId": invocation.trace_id,
            "latencyMs": invocation.latency_ms,
            "totalTokens": token_usage["totalTokens"],
            "costUsed": float(invocation.cost_used or 0.0),
            "tokenUsage": token_usage,
            "contextLengthObservations": context_length_observations,
            "maxContextLengthTokens": max_context_length_tokens,
            "runtimeMetrics": runtime_metrics,
            "windowTransitionCount": max(len(processed_runs) - 1, 0),
            "promptCompileArtifactId": invocation.prompt_compile_artifact_id,
        },
        "providerMatrixEntry": provider_matrix_entry,
        "scorecardRow": scorecard_row,
        "evaluationSandbox": {
            "root": evaluation_sandbox,
            "stateRoot": sandbox_state_root,
            "workspaceRoot": os.environ.get("YGGDRASIL_EVAL_ACTIVE_WORKSPACE_ROOT"),
            "databasePath": os.environ.get("YGGDRASIL_EVAL_ACTIVE_DB_PATH"),
        },
        "artifactRefs": {
            "requestRef": invocation.request_ref.model_dump(mode="json") if invocation.request_ref is not None else None,
            "responseRef": invocation.response_ref.model_dump(mode="json") if invocation.response_ref is not None else None,
            "compiledMessagesRef": prompt_artifact_record.get("compiledMessagesRef"),
            "promptCompileArtifactId": invocation.prompt_compile_artifact_id,
            "windowExecutionRefs": window_execution_refs,
        },
        "dialogueAudit": {
            "auditLevel": audit_level,
            "requestRef": invocation.request_ref.model_dump(mode="json") if invocation.request_ref is not None else None,
            "responseRef": invocation.response_ref.model_dump(mode="json") if invocation.response_ref is not None else None,
            "compiledMessagesRef": prompt_artifact_record.get("compiledMessagesRef"),
            "windowExecutionRefs": window_execution_refs,
        },
        "officialAcceptance": {
            **contract_verification,
            "responsePreview": assistant_preview,
        },
        "restartStabilityReport": restart_stability_report,
        "windowExecutionMetrics": window_execution_metrics,
        "processedRuns": [dict(item) for item in processed_runs],
        "assistantPreview": assistant_preview,
    }


__all__ = [name for name in globals() if not name.startswith("__")]