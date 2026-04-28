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
from .persistence import EvaluationRepository, PromptAssetRepository, RuntimeRepository, ensure_workspace_bootstrap, get_persistence_runtime, initialize_schema, reset_persistence_runtime
from .persistence.constants import DEFAULT_BRANCH_ID, DEFAULT_PROJECT_ID
from .persistence.repositories import CollaborationRepository, NodeRepository, TaskRepository, TrainingRepository, WorkspaceBootstrapRepository
from .support import ensure_state_subdir, new_id, normalize_excerpt, read_json, relative_workspace_path, resolve_workspace_root, resolve_state_dir, utc_now, write_json


def _evaluation_root(workspace_root: Path | None = None) -> Path:
    return resolve_workspace_root(workspace_root) / "evaluation"


def _suites_dir(workspace_root: Path | None = None) -> Path:
    return _evaluation_root(workspace_root) / "suites"


def _resolve_external_ref_path(ref: ExternalRef | dict[str, Any] | None, workspace_root: Path | None = None) -> Path | None:
    if ref is None:
        return None
    locator = str(ref.locator if isinstance(ref, ExternalRef) else ref.get("locator") or "").strip()
    if not locator:
        return None
    candidate = Path(locator)
    if candidate.is_absolute():
        return candidate
    return resolve_workspace_root(workspace_root) / locator


def _read_external_ref_json(ref: ExternalRef | dict[str, Any] | None, workspace_root: Path | None = None) -> Any:
    path = _resolve_external_ref_path(ref, workspace_root)
    if path is None:
        return None
    return read_json(path, None)


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


@contextmanager
def local_evaluation_runtime_environment(workspace_root: Path | None = None) -> Iterator[None]:
    managed_keys = [
        "YGGDRASIL_DATABASE_URL",
        "YGGDRASIL_AUTO_CREATE_SCHEMA",
        "YGGDRASIL_REDIS_URL",
        "YGGDRASIL_STATE_ROOT",
        "YGGDRASIL_STATE_DIR",
    ]
    previous = {key: os.environ.get(key) for key in managed_keys}
    sandbox_root = resolve_workspace_root(workspace_root) / ".yggdrasil" / "evaluation-sandbox"
    sandbox_root.mkdir(parents=True, exist_ok=True)
    os.environ["YGGDRASIL_DATABASE_URL"] = f"sqlite+pysqlite:///{(sandbox_root / 'evaluation.db').as_posix()}"
    os.environ["YGGDRASIL_AUTO_CREATE_SCHEMA"] = "1"
    os.environ["YGGDRASIL_REDIS_URL"] = "redis://127.0.0.1:6390/15"
    os.environ["YGGDRASIL_STATE_ROOT"] = str(sandbox_root.resolve())
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


def _prepare_suite_run(definition: dict[str, Any], suite_id: str, workspace_root: Path | None = None) -> tuple[Any, Any]:
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
    return runtime, run


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


def _seed_tool_case_memory(task_id: str) -> list[dict[str, Any]]:
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        node_repository = NodeRepository(session)
        task = task_repository.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        created: list[dict[str, Any]] = []
        for title, content in [
            (
                "Prompt artifact rollout",
                "Each model invocation now persists prompt profile version, seed template version, compiled messages ref, and promptMetadata-linked prompt compile artifacts.",
            ),
            (
                "Tool execution trace rollout",
                "Live runtime responses now persist toolExecutions, round traces, and request/response payloads so tool use can be audited after the run.",
            ),
            (
                "Safe-stop retention note",
                "For the next run, keep the current objective, the latest model invocation summary, and the pruning narrative while dropping low-value noise.",
            ),
        ]:
            node = node_repository.create_node(
                {
                    "projectId": task.project_id,
                    "spaceId": task.space_id,
                    "branchId": task.branch_id,
                    "parentId": task.execution_root_node_id,
                    "rootBranch": "execution",
                    "nodeType": "task",
                    "title": title,
                    "content": content,
                    "createdBy": {"type": "agent", "id": "evaluation"},
                    "updatedBy": {"type": "agent", "id": "evaluation"},
                }
            )
            created.append(node.model_dump(by_alias=True, mode="json"))
        return created


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


def _branch_context_parent_id(node_repository: NodeRepository, branch_id: str = DEFAULT_BRANCH_ID) -> str:
    _, context_refs, _ = node_repository.root_mount_refs(DEFAULT_PROJECT_ID, branch_id)
    return context_refs[0].id


def _create_context_node(
    node_repository: NodeRepository,
    *,
    branch_id: str,
    space_id: str,
    title: str,
    content: str,
) -> dict[str, Any]:
    node = node_repository.create_node(
        {
            "projectId": DEFAULT_PROJECT_ID,
            "spaceId": space_id,
            "branchId": branch_id,
            "parentId": _branch_context_parent_id(node_repository, branch_id),
            "rootBranch": "context",
            "nodeType": "detail",
            "title": title,
            "content": content,
            "createdBy": {"type": "agent", "id": "evaluation"},
            "updatedBy": {"type": "agent", "id": "evaluation"},
        }
    )
    return node.model_dump(by_alias=True, mode="json")


