from ._common import *  # noqa: F403,F401
from ..domain import PromptProfileVersionRecord
from contextlib import nullcontext

_SCHEMA_TEMPLATE_LOCK = threading.Lock()
_SCHEMA_TEMPLATE_DIR: tempfile.TemporaryDirectory[str] | None = None
_SCHEMA_TEMPLATE_DB: str | None = None

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

def _get_schema_template_db() -> str:
    """Build a schema-only SQLite file once per process, then reuse it via file copy."""
    global _SCHEMA_TEMPLATE_DIR, _SCHEMA_TEMPLATE_DB
    if _SCHEMA_TEMPLATE_DB is not None:
        return _SCHEMA_TEMPLATE_DB
    with _SCHEMA_TEMPLATE_LOCK:
        if _SCHEMA_TEMPLATE_DB is not None:
            return _SCHEMA_TEMPLATE_DB
        _SCHEMA_TEMPLATE_DIR = tempfile.TemporaryDirectory(prefix="yggdrasil-eval-schema-")
        template_path = Path(_SCHEMA_TEMPLATE_DIR.name) / "schema-template.db"
        saved = {k: os.environ.get(k) for k in ("YGGDRASIL_DATABASE_URL", "YGGDRASIL_AUTO_CREATE_SCHEMA")}
        os.environ["YGGDRASIL_DATABASE_URL"] = f"sqlite+pysqlite:///{template_path.as_posix()}"
        os.environ["YGGDRASIL_AUTO_CREATE_SCHEMA"] = "0"
        reset_persistence_runtime()
        initialize_schema()
        reset_persistence_runtime()
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        _SCHEMA_TEMPLATE_DB = str(template_path)
    return _SCHEMA_TEMPLATE_DB

@contextmanager
def isolated_runtime_environment(*, disable_live_llm: bool = True) -> Iterator[None]:
    managed_keys = [
        "YGGDRASIL_DATABASE_URL",
        "YGGDRASIL_AUTO_CREATE_SCHEMA",
        "YGGDRASIL_COORDINATION_BACKEND",
        "YGGDRASIL_REDIS_URL",
        "YGGDRASIL_STATE_ROOT",
        "YGGDRASIL_STATE_DIR",
        "YGGDRASIL_GIT_REPO_PATH",
        "YGGDRASIL_MCP_PROJECT_WORKSPACE",
        "YGGDRASIL_DISABLE_LIVE_LLM",
        "YGGDRASIL_EVAL_ACTIVE_SANDBOX_ROOT",
        "YGGDRASIL_EVAL_ACTIVE_WORKSPACE_ROOT",
        "YGGDRASIL_EVAL_ACTIVE_DB_PATH",
    ]
    previous = {key: os.environ.get(key) for key in managed_keys}
    template_db = _get_schema_template_db()
    preserve_sandbox = str(os.environ.get("YGGDRASIL_EVAL_PRESERVE_SANDBOX") or "").strip().lower() in {"1", "true", "yes", "on"}
    if preserve_sandbox:
        sandbox_root = resolve_state_dir() / "evaluation-sandboxes"
        sandbox_root.mkdir(parents=True, exist_ok=True)
        temp_root = sandbox_root / new_id("evalsandbox", utc_now().isoformat(), stable=False)
        temp_root.mkdir(parents=True, exist_ok=False)
        temp_dir_context = nullcontext(str(temp_root))
    else:
        temp_dir_context = tempfile.TemporaryDirectory(prefix="yggdrasil-eval-")
    with temp_dir_context as temp_dir:
        temp_root = Path(temp_dir)
        sandbox_workspace = prepare_runtime_workspace_sandbox(temp_root)
        db_path = temp_root / "evaluation.db"
        shutil.copy2(template_db, db_path)
        os.environ["YGGDRASIL_DATABASE_URL"] = f"sqlite+pysqlite:///{db_path.as_posix()}"
        os.environ["YGGDRASIL_AUTO_CREATE_SCHEMA"] = "0"
        os.environ["YGGDRASIL_COORDINATION_BACKEND"] = "memory"
        os.environ["YGGDRASIL_REDIS_URL"] = "redis://127.0.0.1:6390/15"
        os.environ["YGGDRASIL_STATE_ROOT"] = str((temp_root / ".yggdrasil").resolve())
        os.environ["YGGDRASIL_GIT_REPO_PATH"] = str(sandbox_workspace.resolve())
        os.environ["YGGDRASIL_MCP_PROJECT_WORKSPACE"] = str(sandbox_workspace.resolve())
        os.environ["YGGDRASIL_EVAL_ACTIVE_SANDBOX_ROOT"] = str(temp_root.resolve())
        os.environ["YGGDRASIL_EVAL_ACTIVE_WORKSPACE_ROOT"] = str(sandbox_workspace.resolve())
        os.environ["YGGDRASIL_EVAL_ACTIVE_DB_PATH"] = str(db_path.resolve())
        if disable_live_llm:
            os.environ["YGGDRASIL_DISABLE_LIVE_LLM"] = "1"
        else:
            os.environ.pop("YGGDRASIL_DISABLE_LIVE_LLM", None)
        os.environ.pop("YGGDRASIL_STATE_DIR", None)
        close_mcp_bridge_sessions()
        reset_persistence_runtime()
        ensure_workspace_bootstrap()
        try:
            yield
        finally:
            close_mcp_bridge_sessions()
            reset_persistence_runtime()
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
            reset_persistence_runtime()

