from __future__ import annotations

from .suite_cases_g4__part01 import *  # noqa: F403,F401

def _g4_contract_verification_results(
    case_payload: dict[str, Any],
    response_text: str,
    runtime_metrics: dict[str, Any],
    window_execution_metrics: dict[str, Any] | None = None,
    invocation_rows: list[dict[str, Any]] | None = None,
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
    require_prefix_cache_key = bool(case_payload.get("acceptanceRequirePrefixCacheKey", False))
    min_cache_evidence = case_payload.get("acceptanceMinCacheEvidence0_1")
    min_independent_steps = case_payload.get("acceptanceMinIndependentSteps")
    min_tool_backed_step_ratio = case_payload.get("acceptanceMinToolBackedStepRatio0_1")
    min_memory_node_count = case_payload.get("acceptanceMinMemoryNodeCount")
    require_experiment_record = bool(case_payload.get("acceptanceRequireExperimentRecord", False))
    require_dispute_list = bool(case_payload.get("acceptanceRequireDisputeList", False))
    required_tool_categories = _g4_string_list(case_payload.get("acceptanceRequireToolCategories"))
    min_successful_tool_executions = case_payload.get("acceptanceMinSuccessfulToolExecutions")
    required_academic_sections = _g4_string_list(case_payload.get("acceptanceRequiredAcademicSections"))
    min_citation_markers = case_payload.get("acceptanceMinCitationMarkers")
    required_deliverables = _g4_string_list(case_payload.get("acceptanceRequiredDeliverables"))
    min_evidence_links = case_payload.get("acceptanceMinEvidenceLinks")
    require_innovation_statement = bool(case_payload.get("acceptanceRequireInnovationStatement", False))
    require_problem_solution_trace = bool(case_payload.get("acceptanceRequireProblemSolutionTrace", False))
    require_limitations_and_future_work = bool(case_payload.get("acceptanceRequireLimitationsAndFutureWork", False))
    require_task_book_progress = bool(case_payload.get("acceptanceRequireTaskBookProgress", False))
    require_foreign_translation = bool(case_payload.get("acceptanceRequireForeignTranslation", False))
    require_defense_qa_ready = bool(case_payload.get("acceptanceRequireDefenseQAReady", False))
    window_execution_metrics = window_execution_metrics or {}
    tool_metrics = _g4_tool_execution_metrics(invocation_rows or [])
    step_metrics = _g4_extract_step_metrics(response_text)

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
            require_prefix_cache_key,
            min_cache_evidence is not None,
            min_independent_steps is not None,
            min_tool_backed_step_ratio is not None,
            min_memory_node_count is not None,
            require_experiment_record,
            require_dispute_list,
            bool(required_tool_categories),
            min_successful_tool_executions is not None,
            bool(required_academic_sections),
            min_citation_markers is not None,
            bool(required_deliverables),
            min_evidence_links is not None,
            require_innovation_statement,
            require_problem_solution_trace,
            require_limitations_and_future_work,
            require_task_book_progress,
            require_foreign_translation,
            require_defense_qa_ready,
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

    if required_academic_sections:
        missing_sections = [
            section for section in required_academic_sections
            if _g4_normalize_match_text(section) not in normalized_response
        ]
        checks.append(
            {
                "command": "g4-required-academic-sections",
                "returncode": 1 if missing_sections else 0,
                "detail": "missing academic sections: " + ", ".join(missing_sections) if missing_sections else "all required academic sections present",
            }
        )
        if missing_sections:
            issues.append("缺少本科论文关键小节: " + ", ".join(missing_sections))

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

    if require_prefix_cache_key:
        actual = float(window_execution_metrics.get("prefixCacheReady0_1") or 0.0)
        checks.append(
            {
                "command": "g4-require-prefix-cache-key",
                "returncode": 0 if actual >= 1.0 else 1,
                "detail": f"prefixCacheReady0_1={actual}, expected=1.0",
            }
        )
        if actual < 1.0:
            issues.append(f"prefixCacheReady0_1 不足: actual={actual}, expected=1.0")

    if min_cache_evidence is not None:
        expected = max(float(min_cache_evidence), 0.0)
        actual = float(window_execution_metrics.get("cacheEvidence0_1") or 0.0)
        checks.append(
            {
                "command": "g4-min-cache-evidence",
                "returncode": 0 if actual >= expected else 1,
                "detail": f"cacheEvidence0_1={actual}, expected>={expected}",
            }
        )
        if actual < expected:
            issues.append(f"cacheEvidence0_1 不足: actual={actual}, expected>={expected}")

    if min_independent_steps is not None:
        expected = max(_g4_int_metric(min_independent_steps), 0)
        actual = _g4_int_metric(step_metrics.get("independentSteps"), 0)
        checks.append(
            {
                "command": "g4-min-independent-steps",
                "returncode": 0 if actual >= expected else 1,
                "detail": f"independentSteps={actual}, expected>={expected}",
            }
        )
        if actual < expected:
            issues.append(f"独立步骤数不足: actual={actual}, expected>={expected}")

    if min_tool_backed_step_ratio is not None:
        expected = max(float(min_tool_backed_step_ratio), 0.0)
        actual = float(step_metrics.get("toolBackedStepRatio0_1") or 0.0)
        checks.append(
            {
                "command": "g4-min-tool-backed-step-ratio",
                "returncode": 0 if actual >= expected else 1,
                "detail": f"toolBackedStepRatio0_1={actual}, expected>={expected}",
            }
        )
        if actual < expected:
            issues.append(f"工具支撑步骤占比不足: actual={actual}, expected>={expected}")

    if min_memory_node_count is not None:
        expected = max(_g4_int_metric(min_memory_node_count), 0)
        actual = max(
            _g4_int_metric(tool_metrics.get("memoryNodeCount"), 0),
            _g4_declared_memory_node_count(response_text),
            0,
        )
        checks.append(
            {
                "command": "g4-min-memory-node-count",
                "returncode": 0 if actual >= expected else 1,
                "detail": f"memoryNodeCount={actual}, expected>={expected}",
            }
        )
        if actual < expected:
            issues.append(f"记忆节点数不足: actual={actual}, expected>={expected}")

    if require_experiment_record:
        has_experiment_record = any(
            marker in normalized_response for marker in (
                _g4_normalize_match_text("实验记录"),
                _g4_normalize_match_text("实验结果"),
                _g4_normalize_match_text("experiment"),
            )
        )
        checks.append(
            {
                "command": "g4-require-experiment-record",
                "returncode": 0 if has_experiment_record else 1,
                "detail": "experiment record marker found" if has_experiment_record else "missing experiment record marker",
            }
        )
        if not has_experiment_record:
            issues.append("缺少实验记录集合")

    if require_dispute_list:
        has_dispute_list = any(
            marker in normalized_response for marker in (
                _g4_normalize_match_text("争议"),
                _g4_normalize_match_text("未决问题"),
                _g4_normalize_match_text("open question"),
            )
        )
        checks.append(
            {
                "command": "g4-require-dispute-list",
                "returncode": 0 if has_dispute_list else 1,
                "detail": "dispute/open-question marker found" if has_dispute_list else "missing dispute/open-question marker",
            }
        )
        if not has_dispute_list:
            issues.append("缺少争议与未决问题清单")

    if required_tool_categories:
        actual_categories = set(str(item).lower() for item in tool_metrics.get("toolCategories") or [])
        actual_categories.update(_g4_declared_tool_categories(response_text))
        expected_categories = [str(item).lower() for item in required_tool_categories]
        missing_categories = [item for item in expected_categories if item not in actual_categories]
        checks.append(
            {
                "command": "g4-require-tool-categories",
                "returncode": 1 if missing_categories else 0,
                "detail": "missing tool categories: " + ", ".join(missing_categories) if missing_categories else "all required tool categories covered",
            }
        )
        if missing_categories:
            issues.append("工具类别覆盖不足: " + ", ".join(missing_categories))

    if min_successful_tool_executions is not None:
        expected = max(_g4_int_metric(min_successful_tool_executions), 0)
        actual = max(_g4_int_metric(tool_metrics.get("successfulToolExecutions"), 0), 0)
        checks.append(
            {
                "command": "g4-min-successful-tool-executions",
                "returncode": 0 if actual >= expected else 1,
                "detail": f"successfulToolExecutions={actual}, expected>={expected}",
            }
        )
        if actual < expected:
            issues.append(f"成功工具动作不足: actual={actual}, expected>={expected}")

    if min_citation_markers is not None:
        expected = max(_g4_int_metric(min_citation_markers), 0)
        actual = _g4_count_citation_markers(response_text)
        checks.append(
            {
                "command": "g4-min-citation-markers",
                "returncode": 0 if actual >= expected else 1,
                "detail": f"citationMarkers={actual}, expected>={expected}",
            }
        )
        if actual < expected:
            issues.append(f"引用标记不足: actual={actual}, expected>={expected}")

    if required_deliverables:
        missing_deliverables = [
            item for item in required_deliverables
            if _g4_normalize_match_text(item) not in normalized_response
        ]
        checks.append(
            {
                "command": "g4-required-deliverables",
                "returncode": 1 if missing_deliverables else 0,
                "detail": "missing deliverables: " + ", ".join(missing_deliverables) if missing_deliverables else "all required deliverables present",
            }
        )
        if missing_deliverables:
            issues.append("缺少关键交付物: " + ", ".join(missing_deliverables))

    if min_evidence_links is not None:
        expected = max(_g4_int_metric(min_evidence_links), 0)
        actual = _g4_count_evidence_links(response_text)
        checks.append(
            {
                "command": "g4-min-evidence-links",
                "returncode": 0 if actual >= expected else 1,
                "detail": f"evidenceLinks={actual}, expected>={expected}",
            }
        )
        if actual < expected:
            issues.append(f"证据链接数量不足: actual={actual}, expected>={expected}")

    if require_innovation_statement:
        has_innovation = _g4_has_any_marker(
            response_text,
            ["创新", "创新点", "贡献", "novel", "novelty", "contribution"],
        )
        checks.append(
            {
                "command": "g4-require-innovation-statement",
                "returncode": 0 if has_innovation else 1,
                "detail": "innovation marker found" if has_innovation else "missing innovation marker",
            }
        )
        if not has_innovation:
            issues.append("缺少创新性或贡献说明")

    if require_problem_solution_trace:
        has_problem = _g4_has_any_marker(response_text, ["问题", "problem", "challenge", "瓶颈"])
        has_solution = _g4_has_any_marker(response_text, ["解决", "solution", "mitigation", "改进"])
        checks.append(
            {
                "command": "g4-require-problem-solution-trace",
                "returncode": 0 if (has_problem and has_solution) else 1,
                "detail": f"problemMarker={has_problem}, solutionMarker={has_solution}",
            }
        )
        if not (has_problem and has_solution):
            issues.append("缺少问题分析与解决路径闭环")

    if require_limitations_and_future_work:
        has_limits = _g4_has_any_marker(response_text, ["局限", "限制", "limitation", "threats to validity"])
        has_future = _g4_has_any_marker(response_text, ["未来工作", "后续工作", "future work", "next steps"])
        checks.append(
            {
                "command": "g4-require-limitations-and-future-work",
                "returncode": 0 if (has_limits and has_future) else 1,
                "detail": f"limitationsMarker={has_limits}, futureWorkMarker={has_future}",
            }
        )
        if not (has_limits and has_future):
            issues.append("缺少局限性与未来工作说明")

    if require_task_book_progress:
        has_task_book_progress = _g4_has_any_marker(response_text, ["任务书", "进度", "milestone", "timeline"])
        checks.append(
            {
                "command": "g4-require-task-book-progress",
                "returncode": 0 if has_task_book_progress else 1,
                "detail": "task-book/progress marker found" if has_task_book_progress else "missing task-book/progress marker",
            }
        )
        if not has_task_book_progress:
            issues.append("缺少任务书与进度执行说明")

    if require_foreign_translation:
        has_foreign_translation = _g4_has_any_marker(response_text, ["外文翻译", "translation", "translated", "原文", "译文"])
        checks.append(
            {
                "command": "g4-require-foreign-translation",
                "returncode": 0 if has_foreign_translation else 1,
                "detail": "foreign translation marker found" if has_foreign_translation else "missing foreign translation marker",
            }
        )
        if not has_foreign_translation:
            issues.append("缺少外文翻译任务与结果说明")

    if require_defense_qa_ready:
        has_defense_ready = _g4_has_any_marker(response_text, ["答辩", "问题回答", "q&a", "问答"])
        checks.append(
            {
                "command": "g4-require-defense-qa-ready",
                "returncode": 0 if has_defense_ready else 1,
                "detail": "defense Q&A marker found" if has_defense_ready else "missing defense Q&A marker",
            }
        )
        if not has_defense_ready:
            issues.append("缺少答辩问答准备说明")

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
    if case_payload.get("expectedPromptProfileId") is not None:
        request_payload.setdefault("promptProfileId", str(case_payload.get("expectedPromptProfileId") or ""))
    if case_payload.get("expectedSeedTemplateId") is not None:
        request_payload.setdefault("seedTemplateId", str(case_payload.get("expectedSeedTemplateId") or ""))
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