def _seed_shared_space_mount(subject: str = "profile:identity_profile_default") -> dict[str, Any]:
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        collaboration_repository = CollaborationRepository(session)
        node_repository = NodeRepository(session)
        shared_space = collaboration_repository.create_space(
            {
                "projectId": DEFAULT_PROJECT_ID,
                "spaceType": "shared",
                "ownerSubject": subject,
            }
        )
        shared_branch = collaboration_repository.create_branch(
            {
                "projectId": DEFAULT_PROJECT_ID,
                "spaceId": shared_space.id,
                "name": "shared-m9-evidence",
            }
        )
        collaboration_repository.create_space_mount(
            {
                "projectId": DEFAULT_PROJECT_ID,
                "hostSpaceId": "space_default",
                "mountedSpaceId": shared_space.id,
                "mountMode": "bidirectional",
            }
        )
        for relation in ("mount", "read", "write"):
            collaboration_repository.create_permission_tuple(
                {
                    "projectId": DEFAULT_PROJECT_ID,
                    "subject": subject,
                    "relation": relation,
                    "resource": f"space:{shared_space.id}",
                }
            )
        anchor_node = _create_context_node(
            node_repository,
            branch_id=shared_branch.id,
            space_id=shared_space.id,
            title="Shared Recovery Anchor",
            content="共享空间中的恢复锚点要求主任务在挂载后读取多模态证据，并在恢复链中保留 safe-stop 关键信息。",
        )
    return {
        "subject": subject,
        "spaceId": shared_space.id,
        "branchId": shared_branch.id,
        "anchorNodeId": anchor_node["id"],
    }


def _seed_training_prompt_assets(case_name: str) -> dict[str, Any]:
    workspace_root = resolve_workspace_root()
    state_dir = ensure_state_subdir("evaluations/m9-training", workspace_root)
    compiled_messages_path = state_dir / f"{case_name}-compiled.json"
    request_path = state_dir / f"{case_name}-request.json"
    response_path = state_dir / f"{case_name}-response.json"
    write_json(
        compiled_messages_path,
        {
            "messages": [
                {
                    "role": "user",
                    "content": "请把共享空间里的恢复证据沉淀成可用于蒸馏验证的数据样本。",
                }
            ]
        },
    )
    write_json(request_path, {"input": "shared memory recovery dataset"})
    write_json(response_path, {"rawResponse": {"text": "dataset version should preserve shared multimodal recovery evidence"}})

    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        prompt_repository = PromptAssetRepository(session)
        runtime_repository = RuntimeRepository(session)
        artifact = prompt_repository.create_prompt_compile_artifact(
            {
                "projectId": DEFAULT_PROJECT_ID,
                "promptProfileVersionId": f"prompt_profile_{case_name}",
                "runType": "main",
                "taskType": "analysis",
                "registeredTools": [
                    {"name": "shared_memory.describe_mounts"},
                    {"name": "training_lab.prepare_dataset"},
                ],
                "compiledMessagesRef": {
                    "type": "file",
                    "locator": relative_workspace_path(compiled_messages_path, workspace_root),
                },
                "contentHash": f"hash_{case_name}",
            }
        )
        invocation = runtime_repository.create_model_invocation(
            {
                "projectId": DEFAULT_PROJECT_ID,
                "requestedModel": "gpt-5.4",
                "requestedProvider": "copilot",
                "resolvedModel": "gpt-5.4",
                "resolvedProvider": "copilot",
                "status": "completed",
                "promptCompileArtifactId": artifact.id,
                "requestRef": {
                    "type": "file",
                    "locator": relative_workspace_path(request_path, workspace_root),
                },
                "responseRef": {
                    "type": "file",
                    "locator": relative_workspace_path(response_path, workspace_root),
                },
                "inputTokensUsed": 48,
                "outputTokensUsed": 96,
                "costUsed": 0.03,
            }
        )
    return {
        "promptCompileArtifactId": artifact.id,
        "modelInvocationId": invocation.id,
    }


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
        prompt_repository = PromptAssetRepository(session)
        runtime_repository = RuntimeRepository(session)
        persisted_task = repository.get_task(task["id"])
        invocations = runtime_repository.list_model_invocations(task_id=task["id"], limit=5)
        prompt_artifact = None
        if invocations and invocations[0].prompt_compile_artifact_id:
            prompt_artifact = prompt_repository.get_prompt_compile_artifact(invocations[0].prompt_compile_artifact_id)

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

    request_payload = _read_external_ref_json(invocation.request_ref, resolve_workspace_root())
    response_payload = _read_external_ref_json(invocation.response_ref, resolve_workspace_root())
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
        "promptCompileArtifactId": invocation.prompt_compile_artifact_id,
    }
    if invocation.prompt_compile_artifact_id and prompt_artifact is None:
        raise RuntimeError(f"prompt compile artifact missing for invocation {invocation.id}")
    return {
        **live_summary,
        "liveScenario": live_summary,
        "assistantPreview": normalize_excerpt(str(result_payload.get("assistantText") or ""), 240),
        "requestPayload": request_payload,
        "responsePayload": response_payload,
    }


