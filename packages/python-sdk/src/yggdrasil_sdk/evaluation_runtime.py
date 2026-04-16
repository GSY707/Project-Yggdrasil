from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
from time import perf_counter
import subprocess
import tempfile
from typing import Any, Iterator

from .contracts import ExternalRef
from .domain import EvaluationSuiteRecord
from .observability_exporters import finish_langfuse_generation
from .observability_exporters import flush_observability_exporters
from .observability_exporters import start_langfuse_generation
from .observability import observe_span, record_log, record_metric
from .persistence import EvaluationRepository, RuntimeRepository, ensure_workspace_bootstrap, get_persistence_runtime, initialize_schema, reset_persistence_runtime
from .persistence.constants import DEFAULT_BRANCH_ID, DEFAULT_PROJECT_ID
from .persistence.repositories import NodeRepository, TaskRepository, WorkspaceBootstrapRepository
from .support import new_id, normalize_excerpt, read_json, resolve_workspace_root, resolve_state_dir, utc_now, write_json


def _evaluation_root(workspace_root: Path | None = None) -> Path:
    return resolve_workspace_root(workspace_root) / "evaluation"


def _suites_dir(workspace_root: Path | None = None) -> Path:
    return _evaluation_root(workspace_root) / "suites"


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
    requested_model = str(case.get("requestedModel") or "LongCat-Flash-Lite")
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


def _aggregate_case_metrics(case_results: list[dict[str, Any]]) -> dict[str, Any]:
    strategy_totals: dict[str, dict[str, float]] = {}
    baseline_comparisons: list[dict[str, Any]] = []
    live_scenarios: list[dict[str, Any]] = []

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
    return payload


def list_evaluation_suite_definitions(workspace_root: Path | None = None) -> list[dict[str, Any]]:
    suites_dir = _suites_dir(workspace_root)
    if not suites_dir.exists():
        return []
    documents: list[dict[str, Any]] = []
    for suite_path in sorted(suites_dir.glob("*.json")):
        payload = read_json(suite_path, {})
        if isinstance(payload, dict):
            documents.append(payload)
    return documents


def get_evaluation_suite_definition(suite_id: str, workspace_root: Path | None = None) -> dict[str, Any]:
    for definition in list_evaluation_suite_definitions(workspace_root):
        if str(definition.get("id")) == suite_id:
            return definition
    raise KeyError(suite_id)


def ensure_evaluation_suites(workspace_root: Path | None = None) -> list[EvaluationSuiteRecord]:
    ensure_workspace_bootstrap()
    runtime = get_persistence_runtime()
    definitions = list_evaluation_suite_definitions(workspace_root)
    if not definitions:
        return []
    with runtime.session_scope() as session:
        repository = EvaluationRepository(session)
        suites: list[EvaluationSuiteRecord] = []
        for definition in definitions:
            suites.append(
                repository.upsert_suite(
                    EvaluationSuiteRecord(
                        id=str(definition.get("id")),
                        name=str(definition.get("name") or definition.get("id")),
                        domain=str(definition.get("domain") or "generic"),
                        metricRefs=[str(metric) for metric in definition.get("metricRefs") or []],
                        createdAt=definition.get("createdAt") or utc_now(),
                    )
                )
            )
        return suites


@contextmanager
def isolated_runtime_environment() -> Iterator[None]:
    managed_keys = [
        "YGGDRASIL_DATABASE_URL",
        "YGGDRASIL_AUTO_CREATE_SCHEMA",
        "YGGDRASIL_REDIS_URL",
        "YGGDRASIL_STATE_ROOT",
        "YGGDRASIL_STATE_DIR",
        "YGGDRASIL_GIT_REPO_PATH",
    ]
    previous = {key: os.environ.get(key) for key in managed_keys}
    with tempfile.TemporaryDirectory(prefix="yggdrasil-eval-") as temp_dir:
        temp_root = Path(temp_dir)
        os.environ["YGGDRASIL_DATABASE_URL"] = f"sqlite+pysqlite:///{(temp_root / 'evaluation.db').as_posix()}"
        os.environ["YGGDRASIL_AUTO_CREATE_SCHEMA"] = "1"
        os.environ["YGGDRASIL_REDIS_URL"] = "redis://127.0.0.1:6390/15"
        os.environ["YGGDRASIL_STATE_ROOT"] = str((temp_root / ".yggdrasil").resolve())
        os.environ.pop("YGGDRASIL_STATE_DIR", None)
        reset_persistence_runtime()
        initialize_schema()
        ensure_workspace_bootstrap()
        try:
            yield
        finally:
            reset_persistence_runtime()
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
            reset_persistence_runtime()


