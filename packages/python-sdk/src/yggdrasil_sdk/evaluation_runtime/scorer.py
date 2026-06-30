from ._common import *  # noqa: F403,F401
from .bootstrap import _evaluation_root

def _read_text_fixture(name: str, workspace_root: Path | None = None) -> str:
    return (_evaluation_root(workspace_root) / "fixtures" / name).read_text(encoding="utf-8")

def _tokenize_text(value: str) -> set[str]:
    tokens = re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]{2,}", value.lower())
    return {token for token in tokens if token}

def _keyword_matches(text: str, expected_keywords: list[str]) -> list[str]:
    lowered = text.lower()
    return [keyword for keyword in expected_keywords if keyword.lower() in lowered]

def _coverage_ratio(text: str, expected_keywords: list[str]) -> float:
    if not expected_keywords:
        return 1.0
    matches = _keyword_matches(text, expected_keywords)
    return round(len(matches) / len(expected_keywords), 4)

def _fragment_score(fragment: dict[str, Any], query_terms: set[str]) -> int:
    haystack = " ".join(
        [
            str(fragment.get("normalizedText") or ""),
            " ".join(str(hint) for hint in fragment.get("relatedHints") or []),
        ]
    ).lower()
    return sum(3 if term in haystack else 0 for term in query_terms)

def _select_flat_fragments(fragments: list[dict[str, Any]], query: str, top_k: int) -> list[str]:
    query_terms = _tokenize_text(query)
    ranked = sorted(
        fragments,
        key=lambda fragment: (
            _fragment_score(fragment, query_terms),
            int(fragment.get("approxTokens") or 0),
        ),
        reverse=True,
    )
    selected: list[str] = []
    for fragment in ranked[: max(top_k, 1)]:
        text = str(fragment.get("normalizedText") or "").strip()
        if text:
            selected.append(text)
    return selected

def _build_memory_tree_context(bundle: dict[str, Any], top_k: int) -> list[str]:
    blocks: list[str] = []
    summary = str(bundle.get("naturalLanguageSummary") or "").strip()
    if summary:
        blocks.append(f"检索摘要:\n{summary}")

    node_payloads = bundle.get("nodePayloads") or []
    related_name_map = bundle.get("relatedNameMap") or {}
    child_name_map = bundle.get("childNameMap") or {}
    for payload in node_payloads[: max(top_k, 1)]:
        node_id = str(payload.get("id") or "")
        title = str(payload.get("title") or node_id or "memory-node")
        content = str(payload.get("content") or "").strip()
        child_names = ", ".join(str(name) for name in child_name_map.get(node_id) or [])
        related_names = ", ".join(str(name) for name in related_name_map.get(node_id) or [])
        sections = [f"标题: {title}"]
        if content:
            sections.append(f"内容: {content}")
        if child_names:
            sections.append(f"子节点: {child_names}")
        if related_names:
            sections.append(f"关联节点: {related_names}")
        blocks.append("\n".join(sections))
    return blocks