def _run_live_llm_tool_case(case: dict[str, Any] | None = None) -> dict[str, Any]:
    from fastapi.testclient import TestClient
    from yggdrasil_agent_runtime.app import app as runtime_app
    from yggdrasil_worker.registry import run_worker_once
    from .llm_runtime import load_runtime_candidate_models

    case_payload = dict(case or {})
    task_id = str(case_payload.get("taskId") or new_id("task", "m8-live-tool-evaluation", stable=False))
    requested_provider = str(case_payload.get("requestedProvider") or "longcat")
    requested_model = str(case_payload.get("requestedModel") or "LongCat-Flash-Lite")
    candidate_models = [
        dict(candidate)
        for candidate in load_runtime_candidate_models() or []
        if str(candidate.get("provider") or "") == requested_provider and str(candidate.get("model") or "") == requested_model
    ]
    require_live = bool(case_payload.get("requireLive", False))
    if require_live and not candidate_models:
        raise RuntimeError(f"requested live candidate is unavailable: {requested_provider}/{requested_model}")

    task = _seed_runtime_task(task_id)
    _seed_tool_case_memory(task_id)
    client = TestClient(runtime_app)
    start_payload = {
        "currentFocus": str(case_payload.get("currentFocus") or "M8 live tool validation"),
        "currentObjective": str(
            case_payload.get("currentObjective")
            or "Recover the archived runtime changes from durable branch memory and prepare a safe-stop retain plan for the next run under a 160 token budget."
        ),
        "currentContext": case_payload.get("currentContext")
        or [
            {
                "id": "ctx_handoff_goal",
                "title": "handoff target",
                "content": "The final note must name the archived runtime changes and include a concrete retain plan for the next run.",
                "importance": 0.98,
            },
            {
                "id": "ctx_handoff_budget",
                "title": "handoff budget",
                "content": "The safe-stop package should fit within roughly 160 retained tokens and prioritize objective, invocation summary, and pruning narrative.",
                "importance": 0.87,
            },
            {
                "id": "ctx_noise",
                "title": "noise",
                "content": "Older brainstorming fragments can be dropped if they do not help the next run resume safely.",
                "importance": 0.12,
            },
        ],
        "protectedItems": case_payload.get("protectedItems") or [{"kind": "node", "id": "ctx_handoff_goal"}],
        "allowModelFallback": bool(case_payload.get("allowFallback", True)),
        "temperature": float(case_payload.get("temperature") or 0.1),
        "maxTokens": int(case_payload.get("maxTokens") or 420),
    }
    if candidate_models:
        start_payload["candidateModels"] = candidate_models
    started = client.post(f"/runtime/tasks/{task['id']}/start", json=start_payload)
    if started.status_code != 202:
        raise RuntimeError(f"live tool evaluation start failed: {started.text}")

    processed = run_worker_once("agent-runtime")
    result_payload = dict(processed.get("result") or {})
    if result_payload.get("status") != "completed":
        raise RuntimeError(f"live tool evaluation worker failed: {json.dumps(processed, ensure_ascii=False)}")

    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        repository = TaskRepository(session)
        prompt_repository = PromptAssetRepository(session)
        runtime_repository = RuntimeRepository(session)
        persisted_task = repository.get_task(task["id"])
        invocations = runtime_repository.list_model_invocations(task_id=task["id"], limit=5)
        prompt_artifact = None
        if invocations and invocations[0].prompt_compile_artifact_id:
            prompt_artifact = prompt_repository.get_prompt_compile_artifact(invocations[0].prompt_compile_artifact_id)

    if not invocations:
        raise RuntimeError("live tool evaluation did not persist any model invocation")
    invocation = invocations[0]
    if require_live and invocation.status != "completed":
        raise RuntimeError(f"live tool provider invocation did not complete: {invocation.status}")
    if require_live and invocation.resolved_provider not in {requested_provider, str(case_payload.get('providerAlias') or '')}:
        raise RuntimeError(
            f"live tool provider mismatch: expected {requested_provider}, got {invocation.resolved_provider or 'unknown'}"
        )

    request_payload = _read_external_ref_json(invocation.request_ref, resolve_workspace_root())
    response_payload = _read_external_ref_json(invocation.response_ref, resolve_workspace_root())
    tool_executions = response_payload.get("toolExecutions") if isinstance(response_payload, dict) else []
    tool_names = [
        str((execution.get("tool") or {}).get("name"))
        for execution in tool_executions
        if isinstance(execution, dict) and (execution.get("tool") or {}).get("name")
    ]
    required_tools = [str(name) for name in case_payload.get("requiredTools") or ["text_memory.retrieve", "context_pruning.plan"]]
    missing_tools = [name for name in required_tools if name not in tool_names]
    if missing_tools:
        raise RuntimeError(f"live tool evaluation did not execute required tools: {', '.join(missing_tools)}")
    if invocation.prompt_compile_artifact_id and prompt_artifact is None:
        raise RuntimeError(f"prompt compile artifact missing for invocation {invocation.id}")

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
        "promptCompileArtifactId": invocation.prompt_compile_artifact_id,
        "toolExecutionNames": tool_names,
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