def _run_git(repo_path: Path, *args: str) -> str:
    completed = subprocess.run(["git", "-C", str(repo_path), *args], capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "unknown git error"
        raise RuntimeError(detail)
    return completed.stdout.strip()


def _seed_runtime_task(task_id: str) -> dict[str, Any]:
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        task = task_repository.create_task(
            {
                "id": task_id,
                "title": "Evaluation Runtime Task",
                "goal": "Validate the main-agent pause and resume closed loop.",
                "status": "draft",
                "currentObjective": "complete the evaluation execution and enter safe-stop",
                "currentFocus": "evaluation-runtime",
                "resumeMessage": "resume the evaluation flow",
                "budgetState": {
                    "tokenBudgetTotal": 1200,
                    "costBudgetTotal": 5.0,
                },
            }
        )
    return task.model_dump(by_alias=True, mode="json")


def _seed_parent_task() -> dict[str, Any]:
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        node_repository = NodeRepository(session)
        task = task_repository.create_task(
            {
                "title": "Evaluation Parent Task",
                "goal": "Validate the sub-agent PR lifecycle.",
                "currentFocus": "evaluation-subagent",
                "currentObjective": "launch a child branch and merge it back",
                "budget": {
                    "tokenBudgetTotal": 2400,
                    "costBudgetTotal": 5.0,
                    "selfThinkTokenLimit": 400,
                    "childBudgetMode": "capped",
                    "maxSubAgents": 2,
                },
            }
        )
        node_repository.create_node(
            {
                "projectId": task.project_id,
                "spaceId": task.space_id,
                "branchId": task.branch_id,
                "parentId": task.execution_root_node_id,
                "rootBranch": "execution",
                "nodeType": "task",
                "title": "Evaluation Parent Context",
                "content": "This readonly context must be passed to the child branch.",
                "createdBy": {"type": "agent", "id": "evaluation"},
                "updatedBy": {"type": "agent", "id": "evaluation"},
            }
        )
    return task.model_dump(by_alias=True, mode="json")


def _run_memory_import_case(case: dict[str, Any] | None = None) -> dict[str, Any]:
    from fastapi.testclient import TestClient
    from yggdrasil_core_api.app import app

    client = TestClient(app)
    source_text = _read_text_fixture("memory_import_sample.txt")
    created = client.post(
        "/memory/import-jobs",
        json={
            "sourceKind": "file",
            "sourceText": source_text,
            "rawRef": {"type": "file", "locator": "evaluation/fixtures/memory_import_sample.txt"},
            "processImmediately": True,
            "requestedBy": {"type": "user", "id": "evaluation"},
            "importPolicy": {
                "segmentTargetChars": 180,
                "allowDiscardLowValue": False,
                "linkStrategy": ["keyword"],
                "mergePolicy": "balanced",
            },
        },
    )
    if created.status_code != 201:
        raise RuntimeError(f"memory import failed: {created.text}")
    body = created.json()
    retrieval = client.post(
        "/memory/retrievals",
        json={
            "queryText": "模块生命周期 事件总线 导入链路 检索",
            "branchId": DEFAULT_BRANCH_ID,
            "maxLeafNodes": 4,
            "maxRelatedNodes": 4,
            "includeNaturalLanguageSummary": True,
        },
    )
    if retrieval.status_code != 201:
        raise RuntimeError(f"memory retrieval failed: {retrieval.text}")
    retrieval_body = retrieval.json()
    return {
        "materializedNodeCount": len(body.get("materializedNodes") or []),
        "materializedEdgeCount": len(body.get("materializedEdges") or []),
        "retrievalMatchCount": len(retrieval_body["retrievalBundle"].get("matchedNodeRefs") or []),
        "summary": retrieval_body["retrievalBundle"].get("naturalLanguageSummary"),
    }


def _run_memory_strategy_compare_case(case: dict[str, Any] | None = None) -> dict[str, Any]:
    from fastapi.testclient import TestClient
    from yggdrasil_core_api.app import app

    case_payload = dict(case or {})
    client = TestClient(app)
    source_text = _read_text_fixture(str(case_payload.get("fixture") or "m8_memory_benchmark.txt"))
    query = str(case_payload.get("query") or "为什么这个系统需要共享术语、事件总线和模块宿主？")
    expected_keywords = [str(keyword) for keyword in case_payload.get("expectedKeywords") or []]
    top_k = max(1, int(case_payload.get("topK") or 4))

    created = client.post(
        "/memory/import-jobs",
        json={
            "sourceKind": "file",
            "sourceText": source_text,
            "rawRef": {"type": "file", "locator": str(case_payload.get("fixture") or "evaluation/fixtures/m8_memory_benchmark.txt")},
            "processImmediately": True,
            "requestedBy": {"type": "user", "id": "evaluation"},
            "importPolicy": {
                "segmentTargetChars": int(case_payload.get("segmentTargetChars") or 220),
                "allowDiscardLowValue": False,
                "linkStrategy": ["keyword"],
                "mergePolicy": "balanced",
            },
        },
    )
    if created.status_code != 201:
        raise RuntimeError(f"memory benchmark import failed: {created.text}")
    body = created.json()
    retrieval = client.post(
        "/memory/retrievals",
        json={
            "queryText": str(case_payload.get("retrievalQuery") or query),
            "branchId": DEFAULT_BRANCH_ID,
            "maxLeafNodes": top_k,
            "maxRelatedNodes": top_k,
            "includeNaturalLanguageSummary": True,
            "includeChildNames": True,
            "includeRelatedNames": True,
        },
    )
    if retrieval.status_code != 201:
        raise RuntimeError(f"memory benchmark retrieval failed: {retrieval.text}")
    retrieval_body = retrieval.json()
    bundle = dict(retrieval_body.get("retrievalBundle") or {})
    fragments = [dict(fragment) for fragment in body.get("fragments") or []]

    strategies = [
        ("no-memory", []),
        ("vector-flat", _select_flat_fragments(fragments, query, top_k)),
        ("memory-tree", _build_memory_tree_context(bundle, top_k)),
    ]
    scored_strategies: list[dict[str, Any]] = []
    for strategy_name, context_blocks in strategies:
        answer = _generate_strategy_answer(case_payload, query, strategy_name, context_blocks)
        scored_strategies.append(
            _score_strategy(
                strategy_name=strategy_name,
                expected_keywords=expected_keywords,
                context_blocks=context_blocks,
                answer_result=answer,
            )
        )

    scored_strategies.sort(
        key=lambda item: (float(item.get("combinedScore") or 0.0), float(item.get("contextCoverage") or 0.0), float(item.get("answerCoverage") or 0.0)),
        reverse=True,
    )
    return {
        "question": query,
        "expectedKeywords": expected_keywords,
        "materializedNodeCount": len(body.get("materializedNodes") or []),
        "materializedEdgeCount": len(body.get("materializedEdges") or []),
        "retrievalMatchCount": len(bundle.get("matchedNodeRefs") or []),
        "retrievalSummary": bundle.get("naturalLanguageSummary"),
        "strategies": scored_strategies,
        "topStrategy": scored_strategies[0]["name"] if scored_strategies else None,
    }


def _run_main_agent_case(case: dict[str, Any] | None = None) -> dict[str, Any]:
    from fastapi.testclient import TestClient
    from yggdrasil_agent_runtime.app import app as runtime_app
    from yggdrasil_worker.registry import run_worker_once

    task = _seed_runtime_task("eval_task_runtime")
    client = TestClient(runtime_app)
    started = client.post(
        f"/runtime/tasks/{task['id']}/start",
        json={
            "currentFocus": "evaluation main agent runtime",
            "currentContext": [
                {
                    "id": "ctx_keep",
                    "title": "runtime protocol",
                    "content": "main agent needs route decision, safe-stop, pause snapshot, and resume handling",
                    "importance": 0.9,
                }
            ],
            "protectedItems": [{"kind": "node", "id": "ctx_keep"}],
        },
    )
    if started.status_code != 202:
        raise RuntimeError(f"runtime start failed: {started.text}")
    pause_request = client.post(
        f"/runtime/tasks/{task['id']}/pause-request",
        json={
            "reason": "evaluation-manual-pause",
            "resumeMessage": "resume the evaluation run",
        },
    )
    if pause_request.status_code != 202:
        raise RuntimeError(f"runtime pause request failed: {pause_request.text}")
    first = run_worker_once("agent-runtime")
    if first.get("result", {}).get("status") != "paused":
        raise RuntimeError(f"runtime pause step failed: {json.dumps(first, ensure_ascii=False)}")
    resume_token = first["result"]["snapshot"]["resumeToken"]
    resumed = client.post(
        f"/runtime/tasks/{task['id']}/resume",
        json={
            "resumeToken": resume_token,
            "nextObjective": "finish the evaluation flow",
        },
    )
    if resumed.status_code != 202:
        raise RuntimeError(f"runtime resume failed: {resumed.text}")
    second = run_worker_once("agent-runtime")
    if second.get("result", {}).get("status") != "completed":
        raise RuntimeError(f"runtime completion failed: {json.dumps(second, ensure_ascii=False)}")
    return {
        "pauseStatus": first["result"]["status"],
        "resumeStatus": second["result"]["status"],
        "snapshotId": first["result"]["snapshot"]["id"],
    }


def _run_live_llm_task_case(case: dict[str, Any] | None = None) -> dict[str, Any]:
    from fastapi.testclient import TestClient
    from yggdrasil_agent_runtime.app import app as runtime_app
    from yggdrasil_worker.registry import run_worker_once
    from .llm_runtime import load_runtime_candidate_models

    case_payload = dict(case or {})
    task_id = str(case_payload.get("taskId") or new_id("task", "m8-live-evaluation", stable=False))
    requested_provider = str(case_payload.get("requestedProvider") or "longcat")
    requested_model = str(case_payload.get("requestedModel") or "LongCat-Flash-Lite")
    candidate_models = [
        dict(candidate)
        for candidate in load_runtime_candidate_models() or []
        if str(candidate.get("provider") or "") == requested_provider and str(candidate.get("model") or "") == requested_model
    ]
    task = _seed_runtime_task(task_id)
    client = TestClient(runtime_app)
    require_live = bool(case_payload.get("requireLive", False))
    if require_live and not candidate_models:
        raise RuntimeError(f"requested live candidate is unavailable: {requested_provider}/{requested_model}")
    start_payload = {
        "currentFocus": str(case_payload.get("currentFocus") or "M8 live LLM evaluation"),
        "currentObjective": str(case_payload.get("currentObjective") or "Use the mounted context to explain how memory-tree retrieval improves answer grounding."),
        "currentContext": [
            {
                "id": "ctx_live_eval",
                "title": str(case_payload.get("contextTitle") or "M8 live benchmark context"),
                "content": str(
                    case_payload.get("context")
                    or "The system now includes real provider routing, benchmark baselines, OpenTelemetry export, Langfuse generation tracing, backup and restore tooling, and compose smoke checks."
                ),
                "importance": 0.98,
            }
        ],
        "protectedItems": [{"kind": "node", "id": "ctx_live_eval"}],
        "allowModelFallback": bool(case_payload.get("allowFallback", True)),
        "temperature": float(case_payload.get("temperature") or 0.15),
        "maxTokens": int(case_payload.get("maxTokens") or 320),
    }
    if candidate_models:
        start_payload["candidateModels"] = candidate_models
    started = client.post(f"/runtime/tasks/{task['id']}/start", json=start_payload)
    if started.status_code != 202:
        raise RuntimeError(f"live evaluation start failed: {started.text}")

    processed = run_worker_once("agent-runtime")
    result_payload = dict(processed.get("result") or {})
    if result_payload.get("status") != "completed":
        raise RuntimeError(f"live evaluation worker failed: {json.dumps(processed, ensure_ascii=False)}")

    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        repository = TaskRepository(session)
        runtime_repository = RuntimeRepository(session)
        persisted_task = repository.get_task(task["id"])
        invocations = runtime_repository.list_model_invocations(task_id=task["id"], limit=5)

    if not invocations:
        raise RuntimeError("live evaluation did not persist any model invocation")
    invocation = invocations[0]
    expected_provider = requested_provider
    if require_live and invocation.status != "completed":
        raise RuntimeError(f"live provider invocation did not complete: {invocation.status}")
    if require_live and invocation.resolved_provider not in {expected_provider, str(case_payload.get('providerAlias') or '')}:
        raise RuntimeError(
            f"live provider mismatch: expected {expected_provider}, got {invocation.resolved_provider or 'unknown'}"
        )

    request_payload = read_json(Path(invocation.request_ref.locator), None) if invocation.request_ref else None
    response_payload = read_json(Path(invocation.response_ref.locator), None) if invocation.response_ref else None
    live_summary = {
        "taskId": task["id"],
        "taskStatus": persisted_task.status if persisted_task is not None else result_payload.get("status"),
        "invocationId": invocation.id,
        "invocationStatus": invocation.status,
        "provider": invocation.resolved_provider,
        "model": invocation.resolved_model,
        "traceId": invocation.trace_id,
        "latencyMs": invocation.latency_ms,
        "totalTokens": int((invocation.input_tokens_used or 0) + (invocation.output_tokens_used or 0)),
        "costUsed": float(invocation.cost_used or 0.0),
    }
    return {
        **live_summary,
        "liveScenario": live_summary,
        "assistantPreview": normalize_excerpt(str(result_payload.get("assistantText") or ""), 240),
        "requestPayload": request_payload,
        "responsePayload": response_payload,
    }


def _run_subagent_pr_case(case: dict[str, Any] | None = None) -> dict[str, Any]:
    from fastapi.testclient import TestClient
    from yggdrasil_core_api.app import app
    from yggdrasil_sdk.collaboration_runtime import launch_subagent_task
    from yggdrasil_worker.registry import run_worker_once

    with tempfile.TemporaryDirectory(prefix="yggdrasil-eval-git-") as temp_dir:
        repo_path = Path(temp_dir) / "collaboration-repo"
        repo_path.mkdir(parents=True, exist_ok=True)
        _run_git(repo_path, "init", "-b", "main")
        _run_git(repo_path, "config", "user.name", "Evaluation User")
        _run_git(repo_path, "config", "user.email", "evaluation@example.com")
        (repo_path / "README.md").write_text("# Evaluation Repo\n", encoding="utf-8")
        _run_git(repo_path, "add", "README.md")
        _run_git(repo_path, "commit", "-m", "init")
        os.environ["YGGDRASIL_GIT_REPO_PATH"] = str(repo_path)

        parent_task = _seed_parent_task()
        launched = launch_subagent_task(
            str(parent_task["id"]),
            {
                "title": "Evaluation child path",
                "goal": "Produce a child proposal and merge it back.",
                "createdBy": {"type": "agent", "id": "evaluation"},
            },
        )
        processed = run_worker_once()
        if processed.get("result", {}).get("status") != "completed":
            raise RuntimeError(f"subagent execution failed: {json.dumps(processed, ensure_ascii=False)}")

        client = TestClient(app)
        pr_id = str(processed["result"]["pullRequest"]["id"])
        reviewed = client.post(
            f"/collaboration/pull-requests/{pr_id}/review",
            json={
                "decision": "approved",
                "mergeImmediately": True,
                "reviewedBy": {"type": "agent", "id": "evaluation"},
            },
        )
        if reviewed.status_code != 200:
            raise RuntimeError(f"subagent review failed: {reviewed.text}")
        review_body = reviewed.json()
        return {
            "branchName": launched["branch"]["name"],
            "pullRequestId": pr_id,
            "pullRequestStatus": review_body["pullRequest"]["status"],
            "mergeCommitRef": review_body["git"].get("mergeCommitRef"),
        }


SCENARIO_HANDLERS = {
    "m4.memory_import_retrieval": _run_memory_import_case,
    "m5.main_agent_pause_resume": _run_main_agent_case,
    "m6.subagent_pr_loop": _run_subagent_pr_case,
    "m8.live_llm_task_execution": _run_live_llm_task_case,
    "m8.memory_strategy_compare": _run_memory_strategy_compare_case,
}


def run_evaluation_suite(suite_id: str, workspace_root: Path | None = None) -> dict[str, Any]:
    definition = get_evaluation_suite_definition(suite_id, workspace_root)
    ensure_evaluation_suites(workspace_root)
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        repository = EvaluationRepository(session)
        run = repository.create_run(
            {
                "suiteId": suite_id,
                "projectId": DEFAULT_PROJECT_ID,
                "subjectKind": definition.get("subjectKind") or "workflow",
                "subjectRef": definition.get("subjectRef") or suite_id,
                "status": "running",
                "startedAt": utc_now(),
            }
        )

    case_results: list[dict[str, Any]] = []
    with observe_span("evaluation", f"suite:{suite_id}", kind="evaluation", attributes={"suiteId": suite_id}) as span:
        record_log("evaluation", "info", f"Starting evaluation suite {suite_id}", attributes={"runId": run.id})
        for case in definition.get("cases") or []:
            case_id = str(case.get("id") or new_id("evalcase", suite_id))
            scenario = str(case.get("scenario") or "")
            handler = SCENARIO_HANDLERS.get(scenario)
            if handler is None:
                case_results.append(
                    {
                        "id": case_id,
                        "title": str(case.get("title") or case_id),
                        "scenario": scenario,
                        "status": "failed",
                        "durationMs": 0.0,
                        "detail": {"error": f"Unsupported scenario: {scenario}"},
                    }
                )
                continue

            case_started = perf_counter()
            try:
                with isolated_runtime_environment():
                    detail = handler(case)
                case_status = "passed"
            except Exception as exc:
                detail = {"error": str(exc), "errorType": exc.__class__.__name__}
                case_status = "failed"
                record_log(
                    "evaluation",
                    "error",
                    f"Evaluation case failed: {case_id}",
                    attributes={"runId": run.id, "suiteId": suite_id, "caseId": case_id, "error": str(exc)},
                )
            duration_ms = round((perf_counter() - case_started) * 1000.0, 2)
            record_metric(
                "evaluation",
                "case.duration",
                duration_ms,
                kind="histogram",
                unit="ms",
                attributes={"suiteId": suite_id, "caseId": case_id, "status": case_status},
            )
            case_results.append(
                {
                    "id": case_id,
                    "title": str(case.get("title") or case_id),
                    "scenario": scenario,
                    "status": case_status,
                    "durationMs": duration_ms,
                    "detail": detail,
                    "tags": [str(tag) for tag in case.get("tags") or []],
                    "difficulty": str(case.get("difficulty") or "medium"),
                }
            )

        passed_count = len([row for row in case_results if row["status"] == "passed"])
        failed_count = len(case_results) - passed_count
        total_duration_ms = round(sum(float(row["durationMs"]) for row in case_results), 2)
        metrics_payload = {
            "suiteId": suite_id,
            "suiteName": definition.get("name") or suite_id,
            "runId": run.id,
            "status": "completed" if failed_count == 0 else "failed",
            "caseCount": len(case_results),
            "passedCount": passed_count,
            "failedCount": failed_count,
            "failedCaseCount": failed_count,
            "passRate": round(passed_count / len(case_results), 4) if case_results else 0.0,
            "totalDurationMs": total_duration_ms,
            "cases": case_results,
            "generatedAt": utc_now().isoformat(),
            "traceId": span["traceId"],
        }
        metrics_payload.update(_aggregate_case_metrics(case_results))

    metrics_dir = resolve_state_dir(workspace_root) / "evaluations"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = metrics_dir / f"{run.id}.json"
    write_json(metrics_path, metrics_payload)
    with runtime.session_scope() as session:
        repository = EvaluationRepository(session)
        completed_run = repository.update_run(
            run.id,
            {
                "status": metrics_payload["status"],
                "metricsRef": ExternalRef(type="file", locator=str(metrics_path.resolve())),
                "endedAt": utc_now(),
            },
        )

    record_log(
        "evaluation",
        "info",
        f"Completed evaluation suite {suite_id}",
        attributes={"runId": completed_run.id, "status": completed_run.status, "failedCount": metrics_payload["failedCount"]},
    )
    flush_observability_exporters()
    return {
        "suite": definition,
        "run": completed_run.model_dump(by_alias=True, mode="json"),
        "metrics": metrics_payload,
    }