@contextmanager
def local_evaluation_runtime_environment(workspace_root: Path | None = None, *, disable_live_llm: bool = True) -> Iterator[None]:
    managed_keys = [
        "YGGDRASIL_DATABASE_URL",
        "YGGDRASIL_AUTO_CREATE_SCHEMA",
        "YGGDRASIL_COORDINATION_BACKEND",
        "YGGDRASIL_REDIS_URL",
        "YGGDRASIL_STATE_ROOT",
        "YGGDRASIL_STATE_DIR",
        "YGGDRASIL_GIT_REPO_PATH",
        "YGGDRASIL_MCP_PROJECT_WORKSPACE",
        "YGGDRASIL_DISABLE_LIVE_LLM",
    ]
    previous = {key: os.environ.get(key) for key in managed_keys}
    with tempfile.TemporaryDirectory(prefix="yggdrasil-eval-local-") as temp_dir:
        temp_root = Path(temp_dir)
        sandbox_root = temp_root / ".yggdrasil"
        sandbox_root.mkdir(parents=True, exist_ok=True)
        sandbox_workspace = prepare_runtime_workspace_sandbox(temp_root, workspace_root)
        os.environ["YGGDRASIL_DATABASE_URL"] = f"sqlite+pysqlite:///{(sandbox_root / 'evaluation.db').as_posix()}"
        os.environ["YGGDRASIL_AUTO_CREATE_SCHEMA"] = "1"
        os.environ["YGGDRASIL_COORDINATION_BACKEND"] = "memory"
        os.environ["YGGDRASIL_REDIS_URL"] = "redis://127.0.0.1:6390/15"
        os.environ["YGGDRASIL_STATE_ROOT"] = str(sandbox_root.resolve())
        os.environ["YGGDRASIL_GIT_REPO_PATH"] = str(sandbox_workspace.resolve())
        os.environ["YGGDRASIL_MCP_PROJECT_WORKSPACE"] = str(sandbox_workspace.resolve())
        if disable_live_llm:
            os.environ["YGGDRASIL_DISABLE_LIVE_LLM"] = "1"
        else:
            os.environ.pop("YGGDRASIL_DISABLE_LIVE_LLM", None)
        os.environ.pop("YGGDRASIL_STATE_DIR", None)
        close_mcp_bridge_sessions()
        reset_persistence_runtime()
        initialize_schema()
        ensure_workspace_bootstrap()
        try:
            yield
        finally:
            close_mcp_bridge_sessions()
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

def _seed_runtime_task(
    task_id: str,
    *,
    app_id: str | None = None,
    title: str | None = None,
    goal: str | None = None,
    current_focus: str | None = None,
    current_objective: str | None = None,
    resume_message: str | None = None,
    token_budget_total: int | None = 1200,
    cost_budget_total: float | None = 5.0,
) -> dict[str, Any]:
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        payload = {
            "id": task_id,
            "title": title or "Evaluation Runtime Task",
            "goal": goal or "Validate the main-agent pause and resume closed loop.",
            "status": "draft",
            "currentObjective": current_objective or "complete the evaluation execution and enter safe-stop",
            "currentFocus": current_focus or "evaluation-runtime",
            "resumeMessage": resume_message or "resume the evaluation flow",
        }
        budget_state: dict[str, Any] = {}
        if token_budget_total is not None:
            budget_state["tokenBudgetTotal"] = int(token_budget_total)
        if cost_budget_total is not None:
            budget_state["costBudgetTotal"] = float(cost_budget_total)
        if budget_state:
            payload["budgetState"] = budget_state
        if app_id is not None:
            payload["appId"] = app_id
        task = task_repository.create_task(payload)
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
        prompt_repository.upsert_prompt_profile_version(
            PromptProfileVersionRecord(
                id=f"prompt_profile_{case_name}",
                promptProfileId=f"evaluation.{case_name}",
                name=f"evaluation.{case_name}",
                version="v1",
                runScope="any",
                body={"id": f"evaluation.{case_name}", "version": "v1"},
                contentHash=f"prompt-profile-{case_name}",
                createdAt=utc_now(),
            )
        )
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



__all__ = [name for name in globals() if not name.startswith('__')]