def _run_m9_shared_multimodal_reasoning_case(case: dict[str, Any] | None = None) -> dict[str, Any]:
    from yggdrasil_memory_organizer.plugin import MemoryOrganizerModule
    from yggdrasil_multimodal_memory.plugin import MultimodalMemoryModule
    from yggdrasil_relation_discovery.plugin import RelationDiscoveryModule
    from yggdrasil_shared_memory.plugin import describe_mounts_tool, plugin as shared_memory_plugin
    from yggdrasil_training_lab.plugin import TrainingLabModule

    case_payload = dict(case or {})
    question = str(
        case_payload.get("query")
        or "为什么主任务必须挂载共享空间中的多模态恢复证据，并把这些证据通过关联发现沉淀为 dataset version 与 model artifact，而不是只保留一条摘要？"
    )
    expected_keywords = [str(keyword) for keyword in case_payload.get("expectedKeywords") or []]
    transcript = _read_text_fixture(str(case_payload.get("fixture") or "m9_multimodal_shared_evidence.txt"))
    shared_setup = _seed_shared_space_mount()
    _seed_training_prompt_assets("m9-shared-multimodal")

    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        node_repository = NodeRepository(session)
        shared_related_node = _create_context_node(
            node_repository,
            branch_id=shared_setup["branchId"],
            space_id=shared_setup["spaceId"],
            title="Distillation Readiness Note",
            content="关联发现表明恢复步骤、共享空间证据、多模态摘要与 dataset version / model artifact 之间必须保留图谱连接。",
        )
        low_value_node = _create_context_node(
            node_repository,
            branch_id=DEFAULT_BRANCH_ID,
            space_id="space_default",
            title="Temporary Scratchpad",
            content="临时草稿，后续应由软遗忘治理压缩。",
        )
        node_repository.append_version(
            low_value_node["id"],
            {
                "importance": 0.05,
                "stability": 0.1,
                "accessScore": 0.0,
                "feedforwardScore": 0.0,
                "changeReason": "m9-acceptance-low-value",
                "updatedBy": {"type": "agent", "id": "evaluation"},
            },
        )

    ingest_result = MultimodalMemoryModule().ingest_asset(
        {
            "mediaType": "audio",
            "sourceText": transcript,
            "spaceId": shared_setup["spaceId"],
            "branchId": shared_setup["branchId"],
            "ownerNodeId": shared_setup["anchorNodeId"],
            "executionContext": {
                "projectId": DEFAULT_PROJECT_ID,
                "spaceId": shared_setup["spaceId"],
                "branchId": shared_setup["branchId"],
                "actor": {"type": "module", "id": "evaluation"},
            },
        }
    )
    describe_result = describe_mounts_tool(
        {
            "executionContext": {
                "projectId": DEFAULT_PROJECT_ID,
                "spaceId": "space_default",
                "branchId": DEFAULT_BRANCH_ID,
                "ownerProfileId": "identity_profile_default",
                "subject": shared_setup["subject"],
            }
        }
    )
    expanded = shared_memory_plugin.expand_retrieval(
        {
            "executionContext": {
                "projectId": DEFAULT_PROJECT_ID,
                "spaceId": "space_default",
                "branchId": DEFAULT_BRANCH_ID,
                "ownerProfileId": "identity_profile_default",
                "subject": shared_setup["subject"],
                "rootMount": {"spaceId": "space_default"},
            }
        }
    )
    scan_result = RelationDiscoveryModule().scan_branch_relations({"branchId": shared_setup["branchId"]})
    organizer_preview = MemoryOrganizerModule().apply_soft_forgetting(
        {
            "branchId": DEFAULT_BRANCH_ID,
            "targetCount": 1,
            "dryRun": True,
        }
    )
    organizer_result = MemoryOrganizerModule().apply_soft_forgetting(
        {
            "branchId": DEFAULT_BRANCH_ID,
            "targetCount": 1,
            "dryRun": False,
        }
    )
    training_lab = TrainingLabModule()
    dataset_result = training_lab.prepare_dataset(
        {
            "datasetName": "m9_acceptance_shared_reasoning",
            "branchId": shared_setup["branchId"],
            "maxRows": 12,
            "includeMemoryNodes": True,
        }
    )
    model_result = training_lab.stage_model_artifact(
        {
            "datasetVersionId": dataset_result["datasetVersion"]["id"],
            "baseModel": "gpt-5.4",
            "tuningMethod": "distillation",
            "minimumRows": 1,
        }
    )

    context_blocks = [
        (
            "共享空间挂载证据: 主任务已挂载共享空间，并通过 mounted branch 读取恢复材料；"
            f"accessible mounts={len(describe_result.get('accessibleMounts') or [])}。"
        ),
        (
            "多模态证据: "
            + str(ingest_result["summaryNode"].get("content") or "")
        ),
        (
            "关联与实验证据: "
            + str(scan_result.get("summary") or "")
            + f" dataset version={dataset_result['datasetVersion']['version']}"
            + f" model artifact={model_result['modelArtifact']['status']}"
        ),
        (
            "软遗忘治理: "
            + str(organizer_result.get("summary") or "")
        ),
    ]
    answer = _generate_strategy_answer(case_payload, question, "m9-shared-multimodal", context_blocks)
    answer_text = str(answer.get("outputText") or "")
    answer_coverage = _coverage_ratio(answer_text, expected_keywords)
    context_coverage = _coverage_ratio("\n\n".join(context_blocks), expected_keywords)
    combined_score = round(context_coverage * 0.7 + answer_coverage * 0.3, 4)

    if not describe_result.get("accessibleMounts"):
        raise RuntimeError("shared mount description did not expose any accessible mounts")
    if not expanded.get("nodes"):
        raise RuntimeError("mounted retrieval expansion did not return any nodes")
    if ingest_result.get("segmentCount", 0) < 1:
        raise RuntimeError("multimodal ingestion did not create any segments")
    if not scan_result.get("createdEdges"):
        raise RuntimeError("relation discovery did not materialize any latent edges")
    if organizer_preview.get("candidates", [{}])[0].get("nodeId") != low_value_node["id"]:
        raise RuntimeError("memory organizer did not target the expected low-value node")
    if dataset_result["datasetVersion"].get("rowCount", 0) < 1:
        raise RuntimeError("training lab did not create a dataset row")
    if model_result["modelArtifact"].get("status") != "validated":
        raise RuntimeError("training lab did not validate the staged model artifact")
    if combined_score < 0.75:
        raise RuntimeError(f"m9 shared reasoning answer coverage is too low: {combined_score}")

    return {
        "question": question,
        "expectedKeywords": expected_keywords,
        "answerPreview": normalize_excerpt(answer_text, 240),
        "answerCoverage": answer_coverage,
        "contextCoverage": context_coverage,
        "combinedScore": combined_score,
        "mountedSpaceCount": len(describe_result.get("accessibleMounts") or []),
        "expandedNodeCount": len(expanded.get("nodes") or []),
        "segmentCount": int(ingest_result.get("segmentCount") or 0),
        "createdEdgeCount": len(scan_result.get("createdEdges") or []),
        "datasetVersionId": dataset_result["datasetVersion"]["id"],
        "datasetRowCount": dataset_result["datasetVersion"]["rowCount"],
        "modelArtifactId": model_result["modelArtifact"]["id"],
        "modelArtifactStatus": model_result["modelArtifact"]["status"],
        "softForgotNodeId": organizer_result["adjustedNodes"][0]["nodeId"],
        "usedFeatures": [
            "shared-memory.describe-mounts",
            "shared-memory.expand-retrieval",
            "multimodal-memory.ingest-asset",
            "relation-discovery.scan-branch",
            "memory-organizer.soft-forgetting",
            "training-lab.prepare-dataset",
            "training-lab.stage-model-artifact",
        ],
        "liveScenario": {
            "question": question,
            "combinedScore": combined_score,
            "usedFeatures": 7,
        },
        "relatedNodeId": shared_related_node["id"],
    }