def _strategy_fallback_answer(query: str, context_blocks: list[str]) -> dict[str, Any]:
    if not context_blocks:
        output = f"当前没有挂载任何记忆上下文，无法对问题给出可信回答：{query}"
    else:
        preview = "\n\n".join(normalize_excerpt(block, 220) for block in context_blocks[:3])
        output = f"基于当前检索到的上下文，可以确认这些证据片段与问题直接相关：\n\n{preview}"
    return {
        "mode": "fallback",
        "provider": "fallback",
        "model": "evaluation-fallback",
        "outputText": output,
        "usage": {
            "inputTokens": max(1, len(query) // 4),
            "outputTokens": max(1, len(output) // 4),
            "totalTokens": max(1, len(query) // 4) + max(1, len(output) // 4),
        },
        "costUsed": 0.0,
        "finishReason": "fallback",
    }

def _generate_strategy_answer(case: dict[str, Any], query: str, strategy_name: str, context_blocks: list[str]) -> dict[str, Any]:
    try:
        from yggdrasil_model_providers import invoke_model
    except Exception:
        return _strategy_fallback_answer(query, context_blocks)

    messages = [
        {
            "role": "system",
            "content": (
                "你是世界树计划的评测模型。必须严格依据提供的上下文作答；若上下文不足，就明确说明缺失，"
                "不要捏造系统能力。输出控制在 180 字以内。"
            ),
        },
        {
            "role": "user",
            "content": "\n\n".join(
                [
                    f"策略: {strategy_name}",
                    f"问题: {query}",
                    "可用上下文:",
                    "\n\n".join(context_blocks) if context_blocks else "<no-context>",
                ]
            ),
        },
    ]
    requested_model = str(case.get("requestedModel") or "LongCat-2.0")
    requested_provider = str(case.get("requestedProvider") or "longcat")
    workspace_root = resolve_workspace_root()
    temperature = float(case.get("temperature") or 0.1)
    max_tokens = int(case.get("maxTokens") or 220)

    try:
        with observe_span(
            "evaluation",
            f"benchmark.strategy.{strategy_name}",
            kind="evaluation",
            attributes={
                "evaluation.strategy": strategy_name,
                "requested.provider": requested_provider,
                "requested.model": requested_model,
            },
            workspace_root=workspace_root,
        ) as span:
            generation = start_langfuse_generation(
                trace_id=span["traceId"],
                name=f"benchmark-{strategy_name}",
                input_payload={
                    "query": query,
                    "strategy": strategy_name,
                    "contextBlocks": context_blocks,
                },
                model=requested_model,
                model_parameters={"temperature": temperature, "max_tokens": max_tokens},
                metadata={
                    "serviceName": "evaluation",
                    "scenario": "m8.memory_strategy_compare",
                    "strategy": strategy_name,
                    "requestedProvider": requested_provider,
                },
            )
            result = invoke_model(
                requested_model=requested_model,
                requested_provider=requested_provider,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                workspace_root=workspace_root,
                allow_fallback=True,
            )
            finish_langfuse_generation(
                generation,
                output=result.get("outputText"),
                metadata={
                    "strategy": strategy_name,
                    "mode": result.get("mode"),
                    "provider": result.get("provider"),
                    "traceId": span["traceId"],
                },
                usage_details=dict(result.get("usage") or {}),
                cost_details={"total_cost": float(result.get("costUsed", 0.0) or 0.0)},
                model=str(result.get("model") or requested_model),
                level="WARNING" if result.get("mode") != "live" else "DEFAULT",
                status_message=str(result.get("error")) if result.get("error") is not None else None,
            )
            return result
    except Exception:
        return _strategy_fallback_answer(query, context_blocks)

def _score_strategy(
    *,
    strategy_name: str,
    expected_keywords: list[str],
    context_blocks: list[str],
    answer_result: dict[str, Any],
) -> dict[str, Any]:
    context_text = "\n\n".join(context_blocks)
    answer_text = str(answer_result.get("outputText") or "")
    answer_matches = _keyword_matches(answer_text, expected_keywords)
    context_matches = _keyword_matches(context_text, expected_keywords)
    answer_coverage = _coverage_ratio(answer_text, expected_keywords)
    context_coverage = _coverage_ratio(context_text, expected_keywords)
    combined_score = round(context_coverage * 0.7 + answer_coverage * 0.3, 4)
    return {
        "name": strategy_name,
        "contextBlocks": len(context_blocks),
        "contextCoverage": context_coverage,
        "answerCoverage": answer_coverage,
        "combinedScore": combined_score,
        "matchedKeywords": sorted({*context_matches, *answer_matches}),
        "mode": answer_result.get("mode"),
        "provider": answer_result.get("provider"),
        "model": answer_result.get("model"),
        "costUsed": float(answer_result.get("costUsed", 0.0) or 0.0),
        "usage": dict(answer_result.get("usage") or {}),
        "answerPreview": normalize_excerpt(answer_text, 240),
    }


def _provider_matrix_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def _average(field: str, bucket: list[dict[str, Any]]) -> float | None:
        values = [
            float(item[field])
            for item in bucket
            if isinstance(item.get(field), (int, float)) and item.get(field) is not None
        ]
        if not values:
            return None
        return round(sum(values) / len(values), 4)

    provider_buckets: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        key = (str(row.get("provider") or "unknown"), str(row.get("model") or "unknown"))
        provider_buckets.setdefault(key, []).append(row)

    provider_summary: list[dict[str, Any]] = []
    for (provider, model), bucket in provider_buckets.items():
        provider_summary.append(
            {
                "provider": provider,
                "model": model,
                "caseCount": len(bucket),
                "passRate": round(sum(1 for item in bucket if bool(item.get("pass"))) / len(bucket), 4) if bucket else 0.0,
                "avgFirstTokenSeconds": _average("firstTokenSeconds", bucket),
                "avgFirstUsefulOutputSeconds": _average("firstUsefulOutputSeconds", bucket),
                "avgPlanQualityScore0_100": _average("planQualityScore0_100", bucket),
                "avgReworkRate": _average("reworkRate", bucket),
                "avgTotalTokens": _average("totalTokens", bucket),
                "avgOutputTokens": _average("outputTokens", bucket),
                "avgCacheHitInputTokens": _average("cacheHitInputTokens", bucket),
                "avgNonCacheInputTokens": _average("nonCacheInputTokens", bucket),
                "avgCacheWriteInputTokens": _average("cacheWriteInputTokens", bucket),
                "avgReasoningTokens": _average("reasoningTokens", bucket),
                "avgMaxContextLengthTokens": _average("maxContextLengthTokens", bucket),
                "avgRestartCount": _average("restartCount", bucket),
                "avgCompressionCount": _average("compressionCount", bucket),
                "avgCumulativeWindowSpanTokens": _average("cumulativeWindowSpanTokens", bucket),
                "avgCarryForwardLossCount": _average("carryForwardLossCount", bucket),
                "avgEffectiveContextWindow": _average("effectiveContextWindow", bucket),
                "avgWindowExecutionCount": _average("windowExecutionCount", bucket),
                "avgWorkTreeContinuity0_1": _average("workTreeContinuity0_1", bucket),
                "avgMinimalWorksetRatio0_1": _average("minimalWorksetRatio0_1", bucket),
                "avgPlanningStubRate0_1": _average("planningStubRate0_1", bucket),
                "avgRetrievalDriftRate0_1": _average("retrievalDriftRate0_1", bucket),
            }
        )
    provider_summary.sort(
        key=lambda item: (
            -(item["passRate"]),
            -(item["avgPlanQualityScore0_100"] or -1.0),
            item["avgReworkRate"] if item["avgReworkRate"] is not None else 999.0,
            item["avgFirstUsefulOutputSeconds"] if item["avgFirstUsefulOutputSeconds"] is not None else 999.0,
        )
    )
    return {
        "providerMatrix": rows,
        "providerSummary": provider_summary,
    }


def _real_task_window_parity_summary(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not rows:
        return None

    def _role_of(row: dict[str, Any]) -> str:
        explicit_role = str(row.get("parityRole") or "").strip().lower()
        if explicit_role in {"short", "long"}:
            return explicit_role
        matrix_key = str(row.get("matrixKey") or "").lower()
        if "short" in matrix_key:
            return "short"
        if "long" in matrix_key:
            return "long"
        return ""

    def _avg(bucket: list[dict[str, Any]], key: str) -> float:
        if not bucket:
            return 0.0
        values = [float(item.get(key) or 0.0) for item in bucket]
        return round(sum(values) / len(values), 4)

    short_rows = [row for row in rows if _role_of(row) == "short"]
    long_rows = [row for row in rows if _role_of(row) == "long"]
    if not short_rows or not long_rows:
        return None

    short_goal_completion = 1 if all(int(item.get("goalCompletion0_1") or 0) == 1 for item in short_rows) else 0
    long_goal_completion = 1 if all(int(item.get("goalCompletion0_1") or 0) == 1 for item in long_rows) else 0
    short_delivery = 1 if all(int(item.get("deliveryCompletion0_1") or 0) == 1 for item in short_rows) else 0
    long_delivery = 1 if all(int(item.get("deliveryCompletion0_1") or 0) == 1 for item in long_rows) else 0
    short_quality = _avg(short_rows, "planQualityScore0_100")
    long_quality = _avg(long_rows, "planQualityScore0_100")
    short_minimal_workset = _avg(short_rows, "minimalWorksetRatio0_1")
    long_minimal_workset = _avg(long_rows, "minimalWorksetRatio0_1")
    quality_delta = round(abs(long_quality - short_quality), 4)
    quality_threshold = min(
        [float(item.get("qualityDeltaThreshold0_100") or 8.0) for item in [*short_rows, *long_rows]]
    )
    work_tree_continuity = 1 if all(int(item.get("workTreeContinuity0_1") or 0) == 1 for item in [*short_rows, *long_rows]) else 0
    minimal_workset_threshold = min(
        [float(item.get("minimalWorksetThreshold0_1") or 0.0) for item in [*short_rows, *long_rows]]
    )
    minimal_workset_ratio = round(min(short_minimal_workset, long_minimal_workset), 4)

    goal_completion_parity = 1 if short_goal_completion == 1 and long_goal_completion == 1 else 0
    delivery_equivalence = 1 if short_delivery == 1 and long_delivery == 1 else 0

    return {
        "goalCompletionParity0_1": goal_completion_parity,
        "deliveryEquivalence0_1": delivery_equivalence,
        "workTreeContinuity0_1": work_tree_continuity,
        "minimalWorksetRatio0_1": minimal_workset_ratio,
        "minimalWorksetThreshold0_1": minimal_workset_threshold,
        "qualityDeltaToLongWindow0_100": quality_delta,
        "qualityDeltaThreshold0_100": quality_threshold,
        "parityPassed0_1": 1
        if goal_completion_parity == 1
        and delivery_equivalence == 1
        and work_tree_continuity == 1
        and minimal_workset_ratio >= minimal_workset_threshold
        and quality_delta <= quality_threshold
        else 0,
        "shortWindow": {
            "caseCount": len(short_rows),
            "goalCompletion0_1": short_goal_completion,
            "deliveryCompletion0_1": short_delivery,
            "avgPlanQualityScore0_100": short_quality,
            "avgMinimalWorksetRatio0_1": short_minimal_workset,
            "workTreeContinuity0_1": 1 if all(int(item.get("workTreeContinuity0_1") or 0) == 1 for item in short_rows) else 0,
        },
        "longWindow": {
            "caseCount": len(long_rows),
            "goalCompletion0_1": long_goal_completion,
            "deliveryCompletion0_1": long_delivery,
            "avgPlanQualityScore0_100": long_quality,
            "avgMinimalWorksetRatio0_1": long_minimal_workset,
            "workTreeContinuity0_1": 1 if all(int(item.get("workTreeContinuity0_1") or 0) == 1 for item in long_rows) else 0,
        },
    }


def _real_task_window_parity_group_summaries(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return []

    grouped_rows: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in rows:
        pair_key = str(row.get("parityPairKey") or "").strip() or "default"
        provider = str(row.get("provider") or "unknown")
        model = str(row.get("model") or "unknown")
        grouped_rows.setdefault((pair_key, provider, model), []).append(row)

    summaries: list[dict[str, Any]] = []
    for (pair_key, provider, model), bucket in grouped_rows.items():
        summary = _real_task_window_parity_summary(bucket)
        if summary is None:
            continue
        summary.update(
            {
                "parityPairKey": pair_key,
                "provider": provider,
                "model": model,
                "groupKey": f"{pair_key}:{provider}:{model}",
            }
        )
        summaries.append(summary)

    summaries.sort(key=lambda item: (str(item.get("parityPairKey") or ""), str(item.get("provider") or ""), str(item.get("model") or "")))
    return summaries

def _aggregate_case_metrics(case_results: list[dict[str, Any]]) -> dict[str, Any]:
    strategy_totals: dict[str, dict[str, float]] = {}
    baseline_comparisons: list[dict[str, Any]] = []
    live_scenarios: list[dict[str, Any]] = []
    provider_matrix_rows: list[dict[str, Any]] = []

    for case in case_results:
        detail = case.get("detail")
        if not isinstance(detail, dict):
            continue
        strategies = detail.get("strategies")
        if isinstance(strategies, list) and strategies:
            baseline_comparisons.append(
                {
                    "caseId": case.get("id"),
                    "caseTitle": case.get("title"),
                    "topStrategy": detail.get("topStrategy"),
                    "strategies": strategies,
                }
            )
            for strategy in strategies:
                name = str(strategy.get("name") or "unknown")
                bucket = strategy_totals.setdefault(
                    name,
                    {
                        "cases": 0.0,
                        "combined": 0.0,
                        "context": 0.0,
                        "answer": 0.0,
                    },
                )
                bucket["cases"] += 1.0
                bucket["combined"] += float(strategy.get("combinedScore") or 0.0)
                bucket["context"] += float(strategy.get("contextCoverage") or 0.0)
                bucket["answer"] += float(strategy.get("answerCoverage") or 0.0)

        live_scenario = detail.get("liveScenario")
        if isinstance(live_scenario, dict):
            live_scenarios.append(live_scenario)

        provider_matrix_entry = detail.get("providerMatrixEntry")
        if isinstance(provider_matrix_entry, dict):
            provider_matrix_rows.append(provider_matrix_entry)

    payload: dict[str, Any] = {}
    if baseline_comparisons:
        leaderboard = [
            {
                "name": name,
                "cases": int(bucket["cases"]),
                "avgCombinedScore": round(bucket["combined"] / bucket["cases"], 4),
                "avgContextCoverage": round(bucket["context"] / bucket["cases"], 4),
                "avgAnswerCoverage": round(bucket["answer"] / bucket["cases"], 4),
            }
            for name, bucket in strategy_totals.items()
            if bucket["cases"] > 0
        ]
        leaderboard.sort(key=lambda item: (item["avgCombinedScore"], item["avgContextCoverage"], item["avgAnswerCoverage"]), reverse=True)
        payload["baselineComparisons"] = baseline_comparisons
        payload["strategyLeaderboard"] = leaderboard
    if live_scenarios:
        payload["liveScenarios"] = live_scenarios
    if provider_matrix_rows:
        payload.update(_provider_matrix_summary(provider_matrix_rows))
        parity_summaries = _real_task_window_parity_group_summaries(provider_matrix_rows)
        if parity_summaries:
            payload["realTaskWindowParityGroups"] = parity_summaries
            if len(parity_summaries) == 1:
                payload["realTaskWindowParity"] = parity_summaries[0]
            else:
                payload["realTaskWindowParity"] = {
                    "groupCount": len(parity_summaries),
                    "passedGroupCount": len([item for item in parity_summaries if int(item.get("parityPassed0_1") or 0) == 1]),
                    "parityPassed0_1": 1 if all(int(item.get("parityPassed0_1") or 0) == 1 for item in parity_summaries) else 0,
                    "groups": parity_summaries,
                }
    return payload



__all__ = [name for name in globals() if not name.startswith('__')]