def _run_m9_pause_resume_memory_tree_case(case: dict[str, Any] | None = None) -> dict[str, Any]:
    from fastapi.testclient import TestClient
    from yggdrasil_agent_runtime.app import app as runtime_app
    from yggdrasil_worker.registry import run_worker_once

    case_payload = dict(case or {})
    question = str(
        case_payload.get("query")
        or "在挂载共享记忆树后，任务必须在 safe-stop 中保留哪些上下文，恢复后又如何继续完成最终写入？"
    )
    expected_keywords = [str(keyword) for keyword in case_payload.get("expectedKeywords") or []]
    shared_setup = _seed_shared_space_mount()

    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        node_repository = NodeRepository(session)
        task_repository = TaskRepository(session)
        _create_context_node(
            node_repository,
            branch_id=shared_setup["branchId"],
            space_id=shared_setup["spaceId"],
            title="Mounted Recovery Branch",
            content="挂载记忆树中的恢复分支要求 safe-stop 保留 snapshot、protectedItems 与 resume token。",
        )
        task = task_repository.create_task(
            {
                "id": "eval_task_m9_pause_resume",
                "title": "M9 Pause Resume Acceptance",
                "goal": "Validate mounted-memory safe-stop and seamless resume.",
                "status": "draft",
                "currentObjective": question,
                "currentFocus": "m9-pause-resume-acceptance",
                "resumeMessage": "恢复后继续完成跨空间恢复总结。",
                "budgetState": {
                    "tokenBudgetTotal": 1400,
                    "costBudgetTotal": 5.0,
                },
            }
        )

    client = TestClient(runtime_app)
    started = client.post(
        f"/runtime/tasks/{task.id}/start",
        json={
            "currentFocus": "执行挂载记忆树任务的 safe-stop 验收",
            "currentObjective": question,
            "currentContext": [
                {
                    "id": "ctx_resume_keep",
                    "title": "Safe Stop Plan",
                    "content": "safe-stop 必须保留 protectedItems、snapshot token、mounted summary 与恢复后的 followup actions。",
                    "importance": 0.98,
                },
                {
                    "id": "ctx_resume_noise",
                    "title": "Noise",
                    "content": "低价值草稿应在恢复后继续压缩。",
                    "importance": 0.1,
                },
            ],
            "protectedItems": [{"kind": "node", "id": "ctx_resume_keep"}],
            "activeCapabilities": ["shared-memory"],
        },
    )
    if started.status_code != 202:
        raise RuntimeError(f"m9 pause-resume start failed: {started.text}")
    paused = client.post(
        f"/runtime/tasks/{task.id}/pause-request",
        json={
            "reason": "m9-acceptance-safe-stop",
            "resumeMessage": "恢复后继续完成挂载记忆树总结。",
        },
    )
    if paused.status_code != 202:
        raise RuntimeError(f"m9 pause request failed: {paused.text}")
    first = run_worker_once("agent-runtime")
    if first.get("result", {}).get("status") != "paused":
        raise RuntimeError(f"m9 pause step failed: {json.dumps(first, ensure_ascii=False)}")
    snapshot = first["result"]["snapshot"]
    root_mount_preview = snapshot.get("rootMountPreview") or {}
    if not root_mount_preview.get("accessibleMounts"):
        raise RuntimeError("m9 pause snapshot did not include any mounted shared space")

    resumed = client.post(
        f"/runtime/tasks/{task.id}/resume",
        json={
            "resumeToken": snapshot["resumeToken"],
            "nextObjective": "恢复后完成跨空间恢复说明并写入最终执行记录。",
        },
    )
    if resumed.status_code != 202:
        raise RuntimeError(f"m9 resume request failed: {resumed.text}")
    second = run_worker_once("agent-runtime")
    if second.get("result", {}).get("status") != "completed":
        raise RuntimeError(f"m9 resume completion failed: {json.dumps(second, ensure_ascii=False)}")

    rehydration = second["result"].get("rehydration") or {}
    restored_state = rehydration.get("restoredState") or {}
    context_blocks = [
        (
            "记忆树 safe-stop: "
            f"snapshot={snapshot['id']} safe-stop={snapshot['safeToPause']} protectedItems preserved before pause."
        ),
        (
            "挂载恢复上下文: "
            f"mountedSpaces={len(root_mount_preview.get('accessibleMounts') or [])} mountedRefs={len(root_mount_preview.get('mountedNodeRefs') or [])}."
        ),
        (
            "无感恢复: "
            + "; ".join(str(summary) for summary in rehydration.get("summaries") or [])
            + f" restoredContext={len(restored_state.get('currentContext') or [])} resume actions={len(rehydration.get('followupActions') or [])}"
        ),
    ]
    answer = _generate_strategy_answer(case_payload, question, "m9-pause-resume", context_blocks)
    answer_text = str(answer.get("outputText") or "")
    answer_coverage = _coverage_ratio(answer_text, expected_keywords)
    context_coverage = _coverage_ratio("\n\n".join(context_blocks), expected_keywords)
    combined_score = round(context_coverage * 0.7 + answer_coverage * 0.3, 4)

    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        node_repository = NodeRepository(session)
        persisted_task = task_repository.get_task(task.id)
        execution_notes = [
            node
            for node in node_repository.list_nodes(branch_id=persisted_task.branch_id, limit=200)
            if node.node_type == "task" and node.parent_id == persisted_task.execution_root_node_id
        ]
        snapshots = task_repository.list_snapshots(task.id)
    if combined_score < 0.75:
        raise RuntimeError(f"m9 pause-resume answer coverage is too low: {combined_score}")
    if persisted_task is None or persisted_task.status != "completed":
        raise RuntimeError("m9 pause-resume task did not reach completed status")
    if len(execution_notes) < 2:
        raise RuntimeError("m9 pause-resume did not persist both pre-pause and post-resume execution notes")
    if not snapshots or snapshots[0].status != "consumed":
        raise RuntimeError("m9 pause-resume snapshot was not consumed on resume")

    return {
        "question": question,
        "expectedKeywords": expected_keywords,
        "answerPreview": normalize_excerpt(answer_text, 240),
        "answerCoverage": answer_coverage,
        "contextCoverage": context_coverage,
        "combinedScore": combined_score,
        "pauseStatus": first["result"]["status"],
        "resumeStatus": second["result"]["status"],
        "snapshotId": snapshot["id"],
        "mountedSpaceCount": len(root_mount_preview.get("accessibleMounts") or []),
        "mountedRefCount": len(root_mount_preview.get("mountedNodeRefs") or []),
        "rehydratedContextCount": len(restored_state.get("currentContext") or []),
        "rehydratedProtectedItemCount": len(restored_state.get("protectedItems") or []),
        "followupActionCount": len(rehydration.get("followupActions") or []),
        "executionNoteCount": len(execution_notes),
        "usedFeatures": [
            "shared-memory.mount-root",
            "pause-resume.prepare",
            "pause-resume.rehydrate",
            "runtime-kernel.pause-request",
            "runtime-kernel.resume",
        ],
        "liveScenario": {
            "question": question,
            "combinedScore": combined_score,
            "usedFeatures": 5,
        },
    }


def _run_m9_control_plane_resource_surface_case(case: dict[str, Any] | None = None) -> dict[str, Any]:
    from fastapi.testclient import TestClient
    from yggdrasil_core_api.app import app

    case_payload = dict(case or {})
    client = TestClient(app)
    dataset_name = str(case_payload.get("datasetName") or f"m9_control_plane_{utc_now().strftime('%H%M%S')}")
    ingested = client.post(
        "/assets/ingest",
        json={
            "mediaType": "document",
            "sourceText": str(
                case_payload.get("sourceText")
                or "共享空间恢复记录、多模态素材摘要和训练实验样本必须作为正式资源暴露到控制面，并能被后续评测与运维链路读取。"
            ),
            "spaceId": "space_default",
            "branchId": DEFAULT_BRANCH_ID,
        },
    )
    if ingested.status_code != 201:
        raise RuntimeError(f"asset ingestion failed: {ingested.text}")
    asset_payload = ingested.json()
    asset_id = str(asset_payload["asset"]["id"])

    prepared = client.post(
        "/training/dataset-versions/prepare",
        json={
            "datasetName": dataset_name,
            "maxRows": int(case_payload.get("maxRows") or 12),
            "includeMemoryNodes": True,
        },
    )
    if prepared.status_code != 201:
        raise RuntimeError(f"dataset preparation failed: {prepared.text}")
    dataset_payload = prepared.json()
    dataset_id = str(dataset_payload["datasetVersion"]["id"])

    staged = client.post(
        "/training/model-artifacts/stage",
        json={
            "datasetVersionId": dataset_id,
            "baseModel": str(case_payload.get("baseModel") or "gpt-5.4"),
            "tuningMethod": str(case_payload.get("tuningMethod") or "distillation"),
            "minimumRows": 1,
        },
    )
    if staged.status_code != 201:
        raise RuntimeError(f"model artifact staging failed: {staged.text}")
    artifact_payload = staged.json()
    artifact_id = str(artifact_payload["modelArtifact"]["id"])

    assets = client.get("/assets", params={"limit": 50})
    asset_detail = client.get(f"/assets/{asset_id}")
    datasets = client.get("/training/dataset-versions", params={"limit": 50})
    dataset_detail = client.get(f"/training/dataset-versions/{dataset_id}")
    artifacts = client.get("/training/model-artifacts", params={"limit": 50})
    artifact_detail = client.get(f"/training/model-artifacts/{artifact_id}")
    responses = [assets, asset_detail, datasets, dataset_detail, artifacts, artifact_detail]
    if any(response.status_code != 200 for response in responses):
        raise RuntimeError("control-plane resource surface returned non-200 responses")

    asset_count = len(assets.json().get("assets") or [])
    dataset_count = len(datasets.json().get("datasetVersions") or [])
    artifact_count = len(artifacts.json().get("modelArtifacts") or [])
    if asset_count < 1 or dataset_count < 1 or artifact_count < 1:
        raise RuntimeError("control-plane resource lists did not expose the seeded resources")
    if len(asset_detail.json().get("segments") or []) < 1:
        raise RuntimeError("asset detail did not expose segments")
    if len(dataset_detail.json().get("previewRows") or []) < 1:
        raise RuntimeError("dataset detail did not expose preview rows")
    if not artifact_detail.json().get("metrics"):
        raise RuntimeError("model artifact detail did not expose validation metrics")

    return {
        "assetId": asset_id,
        "segmentCount": len(asset_detail.json().get("segments") or []),
        "datasetVersionId": dataset_id,
        "datasetRowCount": int(dataset_payload["datasetVersion"].get("rowCount") or 0),
        "modelArtifactId": artifact_id,
        "modelArtifactStatus": artifact_payload["modelArtifact"].get("status"),
        "resourceCounts": {
            "assets": asset_count,
            "datasets": dataset_count,
            "artifacts": artifact_count,
        },
    }


def _run_m9_prompt_control_plane_case(case: dict[str, Any] | None = None) -> dict[str, Any]:
    from fastapi.testclient import TestClient
    from yggdrasil_core_api.app import app

    case_payload = dict(case or {})
    seeded = _seed_training_prompt_assets(str(case_payload.get("seedName") or "m9-prompt-control-plane"))
    client = TestClient(app)
    app_id = str(case_payload.get("appId") or "yggdrasil.app.software-factory")

    prompt_profiles = client.get("/prompting/prompt-profiles", params={"appId": app_id})
    seed_templates = client.get("/prompting/seed-templates", params={"appId": app_id})
    registered_tools = client.get(
        "/prompting/registered-tools",
        params={"activeCapabilities": str(case_payload.get("activeCapabilities") or "text-memory,shared-memory,training-lab")},
    )
    compile_artifacts = client.get("/prompting/compile-artifacts", params={"limit": 50})
    compile_artifact_detail = client.get(f"/prompting/compile-artifacts/{seeded['promptCompileArtifactId']}")
    preview = client.post(
        "/prompting/compile-preview",
        json={
            "appId": app_id,
            "runType": "main",
            "taskType": "coding",
            "activeCapabilities": ["text-memory", "shared-memory", "training-lab"],
            "task": {
                "title": "PromptOps Evaluation",
                "goal": "Expose the compiled prompt through the control plane.",
                "currentFocus": "prompt-control-plane",
                "currentObjective": "Verify prompt profile, seed template, tool registration, and compiled messages.",
                "resumeMessage": "继续查看 prompt 编译结果。",
            },
            "request": {
                "currentFocus": "prompt-control-plane",
                "currentObjective": "Verify prompt profile, seed template, tool registration, and compiled messages.",
                "responseRequirements": "输出必须包含风险与下一步。",
            },
        },
    )
    responses = [prompt_profiles, seed_templates, registered_tools, compile_artifacts, compile_artifact_detail, preview]
    if any(response.status_code not in {200, 201} for response in responses):
        raise RuntimeError("prompt control-plane surface returned non-200 responses")

    profile_list = prompt_profiles.json().get("promptProfiles") or []
    template_list = seed_templates.json().get("seedTemplates") or []
    tool_list = registered_tools.json().get("registeredTools") or []
    artifact_list = compile_artifacts.json().get("promptCompileArtifacts") or []
    preview_payload = preview.json().get("compiledPrompt") or {}
    if len(profile_list) < 2:
        raise RuntimeError("prompt control plane did not expose prompt profiles")
    if len(template_list) < 3:
        raise RuntimeError("prompt control plane did not expose seed templates")
    if not any(str(tool.get("name") or "") == "training_lab.prepare_dataset" for tool in tool_list):
        raise RuntimeError("prompt control plane did not expose the expected registered tool")
    if not any(str(artifact.get("id") or "") == seeded["promptCompileArtifactId"] for artifact in artifact_list):
        raise RuntimeError("prompt control plane did not expose the seeded compile artifact")
    if len((compile_artifact_detail.json().get("compiledMessages") or {}).get("messages") or []) < 1:
        raise RuntimeError("compile artifact detail did not expose compiled messages")
    if preview_payload.get("promptProfileId") != "yggdrasil.software-factory.main-agent":
        raise RuntimeError("prompt preview did not select the software-factory main prompt profile")
    if preview_payload.get("seedTemplateId") != "yggdrasil.seed.coding.inherit-project":
        raise RuntimeError("prompt preview did not select the expected coding seed template")

    return {
        "appId": app_id,
        "promptProfileCount": len(profile_list),
        "seedTemplateCount": len(template_list),
        "registeredToolCount": len(tool_list),
        "promptCompileArtifactId": seeded["promptCompileArtifactId"],
        "previewScenario": preview_payload.get("scenario"),
        "previewMessageCount": len(preview_payload.get("messages") or []),
    }


SCENARIO_HANDLERS = {
    "m4.memory_import_retrieval": _run_memory_import_case,
    "m5.main_agent_pause_resume": _run_main_agent_case,
    "m6.subagent_pr_loop": _run_subagent_pr_case,
    "m8.live_llm_task_execution": _run_live_llm_task_case,
    "m8.live_llm_tool_task": _run_live_llm_tool_case,
    "m8.memory_strategy_compare": _run_memory_strategy_compare_case,
    "m9.control_plane_resource_surface": _run_m9_control_plane_resource_surface_case,
    "m9.prompt_control_plane": _run_m9_prompt_control_plane_case,
    "m9.shared_multimodal_reasoning": _run_m9_shared_multimodal_reasoning_case,
    "m9.pause_resume_memory_tree": _run_m9_pause_resume_memory_tree_case,
}


def run_evaluation_suite(suite_id: str, workspace_root: Path | None = None) -> dict[str, Any]:
    definition = get_evaluation_suite_definition(suite_id, workspace_root)
    fallback_context = None
    try:
        runtime, run = _prepare_suite_run(definition, suite_id, workspace_root)
    except Exception:
        fallback_context = local_evaluation_runtime_environment(workspace_root)
        fallback_context.__enter__()
        runtime, run = _prepare_suite_run(definition, suite_id, workspace_root)

    try:
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
                }
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
    finally:
        if fallback_context is not None:
            fallback_context.__exit__(None, None, None)